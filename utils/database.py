"""
MongoDB database utilities for the Tower of Temptation PvP Statistics Discord Bot.

This module provides:
1. Connection pooling for MongoDB connections
2. Automatic retry on transient database errors
3. Configurable query timeouts
4. Enhanced logging and diagnostics
5. Centralized database access
"""
import asyncio
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Tuple, Set

import motor.motor_asyncio
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection
import pymongo.errors
from pymongo import ReturnDocument

from utils.async_utils import BackgroundTask, AsyncRetry

logger = logging.getLogger(__name__)

# Constants for connection management
DEFAULT_CONNECTION_TIMEOUT = 30000  # 30 seconds
DEFAULT_MAX_POOL_SIZE = 10
DEFAULT_MIN_POOL_SIZE = 1
DEFAULT_RETRY_READS = True
DEFAULT_RETRY_WRITES = True
DEFAULT_DATABASE_NAME = "tower_of_temptation"

class MongoDBManager:
    """Centralized MongoDB manager with connection pooling and retry logic
    
    This class provides a common interface for all MongoDB operations
    with retry logic for transient failures.
    """
    
    def __init__(
        self,
        uri: str,
        database_name: str = DEFAULT_DATABASE_NAME,
        connection_timeout_ms: int = DEFAULT_CONNECTION_TIMEOUT,
        max_pool_size: int = DEFAULT_MAX_POOL_SIZE,
        min_pool_size: int = DEFAULT_MIN_POOL_SIZE,
        retry_reads: bool = DEFAULT_RETRY_READS,
        retry_writes: bool = DEFAULT_RETRY_WRITES
    ):
        """Initialize MongoDB manager
        
        Args:
            uri: MongoDB connection URI
            database_name: Database name
            connection_timeout_ms: Connection timeout in milliseconds
            max_pool_size: Maximum connection pool size
            min_pool_size: Minimum connection pool size
            retry_reads: Whether to retry read operations
            retry_writes: Whether to retry write operations
        """
        self.uri = uri
        self.database_name = database_name
        
        # Create MongoDB client with connection pooling
        self.client = AsyncIOMotorClient(
            uri,
            connectTimeoutMS=connection_timeout_ms,
            maxPoolSize=max_pool_size,
            minPoolSize=min_pool_size,
            retryReads=retry_reads,
            retryWrites=retry_writes
        )
        
        # Get database
        self.db = self.client[database_name]
        
        # Define collections (create lazily)
        self.collections: Dict[str, AsyncIOMotorCollection] = {
            # Core server and player data
            "servers": self.db.servers,
            "players": self.db.players,
            "guild_configs": self.db.guild_configs,
            
            # Game data collections
            "kills": self.db.kills,
            "weapons": self.db.weapons,
            "locations": self.db.locations,
            
            # Relationships and social data
            "factions": self.db.factions,
            "faction_members": self.db.faction_members,
            "rivalries": self.db.rivalries,
            "player_links": self.db.player_links,
            
            # Statistics and analytics
            "player_stats": self.db.player_stats,
            "faction_stats": self.db.faction_stats,
            "server_stats": self.db.server_stats,
            
            # Temporal data
            "events": self.db.events,
            "activity_logs": self.db.activity_logs,
            
            # System data
            "system_metrics": self.db.system_metrics,
            "csv_imports": self.db.csv_imports,
            "cache": self.db.cache
        }
        
        # Set up indexes (async)
        self.index_task = BackgroundTask.create(
            self._setup_indexes(),
            name="mongodb_setup_indexes",
            restart_on_failure=True
        )
        
        # Health check task
        self.health_check_task = BackgroundTask.create(
            self._health_check(),
            name="mongodb_health_check",
            restart_on_failure=True
        )
    
    @AsyncRetry.retryable(
        max_retries=3,
        base_delay=1.0,
        max_delay=5.0,
        backoff_factor=2.0,
        exceptions=(pymongo.errors.ConnectionFailure, pymongo.errors.ServerSelectionTimeoutError)
    )
    async def _health_check(self) -> None:
        """Periodic health check for MongoDB connection"""
        while True:
            try:
                # Run a simple command to check connection
                await self.client.admin.command("ping")
                logger.debug("MongoDB health check: Connection OK")
            except Exception as e:
                logger.error(f"MongoDB health check failed: {e}")
                raise  # Let retry decorator handle it
                
            # Sleep for 60 seconds
            await asyncio.sleep(60)
    
    async def _setup_indexes(self) -> None:
        """Set up database indexes for optimized queries"""
        try:
            # Wait a bit before setting up indexes to ensure connection is ready
            await asyncio.sleep(5)
            
            # Servers collection
            await self.collections["servers"].create_index([("server_id", 1)], unique=True)
            
            # Players collection
            await self.collections["players"].create_index([("server_id", 1), ("name", 1)], unique=True)
            await self.collections["players"].create_index([("server_id", 1), ("kills", -1)])
            await self.collections["players"].create_index([("server_id", 1), ("deaths", -1)])
            
            # Guild configs collection
            await self.collections["guild_configs"].create_index([("guild_id", 1)], unique=True)
            
            # Kills collection
            await self.collections["kills"].create_index([("server_id", 1), ("timestamp", -1)])
            await self.collections["kills"].create_index([("server_id", 1), ("killer_id", 1), ("timestamp", -1)])
            await self.collections["kills"].create_index([("server_id", 1), ("victim_id", 1), ("timestamp", -1)])
            
            # Weapons collection
            await self.collections["weapons"].create_index([("server_id", 1), ("name", 1)], unique=True)
            
            # Locations collection
            await self.collections["locations"].create_index([("server_id", 1), ("name", 1)], unique=True)
            
            # Factions collection
            await self.collections["factions"].create_index([("server_id", 1), ("name", 1)], unique=True)
            await self.collections["factions"].create_index([("server_id", 1), ("tag", 1)], unique=True)
            
            # Faction members collection
            await self.collections["faction_members"].create_index([("faction_id", 1), ("player_id", 1)], unique=True)
            await self.collections["faction_members"].create_index([("player_id", 1)])
            
            # Rivalries collection
            await self.collections["rivalries"].create_index([("server_id", 1), ("player1_id", 1), ("player2_id", 1)], unique=True)
            await self.collections["rivalries"].create_index([("server_id", 1), ("total_kills", -1)])
            
            # Player links collection
            await self.collections["player_links"].create_index([("discord_id", 1)], unique=True)
            await self.collections["player_links"].create_index([("player_ids.server_id", 1), ("player_ids.player_id", 1)])
            
            # Statistics collections
            await self.collections["player_stats"].create_index([("player_id", 1), ("stat_type", 1)], unique=True)
            await self.collections["faction_stats"].create_index([("faction_id", 1), ("stat_type", 1)], unique=True)
            await self.collections["server_stats"].create_index([("server_id", 1), ("stat_type", 1)], unique=True)
            
            # Event collection
            await self.collections["events"].create_index([("server_id", 1), ("timestamp", -1)])
            await self.collections["events"].create_index([("event_type", 1), ("timestamp", -1)])
            
            # CSV imports collection
            await self.collections["csv_imports"].create_index([("server_id", 1), ("filename", 1)], unique=True)
            await self.collections["csv_imports"].create_index([("server_id", 1), ("import_time", -1)])
            
            # Cache collection
            await self.collections["cache"].create_index([("key", 1)], unique=True)
            await self.collections["cache"].create_index([("expiry", 1)], expireAfterSeconds=0)
            
            logger.info("MongoDB indexes setup complete")
            
        except Exception as e:
            logger.error(f"Error setting up MongoDB indexes: {e}")
            raise
    
    @AsyncRetry.retryable(
        max_retries=3,
        base_delay=1.0,
        max_delay=5.0,
        backoff_factor=2.0,
        exceptions=(pymongo.errors.ConnectionFailure, pymongo.errors.ServerSelectionTimeoutError)
    )
    async def get_server_by_id(self, server_id: str) -> Optional[Dict[str, Any]]:
        """Get server by ID
        
        Args:
            server_id: Server ID
            
        Returns:
            Dict or None: Server data if found
        """
        return await self.collections["servers"].find_one({"server_id": server_id})
    
    @AsyncRetry.retryable(
        max_retries=3,
        base_delay=1.0,
        max_delay=5.0,
        backoff_factor=2.0,
        exceptions=(pymongo.errors.ConnectionFailure, pymongo.errors.ServerSelectionTimeoutError)
    )
    async def get_servers(self) -> List[Dict[str, Any]]:
        """Get all servers
        
        Returns:
            List[Dict]: List of servers
        """
        cursor = self.collections["servers"].find()
        return await cursor.to_list(length=None)
    
    @AsyncRetry.retryable(
        max_retries=3,
        base_delay=1.0,
        max_delay=5.0,
        backoff_factor=2.0,
        exceptions=(pymongo.errors.ConnectionFailure, pymongo.errors.ServerSelectionTimeoutError)
    )
    async def get_guild_config(self, guild_id: int) -> Optional[Dict[str, Any]]:
        """Get Discord guild configuration
        
        Args:
            guild_id: Discord guild ID
            
        Returns:
            Dict or None: Guild configuration if found
        """
        return await self.collections["guild_configs"].find_one({"guild_id": guild_id})
    
    @AsyncRetry.retryable(
        max_retries=3,
        base_delay=1.0,
        max_delay=5.0,
        backoff_factor=2.0,
        exceptions=(pymongo.errors.ConnectionFailure, pymongo.errors.ServerSelectionTimeoutError)
    )
    async def update_guild_config(
        self,
        guild_id: int,
        update_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Update Discord guild configuration
        
        Args:
            guild_id: Discord guild ID
            update_data: Update data
            
        Returns:
            Dict or None: Updated guild configuration
        """
        result = await self.collections["guild_configs"].find_one_and_update(
            {"guild_id": guild_id},
            {"$set": {**update_data, "updated_at": datetime.utcnow()}},
            upsert=True,
            return_document=ReturnDocument.AFTER
        )
        return result
    
    @AsyncRetry.retryable(
        max_retries=3,
        base_delay=1.0,
        max_delay=5.0,
        backoff_factor=2.0,
        exceptions=(pymongo.errors.ConnectionFailure, pymongo.errors.ServerSelectionTimeoutError)
    )
    async def get_player_by_name(
        self,
        server_id: str,
        player_name: str
    ) -> Optional[Dict[str, Any]]:
        """Get player by name
        
        Args:
            server_id: Server ID
            player_name: Player name
            
        Returns:
            Dict or None: Player data if found
        """
        return await self.collections["players"].find_one({
            "server_id": server_id,
            "name": player_name
        })
    
    @AsyncRetry.retryable(
        max_retries=3,
        base_delay=1.0,
        max_delay=5.0,
        backoff_factor=2.0,
        exceptions=(pymongo.errors.ConnectionFailure, pymongo.errors.ServerSelectionTimeoutError)
    )
    async def get_top_players(
        self,
        server_id: str,
        sort_by: str = "kills",
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get top players
        
        Args:
            server_id: Server ID
            sort_by: Field to sort by (default: kills)
            limit: Maximum number of players to return (default: 10)
            
        Returns:
            List[Dict]: List of top players
        """
        sort_field = sort_by if sort_by in ["kills", "deaths", "last_seen"] else "kills"
        sort_direction = -1  # Descending
        
        cursor = self.collections["players"].find(
            {"server_id": server_id}
        ).sort(sort_field, sort_direction).limit(limit)
        
        return await cursor.to_list(length=None)
    
    @AsyncRetry.retryable(
        max_retries=3,
        base_delay=1.0,
        max_delay=5.0,
        backoff_factor=2.0,
        exceptions=(pymongo.errors.ConnectionFailure, pymongo.errors.ServerSelectionTimeoutError)
    )
    async def get_recent_kills(
        self,
        server_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get recent kills
        
        Args:
            server_id: Server ID
            limit: Maximum number of kills to return (default: 10)
            
        Returns:
            List[Dict]: List of recent kills
        """
        cursor = self.collections["kills"].find(
            {"server_id": server_id}
        ).sort("timestamp", -1).limit(limit)
        
        return await cursor.to_list(length=None)
    
    async def close(self) -> None:
        """Close MongoDB connection"""
        if self.health_check_task:
            self.health_check_task.cancel()
        
        if self.index_task:
            self.index_task.cancel()
        
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed")

# Singleton instance
_mongodb_manager: Optional[MongoDBManager] = None

async def get_db() -> MongoDBManager:
    """Get MongoDB manager instance
    
    Returns:
        MongoDBManager: MongoDB manager
    """
    global _mongodb_manager
    
    if _mongodb_manager is None:
        # Get MongoDB URI from environment
        mongodb_uri = os.environ.get("MONGODB_URI")
        if not mongodb_uri:
            raise ValueError("MONGODB_URI environment variable is not set")
        
        # Create MongoDB manager
        _mongodb_manager = MongoDBManager(mongodb_uri)
        logger.info("MongoDB manager initialized")
    
    return _mongodb_manager