"""
Guild model for the Tower of Temptation PvP Statistics Discord Bot.

This module provides a Guild class to interact with guild data in MongoDB.
"""
from datetime import datetime
from typing import Dict, List, Optional, Any

class Guild:
    """
    Guild (Discord server) model
    """
    
    @staticmethod
    async def create(db, guild_id: str, name: str, premium_tier: int = 0) -> Dict[str, Any]:
        """
        Create a new guild record
        
        Args:
            db: Database connection
            guild_id: Discord guild ID
            name: Guild name
            premium_tier: Premium tier level (0-3)
            
        Returns:
            Dictionary containing the created guild data
        """
        guild_data = {
            "guild_id": guild_id,
            "name": name,
            "premium_tier": premium_tier,
            "join_date": datetime.utcnow(),
            "last_activity": datetime.utcnow()
        }
        result = await db.db.guilds.insert_one(guild_data)
        guild_data["_id"] = result.inserted_id
        return guild_data
    
    @staticmethod
    async def get_by_id(db, guild_id: str) -> Optional[Dict[str, Any]]:
        """
        Get guild by Discord ID
        
        Args:
            db: Database connection
            guild_id: Discord guild ID
            
        Returns:
            Guild data dictionary or None if not found
        """
        return await db.db.guilds.find_one({"guild_id": guild_id})
    
    @staticmethod
    async def update_activity(db, guild_id: str) -> None:
        """
        Update the last activity timestamp
        
        Args:
            db: Database connection
            guild_id: Discord guild ID
        """
        await db.db.guilds.update_one(
            {"guild_id": guild_id},
            {"$set": {"last_activity": datetime.utcnow()}}
        )
    
    @staticmethod
    async def update_premium(db, guild_id: str, premium_tier: int) -> None:
        """
        Update the premium tier level
        
        Args:
            db: Database connection
            guild_id: Discord guild ID
            premium_tier: Premium tier level (0-3)
        """
        await db.db.guilds.update_one(
            {"guild_id": guild_id},
            {"$set": {"premium_tier": premium_tier}}
        )
    
    @staticmethod
    async def get_all(db) -> List[Dict[str, Any]]:
        """
        Get all guilds
        
        Args:
            db: Database connection
            
        Returns:
            List of guild data dictionaries
        """
        cursor = db.db.guilds.find({})
        return await cursor.to_list(length=100)