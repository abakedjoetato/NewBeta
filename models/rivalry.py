"""
Rivalry model for the Tower of Temptation PvP Statistics Discord Bot.

This module provides:
1. Rivalry class for tracking player rivalries
2. Methods for creating and retrieving rivalries
3. Rivalry scoring and calculation
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Union, TypeVar, Tuple, cast

from utils.database import get_db, get_collection
from utils.async_utils import AsyncCache

from models.player import Player

logger = logging.getLogger(__name__)

# Type variables
R = TypeVar('R', bound='Rivalry')

# Constants
MIN_KILLS_FOR_RIVALRY = 3  # Minimum kills to consider a rivalry
RIVALRY_SCORE_MULTIPLIER = 1.5  # Multiplier for successive kills
RIVALRY_DECAY_DAYS = 7  # Days before rivalry score starts decaying
RIVALRY_DECAY_RATE = 0.1  # Daily decay rate for rivalries

class Rivalry:
    """Rivalry class for tracking player rivalries"""
    
    def __init__(self, data: Dict[str, Any]):
        """Initialize a rivalry
        
        Args:
            data: Rivalry data from database
        """
        self.data = data
        self._id = data.get("_id")
        self.server_id = data.get("server_id")
        self.player1_id = data.get("player1_id")
        self.player1_name = data.get("player1_name")
        self.player2_id = data.get("player2_id")
        self.player2_name = data.get("player2_name")
        self.player1_kills = data.get("player1_kills", 0)
        self.player2_kills = data.get("player2_kills", 0)
        self.rivalry_score = data.get("rivalry_score", 0)
        self.last_kill = data.get("last_kill")
        self.created_at = data.get("created_at")
        self.updated_at = data.get("updated_at")
        self.kill_history = data.get("kill_history", [])
    
    @property
    def id(self) -> str:
        """Get rivalry ID
        
        Returns:
            str: Rivalry ID
        """
        return str(self._id)
    
    @property
    def total_kills(self) -> int:
        """Get total kills in the rivalry
        
        Returns:
            int: Total kills
        """
        return self.player1_kills + self.player2_kills
    
    @property
    def is_active(self) -> bool:
        """Check if rivalry is active
        
        Returns:
            bool: True if rivalry is active
        """
        return self.total_kills >= MIN_KILLS_FOR_RIVALRY
    
    @property
    def is_one_sided(self) -> bool:
        """Check if rivalry is one-sided
        
        Returns:
            bool: True if rivalry is one-sided
        """
        # Requires at least 5 total kills and one player has > 80% of kills
        if self.total_kills < 5:
            return False
            
        player1_percent = self.player1_kills / self.total_kills
        player2_percent = self.player2_kills / self.total_kills
        
        return player1_percent > 0.8 or player2_percent > 0.8
    
    @classmethod
    @AsyncCache.cached(ttl=60)
    async def get_by_id(cls, rivalry_id: str) -> Optional['Rivalry']:
        """Get rivalry by ID
        
        Args:
            rivalry_id: Rivalry document ID
            
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
        """Get rivalry between two players
        
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
            "player1_id": player1_id,
            "player2_id": player2_id
        })
        
        if not rivalry_data:
            rivalry_data = await db.collections["rivalries"].find_one({
                "server_id": server_id,
                "player1_id": player2_id,
                "player2_id": player1_id
            })
        
        if not rivalry_data:
            return None
        
        return cls(rivalry_data)
    
    @classmethod
    async def get_by_player(cls, server_id: str, player_id: str) -> List['Rivalry']:
        """Get all rivalries for a player
        
        Args:
            server_id: Server ID
            player_id: Player ID
            
        Returns:
            List[Rivalry]: List of rivalries
        """
        db = await get_db()
        
        # Get rivalries where player is either player1 or player2
        cursor1 = db.collections["rivalries"].find({
            "server_id": server_id,
            "player1_id": player_id
        })
        
        cursor2 = db.collections["rivalries"].find({
            "server_id": server_id,
            "player2_id": player_id
        })
        
        # Combine results
        rivalries_data = await cursor1.to_list(length=None)
        rivalries_data.extend(await cursor2.to_list(length=None))
        
        # Convert to rivalry objects
        return [cls(rivalry_data) for rivalry_data in rivalries_data]
    
    @classmethod
    async def get_top_rivalries(
        cls,
        server_id: str,
        limit: int = 10
    ) -> List['Rivalry']:
        """Get top rivalries by score
        
        Args:
            server_id: Server ID
            limit: Maximum number of rivalries to return (default: 10)
            
        Returns:
            List[Rivalry]: List of top rivalries
        """
        db = await get_db()
        
        rivalries_data = await db.collections["rivalries"].find({
            "server_id": server_id,
            "rivalry_score": {"$gt": 0}
        }).sort("rivalry_score", -1).limit(limit).to_list(length=limit)
        
        return [cls(rivalry_data) for rivalry_data in rivalries_data]
    
    @classmethod
    async def get_most_one_sided(
        cls,
        server_id: str,
        limit: int = 10
    ) -> List['Rivalry']:
        """Get most one-sided rivalries
        
        Args:
            server_id: Server ID
            limit: Maximum number of rivalries to return (default: 10)
            
        Returns:
            List[Rivalry]: List of most one-sided rivalries
        """
        db = await get_db()
        
        # Get rivalries with at least 5 total kills
        rivalries_data = await db.collections["rivalries"].find({
            "server_id": server_id,
            "$expr": {"$gte": [{"$add": ["$player1_kills", "$player2_kills"]}, 5]}
        }).to_list(length=None)
        
        # Calculate one-sidedness for each rivalry
        rivalries = []
        for data in rivalries_data:
            rivalry = cls(data)
            if rivalry.is_one_sided:
                rivalries.append(rivalry)
        
        # Sort by difference between player kills
        rivalries.sort(key=lambda r: abs(r.player1_kills - r.player2_kills), reverse=True)
        
        return rivalries[:limit]
    
    @classmethod
    async def record_kill(
        cls,
        server_id: str,
        killer_id: str,
        killer_name: str,
        victim_id: str,
        victim_name: str,
        weapon: str = None,
        location: str = None
    ) -> 'Rivalry':
        """Record a kill and update the rivalry
        
        Args:
            server_id: Server ID
            killer_id: Killer ID
            killer_name: Killer name
            victim_id: Victim ID
            victim_name: Victim name
            weapon: Weapon used (default: None)
            location: Location (default: None)
            
        Returns:
            Rivalry: Updated rivalry
        """
        # Don't create rivalry for self-kills
        if killer_id == victim_id:
            logger.debug(f"Ignoring self-kill: {killer_name} ({killer_id})")
            return None
            
        # Get or create Player objects
        killer = await Player.create_or_update(server_id, killer_id, killer_name)
        victim = await Player.create_or_update(server_id, victim_id, victim_name)
        
        # Record kill and death for players
        await killer.record_kill(victim_id, victim_name, weapon)
        await victim.record_death(killer_id, killer_name, weapon)
        
        # Get current time
        now = datetime.utcnow()
        
        # Get existing rivalry or create new one
        rivalry = await cls.get_by_players(server_id, killer_id, victim_id)
        
        if rivalry:
            # Update existing rivalry
            db = await get_db()
            
            # Determine which player is the killer
            if killer_id == rivalry.player1_id:
                player1_kills = rivalry.player1_kills + 1
                player2_kills = rivalry.player2_kills
                last_killer = 1
            else:
                player1_kills = rivalry.player1_kills
                player2_kills = rivalry.player2_kills + 1
                last_killer = 2
                
            # Calculate new rivalry score
            kill_history = rivalry.kill_history + [last_killer]
            rivalry_score = cls._calculate_rivalry_score(kill_history)
            
            # Prepare kill event data
            kill_event = {
                "killer_id": killer_id,
                "killer_name": killer_name,
                "victim_id": victim_id,
                "victim_name": victim_name,
                "weapon": weapon,
                "location": location,
                "timestamp": now
            }
            
            # Update rivalry data
            update_data = {
                "player1_kills": player1_kills,
                "player2_kills": player2_kills,
                "rivalry_score": rivalry_score,
                "last_kill": kill_event,
                "updated_at": now,
                "kill_history": kill_history[-20:]  # Keep last 20 kills
            }
            
            result = await db.collections["rivalries"].update_one(
                {"_id": rivalry._id},
                {"$set": update_data}
            )
            
            # Update local data
            rivalry.player1_kills = player1_kills
            rivalry.player2_kills = player2_kills
            rivalry.rivalry_score = rivalry_score
            rivalry.last_kill = kill_event
            rivalry.updated_at = now
            rivalry.kill_history = kill_history[-20:]
            
            # Clear cache
            AsyncCache.invalidate(cls.get_by_id, rivalry.id)
            AsyncCache.invalidate(cls.get_by_players, server_id, rivalry.player1_id, rivalry.player2_id)
            
            # Store kill event
            await cls._store_kill_event(server_id, killer_id, killer_name, victim_id, victim_name, weapon, location)
            
            return rivalry
            
        else:
            # Create new rivalry
            db = await get_db()
            
            # Ensure consistent order (smaller ID first)
            if killer_id < victim_id:
                player1_id = killer_id
                player1_name = killer_name
                player2_id = victim_id
                player2_name = victim_name
                player1_kills = 1
                player2_kills = 0
                kill_history = [1]  # 1 represents player1 killed player2
            else:
                player1_id = victim_id
                player1_name = victim_name
                player2_id = killer_id
                player2_name = killer_name
                player1_kills = 0
                player2_kills = 1
                kill_history = [2]  # 2 represents player2 killed player1
            
            # Prepare kill event data
            kill_event = {
                "killer_id": killer_id,
                "killer_name": killer_name,
                "victim_id": victim_id,
                "victim_name": victim_name,
                "weapon": weapon,
                "location": location,
                "timestamp": now
            }
            
            # Create rivalry document
            rivalry_data = {
                "server_id": server_id,
                "player1_id": player1_id,
                "player1_name": player1_name,
                "player2_id": player2_id,
                "player2_name": player2_name,
                "player1_kills": player1_kills,
                "player2_kills": player2_kills,
                "rivalry_score": 1,  # Initial score
                "last_kill": kill_event,
                "kill_history": kill_history,
                "created_at": now,
                "updated_at": now
            }
            
            result = await db.collections["rivalries"].insert_one(rivalry_data)
            rivalry_data["_id"] = result.inserted_id
            
            # Store kill event
            await cls._store_kill_event(server_id, killer_id, killer_name, victim_id, victim_name, weapon, location)
            
            return cls(rivalry_data)
    
    @classmethod
    async def _store_kill_event(cls, server_id: str, killer_id: str, killer_name: str,
                               victim_id: str, victim_name: str, weapon: str = None,
                               location: str = None) -> bool:
        """Store a kill event in the database
        
        Args:
            server_id: Server ID
            killer_id: Killer ID
            killer_name: Killer name
            victim_id: Victim ID
            victim_name: Victim name
            weapon: Weapon used (default: None)
            location: Location (default: None)
            
        Returns:
            bool: True if successful
        """
        db = await get_db()
        now = datetime.utcnow()
        
        # Create kill event document
        kill_event = {
            "server_id": server_id,
            "killer_id": killer_id,
            "killer_name": killer_name,
            "victim_id": victim_id,
            "victim_name": victim_name,
            "weapon": weapon,
            "location": location,
            "timestamp": now
        }
        
        try:
            result = await db.collections["kill_events"].insert_one(kill_event)
            return result.acknowledged
        except Exception as e:
            logger.error(f"Error storing kill event: {str(e)}")
            return False
    
    @classmethod
    def _calculate_rivalry_score(cls, kill_history: List[int]) -> float:
        """Calculate rivalry score from kill history
        
        Args:
            kill_history: List of kill history (1 = player1, 2 = player2)
            
        Returns:
            float: Rivalry score
        """
        if not kill_history:
            return 0
            
        score = 0
        streak = 0
        last_killer = 0
        
        for killer in kill_history:
            if killer == last_killer:
                # Continuing streak
                streak += 1
                # Apply multiplier for successive kills
                score += 1 * (RIVALRY_SCORE_MULTIPLIER ** min(streak, 3))
            else:
                # New killer, reset streak
                streak = 0
                score += 1
                
            last_killer = killer
            
        # Bonus for balanced rivalries
        player1_kills = kill_history.count(1)
        player2_kills = kill_history.count(2)
        total_kills = player1_kills + player2_kills
        
        if total_kills >= 6:
            min_kills = min(player1_kills, player2_kills)
            max_kills = max(player1_kills, player2_kills)
            
            # If at least 25% of kills are from underdog
            if min_kills / total_kills >= 0.25:
                score *= 1.2
                
        return round(score, 1)
    
    async def update_player_names(self) -> bool:
        """Update player names from latest data
        
        Returns:
            bool: True if successful
        """
        db = await get_db()
        now = datetime.utcnow()
        
        # Get latest player data
        player1 = await Player.get_by_player_id(self.server_id, self.player1_id)
        player2 = await Player.get_by_player_id(self.server_id, self.player2_id)
        
        if player1 and player2:
            # Update if names have changed
            if player1.player_name != self.player1_name or player2.player_name != self.player2_name:
                update_data = {
                    "player1_name": player1.player_name,
                    "player2_name": player2.player_name,
                    "updated_at": now
                }
                
                result = await db.collections["rivalries"].update_one(
                    {"_id": self._id},
                    {"$set": update_data}
                )
                
                # Update local data
                self.player1_name = player1.player_name
                self.player2_name = player2.player_name
                self.updated_at = now
                
                # Clear cache
                AsyncCache.invalidate(self.__class__.get_by_id, self.id)
                AsyncCache.invalidate(self.__class__.get_by_players, self.server_id, self.player1_id, self.player2_id)
                
                return result.acknowledged
                
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert rivalry to dictionary
        
        Returns:
            Dict: Rivalry data
        """
        return {
            "id": self.id,
            "server_id": self.server_id,
            "player1_id": self.player1_id,
            "player1_name": self.player1_name,
            "player2_id": self.player2_id,
            "player2_name": self.player2_name,
            "player1_kills": self.player1_kills,
            "player2_kills": self.player2_kills,
            "total_kills": self.total_kills,
            "rivalry_score": self.rivalry_score,
            "is_active": self.is_active,
            "is_one_sided": self.is_one_sided,
            "last_kill": self.last_kill,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }