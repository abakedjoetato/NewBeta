"""
Database connection manager for Tower of Temptation PvP Statistics Bot

This module provides a unified interface for MongoDB database connections
and handles connection pooling, reconnection logic, and error handling.
"""
import logging
import os
import asyncio
import motor.motor_asyncio
from typing import Optional, Dict, Any, List, Union
from datetime import datetime
from bson import ObjectId

logger = logging.getLogger(__name__)

class DatabaseManager:
    """MongoDB database connection manager"""
    
    def __init__(self, connection_string: Optional[str] = None, db_name: Optional[str] = None):
        """Initialize database manager
        
        Args:
            connection_string: MongoDB connection string (defaults to MONGODB_URI env var)
            db_name: MongoDB database name (extracted from connection string if not provided)
        """
        # Get connection string from env var if not provided
        self.connection_string = connection_string or os.environ.get("MONGODB_URI")
        if not self.connection_string:
            raise ValueError("MongoDB connection string not provided and MONGODB_URI env var not set")
            
        # Get database name from connection string if not provided
        if not db_name:
            # Extract database name from connection string (after last / and before ?)
            parts = self.connection_string.split("/")
            if len(parts) > 3:
                db_name_part = parts[3].split("?")[0]
                db_name = db_name_part if db_name_part else "tower_of_temptation"
            else:
                db_name = "tower_of_temptation"
        
        self.db_name = db_name
        self._client = None
        self._db = None
        self._connected = False
        self._connection_attempts = 0
        self._max_connection_attempts = 5
        self._reconnection_delay = 1  # Starting delay in seconds
    
    async def connect(self) -> bool:
        """Connect to MongoDB database
        
        Returns:
            True if connected successfully, False otherwise
        """
        if self._connected and self._client and self._db:
            return True
            
        try:
            # Create client and connect
            self._client = motor.motor_asyncio.AsyncIOMotorClient(
                self.connection_string,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000
            )
            
            # Test connection
            await self._client.server_info()
            
            # Get database
            self._db = self._client[self.db_name]
            
            self._connected = True
            self._connection_attempts = 0
            self._reconnection_delay = 1
            
            logger.info(f"Connected to MongoDB database: {self.db_name}")
            return True
            
        except Exception as e:
            self._connected = False
            self._connection_attempts += 1
            
            logger.error(f"Failed to connect to MongoDB database (attempt {self._connection_attempts}): {e}")
            
            if self._connection_attempts >= self._max_connection_attempts:
                logger.critical("Maximum connection attempts reached. Giving up.")
                raise RuntimeError(f"Failed to connect to MongoDB after {self._max_connection_attempts} attempts") from e
                
            # Exponential backoff for reconnection
            delay = min(30, self._reconnection_delay * 2)
            self._reconnection_delay = delay
            
            logger.info(f"Retrying connection in {delay} seconds...")
            await asyncio.sleep(delay)
            
            return await self.connect()
    
    async def disconnect(self):
        """Disconnect from MongoDB database"""
        if self._client:
            self._client.close()
            self._client = None
            self._db = None
            self._connected = False
            logger.info("Disconnected from MongoDB database")
    
    async def ensure_connected(self):
        """Ensure connection to MongoDB database"""
        if not self._connected or not self._client or not self._db:
            await self.connect()
    
    @property
    def db(self):
        """Get database connection
        
        Returns:
            MongoDB database connection
        """
        if not self._connected or not self._db:
            raise RuntimeError("Not connected to MongoDB database")
            
        return self._db
    
    @property
    def client(self):
        """Get client connection
        
        Returns:
            MongoDB client connection
        """
        if not self._connected or not self._client:
            raise RuntimeError("Not connected to MongoDB database")
            
        return self._client
        
    async def get_collection(self, collection_name: str):
        """Get collection by name
        
        Args:
            collection_name: Collection name
            
        Returns:
            MongoDB collection
        """
        await self.ensure_connected()
        return self._db[collection_name]
    
    async def create_indexes(self):
        """Create indexes for all collections"""
        await self.ensure_connected()
        
        # Guild indexes
        await self._db.guilds.create_index("guild_id", unique=True)
        
        # Server indexes
        await self._db.game_servers.create_index("server_id", unique=True)
        await self._db.game_servers.create_index("guild_id")
        
        # Player indexes
        await self._db.players.create_index("player_id", unique=True)
        await self._db.players.create_index("server_id")
        await self._db.players.create_index("name")
        await self._db.players.create_index([("server_id", 1), ("name", 1)])
        
        # Player link indexes
        await self._db.player_links.create_index("link_id", unique=True)
        await self._db.player_links.create_index("player_id")
        await self._db.player_links.create_index("discord_id")
        await self._db.player_links.create_index([("player_id", 1), ("status", 1)])
        await self._db.player_links.create_index([("discord_id", 1), ("status", 1)])
        
        # Economy indexes
        await self._db.economy.create_index("player_id", unique=True)
        await self._db.economy.create_index("discord_id")
        
        # Bounty indexes
        await self._db.bounties.create_index("bounty_id", unique=True)
        await self._db.bounties.create_index("target_id")
        await self._db.bounties.create_index("placed_by_id")
        await self._db.bounties.create_index("server_id")
        await self._db.bounties.create_index("status")
        await self._db.bounties.create_index([("target_id", 1), ("status", 1)])
        await self._db.bounties.create_index([("expires_at", 1), ("status", 1)])
        
        # Kills indexes
        await self._db.kills.create_index([("server_id", 1), ("timestamp", -1)])
        await self._db.kills.create_index([("killer_id", 1), ("timestamp", -1)])
        await self._db.kills.create_index([("victim_id", 1), ("timestamp", -1)])
        
        # Historical data indexes
        await self._db.historical_data.create_index([("server_id", 1), ("date", -1)])
        await self._db.historical_data.create_index([("server_id", 1), ("player_id", 1), ("date", -1)])
        
        logger.info("Created indexes for all collections")
        
    async def initialize(self):
        """Initialize database connection and create indexes"""
        await self.connect()
        await self.create_indexes()
        logger.info("Database initialized successfully")
        
    def __getattr__(self, name):
        """Get collection by attribute name
        
        Args:
            name: Collection name
            
        Returns:
            MongoDB collection
        """
        if not self._connected or not self._db:
            raise RuntimeError("Not connected to MongoDB database")
            
        return self._db[name]