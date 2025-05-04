"""
Server model for the Tower of Temptation PvP Statistics Discord Bot.

This module provides a Server class to interact with game server data in MongoDB.
"""
from datetime import datetime
from typing import Dict, List, Optional, Any, Union

class Server:
    """
    Game server model
    """
    
    @staticmethod
    async def create(db, guild_id: str, server_id: str, name: str,
                   sftp_host: Optional[str] = None, sftp_port: int = 22,
                   sftp_username: Optional[str] = None, sftp_password: Optional[str] = None,
                   sftp_directory: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new game server record
        
        Args:
            db: Database connection
            guild_id: Discord guild ID
            server_id: Game server ID
            name: Server name
            sftp_host: SFTP host
            sftp_port: SFTP port
            sftp_username: SFTP username
            sftp_password: SFTP password
            sftp_directory: SFTP directory
            
        Returns:
            Dictionary containing the created server data
        """
        server_data = {
            "guild_id": guild_id,
            "server_id": server_id,
            "name": name,
            "sftp_host": sftp_host,
            "sftp_port": sftp_port,
            "sftp_username": sftp_username,
            "sftp_password": sftp_password,
            "sftp_directory": sftp_directory,
            "active": True,
            "created_at": datetime.utcnow(),
            "last_sync": None
        }
        result = await db.db.game_servers.insert_one(server_data)
        server_data["_id"] = result.inserted_id
        return server_data
    
    @staticmethod
    async def get_by_id(db, guild_id: str, server_id: str) -> Optional[Dict[str, Any]]:
        """
        Get game server by ID
        
        Args:
            db: Database connection
            guild_id: Discord guild ID
            server_id: Game server ID
            
        Returns:
            Server data dictionary or None if not found
        """
        return await db.db.game_servers.find_one({
            "guild_id": guild_id,
            "server_id": server_id
        })
    
    @staticmethod
    async def get_for_guild(db, guild_id: str, active_only: bool = True) -> List[Dict[str, Any]]:
        """
        Get all game servers for a guild
        
        Args:
            db: Database connection
            guild_id: Discord guild ID
            active_only: Only return active servers
            
        Returns:
            List of server data dictionaries
        """
        query = {"guild_id": guild_id}
        if active_only:
            query["active"] = True
            
        cursor = db.db.game_servers.find(query)
        return await cursor.to_list(length=100)
    
    @staticmethod
    async def update_sync(db, guild_id: str, server_id: str) -> None:
        """
        Update the last sync timestamp
        
        Args:
            db: Database connection
            guild_id: Discord guild ID
            server_id: Game server ID
        """
        await db.db.game_servers.update_one(
            {"guild_id": guild_id, "server_id": server_id},
            {"$set": {"last_sync": datetime.utcnow()}}
        )
    
    @staticmethod
    async def update_status(db, guild_id: str, server_id: str, active: bool) -> None:
        """
        Update the active status
        
        Args:
            db: Database connection
            guild_id: Discord guild ID
            server_id: Game server ID
            active: Active status
        """
        await db.db.game_servers.update_one(
            {"guild_id": guild_id, "server_id": server_id},
            {"$set": {"active": active}}
        )