"""
Player Link model for the Tower of Temptation PvP Statistics Discord Bot.

This module provides a PlayerLink class to link Discord users to in-game players.
"""
from datetime import datetime
from typing import Dict, List, Optional, Any, Union

class PlayerLink:
    """
    Player Link model for connecting Discord users to in-game players
    """
    
    @staticmethod
    async def create(db, discord_id: str, guild_id: str, server_id: str, 
                   player_id: str, player_name: str) -> Dict[str, Any]:
        """
        Create a new player link record
        
        Args:
            db: Database connection
            discord_id: Discord user ID
            guild_id: Discord guild ID
            server_id: Game server ID
            player_id: Player ID in the game
            player_name: Player name in the game
            
        Returns:
            Dictionary containing the created player link data
        """
        link_data = {
            "discord_id": discord_id,
            "guild_id": guild_id,
            "server_id": server_id,
            "player_id": player_id,
            "player_name": player_name,
            "created_at": datetime.utcnow(),
            "last_updated": datetime.utcnow(),
            "verified": False
        }
        result = await db.db.player_links.insert_one(link_data)
        link_data["_id"] = result.inserted_id
        return link_data
    
    @staticmethod
    async def get_by_discord_id(db, discord_id: str, guild_id: str) -> List[Dict[str, Any]]:
        """
        Get all player links for a Discord user in a guild
        
        Args:
            db: Database connection
            discord_id: Discord user ID
            guild_id: Discord guild ID
            
        Returns:
            List of player link data dictionaries
        """
        cursor = db.db.player_links.find({
            "discord_id": discord_id,
            "guild_id": guild_id
        })
        return await cursor.to_list(length=100)
    
    @staticmethod
    async def get_by_player_id(db, server_id: str, player_id: str) -> List[Dict[str, Any]]:
        """
        Get all player links for a game player
        
        Args:
            db: Database connection
            server_id: Game server ID
            player_id: Player ID in the game
            
        Returns:
            List of player link data dictionaries
        """
        cursor = db.db.player_links.find({
            "server_id": server_id,
            "player_id": player_id
        })
        return await cursor.to_list(length=100)
    
    @staticmethod
    async def get_specific_link(db, discord_id: str, guild_id: str, 
                              server_id: str, player_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific player link
        
        Args:
            db: Database connection
            discord_id: Discord user ID
            guild_id: Discord guild ID
            server_id: Game server ID
            player_id: Player ID in the game
            
        Returns:
            Player link data dictionary or None if not found
        """
        return await db.db.player_links.find_one({
            "discord_id": discord_id,
            "guild_id": guild_id,
            "server_id": server_id,
            "player_id": player_id
        })
    
    @staticmethod
    async def verify_link(db, discord_id: str, guild_id: str, 
                        server_id: str, player_id: str) -> bool:
        """
        Mark a player link as verified
        
        Args:
            db: Database connection
            discord_id: Discord user ID
            guild_id: Discord guild ID
            server_id: Game server ID
            player_id: Player ID in the game
            
        Returns:
            True if successful, False otherwise
        """
        result = await db.db.player_links.update_one(
            {
                "discord_id": discord_id,
                "guild_id": guild_id,
                "server_id": server_id,
                "player_id": player_id
            },
            {
                "$set": {
                    "verified": True,
                    "last_updated": datetime.utcnow()
                }
            }
        )
        return result.modified_count > 0
    
    @staticmethod
    async def remove_link(db, discord_id: str, guild_id: str, 
                        server_id: str, player_id: str) -> bool:
        """
        Remove a player link
        
        Args:
            db: Database connection
            discord_id: Discord user ID
            guild_id: Discord guild ID
            server_id: Game server ID
            player_id: Player ID in the game
            
        Returns:
            True if successful, False otherwise
        """
        result = await db.db.player_links.delete_one({
            "discord_id": discord_id,
            "guild_id": guild_id,
            "server_id": server_id,
            "player_id": player_id
        })
        return result.deleted_count > 0