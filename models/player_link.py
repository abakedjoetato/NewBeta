"""
Player Link model for the Tower of Temptation PvP Statistics Discord Bot.

This module provides:
1. PlayerLink class for linking Discord users to in-game players
2. Methods for creating, retrieving, and managing player links
3. Verification token system for confirming player ownership
"""
import asyncio
import logging
import random
import string
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set, Union, TypeVar

from utils.database import get_db
from utils.async_utils import AsyncCache

logger = logging.getLogger(__name__)

# Type variables
PL = TypeVar('PL', bound='PlayerLink')

class PlayerLink:
    """Player Link class for linking Discord users to in-game players"""
    
    def __init__(self, data: Dict[str, Any]):
        """Initialize a player link
        
        Args:
            data: Player link data from database
        """
        self.data = data
        self._id = data.get("_id")
        self.discord_id = data.get("discord_id")
        self.players = data.get("players", [])
        self.pending_verifications = data.get("pending_verifications", [])
        self.created_at = data.get("created_at")
        self.updated_at = data.get("updated_at")
    
    @property
    def id(self) -> str:
        """Get player link ID
        
        Returns:
            str: Player link ID
        """
        return str(self._id)
    
    def get_player_id_for_server(self, server_id: str) -> Optional[str]:
        """Get player ID for a server
        
        Args:
            server_id: Server ID
            
        Returns:
            str or None: Player ID if found
        """
        for player in self.players:
            if player.get("server_id") == server_id:
                return player.get("player_id")
        
        return None
    
    def get_all_linked_players(self) -> List[Dict[str, Any]]:
        """Get all linked players
        
        Returns:
            List[Dict]: List of linked players
        """
        return self.players
    
    @classmethod
    @AsyncCache.cached(ttl=60)
    async def get_by_id(cls, player_link_id: str) -> Optional['PlayerLink']:
        """Get player link by ID
        
        Args:
            player_link_id: Player link ID
            
        Returns:
            PlayerLink or None: Player link if found
        """
        db = await get_db()
        player_link_data = await db.collections["player_links"].find_one({"_id": player_link_id})
        
        if not player_link_data:
            return None
        
        return cls(player_link_data)
    
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
        player_link_data = await db.collections["player_links"].find_one({"discord_id": discord_id})
        
        if not player_link_data:
            return None
        
        return cls(player_link_data)
    
    @classmethod
    @AsyncCache.cached(ttl=60)
    async def get_by_player_id(cls, server_id: str, player_id: str) -> Optional['PlayerLink']:
        """Get player link by server ID and player ID
        
        Args:
            server_id: Server ID
            player_id: Player ID
            
        Returns:
            PlayerLink or None: Player link if found
        """
        db = await get_db()
        player_link_data = await db.collections["player_links"].find_one({
            "players": {
                "$elemMatch": {
                    "server_id": server_id,
                    "player_id": player_id
                }
            }
        })
        
        if not player_link_data:
            return None
        
        return cls(player_link_data)
    
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
        existing_link = await cls.get_by_discord_id(discord_id)
        if existing_link:
            return existing_link
        
        now = datetime.utcnow()
        db = await get_db()
        
        # Create player link
        player_link_data = {
            "discord_id": discord_id,
            "players": [],
            "pending_verifications": [],
            "created_at": now,
            "updated_at": now
        }
        
        result = await db.collections["player_links"].insert_one(player_link_data)
        player_link_data["_id"] = result.inserted_id
        
        # Invalidate caches
        AsyncCache.invalidate_all(cls.get_by_discord_id)
        
        return cls(player_link_data)
    
    async def add_player(self, server_id: str, player_id: str) -> bool:
        """Add a player to the link
        
        Args:
            server_id: Server ID
            player_id: Player ID
            
        Returns:
            bool: True if successfully added
            
        Raises:
            ValueError: If player is already linked to another Discord user
        """
        # Check if player is already linked to someone else
        existing_link = await self.__class__.get_by_player_id(server_id, player_id)
        if existing_link and existing_link.discord_id != self.discord_id:
            raise ValueError(f"Player is already linked to Discord user ID {existing_link.discord_id}")
        
        # Check if player is already in this link
        for player in self.players:
            if player.get("server_id") == server_id and player.get("player_id") == player_id:
                # Already linked
                return True
        
        # Add player to link
        now = datetime.utcnow()
        db = await get_db()
        
        # Check if server already has a linked player
        for i, player in enumerate(self.players):
            if player.get("server_id") == server_id:
                # Replace existing link for this server
                self.players[i] = {
                    "server_id": server_id,
                    "player_id": player_id,
                    "linked_at": now
                }
                
                result = await db.collections["player_links"].update_one(
                    {"_id": self._id},
                    {
                        "$set": {
                            f"players.{i}": {
                                "server_id": server_id,
                                "player_id": player_id,
                                "linked_at": now
                            },
                            "updated_at": now
                        }
                    }
                )
                
                # Invalidate caches
                AsyncCache.invalidate(self.__class__.get_by_id, self.id)
                AsyncCache.invalidate(self.__class__.get_by_discord_id, self.discord_id)
                AsyncCache.invalidate(self.__class__.get_by_player_id, server_id, player_id)
                
                return True
        
        # Add new link
        self.players.append({
            "server_id": server_id,
            "player_id": player_id,
            "linked_at": now
        })
        
        result = await db.collections["player_links"].update_one(
            {"_id": self._id},
            {
                "$push": {
                    "players": {
                        "server_id": server_id,
                        "player_id": player_id,
                        "linked_at": now
                    }
                },
                "$set": {
                    "updated_at": now
                }
            }
        )
        
        # Invalidate caches
        AsyncCache.invalidate(self.__class__.get_by_id, self.id)
        AsyncCache.invalidate(self.__class__.get_by_discord_id, self.discord_id)
        AsyncCache.invalidate(self.__class__.get_by_player_id, server_id, player_id)
        
        return True
    
    async def remove_player(self, server_id: str) -> bool:
        """Remove a player from the link
        
        Args:
            server_id: Server ID
            
        Returns:
            bool: True if successfully removed
        """
        # Check if player is in this link
        player_found = False
        for player in self.players:
            if player.get("server_id") == server_id:
                player_found = True
                break
        
        if not player_found:
            return False
        
        # Remove player from link
        now = datetime.utcnow()
        db = await get_db()
        
        self.players = [p for p in self.players if p.get("server_id") != server_id]
        
        result = await db.collections["player_links"].update_one(
            {"_id": self._id},
            {
                "$pull": {
                    "players": {
                        "server_id": server_id
                    }
                },
                "$set": {
                    "updated_at": now
                }
            }
        )
        
        # Invalidate caches
        AsyncCache.invalidate(self.__class__.get_by_id, self.id)
        AsyncCache.invalidate(self.__class__.get_by_discord_id, self.discord_id)
        AsyncCache.invalidate_all(self.__class__.get_by_player_id)
        
        return True
    
    async def create_verification_token(self, server_id: str, player_id: str) -> str:
        """Create a verification token for a player
        
        Args:
            server_id: Server ID
            player_id: Player ID
            
        Returns:
            str: Verification token
        """
        # Generate random token
        token = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        
        # Set expiration time (1 hour from now)
        expiration = datetime.utcnow() + timedelta(hours=1)
        
        # Add to pending verifications
        now = datetime.utcnow()
        db = await get_db()
        
        # Remove any existing verification for this server
        for i, verification in enumerate(self.pending_verifications):
            if verification.get("server_id") == server_id:
                del self.pending_verifications[i]
                break
        
        # Add new verification
        verification_data = {
            "token": token,
            "server_id": server_id,
            "player_id": player_id,
            "created_at": now,
            "expires_at": expiration
        }
        
        self.pending_verifications.append(verification_data)
        
        result = await db.collections["player_links"].update_one(
            {"_id": self._id},
            {
                "$pull": {
                    "pending_verifications": {
                        "server_id": server_id
                    }
                }
            }
        )
        
        result = await db.collections["player_links"].update_one(
            {"_id": self._id},
            {
                "$push": {
                    "pending_verifications": verification_data
                },
                "$set": {
                    "updated_at": now
                }
            }
        )
        
        # Invalidate caches
        AsyncCache.invalidate(self.__class__.get_by_id, self.id)
        AsyncCache.invalidate(self.__class__.get_by_discord_id, self.discord_id)
        
        return token
    
    async def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify a token and add the player to the link
        
        Args:
            token: Verification token
            
        Returns:
            Dict or None: Verification data if successful
        """
        # Find matching token
        verification = None
        for v in self.pending_verifications:
            if v.get("token") == token:
                verification = v
                break
        
        if not verification:
            # Token not found
            return None
        
        # Check if token is expired
        expires_at = verification.get("expires_at")
        if expires_at and expires_at < datetime.utcnow():
            # Token expired
            return None
        
        # Extract server and player IDs
        server_id = verification.get("server_id")
        player_id = verification.get("player_id")
        
        if not server_id or not player_id:
            # Invalid verification data
            return None
        
        # Add player to link
        await self.add_player(server_id, player_id)
        
        # Remove verification
        db = await get_db()
        
        self.pending_verifications = [v for v in self.pending_verifications if v.get("token") != token]
        
        result = await db.collections["player_links"].update_one(
            {"_id": self._id},
            {
                "$pull": {
                    "pending_verifications": {
                        "token": token
                    }
                }
            }
        )
        
        # Invalidate caches
        AsyncCache.invalidate(self.__class__.get_by_id, self.id)
        AsyncCache.invalidate(self.__class__.get_by_discord_id, self.discord_id)
        
        return {
            "server_id": server_id,
            "player_id": player_id
        }
    
    async def delete(self) -> bool:
        """Delete the player link
        
        Returns:
            bool: True if successfully deleted
        """
        db = await get_db()
        
        # Store player IDs for cache invalidation
        player_servers = [(p.get("server_id"), p.get("player_id")) for p in self.players]
        
        # Delete player link
        result = await db.collections["player_links"].delete_one({"_id": self._id})
        
        # Invalidate caches
        AsyncCache.invalidate(self.__class__.get_by_id, self.id)
        AsyncCache.invalidate(self.__class__.get_by_discord_id, self.discord_id)
        
        for server_id, player_id in player_servers:
            if server_id and player_id:
                AsyncCache.invalidate(self.__class__.get_by_player_id, server_id, player_id)
        
        return result.deleted_count > 0