"""
Player Link model for the Tower of Temptation PvP Statistics Discord Bot.

This module provides:
1. PlayerLink class for linking Discord users to in-game players
2. Methods for creating, retrieving, and managing player links
"""
import logging
import random
import string
from datetime import datetime
from typing import Dict, List, Optional, Any, Union, TypeVar

from utils.database import get_db
from utils.async_utils import AsyncCache

logger = logging.getLogger(__name__)

# Type variables
PL = TypeVar('PL', bound='PlayerLink')

class PlayerLink:
    """PlayerLink class for linking Discord users to in-game players"""
    
    def __init__(self, data: Dict[str, Any]):
        """Initialize a player link
        
        Args:
            data: Player link data from database
        """
        self.data = data
        self._id = data.get("_id")
        self.server_id = data.get("server_id")
        self.guild_id = data.get("guild_id")
        self.discord_id = data.get("discord_id")
        self.player_id = data.get("player_id")
        self.player_name = data.get("player_name")
        self.verify_code = data.get("verify_code")
        self.verified = data.get("verified", False)
        self.created_at = data.get("created_at")
        self.updated_at = data.get("updated_at")
    
    @property
    def id(self) -> str:
        """Get player link ID
        
        Returns:
            str: Player link ID
        """
        return str(self._id)
    
    @classmethod
    @AsyncCache.cached(ttl=60)
    async def get_by_id(cls, link_id: str) -> Optional['PlayerLink']:
        """Get player link by ID
        
        Args:
            link_id: Player link document ID
            
        Returns:
            PlayerLink or None: Player link if found
        """
        db = await get_db()
        link_data = await db.collections["player_links"].find_one({"_id": link_id})
        
        if not link_data:
            return None
        
        return cls(link_data)
    
    @classmethod
    @AsyncCache.cached(ttl=60)
    async def get_by_discord_id(cls, server_id: str, discord_id: str) -> List['PlayerLink']:
        """Get player links by Discord ID
        
        Args:
            server_id: Server ID
            discord_id: Discord user ID
            
        Returns:
            List[PlayerLink]: List of player links
        """
        db = await get_db()
        links_data = await db.collections["player_links"].find({
            "server_id": server_id,
            "discord_id": discord_id
        }).to_list(length=None)
        
        return [cls(link_data) for link_data in links_data]
    
    @classmethod
    @AsyncCache.cached(ttl=60)
    async def get_by_player_id(cls, server_id: str, player_id: str) -> Optional['PlayerLink']:
        """Get player link by player ID
        
        Args:
            server_id: Server ID
            player_id: In-game player ID
            
        Returns:
            PlayerLink or None: Player link if found
        """
        db = await get_db()
        link_data = await db.collections["player_links"].find_one({
            "server_id": server_id,
            "player_id": player_id
        })
        
        if not link_data:
            return None
        
        return cls(link_data)
    
    @classmethod
    async def get_all_for_server(cls, server_id: str) -> List['PlayerLink']:
        """Get all player links for a server
        
        Args:
            server_id: Server ID
            
        Returns:
            List[PlayerLink]: List of player links
        """
        db = await get_db()
        links_data = await db.collections["player_links"].find({
            "server_id": server_id
        }).to_list(length=None)
        
        return [cls(link_data) for link_data in links_data]
    
    @classmethod
    async def create_or_update(
        cls,
        server_id: str,
        guild_id: int,
        discord_id: str,
        player_id: str,
        player_name: str,
        verify_code: Optional[str] = None
    ) -> 'PlayerLink':
        """Create or update a player link
        
        Args:
            server_id: Server ID
            guild_id: Discord guild ID
            discord_id: Discord user ID
            player_id: In-game player ID
            player_name: In-game player name
            verify_code: Verification code (default: None)
            
        Returns:
            PlayerLink: Created or updated player link
        """
        db = await get_db()
        now = datetime.utcnow()
        
        # Check if link already exists
        existing_link = await cls.get_by_player_id(server_id, player_id)
        
        if existing_link:
            # Update existing link
            update_fields = {
                "discord_id": discord_id,
                "player_name": player_name,
                "updated_at": now
            }
            
            if verify_code is not None:
                update_fields["verify_code"] = verify_code
                update_fields["verified"] = False
            
            result = await db.collections["player_links"].update_one(
                {"_id": existing_link._id},
                {"$set": update_fields}
            )
            
            # Update local data
            for key, value in update_fields.items():
                setattr(existing_link, key, value)
                
            # Clear cache
            AsyncCache.invalidate(cls.get_by_id, existing_link.id)
            AsyncCache.invalidate(cls.get_by_player_id, server_id, player_id)
            AsyncCache.invalidate(cls.get_by_discord_id, server_id, discord_id)
            
            return existing_link
        else:
            # Create new link
            # Generate verification code if not provided
            if verify_code is None:
                verify_code = cls._generate_verify_code()
                
            link_data = {
                "server_id": server_id,
                "guild_id": guild_id,
                "discord_id": discord_id,
                "player_id": player_id,
                "player_name": player_name,
                "verify_code": verify_code,
                "verified": False,
                "created_at": now,
                "updated_at": now
            }
            
            result = await db.collections["player_links"].insert_one(link_data)
            link_data["_id"] = result.inserted_id
            
            return cls(link_data)
    
    async def verify(self) -> bool:
        """Mark player link as verified
        
        Returns:
            bool: True if successful
        """
        db = await get_db()
        now = datetime.utcnow()
        
        result = await db.collections["player_links"].update_one(
            {"_id": self._id},
            {
                "$set": {
                    "verified": True,
                    "updated_at": now
                }
            }
        )
        
        if result.modified_count > 0:
            self.verified = True
            self.updated_at = now
            
            # Clear cache
            AsyncCache.invalidate(self.__class__.get_by_id, self.id)
            AsyncCache.invalidate(self.__class__.get_by_player_id, self.server_id, self.player_id)
            AsyncCache.invalidate(self.__class__.get_by_discord_id, self.server_id, self.discord_id)
            
            return True
            
        return False
    
    async def delete(self) -> bool:
        """Delete player link
        
        Returns:
            bool: True if successful
        """
        db = await get_db()
        
        result = await db.collections["player_links"].delete_one({"_id": self._id})
        
        if result.deleted_count > 0:
            # Clear cache
            AsyncCache.invalidate(self.__class__.get_by_id, self.id)
            AsyncCache.invalidate(self.__class__.get_by_player_id, self.server_id, self.player_id)
            AsyncCache.invalidate(self.__class__.get_by_discord_id, self.server_id, self.discord_id)
            
            return True
            
        return False
    
    @staticmethod
    def _generate_verify_code() -> str:
        """Generate a random verification code
        
        Returns:
            str: Verification code
        """
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert player link to dictionary
        
        Returns:
            Dict: Player link data
        """
        return {
            "id": self.id,
            "server_id": self.server_id,
            "guild_id": self.guild_id,
            "discord_id": self.discord_id,
            "player_id": self.player_id,
            "player_name": self.player_name,
            "verified": self.verified,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }