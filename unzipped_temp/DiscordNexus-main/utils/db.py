"""
Database utility functions for MongoDB connections and operations
"""
import os
import logging
import asyncio
import motor.motor_asyncio
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from typing import Optional, Dict, Any, List, TypeVar, Awaitable

from config import MONGODB_SETTINGS, COLLECTIONS

logger = logging.getLogger(__name__)

# Define a TypeVar for the return type of database operations
T = TypeVar('T')

async def initialize_db():
    """Initialize MongoDB connection and return database object"""
    mongodb_uri = os.getenv("MONGODB_URI")
    if not mongodb_uri:
        logger.critical("MONGODB_URI environment variable not set. Exiting.")
        raise ValueError("MONGODB_URI environment variable not set")
    
    try:
        # Create client with configuration
        client = motor.motor_asyncio.AsyncIOMotorClient(
            mongodb_uri, 
            **MONGODB_SETTINGS
        )
        
        # Check connection
        await client.admin.command('ping')
        logger.info("Connected to MongoDB successfully")
        
        # Get database
        db_name = os.getenv("MONGODB_DB", "pvp_stats_bot")
        db = client[db_name]
        
        # Create collections and indexes
        await create_collections_and_indexes(db)
        
        return db
    except (ConnectionFailure, ServerSelectionTimeoutError) as e:
        logger.critical(f"Failed to connect to MongoDB: {e}")
        raise

async def db_operation_with_timeout(operation: Awaitable[T], timeout: float = 2.0, operation_name: str = "db_operation") -> Optional[T]:
    """Execute a database operation with timeout protection
    
    Args:
        operation: The database operation coroutine to execute
        timeout: Timeout in seconds (default: 2.0)
        operation_name: Name of the operation for logging
        
    Returns:
        The result of the operation, or None if timeout or error occurs
    """
    try:
        return await asyncio.wait_for(operation, timeout=timeout)
    except asyncio.TimeoutError:
        logger.warning(f"Timeout in database operation: {operation_name} (timeout: {timeout}s)")
        return None
    except Exception as e:
        logger.error(f"Error in database operation {operation_name}: {e}", exc_info=True)
        return None

async def create_collections_and_indexes(db):
    """Create necessary collections and indexes"""
    try:
        # Ensure collections exist (MongoDB creates them on first access)
        for collection_name in COLLECTIONS.values():
            try:
                await db_operation_with_timeout(
                    db.create_collection(collection_name),
                    timeout=3.0,
                    operation_name=f"create_collection({collection_name})"
                )
                logger.info(f"Created collection: {collection_name}")
            except:
                # Collection already exists
                pass
        
        # Create indexes
        # Guild collection indexes
        await db[COLLECTIONS["guilds"]].create_index("guild_id", unique=True)
        
        # Players collection indexes
        await db[COLLECTIONS["players"]].create_index([
            ("server_id", 1),
            ("player_id", 1)
        ], unique=True)
        await db[COLLECTIONS["players"]].create_index("player_name")
        
        # Kills collection indexes
        await db[COLLECTIONS["kills"]].create_index([
            ("server_id", 1),
            ("timestamp", 1)
        ])
        await db[COLLECTIONS["kills"]].create_index("killer_id")
        await db[COLLECTIONS["kills"]].create_index("victim_id")
        
        # Events collection indexes
        await db[COLLECTIONS["events"]].create_index([
            ("server_id", 1),
            ("timestamp", 1)
        ])
        await db[COLLECTIONS["events"]].create_index("event_type")
        
        # Connections collection indexes
        await db[COLLECTIONS["connections"]].create_index([
            ("server_id", 1),
            ("player_id", 1),
            ("timestamp", 1)
        ])
        
        # Economy collection indexes
        await db[COLLECTIONS["economy"]].create_index([
            ("server_id", 1),
            ("player_id", 1)
        ], unique=True)
        
        # Transactions collection indexes
        await db[COLLECTIONS["transactions"]].create_index([
            ("server_id", 1),
            ("player_id", 1),
            ("timestamp", 1)
        ])
        await db[COLLECTIONS["transactions"]].create_index("source")
        
        logger.info("Created all necessary indexes")
    except Exception as e:
        logger.error(f"Error creating collections or indexes: {e}", exc_info=True)
        raise
