"""
Rivalry model for the Tower of Temptation PvP Statistics Discord Bot.

This module provides:
1. Rivalry class for tracking player-vs-player rivalries
2. Methods for updating rivalry stats
3. Methods for retrieving rivalry information
"""
import asyncio
import logging
import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set, Union, TypeVar, Tuple

from utils.database import get_db
from utils.async_utils import AsyncCache

logger = logging.getLogger(__name__)

# Type variables
R = TypeVar('R', bound='Rivalry')

class Rivalry:
    """Rivalry class for tracking player-vs-player rivalries"""
    
    def __init__(self, data: Dict[str, Any]):
        """Initialize a rivalry
        
        Args:
            data: Rivalry data from database
        """
        self.data = data
        self._id = data.get("_id")
        self.server_id = data.get("server_id")
        self.player1_id = data.get("player1_id")
        self.player2_id = data.get("player2_id")
        self.player1_name = data.get("player1_name")
        self.player2_name = data.get("player2_name")
        self.player1_kills = data.get("player1_kills", 0)
        self.player2_kills = data.get("player2_kills", 0)
        self.total_kills = data.get("total_kills", 0)
        self.last_kill = data.get("last_kill")
        self.last_weapon = data.get("last_weapon")
        self.last_location = data.get("last_location")
        self.created_at = data.get("created_at")
        self.updated_at = data.get("updated_at")
        self.is_active = data.get("is_active", True)
        self.recent_kills = data.get("recent_kills", [])
    
    @property
    def id(self) -> str:
        """Get rivalry ID
        
        Returns:
            str: Rivalry ID
        """
        return str(self._id)
    
    @property
    def score_difference(self) -> int:
        """Get score difference
        
        Returns:
            int: Score difference
        """
        return abs(self.player1_kills - self.player2_kills)
    
    @property
    def intensity_score(self) -> float:
        """Get rivalry intensity score
        
        This is a measure of how competitive the rivalry is.
        Higher scores indicate more intense rivalries.
        
        Formula: total_kills * (1 - abs(p1_kills - p2_kills) / total_kills)^2
        
        Returns:
            float: Intensity score
        """
        if self.total_kills <= 1:
            return 0.0
            
        balance = 1.0 - (self.score_difference / self.total_kills)
        return self.total_kills * (balance ** 2)
    
    def get_leader(self) -> Tuple[str, str]:
        """Get rivalry leader
        
        Returns:
            Tuple[str, str]: Leader player ID and name
        """
        if self.player1_kills >= self.player2_kills:
            return self.player1_id, self.player1_name
        else:
            return self.player2_id, self.player2_name
    
    def get_stats_for_player(self, player_id: str) -> Dict[str, Any]:
        """Get rivalry stats from a player's perspective
        
        Args:
            player_id: Player ID
            
        Returns:
            Dict: Rivalry stats
            
        Raises:
            ValueError: If player is not part of this rivalry
        """
        if player_id == self.player1_id:
            # Player is player1
            kills = self.player1_kills
            deaths = self.player2_kills
            opponent_id = self.player2_id
            opponent_name = self.player2_name
            is_leading = kills >= deaths
        elif player_id == self.player2_id:
            # Player is player2
            kills = self.player2_kills
            deaths = self.player1_kills
            opponent_id = self.player1_id
            opponent_name = self.player1_name
            is_leading = kills >= deaths
        else:
            raise ValueError("Player is not part of this rivalry")
        
        # Calculate K/D ratio
        kd_ratio = kills / max(deaths, 1)
        
        return {
            "player_id": player_id,
            "opponent_id": opponent_id,
            "opponent_name": opponent_name,
            "kills": kills,
            "deaths": deaths,
            "total_kills": self.total_kills,
            "kd_ratio": kd_ratio,
            "is_leading": is_leading,
            "score_difference": abs(kills - deaths),
            "last_kill": self.last_kill,
            "last_weapon": self.last_weapon,
            "last_location": self.last_location,
            "intensity_score": self.intensity_score
        }
    
    @classmethod
    @AsyncCache.cached(ttl=60)
    async def get_by_id(cls, rivalry_id: str) -> Optional['Rivalry']:
        """Get rivalry by ID
        
        Args:
            rivalry_id: Rivalry ID
            
        Returns:
            Rivalry or None: Rivalry if found
        """
        db = await get_db()
        rivalry_data = await db.collections["rivalries"].find_one({"_id": rivalry_id})
        
        if not rivalry_data:
            return None
        
        return cls(rivalry_data)
    
    @classmethod
    @AsyncCache.cached(ttl=60)
    async def get_by_players(
        cls,
        server_id: str,
        player1_id: str,
        player2_id: str
    ) -> Optional['Rivalry']:
        """Get rivalry by players
        
        Args:
            server_id: Server ID
            player1_id: First player ID
            player2_id: Second player ID
            
        Returns:
            Rivalry or None: Rivalry if found
        """
        db = await get_db()
        
        # Try both player orders
        rivalry_data = await db.collections["rivalries"].find_one({
            "server_id": server_id,
            "$or": [
                {
                    "player1_id": player1_id,
                    "player2_id": player2_id
                },
                {
                    "player1_id": player2_id,
                    "player2_id": player1_id
                }
            ]
        })
        
        if not rivalry_data:
            return None
        
        return cls(rivalry_data)
    
    @classmethod
    @AsyncCache.cached(ttl=60)
    async def get_for_player(cls, server_id: str, player_id: str) -> List['Rivalry']:
        """Get rivalries for a player
        
        Args:
            server_id: Server ID
            player_id: Player ID
            
        Returns:
            List[Rivalry]: List of rivalries
        """
        db = await get_db()
        
        # Get rivalries where player is involved
        cursor = db.collections["rivalries"].find({
            "server_id": server_id,
            "$or": [
                {"player1_id": player_id},
                {"player2_id": player_id}
            ]
        }).sort("total_kills", -1)
        
        rivalry_data = await cursor.to_list(length=None)
        return [cls(data) for data in rivalry_data]
    
    @classmethod
    @AsyncCache.cached(ttl=30)
    async def get_top_rivalries(cls, server_id: str, limit: int = 10) -> List['Rivalry']:
        """Get top rivalries by total kills
        
        Args:
            server_id: Server ID
            limit: Maximum number of rivalries to return
            
        Returns:
            List[Rivalry]: List of top rivalries
        """
        db = await get_db()
        
        # Get rivalries with minimum kill threshold
        cursor = db.collections["rivalries"].find({
            "server_id": server_id,
            "total_kills": {"$gt": 1}
        }).sort("total_kills", -1).limit(limit)
        
        rivalry_data = await cursor.to_list(length=None)
        return [cls(data) for data in rivalry_data]
    
    @classmethod
    @AsyncCache.cached(ttl=30)
    async def get_closest_rivalries(cls, server_id: str, limit: int = 10) -> List['Rivalry']:
        """Get closest rivalries by score difference
        
        Args:
            server_id: Server ID
            limit: Maximum number of rivalries to return
            
        Returns:
            List[Rivalry]: List of closest rivalries
        """
        db = await get_db()
        pipeline = [
            {"$match": {
                "server_id": server_id,
                "total_kills": {"$gt": 3}  # Require at least 4 kills
            }},
            {"$addFields": {
                "score_difference": {"$abs": {"$subtract": ["$player1_kills", "$player2_kills"]}},
            }},
            {"$sort": {"score_difference": 1, "total_kills": -1}},
            {"$limit": limit}
        ]
        
        cursor = db.collections["rivalries"].aggregate(pipeline)
        rivalry_data = await cursor.to_list(length=None)
        
        return [cls(data) for data in rivalry_data]
    
    @classmethod
    @AsyncCache.cached(ttl=30)
    async def get_recent_rivalries(
        cls,
        server_id: str,
        limit: int = 10,
        days: int = 7
    ) -> List['Rivalry']:
        """Get recently active rivalries
        
        Args:
            server_id: Server ID
            limit: Maximum number of rivalries to return
            days: Number of days to look back
            
        Returns:
            List[Rivalry]: List of recent rivalries
        """
        db = await get_db()
        
        # Calculate date threshold
        threshold = datetime.utcnow() - timedelta(days=days)
        
        # Get rivalries with recent activity
        cursor = db.collections["rivalries"].find({
            "server_id": server_id,
            "last_kill": {"$gte": threshold}
        }).sort("last_kill", -1).limit(limit)
        
        rivalry_data = await cursor.to_list(length=None)
        return [cls(data) for data in rivalry_data]
    
    @classmethod
    async def record_kill(
        cls,
        server_id: str,
        killer_id: str,
        killer_name: str,
        victim_id: str,
        victim_name: str,
        weapon: Optional[str] = None,
        location: Optional[str] = None
    ) -> 'Rivalry':
        """Record a kill and update rivalry
        
        Args:
            server_id: Server ID
            killer_id: Killer player ID
            killer_name: Killer player name
            victim_id: Victim player ID
            victim_name: Victim player name
            weapon: Weapon used (optional)
            location: Kill location (optional)
            
        Returns:
            Rivalry: Updated rivalry
        """
        # Check if rivalry exists
        rivalry = await cls.get_by_players(server_id, killer_id, victim_id)
        
        now = datetime.utcnow()
        db = await get_db()
        
        # Create or update rivalry
        if not rivalry:
            # Create new rivalry
            rivalry_data = {
                "server_id": server_id,
                "player1_id": killer_id,
                "player2_id": victim_id,
                "player1_name": killer_name,
                "player2_name": victim_name,
                "player1_kills": 1,
                "player2_kills": 0,
                "total_kills": 1,
                "last_kill": now,
                "last_weapon": weapon,
                "last_location": location,
                "created_at": now,
                "updated_at": now,
                "is_active": True,
                "recent_kills": [{
                    "killer_id": killer_id,
                    "killer_name": killer_name,
                    "victim_id": victim_id,
                    "victim_name": victim_name,
                    "weapon": weapon,
                    "location": location,
                    "timestamp": now
                }]
            }
            
            result = await db.collections["rivalries"].insert_one(rivalry_data)
            rivalry_data["_id"] = result.inserted_id
            
            # Invalidate caches
            AsyncCache.invalidate_all(cls.get_for_player)
            AsyncCache.invalidate_all(cls.get_top_rivalries)
            AsyncCache.invalidate_all(cls.get_closest_rivalries)
            AsyncCache.invalidate_all(cls.get_recent_rivalries)
            
            return cls(rivalry_data)
        
        # Prepare update
        kill_data = {
            "killer_id": killer_id,
            "killer_name": killer_name,
            "victim_id": victim_id,
            "victim_name": victim_name,
            "weapon": weapon,
            "location": location,
            "timestamp": now
        }
        
        update_query = {
            "$set": {
                "last_kill": now,
                "last_weapon": weapon,
                "last_location": location,
                "updated_at": now,
                "is_active": True
            },
            "$inc": {"total_kills": 1},
            "$push": {
                "recent_kills": {
                    "$each": [kill_data],
                    "$slice": -10  # Keep only the 10 most recent kills
                }
            }
        }
        
        # Increment the appropriate kill counter
        if killer_id == rivalry.player1_id:
            update_query["$inc"]["player1_kills"] = 1
        else:
            update_query["$inc"]["player2_kills"] = 1
        
        # Update rivalry
        result = await db.collections["rivalries"].find_one_and_update(
            {"_id": rivalry._id},
            update_query,
            return_document=True
        )
        
        # Invalidate caches
        AsyncCache.invalidate(cls.get_by_id, rivalry.id)
        AsyncCache.invalidate(cls.get_by_players, server_id, killer_id, victim_id)
        AsyncCache.invalidate_all(cls.get_for_player)
        AsyncCache.invalidate_all(cls.get_top_rivalries)
        AsyncCache.invalidate_all(cls.get_closest_rivalries)
        AsyncCache.invalidate_all(cls.get_recent_rivalries)
        
        return cls(result)
    
    async def update(self, update_data: Dict[str, Any]) -> 'Rivalry':
        """Update rivalry data
        
        Args:
            update_data: Data to update
            
        Returns:
            Rivalry: Updated rivalry
        """
        # Update rivalry
        db = await get_db()
        update_data["updated_at"] = datetime.utcnow()
        
        result = await db.collections["rivalries"].find_one_and_update(
            {"_id": self._id},
            {"$set": update_data},
            return_document=True
        )
        
        # Invalidate caches
        AsyncCache.invalidate(self.__class__.get_by_id, self.id)
        AsyncCache.invalidate(self.__class__.get_by_players, self.server_id, self.player1_id, self.player2_id)
        AsyncCache.invalidate_all(self.__class__.get_for_player)
        AsyncCache.invalidate_all(self.__class__.get_top_rivalries)
        AsyncCache.invalidate_all(self.__class__.get_closest_rivalries)
        AsyncCache.invalidate_all(self.__class__.get_recent_rivalries)
        
        # Update local state
        self.data = result
        for key, value in update_data.items():
            setattr(self, key, value)
        
        return self
    
    async def deactivate(self) -> bool:
        """Deactivate rivalry
        
        Returns:
            bool: True if successfully deactivated
        """
        return await self.update({"is_active": False})
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert rivalry to dictionary
        
        Returns:
            Dict: Rivalry data
        """
        return {
            "id": self.id,
            "server_id": self.server_id,
            "player1_id": self.player1_id,
            "player2_id": self.player2_id,
            "player1_name": self.player1_name,
            "player2_name": self.player2_name,
            "player1_kills": self.player1_kills,
            "player2_kills": self.player2_kills,
            "total_kills": self.total_kills,
            "score_difference": self.score_difference,
            "intensity_score": self.intensity_score,
            "last_kill": self.last_kill.isoformat() if self.last_kill else None,
            "last_weapon": self.last_weapon,
            "last_location": self.last_location,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "is_active": self.is_active
        }