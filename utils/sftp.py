"""
SFTP client module for the Tower of Temptation PvP Statistics Discord Bot.

This module provides:
1. Connection pooling for SFTP connections
2. Automatic retry on transient failures
3. Reliable file transfer with integrity verification
4. Directory watching for new CSV files
5. Enhanced logging and diagnostics
"""
import asyncio
import base64
import hashlib
import io
import logging
import os
import re
import stat
import time
from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Set, Union, BinaryIO, Callable, AsyncGenerator

import paramiko
from paramiko import SFTPClient, SSHClient, AutoAddPolicy, Transport, RSAKey

from utils.async_utils import BackgroundTask, AsyncRetry

logger = logging.getLogger(__name__)

# Constants for connection pooling
MAX_POOL_SIZE = 5
CONNECTION_TIMEOUT = 10.0  # seconds
CONNECTION_LIFETIME = 300.0  # 5 minutes
RETRY_DELAY = 2.0  # seconds
MAX_RETRIES = 3

class SFTPConnectionPool:
    """Connection pool for SFTP connections
    
    This class manages a pool of SSH/SFTP connections to avoid
    establishing new connections for each operation.
    """
    
    _pools: Dict[str, 'SFTPConnectionPool'] = {}
    
    @classmethod
    def get_pool(cls, host: str, port: int = 22) -> 'SFTPConnectionPool':
        """Get or create a connection pool for a host
        
        Args:
            host: SFTP host
            port: SFTP port (default: 22)
            
        Returns:
            SFTPConnectionPool: Connection pool
        """
        pool_key = f"{host}:{port}"
        
        if pool_key not in cls._pools:
            cls._pools[pool_key] = cls(host, port)
        
        return cls._pools[pool_key]
    
    def __init__(self, host: str, port: int = 22):
        """Initialize connection pool
        
        Args:
            host: SFTP host
            port: SFTP port (default: 22)
        """
        self.host = host
        self.port = port
        self.connections: Dict[str, List[Tuple[SFTPClient, float]]] = defaultdict(list)
        self.locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self.cleanup_task = BackgroundTask.create(
            self._cleanup_connections(),
            name=f"sftp_pool_cleanup_{host}:{port}",
            restart_on_failure=True
        )
    
    def _get_connection_key(self, username: str, password: Optional[str] = None, key_data: Optional[str] = None) -> str:
        """Get a unique key for this connection configuration
        
        Args:
            username: SFTP username
            password: SFTP password (optional)
            key_data: SSH key data (optional)
            
        Returns:
            str: Connection key
        """
        key_parts = [username]
        
        if password:
            # Use hash of password to avoid storing passwords in memory
            key_parts.append(hashlib.sha256(password.encode()).hexdigest())
        
        if key_data:
            # Use hash of key data to avoid storing keys in memory
            key_parts.append(hashlib.sha256(key_data.encode()).hexdigest())
        
        return ":".join(key_parts)
    
    async def get_connection(
        self,
        username: str,
        password: Optional[str] = None,
        key_data: Optional[str] = None
    ) -> SFTPClient:
        """Get a connection from the pool or create a new one
        
        Args:
            username: SFTP username
            password: SFTP password (optional)
            key_data: SSH key data (optional)
            
        Returns:
            SFTPClient: SFTP client
            
        Raises:
            paramiko.SSHException: If connection fails
        """
        conn_key = self._get_connection_key(username, password, key_data)
        
        # Get lock for this connection key
        async with self.locks[conn_key]:
            # Check if we have available connections
            if conn_key in self.connections and self.connections[conn_key]:
                # Find a usable connection
                for i, (sftp, created_at) in enumerate(self.connections[conn_key]):
                    # Check if connection is still alive
                    try:
                        sftp.stat(".")
                        # Remove from pool so it won't be used by others
                        self.connections[conn_key].pop(i)
                        return sftp
                    except:
                        # Connection is dead, close it
                        try:
                            sftp.close()
                            transport = sftp.get_channel().get_transport()
                            if transport:
                                transport.close()
                        except:
                            pass
                
                # All connections are dead, clear the list
                self.connections[conn_key] = []
            
            # Create a new connection
            return await self._create_connection(username, password, key_data)
    
    def release_connection(
        self,
        sftp: SFTPClient,
        username: str,
        password: Optional[str] = None,
        key_data: Optional[str] = None
    ) -> None:
        """Release a connection back to the pool
        
        Args:
            sftp: SFTP client
            username: SFTP username
            password: SFTP password (optional)
            key_data: SSH key data (optional)
        """
        conn_key = self._get_connection_key(username, password, key_data)
        
        # Check if connection is alive
        try:
            sftp.stat(".")
            
            # Check if pool is full
            if len(self.connections[conn_key]) >= MAX_POOL_SIZE:
                # Pool is full, close this connection
                try:
                    sftp.close()
                    transport = sftp.get_channel().get_transport()
                    if transport:
                        transport.close()
                except:
                    pass
                return
            
            # Add connection back to pool
            self.connections[conn_key].append((sftp, time.time()))
        except:
            # Connection is dead, close it
            try:
                sftp.close()
                transport = sftp.get_channel().get_transport()
                if transport:
                    transport.close()
            except:
                pass
    
    async def _create_connection(
        self,
        username: str,
        password: Optional[str] = None,
        key_data: Optional[str] = None
    ) -> SFTPClient:
        """Create a new SFTP connection
        
        Args:
            username: SFTP username
            password: SFTP password (optional)
            key_data: SSH key data (optional)
            
        Returns:
            SFTPClient: SFTP client
            
        Raises:
            paramiko.SSHException: If connection fails
        """
        ssh = SSHClient()
        ssh.set_missing_host_key_policy(AutoAddPolicy())
        
        # Prepare key if provided
        pkey = None
        if key_data:
            key_file = io.StringIO(key_data)
            try:
                pkey = paramiko.RSAKey.from_private_key(key_file, password=password)
                # If key has a passphrase, don't send the passphrase as password
                if password:
                    password = None
            except:
                logger.error("Failed to load SSH key, falling back to password auth")
            finally:
                key_file.close()
        
        # Connect with retry
        retries = 0
        last_exception = None
        
        while retries <= MAX_RETRIES:
            try:
                ssh.connect(
                    hostname=self.host,
                    port=self.port,
                    username=username,
                    password=password,
                    pkey=pkey,
                    timeout=CONNECTION_TIMEOUT,
                    allow_agent=False,
                    look_for_keys=False
                )
                
                # Create SFTP client
                sftp = ssh.open_sftp()
                logger.info(f"Successfully established SFTP connection to {self.host}:{self.port}")
                return sftp
                
            except Exception as e:
                last_exception = e
                retries += 1
                
                if retries <= MAX_RETRIES:
                    logger.warning(f"SFTP connection attempt {retries} failed: {e}. Retrying in {RETRY_DELAY} seconds...")
                    await asyncio.sleep(RETRY_DELAY)
                else:
                    logger.error(f"Failed to establish SFTP connection after {MAX_RETRIES} retries: {e}")
                    raise
        
        # This should never happen, but just in case
        if last_exception:
            raise last_exception
        raise paramiko.SSHException("Failed to establish SFTP connection for unknown reason")
    
    async def _cleanup_connections(self) -> None:
        """Clean up expired connections periodically"""
        while True:
            try:
                current_time = time.time()
                
                # Iterate through all connection keys
                for conn_key in list(self.connections.keys()):
                    # Only clean up if we're not currently using this connection key
                    if not self.locks[conn_key].locked():
                        connections = self.connections[conn_key]
                        
                        # Find expired connections
                        expired = []
                        for i, (sftp, created_at) in enumerate(connections):
                            if current_time - created_at > CONNECTION_LIFETIME:
                                expired.append(i)
                        
                        # Close and remove expired connections (in reverse order)
                        for i in reversed(expired):
                            sftp, _ = connections.pop(i)
                            try:
                                sftp.close()
                                transport = sftp.get_channel().get_transport()
                                if transport:
                                    transport.close()
                            except:
                                pass
                
                # Sleep until next cleanup
                await asyncio.sleep(60.0)  # Check every minute
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error cleaning up SFTP connections: {e}")
                await asyncio.sleep(60.0)  # Retry in a minute
    
    def close_all(self) -> None:
        """Close all connections in the pool"""
        for conn_key in list(self.connections.keys()):
            for sftp, _ in self.connections[conn_key]:
                try:
                    sftp.close()
                    transport = sftp.get_channel().get_transport()
                    if transport:
                        transport.close()
                except:
                    pass
            
            self.connections[conn_key] = []

