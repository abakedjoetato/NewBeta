"""
Database Manager for the Tower of Temptation PvP Statistics Discord Bot.

This module provides:
1. MongoDB connection management
2. Connection pooling
3. Database operations
4. Caching
"""
import os
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Set, Tuple

import motor.motor_asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import pymongo.errors
from pymongo import IndexModel, ASCENDING, DESCENDING

from utils.async_utils import retryable

logger = logging.getLogger(__name__)

class DatabaseManager:
    """MongoDB database manager"""
    
    def __init__(self, uri: str, db_name: str):
        """Initialize database manager
        
        Args:
            uri: MongoDB connection URI
            db_name: Database name
        """
        self.uri = uri
        self.db_name = db_name
        self.client: Optional[AsyncIOMotorClient] = None
        self.db = None
        self._lock = asyncio.Lock()
        self._connected = False
        self._collections: Dict[str, Any] = {}
    
    async def connect(self) -> bool:
        """Connect to MongoDB database
        
        Returns:
            bool: True if connected successfully
        """
        if self._connected and self.client and not self.client.io_loop.is_closed():
            return True
            
        async with self._lock:
            # Check again inside lock
            if self._connected and self.client and not self.client.io_loop.is_closed():
                return True
                
            try:
                # Create client
                logger.info(f"Connecting to MongoDB at {self.uri}")
                self.client = AsyncIOMotorClient(self.uri)
                
                # Test connection
                await self.client.admin.command("ping")
                
                # Get database
                self.db = self.client[self.db_name]
                
                self._connected = True
                logger.info(f"Connected to MongoDB database {self.db_name}")
                
                return True
                
            except Exception as e:
                logger.error(f"Error connecting to MongoDB: {str(e)}")
                self._connected = False
                if self.client:
                    self.client.close()
                    self.client = None
                self.db = None
                return False
    
    async def disconnect(self) -> None:
        """Disconnect from MongoDB database"""
        if self.client:
            self.client.close()
            self.client = None
            
        self._connected = False
        self.db = None
        logger.info("Disconnected from MongoDB")
    
    async def _ensure_connected(self) -> bool:
        """Ensure database connection is established
        
        Returns:
            bool: True if connected
        """
        if not self._connected or not self.client or not self.db:
            return await self.connect()
            
        return True
    
    @retryable(max_retries=3, delay=1.0, exceptions=[pymongo.errors.PyMongoError])
    async def get_document(self, collection: str, query: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Get document from collection
        
        Args:
            collection: Collection name
            query: Query to find document
            
        Returns:
            Dict or None: Document or None if not found
        """
        if not await self._ensure_connected():
            return None
            
        try:
            result = await self.db[collection].find_one(query)
            return result
            
        except pymongo.errors.PyMongoError as e:
            logger.error(f"Error getting document from {collection}: {str(e)}")
            raise
    
    @retryable(max_retries=3, delay=1.0, exceptions=[pymongo.errors.PyMongoError])
    async def get_documents(self, collection: str, query: Dict[str, Any], sort: Optional[List[Tuple[str, int]]] = None, limit: Optional[int] = None, skip: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get documents from collection
        
        Args:
            collection: Collection name
            query: Query to find documents
            sort: Sort criteria (default: None)
            limit: Maximum number of documents to return (default: None)
            skip: Number of documents to skip (default: None)
            
        Returns:
            List[Dict]: List of documents
        """
        if not await self._ensure_connected():
            return []
            
        try:
            cursor = self.db[collection].find(query)
            
            if sort:
                cursor = cursor.sort(sort)
                
            if skip:
                cursor = cursor.skip(skip)
                
            if limit:
                cursor = cursor.limit(limit)
                
            return await cursor.to_list(length=None)
            
        except pymongo.errors.PyMongoError as e:
            logger.error(f"Error getting documents from {collection}: {str(e)}")
            raise
    
    @retryable(max_retries=3, delay=1.0, exceptions=[pymongo.errors.PyMongoError])
    async def count_documents(self, collection: str, query: Dict[str, Any]) -> int:
        """Count documents in collection
        
        Args:
            collection: Collection name
            query: Query to count documents
            
        Returns:
            int: Number of documents
        """
        if not await self._ensure_connected():
            return 0
            
        try:
            return await self.db[collection].count_documents(query)
            
        except pymongo.errors.PyMongoError as e:
            logger.error(f"Error counting documents in {collection}: {str(e)}")
            raise
    
    @retryable(max_retries=3, delay=1.0, exceptions=[pymongo.errors.PyMongoError])
    async def insert_document(self, collection: str, document: Dict[str, Any]) -> Optional[str]:
        """Insert document into collection
        
        Args:
            collection: Collection name
            document: Document to insert
            
        Returns:
            str or None: Document ID or None if error
        """
        if not await self._ensure_connected():
            return None
            
        try:
            result = await self.db[collection].insert_one(document)
            return str(result.inserted_id)
            
        except pymongo.errors.PyMongoError as e:
            logger.error(f"Error inserting document into {collection}: {str(e)}")
            raise
    
    @retryable(max_retries=3, delay=1.0, exceptions=[pymongo.errors.PyMongoError])
    async def insert_documents(self, collection: str, documents: List[Dict[str, Any]]) -> Optional[List[str]]:
        """Insert multiple documents into collection
        
        Args:
            collection: Collection name
            documents: Documents to insert
            
        Returns:
            List[str] or None: Document IDs or None if error
        """
        if not await self._ensure_connected() or not documents:
            return None
            
        try:
            result = await self.db[collection].insert_many(documents)
            return [str(id) for id in result.inserted_ids]
            
        except pymongo.errors.PyMongoError as e:
            logger.error(f"Error inserting documents into {collection}: {str(e)}")
            raise
    
    @retryable(max_retries=3, delay=1.0, exceptions=[pymongo.errors.PyMongoError])
    async def update_document(self, collection: str, query: Dict[str, Any], update: Dict[str, Any], upsert: bool = False) -> bool:
        """Update document in collection
        
        Args:
            collection: Collection name
            query: Query to find document
            update: Update operations
            upsert: Whether to insert if not exists (default: False)
            
        Returns:
            bool: True if successful
        """
        if not await self._ensure_connected():
            return False
            
        try:
            result = await self.db[collection].update_one(query, update, upsert=upsert)
            return result.modified_count > 0 or (upsert and result.upserted_id is not None)
            
        except pymongo.errors.PyMongoError as e:
            logger.error(f"Error updating document in {collection}: {str(e)}")
            raise
    
    @retryable(max_retries=3, delay=1.0, exceptions=[pymongo.errors.PyMongoError])
    async def update_documents(self, collection: str, query: Dict[str, Any], update: Dict[str, Any]) -> int:
        """Update multiple documents in collection
        
        Args:
            collection: Collection name
            query: Query to find documents
            update: Update operations
            
        Returns:
            int: Number of documents updated
        """
        if not await self._ensure_connected():
            return 0
            
        try:
            result = await self.db[collection].update_many(query, update)
            return result.modified_count
            
        except pymongo.errors.PyMongoError as e:
            logger.error(f"Error updating documents in {collection}: {str(e)}")
            raise
    
    @retryable(max_retries=3, delay=1.0, exceptions=[pymongo.errors.PyMongoError])
    async def delete_document(self, collection: str, query: Dict[str, Any]) -> bool:
        """Delete document from collection
        
        Args:
            collection: Collection name
            query: Query to find document
            
        Returns:
            bool: True if successful
        """
        if not await self._ensure_connected():
            return False
            
        try:
            result = await self.db[collection].delete_one(query)
            return result.deleted_count > 0
            
        except pymongo.errors.PyMongoError as e:
            logger.error(f"Error deleting document from {collection}: {str(e)}")
            raise
    
    @retryable(max_retries=3, delay=1.0, exceptions=[pymongo.errors.PyMongoError])
    async def delete_documents(self, collection: str, query: Dict[str, Any]) -> int:
        """Delete multiple documents from collection
        
        Args:
            collection: Collection name
            query: Query to find documents
            
        Returns:
            int: Number of documents deleted
        """
        if not await self._ensure_connected():
            return 0
            
        try:
            result = await self.db[collection].delete_many(query)
            return result.deleted_count
            
        except pymongo.errors.PyMongoError as e:
            logger.error(f"Error deleting documents from {collection}: {str(e)}")
            raise
    
    @retryable(max_retries=3, delay=1.0, exceptions=[pymongo.errors.PyMongoError])
    async def create_index(self, collection: str, keys: List[Tuple[str, int]], unique: bool = False, name: Optional[str] = None) -> str:
        """Create index on collection
        
        Args:
            collection: Collection name
            keys: List of (field, direction) tuples
            unique: Whether index should be unique (default: False)
            name: Index name (default: None)
            
        Returns:
            str: Index name
        """
        if not await self._ensure_connected():
            return ""
            
        try:
            result = await self.db[collection].create_index(keys, unique=unique, name=name)
            return result
            
        except pymongo.errors.PyMongoError as e:
            logger.error(f"Error creating index on {collection}: {str(e)}")
            raise
    
    @retryable(max_retries=3, delay=1.0, exceptions=[pymongo.errors.PyMongoError])
    async def create_indexes(self, collection: str, indexes: List[IndexModel]) -> List[str]:
        """Create multiple indexes on collection
        
        Args:
            collection: Collection name
            indexes: List of IndexModel instances
            
        Returns:
            List[str]: Index names
        """
        if not await self._ensure_connected() or not indexes:
            return []
            
        try:
            result = await self.db[collection].create_indexes(indexes)
            return result
            
        except pymongo.errors.PyMongoError as e:
            logger.error(f"Error creating indexes on {collection}: {str(e)}")
            raise
    
    @retryable(max_retries=3, delay=1.0, exceptions=[pymongo.errors.PyMongoError])
    async def drop_index(self, collection: str, index_name: str) -> bool:
        """Drop index from collection
        
        Args:
            collection: Collection name
            index_name: Index name
            
        Returns:
            bool: True if successful
        """
        if not await self._ensure_connected():
            return False
            
        try:
            await self.db[collection].drop_index(index_name)
            return True
            
        except pymongo.errors.PyMongoError as e:
            logger.error(f"Error dropping index from {collection}: {str(e)}")
            raise
    
    @retryable(max_retries=3, delay=1.0, exceptions=[pymongo.errors.PyMongoError])
    async def drop_indexes(self, collection: str) -> bool:
        """Drop all indexes from collection
        
        Args:
            collection: Collection name
            
        Returns:
            bool: True if successful
        """
        if not await self._ensure_connected():
            return False
            
        try:
            await self.db[collection].drop_indexes()
            return True
            
        except pymongo.errors.PyMongoError as e:
            logger.error(f"Error dropping indexes from {collection}: {str(e)}")
            raise
    
    @retryable(max_retries=3, delay=1.0, exceptions=[pymongo.errors.PyMongoError])
    async def aggregate(self, collection: str, pipeline: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Run aggregation pipeline on collection
        
        Args:
            collection: Collection name
            pipeline: Aggregation pipeline
            
        Returns:
            List[Dict]: Aggregation results
        """
        if not await self._ensure_connected():
            return []
            
        try:
            cursor = self.db[collection].aggregate(pipeline)
            return await cursor.to_list(length=None)
            
        except pymongo.errors.PyMongoError as e:
            logger.error(f"Error running aggregation on {collection}: {str(e)}")
            raise

# Global database manager instance
_db_manager = None

async def initialize_db(uri: Optional[str] = None, db_name: Optional[str] = None) -> bool:
    """Initialize database connection
    
    Args:
        uri: MongoDB connection URI (default: None)
        db_name: Database name (default: None)
        
    Returns:
        bool: True if successful
    """
    global _db_manager
    
    # Get connection info from environment variables if not provided
    uri = uri or os.environ.get("MONGODB_URI")
    db_name = db_name or os.environ.get("MONGODB_DB")
    
    if not uri or not db_name:
        logger.error("MongoDB connection info not set (MONGODB_URI, MONGODB_DB)")
        return False
    
    # Create database manager
    _db_manager = DatabaseManager(uri, db_name)
    
    # Connect to database
    return await _db_manager.connect()

async def get_db() -> DatabaseManager:
    """Get database manager instance
    
    Returns:
        DatabaseManager: Database manager
    """
    global _db_manager
    
    if not _db_manager:
        # Initialize database connection
        await initialize_db()
        
    return _db_manager

async def close_db() -> None:
    """Close database connection"""
    global _db_manager
    
    if _db_manager:
        await _db_manager.disconnect()