"""
Player model for the Tower of Temptation PvP Statistics Discord Bot.

This module provides:
1. Player data storage
2. Player statistics tracking
3. Weapon usage analytics
4. Rivalry tracking
"""
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Set, Tuple

from utils.database import get_db
from utils.async_utils import AsyncCache

logger = logging.getLogger(__name__)

class Player:
    """Player model for game statistics"""
    
    # Collection name in database
    COLLECTION_NAME = "players"
    
    # Default values
    DEFAULT_VALUES = {
        "player_name": "Unknown",
        "discord_id": None,
        "kills": 0,
        "deaths": 0,
        "weapons": {},
        "victims": {},
        "killers": {},
        "longest_kill": 0,
        "total_distance": 0,
        "playtime": 0,
        "faction_id": None,
        "last_seen": None,
        "first_seen": None,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    
    def __init__(self, data: Dict[str, Any]):
        """Initialize player from database document
        
        Args:
            data: Document from database
        """
        self._id = data.get("_id")
        self.server_id = data.get("server_id")
        self.player_id = data.get("player_id")
        
        # Apply defaults for missing values
        for key, default in self.DEFAULT_VALUES.items():
            if isinstance(default, dict) and key in data and isinstance(data[key], dict):
                # Merge nested dictionaries
                setattr(self, key, {**default, **data[key]})
            else:
                # Use value from data or default
                setattr(self, key, data.get(key, default))
        
        # Convert datetime strings to datetime objects
        for field in ["created_at", "updated_at", "last_seen", "first_seen"]:
            value = getattr(self, field, None)
            if isinstance(value, str):
                try:
                    setattr(self, field, datetime.fromisoformat(value))
                except (ValueError, TypeError):
                    setattr(self, field, None)
    
    @property
    def id(self) -> str:
        """Get document ID
        
        Returns:
            str: Document ID
        """
        return str(self._id) if self._id else None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage
        
        Returns:
            Dict: Dictionary representation
        """
        # Get all attributes
        result = {
            "server_id": self.server_id,
            "player_id": self.player_id,
        }
        
        # Add all player values
        for key in self.DEFAULT_VALUES.keys():
            value = getattr(self, key, None)
            
            # Convert datetime objects to ISO format strings
            if isinstance(value, datetime):
                value = value.isoformat()
                
            result[key] = value
        
        # Add document ID if available
        if self._id:
            result["_id"] = self._id
            
        return result
    
    async def update(self) -> bool:
        """Update player in database
        
        Returns:
            bool: True if successful
        """
        if not self.server_id or not self.player_id:
            logger.error("Cannot update player: server_id or player_id is missing")
            return False
            
        # Update timestamp
        self.updated_at = datetime.utcnow()
        
        # Convert to dictionary
        data = self.to_dict()
        
        # Get database
        db = await get_db()
        
        # Update document
        if self._id:
            # Update existing document
            result = await db.update_document(
                self.COLLECTION_NAME,
                {"_id": self._id},
                {"$set": data}
            )
        else:
            # Insert new document
            inserted_id = await db.insert_document(self.COLLECTION_NAME, data)
            if inserted_id:
                self._id = inserted_id
                result = True
            else:
                result = False
                
        # Invalidate cache
        if result:
            AsyncCache.invalidate(Player.get_by_player_id, self.server_id, self.player_id)
            AsyncCache.invalidate(Player.get_by_id, self.id)
            
        return result
    
    async def delete(self) -> bool:
        """Delete player from database
        
        Returns:
            bool: True if successful
        """
        if not self._id:
            logger.error("Cannot delete player: _id is missing")
            return False
            
        # Get database
        db = await get_db()
        
        # Delete document
        result = await db.delete_document(self.COLLECTION_NAME, {"_id": self._id})
        
        # Invalidate cache
        if result:
            AsyncCache.invalidate(Player.get_by_player_id, self.server_id, self.player_id)
            AsyncCache.invalidate(Player.get_by_id, self.id)
            
        return result
    
    def get_kd_ratio(self) -> float:
        """Get kill/death ratio
        
        Returns:
            float: Kill/death ratio
        """
        if self.deaths == 0:
            return float(self.kills)
        return self.kills / self.deaths
    
    def get_avg_kill_distance(self) -> float:
        """Get average kill distance
        
        Returns:
            float: Average kill distance
        """
        if self.kills == 0:
            return 0.0
        return self.total_distance / self.kills
    
    def get_favorite_weapon(self) -> Optional[str]:
        """Get favorite weapon
        
        Returns:
            str or None: Favorite weapon or None if no kills
        """
        if not self.weapons:
            return None
            
        # Find weapon with most kills
        return max(self.weapons.items(), key=lambda x: x[1])[0]
    
    def get_nemesis(self) -> Optional[Dict[str, Any]]:
        """Get player who killed this player the most
        
        Returns:
            Dict or None: Nemesis information or None if no deaths
        """
        if not self.killers:
            return None
            
        # Find killer with most kills
        killer_id, kills = max(self.killers.items(), key=lambda x: x[1])
        
        return {
            "player_id": killer_id,
            "kills": kills
        }
    
    def get_favorite_victim(self) -> Optional[Dict[str, Any]]:
        """Get player who this player killed the most
        
        Returns:
            Dict or None: Victim information or None if no kills
        """
        if not self.victims:
            return None
            
        # Find victim with most deaths
        victim_id, kills = max(self.victims.items(), key=lambda x: x[1])
        
        return {
            "player_id": victim_id,
            "kills": kills
        }
    
    def get_weapon_stats(self) -> List[Dict[str, Any]]:
        """Get weapon usage statistics
        
        Returns:
            List[Dict]: Weapon statistics
        """
        if not self.weapons:
            return []
            
        # Sort weapons by kills (descending)
        sorted_weapons = sorted(self.weapons.items(), key=lambda x: x[1], reverse=True)
        
        # Calculate total kills
        total_kills = sum(self.weapons.values())
        
        # Create weapon stats
        weapon_stats = []
        for weapon, kills in sorted_weapons:
            weapon_stats.append({
                "weapon": weapon,
                "kills": kills,
                "percentage": (kills / total_kills) * 100
            })
            
        return weapon_stats
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get player statistics
        
        Returns:
            Dict: Player statistics
        """
        # Calculate derived statistics
        kd_ratio = self.get_kd_ratio()
        avg_kill_distance = self.get_avg_kill_distance()
        favorite_weapon = self.get_favorite_weapon()
        nemesis = self.get_nemesis()
        favorite_victim = self.get_favorite_victim()
        weapon_stats = self.get_weapon_stats()
        
        # Create statistics dictionary
        return {
            "player_id": self.player_id,
            "player_name": self.player_name,
            "discord_id": self.discord_id,
            "faction_id": self.faction_id,
            "kills": self.kills,
            "deaths": self.deaths,
            "kd_ratio": kd_ratio,
            "longest_kill": self.longest_kill,
            "avg_kill_distance": avg_kill_distance,
            "playtime": self.playtime,
            "favorite_weapon": favorite_weapon,
            "nemesis": nemesis,
            "favorite_victim": favorite_victim,
            "weapon_stats": weapon_stats,
            "last_seen": self.last_seen,
            "first_seen": self.first_seen
        }
    
    def update_statistics(self, kill_events: List[Dict[str, Any]]) -> None:
        """Update player statistics from kill events
        
        Args:
            kill_events: List of kill events
        """
        # Process kill events
        for event in kill_events:
            killer_id = event.get("killer_id")
            victim_id = event.get("victim_id")
            
            # Skip invalid events
            if not killer_id or not victim_id:
                continue
                
            # Update based on player role in event
            if killer_id == self.player_id:
                # Player is killer
                self.kills += 1
                
                # Update weapon stats
                weapon = event.get("weapon", "Unknown")
                self.weapons[weapon] = self.weapons.get(weapon, 0) + 1
                
                # Update victim stats
                self.victims[victim_id] = self.victims.get(victim_id, 0) + 1
                
                # Update distance stats
                distance = float(event.get("distance", 0))
                self.total_distance += distance
                self.longest_kill = max(self.longest_kill, distance)
                
            elif victim_id == self.player_id:
                # Player is victim
                self.deaths += 1
                
                # Update killer stats
                self.killers[killer_id] = self.killers.get(killer_id, 0) + 1
            
            # Update timestamps
            timestamp = event.get("timestamp", datetime.now())
            if isinstance(timestamp, str):
                try:
                    timestamp = datetime.fromisoformat(timestamp)
                except (ValueError, TypeError):
                    timestamp = datetime.now()
            
            # Update first/last seen
            if self.first_seen is None or timestamp < self.first_seen:
                self.first_seen = timestamp
                
            if self.last_seen is None or timestamp > self.last_seen:
                self.last_seen = timestamp
    
    @staticmethod
    async def ensure_indexes() -> bool:
        """Create database indexes
        
        Returns:
            bool: True if successful
        """
        # Get database
        db = await get_db()
        
        # Create compound index on server_id and player_id
        result1 = await db.create_index(
            Player.COLLECTION_NAME,
            [("server_id", 1), ("player_id", 1)],
            unique=True,
            name="server_player_unique"
        )
        
        # Create index on discord_id
        result2 = await db.create_index(
            Player.COLLECTION_NAME,
            [("discord_id", 1)],
            name="discord_id"
        )
        
        # Create index on faction_id
        result3 = await db.create_index(
            Player.COLLECTION_NAME,
            [("faction_id", 1)],
            name="faction_id"
        )
        
        # Create index on last_seen
        result4 = await db.create_index(
            Player.COLLECTION_NAME,
            [("last_seen", -1)],
            name="last_seen_desc"
        )
        
        return bool(result1 and result2 and result3 and result4)
    
    @classmethod
    @AsyncCache.cached(ttl=300)
    async def get_by_id(cls, id: str) -> Optional["Player"]:
        """Get player by document ID
        
        Args:
            id: Document ID
            
        Returns:
            Player or None: Player or None if not found
        """
        # Get database
        db = await get_db()
        
        # Get document
        document = await db.get_document(cls.COLLECTION_NAME, {"_id": id})
        
        if document:
            return cls(document)
            
        return None
    
    @classmethod
    @AsyncCache.cached(ttl=300)
    async def get_by_player_id(cls, server_id: str, player_id: str) -> Optional["Player"]:
        """Get player by server ID and player ID
        
        Args:
            server_id: Server ID
            player_id: Player ID
            
        Returns:
            Player or None: Player or None if not found
        """
        # Get database
        db = await get_db()
        
        # Get document
        document = await db.get_document(
            cls.COLLECTION_NAME,
            {"server_id": server_id, "player_id": player_id}
        )
        
        if document:
            return cls(document)
            
        return None
    
    @classmethod
    async def get_by_discord_id(cls, server_id: str, discord_id: Union[str, int]) -> Optional["Player"]:
        """Get player by Discord ID
        
        Args:
            server_id: Server ID
            discord_id: Discord user ID
            
        Returns:
            Player or None: Player or None if not found
        """
        # Convert discord_id to string if it's an integer
        if isinstance(discord_id, int):
            discord_id = str(discord_id)
            
        # Get database
        db = await get_db()
        
        # Get document
        document = await db.get_document(
            cls.COLLECTION_NAME,
            {"server_id": server_id, "discord_id": discord_id}
        )
        
        if document:
            return cls(document)
            
        return None
    
    @classmethod
    async def create(cls, server_id: str, player_id: str, player_name: str) -> Optional["Player"]:
        """Create new player
        
        Args:
            server_id: Server ID
            player_id: Player ID
            player_name: Player name
            
        Returns:
            Player or None: Created player or None if error
        """
        # Get database
        db = await get_db()
        
        # Check if player already exists
        existing = await db.get_document(
            cls.COLLECTION_NAME,
            {"server_id": server_id, "player_id": player_id}
        )
        
        if existing:
            logger.warning(f"Player already exists for server {server_id}, player {player_id}")
            return cls(existing)
            
        # Create new document
        now = datetime.utcnow()
        document = {
            "server_id": server_id,
            "player_id": player_id,
            "player_name": player_name,
            "created_at": now,
            "updated_at": now
        }
        
        # Insert document
        inserted_id = await db.insert_document(cls.COLLECTION_NAME, document)
        
        if not inserted_id:
            logger.error(f"Failed to create player for server {server_id}, player {player_id}")
            return None
            
        # Get created document
        created = await db.get_document(cls.COLLECTION_NAME, {"_id": inserted_id})
        
        if created:
            return cls(created)
            
        return None
    
    @classmethod
    async def get_all(cls, server_id: str, limit: Optional[int] = None, skip: Optional[int] = None) -> List["Player"]:
        """Get all players for server
        
        Args:
            server_id: Server ID
            limit: Maximum number of players to return (default: None)
            skip: Number of players to skip (default: None)
            
        Returns:
            List[Player]: List of players
        """
        # Get database
        db = await get_db()
        
        # Get all documents
        documents = await db.get_documents(
            cls.COLLECTION_NAME,
            {"server_id": server_id},
            sort=[("last_seen", -1)],
            limit=limit,
            skip=skip
        )
        
        return [cls(doc) for doc in documents]
    
    @classmethod
    async def get_by_faction(cls, server_id: str, faction_id: str) -> List["Player"]:
        """Get players by faction
        
        Args:
            server_id: Server ID
            faction_id: Faction ID
            
        Returns:
            List[Player]: List of players in faction
        """
        # Get database
        db = await get_db()
        
        # Get documents
        documents = await db.get_documents(
            cls.COLLECTION_NAME,
            {"server_id": server_id, "faction_id": faction_id},
            sort=[("kills", -1)]
        )
        
        return [cls(doc) for doc in documents]
    
    @classmethod
    async def search_by_name(cls, server_id: str, name_query: str, limit: int = 10) -> List["Player"]:
        """Search players by name
        
        Args:
            server_id: Server ID
            name_query: Name query string
            limit: Maximum number of results (default: 10)
            
        Returns:
            List[Player]: List of matching players
        """
        # Get database
        db = await get_db()
        
        # Create regex query (case insensitive)
        name_regex = f".*{re.escape(name_query)}.*"
        
        # Get documents
        documents = await db.get_documents(
            cls.COLLECTION_NAME,
            {
                "server_id": server_id,
                "player_name": {"$regex": name_regex, "$options": "i"}
            },
            sort=[("last_seen", -1)],
            limit=limit
        )
        
        return [cls(doc) for doc in documents]
    
    @classmethod
    async def get_top_players(cls, server_id: str, stat: str = "kills", limit: int = 10) -> List["Player"]:
        """Get top players by statistic
        
        Args:
            server_id: Server ID
            stat: Statistic field to sort by (default: "kills")
            limit: Maximum number of players (default: 10)
            
        Returns:
            List[Player]: List of top players
        """
        # Get database
        db = await get_db()
        
        # Valid sort fields
        valid_fields = ["kills", "deaths", "longest_kill", "playtime"]
        if stat not in valid_fields:
            stat = "kills"
            
        # Get documents
        documents = await db.get_documents(
            cls.COLLECTION_NAME,
            {"server_id": server_id},
            sort=[(stat, -1)],
            limit=limit
        )
        
        return [cls(doc) for doc in documents]
    
    @classmethod
    async def count_players(cls, server_id: str) -> int:
        """Count players for server
        
        Args:
            server_id: Server ID
            
        Returns:
            int: Number of players
        """
        # Get database
        db = await get_db()
        
        # Count documents
        return await db.count_documents(
            cls.COLLECTION_NAME,
            {"server_id": server_id}
        )
    
    @classmethod
    async def link_discord_account(cls, server_id: str, player_id: str, discord_id: Union[str, int]) -> bool:
        """Link player to Discord account
        
        Args:
            server_id: Server ID
            player_id: Player ID
            discord_id: Discord user ID
            
        Returns:
            bool: True if linked successfully
        """
        # Convert discord_id to string if it's an integer
        if isinstance(discord_id, int):
            discord_id = str(discord_id)
            
        # Get player
        player = await cls.get_by_player_id(server_id, player_id)
        if not player:
            logger.error(f"Player not found: server_id={server_id}, player_id={player_id}")
            return False
            
        # Update Discord ID
        player.discord_id = discord_id
        return await player.update()
    
    @classmethod
    async def set_faction(cls, server_id: str, player_id: str, faction_id: Optional[str]) -> bool:
        """Set player faction
        
        Args:
            server_id: Server ID
            player_id: Player ID
            faction_id: Faction ID or None to remove
            
        Returns:
            bool: True if updated successfully
        """
        # Get player
        player = await cls.get_by_player_id(server_id, player_id)
        if not player:
            logger.error(f"Player not found: server_id={server_id}, player_id={player_id}")
            return False
            
        # Update faction ID
        player.faction_id = faction_id
        return await player.update()
    
    @classmethod
    async def update_player_name(cls, server_id: str, player_id: str, player_name: str) -> bool:
        """Update player name
        
        Args:
            server_id: Server ID
            player_id: Player ID
            player_name: New player name
            
        Returns:
            bool: True if updated successfully
        """
        # Get player
        player = await cls.get_by_player_id(server_id, player_id)
        if not player:
            logger.error(f"Player not found: server_id={server_id}, player_id={player_id}")
            return False
            
        # Update player name
        player.player_name = player_name
        return await player.update()