class SFTPManager:
    """Enhanced SFTP manager with retry logic and connection pooling"""
    
    def __init__(
        self,
        host: str,
        port: int = 22,
        username: str = "",
        password: Optional[str] = None,
        key_data: Optional[str] = None,
        base_path: str = "/"
    ):
        """Initialize SFTP manager
        
        Args:
            host: SFTP host
            port: SFTP port (default: 22)
            username: SFTP username
            password: SFTP password (optional)
            key_data: SSH key data (optional)
            base_path: Base directory path (default: /)
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.key_data = key_data
        self.base_path = base_path
        self.pool = SFTPConnectionPool.get_pool(host, port)
    
    @contextmanager
    def _get_sftp_client(self) -> SFTPClient:
        """Get an SFTP client from the pool
        
        Returns:
            SFTPClient: SFTP client
        """
        sftp = None
        try:
            # This is synchronous as it's used in a contextmanager
            # We'll use the event loop directly
            loop = asyncio.get_event_loop()
            sftp = loop.run_until_complete(
                self.pool.get_connection(self.username, self.password, self.key_data)
            )
            yield sftp
        finally:
            if sftp:
                self.pool.release_connection(
                    sftp, self.username, self.password, self.key_data
                )
    
    async def get_sftp_client(self) -> SFTPClient:
        """Get an SFTP client from the pool (async version)
        
        Returns:
            SFTPClient: SFTP client
        """
        return await self.pool.get_connection(
            self.username, self.password, self.key_data
        )
    
    def release_sftp_client(self, sftp: SFTPClient) -> None:
        """Release an SFTP client back to the pool
        
        Args:
            sftp: SFTP client
        """
        self.pool.release_connection(
            sftp, self.username, self.password, self.key_data
        )
    
    @AsyncRetry.retryable(
        max_retries=MAX_RETRIES,
        base_delay=RETRY_DELAY,
        exceptions=(IOError, paramiko.SSHException)
    )
    async def list_directory(
        self,
        path: Optional[str] = None,
        pattern: Optional[str] = None,
        recursive: bool = False,
        include_dirs: bool = False
    ) -> List[Dict[str, Any]]:
        """List directory contents
        
        Args:
            path: Directory path (optional - uses base_path if not specified)
            pattern: File pattern glob (optional)
            recursive: Whether to list contents recursively
            include_dirs: Whether to include directories in results
            
        Returns:
            List[Dict]: List of file information
        """
        dir_path = path or self.base_path
        pattern_regex = None
        
        if pattern:
            # Convert glob pattern to regex
            pattern_regex = re.compile(
                "^" + pattern.replace(".", "\\.").replace("*", ".*") + "$"
            )
        
        sftp = await self.get_sftp_client()
        try:
            return await self._list_directory_recursive(
                sftp, dir_path, pattern_regex, recursive, include_dirs
            )
        finally:
            self.release_sftp_client(sftp)
    
    async def _list_directory_recursive(
        self,
        sftp: SFTPClient,
        path: str,
        pattern_regex: Optional[re.Pattern] = None,
        recursive: bool = False,
        include_dirs: bool = False,
        _depth: int = 0,
        _max_depth: int = 10  # Prevent infinite recursion
    ) -> List[Dict[str, Any]]:
        """Recursively list directory contents
        
        Args:
            sftp: SFTP client
            path: Directory path
            pattern_regex: File pattern regex (optional)
            recursive: Whether to list contents recursively
            include_dirs: Whether to include directories in results
            _depth: Current recursion depth
            _max_depth: Maximum recursion depth
            
        Returns:
            List[Dict]: List of file information
        """
        if _depth > _max_depth:
            logger.warning(f"Maximum recursion depth reached for {path}")
            return []
        
        results = []
        
        try:
            items = sftp.listdir_attr(path)
            
            for item in items:
                item_path = os.path.join(path, item.filename)
                is_dir = stat.S_ISDIR(item.st_mode)
                
                # Include directories if requested
                if is_dir and include_dirs:
                    if not pattern_regex or pattern_regex.match(item.filename):
                        results.append({
                            "name": item.filename,
                            "path": item_path,
                            "size": item.st_size,
                            "mtime": datetime.fromtimestamp(item.st_mtime),
                            "is_dir": True
                        })
                
                # Recursively list subdirectories if requested
                if is_dir and recursive:
                    sub_results = await self._list_directory_recursive(
                        sftp, item_path, pattern_regex, recursive, include_dirs,
                        _depth + 1, _max_depth
                    )
                    results.extend(sub_results)
                
                # Include files that match the pattern
                if not is_dir:
                    if not pattern_regex or pattern_regex.match(item.filename):
                        results.append({
                            "name": item.filename,
                            "path": item_path,
                            "size": item.st_size,
                            "mtime": datetime.fromtimestamp(item.st_mtime),
                            "is_dir": False
                        })
            
            return results
            
        except Exception as e:
            logger.error(f"Error listing directory {path}: {e}")
            raise
    
    @AsyncRetry.retryable(
        max_retries=MAX_RETRIES,
        base_delay=RETRY_DELAY,
        exceptions=(IOError, paramiko.SSHException)
    )
    async def read_file(self, path: str) -> bytes:
        """Read file contents
        
        Args:
            path: File path
            
        Returns:
            bytes: File contents
        """
        sftp = await self.get_sftp_client()
        try:
            # Create a BytesIO buffer to receive file contents
            buffer = io.BytesIO()
            
            # Read file using SFTP
            with sftp.open(path, 'rb') as f:
                while True:
                    chunk = f.read(32768)  # 32KB chunks
                    if not chunk:
                        break
                    buffer.write(chunk)
            
            # Return file contents
            return buffer.getvalue()
        finally:
            self.release_sftp_client(sftp)
    
    @AsyncRetry.retryable(
        max_retries=MAX_RETRIES,
        base_delay=RETRY_DELAY,
        exceptions=(IOError, paramiko.SSHException)
    )
    async def read_file_text(self, path: str, encoding: str = 'utf-8') -> str:
        """Read file contents as text
        
        Args:
            path: File path
            encoding: Text encoding (default: utf-8)
            
        Returns:
            str: File contents as text
        """
        data = await self.read_file(path)
        return data.decode(encoding)
    
    @AsyncRetry.retryable(
        max_retries=MAX_RETRIES,
        base_delay=RETRY_DELAY,
        exceptions=(IOError, paramiko.SSHException)
    )
    async def write_file(self, path: str, content: bytes) -> None:
        """Write file contents
        
        Args:
            path: File path
            content: File contents
        """
        sftp = await self.get_sftp_client()
        try:
            # Ensure directory exists
            directory = os.path.dirname(path)
            await self._ensure_directory(sftp, directory)
            
            # Write file using SFTP
            with sftp.open(path, 'wb') as f:
                f.write(content)
        finally:
            self.release_sftp_client(sftp)
    
    @AsyncRetry.retryable(
        max_retries=MAX_RETRIES,
        base_delay=RETRY_DELAY,
        exceptions=(IOError, paramiko.SSHException)
    )
    async def write_file_text(self, path: str, content: str, encoding: str = 'utf-8') -> None:
        """Write file contents as text
        
        Args:
            path: File path
            content: File contents as text
            encoding: Text encoding (default: utf-8)
        """
        await self.write_file(path, content.encode(encoding))
    
    async def _ensure_directory(self, sftp: SFTPClient, directory: str) -> None:
        """Ensure a directory exists, creating it if necessary
        
        Args:
            sftp: SFTP client
            directory: Directory path
        """
        if directory == '/' or directory == '':
            return
        
        # Split path into components
        components = directory.split('/')
        current_path = '/' if directory.startswith('/') else ''
        
        # Create each directory component if it doesn't exist
        for component in components:
            if not component:
                continue
            
            current_path = os.path.join(current_path, component)
            
            try:
                sftp.stat(current_path)
            except FileNotFoundError:
                sftp.mkdir(current_path)
    
    @AsyncRetry.retryable(
        max_retries=MAX_RETRIES,
        base_delay=RETRY_DELAY,
        exceptions=(IOError, paramiko.SSHException)
    )
    async def delete_file(self, path: str) -> None:
        """Delete a file
        
        Args:
            path: File path
        """
        sftp = await self.get_sftp_client()
        try:
            sftp.remove(path)
        finally:
            self.release_sftp_client(sftp)
    
    @AsyncRetry.retryable(
        max_retries=MAX_RETRIES,
        base_delay=RETRY_DELAY,
        exceptions=(IOError, paramiko.SSHException)
    )
    async def rename_file(self, old_path: str, new_path: str) -> None:
        """Rename a file
        
        Args:
            old_path: Old file path
            new_path: New file path
        """
        sftp = await self.get_sftp_client()
        try:
            # Ensure directory exists
            directory = os.path.dirname(new_path)
            await self._ensure_directory(sftp, directory)
            
            # Rename file
            sftp.rename(old_path, new_path)
        finally:
            self.release_sftp_client(sftp)
    
    @AsyncRetry.retryable(
        max_retries=MAX_RETRIES,
        base_delay=RETRY_DELAY,
        exceptions=(IOError, paramiko.SSHException)
    )
    async def file_exists(self, path: str) -> bool:
        """Check if a file exists
        
        Args:
            path: File path
            
        Returns:
            bool: True if file exists
        """
        sftp = await self.get_sftp_client()
        try:
            try:
                sftp.stat(path)
                return True
            except FileNotFoundError:
                return False
        finally:
            self.release_sftp_client(sftp)
    
    @AsyncRetry.retryable(
        max_retries=MAX_RETRIES,
        base_delay=RETRY_DELAY,
        exceptions=(IOError, paramiko.SSHException)
    )
    async def get_file_size(self, path: str) -> int:
        """Get file size
        
        Args:
            path: File path
            
        Returns:
            int: File size in bytes
        """
        sftp = await self.get_sftp_client()
        try:
            stats = sftp.stat(path)
            return stats.st_size
        finally:
            self.release_sftp_client(sftp)
    
    @AsyncRetry.retryable(
        max_retries=MAX_RETRIES,
        base_delay=RETRY_DELAY,
        exceptions=(IOError, paramiko.SSHException)
    )
    async def get_file_mtime(self, path: str) -> datetime:
        """Get file modification time
        
        Args:
            path: File path
            
        Returns:
            datetime: File modification time
        """
        sftp = await self.get_sftp_client()
        try:
            stats = sftp.stat(path)
            return datetime.fromtimestamp(stats.st_mtime)
        finally:
            self.release_sftp_client(sftp)
    
    async def watch_directory(
        self,
        path: Optional[str] = None,
        pattern: Optional[str] = None,
        interval: float = 60.0,
        callback: Optional[Callable[[Dict[str, Any]], Any]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Watch a directory for new files
        
        Args:
            path: Directory path (optional - uses base_path if not specified)
            pattern: File pattern glob (optional)
            interval: Polling interval in seconds
            callback: Callback function for new files (optional)
            
        Yields:
            Dict: New file information
        """
        dir_path = path or self.base_path
        seen_files: Dict[str, datetime] = {}
        
        while True:
            try:
                # List directory contents
                files = await self.list_directory(dir_path, pattern)
                
                # Find new files
                for file_info in files:
                    file_path = file_info["path"]
                    file_mtime = file_info["mtime"]
                    
                    # Skip directories
                    if file_info["is_dir"]:
                        continue
                    
                    # Check if file is new or modified
                    if file_path not in seen_files or file_mtime > seen_files[file_path]:
                        seen_files[file_path] = file_mtime
                        
                        # Call callback if provided
                        if callback:
                            await callback(file_info)
                        
                        # Yield file info
                        yield file_info
                
                # Sleep until next check
                await asyncio.sleep(interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error watching directory {dir_path}: {e}")
                await asyncio.sleep(interval)
    
    async def find_csv_files(
        self,
        directory: str,
        pattern: str = "*.csv",
        after_date: Optional[datetime] = None,
        max_files: int = 100
    ) -> List[Dict[str, Any]]:
        """Find CSV files in a directory
        
        Args:
            directory: Directory path
            pattern: File pattern glob (default: *.csv)
            after_date: Only include files modified after this date (optional)
            max_files: Maximum number of files to return
            
        Returns:
            List[Dict]: List of file information
        """
        # List directory contents
        files = await self.list_directory(directory, pattern)
        
        # Filter by date if specified
        if after_date:
            files = [f for f in files if f["mtime"] >= after_date]
        
        # Sort by modification time (newest first)
        files.sort(key=lambda x: x["mtime"], reverse=True)
        
        # Limit to max_files
        return files[:max_files]
    
    @AsyncRetry.retryable(
        max_retries=MAX_RETRIES,
        base_delay=RETRY_DELAY,
        exceptions=(IOError, paramiko.SSHException)
    )
    async def upload_file(self, local_path: str, remote_path: str) -> None:
        """Upload a file
        
        Args:
            local_path: Local file path
            remote_path: Remote file path
        """
        # Read local file
        with open(local_path, 'rb') as f:
            content = f.read()
        
        # Write remote file
        await self.write_file(remote_path, content)
    
    @AsyncRetry.retryable(
        max_retries=MAX_RETRIES,
        base_delay=RETRY_DELAY,
        exceptions=(IOError, paramiko.SSHException)
    )
    async def download_file(self, remote_path: str, local_path: str) -> None:
        """Download a file
        
        Args:
            remote_path: Remote file path
            local_path: Local file path
        """
        # Read remote file
        content = await self.read_file(remote_path)
        
        # Write local file
        with open(local_path, 'wb') as f:
            f.write(content)
    
    async def close(self) -> None:
        """Close all connections"""
        self.pool.close_all()