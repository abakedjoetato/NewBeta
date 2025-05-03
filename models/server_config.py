"""
Server Config model for the Tower of Temptation PvP Statistics Discord Bot.

This module provides:
1. ServerConfig class for storing server-specific settings
2. Methods for creating and retrieving server configs
3. Configuration validation and defaults
"""
import logging
import re
from datetime import datetime
from typing import Dict, List, Optional, Any, Set, Union, TypeVar

from utils.database import get_db
from utils.async_utils import AsyncCache

logger = logging.getLogger(__name__)

# Type variables
SC = TypeVar('SC', bound='ServerConfig')

class ServerConfig:
    """Server Config class for server-specific settings"""
    
    # Default settings
    DEFAULT_SETTINGS = {
        "premium": False,
        "csv_pattern": r"\d{4}\.\d{2}\.\d{2}-\d{2}\.\d{2}\.\d{2}\.csv",
        "leaderboard_size": 10,
        "update_interval": 5,  # minutes
        "sftp_enabled": False,
        "sftp_host": "",
        "sftp_port": 22,
        "sftp_username": "",
        "sftp_password": "",
        "sftp_path": "/logs",
        "faction_enabled": True,
        "player_link_enabled": True,
        "rivalry_enabled": True,
        "theme_color": 0x7289DA,  # Discord Blurple
        "log_channel_id": None,
        "admin_role_ids": [],
        "mod_role_ids": []
    }
    
    def __init__(self, data: Dict[str, Any]):
        """Initialize a server config
        
        Args:
            data: Server config data from database
        """
        self.data = data
        self._id = data.get("_id")
        self.guild_id = data.get("guild_id")
        self.server_id = data.get("server_id")
        self.server_name = data.get("server_name", "Unknown Server")
        self.settings = data.get("settings", {})
        self.created_at = data.get("created_at")
        self.updated_at = data.get("updated_at")
        
        # Apply default settings for missing values
        for key, default_value in self.DEFAULT_SETTINGS.items():
            if key not in self.settings:
                self.settings[key] = default_value
    
    @property
    def id(self) -> str:
        """Get server config ID
        
        Returns:
            str: Server config ID
        """
        return str(self._id)
    
    @property
    def is_premium(self) -> bool:
        """Check if server has premium status
        
        Returns:
            bool: True if server has premium status
        """
        return self.settings.get("premium", False)
    
    @property
    def sftp_config(self) -> Dict[str, Any]:
        """Get SFTP configuration
        
        Returns:
            Dict: SFTP configuration
        """
        return {
            "enabled": self.settings.get("sftp_enabled", False),
            "host": self.settings.get("sftp_host", ""),
            "port": self.settings.get("sftp_port", 22),
            "username": self.settings.get("sftp_username", ""),
            "password": self.settings.get("sftp_password", ""),
            "path": self.settings.get("sftp_path", "/logs")
        }
    
    @property
    def theme_color(self) -> int:
        """Get theme color
        
        Returns:
            int: Theme color
        """
        return self.settings.get("theme_color", 0x7289DA)
    
    @classmethod
    @AsyncCache.cached(ttl=60)
    async def get_by_id(cls, config_id: str) -> Optional['ServerConfig']:
        """Get server config by ID
        
        Args:
            config_id: Server config ID
            
        Returns:
            ServerConfig or None: Server config if found
        """
        db = await get_db()
        config_data = await db.collections["server_configs"].find_one({"_id": config_id})
        
        if not config_data:
            return None
        
        return cls(config_data)
    
    @classmethod
    @AsyncCache.cached(ttl=60)
    async def get_by_guild_id(cls, guild_id: int) -> Optional['ServerConfig']:
        """Get server config by Discord guild ID
        
        Args:
            guild_id: Discord guild ID
            
        Returns:
            ServerConfig or None: Server config if found
        """
        db = await get_db()
        config_data = await db.collections["server_configs"].find_one({"guild_id": guild_id})
        
        if not config_data:
            return None
        
        return cls(config_data)
    
    @classmethod
    @AsyncCache.cached(ttl=60)
    async def get_by_server_id(cls, server_id: str) -> Optional['ServerConfig']:
        """Get server config by server ID
        
        Args:
            server_id: Server ID
            
        Returns:
            ServerConfig or None: Server config if found
        """
        db = await get_db()
        config_data = await db.collections["server_configs"].find_one({"server_id": server_id})
        
        if not config_data:
            return None
        
        return cls(config_data)
    
    @classmethod
    async def get_all(cls) -> List['ServerConfig']:
        """Get all server configs
        
        Returns:
            List[ServerConfig]: List of all server configs
        """
        db = await get_db()
        configs_data = await db.collections["server_configs"].find({}).to_list(length=None)
        
        return [cls(data) for data in configs_data]
    
    @classmethod
    async def create(
        cls,
        guild_id: int,
        server_id: str,
        server_name: str,
        settings: Optional[Dict[str, Any]] = None
    ) -> 'ServerConfig':
        """Create a new server config
        
        Args:
            guild_id: Discord guild ID
            server_id: Server ID
            server_name: Server name
            settings: Server settings (optional)
            
        Returns:
            ServerConfig: Created server config
            
        Raises:
            ValueError: If a config already exists for this guild or server
        """
        # Check if config already exists for this guild
        existing_guild = await cls.get_by_guild_id(guild_id)
        if existing_guild:
            return existing_guild
        
        # Check if config already exists for this server
        existing_server = await cls.get_by_server_id(server_id)
        if existing_server:
            raise ValueError(f"Server config already exists for server ID {server_id}")
        
        now = datetime.utcnow()
        db = await get_db()
        
        # Use default settings if none provided
        if settings is None:
            settings = cls.DEFAULT_SETTINGS.copy()
        
        # Create server config
        config_data = {
            "guild_id": guild_id,
            "server_id": server_id,
            "server_name": server_name,
            "settings": settings,
            "created_at": now,
            "updated_at": now
        }
        
        result = await db.collections["server_configs"].insert_one(config_data)
        config_data["_id"] = result.inserted_id
        
        # Invalidate caches
        AsyncCache.invalidate_all(cls.get_by_guild_id)
        AsyncCache.invalidate_all(cls.get_by_server_id)
        
        return cls(config_data)
    
    async def update(self, settings: Dict[str, Any]) -> 'ServerConfig':
        """Update server config settings
        
        Args:
            settings: Settings to update
            
        Returns:
            ServerConfig: Updated server config
        """
        now = datetime.utcnow()
        db = await get_db()
        
        # Update only specified settings
        for key, value in settings.items():
            self.settings[key] = value
        
        result = await db.collections["server_configs"].update_one(
            {"_id": self._id},
            {
                "$set": {
                    "settings": self.settings,
                    "updated_at": now
                }
            }
        )
        
        # Invalidate caches
        AsyncCache.invalidate(self.__class__.get_by_id, self.id)
        AsyncCache.invalidate(self.__class__.get_by_guild_id, self.guild_id)
        AsyncCache.invalidate(self.__class__.get_by_server_id, self.server_id)
        
        return self
    
    async def update_server_info(self, server_name: str) -> 'ServerConfig':
        """Update server information
        
        Args:
            server_name: New server name
            
        Returns:
            ServerConfig: Updated server config
        """
        now = datetime.utcnow()
        db = await get_db()
        
        self.server_name = server_name
        
        result = await db.collections["server_configs"].update_one(
            {"_id": self._id},
            {
                "$set": {
                    "server_name": server_name,
                    "updated_at": now
                }
            }
        )
        
        # Invalidate caches
        AsyncCache.invalidate(self.__class__.get_by_id, self.id)
        AsyncCache.invalidate(self.__class__.get_by_guild_id, self.guild_id)
        AsyncCache.invalidate(self.__class__.get_by_server_id, self.server_id)
        
        return self
    
    async def delete(self) -> bool:
        """Delete the server config
        
        Returns:
            bool: True if successfully deleted
        """
        db = await get_db()
        
        result = await db.collections["server_configs"].delete_one({"_id": self._id})
        
        # Invalidate caches
        AsyncCache.invalidate(self.__class__.get_by_id, self.id)
        AsyncCache.invalidate(self.__class__.get_by_guild_id, self.guild_id)
        AsyncCache.invalidate(self.__class__.get_by_server_id, self.server_id)
        
        return result.deleted_count > 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert server config to dictionary
        
        Returns:
            Dict: Server config data
        """
        return {
            "id": self.id,
            "guild_id": self.guild_id,
            "server_id": self.server_id,
            "server_name": self.server_name,
            "settings": self.settings,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }