"""
Rivalry Tracker Utility

This module handles the hourly updating of player rivalries (Prey/Nemesis relationships).
It calculates which player a given player has killed the most (their Prey),
and which player has killed them the most (their Nemesis).
"""
import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

class RivalryTracker:
    """Utility for tracking player rivalries (Prey/Nemesis relationships)"""

    @staticmethod
    async def update_player_rivalries(db, server_id: str) -> bool:
        """
        Update prey and nemesis data for all players on a server
        This is called hourly to save resources
        
        Args:
            db: Database connection
            server_id: The server ID to update rivalries for
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Get all active players for the server
            cursor = db.players.find({
                "server_id": server_id,
                "active": True
            })
            
            players = await cursor.to_list(length=None)
            if not players:
                logger.warning(f"No active players found for server {server_id}")
                return False
                
            logger.info(f"Updating rivalries for {len(players)} players on server {server_id}")
            update_count = 0
            
            # Process each player
            for player in players:
                player_id = player.get("player_id")
                
                # Skip if missing key data
                if not player_id:
                    continue
                    
                # Get kills data (for prey calculation)
                if not player.get("victims") or not isinstance(player.get("victims"), dict):
                    continue
                    
                victims = player.get("victims", {})
                
                # Find the player's prey (player they've killed the most)
                prey = None
                prey_count = 0
                
                for victim_id, data in victims.items():
                    count = data.get("count", 0)
                    if count > prey_count and count >= 3:  # Minimum 3 kills to be considered prey
                        # Get death count from this player (for KD calculation)
                        death_count = 0
                        if killers := player.get("killers"):
                            if victim_data := killers.get(victim_id):
                                death_count = victim_data.get("count", 0)
                                
                        prey = {
                            "player_id": victim_id,
                            "player_name": data.get("name", "Unknown"),
                            "kill_count": count,
                            "death_count": death_count
                        }
                        prey_count = count
                
                # Get deaths data (for nemesis calculation)  
                if not player.get("killers") or not isinstance(player.get("killers"), dict):
                    continue
                    
                killers = player.get("killers", {})
                
                # Find the player's nemesis (player who killed them the most)
                nemesis = None
                nemesis_count = 0
                
                for killer_id, data in killers.items():
                    count = data.get("count", 0)
                    if count > nemesis_count and count >= 3:  # Minimum 3 kills to be considered nemesis
                        # Get kill count against this player (for KD calculation)
                        kill_count = 0
                        if victims := player.get("victims"):
                            if killer_data := victims.get(killer_id):
                                kill_count = killer_data.get("count", 0)
                                
                        nemesis = {
                            "player_id": killer_id,
                            "player_name": data.get("name", "Unknown"),
                            "kill_count": count,
                            "death_count": kill_count
                        }
                        nemesis_count = count
                
                # Update player with rivalry data
                rivalries = {
                    "prey": prey,
                    "nemesis": nemesis,
                    "last_updated": datetime.utcnow().isoformat()
                }
                
                # Update the database
                result = await db.players.update_one(
                    {
                        "player_id": player_id,
                        "server_id": server_id
                    }, 
                    {
                        "$set": {
                            "rivalries": rivalries
                        }
                    }
                )
                
                if result.modified_count > 0:
                    update_count += 1
            
            logger.info(f"Updated rivalries for {update_count} players on server {server_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating player rivalries: {e}", exc_info=True)
            return False

    @staticmethod
    async def schedule_rivalry_updates(bot):
        """
        Schedule hourly rivalry updates for all servers
        
        Args:
            bot: The Discord bot instance
        """
        while True:
            try:
                # Get all server IDs from the database
                cursor = bot.db.servers.find({})
                servers = await cursor.to_list(length=None)
                
                for server in servers:
                    server_id = server.get("server_id")
                    if server_id:
                        logger.info(f"Running scheduled rivalry update for server {server_id}")
                        await RivalryTracker.update_player_rivalries(bot.db, server_id)
                
                # Log completion of update cycle
                logger.info(f"Completed rivalry update cycle for {len(servers)} servers")
                
            except Exception as e:
                logger.error(f"Error in rivalry update schedule: {e}", exc_info=True)
            
            # Wait for one hour before the next update
            await asyncio.sleep(3600)  # 3600 seconds = 1 hour