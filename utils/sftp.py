"""
SFTP Manager for the Tower of Temptation PvP Statistics Discord Bot.

This module provides:
1. SFTP connection management
2. Connection pooling
3. File retrieval
4. CSV file filtering
"""
import os
import re
import logging
import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Set, Tuple, BinaryIO, Pattern

import asyncssh
from asyncssh.misc import PermissionDenied, ConnectionLost

from utils.async_utils import AsyncCache, RateLimiter, retryable, semaphore_gather

logger = logging.getLogger(__name__)

class SFTPManager:
    """SFTP connection manager with connection pooling"""
    
    def __init__(self):
        """Initialize SFTP manager"""
        self._connections: Dict[str, Dict[str, Any]] = {}
        self._connection_locks: Dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()
        self._rate_limiter = RateLimiter(calls=5, period=1.0, spread=True)
    
    def _get_conn_key(self, host: str, port: int, username: str, password: Optional[str] = None, key_path: Optional[str] = None) -> str:
        """Get connection key for the given parameters
        
        Args:
            host: SFTP server hostname
            port: SFTP server port
            username: SFTP username
            password: SFTP password (default: None)
            key_path: Path to private key file (default: None)
            
        Returns:
            str: Connection key
        """
        # Create unique connection key
        return f"{username}@{host}:{port}:{password or ''}:{key_path or ''}"
    
    @retryable(max_retries=2, delay=1.0, exceptions=[ConnectionLost, PermissionDenied, OSError])
    async def _create_connection(self, host: str, port: int, username: str, password: Optional[str] = None, key_path: Optional[str] = None) -> Tuple[asyncssh.SSHClient, asyncssh.SFTPClient]:
        """Create new SFTP connection
        
        Args:
            host: SFTP server hostname
            port: SFTP server port
            username: SFTP username
            password: SFTP password (default: None)
            key_path: Path to private key file (default: None)
            
        Returns:
            Tuple[asyncssh.SSHClient, asyncssh.SFTPClient]: SSH client and SFTP client
        """
        # Apply rate limiting
        await self._rate_limiter.acquire()
        
        # Set up connection options
        conn_options = {
            "username": username,
            "port": port,
            "known_hosts": None
        }
        
        # Add authentication
        if password:
            conn_options["password"] = password
        elif key_path:
            if os.path.exists(key_path):
                conn_options["client_keys"] = [key_path]
            else:
                logger.error(f"Private key file not found: {key_path}")
                raise FileNotFoundError(f"Private key file not found: {key_path}")
        
        try:
            # Connect to server
            logger.info(f"Connecting to SFTP server {username}@{host}:{port}")
            ssh_client = await asyncssh.connect(host, **conn_options)
            sftp_client = await ssh_client.start_sftp_client()
            
            logger.info(f"Connected to SFTP server {username}@{host}:{port}")
            return ssh_client, sftp_client
            
        except (OSError, asyncssh.Error) as e:
            logger.error(f"Failed to connect to SFTP server {username}@{host}:{port}: {str(e)}")
            raise
    
    async def get_connection(self, host: str, port: int, username: str, password: Optional[str] = None, key_path: Optional[str] = None) -> Optional[asyncssh.SFTPClient]:
        """Get or create SFTP connection
        
        Args:
            host: SFTP server hostname
            port: SFTP server port
            username: SFTP username
            password: SFTP password (default: None)
            key_path: Path to private key file (default: None)
            
        Returns:
            asyncssh.SFTPClient or None: SFTP client or None if error
        """
        # Get connection key
        conn_key = self._get_conn_key(host, port, username, password, key_path)
        
        # Get or create connection lock
        async with self._global_lock:
            if conn_key not in self._connection_locks:
                self._connection_locks[conn_key] = asyncio.Lock()
        
        # Get connection lock
        lock = self._connection_locks[conn_key]
        
        # Acquire lock for this connection
        async with lock:
            # Check if connection exists
            if conn_key in self._connections:
                conn = self._connections[conn_key]
                
                # Check if connection is still active
                ssh_client = conn["ssh_client"]
                sftp_client = conn["sftp_client"]
                last_used = conn["last_used"]
                
                if ssh_client and sftp_client and not ssh_client.is_closed():
                    # Update last used timestamp
                    conn["last_used"] = time.time()
                    return sftp_client
                else:
                    # Connection is closed, remove it
                    logger.info(f"Removing closed SFTP connection: {conn_key}")
                    del self._connections[conn_key]
            
            try:
                # Create new connection
                ssh_client, sftp_client = await self._create_connection(host, port, username, password, key_path)
                
                # Store connection
                self._connections[conn_key] = {
                    "ssh_client": ssh_client,
                    "sftp_client": sftp_client,
                    "last_used": time.time()
                }
                
                return sftp_client
                
            except Exception as e:
                logger.error(f"Error getting SFTP connection: {str(e)}")
                return None
    
    async def close_connection(self, host: str, port: int, username: str, password: Optional[str] = None, key_path: Optional[str] = None) -> bool:
        """Close SFTP connection
        
        Args:
            host: SFTP server hostname
            port: SFTP server port
            username: SFTP username
            password: SFTP password (default: None)
            key_path: Path to private key file (default: None)
            
        Returns:
            bool: True if connection was closed
        """
        # Get connection key
        conn_key = self._get_conn_key(host, port, username, password, key_path)
        
        # Get connection lock
        async with self._global_lock:
            if conn_key not in self._connection_locks:
                return False
        
        # Get connection lock
        lock = self._connection_locks[conn_key]
        
        # Acquire lock for this connection
        async with lock:
            # Check if connection exists
            if conn_key in self._connections:
                conn = self._connections[conn_key]
                
                # Close connection
                ssh_client = conn["ssh_client"]
                sftp_client = conn["sftp_client"]
                
                if sftp_client:
                    sftp_client.close()
                
                if ssh_client:
                    ssh_client.close()
                
                # Remove connection
                del self._connections[conn_key]
                
                logger.info(f"Closed SFTP connection: {conn_key}")
                return True
            
            return False
    
    async def close_all_connections(self) -> int:
        """Close all SFTP connections
        
        Returns:
            int: Number of closed connections
        """
        closed = 0
        
        # Get all connection keys
        async with self._global_lock:
            conn_keys = list(self._connections.keys())
        
        # Close each connection
        for conn_key in conn_keys:
            async with self._global_lock:
                if conn_key in self._connections:
                    conn = self._connections[conn_key]
                    
                    # Close connection
                    ssh_client = conn["ssh_client"]
                    sftp_client = conn["sftp_client"]
                    
                    if sftp_client:
                        sftp_client.close()
                    
                    if ssh_client:
                        ssh_client.close()
                    
                    # Remove connection
                    del self._connections[conn_key]
                    closed += 1
        
        logger.info(f"Closed {closed} SFTP connections")
        return closed
    
    @retryable(max_retries=2, delay=1.0, exceptions=[ConnectionLost, PermissionDenied, OSError])
    async def list_files(self, sftp: asyncssh.SFTPClient, path: str, pattern: Optional[str] = None) -> List[str]:
        """List files in directory matching pattern
        
        Args:
            sftp: SFTP client
            path: Directory path
            pattern: File pattern regex (default: None)
            
        Returns:
            List[str]: List of filenames
        """
        try:
            # List files in directory
            files = await sftp.readdir(path)
            
            # Filter files by pattern
            if pattern:
                regex = re.compile(pattern)
                return [f.filename for f in files if f.filename and regex.match(f.filename)]
            else:
                return [f.filename for f in files if f.filename]
                
        except (OSError, asyncssh.Error) as e:
            logger.error(f"Error listing files in {path}: {str(e)}")
            raise
    
    @retryable(max_retries=2, delay=1.0, exceptions=[ConnectionLost, PermissionDenied, OSError])
    async def get_file_info(self, sftp: asyncssh.SFTPClient, path: str) -> Optional[Dict[str, Any]]:
        """Get file information
        
        Args:
            sftp: SFTP client
            path: File path
            
        Returns:
            Dict or None: File information or None if error
        """
        try:
            # Get file attributes
            attrs = await sftp.stat(path)
            
            # Extract file information
            return {
                "size": attrs.size,
                "mtime": datetime.fromtimestamp(attrs.mtime),
                "atime": datetime.fromtimestamp(attrs.atime),
                "permissions": attrs.permissions,
                "uid": attrs.uid,
                "gid": attrs.gid,
                "type": "directory" if attrs.type == 4 else "file"
            }
                
        except (OSError, asyncssh.Error) as e:
            logger.error(f"Error getting file info for {path}: {str(e)}")
            return None
    
    @retryable(max_retries=2, delay=1.0, exceptions=[ConnectionLost, PermissionDenied, OSError])
    async def read_file(self, sftp: asyncssh.SFTPClient, path: str) -> Optional[bytes]:
        """Read file contents
        
        Args:
            sftp: SFTP client
            path: File path
            
        Returns:
            bytes or None: File contents or None if error
        """
        try:
            # Open file for reading
            async with sftp.open(path, "rb") as f:
                # Read file contents
                return await f.read()
                
        except (OSError, asyncssh.Error) as e:
            logger.error(f"Error reading file {path}: {str(e)}")
            return None
    
    @retryable(max_retries=2, delay=1.0, exceptions=[ConnectionLost, PermissionDenied, OSError])
    async def read_file_chunk(self, sftp: asyncssh.SFTPClient, path: str, start: int, size: int) -> Optional[bytes]:
        """Read chunk of file
        
        Args:
            sftp: SFTP client
            path: File path
            start: Start position
            size: Chunk size
            
        Returns:
            bytes or None: File chunk or None if error
        """
        try:
            # Open file for reading
            async with sftp.open(path, "rb") as f:
                # Seek to start position
                await f.seek(start)
                
                # Read chunk
                return await f.read(size)
                
        except (OSError, asyncssh.Error) as e:
            logger.error(f"Error reading file chunk {path} (start={start}, size={size}): {str(e)}")
            return None
    
    @retryable(max_retries=2, delay=1.0, exceptions=[ConnectionLost, PermissionDenied, OSError])
    async def write_file(self, sftp: asyncssh.SFTPClient, path: str, data: Union[str, bytes]) -> bool:
        """Write data to file
        
        Args:
            sftp: SFTP client
            path: File path
            data: Data to write
            
        Returns:
            bool: True if successful
        """
        try:
            # Ensure directory exists
            dirname = os.path.dirname(path)
            if dirname:
                try:
                    await sftp.mkdir(dirname, exist_ok=True)
                except asyncssh.SFTPError:
                    pass
            
            # Open file for writing
            async with sftp.open(path, "wb") as f:
                # Write data
                if isinstance(data, str):
                    await f.write(data.encode("utf-8"))
                else:
                    await f.write(data)
                    
            return True
                
        except (OSError, asyncssh.Error) as e:
            logger.error(f"Error writing to file {path}: {str(e)}")
            return False
    
    async def find_csv_files(self, 
                           host: str, 
                           port: int, 
                           username: str, 
                           base_path: str,
                           pattern: Optional[str] = None,
                           recursive: bool = False,
                           password: Optional[str] = None,
                           key_path: Optional[str] = None,
                           min_size: Optional[int] = None,
                           max_age: Optional[datetime] = None,
                           min_age: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Find CSV files on SFTP server
        
        Args:
            host: SFTP server hostname
            port: SFTP server port
            username: SFTP username
            base_path: Base directory path
            pattern: File pattern regex (default: None)
            recursive: Search recursively (default: False)
            password: SFTP password (default: None)
            key_path: Path to private key file (default: None)
            min_size: Minimum file size (default: None)
            max_age: Maximum file age (default: None)
            min_age: Minimum file age (default: None)
            
        Returns:
            List[Dict]: List of file information dictionaries
        """
        # Get SFTP connection
        sftp = await self.get_connection(host, port, username, password, key_path)
        if not sftp:
            logger.error(f"Failed to connect to SFTP server {username}@{host}:{port}")
            return []
        
        try:
            # List files in directory
            files = await self.list_files(sftp, base_path, pattern)
            
            # Get file information for CSV files
            result = []
            for filename in files:
                # Skip directories
                file_path = os.path.join(base_path, filename)
                
                # Get file info
                info = await self.get_file_info(sftp, file_path)
                if not info:
                    continue
                
                # Skip directories
                if info["type"] == "directory":
                    if recursive:
                        # Search recursively
                        sub_files = await self.find_csv_files(
                            host, port, username, file_path, pattern, recursive,
                            password, key_path, min_size, max_age, min_age
                        )
                        result.extend(sub_files)
                    continue
                
                # Apply filters
                if min_size is not None and info["size"] < min_size:
                    continue
                    
                if max_age is not None and info["mtime"] < max_age:
                    continue
                    
                if min_age is not None and info["mtime"] > min_age:
                    continue
                
                # Add file information
                result.append({
                    "filename": filename,
                    "path": file_path,
                    "size": info["size"],
                    "mtime": info["mtime"]
                })
            
            # Sort by modification time (newest first)
            result.sort(key=lambda x: x["mtime"], reverse=True)
            
            return result
            
        except Exception as e:
            logger.error(f"Error finding CSV files on {username}@{host}:{port}: {str(e)}")
            return []
    
    async def download_csv_files(self,
                               host: str,
                               port: int,
                               username: str,
                               files: List[Dict[str, Any]],
                               dest_dir: str,
                               password: Optional[str] = None,
                               key_path: Optional[str] = None,
                               max_concurrent: int = 3) -> List[str]:
        """Download CSV files from SFTP server
        
        Args:
            host: SFTP server hostname
            port: SFTP server port
            username: SFTP username
            files: List of file information dictionaries
            dest_dir: Destination directory
            password: SFTP password (default: None)
            key_path: Path to private key file (default: None)
            max_concurrent: Maximum concurrent downloads (default: 3)
            
        Returns:
            List[str]: List of downloaded file paths
        """
        if not files:
            return []
            
        # Create destination directory if it doesn't exist
        os.makedirs(dest_dir, exist_ok=True)
        
        # Get SFTP connection
        sftp = await self.get_connection(host, port, username, password, key_path)
        if not sftp:
            logger.error(f"Failed to connect to SFTP server {username}@{host}:{port}")
            return []
        
        # Create semaphore for limiting concurrent downloads
        semaphore = asyncio.Semaphore(max_concurrent)
        
        # Define download coroutine
        async def download_file(file_info):
            async with semaphore:
                try:
                    # Read file contents
                    data = await self.read_file(sftp, file_info["path"])
                    if not data:
                        return None
                        
                    # Create destination file path
                    dest_path = os.path.join(dest_dir, file_info["filename"])
                    
                    # Write file to disk
                    with open(dest_path, "wb") as f:
                        f.write(data)
                        
                    logger.info(f"Downloaded {file_info['path']} to {dest_path}")
                    return dest_path
                    
                except Exception as e:
                    logger.error(f"Error downloading file {file_info['path']}: {str(e)}")
                    return None
        
        # Download files concurrently
        results = await asyncio.gather(*[download_file(file) for file in files])
        
        # Filter out failed downloads
        return [path for path in results if path]
    
    async def process_latest_csv(self,
                              host: str,
                              port: int,
                              username: str,
                              base_path: str,
                              processor: callable,
                              pattern: Optional[str] = None,
                              password: Optional[str] = None,
                              key_path: Optional[str] = None,
                              max_age: Optional[timedelta] = None,
                              min_size: int = 100) -> Optional[Dict[str, Any]]:
        """Process latest CSV file from SFTP server
        
        Args:
            host: SFTP server hostname
            port: SFTP server port
            username: SFTP username
            base_path: Base directory path
            processor: Function to process CSV data
            pattern: File pattern regex (default: None)
            password: SFTP password (default: None)
            key_path: Path to private key file (default: None)
            max_age: Maximum file age (default: None)
            min_size: Minimum file size (default: 100)
            
        Returns:
            Dict or None: Processing result or None if error
        """
        # Get SFTP connection
        sftp = await self.get_connection(host, port, username, password, key_path)
        if not sftp:
            logger.error(f"Failed to connect to SFTP server {username}@{host}:{port}")
            return None
        
        try:
            # Find CSV files
            files = await self.find_csv_files(
                host, port, username, base_path, pattern, False,
                password, key_path, min_size,
                datetime.utcnow() - max_age if max_age else None, None
            )
            
            if not files:
                logger.warning(f"No CSV files found on {username}@{host}:{port}:{base_path}")
                return None
                
            # Get latest file
            latest_file = files[0]
            
            # Read file contents
            data = await self.read_file(sftp, latest_file["path"])
            if not data:
                logger.error(f"Failed to read file {latest_file['path']}")
                return None
                
            # Process CSV data
            result = await processor(data, latest_file)
            
            return {
                "file": latest_file,
                "result": result
            }
            
        except Exception as e:
            logger.error(f"Error processing CSV file on {username}@{host}:{port}: {str(e)}")
            return None

# Global SFTP manager instance
_sftp_manager = SFTPManager()

async def get_sftp_manager() -> SFTPManager:
    """Get the SFTP manager instance
    
    Returns:
        SFTPManager: SFTP manager
    """
    return _sftp_manager

async def close_sftp_connections() -> int:
    """Close all SFTP connections
    
    Returns:
        int: Number of closed connections
    """
    return await _sftp_manager.close_all_connections()