"""
Player Link model for the Tower of Temptation PvP Statistics Discord Bot.

This module provides:
1. PlayerLink class for connecting game IDs with Discord users
2. Methods for creating and retrieving player links
3. Link verification and management
"""
import logging
import secrets
import string
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, TypeVar

from utils.database import get_db
from utils.async_utils import AsyncCache

from models.player import Player

logger = logging.getLogger(__name__)

# Type variables
PL = TypeVar('PL', bound='PlayerLink')

# Constants
VERIFICATION_CODE_LENGTH = 8
VERIFICATION_EXPIRY_HOURS = 24

class PlayerLink:
    """PlayerLink class for connecting game IDs with Discord users"""
    
    def __init__(self, data: Dict[str, Any]):
        """Initialize a player link
        
        Args:
            data: Player link data from database
        """
        self.data = data
        self._id = data.get("_id")
        self.server_id = data.get("server_id")
        self.player_id = data.get("player_id")
        self.player_name = data.get("player_name")
        self.discord_id = data.get("discord_id")
        self.discord_name = data.get("discord_name")
        self.verification_code = data.get("verification_code")
        self.verification_expiry = data.get("verification_expiry")
        self.is_verified = data.get("is_verified", False)
        self.verified_at = data.get("verified_at")
        self.created_at = data.get("created_at")
        self.updated_at = data.get("updated_at")
    
    @property
    def id(self) -> str:
        """Get player link ID
        
        Returns:
            str: Player link ID
        """
        return str(self._id)
    
    @property
    def is_expired(self) -> bool:
        """Check if verification code is expired
        
        Returns:
            bool: True if expired
        """
        if not self.verification_code or not self.verification_expiry:
            return True
            
        return datetime.utcnow() > self.verification_expiry
    
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
    async def get_by_player(cls, server_id: str, player_id: str) -> Optional['PlayerLink']:
        """Get player link by player ID
        
        Args:
            server_id: Server ID
            player_id: Player ID
            
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
    @AsyncCache.cached(ttl=60)
    async def get_by_discord(cls, server_id: str, discord_id: int) -> Optional['PlayerLink']:
        """Get player link by Discord user ID
        
        Args:
            server_id: Server ID
            discord_id: Discord user ID
            
        Returns:
            PlayerLink or None: Player link if found
        """
        db = await get_db()
        link_data = await db.collections["player_links"].find_one({
            "server_id": server_id,
            "discord_id": discord_id
        })
        
        if not link_data:
            return None
        
        return cls(link_data)
    
    @classmethod
    @AsyncCache.cached(ttl=60)
    async def get_by_verification_code(cls, verification_code: str) -> Optional['PlayerLink']:
        """Get player link by verification code
        
        Args:
            verification_code: Verification code
            
        Returns:
            PlayerLink or None: Player link if found
        """
        db = await get_db()
        link_data = await db.collections["player_links"].find_one({
            "verification_code": verification_code,
            "is_verified": False,
            "verification_expiry": {"$gt": datetime.utcnow()}
        })
        
        if not link_data:
            return None
        
        return cls(link_data)
    
    @classmethod
    async def get_all_for_server(cls, server_id: str, verified_only: bool = False) -> List['PlayerLink']:
        """Get all player links for a server
        
        Args:
            server_id: Server ID
            verified_only: Only return verified links (default: False)
            
        Returns:
            List[PlayerLink]: List of player links
        """
        db = await get_db()
        
        query = {"server_id": server_id}
        if verified_only:
            query["is_verified"] = True
            
        links_data = await db.collections["player_links"].find(query).to_list(length=None)
        
        return [cls(link_data) for link_data in links_data]
    
    @classmethod
    async def create_link(
        cls,
        server_id: str,
        player_id: str,
        player_name: str,
        discord_id: int,
        discord_name: str
    ) -> 'PlayerLink':
        """Create a new player link
        
        Args:
            server_id: Server ID
            player_id: Player ID
            player_name: Player name
            discord_id: Discord user ID
            discord_name: Discord username
            
        Returns:
            PlayerLink: Created player link
            
        Raises:
            ValueError: If player or Discord user already has a link
        """
        # Check for existing links
        existing_player = await cls.get_by_player(server_id, player_id)
        if existing_player and existing_player.is_verified:
            raise ValueError(f"Player {player_name} is already linked to Discord user {existing_player.discord_name}")
            
        existing_discord = await cls.get_by_discord(server_id, discord_id)
        if existing_discord and existing_discord.is_verified:
            raise ValueError(f"Discord user {discord_name} is already linked to player {existing_discord.player_name}")
            
        # Generate verification code
        verification_code = cls._generate_verification_code()
        verification_expiry = datetime.utcnow() + timedelta(hours=VERIFICATION_EXPIRY_HOURS)
        
        db = await get_db()
        now = datetime.utcnow()
        
        # Create player link document
        link_data = {
            "server_id": server_id,
            "player_id": player_id,
            "player_name": player_name,
            "discord_id": discord_id,
            "discord_name": discord_name,
            "verification_code": verification_code,
            "verification_expiry": verification_expiry,
            "is_verified": False,
            "verified_at": None,
            "created_at": now,
            "updated_at": now
        }
        
        # If player already has a link, update it
        if existing_player:
            result = await db.collections["player_links"].update_one(
                {"_id": existing_player._id},
                {"$set": link_data}
            )
            link_data["_id"] = existing_player._id
            
            # Clear cache
            AsyncCache.invalidate(cls.get_by_id, existing_player.id)
            AsyncCache.invalidate(cls.get_by_player, server_id, player_id)
            if existing_player.discord_id:
                AsyncCache.invalidate(cls.get_by_discord, server_id, existing_player.discord_id)
            if existing_player.verification_code:
                AsyncCache.invalidate(cls.get_by_verification_code, existing_player.verification_code)
        
        # If Discord user already has a link, update it
        elif existing_discord:
            result = await db.collections["player_links"].update_one(
                {"_id": existing_discord._id},
                {"$set": link_data}
            )
            link_data["_id"] = existing_discord._id
            
            # Clear cache
            AsyncCache.invalidate(cls.get_by_id, existing_discord.id)
            if existing_discord.player_id:
                AsyncCache.invalidate(cls.get_by_player, server_id, existing_discord.player_id)
            AsyncCache.invalidate(cls.get_by_discord, server_id, discord_id)
            if existing_discord.verification_code:
                AsyncCache.invalidate(cls.get_by_verification_code, existing_discord.verification_code)
        
        # Otherwise create a new link
        else:
            result = await db.collections["player_links"].insert_one(link_data)
            link_data["_id"] = result.inserted_id
        
        return cls(link_data)
    
    async def verify(self, verification_code: str) -> bool:
        """Verify the player link
        
        Args:
            verification_code: Verification code
            
        Returns:
            bool: True if verification successful
            
        Raises:
            ValueError: If verification fails
        """
        # Check if already verified
        if self.is_verified:
            return True
            
        # Check if verification code matches
        if self.verification_code != verification_code:
            raise ValueError("Invalid verification code")
            
        # Check if verification code is expired
        if self.is_expired:
            raise ValueError("Verification code has expired")
            
        db = await get_db()
        now = datetime.utcnow()
        
        # Update player link
        update_data = {
            "is_verified": True,
            "verified_at": now,
            "updated_at": now
        }
        
        result = await db.collections["player_links"].update_one(
            {"_id": self._id},
            {"$set": update_data}
        )
        
        # Update local data
        self.is_verified = True
        self.verified_at = now
        self.updated_at = now
        
        # Get player and update stats
        player = await Player.get_by_player_id(self.server_id, self.player_id)
        if not player:
            # Create player if it doesn't exist
            player = await Player.create_or_update(
                self.server_id,
                self.player_id,
                self.player_name
            )
        
        # Clear cache
        AsyncCache.invalidate(self.__class__.get_by_id, self.id)
        AsyncCache.invalidate(self.__class__.get_by_player, self.server_id, self.player_id)
        AsyncCache.invalidate(self.__class__.get_by_discord, self.server_id, self.discord_id)
        AsyncCache.invalidate(self.__class__.get_by_verification_code, self.verification_code)
        
        return result.acknowledged
    
    async def refresh_verification(self) -> str:
        """Refresh verification code
        
        Returns:
            str: New verification code
            
        Raises:
            ValueError: If already verified
        """
        # Check if already verified
        if self.is_verified:
            raise ValueError("Cannot refresh verification for verified link")
            
        db = await get_db()
        now = datetime.utcnow()
        
        # Generate new verification code
        verification_code = self._generate_verification_code()
        verification_expiry = now + timedelta(hours=VERIFICATION_EXPIRY_HOURS)
        
        # Update player link
        update_data = {
            "verification_code": verification_code,
            "verification_expiry": verification_expiry,
            "updated_at": now
        }
        
        result = await db.collections["player_links"].update_one(
            {"_id": self._id},
            {"$set": update_data}
        )
        
        # Update local data
        self.verification_code = verification_code
        self.verification_expiry = verification_expiry
        self.updated_at = now
        
        # Clear cache
        AsyncCache.invalidate(self.__class__.get_by_id, self.id)
        AsyncCache.invalidate(self.__class__.get_by_player, self.server_id, self.player_id)
        AsyncCache.invalidate(self.__class__.get_by_discord, self.server_id, self.discord_id)
        if hasattr(self, "old_verification_code"):
            AsyncCache.invalidate(self.__class__.get_by_verification_code, self.old_verification_code)
        
        return verification_code
    
    async def update_player_name(self, player_name: str) -> bool:
        """Update player name
        
        Args:
            player_name: New player name
            
        Returns:
            bool: True if successful
        """
        db = await get_db()
        now = datetime.utcnow()
        
        # Update player link
        update_data = {
            "player_name": player_name,
            "updated_at": now
        }
        
        result = await db.collections["player_links"].update_one(
            {"_id": self._id},
            {"$set": update_data}
        )
        
        # Update local data
        self.player_name = player_name
        self.updated_at = now
        
        # Update player if exists
        player = await Player.get_by_player_id(self.server_id, self.player_id)
        if player:
            await player.update({"player_name": player_name})
        
        # Clear cache
        AsyncCache.invalidate(self.__class__.get_by_id, self.id)
        AsyncCache.invalidate(self.__class__.get_by_player, self.server_id, self.player_id)
        AsyncCache.invalidate(self.__class__.get_by_discord, self.server_id, self.discord_id)
        
        return result.acknowledged
    
    async def update_discord_name(self, discord_name: str) -> bool:
        """Update Discord username
        
        Args:
            discord_name: New Discord username
            
        Returns:
            bool: True if successful
        """
        db = await get_db()
        now = datetime.utcnow()
        
        # Update player link
        update_data = {
            "discord_name": discord_name,
            "updated_at": now
        }
        
        result = await db.collections["player_links"].update_one(
            {"_id": self._id},
            {"$set": update_data}
        )
        
        # Update local data
        self.discord_name = discord_name
        self.updated_at = now
        
        # Clear cache
        AsyncCache.invalidate(self.__class__.get_by_id, self.id)
        AsyncCache.invalidate(self.__class__.get_by_player, self.server_id, self.player_id)
        AsyncCache.invalidate(self.__class__.get_by_discord, self.server_id, self.discord_id)
        
        return result.acknowledged
    
    async def delete(self) -> bool:
        """Delete the player link
        
        Returns:
            bool: True if successful
        """
        db = await get_db()
        
        result = await db.collections["player_links"].delete_one({"_id": self._id})
        
        # Clear cache
        AsyncCache.invalidate(self.__class__.get_by_id, self.id)
        AsyncCache.invalidate(self.__class__.get_by_player, self.server_id, self.player_id)
        AsyncCache.invalidate(self.__class__.get_by_discord, self.server_id, self.discord_id)
        if self.verification_code:
            AsyncCache.invalidate(self.__class__.get_by_verification_code, self.verification_code)
        
        return result.deleted_count > 0
    
    @staticmethod
    def _generate_verification_code() -> str:
        """Generate a random verification code
        
        Returns:
            str: Verification code
        """
        # Use uppercase letters and digits
        alphabet = string.ascii_uppercase + string.digits
        # Remove similar looking characters
        alphabet = alphabet.replace('0', '').replace('O', '').replace('1', '').replace('I', '')
        
        # Generate random code
        return ''.join(secrets.choice(alphabet) for _ in range(VERIFICATION_CODE_LENGTH))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert player link to dictionary
        
        Returns:
            Dict: Player link data
        """
        return {
            "id": self.id,
            "server_id": self.server_id,
            "player_id": self.player_id,
            "player_name": self.player_name,
            "discord_id": self.discord_id,
            "discord_name": self.discord_name,
            "is_verified": self.is_verified,
            "is_expired": self.is_expired,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "verified_at": self.verified_at.isoformat() if self.verified_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }