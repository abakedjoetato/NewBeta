"""
SFTP connection handler for Tower of Temptation PvP Statistics Bot

This module provides utilities for connecting to game servers via SFTP 
and retrieving log files.
"""
import os
import logging
import asyncio
import re
import io
from typing import List, Dict, Any, Optional, Tuple, Union, BinaryIO
from datetime import datetime, timedelta
import paramiko
import asyncssh

logger = logging.getLogger(__name__)

class SFTPHandler:
    """SFTP connection handler for game servers"""
    
    def __init__(
        self,
        hostname: str,
        port: int,
        username: str,
        password: str,
        timeout: int = 30,
        max_retries: int = 3
    ):
        """Initialize SFTP handler
        
        Args:
            hostname: SFTP hostname
            port: SFTP port
            username: SFTP username
            password: SFTP password
            timeout: Connection timeout in seconds
            max_retries: Maximum number of connection retries
        """
        self.hostname = hostname
        self.port = port
        self.username = username
        self.password = password
        self.timeout = timeout
        self.max_retries = max_retries
        self._sftp_client = None
        self._ssh_client = None
        self._connected = False
        self._connection_attempts = 0
        
    async def connect(self) -> bool:
        """Connect to SFTP server
        
        Returns:
            True if connected successfully, False otherwise
        """
        if self._connected and self._sftp_client:
            return True
            
        try:
            # Create asyncssh connection
            self._ssh_client = await asyncssh.connect(
                host=self.hostname,
                port=self.port,
                username=self.username,
                password=self.password,
                known_hosts=None,  # Disable known hosts check
                connect_timeout=self.timeout
            )
            
            # Get SFTP client
            self._sftp_client = await self._ssh_client.start_sftp_client()
            
            self._connected = True
            self._connection_attempts = 0
            
            logger.info(f"Connected to SFTP server: {self.hostname}:{self.port}")
            return True
            
        except Exception as e:
            self._connected = False
            self._connection_attempts += 1
            
            logger.error(f"Failed to connect to SFTP server (attempt {self._connection_attempts}): {e}")
            
            if self._connection_attempts >= self.max_retries:
                logger.critical("Maximum connection attempts reached. Giving up.")
                return False
                
            # Exponential backoff for reconnection
            delay = min(30, 2 ** self._connection_attempts)
            logger.info(f"Retrying connection in {delay} seconds...")
            await asyncio.sleep(delay)
            
            return await self.connect()
    
    async def disconnect(self):
        """Disconnect from SFTP server"""
        if self._sftp_client:
            self._sftp_client.close()
            self._sftp_client = None
            
        if self._ssh_client:
            self._ssh_client.close()
            self._ssh_client = None
            
        self._connected = False
        logger.info("Disconnected from SFTP server")
    
    async def ensure_connected(self):
        """Ensure connection to SFTP server"""
        if not self._connected or not self._sftp_client or not self._ssh_client:
            await self.connect()
    
    async def list_directory(self, directory: str) -> List[str]:
        """List files in directory
        
        Args:
            directory: Directory to list
            
        Returns:
            List of filenames
        """
        await self.ensure_connected()
        
        try:
            entries = await self._sftp_client.listdir(directory)
            return entries
        except Exception as e:
            logger.error(f"Failed to list directory {directory}: {e}")
            return []
            
    async def get_file_info(self, path: str) -> Optional[Dict[str, Any]]:
        """Get file information
        
        Args:
            path: File path
            
        Returns:
            File information or None if not found
        """
        await self.ensure_connected()
        
        try:
            stat = await self._sftp_client.stat(path)
            return {
                "size": stat.size,
                "mtime": datetime.fromtimestamp(stat.mtime),
                "atime": datetime.fromtimestamp(stat.atime),
                "is_dir": stat.type == 2,  # asyncssh.FILEXFER_TYPE_DIRECTORY = 2
                "is_file": stat.type == 1,  # asyncssh.FILEXFER_TYPE_REGULAR = 1
                "permissions": stat.permissions
            }
        except Exception as e:
            logger.error(f"Failed to get file info for {path}: {e}")
            return None
    
    async def download_file(self, remote_path: str, local_path: Optional[str] = None) -> Optional[bytes]:
        """Download file from SFTP server
        
        Args:
            remote_path: Remote file path
            local_path: Optional local file path to save to
            
        Returns:
            File contents as bytes if local_path not provided, otherwise None
        """
        await self.ensure_connected()
        
        try:
            if local_path:
                # Download to file
                await self._sftp_client.get(remote_path, local_path)
                logger.info(f"Downloaded {remote_path} to {local_path}")
                return None
            else:
                # Download to memory
                file_obj = io.BytesIO()
                await self._sftp_client.getfo(remote_path, file_obj)
                
                # Reset position to beginning
                file_obj.seek(0)
                content = file_obj.read()
                
                logger.info(f"Downloaded {remote_path} to memory ({len(content)} bytes)")
                return content
                
        except Exception as e:
            logger.error(f"Failed to download file {remote_path}: {e}")
            return None
            
    async def read_file_by_chunks(self, remote_path: str, chunk_size: int = 4096) -> Optional[List[bytes]]:
        """Read file by chunks
        
        Args:
            remote_path: Remote file path
            chunk_size: Chunk size in bytes
            
        Returns:
            List of chunks or None if failed
        """
        await self.ensure_connected()
        
        try:
            chunks = []
            async with self._sftp_client.open(remote_path, 'rb') as f:
                while True:
                    chunk = await f.read(chunk_size)
                    if not chunk:
                        break
                    chunks.append(chunk)
                    
            logger.info(f"Read {remote_path} by chunks ({len(chunks)} chunks)")
            return chunks
            
        except Exception as e:
            logger.error(f"Failed to read file {remote_path} by chunks: {e}")
            return None
            
    async def find_files_by_pattern(self, directory: str, pattern: str, recursive: bool = False, max_depth: int = 5) -> List[str]:
        """Find files by pattern
        
        Args:
            directory: Directory to search
            pattern: Regular expression pattern for filenames
            recursive: Whether to search recursively
            max_depth: Maximum recursion depth
            
        Returns:
            List of matching file paths
        """
        await self.ensure_connected()
        
        result = []
        pattern_re = re.compile(pattern)
        
        await self._find_files_recursive(directory, pattern_re, result, recursive, max_depth, 0)
        
        return result
        
    async def _find_files_recursive(self, directory: str, pattern_re: re.Pattern, result: List[str], recursive: bool, max_depth: int, current_depth: int):
        """Recursively find files by pattern
        
        Args:
            directory: Directory to search
            pattern_re: Compiled regular expression pattern
            result: List to add results to
            recursive: Whether to search recursively
            max_depth: Maximum recursion depth
            current_depth: Current recursion depth
        """
        if current_depth > max_depth:
            return
            
        try:
            entries = await self._sftp_client.listdir(directory)
            
            for entry in entries:
                entry_path = f"{directory}/{entry}"
                
                try:
                    entry_info = await self.get_file_info(entry_path)
                    
                    if not entry_info:
                        continue
                        
                    if entry_info["is_file"] and pattern_re.search(entry):
                        result.append(entry_path)
                        
                    elif entry_info["is_dir"] and recursive:
                        await self._find_files_recursive(entry_path, pattern_re, result, recursive, max_depth, current_depth + 1)
                        
                except Exception as e:
                    logger.warning(f"Error processing entry {entry_path}: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Failed to list directory {directory}: {e}")
            
    async def find_csv_files(
        self, 
        directory: str, 
        date_range: Optional[Tuple[datetime, datetime]] = None,
        recursive: bool = True,
        max_depth: int = 5
    ) -> List[str]:
        """Find CSV files in directory
        
        Args:
            directory: Directory to search
            date_range: Optional tuple of (start_date, end_date) to filter by filename date
            recursive: Whether to search recursively
            max_depth: Maximum recursion depth
            
        Returns:
            List of CSV file paths
        """
        # Find all CSV files
        csv_files = await self.find_files_by_pattern(directory, r'\.csv$', recursive, max_depth)
        
        # Filter by date range if provided
        if date_range:
            start_date, end_date = date_range
            filtered_files = []
            
            for file_path in csv_files:
                # Extract date from filename using common patterns
                file_name = os.path.basename(file_path)
                date_match = re.search(r'(\d{4}[.-]\d{2}[.-]\d{2})', file_name)
                
                if date_match:
                    date_str = date_match.group(1)
                    try:
                        # Try to parse date from filename
                        if '-' in date_str:
                            file_date = datetime.strptime(date_str, '%Y-%m-%d')
                        else:
                            file_date = datetime.strptime(date_str, '%Y.%m.%d')
                            
                        # Check if date is within range
                        if start_date <= file_date <= end_date:
                            filtered_files.append(file_path)
                            
                    except Exception:
                        # If date parsing fails, include the file
                        filtered_files.append(file_path)
                else:
                    # If no date found in filename, include the file
                    filtered_files.append(file_path)
                    
            csv_files = filtered_files
            
        return csv_files
        
    async def read_csv_lines(self, remote_path: str, encoding: str = 'utf-8') -> List[str]:
        """Read CSV file lines
        
        Args:
            remote_path: Remote file path
            encoding: File encoding
            
        Returns:
            List of lines
        """
        content = await self.download_file(remote_path)
        
        if not content:
            return []
            
        try:
            text = content.decode(encoding)
            lines = text.splitlines()
            return lines
        except UnicodeDecodeError:
            # Try with different encodings
            try:
                text = content.decode('latin-1')
                lines = text.splitlines()
                return lines
            except Exception as e:
                logger.error(f"Failed to decode file {remote_path}: {e}")
                return []
        except Exception as e:
            logger.error(f"Failed to process file {remote_path}: {e}")
            return []