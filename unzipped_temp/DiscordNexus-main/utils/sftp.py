"""
SFTP utility functions for server connections and file operations
"""
import os
import re
import logging
import asyncio
import datetime
import time
from io import StringIO

import paramiko
from paramiko.ssh_exception import SSHException, AuthenticationException

from config import SFTP_CONNECTION_SETTINGS, CSV_FILENAME_PATTERN, LOG_FILENAME

logger = logging.getLogger(__name__)

class SFTPClient:
    """SFTP client for connecting to game servers and retrieving files"""

    def __init__(self, host, port, username, password, server_id):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.server_id = server_id
        self.client = None
        self.sftp = None
        self.root_path = None
        self.connected = False
        self.last_error = None
        self._csv_cache = {}
        self._csv_cache_time = 0
        self._csv_cache_duration = 300  # Cache CSV file list for 5 minutes
        self.last_heartbeat = time.time()
        self.heartbeat_interval = 30  # 30 seconds
        self._cache_duration = 300  # 5 minute cache for directory structure
        self._dir_cache = {}
        self._last_cache_refresh = 0
        self._csv_pattern = re.compile(CSV_FILENAME_PATTERN)
        self._connection_timeout = 10  # 10 second timeout for operations


    async def connect(self):
        """Establish SFTP connection"""
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            self.client.connect(
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                **SFTP_CONNECTION_SETTINGS
            )

            self.sftp = self.client.open_sftp()
            logger.info(f"Connected to SFTP server: {self.host}:{self.port} for server {self.server_id}")

            await self.find_root_path()

            self.connected = True
            self.last_error = None
            return True

        except Exception as e:
            self.last_error = str(e)
            logger.error(f"Connection error: {e}", exc_info=True)
            self.connected = False
            return False

    async def find_root_path(self):
        """Find the root path containing server directory with optimized search"""
        try:
            current_path = '.'
            self.root_path = None

            # Create pattern for server directory
            ip_address = self.host.split(':')[0]
            server_pattern = f"{ip_address}_{self.server_id}"

            # Configure optimal depth for CSV files (root/serverid/actual1/deathlogs/worldX/)
            self.max_search_depth = 6
            self.world_dir_pattern = re.compile(r'^world_\d+$', re.IGNORECASE)

            # Add heartbeat monitoring with improved timeout handling
            self.last_heartbeat = time.time()
            self.heartbeat_interval = 30  # 30 seconds

            # Use cached directory listing if available and fresh
            current_time = time.time()
            if (current_path in self._dir_cache and 
                current_time - self._last_cache_refresh < self._cache_duration):
                items = self._dir_cache[current_path]
                logger.debug(f"Using cached directory listing for {current_path}")
            else:
                items = await self._list_dir_safe(current_path)
                self._dir_cache[current_path] = items
                self._last_cache_refresh = current_time

            logger.info(f"Searching for server directory matching pattern: {server_pattern}")
            logger.info(f"Found items in root: {items}")

            # Look for exact match first
            for item in items:
                if server_pattern.lower() in item.lower():
                    self.root_path = os.path.join(current_path, item)
                    logger.info(f"Found server directory: {self.root_path}")
                    return

            if not self.root_path:
                logger.warning(f"Could not find server directory matching {server_pattern}")
                self.root_path = current_path

        except Exception as e:
            logger.error(f"Error finding root path: {e}", exc_info=True)
            self.root_path = '.'

    async def get_latest_csv_file(self):
        """Get the most recent CSV file from any subdirectory with improved error handling"""
        retry_count = 0
        max_retries = 3

        while retry_count < max_retries:
            try:
                if not self.connected:
                    await self.connect()
                    if not self.connected:
                        return None

                self.last_heartbeat = time.time()
                current_time = time.time()

                # Check cache validity
                if (self._csv_cache and 
                    current_time - self._csv_cache_time < self._csv_cache_duration):
                    logger.debug("Using cached CSV file list")
                    if self._csv_cache.get('latest'):
                        return self._csv_cache['latest']

                try:
                    # Construct base paths to check
                    server_dir = f"{self.host.split(':')[0]}_{self.server_id}"
                    paths_to_check = [
                        os.path.join(".", server_dir, "actual1", "deathlogs"),
                        os.path.join(".", server_dir, "deathlogs")
                    ]

                    csv_files = []
                    paths_checked = set()

                    async def check_path(base_path, depth=0):
                        if depth > 10 or base_path in paths_checked:  # Prevent infinite recursion
                            return []

                        paths_checked.add(base_path)
                        found_files = []

                        try:
                            items = await self._list_dir_safe(base_path)
                            if not items:
                                return []

                            # First prioritize worldX directories
                            world_dirs = [item for item in items if re.match(r'^world_\d+$', item.lower())]

                            # Then check these world directories first
                            for world_dir in world_dirs:
                                full_path = os.path.join(base_path, world_dir)
                                if await self._is_dir_safe(full_path):
                                    subdir_files = await check_path(full_path, depth + 1)
                                    found_files.extend(subdir_files)

                            # Check for CSV files in current directory
                            csv_files = [item for item in items if re.match(CSV_FILENAME_PATTERN, item)]
                            found_files.extend([os.path.join(base_path, csv) for csv in csv_files])

                            # Only check other directories if we haven't found files
                            if not found_files:
                                other_dirs = [item for item in items if item not in world_dirs and await self._is_dir_safe(os.path.join(base_path, item))]
                                for other_dir in other_dirs:
                                    full_path = os.path.join(base_path, other_dir)
                                    subdir_files = await check_path(full_path, depth + 1)
                                    found_files.extend(subdir_files)

                        except Exception as e:
                            logger.warning(f"Error checking path {base_path}: {e}")

                        return found_files

                    # Check all potential paths
                    for deathlogs_path in paths_to_check:
                        logger.info(f"Searching for CSV files in {deathlogs_path}")
                        found_files = await check_path(deathlogs_path)
                        if found_files:
                            csv_files.extend(found_files)
                            logger.info(f"Found {len(found_files)} CSV files in {deathlogs_path}")

                    if not csv_files:
                        logger.warning(f"No CSV files found in {deathlogs_path}")
                        return None

                    # Sort by timestamp from filename
                    sorted_files = []
                    for file_path in csv_files:
                        try:
                            filename = os.path.basename(file_path)
                            # Parse timestamp from filename (YYYY.MM.DD-HH.MM.SS)
                            timestamp_str = filename.split('.csv')[0]
                            dt = datetime.datetime.strptime(timestamp_str, '%Y.%m.%d-%H.%M.%S')
                            sorted_files.append((file_path, dt.timestamp(), filename))
                            logger.info(f"Parsed CSV file: {filename} with timestamp {dt}")
                        except Exception as e:
                            logger.warning(f"Could not parse timestamp from {filename}: {e}")
                            # Use file modification time as fallback
                            try:
                                attrs = await asyncio.to_thread(lambda: self.sftp.stat(file_path))
                                sorted_files.append((file_path, attrs.st_mtime, filename))
                            except Exception:
                                sorted_files.append((file_path, 0, filename))

                    # Sort by timestamp (newest first)
                    sorted_files.sort(key=lambda x: float(x[1]), reverse=True)

                    if sorted_files:
                        latest_file = sorted_files[0][0]
                        logger.info(f"Using latest CSV file: {latest_file}")
                        self._csv_cache = {'latest': latest_file, 'time': current_time}
                        return latest_file

                    return None

                except Exception as e:
                    logger.error(f"Error getting latest CSV file: {e}", exc_info=True)
                    return None

            except Exception as e:
                logger.error(f"Error in get_latest_csv_file retry {retry_count + 1}: {e}")
                retry_count += 1
                await asyncio.sleep(2**retry_count)  # Exponential backoff
        return None

    async def _find_csv_files_recursive(self, directory, max_depth=6, current_depth=0):
        """Find all CSV files recursively with improved error handling"""
        if current_depth > max_depth:
            return []

        csv_files = []
        try:
            items = await self._list_dir_safe(directory)
            if not items:
                return []

            logger.info(f"Checking directory: {directory} (depth: {current_depth})")

            # Prioritize world directories and CSV files
            world_dirs = [item for item in items if 'world' in item.lower()]
            other_items = [item for item in items if item not in world_dirs]

            # Process world directories first
            for item in world_dirs + other_items:
                item_path = os.path.join(directory, item)

                # Check if it's a CSV file
                if item.lower().endswith('.csv'):
                    logger.info(f"Found CSV file: {item_path}")
                    csv_files.append(item_path)
                    continue

                # Check if it's a directory
                try:
                    if await self._is_dir_safe(item_path):
                        # Reduce depth counter for world directories to ensure full exploration
                        effective_depth = current_depth
                        if 'world' in item.lower():
                            effective_depth = max(0, current_depth - 1)

                        subdir_files = await self._find_csv_files_recursive(
                            item_path, max_depth, effective_depth
                        )
                        if subdir_files:
                            logger.info(f"Found {len(subdir_files)} CSV files in {item_path}")
                            csv_files.extend(subdir_files)
                except Exception as e:
                    logger.warning(f"Error checking subdirectory {item_path}: {e}")

        except Exception as e:
            logger.error(f"Error scanning directory {directory}: {e}")

        return csv_files

    async def _list_dir_safe(self, path):
        """Safely list directory contents with timeout protection"""
        try:
            items = await asyncio.wait_for(
                asyncio.to_thread(lambda: self.sftp.listdir(path)),
                timeout=self._connection_timeout
            )
            return items
        except Exception as e:
            logger.warning(f"Error listing directory {path}: {e}")
            return []

    async def _is_dir_safe(self, path):
        """Safely check if path is directory with timeout protection"""
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(lambda: self.sftp.stat(path).st_mode & 0o40000 != 0),
                timeout=self._connection_timeout
            )
            return result
        except Exception:
            return False

    async def disconnect(self):
        """Close SFTP connection"""
        try:
            if self.sftp:
                self.sftp.close()
            if self.client:
                self.client.close()
            self.connected = False
            logger.info(f"Disconnected from SFTP server: {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"Error disconnecting: {e}")

    async def get_log_file(self):
        """Get the path to the Deadside.log file"""
        if not self.connected:
            await self.connect()
        if not self.connected:
            return None

        try:
            # Record start time to prevent heartbeat blocks
            start_time = asyncio.get_event_loop().time()

            # First find the server directory using specific format {Host}_{serverid}/Logs
            target_directory = None

            # Direct path to the logs directory based on the provided structure
            server_dir_pattern = f"{self.host.split(':')[0]}_{self.server_id}"
            logs_dir = os.path.join(".", server_dir_pattern, "Logs")

            logger.info(f"Using direct log path: {logs_dir}")

            # Check if the logs directory exists with timeout protection
            try:
                async def dir_exists_with_timeout():
                    try:
                        # Try to list the directory to see if it exists
                        items = await asyncio.to_thread(lambda: self.sftp.listdir(logs_dir))
                        return True, items
                    except:
                        return False, None

                exists, logs_items = await asyncio.wait_for(dir_exists_with_timeout(), timeout=3.0)

                if exists and logs_items:
                    logger.info(f"'Logs' directory contains: {', '.join(logs_items)}")

                    # Check for Deadside.log in the logs directory
                    if LOG_FILENAME in logs_items:
                        log_path = os.path.join(logs_dir, LOG_FILENAME)
                        logger.info(f"Found log file at: {log_path}")
                        return log_path
                    else:
                        logger.warning(f"'{LOG_FILENAME}' not found in direct Logs directory path")

            except asyncio.TimeoutError:
                logger.warning(f"Timeout checking direct logs directory: {logs_dir}")
            except Exception as e:
                logger.warning(f"Error with direct logs path: {e}")

            # Fallback approach if direct path fails
            if asyncio.get_event_loop().time() - start_time > 15:
                logger.warning("Log file search is taking too long, stopping to prevent heartbeat timeout")
                return None

            # List root directory with timeout protection
            logger.info("Fallback: Searching for server directory in root...")
            try:
                async def list_root_with_timeout():
                    return await asyncio.to_thread(lambda: self.sftp.listdir("."))

                root_files = await asyncio.wait_for(list_root_with_timeout(), timeout=3.0)

                # Look for the server ID pattern
                for item in root_files:
                    if server_dir_pattern in item:
                        # Found matching directory
                        target_directory = os.path.join(".", item)
                        logger.info(f"Found server directory for logs: {target_directory}")

                        # Try to directly access the logs directory now
                        logs_dir = os.path.join(target_directory, "Logs")

                        try:
                            async def check_logs_dir():
                                return await asyncio.to_thread(lambda: self.sftp.listdir(logs_dir))

                            logs_items = await asyncio.wait_for(check_logs_dir(), timeout=3.0)

                            if LOG_FILENAME in logs_items:
                                log_path = os.path.join(logs_dir, LOG_FILENAME)
                                logger.info(f"Found log file at: {log_path}")
                                return log_path
                        except Exception:
                            logger.warning(f"Could not find {LOG_FILENAME} in {logs_dir}")

                        break

            except (asyncio.TimeoutError, Exception) as e:
                logger.error(f"Error in fallback log file search: {e}")

            # If we've tried everything and still don't have the file
            logger.error("Could not find the log file using any method")
            return None

        except Exception as e:
            logger.error(f"Error getting log file: {e}", exc_info=True)
            return None

    async def read_file(self, file_path, start_line=0, max_lines=None, chunk_size=1000):
        """Read a file from the SFTP server with timeout protection
        Args:
            file_path: Path to the file to read
            start_line: First line to read (0-indexed)
            max_lines: Maximum number of lines to read
            chunk_size: Number of lines to read in each chunk (to prevent timeout)
        Returns:
            List of lines read from the file
        """
        if not self.connected:
            await self.connect()
        if not self.connected:
            return []

        try:
            # Create a new task with timeout to prevent event loop blocking
            async def read_chunk(start, max_count):
                try:
                    # We'll create a new file handle for each chunk to avoid timeout issues
                    with self.sftp.file(file_path, 'r') as chunk_file:
                        # Skip to the starting position
                        for _ in range(start):
                            next(chunk_file, None)

                        # Read the requested chunk with stricter timeout
                        chunk_lines = []
                        count = 0

                        try:
                            async with asyncio.timeout(3.0):  # Shorter timeout to prevent heartbeat blocks
                                return await asyncio.to_thread(self._read_chunk, chunk_file, max_count)
                        except asyncio.TimeoutError:
                            logger.warning(f"Chunk read timeout for {file_path} at position {start}")
                            # Return partial data if we have any
                            return chunk_lines if chunk_lines else []

                except asyncio.TimeoutError:
                    logger.warning(f"Timeout reading file {file_path} at position {start}")
                    # Try to reconnect on timeout
                    await self.disconnect()
                    await asyncio.sleep(1)
                    await self.connect()
                    return []
                except Exception as e:
                    logger.error(f"Error reading chunk at position {start}: {e}")
                    return []

            all_lines = []
            current_position = start_line
            remaining_lines = max_lines

            while True:
                # Determine how many lines to read in this chunk
                current_chunk_size = chunk_size
                if remaining_lines is not None:
                    if remaining_lines <= 0:
                        break
                    current_chunk_size = min(chunk_size, remaining_lines)

                # Read the next chunk with timeout protection
                chunk_data = await read_chunk(current_position, current_chunk_size)

                # Break if we got no data (end of file or error)
                if not chunk_data:
                    break

                # Update our tracking variables
                all_lines.extend([line.strip() for line in chunk_data])
                chunk_line_count = len(chunk_data)
                current_position += chunk_line_count

                if remaining_lines is not None:
                    remaining_lines -= chunk_line_count

                # If we got fewer lines than requested, we've reached the end of the file
                if chunk_line_count < current_chunk_size:
                    break

                # Add a small delay to prevent overloading the event loop
                await asyncio.sleep(0.01)

            return all_lines

        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}", exc_info=True)
            # Try to reconnect after an error
            await self.disconnect()
            await asyncio.sleep(1)
            await self.connect()
            return []

    def _read_chunk(self, file_obj, max_lines):
        """Read a chunk of lines from a file with improved error handling
        Args:
            file_obj: Open file object
            max_lines: Maximum number of lines to read
        Returns:
            List of lines read
        """
        try:
            lines = []
            for _ in range(max_lines):
                try:
                    line = next(file_obj)
                    # Skip non-UTF8 characters if present
                    if line:
                        try:
                            # Try to decode and re-encode to ensure valid UTF-8
                            # This handles cases where files have mixed encodings
                            line = line.encode('utf-8', errors='replace').decode('utf-8')
                        except Exception as enc_err:
                            logger.debug(f"Encoding fix failed, using original line: {enc_err}")
                            # Just use the original line if encoding conversion fails
                            pass
                    lines.append(line)
                except StopIteration:
                    break
                except Exception as line_err:
                    logger.warning(f"Error reading line: {line_err}")
                    continue  # Skip problematic lines but continue reading

            logger.debug(f"Read {len(lines)} lines in chunk")
            return lines
        except Exception as e:
            logger.error(f"Error in _read_chunk: {e}")
            return []

    async def get_file_size(self, file_path, chunk_size=5000):
        """Get the size of a file in lines with improved reliability and performance
        Args:
            file_path: Path to the file
            chunk_size: Number of lines to count in each chunk
        Returns:
            Number of lines in the file
        """
        if not self.connected:
            await self.connect()
        if not self.connected:
            return 0

        try:
            # OPTIMIZATION: Use a faster method to count lines
            # First try the fastest approach - check if we can get an exact count quickly
            async def fast_count():
                """Fast line counting using wc -l if available, otherwise fall back to reading"""
                try:
                    # Try to use shell command to count lines (much faster)
                    stdin, stdout, stderr = await asyncio.to_thread(
                        lambda: self.client.exec_command(f"wc -l '{file_path}'", timeout=5.0)
                    )
                    result = await asyncio.to_thread(lambda: stdout.read().decode().strip())
                    if result and ' ' in result:
                        # wc -l output format: "N filename"
                        try:
                            count = int(result.split(' ')[0])
                            logger.info(f"Fast line count for {file_path}: {count} lines")
                            return count
                        except (ValueError, IndexError):
                            logger.debug(f"Could not parse wc output: {result}")
                    return None
                except Exception as e:
                    logger.debug(f"Fast count failed, falling back to python method: {e}")
                    return None

            # Try the fast count first with timeout
            try:
                count = await asyncio.wait_for(fast_count(), timeout=5.0)
                if count is not None:
                    return count
            except (asyncio.TimeoutError, Exception):
                logger.debug("Fast count timed out or failed")

            # Fall back to Python counting method with performance optimizations
            def optimized_count():
                try:
                    with self.sftp.file(file_path, 'r') as f:
                        # Use a faster method to count lines
                        # Read the file in larger chunks for speed
                        chunk_size = 1024 * 1024  # 1MB chunks
                        total_lines = 0
                        read_bytes = 0
                        file_size = 0

                        # Get file size first
                        try:
                            file_size = self.sftp.stat(file_path).st_size
                            logger.debug(f"File size for {file_path}: {file_size} bytes")
                        except Exception as fs_err:
                            logger.warning(f"Error getting file size: {fs_err}")
                            file_size = 0

                        # Stop after reading more than 100MB to prevent timeouts on huge files
                        # This will provide a good estimate for large files
                        max_bytes_to_read = min(file_size, 100 * 1024 * 1024) if file_size > 0 else 10 * 1024 * 1024

                        # Read and count newlines in chunks
                        buffer = f.read(chunk_size)
                        while buffer:
                            read_bytes += len(buffer)
                            total_lines += buffer.count('\n')

                            # Break if we've read enough
                            if read_bytes >= max_bytes_to_read:
                                # Estimate total based on portion read
                                if file_size > 0 and read_bytes < file_size:
                                    scale_factor = file_size / read_bytes
                                    if scale_factor > 1:
                                        estimated_total = int(total_lines * scale_factor)
                                        logger.info(f"Estimated total lines for {file_path}: {estimated_total} based on {total_lines} in {read_bytes}/{file_size} bytes")
                                        return estimated_total
                                break

                            # Read next chunk
                            buffer = f.read(chunk_size)

                        # Add 1 if last line doesn't end with newline (but not if file is empty)
                        if buffer and not buffer.endswith('\n'):
                            total_lines += 1

                        logger.info(f"Counted {total_lines} lines in {file_path}")
                        return total_lines
                except Exception as e:
                    logger.error(f"Error in optimized count: {e}")
                    # Use a reasonable default based on typical CSV files
                    return 600  # Typical line count for a CSV file

            # Implement an optimized hybrid counting approach
            try:
                async def count_lines_fast():
                    try:
                        # First attempt: Use wc -l through SSH if available
                        if self.client:
                            try:
                                stdin, stdout, stderr = await asyncio.wait_for(
                                    asyncio.to_thread(
                                        lambda: self.client.exec_command(f"wc -l '{file_path}'", timeout=5.0)
                                    ),
                                    timeout=5.0
                                )
                                result = await asyncio.to_thread(lambda: stdout.read().decode().strip())
                                if result and ' ' in result:
                                    count = int(result.split(' ')[0])
                                    logger.info(f"Fast count successful for {file_path}: {count} lines")
                                    return count
                            except Exception as e:
                                logger.debug(f"Fast count failed, falling back to direct read: {e}")

                        # Second attempt: Direct binary read with chunking
                        async with asyncio.timeout(10.0):
                            chunk_size = 1024 * 1024  # 1MB chunks
                            total_lines = 0
                            read_size = 0
                            max_read = 100 * 1024 * 1024  # 100MB read limit for large files

                            with self.sftp.file(file_path, 'rb') as f:
                                try:
                                    # Get file size for progress tracking
                                    file_size = self.sftp.stat(file_path).st_size
                                except:
                                    file_size = 0

                                while True:
                                    chunk = f.read(chunk_size)
                                    if not chunk:
                                        break

                                    read_size += len(chunk)
                                    total_lines += chunk.count(b'\n')

                                    # Stop if we've read enough
                                    if read_size >= max_read:
                                        # Estimate total based on file size
                                        if file_size > read_size:
                                            ratio = file_size / read_size
                                            total_lines = int(total_lines * ratio)
                                        break

                                # Add 1 if file doesn't end with newline
                                if chunk and not chunk.endswith(b'\n'):
                                    total_lines += 1

                            logger.info(f"Direct count successful for {file_path}: {total_lines} lines")
                            return total_lines

                    except asyncio.TimeoutError:
                        logger.warning(f"Timeout counting lines in {file_path}")
                        return 600
                    except Exception as e:
                        logger.error(f"Error counting lines: {e}")
                        return 600

                # Execute the counting with timeout protection
                return await asyncio.wait_for(
                    count_lines_fast(),
                    timeout=15.0
                )
            except asyncio.TimeoutError:
                # Use stats-based estimation as fallback
                try:
                    attrs = await asyncio.to_thread(lambda: self.sftp.stat(file_path))
                    # Estimate based on file size - assume approximately 80 bytes per line (typical for CSV)
                    estimated_lines = max(100, attrs.st_size // 80) 
                    logger.info(f"Using size-based estimation for {file_path}: ~{estimated_lines} lines")
                    return estimated_lines
                except Exception as est_err:
                    logger.warning(f"Fallback estimation failed for {file_path}: {est_err}, using default")
                    return 600  # Default if all methods fail - typical for CSV files

        except Exception as e:
            logger.error(f"Error in get_file_size: {e}", exc_info=True)
            # Still return a reasonable number instead of 0
            return 600

    @staticmethod
    def run_in_executor(func, *args, **kwargs):
        """Run a blocking function in an executor"""
        loop = asyncio.get_event_loop()
        return loop.run_in_executor(None, lambda: func(*args, **kwargs))