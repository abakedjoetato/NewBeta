"""
Bounty model for the Tower of Temptation PvP Statistics Bot.

Represents a bounty that can be placed on a player, with automatic expiration
after a configurable amount of time.
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Union
import uuid

from utils.database import get_db
from models.player import Player
from models.economy import Economy

logger = logging.getLogger(__name__)

class Bounty:
    """
    Represents a bounty on a player.
    
    Attributes:
        id (str): Unique identifier for the bounty
        guild_id (str): Discord guild ID
        server_id (str): Game server ID
        target_id (str): Player ID of the bounty target
        target_name (str): Player name of the bounty target
        placed_by (str): Discord ID of the user who placed the bounty
        placed_by_name (str): Discord name of the user who placed the bounty
        placed_at (datetime): When the bounty was placed
        reason (str): Reason for the bounty
        reward (int): Reward amount for completing the bounty
        expires_at (datetime): When the bounty expires
        status (str): Current status (active, claimed, expired)
        claimed_by (str, optional): Discord ID of user who claimed the bounty
        claimed_by_name (str, optional): Discord name of user who claimed the bounty
        claimed_at (datetime, optional): When the bounty was claimed
        source (str): Source of the bounty (player, system, auto)
    """
    
    # Status constants
    STATUS_ACTIVE = "active"
    STATUS_CLAIMED = "claimed"
    STATUS_EXPIRED = "expired"
    
    # Source constants
    SOURCE_PLAYER = "player"     # Manually placed by a player
    SOURCE_SYSTEM = "system"     # Placed by a system/admin action
    SOURCE_AUTO = "auto"         # Automatically generated (e.g., for killstreaks)
    
    def __init__(self, data: Dict[str, Any]):
        """
        Initialize a Bounty object from database data.
        
        Args:
            data: Dictionary containing bounty data from database
        """
        self.id = str(data.get("_id", uuid.uuid4()))
        self.guild_id = str(data.get("guild_id", ""))
        self.server_id = str(data.get("server_id", ""))
        self.target_id = str(data.get("target_id", ""))
        self.target_name = str(data.get("target_name", ""))
        self.placed_by = str(data.get("placed_by", ""))
        self.placed_by_name = str(data.get("placed_by_name", ""))
        
        # Handle datetime fields
        self.placed_at = data.get("placed_at", datetime.utcnow())
        if isinstance(self.placed_at, str):
            try:
                self.placed_at = datetime.fromisoformat(self.placed_at.replace("Z", "+00:00"))
            except ValueError:
                self.placed_at = datetime.utcnow()
        
        self.reason = str(data.get("reason", ""))
        self.reward = int(data.get("reward", 0))
        
        # Expiration handling
        self.expires_at = data.get("expires_at")
        if isinstance(self.expires_at, str):
            try:
                self.expires_at = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
            except ValueError:
                # Default to 1 hour from placed_at
                self.expires_at = self.placed_at + timedelta(hours=1)
        
        self.status = str(data.get("status", self.STATUS_ACTIVE))
        
        # Claiming info (optional)
        self.claimed_by = data.get("claimed_by")
        self.claimed_by_name = data.get("claimed_by_name")
        
        self.claimed_at = data.get("claimed_at")
        if self.claimed_at and isinstance(self.claimed_at, str):
            try:
                self.claimed_at = datetime.fromisoformat(self.claimed_at.replace("Z", "+00:00"))
            except ValueError:
                self.claimed_at = datetime.utcnow()
        
        # Source of the bounty
        self.source = str(data.get("source", self.SOURCE_PLAYER))
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the Bounty object to a dictionary for database storage.
        
        Returns:
            Dictionary representation of the bounty
        """
        result = {
            "guild_id": self.guild_id,
            "server_id": self.server_id,
            "target_id": self.target_id,
            "target_name": self.target_name,
            "placed_by": self.placed_by,
            "placed_by_name": self.placed_by_name,
            "placed_at": self.placed_at,
            "reason": self.reason,
            "reward": self.reward,
            "expires_at": self.expires_at,
            "status": self.status,
            "claimed_by": self.claimed_by,
            "claimed_by_name": self.claimed_by_name,
            "claimed_at": self.claimed_at,
            "source": self.source
        }
        
        # Don't override the ID if it exists
        if hasattr(self, "id") and self.id != str(uuid.uuid4()):
            result["_id"] = self.id
            
        return result
    
    @classmethod
    async def create(cls, guild_id: str, server_id: str, target_id: str, target_name: str,
                 placed_by: str, placed_by_name: str, reason: str, reward: int,
                 source: str = SOURCE_PLAYER, lifespan_hours: float = 1.0) -> "Bounty":
        """
        Create a new bounty in the database.
        
        Args:
            guild_id: Discord guild ID
            server_id: Game server ID
            target_id: Player ID of the bounty target
            target_name: Player name of the bounty target
            placed_by: Discord ID of the user who placed the bounty
            placed_by_name: Discord name of the user who placed the bounty
            reason: Reason for the bounty
            reward: Reward amount for completing the bounty
            source: Source of the bounty (player, system, auto)
            lifespan_hours: How long the bounty should last before expiring (in hours)
            
        Returns:
            Newly created Bounty object
        """
        now = datetime.utcnow()
        expires_at = now + timedelta(hours=lifespan_hours)
        
        bounty_data = {
            "_id": str(uuid.uuid4()),
            "guild_id": str(guild_id),
            "server_id": str(server_id),
            "target_id": str(target_id),
            "target_name": str(target_name),
            "placed_by": str(placed_by),
            "placed_by_name": str(placed_by_name),
            "placed_at": now,
            "reason": str(reason),
            "reward": int(reward),
            "expires_at": expires_at,
            "status": cls.STATUS_ACTIVE,
            "claimed_by": None,
            "claimed_by_name": None,
            "claimed_at": None,
            "source": source
        }
        
        db = await get_db()
        
        # Insert the bounty into the database
        await db.collections["bounties"].insert_one(bounty_data)
        
        return cls(bounty_data)
    
    @classmethod
    async def get_by_id(cls, bounty_id: str) -> Optional["Bounty"]:
        """
        Get a bounty by its ID.
        
        Args:
            bounty_id: The ID of the bounty to retrieve
            
        Returns:
            Bounty object if found, None otherwise
        """
        db = await get_db()
        bounty_data = await db.collections["bounties"].find_one({"_id": str(bounty_id)})
        
        if bounty_data:
            return cls(bounty_data)
        
        return None
    
    @classmethod
    async def get_active_bounties(cls, guild_id: str, server_id: str) -> List["Bounty"]:
        """
        Get all active bounties for a server.
        
        Args:
            guild_id: Discord guild ID
            server_id: Game server ID
            
        Returns:
            List of active Bounty objects
        """
        db = await get_db()
        cursor = db.collections["bounties"].find({
            "guild_id": str(guild_id),
            "server_id": str(server_id),
            "status": cls.STATUS_ACTIVE,
            "expires_at": {"$gt": datetime.utcnow()}
        })
        
        bounties = []
        async for bounty_data in cursor:
            bounties.append(cls(bounty_data))
        
        return bounties
    
    @classmethod
    async def get_active_bounties_for_target(cls, guild_id: str, server_id: str, 
                                         target_id: str) -> List["Bounty"]:
        """
        Get all active bounties for a specific target.
        
        Args:
            guild_id: Discord guild ID
            server_id: Game server ID
            target_id: Player ID of the bounty target
            
        Returns:
            List of active Bounty objects for the target
        """
        db = await get_db()
        cursor = db.collections["bounties"].find({
            "guild_id": str(guild_id),
            "server_id": str(server_id),
            "target_id": str(target_id),
            "status": cls.STATUS_ACTIVE,
            "expires_at": {"$gt": datetime.utcnow()}
        })
        
        bounties = []
        async for bounty_data in cursor:
            bounties.append(cls(bounty_data))
        
        return bounties
    
    @classmethod
    async def get_bounties_placed_by(cls, guild_id: str, server_id: str, 
                                  placed_by: str) -> List["Bounty"]:
        """
        Get all bounties placed by a user.
        
        Args:
            guild_id: Discord guild ID
            server_id: Game server ID
            placed_by: Discord ID of the user who placed the bounties
            
        Returns:
            List of Bounty objects placed by the user
        """
        db = await get_db()
        cursor = db.collections["bounties"].find({
            "guild_id": str(guild_id),
            "server_id": str(server_id),
            "placed_by": str(placed_by)
        }).sort("placed_at", -1)  # Most recent first
        
        bounties = []
        async for bounty_data in cursor:
            bounties.append(cls(bounty_data))
        
        return bounties
    
    @classmethod
    async def get_bounties_claimed_by(cls, guild_id: str, server_id: str, 
                                   claimed_by: str) -> List["Bounty"]:
        """
        Get all bounties claimed by a user.
        
        Args:
            guild_id: Discord guild ID
            server_id: Game server ID
            claimed_by: Discord ID of the user who claimed the bounties
            
        Returns:
            List of Bounty objects claimed by the user
        """
        db = await get_db()
        cursor = db.collections["bounties"].find({
            "guild_id": str(guild_id),
            "server_id": str(server_id),
            "claimed_by": str(claimed_by),
            "status": cls.STATUS_CLAIMED
        }).sort("claimed_at", -1)  # Most recent first
        
        bounties = []
        async for bounty_data in cursor:
            bounties.append(cls(bounty_data))
        
        return bounties
    
    @classmethod
    async def expire_old_bounties(cls) -> int:
        """
        Find and expire all bounties that have passed their expiration time.
        
        Returns:
            Number of bounties expired
        """
        db = await get_db()
        now = datetime.utcnow()
        
        result = await db.collections["bounties"].update_many(
            {
                "status": cls.STATUS_ACTIVE,
                "expires_at": {"$lt": now}
            },
            {"$set": {"status": cls.STATUS_EXPIRED}}
        )
        
        return result.modified_count
    
    @classmethod
    async def check_bounties_for_kill(cls, guild_id: str, server_id: str, 
                                  killer_id: str, killer_name: str, 
                                  victim_id: str) -> List["Bounty"]:
        """
        Check if a kill satisfies any active bounties.
        
        Args:
            guild_id: Discord guild ID
            server_id: Game server ID
            killer_id: Player ID of the killer
            killer_name: Player name of the killer
            victim_id: Player ID of the victim
            
        Returns:
            List of Bounty objects that were claimed
        """
        # First check if the killer is linked - only linked players can claim bounties
        is_linked = await cls.is_linked_player(None, server_id, killer_id)
        if not is_linked:
            return []
        
        # Get active bounties for the victim
        bounties = await cls.get_active_bounties_for_target(guild_id, server_id, victim_id)
        if not bounties:
            return []
        
        # Claim all matching bounties
        claimed_bounties = []
        for bounty in bounties:
            # Don't allow claiming your own bounties
            if str(bounty.placed_by) == str(killer_id):
                continue
                
            # Claim the bounty
            claimed = await bounty.claim(killer_id, killer_name)
            if claimed:
                claimed_bounties.append(bounty)
                
                # Award the bounty to the killer
                try:
                    db = await get_db()
                    killer_economy = await Economy.get_by_player(db, killer_id, server_id)
                    if killer_economy:
                        await killer_economy.add_currency(bounty.reward, "bounty_claimed", {
                            "bounty_id": str(bounty.id),
                            "target_id": victim_id,
                            "target_name": bounty.target_name
                        })
                except Exception as e:
                    logger.error(f"Error awarding bounty reward to {killer_id}: {e}")
        
        return claimed_bounties
    
    @classmethod
    async def is_linked_player(cls, discord_id: Optional[str], server_id: str, player_id: str) -> bool:
        """
        Check if a player is linked to a Discord account.
        
        Args:
            discord_id: Discord ID to check (if None, will check if any link exists)
            server_id: Game server ID
            player_id: Player ID
            
        Returns:
            True if the player is linked, False otherwise
        """
        try:
            db = await get_db()
            
            # Build the query
            query = {
                "server_id": server_id,
                "player_id": player_id,
                "verified": True
            }
            
            # If a specific Discord ID is provided, check against it
            if discord_id:
                query["discord_id"] = str(discord_id)
            
            # Check if a link exists
            link = await db.collections["player_links"].find_one(query)
            return link is not None
        except Exception as e:
            logger.error(f"Error checking player link: {e}")
            return False
    
    @classmethod
    async def get_player_stats_for_bounty(cls, guild_id: str, server_id: str, 
                                      minutes: int = 10, kill_threshold: int = 5,
                                      repeat_threshold: int = 3) -> List[Dict[str, Any]]:
        """
        Get player stats to identify potential auto-bounty targets.
        
        Args:
            guild_id: Discord guild ID
            server_id: Game server ID
            minutes: Time window to check (in minutes)
            kill_threshold: Minimum kills to trigger a killstreak bounty
            repeat_threshold: Minimum kills on the same victim to trigger a repeat bounty
            
        Returns:
            List of dictionaries with potential bounty targets
        """
        db = await get_db()
        now = datetime.utcnow()
        time_window = now - timedelta(minutes=minutes)
        
        # Get all kills in the time window
        cursor = db.collections["kills"].find({
            "guild_id": str(guild_id),
            "server_id": str(server_id),
            "timestamp": {"$gt": time_window}
        })
        
        # Collect kill data
        all_kills = []
        player_kill_counts = {}  # {killer_id: count}
        victim_counts = {}       # {killer_id: {victim_id: count}}
        
        async for kill in cursor:
            all_kills.append(kill)
            
            killer_id = str(kill.get("killer_id", ""))
            victim_id = str(kill.get("victim_id", ""))
            
            if not killer_id or not victim_id or killer_id == victim_id:
                continue
            
            # Increment total kill count for this killer
            player_kill_counts[killer_id] = player_kill_counts.get(killer_id, 0) + 1
            
            # Initialize victim count for this killer if needed
            if killer_id not in victim_counts:
                victim_counts[killer_id] = {}
            
            # Increment victim-specific kill count
            victim_counts[killer_id][victim_id] = victim_counts[killer_id].get(victim_id, 0) + 1
        
        # Generate potential bounty targets
        potential_bounties = []
        
        # Check for killstreaks
        for killer_id, kill_count in player_kill_counts.items():
            if kill_count >= kill_threshold:
                # Get player info
                player = await Player.get_by_player_id(db, killer_id, server_id)
                if not player:
                    continue
                
                potential_bounties.append({
                    "player_id": killer_id,
                    "player_name": player.player_name,
                    "type": "killstreak",
                    "kill_count": kill_count,
                    "reason": f"On a {kill_count}-kill streak in the last {minutes} minutes!"
                })
        
        # Check for repeated kills on the same victim
        for killer_id, victims in victim_counts.items():
            for victim_id, victim_kill_count in victims.items():
                if victim_kill_count >= repeat_threshold:
                    # Get player info
                    killer = await Player.get_by_player_id(db, killer_id, server_id)
                    victim = await Player.get_by_player_id(db, victim_id, server_id)
                    
                    if not killer or not victim:
                        continue
                    
                    potential_bounties.append({
                        "player_id": killer_id,
                        "player_name": killer.player_name,
                        "type": "repeat",
                        "kill_count": victim_kill_count,
                        "victim_id": victim_id,
                        "victim_name": victim.player_name,
                        "reason": f"Killed {victim.player_name} {victim_kill_count} times in the last {minutes} minutes!"
                    })
        
        return potential_bounties
    
    async def save(self) -> bool:
        """
        Save the current state of the bounty to the database.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            db = await get_db()
            result = await db.collections["bounties"].update_one(
                {"_id": str(self.id)},
                {"$set": self.to_dict()}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error saving bounty: {e}")
            return False
    
    async def claim(self, claimed_by: str, claimed_by_name: str) -> bool:
        """
        Claim this bounty.
        
        Args:
            claimed_by: Discord ID of the user claiming the bounty
            claimed_by_name: Discord name of the user claiming the bounty
            
        Returns:
            True if the bounty was claimed, False otherwise
        """
        # Check if the bounty is already claimed or expired
        if self.status != self.STATUS_ACTIVE:
            return False
        
        # Check if the bounty is expired
        now = datetime.utcnow()
        if self.expires_at and self.expires_at < now:
            await self.expire()
            return False
        
        # Update the bounty
        self.status = self.STATUS_CLAIMED
        self.claimed_by = str(claimed_by)
        self.claimed_by_name = str(claimed_by_name)
        self.claimed_at = now
        
        # Save to database
        return await self.save()
    
    async def expire(self) -> bool:
        """
        Mark this bounty as expired.
        
        Returns:
            True if the bounty was expired, False otherwise
        """
        # Only active bounties can be expired
        if self.status != self.STATUS_ACTIVE:
            return False
        
        # Update the bounty
        self.status = self.STATUS_EXPIRED
        
        # Save to database
        return await self.save()