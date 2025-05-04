"""
Player model for the Tower of Temptation PvP Statistics Discord Bot.

This module provides a Player class to interact with player data in MongoDB.
"""
from datetime import datetime
from typing import Dict, List, Optional, Any, Union

class Player:
    """
    Player model
    """
    
    @staticmethod
    async def create(db, server_id: str, player_id: str, name: str) -> Dict[str, Any]:
        """
        Create a new player record
        
        Args:
            db: Database connection
            server_id: Game server ID
            player_id: Player ID in the game
            name: Player name
            
        Returns:
            Dictionary containing the created player data
        """
        player_data = {
            "server_id": server_id,
            "player_id": player_id,
            "name": name,
            "kills": 0,
            "deaths": 0,
            "kd_ratio": 0.0,
            "first_seen": datetime.utcnow(),
            "last_seen": datetime.utcnow(),
            # Rivalry tracking
            "nemesis": None,          # Player killed by most
            "nemesis_name": None,     # Name of nemesis
            "nemesis_kills": 0,       # Times killed by nemesis
            "prey": None,             # Player most killed
            "prey_name": None,        # Name of prey
            "prey_kills": 0,          # Times killed prey
            # Weapon stats
            "favorite_weapon": None,  # Most used weapon
            "weapon_kills": {}        # Kills per weapon
        }
        result = await db.db.players.insert_one(player_data)
        player_data["_id"] = result.inserted_id
        return player_data
    
    @staticmethod
    async def get_by_player_id(db, server_id: str, player_id: str) -> Optional[Dict[str, Any]]:
        """
        Get player by player ID
        
        Args:
            db: Database connection
            server_id: Game server ID
            player_id: Player ID in the game
            
        Returns:
            Player data dictionary or None if not found
        """
        return await db.db.players.find_one({
            "server_id": server_id,
            "player_id": player_id
        })
    
    @staticmethod
    async def update_stats(db, server_id: str, player_id: str, 
                         kills: Optional[int] = None, 
                         deaths: Optional[int] = None) -> bool:
        """
        Update player's kill/death stats
        
        Args:
            db: Database connection
            server_id: Game server ID
            player_id: Player ID in the game
            kills: New kill count (if None, no change)
            deaths: New death count (if None, no change)
            
        Returns:
            True if successful, False otherwise
        """
        update = {"last_seen": datetime.utcnow()}
        
        # Only update fields that are provided
        if kills is not None:
            update["kills"] = kills
        
        if deaths is not None:
            update["deaths"] = deaths
        
        # Calculate K/D ratio
        if kills is not None and deaths is not None:
            # Use at least 1 death to avoid division by zero
            update["kd_ratio"] = kills / max(deaths, 1)
        
        result = await db.db.players.update_one(
            {"server_id": server_id, "player_id": player_id},
            {"$set": update}
        )
        
        return result.modified_count > 0
    
    @staticmethod
    async def update_weapon_stats(db, server_id: str, player_id: str, 
                                weapon: str) -> bool:
        """
        Update player's weapon stats
        
        Args:
            db: Database connection
            server_id: Game server ID
            player_id: Player ID in the game
            weapon: Weapon used for kill
            
        Returns:
            True if successful, False otherwise
        """
        # First, get the player to check current weapon stats
        player = await Player.get_by_player_id(db, server_id, player_id)
        if not player:
            return False
        
        # Update the weapon kills count
        weapon_kills = player.get("weapon_kills", {})
        weapon_kills[weapon] = weapon_kills.get(weapon, 0) + 1
        
        # Determine favorite weapon
        favorite_weapon = max(weapon_kills.items(), key=lambda x: x[1])[0] if weapon_kills else None
        
        result = await db.db.players.update_one(
            {"server_id": server_id, "player_id": player_id},
            {
                "$set": {
                    "weapon_kills": weapon_kills,
                    "favorite_weapon": favorite_weapon
                }
            }
        )
        
        return result.modified_count > 0
    
    @staticmethod
    async def update_rivalry(db, server_id: str, player_id: str,
                           nemesis: Optional[str] = None,
                           nemesis_name: Optional[str] = None,
                           nemesis_kills: Optional[int] = None,
                           prey: Optional[str] = None,
                           prey_name: Optional[str] = None,
                           prey_kills: Optional[int] = None) -> bool:
        """
        Update player's rivalry stats
        
        Args:
            db: Database connection
            server_id: Game server ID
            player_id: Player ID in the game
            nemesis: Player ID of nemesis
            nemesis_name: Name of nemesis
            nemesis_kills: Times killed by nemesis
            prey: Player ID of prey
            prey_name: Name of prey
            prey_kills: Times killed prey
            
        Returns:
            True if successful, False otherwise
        """
        update = {}
        
        if nemesis is not None:
            update["nemesis"] = nemesis
            update["nemesis_name"] = nemesis_name
            update["nemesis_kills"] = nemesis_kills
        
        if prey is not None:
            update["prey"] = prey
            update["prey_name"] = prey_name
            update["prey_kills"] = prey_kills
        
        if not update:
            return False
        
        result = await db.db.players.update_one(
            {"server_id": server_id, "player_id": player_id},
            {"$set": update}
        )
        
        return result.modified_count > 0
    
    @staticmethod
    async def get_top_players(db, server_id: str, sort_by: str = "kills", 
                            limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get top players for a server
        
        Args:
            db: Database connection
            server_id: Game server ID
            sort_by: Field to sort by (kills, kd_ratio)
            limit: Number of players to return
            
        Returns:
            List of player data dictionaries
        """
        sort_field = sort_by
        if sort_by not in ["kills", "deaths", "kd_ratio"]:
            sort_field = "kills"  # Default sort by kills
            
        cursor = db.db.players.find({"server_id": server_id}).sort(sort_field, -1).limit(limit)
        return await cursor.to_list(length=limit)