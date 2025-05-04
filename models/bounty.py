"""
Bounty model for the Tower of Temptation PvP Statistics Discord Bot.

This module provides:
1. Bounty class for tracking bounties placed on players
2. Methods for creating, retrieving, claiming and managing bounties
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, TypeVar

from utils.database import get_db
from utils.async_utils import AsyncCache
from models.player_link import PlayerLink

logger = logging.getLogger(__name__)

# Type variables
B = TypeVar('B', bound='Bounty')

class Bounty:
    """Bounty model for tracking bounties placed on players"""
    
    # Bounty status
    STATUS_ACTIVE = "active"
    STATUS_CLAIMED = "claimed"
    STATUS_EXPIRED = "expired"
    
    # Bounty source
    SOURCE_PLAYER = "player"
    SOURCE_AI = "ai"
    
    # Bounty lifespans
    DEFAULT_LIFESPAN_HOURS = 1  # Default of 1 hour
    
    def __init__(self, bounty_data: Dict[str, Any]):
        """Initialize bounty model
        
        Args:
            bounty_data: Dictionary with bounty data
        """
        self.id = bounty_data.get("_id")
        self.guild_id = bounty_data.get("guild_id")
        self.server_id = bounty_data.get("server_id")
        self.target_id = bounty_data.get("target_id")
        self.target_name = bounty_data.get("target_name")
        self.placed_by = bounty_data.get("placed_by")
        self.placed_by_name = bounty_data.get("placed_by_name", "Unknown")
        self.placed_at = bounty_data.get("placed_at")
        self.reason = bounty_data.get("reason")
        self.reward = bounty_data.get("reward", 0)
        self.claimed_by = bounty_data.get("claimed_by")
        self.claimed_by_name = bounty_data.get("claimed_by_name")
        self.claimed_at = bounty_data.get("claimed_at")
        self.status = bounty_data.get("status", self.STATUS_ACTIVE)
        self.expires_at = bounty_data.get("expires_at")
        self.source = bounty_data.get("source", self.SOURCE_PLAYER)
    
    @classmethod
    async def get_by_id(cls, bounty_id: str) -> Optional['Bounty']:
        """Get a bounty by ID
        
        Args:
            bounty_id: Bounty ID
            
        Returns:
            Bounty: Bounty if found, None otherwise
        """
        db = await get_db()
        bounty_data = await db.collections["bounties"].find_one({"_id": bounty_id})
        if not bounty_data:
            return None
        
        return cls(bounty_data)
    
    @classmethod
    async def get_active_bounties(cls, guild_id: str, server_id: str) -> List['Bounty']:
        """Get all active bounties for a guild and server
        
        Args:
            guild_id: Guild ID
            server_id: Server ID
            
        Returns:
            List[Bounty]: List of active bounties
        """
        db = await get_db()
        cursor = db.collections["bounties"].find({
            "guild_id": guild_id,
            "server_id": server_id,
            "status": cls.STATUS_ACTIVE,
            "expires_at": {"$gt": datetime.utcnow()}
        })
        
        bounties = []
        async for bounty_data in cursor:
            bounties.append(cls(bounty_data))
        
        return bounties
    
    @classmethod
    async def get_bounties_by_placed_by(cls, guild_id: str, server_id: str, placed_by: str) -> List['Bounty']:
        """Get all bounties placed by a specific player
        
        Args:
            guild_id: Guild ID
            server_id: Server ID
            placed_by: Discord ID or AI
            
        Returns:
            List[Bounty]: List of bounties
        """
        db = await get_db()
        cursor = db.collections["bounties"].find({
            "guild_id": guild_id,
            "server_id": server_id,
            "placed_by": placed_by
        }).sort("placed_at", -1)
        
        bounties = []
        async for bounty_data in cursor:
            bounties.append(cls(bounty_data))
        
        return bounties
    
    @classmethod
    async def get_bounties_by_claimed_by(cls, guild_id: str, server_id: str, claimed_by: str) -> List['Bounty']:
        """Get all bounties claimed by a specific player
        
        Args:
            guild_id: Guild ID
            server_id: Server ID
            claimed_by: Discord ID
            
        Returns:
            List[Bounty]: List of bounties
        """
        db = await get_db()
        cursor = db.collections["bounties"].find({
            "guild_id": guild_id,
            "server_id": server_id,
            "claimed_by": claimed_by,
            "status": cls.STATUS_CLAIMED
        }).sort("claimed_at", -1)
        
        bounties = []
        async for bounty_data in cursor:
            bounties.append(cls(bounty_data))
        
        return bounties
    
    @classmethod
    async def get_active_bounty_for_target(cls, guild_id: str, server_id: str, target_id: str) -> Optional['Bounty']:
        """Get active bounty for a specific target
        
        Args:
            guild_id: Guild ID
            server_id: Server ID
            target_id: Target player ID
            
        Returns:
            Bounty: Active bounty if found, None otherwise
        """
        db = await get_db()
        bounty_data = await db.collections["bounties"].find_one({
            "guild_id": guild_id,
            "server_id": server_id,
            "target_id": target_id,
            "status": cls.STATUS_ACTIVE,
            "expires_at": {"$gt": datetime.utcnow()}
        })
        
        if not bounty_data:
            return None
        
        return cls(bounty_data)
    
    @classmethod
    async def create(
        cls,
        guild_id: str,
        server_id: str,
        target_id: str,
        target_name: str,
        placed_by: str,
        placed_by_name: str,
        reason: str,
        reward: int,
        source: str = SOURCE_PLAYER,
        lifespan_hours: int = DEFAULT_LIFESPAN_HOURS
    ) -> 'Bounty':
        """Create a new bounty
        
        Args:
            guild_id: Guild ID
            server_id: Server ID
            target_id: Target player ID
            target_name: Target player name
            placed_by: Discord ID or AI
            placed_by_name: Name of the person placing the bounty
            reason: Reason for bounty
            reward: Reward amount
            source: Source of bounty (player or ai)
            lifespan_hours: Hours until bounty expires
            
        Returns:
            Bounty: Created bounty
        """
        db = await get_db()
        now = datetime.utcnow()
        
        # Check for existing active bounty on this target
        existing_bounty = await cls.get_active_bounty_for_target(guild_id, server_id, target_id)
        if existing_bounty:
            # Update existing bounty with new reward (cumulative)
            total_reward = existing_bounty.reward + reward
            
            # Update the existing bounty
            result = await db.collections["bounties"].update_one(
                {"_id": existing_bounty.id},
                {"$set": {
                    "reward": total_reward,
                    "reason": reason,  # Update reason
                    "expires_at": now + timedelta(hours=lifespan_hours)  # Reset expiration
                }}
            )
            
            if result.modified_count > 0:
                existing_bounty.reward = total_reward
                existing_bounty.reason = reason
                existing_bounty.expires_at = now + timedelta(hours=lifespan_hours)
                
            return existing_bounty
        
        # Create new bounty
        bounty_data = {
            "guild_id": guild_id,
            "server_id": server_id,
            "target_id": target_id,
            "target_name": target_name,
            "placed_by": placed_by,
            "placed_by_name": placed_by_name,
            "placed_at": now,
            "reason": reason,
            "reward": reward,
            "claimed_by": None,
            "claimed_by_name": None,
            "claimed_at": None,
            "status": cls.STATUS_ACTIVE,
            "expires_at": now + timedelta(hours=lifespan_hours),
            "source": source
        }
        
        result = await db.collections["bounties"].insert_one(bounty_data)
        bounty_data["_id"] = result.inserted_id
        
        return cls(bounty_data)
    
    async def claim(self, claimed_by: str, claimed_by_name: str) -> bool:
        """Claim a bounty
        
        Args:
            claimed_by: Discord ID of claimer
            claimed_by_name: Name of claimer
            
        Returns:
            bool: True if claimed successfully, False otherwise
        """
        # Check if already claimed or expired
        if self.status != self.STATUS_ACTIVE:
            return False
        
        # Check if expired
        if self.expires_at and self.expires_at < datetime.utcnow():
            await self.expire()
            return False
        
        db = await get_db()
        now = datetime.utcnow()
        
        # Update bounty
        result = await db.collections["bounties"].update_one(
            {
                "_id": self.id,
                "status": self.STATUS_ACTIVE  # Ensure it's still active
            },
            {"$set": {
                "claimed_by": claimed_by,
                "claimed_by_name": claimed_by_name,
                "claimed_at": now,
                "status": self.STATUS_CLAIMED
            }}
        )
        
        if result.modified_count > 0:
            self.claimed_by = claimed_by
            self.claimed_by_name = claimed_by_name
            self.claimed_at = now
            self.status = self.STATUS_CLAIMED
            return True
        
        return False
    
    async def expire(self) -> bool:
        """Mark bounty as expired
        
        Returns:
            bool: True if expired successfully, False otherwise
        """
        # Check if already claimed or expired
        if self.status != self.STATUS_ACTIVE:
            return False
        
        db = await get_db()
        
        # Update bounty
        result = await db.collections["bounties"].update_one(
            {
                "_id": self.id,
                "status": self.STATUS_ACTIVE  # Ensure it's still active
            },
            {"$set": {
                "status": self.STATUS_EXPIRED
            }}
        )
        
        if result.modified_count > 0:
            self.status = self.STATUS_EXPIRED
            return True
        
        return False
    
    @classmethod
    async def expire_old_bounties(cls) -> int:
        """Expire all bounties that have passed their expiration date
        
        Returns:
            int: Number of bounties expired
        """
        db = await get_db()
        
        # Find and update all expired bounties
        result = await db.collections["bounties"].update_many(
            {
                "status": cls.STATUS_ACTIVE,
                "expires_at": {"$lt": datetime.utcnow()}
            },
            {"$set": {
                "status": cls.STATUS_EXPIRED
            }}
        )
        
        return result.modified_count
    
    @classmethod
    async def is_linked_player(cls, discord_id: str, server_id: str, player_id: str) -> bool:
        """Check if a player is linked to a Discord user
        
        Args:
            discord_id: Discord ID
            server_id: Server ID
            player_id: Player ID
            
        Returns:
            bool: True if player is linked to Discord user, False otherwise
        """
        player_link = await PlayerLink.get_by_discord_id(server_id, discord_id)
        if not player_link:
            return False
        
        return player_link.player_id == player_id

    @classmethod
    async def get_player_stats_for_bounty(cls, guild_id: str, server_id: str, minutes: int = 10, kill_threshold: int = 5, 
                                          repeat_threshold: int = 3) -> List[Dict[str, Any]]:
        """Get player stats for potential auto-bounties
        
        Args:
            guild_id: Guild ID
            server_id: Server ID
            minutes: Minutes to look back for kills
            kill_threshold: Minimum kills to trigger a killstreak bounty
            repeat_threshold: Minimum kills against the same victim to trigger a repeat bounty
            
        Returns:
            List[Dict[str, Any]]: List of player stats for potential bounties
        """
        db = await get_db()
        now = datetime.utcnow()
        time_threshold = now - timedelta(minutes=minutes)
        
        # Get recent kills
        cursor = db.collections["kills"].find({
            "server_id": server_id,
            "timestamp": {"$gt": time_threshold}
        })
        
        # Track kills by killer
        kill_counts = {}
        victim_counts = {}
        
        async for kill in cursor:
            killer_id = kill.get("killer_id")
            killer_name = kill.get("killer_name")
            victim_id = kill.get("victim_id")
            victim_name = kill.get("victim_name")
            
            if not killer_id or not victim_id:
                continue
            
            # Skip self-kills
            if killer_id == victim_id:
                continue
            
            # Count kills by killer
            if killer_id not in kill_counts:
                kill_counts[killer_id] = {
                    "killer_id": killer_id,
                    "killer_name": killer_name,
                    "total_kills": 0,
                    "victims": {}
                }
            
            kill_counts[killer_id]["total_kills"] += 1
            
            # Count kills by victim
            if victim_id not in kill_counts[killer_id]["victims"]:
                kill_counts[killer_id]["victims"][victim_id] = {
                    "victim_id": victim_id,
                    "victim_name": victim_name,
                    "kill_count": 0
                }
            
            kill_counts[killer_id]["victims"][victim_id]["kill_count"] += 1
        
        # Find potential bounty targets
        potential_bounties = []
        
        for killer_id, data in kill_counts.items():
            # Check for killstreak bounty
            if data["total_kills"] >= kill_threshold:
                potential_bounties.append({
                    "player_id": killer_id,
                    "player_name": data["killer_name"],
                    "kill_count": data["total_kills"],
                    "type": "killstreak",
                    "reason": f"Killstreak: {data['total_kills']} kills in {minutes} minutes"
                })
                continue  # Only one bounty type per player
            
            # Check for repeat kill bounty
            for victim_id, victim_data in data["victims"].items():
                if victim_data["kill_count"] >= repeat_threshold:
                    potential_bounties.append({
                        "player_id": killer_id,
                        "player_name": data["killer_name"],
                        "kill_count": victim_data["kill_count"],
                        "victim_name": victim_data["victim_name"],
                        "type": "repetition",
                        "reason": f"Repetition: Killed {victim_data['victim_name']} {victim_data['kill_count']} times"
                    })
                    break  # Only one repeat kill bounty per player
        
        return potential_bounties