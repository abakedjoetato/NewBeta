"""
Player Link model for the Tower of Temptation PvP Statistics Discord Bot.

This module provides:
1. PlayerLink class for linking Discord users to in-game players
2. Verification methods for ensuring link validity
3. Methods for retrieving linked players for a Discord user
"""
import asyncio
import logging
import random
import string
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set, Union, TypeVar, Tuple

from utils.database import get_db
from utils.async_utils import AsyncCache

logger = logging.getLogger(__name__)

# Type variables
PL = TypeVar('PL', bound='PlayerLink')

class PlayerLink:
    """PlayerLink class for managing player-Discord user links"""
    
    def __init__(self, data: Dict[str, Any]):
        """Initialize a player link
        
        Args:
            data: Player link data from database
        """
        self.data = data
        self._id = data.get("_id")
        self.discord_id = data.get("discord_id")
        self.player_ids = data.get("player_ids", [])
        self.created_at = data.get("created_at")
        self.updated_at = data.get("updated_at")
        self.verification_tokens = data.get("verification_tokens", [])
    
    @property
    def id(self) -> str:
        """Get player link ID
        
        Returns:
            str: Player link ID
        """
        return str(self._id)
    
    def get_player_id_for_server(self, server_id: str) -> Optional[str]:
        """Get linked player ID for a server
        
        Args:
            server_id: Server ID
            
        Returns:
            str or None: Player ID if found
        """
        for link in self.player_ids:
            if link.get("server_id") == server_id:
                return link.get("player_id")
        
        return None
    
    def get_all_linked_players(self) -> List[Dict[str, str]]:
        """Get all linked players
        
        Returns:
            List[Dict]: List of server_id, player_id pairs
        """
        return self.player_ids
    
    @classmethod
    @AsyncCache.cached(ttl=60)
    async def get_by_id(cls, link_id: str) -> Optional['PlayerLink']:
        """Get player link by ID
        
        Args:
            link_id: Player link ID
            
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
    async def get_by_discord_id(cls, discord_id: int) -> Optional['PlayerLink']:
        """Get player link by Discord ID
        
        Args:
            discord_id: Discord user ID
            
        Returns:
            PlayerLink or None: Player link if found
        """
        db = await get_db()
        link_data = await db.collections["player_links"].find_one({"discord_id": discord_id})
        
        if not link_data:
            return None
        
        return cls(link_data)
    
    @classmethod
    @AsyncCache.cached(ttl=60)
    async def get_by_player_id(cls, server_id: str, player_id: str) -> Optional['PlayerLink']:
        """Get player link by player ID
        
        Args:
            server_id: Server ID
            player_id: Player ID
            
        Returns:
            PlayerLink or None: Player link if found
        """
        db = await get_db()
        link_data = await db.collections["player_links"].find_one({
            "player_ids": {
                "$elemMatch": {
                    "server_id": server_id,
                    "player_id": player_id
                }
            }
        })
        
        if not link_data:
            return None
        
        return cls(link_data)
    
    @classmethod
    async def create(cls, discord_id: int) -> 'PlayerLink':
        """Create a new player link
        
        Args:
            discord_id: Discord user ID
            
        Returns:
            PlayerLink: Created player link
            
        Raises:
            ValueError: If player link already exists for this Discord ID
        """
        # Check if player link already exists
        db = await get_db()
        existing_link = await db.collections["player_links"].find_one({
            "discord_id": discord_id
        })
        
        if existing_link:
            raise ValueError(f"Player link already exists for Discord user {discord_id}")
        
        # Create player link
        now = datetime.utcnow()
        link_data = {
            "discord_id": discord_id,
            "player_ids": [],
            "created_at": now,
            "updated_at": now,
            "verification_tokens": []
        }
        
        result = await db.collections["player_links"].insert_one(link_data)
        link_data["_id"] = result.inserted_id
        
        # Invalidate caches
        AsyncCache.invalidate_all(cls.get_by_discord_id)
        
        return cls(link_data)
    
    async def add_player(self, server_id: str, player_id: str) -> bool:
        """Add player to link
        
        Args:
            server_id: Server ID
            player_id: Player ID
            
        Returns:
            bool: True if successfully added
            
        Raises:
            ValueError: If player is already linked to another Discord user
        """
        # Check if player is already linked to another Discord user
        existing_link = await self.__class__.get_by_player_id(server_id, player_id)
        if existing_link and existing_link.discord_id != self.discord_id:
            raise ValueError(f"Player is already linked to Discord user {existing_link.discord_id}")
        
        # Check if player is already linked to this Discord user
        if self.get_player_id_for_server(server_id) == player_id:
            return True  # Already linked, no need to update
        
        # Check if player exists
        db = await get_db()
        player = await db.collections["players"].find_one({
            "server_id": server_id,
            "_id": player_id
        })
        
        if not player:
            raise ValueError(f"Player with ID {player_id} not found on server {server_id}")
        
        # Update link
        now = datetime.utcnow()
        
        # Check if there's an existing link for this server
        existing_server_link = False
        for i, link in enumerate(self.player_ids):
            if link.get("server_id") == server_id:
                # Update existing link
                self.player_ids[i] = {
                    "server_id": server_id,
                    "player_id": player_id,
                    "linked_at": now
                }
                existing_server_link = True
                break
        
        # Add new link if no existing link for this server
        if not existing_server_link:
            self.player_ids.append({
                "server_id": server_id,
                "player_id": player_id,
                "linked_at": now
            })
        
        # Update database
        result = await db.collections["player_links"].update_one(
            {"_id": self._id},
            {
                "$set": {
                    "player_ids": self.player_ids,
                    "updated_at": now
                }
            }
        )
        
        # Update local state
        self.updated_at = now
        
        # Invalidate caches
        AsyncCache.invalidate(self.__class__.get_by_id, self.id)
        AsyncCache.invalidate(self.__class__.get_by_discord_id, self.discord_id)
        AsyncCache.invalidate(self.__class__.get_by_player_id, server_id, player_id)
        
        return result.modified_count > 0
    
    async def remove_player(self, server_id: str) -> bool:
        """Remove player from link
        
        Args:
            server_id: Server ID
            
        Returns:
            bool: True if successfully removed
        """
        # Check if player is linked
        player_id = self.get_player_id_for_server(server_id)
        if not player_id:
            return True  # Not linked, no need to update
        
        # Update link
        now = datetime.utcnow()
        self.player_ids = [link for link in self.player_ids if link.get("server_id") != server_id]
        
        # Update database
        db = await get_db()
        result = await db.collections["player_links"].update_one(
            {"_id": self._id},
            {
                "$set": {
                    "player_ids": self.player_ids,
                    "updated_at": now
                }
            }
        )
        
        # Update local state
        self.updated_at = now
        
        # Invalidate caches
        AsyncCache.invalidate(self.__class__.get_by_id, self.id)
        AsyncCache.invalidate(self.__class__.get_by_discord_id, self.discord_id)
        AsyncCache.invalidate(self.__class__.get_by_player_id, server_id, player_id)
        
        return result.modified_count > 0
    
    async def create_verification_token(self, server_id: str, player_id: str) -> str:
        """Create verification token for player link
        
        Args:
            server_id: Server ID
            player_id: Player ID
            
        Returns:
            str: Verification token
        """
        # Generate random token
        token = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        
        # Add token to database
        now = datetime.utcnow()
        expiry = now + timedelta(hours=1)
        
        token_data = {
            "token": token,
            "server_id": server_id,
            "player_id": player_id,
            "created_at": now,
            "expires_at": expiry
        }
        
        # Add to local state
        self.verification_tokens.append(token_data)
        
        # Update database
        db = await get_db()
        await db.collections["player_links"].update_one(
            {"_id": self._id},
            {
                "$push": {"verification_tokens": token_data},
                "$set": {"updated_at": now}
            }
        )
        
        # Update local state
        self.updated_at = now
        
        # Invalidate caches
        AsyncCache.invalidate(self.__class__.get_by_id, self.id)
        AsyncCache.invalidate(self.__class__.get_by_discord_id, self.discord_id)
        
        return token
    
    async def verify_token(self, token: str) -> Optional[Dict[str, str]]:
        """Verify token and link player
        
        Args:
            token: Verification token
            
        Returns:
            Dict or None: Player info if token is valid
        """
        # Find token
        now = datetime.utcnow()
        for token_data in self.verification_tokens:
            if token_data.get("token") == token and token_data.get("expires_at") > now:
                server_id = token_data.get("server_id")
                player_id = token_data.get("player_id")
                
                # Link player
                await self.add_player(server_id, player_id)
                
                # Remove token
                self.verification_tokens = [t for t in self.verification_tokens if t.get("token") != token]
                
                # Update database
                db = await get_db()
                await db.collections["player_links"].update_one(
                    {"_id": self._id},
                    {
                        "$set": {
                            "verification_tokens": self.verification_tokens,
                            "updated_at": now
                        }
                    }
                )
                
                # Update local state
                self.updated_at = now
                
                # Invalidate caches
                AsyncCache.invalidate(self.__class__.get_by_id, self.id)
                AsyncCache.invalidate(self.__class__.get_by_discord_id, self.discord_id)
                
                return {"server_id": server_id, "player_id": player_id}
        
        return None
    
    async def clean_expired_tokens(self) -> int:
        """Clean expired tokens
        
        Returns:
            int: Number of tokens removed
        """
        now = datetime.utcnow()
        original_count = len(self.verification_tokens)
        
        # Filter out expired tokens
        self.verification_tokens = [t for t in self.verification_tokens if t.get("expires_at") > now]
        
        # Check if any tokens were removed
        removed_count = original_count - len(self.verification_tokens)
        if removed_count > 0:
            # Update database
            db = await get_db()
            await db.collections["player_links"].update_one(
                {"_id": self._id},
                {
                    "$set": {
                        "verification_tokens": self.verification_tokens,
                        "updated_at": now
                    }
                }
            )
            
            # Update local state
            self.updated_at = now
            
            # Invalidate caches
            AsyncCache.invalidate(self.__class__.get_by_id, self.id)
            AsyncCache.invalidate(self.__class__.get_by_discord_id, self.discord_id)
        
        return removed_count
    
    async def delete(self) -> bool:
        """Delete player link
        
        Returns:
            bool: True if successfully deleted
        """
        db = await get_db()
        
        # Delete link
        result = await db.collections["player_links"].delete_one({
            "_id": self._id
        })
        
        # Invalidate caches
        AsyncCache.invalidate(self.__class__.get_by_id, self.id)
        AsyncCache.invalidate(self.__class__.get_by_discord_id, self.discord_id)
        
        for link in self.player_ids:
            server_id = link.get("server_id")
            player_id = link.get("player_id")
            AsyncCache.invalidate(self.__class__.get_by_player_id, server_id, player_id)
        
        return result.deleted_count > 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert player link to dictionary
        
        Returns:
            Dict: Player link data
        """
        return {
            "id": self.id,
            "discord_id": self.discord_id,
            "player_ids": self.player_ids,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }