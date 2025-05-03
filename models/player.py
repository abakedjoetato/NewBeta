"""
Player model for the Tower of Temptation PvP Statistics Discord Bot.

This module provides:
1. Player class for storing player data
2. Methods for creating and retrieving players
3. Player statistics calculation
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Union, TypeVar

from utils.database import get_db, get_collection
from utils.async_utils import AsyncCache

logger = logging.getLogger(__name__)

# Type variables
P = TypeVar('P', bound='Player')

class Player:
    """Player class for player data and statistics"""
    
    def __init__(self, data: Dict[str, Any]):
        """Initialize a player
        
        Args:
            data: Player data from database
        """
        self.data = data
        self._id = data.get("_id")
        self.server_id = data.get("server_id")
        self.player_id = data.get("player_id")
        self.player_name = data.get("player_name")
        self.faction_id = data.get("faction_id")
        self.first_seen = data.get("first_seen")
        self.last_seen = data.get("last_seen")
        self.kills = data.get("kills", 0)
        self.deaths = data.get("deaths", 0)
        self.assists = data.get("assists", 0)
        self.stats = data.get("stats", {})
        self.weapons = data.get("weapons", {})
        self.victims = data.get("victims", {})
        self.killers = data.get("killers", {})
        self.last_kill = data.get("last_kill")
        self.last_death = data.get("last_death")
        self.created_at = data.get("created_at")
        self.updated_at = data.get("updated_at")
    
    @property
    def id(self) -> str:
        """Get player ID
        
        Returns:
            str: Player ID
        """
        return str(self._id)
    
    @property
    def kd_ratio(self) -> float:
        """Get kill/death ratio
        
        Returns:
            float: Kill/death ratio
        """
        if self.deaths == 0:
            return float(self.kills)
        return self.kills / self.deaths
    
    @property
    def favorite_weapon(self) -> Optional[str]:
        """Get favorite weapon
        
        Returns:
            str or None: Favorite weapon
        """
        if not self.weapons:
            return None
            
        # Sort weapons by kill count
        sorted_weapons = sorted(self.weapons.items(), key=lambda x: x[1], reverse=True)
        if sorted_weapons:
            return sorted_weapons[0][0]
            
        return None
    
    @property
    def is_active(self) -> bool:
        """Check if player is active
        
        Returns:
            bool: True if player is active
        """
        return self.last_seen is not None and (
            datetime.utcnow() - self.last_seen).days < 30
    
    @classmethod
    @AsyncCache.cached(ttl=60)
    async def get_by_id(cls, player_id: str) -> Optional['Player']:
        """Get player by ID
        
        Args:
            player_id: Player document ID
            
        Returns:
            Player or None: Player if found
        """
        db = await get_db()
        player_data = await db.collections["players"].find_one({"_id": player_id})
        
        if not player_data:
            return None
        
        return cls(player_data)
    
    @classmethod
    @AsyncCache.cached(ttl=60)
    async def get_by_player_id(cls, server_id: str, player_id: str) -> Optional['Player']:
        """Get player by player ID
        
        Args:
            server_id: Server ID
            player_id: Player ID
            
        Returns:
            Player or None: Player if found
        """
        db = await get_db()
        player_data = await db.collections["players"].find_one({
            "server_id": server_id,
            "player_id": player_id
        })
        
        if not player_data:
            return None
        
        return cls(player_data)
    
    @classmethod
    @AsyncCache.cached(ttl=60)
    async def get_by_player_name(cls, server_id: str, player_name: str) -> Optional['Player']:
        """Get player by player name
        
        Args:
            server_id: Server ID
            player_name: Player name
            
        Returns:
            Player or None: Player if found
        """
        db = await get_db()
        player_data = await db.collections["players"].find_one({
            "server_id": server_id,
            "player_name": player_name
        })
        
        if not player_data:
            return None
        
        return cls(player_data)
    
    @classmethod
    async def get_by_faction(cls, server_id: str, faction_id: str) -> List['Player']:
        """Get players by faction
        
        Args:
            server_id: Server ID
            faction_id: Faction ID
            
        Returns:
            List[Player]: List of players in faction
        """
        db = await get_db()
        players_data = await db.collections["players"].find({
            "server_id": server_id,
            "faction_id": faction_id
        }).to_list(length=None)
        
        return [cls(player_data) for player_data in players_data]
    
    @classmethod
    async def get_top_players(
        cls,
        server_id: str,
        sort_by: str = "kills",
        limit: int = 10
    ) -> List['Player']:
        """Get top players
        
        Args:
            server_id: Server ID
            sort_by: Field to sort by (default: "kills")
            limit: Maximum number of players to return (default: 10)
            
        Returns:
            List[Player]: List of top players
        """
        db = await get_db()
        
        # Determine sort direction (descending for most fields)
        sort_direction = -1
        
        # Make sure sort field exists
        valid_sort_fields = ["kills", "deaths", "kd_ratio", "last_seen"]
        if sort_by not in valid_sort_fields:
            sort_by = "kills"
        
        players_data = await db.collections["players"].find({
            "server_id": server_id
        }).sort(sort_by, sort_direction).limit(limit).to_list(length=limit)
        
        return [cls(player_data) for player_data in players_data]
    
    @classmethod
    async def search_by_name(cls, server_id: str, name_query: str) -> List['Player']:
        """Search players by name
        
        Args:
            server_id: Server ID
            name_query: Name query
            
        Returns:
            List[Player]: List of matching players
        """
        db = await get_db()
        
        # Case insensitive search with regex
        players_data = await db.collections["players"].find({
            "server_id": server_id,
            "player_name": {"$regex": name_query, "$options": "i"}
        }).limit(10).to_list(length=10)
        
        return [cls(player_data) for player_data in players_data]
    
    @classmethod
    async def create_or_update(
        cls,
        server_id: str,
        player_id: str,
        player_name: str
    ) -> 'Player':
        """Create or update a player
        
        Args:
            server_id: Server ID
            player_id: Player ID
            player_name: Player name
            
        Returns:
            Player: Created or updated player
        """
        db = await get_db()
        now = datetime.utcnow()
        
        # Check if player exists
        existing_player = await cls.get_by_player_id(server_id, player_id)
        
        if existing_player:
            # Update player
            update_data = {
                "player_name": player_name,
                "last_seen": now,
                "updated_at": now
            }
            
            result = await db.collections["players"].update_one(
                {"_id": existing_player._id},
                {"$set": update_data}
            )
            
            # Clear cache
            AsyncCache.invalidate(cls.get_by_id, existing_player.id)
            AsyncCache.invalidate(cls.get_by_player_id, server_id, player_id)
            AsyncCache.invalidate(cls.get_by_player_name, server_id, existing_player.player_name)
            
            # Update data
            existing_player.player_name = player_name
            existing_player.last_seen = now
            existing_player.updated_at = now
            
            return existing_player
        else:
            # Create new player
            player_data = {
                "server_id": server_id,
                "player_id": player_id,
                "player_name": player_name,
                "faction_id": None,
                "first_seen": now,
                "last_seen": now,
                "kills": 0,
                "deaths": 0,
                "assists": 0,
                "stats": {},
                "weapons": {},
                "victims": {},
                "killers": {},
                "created_at": now,
                "updated_at": now
            }
            
            result = await db.collections["players"].insert_one(player_data)
            player_data["_id"] = result.inserted_id
            
            return cls(player_data)
    
    async def record_kill(self, victim_id: str, victim_name: str, weapon: str = None) -> bool:
        """Record a kill
        
        Args:
            victim_id: Victim ID
            victim_name: Victim name
            weapon: Weapon used (default: None)
            
        Returns:
            bool: True if successful
        """
        db = await get_db()
        now = datetime.utcnow()
        
        # Update victim count
        self.victims[victim_id] = self.victims.get(victim_id, 0) + 1
        
        # Update weapon count
        if weapon:
            self.weapons[weapon] = self.weapons.get(weapon, 0) + 1
        
        # Prepare update data
        update_data = {
            "kills": self.kills + 1,
            "last_seen": now,
            "updated_at": now,
            "victims": self.victims,
            "weapons": self.weapons,
            "last_kill": {
                "victim_id": victim_id,
                "victim_name": victim_name,
                "weapon": weapon,
                "timestamp": now
            }
        }
        
        # Update database
        result = await db.collections["players"].update_one(
            {"_id": self._id},
            {"$set": update_data, "$inc": {"kills": 1}}
        )
        
        # Update local data
        self.kills += 1
        self.last_seen = now
        self.updated_at = now
        self.last_kill = update_data["last_kill"]
        
        # Clear cache
        AsyncCache.invalidate(self.__class__.get_by_id, self.id)
        AsyncCache.invalidate(self.__class__.get_by_player_id, self.server_id, self.player_id)
        AsyncCache.invalidate(self.__class__.get_by_player_name, self.server_id, self.player_name)
        
        return result.acknowledged
    
    async def record_death(self, killer_id: str, killer_name: str, weapon: str = None) -> bool:
        """Record a death
        
        Args:
            killer_id: Killer ID
            killer_name: Killer name
            weapon: Weapon used (default: None)
            
        Returns:
            bool: True if successful
        """
        db = await get_db()
        now = datetime.utcnow()
        
        # Update killer count
        self.killers[killer_id] = self.killers.get(killer_id, 0) + 1
        
        # Prepare update data
        update_data = {
            "deaths": self.deaths + 1,
            "last_seen": now,
            "updated_at": now,
            "killers": self.killers,
            "last_death": {
                "killer_id": killer_id,
                "killer_name": killer_name,
                "weapon": weapon,
                "timestamp": now
            }
        }
        
        # Update database
        result = await db.collections["players"].update_one(
            {"_id": self._id},
            {"$set": update_data, "$inc": {"deaths": 1}}
        )
        
        # Update local data
        self.deaths += 1
        self.last_seen = now
        self.updated_at = now
        self.last_death = update_data["last_death"]
        
        # Clear cache
        AsyncCache.invalidate(self.__class__.get_by_id, self.id)
        AsyncCache.invalidate(self.__class__.get_by_player_id, self.server_id, self.player_id)
        AsyncCache.invalidate(self.__class__.get_by_player_name, self.server_id, self.player_name)
        
        return result.acknowledged
    
    async def set_faction(self, faction_id: Optional[str]) -> bool:
        """Set player faction
        
        Args:
            faction_id: Faction ID or None to remove
            
        Returns:
            bool: True if successful
        """
        db = await get_db()
        now = datetime.utcnow()
        
        # Prepare update data
        update_data = {
            "faction_id": faction_id,
            "updated_at": now
        }
        
        # Update database
        result = await db.collections["players"].update_one(
            {"_id": self._id},
            {"$set": update_data}
        )
        
        # Update local data
        self.faction_id = faction_id
        self.updated_at = now
        
        # Clear cache
        AsyncCache.invalidate(self.__class__.get_by_id, self.id)
        AsyncCache.invalidate(self.__class__.get_by_player_id, self.server_id, self.player_id)
        AsyncCache.invalidate(self.__class__.get_by_player_name, self.server_id, self.player_name)
        
        return result.acknowledged
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get player statistics
        
        Returns:
            Dict: Player statistics
        """
        db = await get_db()
        
        # Basic stats
        stats = {
            "kills": self.kills,
            "deaths": self.deaths,
            "kd_ratio": self.kd_ratio,
            "favorite_weapon": self.favorite_weapon,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "is_active": self.is_active
        }
        
        # Get top victims
        if self.victims:
            top_victims = sorted(self.victims.items(), key=lambda x: x[1], reverse=True)[:5]
            stats["top_victims"] = []
            
            for victim_id, count in top_victims:
                victim = await self.__class__.get_by_player_id(self.server_id, victim_id)
                if victim:
                    stats["top_victims"].append({
                        "id": victim_id,
                        "name": victim.player_name,
                        "count": count
                    })
        
        # Get top killers
        if self.killers:
            top_killers = sorted(self.killers.items(), key=lambda x: x[1], reverse=True)[:5]
            stats["top_killers"] = []
            
            for killer_id, count in top_killers:
                killer = await self.__class__.get_by_player_id(self.server_id, killer_id)
                if killer:
                    stats["top_killers"].append({
                        "id": killer_id,
                        "name": killer.player_name,
                        "count": count
                    })
        
        # Get recent kills
        kills_collection = await get_collection("kill_events")
        if kills_collection:
            recent_kills = await kills_collection.find({
                "server_id": self.server_id,
                "killer_id": self.player_id
            }).sort("timestamp", -1).limit(5).to_list(length=5)
            
            if recent_kills:
                stats["recent_kills"] = recent_kills
        
        # Get recent deaths
        if kills_collection:
            recent_deaths = await kills_collection.find({
                "server_id": self.server_id,
                "victim_id": self.player_id
            }).sort("timestamp", -1).limit(5).to_list(length=5)
            
            if recent_deaths:
                stats["recent_deaths"] = recent_deaths
        
        return stats
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert player to dictionary
        
        Returns:
            Dict: Player data
        """
        return {
            "id": self.id,
            "server_id": self.server_id,
            "player_id": self.player_id,
            "player_name": self.player_name,
            "faction_id": self.faction_id,
            "kills": self.kills,
            "deaths": self.deaths,
            "kd_ratio": self.kd_ratio,
            "favorite_weapon": self.favorite_weapon,
            "first_seen": self.first_seen.isoformat() if self.first_seen else None,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "is_active": self.is_active
        }