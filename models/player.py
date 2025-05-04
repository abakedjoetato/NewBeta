"""
Player model for Tower of Temptation PvP Statistics Bot

This module defines the Player data structure for game players.
"""
import logging
from datetime import datetime
from typing import Dict, Any, Optional, ClassVar, List

from models.base_model import BaseModel

logger = logging.getLogger(__name__)

class Player(BaseModel):
    """Game player data"""
    collection_name: ClassVar[str] = "players"
    
    def __init__(
        self,
        player_id: Optional[str] = None,
        server_id: Optional[str] = None,
        name: Optional[str] = None,
        kills: int = 0,
        deaths: int = 0,
        suicides: int = 0,
        display_name: Optional[str] = None,
        last_seen: Optional[datetime] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
        **kwargs
    ):
        self._id = None
        self.player_id = player_id
        self.server_id = server_id
        self.name = name
        self.kills = kills
        self.deaths = deaths
        self.suicides = suicides
        self.display_name = display_name or name
        self.last_seen = last_seen
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()
        
        # Optional player metadata
        self.faction = kwargs.get("faction")
        self.rank = kwargs.get("rank")
        self.score = kwargs.get("score", 0)
        self.longest_kill_distance = kwargs.get("longest_kill_distance", 0)
        self.total_kill_distance = kwargs.get("total_kill_distance", 0)
        self.favorite_weapon = kwargs.get("favorite_weapon")
        self.nemesis_id = kwargs.get("nemesis_id")
        self.nemesis_name = kwargs.get("nemesis_name")
        self.prey_id = kwargs.get("prey_id")
        self.prey_name = kwargs.get("prey_name")
        
        # Add any additional player attributes
        for key, value in kwargs.items():
            if not hasattr(self, key):
                setattr(self, key, value)
    
    @classmethod
    async def get_by_player_id(cls, db, player_id: str) -> Optional['Player']:
        """Get a player by player_id
        
        Args:
            db: Database connection
            player_id: Player ID
            
        Returns:
            Player object or None if not found
        """
        document = await db.players.find_one({"player_id": player_id})
        return cls.from_document(document) if document else None
    
    @classmethod
    async def get_by_name(cls, db, name: str, server_id: Optional[str] = None) -> Optional['Player']:
        """Get a player by name
        
        Args:
            db: Database connection
            name: Player name
            server_id: Optional server ID to filter by
            
        Returns:
            Player object or None if not found
        """
        query = {"name": name}
        if server_id:
            query["server_id"] = server_id
            
        document = await db.players.find_one(query)
        return cls.from_document(document) if document else None
    
    @classmethod
    async def get_players_for_server(cls, db, server_id: str) -> List['Player']:
        """Get all players for a server
        
        Args:
            db: Database connection
            server_id: Server ID
            
        Returns:
            List of Player objects
        """
        cursor = db.players.find({"server_id": server_id})
        
        players = []
        async for document in cursor:
            players.append(cls.from_document(document))
            
        return players
    
    @classmethod
    async def get_top_players(cls, db, server_id: str, sort_by: str = "kills", limit: int = 10) -> List['Player']:
        """Get top players for a server
        
        Args:
            db: Database connection
            server_id: Server ID
            sort_by: Field to sort by (kills, deaths, kd)
            limit: Number of players to return
            
        Returns:
            List of Player objects
        """
        sort_field = sort_by
        if sort_by == "kd":
            # For K/D ratio, we sort by kills and handle the ratio in Python
            sort_field = "kills"
            
        cursor = db.players.find({"server_id": server_id}).sort(sort_field, -1).limit(limit)
        
        players = []
        async for document in cursor:
            players.append(cls.from_document(document))
            
        if sort_by == "kd":
            # Sort by K/D ratio after fetching
            players.sort(key=lambda p: p.kills / max(p.deaths, 1), reverse=True)
            
        return players
    
    async def update_stats(
        self, 
        db, 
        kills: Optional[int] = None,
        deaths: Optional[int] = None,
        suicides: Optional[int] = None
    ) -> bool:
        """Update player statistics
        
        Args:
            db: Database connection
            kills: Number of kills to add
            deaths: Number of deaths to add
            suicides: Number of suicides to add
            
        Returns:
            True if updated successfully, False otherwise
        """
        update_dict = {"updated_at": datetime.utcnow()}
        
        if kills is not None:
            self.kills += kills
            update_dict["kills"] = self.kills
        
        if deaths is not None:
            self.deaths += deaths
            update_dict["deaths"] = self.deaths
        
        if suicides is not None:
            self.suicides += suicides
            update_dict["suicides"] = self.suicides
        
        self.updated_at = update_dict["updated_at"]
        
        # Update in database
        result = await db.players.update_one(
            {"player_id": self.player_id},
            {"$set": update_dict}
        )
        
        return result.modified_count > 0
    
    async def update_rivalries(
        self, 
        db, 
        nemesis_id: Optional[str] = None,
        nemesis_name: Optional[str] = None,
        prey_id: Optional[str] = None,
        prey_name: Optional[str] = None
    ) -> bool:
        """Update player rivalries
        
        Args:
            db: Database connection
            nemesis_id: Player ID of nemesis (player killed by most)
            nemesis_name: Name of nemesis
            prey_id: Player ID of prey (player killed most)
            prey_name: Name of prey
            
        Returns:
            True if updated successfully, False otherwise
        """
        update_dict = {"updated_at": datetime.utcnow()}
        
        if nemesis_id is not None:
            self.nemesis_id = nemesis_id
            update_dict["nemesis_id"] = nemesis_id
        
        if nemesis_name is not None:
            self.nemesis_name = nemesis_name
            update_dict["nemesis_name"] = nemesis_name
        
        if prey_id is not None:
            self.prey_id = prey_id
            update_dict["prey_id"] = prey_id
        
        if prey_name is not None:
            self.prey_name = prey_name
            update_dict["prey_name"] = prey_name
        
        self.updated_at = update_dict["updated_at"]
        
        # Update in database
        result = await db.players.update_one(
            {"player_id": self.player_id},
            {"$set": update_dict}
        )
        
        return result.modified_count > 0
    
    async def update_last_seen(self, db, last_seen: datetime) -> bool:
        """Update player's last seen timestamp
        
        Args:
            db: Database connection
            last_seen: Last seen timestamp
            
        Returns:
            True if updated successfully, False otherwise
        """
        self.last_seen = last_seen
        self.updated_at = datetime.utcnow()
        
        # Update in database
        result = await db.players.update_one(
            {"player_id": self.player_id},
            {"$set": {
                "last_seen": self.last_seen,
                "updated_at": self.updated_at
            }}
        )
        
        return result.modified_count > 0
    
    @property
    def kd_ratio(self) -> float:
        """Calculate K/D ratio
        
        Returns:
            K/D ratio (kills / deaths, with deaths=1 if deaths=0)
        """
        if self.deaths == 0:
            return self.kills
        return self.kills / self.deaths