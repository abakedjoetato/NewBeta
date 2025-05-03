"""
Faction model for the Tower of Temptation PvP Statistics Discord Bot.

This module provides:
1. Faction class with database operations
2. Faction member management
3. Permission management
4. Faction statistics tracking
"""
import asyncio
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set, Union, TypeVar, Tuple

import discord

from utils.database import get_db
from utils.async_utils import AsyncCache

logger = logging.getLogger(__name__)

# Type variables
F = TypeVar('F', bound='Faction')

# Constants for faction settings
MAX_FACTION_NAME_LENGTH = 32
MAX_FACTION_TAG_LENGTH = 10
MAX_FACTION_DESC_LENGTH = 1024
MAX_FACTION_MEMBERS = 100
DEFAULT_FACTION_COLOR = 0x7289DA

# Regex for valid faction names and tags
VALID_FACTION_NAME_REGEX = re.compile(r'^[a-zA-Z0-9 \-_\']+$')
VALID_FACTION_TAG_REGEX = re.compile(r'^[a-zA-Z0-9\-_]+$')

# Faction roles
FACTION_ROLES = ["member", "officer", "leader"]

class Faction:
    """Faction class for managing player factions"""
    
    def __init__(self, data: Dict[str, Any]):
        """Initialize a faction
        
        Args:
            data: Faction data from database
        """
        self.data = data
        self._id = data.get("_id")
        self.server_id = data.get("server_id")
        self.name = data.get("name")
        self.tag = data.get("tag")
        self.description = data.get("description")
        self.color = data.get("color", DEFAULT_FACTION_COLOR)
        self.icon_url = data.get("icon_url")
        self.banner_url = data.get("banner_url")
        self.leader_id = data.get("leader_id")
        self.created_at = data.get("created_at")
        self.updated_at = data.get("updated_at")
        self.member_count = data.get("member_count", 0)
        self.is_public = data.get("is_public", True)
        self.require_approval = data.get("require_approval", False)
        self.discord_role_id = data.get("discord_role_id")
        self.discord_guild_id = data.get("discord_guild_id")
        self.stats = data.get("stats", {})
    
    @property
    def id(self) -> str:
        """Get faction ID
        
        Returns:
            str: Faction ID
        """
        return str(self._id)
    
    @classmethod
    @AsyncCache.cached(ttl=60)
    async def get_by_id(cls, faction_id: str) -> Optional['Faction']:
        """Get faction by ID
        
        Args:
            faction_id: Faction ID
            
        Returns:
            Faction or None: Faction if found
        """
        db = await get_db()
        faction_data = await db.collections["factions"].find_one({"_id": faction_id})
        
        if not faction_data:
            return None
        
        return cls(faction_data)
    
    @classmethod
    @AsyncCache.cached(ttl=60)
    async def get_by_name(cls, server_id: str, name: str) -> Optional['Faction']:
        """Get faction by name
        
        Args:
            server_id: Server ID
            name: Faction name
            
        Returns:
            Faction or None: Faction if found
        """
        db = await get_db()
        faction_data = await db.collections["factions"].find_one({
            "server_id": server_id,
            "name": name
        })
        
        if not faction_data:
            # Try case-insensitive search (but not primary lookup for performance)
            faction_data = await db.collections["factions"].find_one({
                "server_id": server_id,
                "name": {"$regex": f"^{re.escape(name)}$", "$options": "i"}
            })
            
            if not faction_data:
                return None
        
        return cls(faction_data)
    
    @classmethod
    @AsyncCache.cached(ttl=60)
    async def get_by_tag(cls, server_id: str, tag: str) -> Optional['Faction']:
        """Get faction by tag
        
        Args:
            server_id: Server ID
            tag: Faction tag
            
        Returns:
            Faction or None: Faction if found
        """
        db = await get_db()
        faction_data = await db.collections["factions"].find_one({
            "server_id": server_id,
            "tag": tag
        })
        
        if not faction_data:
            # Try case-insensitive search (but not primary lookup for performance)
            faction_data = await db.collections["factions"].find_one({
                "server_id": server_id,
                "tag": {"$regex": f"^{re.escape(tag)}$", "$options": "i"}
            })
            
            if not faction_data:
                return None
        
        return cls(faction_data)
    
    @classmethod
    @AsyncCache.cached(ttl=60)
    async def get_all(cls, server_id: str) -> List['Faction']:
        """Get all factions on a server
        
        Args:
            server_id: Server ID
            
        Returns:
            List[Faction]: List of factions
        """
        db = await get_db()
        cursor = db.collections["factions"].find({"server_id": server_id})
        faction_data = await cursor.to_list(length=None)
        
        return [cls(data) for data in faction_data]
    
    @classmethod
    @AsyncCache.cached(ttl=60)
    async def get_for_player(cls, server_id: str, player_id: str) -> List['Faction']:
        """Get factions a player is a member of
        
        Args:
            server_id: Server ID
            player_id: Player ID
            
        Returns:
            List[Faction]: List of factions
        """
        db = await get_db()
        
        # Find faction members for this player
        cursor = db.collections["faction_members"].find({
            "player_id": player_id
        })
        faction_members = await cursor.to_list(length=None)
        
        # Extract faction IDs
        faction_ids = [member["faction_id"] for member in faction_members]
        
        if not faction_ids:
            return []
        
        # Find factions by ID and server ID
        cursor = db.collections["factions"].find({
            "_id": {"$in": faction_ids},
            "server_id": server_id
        })
        faction_data = await cursor.to_list(length=None)
        
        return [cls(data) for data in faction_data]
    
    @classmethod
    @AsyncCache.cached(ttl=60)
    async def get_top_factions(cls, server_id: str, limit: int = 10) -> List['Faction']:
        """Get top factions by member count
        
        Args:
            server_id: Server ID
            limit: Maximum number of factions to return
            
        Returns:
            List[Faction]: List of top factions
        """
        db = await get_db()
        cursor = db.collections["factions"].find({
            "server_id": server_id
        }).sort("member_count", -1).limit(limit)
        
        faction_data = await cursor.to_list(length=None)
        return [cls(data) for data in faction_data]
    
    @classmethod
    async def create(
        cls,
        server_id: str,
        name: str,
        tag: str,
        leader_id: str,
        description: Optional[str] = None,
        color: int = DEFAULT_FACTION_COLOR,
        icon_url: Optional[str] = None,
        banner_url: Optional[str] = None,
        discord_role_id: Optional[int] = None,
        discord_guild_id: Optional[int] = None,
        is_public: bool = True,
        require_approval: bool = False
    ) -> 'Faction':
        """Create a new faction
        
        Args:
            server_id: Server ID
            name: Faction name
            tag: Faction tag
            leader_id: Leader player ID
            description: Faction description (optional)
            color: Faction color (optional)
            icon_url: Faction icon URL (optional)
            banner_url: Faction banner URL (optional)
            discord_role_id: Discord role ID (optional)
            discord_guild_id: Discord guild ID (optional)
            is_public: Whether faction is public (optional)
            require_approval: Whether to require approval for joins (optional)
            
        Returns:
            Faction: Created faction
            
        Raises:
            ValueError: If faction name or tag already exists
        """
        # Validate faction name and tag
        if not VALID_FACTION_NAME_REGEX.match(name):
            raise ValueError("Faction name can only contain letters, numbers, spaces, hyphens, underscores, and apostrophes")
        
        if not VALID_FACTION_TAG_REGEX.match(tag):
            raise ValueError("Faction tag can only contain letters, numbers, hyphens, and underscores")
        
        if len(name) > MAX_FACTION_NAME_LENGTH:
            raise ValueError(f"Faction name cannot exceed {MAX_FACTION_NAME_LENGTH} characters")
        
        if len(tag) > MAX_FACTION_TAG_LENGTH:
            raise ValueError(f"Faction tag cannot exceed {MAX_FACTION_TAG_LENGTH} characters")
        
        if description and len(description) > MAX_FACTION_DESC_LENGTH:
            raise ValueError(f"Faction description cannot exceed {MAX_FACTION_DESC_LENGTH} characters")
        
        # Check if faction name or tag already exists
        db = await get_db()
        existing_faction = await db.collections["factions"].find_one({
            "server_id": server_id,
            "$or": [
                {"name": name},
                {"tag": tag}
            ]
        })
        
        if existing_faction:
            if existing_faction["name"] == name:
                raise ValueError(f"Faction with name '{name}' already exists")
            else:
                raise ValueError(f"Faction with tag '{tag}' already exists")
        
        # Create faction
        now = datetime.utcnow()
        faction_data = {
            "server_id": server_id,
            "name": name,
            "tag": tag,
            "description": description,
            "color": color,
            "icon_url": icon_url,
            "banner_url": banner_url,
            "leader_id": leader_id,
            "created_at": now,
            "updated_at": now,
            "member_count": 1,  # Leader is the first member
            "is_public": is_public,
            "require_approval": require_approval,
            "discord_role_id": discord_role_id,
            "discord_guild_id": discord_guild_id,
            "stats": {
                "kills": 0,
                "deaths": 0,
                "assists": 0,
                "revives": 0
            }
        }
        
        result = await db.collections["factions"].insert_one(faction_data)
        faction_data["_id"] = result.inserted_id
        
        # Add leader as first member
        await db.collections["faction_members"].insert_one({
            "faction_id": result.inserted_id,
            "player_id": leader_id,
            "server_id": server_id,
            "role": "leader",
            "joined_at": now
        })
        
        # Invalidate caches
        AsyncCache.invalidate_all(cls.get_all)
        AsyncCache.invalidate_all(cls.get_for_player)
        AsyncCache.invalidate_all(cls.get_top_factions)
        
        return cls(faction_data)
    
    async def update(self, update_data: Dict[str, Any]) -> 'Faction':
        """Update faction data
        
        Args:
            update_data: Data to update
            
        Returns:
            Faction: Updated faction
        """
        # Validate updates
        if "name" in update_data:
            name = update_data["name"]
            if not VALID_FACTION_NAME_REGEX.match(name):
                raise ValueError("Faction name can only contain letters, numbers, spaces, hyphens, underscores, and apostrophes")
            
            if len(name) > MAX_FACTION_NAME_LENGTH:
                raise ValueError(f"Faction name cannot exceed {MAX_FACTION_NAME_LENGTH} characters")
            
            # Check if name already exists
            db = await get_db()
            existing_faction = await db.collections["factions"].find_one({
                "server_id": self.server_id,
                "name": name,
                "_id": {"$ne": self._id}
            })
            
            if existing_faction:
                raise ValueError(f"Faction with name '{name}' already exists")
        
        if "tag" in update_data:
            tag = update_data["tag"]
            if not VALID_FACTION_TAG_REGEX.match(tag):
                raise ValueError("Faction tag can only contain letters, numbers, hyphens, and underscores")
            
            if len(tag) > MAX_FACTION_TAG_LENGTH:
                raise ValueError(f"Faction tag cannot exceed {MAX_FACTION_TAG_LENGTH} characters")
            
            # Check if tag already exists
            db = await get_db()
            existing_faction = await db.collections["factions"].find_one({
                "server_id": self.server_id,
                "tag": tag,
                "_id": {"$ne": self._id}
            })
            
            if existing_faction:
                raise ValueError(f"Faction with tag '{tag}' already exists")
        
        if "description" in update_data and update_data["description"]:
            if len(update_data["description"]) > MAX_FACTION_DESC_LENGTH:
                raise ValueError(f"Faction description cannot exceed {MAX_FACTION_DESC_LENGTH} characters")
        
        # Update faction in database
        db = await get_db()
        update_data["updated_at"] = datetime.utcnow()
        
        result = await db.collections["factions"].find_one_and_update(
            {"_id": self._id},
            {"$set": update_data},
            return_document=True
        )
        
        # Invalidate caches
        AsyncCache.invalidate(self.__class__.get_by_id, self.id)
        if "name" in update_data:
            AsyncCache.invalidate(self.__class__.get_by_name, self.server_id, self.name)
            AsyncCache.invalidate(self.__class__.get_by_name, self.server_id, update_data["name"])
        if "tag" in update_data:
            AsyncCache.invalidate(self.__class__.get_by_tag, self.server_id, self.tag)
            AsyncCache.invalidate(self.__class__.get_by_tag, self.server_id, update_data["tag"])
        AsyncCache.invalidate_all(self.__class__.get_all)
        AsyncCache.invalidate_all(self.__class__.get_for_player)
        AsyncCache.invalidate_all(self.__class__.get_top_factions)
        
        # Update local state
        self.data = result
        for key, value in update_data.items():
            setattr(self, key, value)
        
        return self
    
    async def delete(self) -> bool:
        """Delete faction
        
        Returns:
            bool: True if successfully deleted
        """
        db = await get_db()
        
        # Delete faction members
        await db.collections["faction_members"].delete_many({
            "faction_id": self._id
        })
        
        # Delete faction
        result = await db.collections["factions"].delete_one({
            "_id": self._id
        })
        
        # Invalidate caches
        AsyncCache.invalidate(self.__class__.get_by_id, self.id)
        AsyncCache.invalidate(self.__class__.get_by_name, self.server_id, self.name)
        AsyncCache.invalidate(self.__class__.get_by_tag, self.server_id, self.tag)
        AsyncCache.invalidate_all(self.__class__.get_all)
        AsyncCache.invalidate_all(self.__class__.get_for_player)
        AsyncCache.invalidate_all(self.__class__.get_top_factions)
        
        return result.deleted_count > 0
    
    @AsyncCache.cached(ttl=60)
    async def get_members(self) -> List[Dict[str, Any]]:
        """Get faction members
        
        Returns:
            List[Dict]: List of faction member data
        """
        db = await get_db()
        
        # Get faction members
        cursor = db.collections["faction_members"].find({
            "faction_id": self._id
        })
        faction_members = await cursor.to_list(length=None)
        
        # Get player details for members
        members = []
        for member in faction_members:
            player_id = member["player_id"]
            player = await db.collections["players"].find_one({"_id": player_id})
            
            if player:
                members.append({
                    "player_id": player_id,
                    "player_name": player.get("name", "Unknown"),
                    "server_id": member["server_id"],
                    "role": member["role"],
                    "joined_at": member["joined_at"]
                })
        
        return members
    
    async def add_member(
        self,
        player_id: str,
        role: str = "member"
    ) -> bool:
        """Add member to faction
        
        Args:
            player_id: Player ID
            role: Member role (default: member)
            
        Returns:
            bool: True if successfully added
            
        Raises:
            ValueError: If faction is full or player is already in faction
        """
        # Check if faction is full
        if self.member_count >= MAX_FACTION_MEMBERS:
            raise ValueError(f"Faction is full (maximum {MAX_FACTION_MEMBERS} members)")
        
        # Validate role
        if role not in FACTION_ROLES:
            raise ValueError(f"Invalid role '{role}'. Must be one of: {', '.join(FACTION_ROLES)}")
        
        db = await get_db()
        
        # Check if player is already in a faction on this server
        player_factions = await self.__class__.get_for_player(self.server_id, player_id)
        if player_factions:
            # Check if player is already in this faction
            if any(f.id == self.id for f in player_factions):
                raise ValueError("Player is already a member of this faction")
            
            # Check if player is in another faction
            raise ValueError("Player is already a member of another faction")
        
        # Add member
        now = datetime.utcnow()
        result = await db.collections["faction_members"].insert_one({
            "faction_id": self._id,
            "player_id": player_id,
            "server_id": self.server_id,
            "role": role,
            "joined_at": now
        })
        
        # Update member count
        await db.collections["factions"].update_one(
            {"_id": self._id},
            {
                "$inc": {"member_count": 1},
                "$set": {"updated_at": now}
            }
        )
        
        # Update local state
        self.member_count += 1
        self.updated_at = now
        
        # Invalidate caches
        AsyncCache.invalidate(self.__class__.get_by_id, self.id)
        AsyncCache.invalidate_all(self.__class__.get_for_player)
        AsyncCache.invalidate(self.get_members)
        
        return result.acknowledged
    
    async def remove_member(self, player_id: str) -> bool:
        """Remove member from faction
        
        Args:
            player_id: Player ID
            
        Returns:
            bool: True if successfully removed
            
        Raises:
            ValueError: If player is the leader or not in faction
        """
        # Check if player is the leader
        if player_id == self.leader_id:
            raise ValueError("Cannot remove faction leader. Transfer leadership first.")
        
        db = await get_db()
        
        # Check if player is in faction
        member = await db.collections["faction_members"].find_one({
            "faction_id": self._id,
            "player_id": player_id
        })
        
        if not member:
            raise ValueError("Player is not a member of this faction")
        
        # Remove member
        result = await db.collections["faction_members"].delete_one({
            "faction_id": self._id,
            "player_id": player_id
        })
        
        if result.deleted_count > 0:
            # Update member count
            now = datetime.utcnow()
            await db.collections["factions"].update_one(
                {"_id": self._id},
                {
                    "$inc": {"member_count": -1},
                    "$set": {"updated_at": now}
                }
            )
            
            # Update local state
            self.member_count = max(0, self.member_count - 1)
            self.updated_at = now
            
            # Invalidate caches
            AsyncCache.invalidate(self.__class__.get_by_id, self.id)
            AsyncCache.invalidate_all(self.__class__.get_for_player)
            AsyncCache.invalidate(self.get_members)
            
            return True
        
        return False
    
    async def update_member_role(self, player_id: str, new_role: str) -> bool:
        """Update member role
        
        Args:
            player_id: Player ID
            new_role: New role
            
        Returns:
            bool: True if successfully updated
            
        Raises:
            ValueError: If player is not in faction or role is invalid
        """
        # Validate role
        if new_role not in FACTION_ROLES:
            raise ValueError(f"Invalid role '{new_role}'. Must be one of: {', '.join(FACTION_ROLES)}")
        
        # Handle leader role specially
        if new_role == "leader":
            return await self.transfer_leadership(player_id)
        
        db = await get_db()
        
        # Check if player is in faction
        member = await db.collections["faction_members"].find_one({
            "faction_id": self._id,
            "player_id": player_id
        })
        
        if not member:
            raise ValueError("Player is not a member of this faction")
        
        # Don't allow changing leader's role this way
        if member["player_id"] == self.leader_id:
            raise ValueError("Cannot change leader's role. Transfer leadership first.")
        
        # Update role
        result = await db.collections["faction_members"].update_one(
            {
                "faction_id": self._id,
                "player_id": player_id
            },
            {
                "$set": {
                    "role": new_role
                }
            }
        )
        
        # Invalidate caches
        AsyncCache.invalidate(self.get_members)
        
        return result.modified_count > 0
    
    async def transfer_leadership(self, new_leader_id: str) -> bool:
        """Transfer faction leadership
        
        Args:
            new_leader_id: New leader player ID
            
        Returns:
            bool: True if successfully transferred
            
        Raises:
            ValueError: If new leader is not in faction
        """
        db = await get_db()
        
        # Check if new leader is in faction
        new_leader_member = await db.collections["faction_members"].find_one({
            "faction_id": self._id,
            "player_id": new_leader_id
        })
        
        if not new_leader_member:
            raise ValueError("New leader is not a member of this faction")
        
        # Get current leader
        old_leader_id = self.leader_id
        
        # Update faction leader
        now = datetime.utcnow()
        faction_result = await db.collections["factions"].update_one(
            {"_id": self._id},
            {
                "$set": {
                    "leader_id": new_leader_id,
                    "updated_at": now
                }
            }
        )
        
        # Update member roles
        await db.collections["faction_members"].update_one(
            {
                "faction_id": self._id,
                "player_id": new_leader_id
            },
            {
                "$set": {"role": "leader"}
            }
        )
        
        await db.collections["faction_members"].update_one(
            {
                "faction_id": self._id,
                "player_id": old_leader_id
            },
            {
                "$set": {"role": "officer"}
            }
        )
        
        # Update local state
        self.leader_id = new_leader_id
        self.updated_at = now
        
        # Invalidate caches
        AsyncCache.invalidate(self.__class__.get_by_id, self.id)
        AsyncCache.invalidate(self.get_members)
        
        return faction_result.modified_count > 0
    
    async def update_stats(self, stats_update: Dict[str, int]) -> bool:
        """Update faction statistics
        
        Args:
            stats_update: Statistics to update
            
        Returns:
            bool: True if successfully updated
        """
        db = await get_db()
        
        # Create update operation
        update_op = {}
        for stat, value in stats_update.items():
            if value != 0:  # Only update non-zero values
                update_op[f"stats.{stat}"] = value
        
        if not update_op:
            return True  # No updates needed
        
        # Update stats
        now = datetime.utcnow()
        result = await db.collections["factions"].update_one(
            {"_id": self._id},
            {
                "$inc": update_op,
                "$set": {"updated_at": now}
            }
        )
        
        # Update local state
        for stat, value in stats_update.items():
            if stat in self.stats:
                self.stats[stat] += value
            else:
                self.stats[stat] = value
        
        self.updated_at = now
        
        # Invalidate caches
        AsyncCache.invalidate(self.__class__.get_by_id, self.id)
        
        return result.modified_count > 0
    
    def get_discord_embed(self, guild: Optional[discord.Guild] = None) -> discord.Embed:
        """Get Discord embed for faction
        
        Args:
            guild: Discord guild (optional)
            
        Returns:
            discord.Embed: Faction embed
        """
        embed = discord.Embed(
            title=f"{self.name} [{self.tag}]",
            description=self.description,
            color=self.color
        )
        
        # Set thumbnail if available
        if self.icon_url:
            embed.set_thumbnail(url=self.icon_url)
        
        # Add member count
        embed.add_field(name="Members", value=str(self.member_count), inline=True)
        
        # Add stats
        kills = self.stats.get("kills", 0)
        deaths = self.stats.get("deaths", 0)
        kd_ratio = kills / max(deaths, 1)
        
        embed.add_field(name="Kills", value=str(kills), inline=True)
        embed.add_field(name="Deaths", value=str(deaths), inline=True)
        embed.add_field(name="K/D Ratio", value=f"{kd_ratio:.2f}", inline=True)
        
        # Add secondary stats if available
        if "assists" in self.stats and self.stats["assists"] > 0:
            embed.add_field(name="Assists", value=str(self.stats["assists"]), inline=True)
        if "revives" in self.stats and self.stats["revives"] > 0:
            embed.add_field(name="Revives", value=str(self.stats["revives"]), inline=True)
        
        # Add creation date
        if self.created_at:
            embed.set_footer(text=f"Created")
            embed.timestamp = self.created_at
        
        return embed
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert faction to dictionary
        
        Returns:
            Dict: Faction data
        """
        return {
            "id": self.id,
            "server_id": self.server_id,
            "name": self.name,
            "tag": self.tag,
            "description": self.description,
            "color": self.color,
            "icon_url": self.icon_url,
            "banner_url": self.banner_url,
            "leader_id": self.leader_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "member_count": self.member_count,
            "is_public": self.is_public,
            "require_approval": self.require_approval,
            "discord_role_id": self.discord_role_id,
            "discord_guild_id": self.discord_guild_id,
            "stats": self.stats
        }