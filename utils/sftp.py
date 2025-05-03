"""
SFTP manager for the Tower of Temptation PvP Statistics Discord Bot.

This module provides:
1. Enhanced SFTP client with connection pooling
2. Auto-reconnection and retry logic
3. Concurrent connection management
4. Caching for improved performance
"""
import asyncio
import functools
import io
import logging
import os
import re
import stat
import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict, List, Optional, Any, Union, Tuple, Set, Callable, TypeVar, AsyncGenerator, Awaitable, cast

import asyncssh
from asyncssh import SSHClient, SSHClientConnection, SFTPClient, SSHException, SFTPAttrs, SFTPError

from utils.async_utils import retryable, AsyncCache, semaphore_gather

logger = logging.getLogger(__name__)

# Type variables
T = TypeVar('T')
ConnT = TypeVar('ConnT')

# Constants
MAX_CONNECTIONS = 5  # Maximum number of concurrent SFTP connections
MAX_RETRIES = 3      # Maximum number of retry attempts for SFTP operations
RETRY_DELAY = 1.0    # Delay between retry attempts in seconds
DEFAULT_TIMEOUT = 30 # Default timeout for SFTP operations in seconds

class SFTPPoolManager:
    """Manager for a pool of SFTP connections"""
    
    def __init__(self):
        """Initialize SFTP pool manager"""
        self.connection_pools: Dict[str, List[Tuple[SSHClientConnection, SFTPClient]]] = {}
        self.connection_semaphores: Dict[str, asyncio.Semaphore] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
    
    def get_pool_key(self, **connection_args) -> str:
        """Generate a unique key for a connection pool
        
        Args:
            **connection_args: Connection arguments
            
        Returns:
            str: Pool key
        """
        hostname = connection_args.get("hostname", "")
        port = connection_args.get("port", 22)
        username = connection_args.get("username", "")
        
        return f"{hostname}:{port}:{username}"
    
    async def get_connection(self, **connection_args) -> Tuple[SSHClientConnection, SFTPClient]:
        """Get an SFTP connection from the pool or create a new one
        
        Args:
            **connection_args: Connection arguments
            
        Returns:
            Tuple[SSHClientConnection, SFTPClient]: SSH connection and SFTP client
            
        Raises:
            SSHException: If connection fails
        """
        pool_key = self.get_pool_key(**connection_args)
        
        # Create a lock for this pool if it doesn't exist
        if pool_key not in self._locks:
            self._locks[pool_key] = asyncio.Lock()
        
        # Create a semaphore for this pool if it doesn't exist
        if pool_key not in self.connection_semaphores:
            self.connection_semaphores[pool_key] = asyncio.Semaphore(MAX_CONNECTIONS)
        
        # Acquire semaphore to limit concurrent connections
        await self.connection_semaphores[pool_key].acquire()
        
        try:
            async with self._locks[pool_key]:
                # Create connection pool if it doesn't exist
                if pool_key not in self.connection_pools:
                    self.connection_pools[pool_key] = []
                
                pool = self.connection_pools[pool_key]
                
                # Try to get a connection from the pool
                while pool:
                    conn, sftp = pool.pop()
                    
                    # Check if connection is still active
                    if conn.is_connected():
                        return conn, sftp
                    else:
                        try:
                            # Close broken connection
                            await sftp.close()
                            conn.close()
                        except Exception as e:
                            logger.warning(f"Error closing broken SFTP connection: {str(e)}")
                
                # Create a new connection
                logger.debug(f"Creating new SFTP connection to {connection_args.get('hostname')}")
                
                # Connect to SSH server
                conn = await asyncssh.connect(
                    **connection_args,
                    known_hosts=None  # Skip host key verification
                )
                
                # Open SFTP client
                sftp = await conn.start_sftp_client()
                
                return conn, sftp
                
        except Exception as e:
            # Release semaphore if connection fails
            self.connection_semaphores[pool_key].release()
            raise e
    
    async def release_connection(self, conn: SSHClientConnection, sftp: SFTPClient, **connection_args):
        """Release a connection back to the pool
        
        Args:
            conn: SSH connection
            sftp: SFTP client
            **connection_args: Connection arguments
        """
        pool_key = self.get_pool_key(**connection_args)
        
        try:
            # If connection is still active, add it back to the pool
            if conn.is_connected():
                async with self._locks[pool_key]:
                    self.connection_pools[pool_key].append((conn, sftp))
            else:
                try:
                    # Close broken connection
                    await sftp.close()
                    conn.close()
                except Exception as e:
                    logger.warning(f"Error closing broken SFTP connection: {str(e)}")
        
        finally:
            # Release semaphore
            self.connection_semaphores[pool_key].release()
    
    async def close_all_connections(self):
        """Close all connections in all pools"""
        for pool_key, pool in self.connection_pools.items():
            logger.debug(f"Closing {len(pool)} connections for {pool_key}")
            
            for conn, sftp in pool:
                try:
                    await sftp.close()
                    conn.close()
                except Exception as e:
                    logger.warning(f"Error closing SFTP connection: {str(e)}")
            
            pool.clear()


class SFTPManager:
    """Enhanced SFTP client with connection pooling and retry logic"""
    
    def __init__(self):
        """Initialize SFTP manager"""
        self.pool_manager = SFTPPoolManager()
    
    @asynccontextmanager
    async def create_connection(self, **connection_args) -> AsyncGenerator[SFTPClient, None]:
        """Create and manage an SFTP connection
        
        Args:
            **connection_args: Connection arguments
            
        Yields:
            SFTPClient: SFTP client
            
        Raises:
            SSHException: If connection fails
        """
        conn = None
        sftp = None
        
        try:
            conn, sftp = await self.pool_manager.get_connection(**connection_args)
            yield sftp
        finally:
            if conn and sftp:
                await self.pool_manager.release_connection(conn, sftp, **connection_args)
    
    @retryable(exceptions=(IOError, SSHException), max_retries=MAX_RETRIES, delay=RETRY_DELAY)
    async def list_directory(self, sftp: SFTPClient, path: str) -> List[SFTPAttrs]:
        """List a directory
        
        Args:
            sftp: SFTP client
            path: Directory path
            
        Returns:
            List[SFTPAttrs]: Directory entries
            
        Raises:
            SSHException: If directory listing fails
        """
        try:
            return await sftp.readdir(path)
        except Exception as e:
            logger.error(f"Error listing directory {path}: {str(e)}")
            raise
    
    @retryable(exceptions=(IOError, SSHException), max_retries=MAX_RETRIES, delay=RETRY_DELAY)
    async def listdir(self, path: str, **connection_args) -> List[str]:
        """List directory contents
        
        Args:
            path: Directory path
            **connection_args: Connection arguments
            
        Returns:
            List[str]: Directory contents
            
        Raises:
            SSHException: If directory listing fails
        """
        async with self.create_connection(**connection_args) as sftp:
            entries = await self.list_directory(sftp, path)
            return [entry.filename for entry in entries if entry.filename not in ('.', '..')]
    
    @retryable(exceptions=(IOError, SSHException), max_retries=MAX_RETRIES, delay=RETRY_DELAY)
    async def listdir_attr(self, path: str, **connection_args) -> List[SFTPAttrs]:
        """List directory contents with attributes
        
        Args:
            path: Directory path
            **connection_args: Connection arguments
            
        Returns:
            List[SFTPAttrs]: Directory entries with attributes
            
        Raises:
            SSHException: If directory listing fails
        """
        async with self.create_connection(**connection_args) as sftp:
            entries = await self.list_directory(sftp, path)
            return [entry for entry in entries if entry.filename not in ('.', '..')]
    
    @retryable(exceptions=(IOError, SSHException), max_retries=MAX_RETRIES, delay=RETRY_DELAY)
    async def get_file_attrs(self, sftp: SFTPClient, path: str) -> SFTPAttrs:
        """Get file attributes
        
        Args:
            sftp: SFTP client
            path: File path
            
        Returns:
            SFTPAttrs: File attributes
            
        Raises:
            SSHException: If file status fails
        """
        try:
            return await sftp.stat(path)
        except Exception as e:
            logger.error(f"Error getting file attributes for {path}: {str(e)}")
            raise
    
    @retryable(exceptions=(IOError, SSHException), max_retries=MAX_RETRIES, delay=RETRY_DELAY)
    async def stat(self, path: str, **connection_args) -> SFTPAttrs:
        """Get file attributes
        
        Args:
            path: File path
            **connection_args: Connection arguments
            
        Returns:
            SFTPAttrs: File attributes
            
        Raises:
            SSHException: If file status fails
        """
        async with self.create_connection(**connection_args) as sftp:
            return await self.get_file_attrs(sftp, path)
    
    @retryable(exceptions=(IOError, SSHException), max_retries=MAX_RETRIES, delay=RETRY_DELAY)
    async def exists(self, path: str, **connection_args) -> bool:
        """Check if a path exists
        
        Args:
            path: Path to check
            **connection_args: Connection arguments
            
        Returns:
            bool: True if path exists
        """
        try:
            async with self.create_connection(**connection_args) as sftp:
                await self.get_file_attrs(sftp, path)
                return True
        except Exception:
            return False
    
    @retryable(exceptions=(IOError, SSHException), max_retries=MAX_RETRIES, delay=RETRY_DELAY)
    async def is_file(self, path: str, **connection_args) -> bool:
        """Check if a path is a file
        
        Args:
            path: Path to check
            **connection_args: Connection arguments
            
        Returns:
            bool: True if path is a file
        """
        try:
            async with self.create_connection(**connection_args) as sftp:
                attrs = await self.get_file_attrs(sftp, path)
                return not stat.S_ISDIR(attrs.permissions)
        except Exception:
            return False
    
    @retryable(exceptions=(IOError, SSHException), max_retries=MAX_RETRIES, delay=RETRY_DELAY)
    async def is_dir(self, path: str, **connection_args) -> bool:
        """Check if a path is a directory
        
        Args:
            path: Path to check
            **connection_args: Connection arguments
            
        Returns:
            bool: True if path is a directory
        """
        try:
            async with self.create_connection(**connection_args) as sftp:
                attrs = await self.get_file_attrs(sftp, path)
                return stat.S_ISDIR(attrs.permissions)
        except Exception:
            return False
    
    @retryable(exceptions=(IOError, SSHException), max_retries=MAX_RETRIES, delay=RETRY_DELAY)
    async def get_file_size(self, path: str, **connection_args) -> int:
        """Get file size
        
        Args:
            path: File path
            **connection_args: Connection arguments
            
        Returns:
            int: File size in bytes
            
        Raises:
            SSHException: If file size retrieval fails
        """
        async with self.create_connection(**connection_args) as sftp:
            attrs = await self.get_file_attrs(sftp, path)
            return attrs.size
    
    @retryable(exceptions=(IOError, SSHException), max_retries=MAX_RETRIES, delay=RETRY_DELAY)
    async def get_modified_time(self, path: str, **connection_args) -> Optional[datetime]:
        """Get file modification time
        
        Args:
            path: File path
            **connection_args: Connection arguments
            
        Returns:
            datetime or None: File modification time
            
        Raises:
            SSHException: If modification time retrieval fails
        """
        async with self.create_connection(**connection_args) as sftp:
            attrs = await self.get_file_attrs(sftp, path)
            if attrs.mtime:
                return datetime.fromtimestamp(attrs.mtime)
            return None
    
    @retryable(exceptions=(IOError, SSHException), max_retries=MAX_RETRIES, delay=RETRY_DELAY)
    async def get_file_content(self, path: str, **connection_args) -> bytes:
        """Get file content
        
        Args:
            path: File path
            **connection_args: Connection arguments
            
        Returns:
            bytes: File content
            
        Raises:
            SSHException: If file retrieval fails
        """
        async with self.create_connection(**connection_args) as sftp:
            try:
                async with sftp.open(path, 'rb') as f:
                    return await f.read()
            except Exception as e:
                logger.error(f"Error reading file {path}: {str(e)}")
                raise
    
    @retryable(exceptions=(IOError, SSHException), max_retries=MAX_RETRIES, delay=RETRY_DELAY)
    async def find_files(self, path: str, pattern: str = None, **connection_args) -> List[str]:
        """Find files in a directory
        
        Args:
            path: Directory path
            pattern: Regex pattern to match filenames
            **connection_args: Connection arguments
            
        Returns:
            List[str]: Files matching pattern
            
        Raises:
            SSHException: If file search fails
        """
        try:
            async with self.create_connection(**connection_args) as sftp:
                entries = await self.list_directory(sftp, path)
                files = [entry.filename for entry in entries 
                        if entry.filename not in ('.', '..') 
                        and not stat.S_ISDIR(entry.permissions)]
                
                if pattern:
                    regex = re.compile(pattern)
                    return [f for f in files if regex.match(f)]
                
                return files
                
        except Exception as e:
            logger.error(f"Error finding files in {path}: {str(e)}")
            raise
    
    @retryable(exceptions=(IOError, SSHException), max_retries=MAX_RETRIES, delay=RETRY_DELAY)
    async def find_files_recursive(
        self, 
        path: str, 
        pattern: str = None, 
        max_depth: int = 5,
        **connection_args
    ) -> List[str]:
        """Find files recursively
        
        Args:
            path: Directory path
            pattern: Regex pattern to match filenames
            max_depth: Maximum recursion depth
            **connection_args: Connection arguments
            
        Returns:
            List[str]: Files matching pattern with paths
            
        Raises:
            SSHException: If file search fails
        """
        async def _find_recursive(current_path: str, depth: int) -> List[str]:
            """Recursive helper function"""
            if depth > max_depth:
                return []
                
            results = []
            
            try:
                entries = await self.list_directory(sftp, current_path)
                
                for entry in entries:
                    if entry.filename in ('.', '..'):
                        continue
                        
                    entry_path = f"{current_path}/{entry.filename}"
                    
                    if stat.S_ISDIR(entry.permissions):
                        # Recursive call for directories
                        subdirectory_files = await _find_recursive(entry_path, depth + 1)
                        results.extend(subdirectory_files)
                    else:
                        # Check if file matches pattern
                        if not pattern or re.match(pattern, entry.filename):
                            results.append(entry_path)
                            
            except Exception as e:
                logger.error(f"Error in recursive search at {current_path}: {str(e)}")
                
            return results
        
        try:
            async with self.create_connection(**connection_args) as sftp:
                return await _find_recursive(path, 0)
                
        except Exception as e:
            logger.error(f"Error in recursive file search for {path}: {str(e)}")
            raise
    
    @retryable(exceptions=(IOError, SSHException), max_retries=MAX_RETRIES, delay=RETRY_DELAY)
    async def get_directory_content(self, path: str, pattern: str = None, **connection_args) -> Dict[str, bytes]:
        """Get content of all files in a directory
        
        Args:
            path: Directory path
            pattern: Regex pattern to match filenames
            **connection_args: Connection arguments
            
        Returns:
            Dict[str, bytes]: Map of filenames to content
            
        Raises:
            SSHException: If directory content retrieval fails
        """
        try:
            files = await self.find_files(path, pattern, **connection_args)
            result = {}
            
            for filename in files:
                file_path = f"{path}/{filename}"
                content = await self.get_file_content(file_path, **connection_args)
                result[filename] = content
                
            return result
                
        except Exception as e:
            logger.error(f"Error getting directory content for {path}: {str(e)}")
            raise
    
    async def close_connections(self):
        """Close all SFTP connections"""
        await self.pool_manager.close_all_connections()
    
    # Context manager support
    async def __aenter__(self):
        """Enter context manager"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager"""
        await self.close_connections()