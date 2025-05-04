"""
Simple test script for the rivalry tracker functionality with manual data
"""
import asyncio
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def update_player_rivalries(players):
    """
    Update prey and nemesis data for players
    A simplified version of RivalryTracker.update_player_rivalries for testing
    
    Args:
        players: List of player data
    """
    logger.info(f"Updating rivalries for {len(players)} players")
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
        
        # Add rivalries to player data
        player["rivalries"] = rivalries
        update_count += 1
    
    logger.info(f"Updated rivalries for {update_count} players")
    return True

async def main():
    """Test rivalry tracker functionality with manual data"""
    logger.info("Testing rivalry tracker with manual data...")
    
    # Test data
    test_players = [
        {
            "player_id": "player1",
            "player_name": "TestPlayer1",
            "server_id": "server1",
            "active": True,
            "victims": {
                "player2": {"name": "TestPlayer2", "count": 5},
                "player3": {"name": "TestPlayer3", "count": 2}
            },
            "killers": {
                "player4": {"name": "TestPlayer4", "count": 3},
                "player5": {"name": "TestPlayer5", "count": 7}
            }
        },
        {
            "player_id": "player2",
            "player_name": "TestPlayer2",
            "server_id": "server1",
            "active": True,
            "victims": {
                "player1": {"name": "TestPlayer1", "count": 4},
                "player5": {"name": "TestPlayer5", "count": 1}
            },
            "killers": {
                "player1": {"name": "TestPlayer1", "count": 5},
                "player3": {"name": "TestPlayer3", "count": 2}
            }
        }
    ]
    
    # Run rivalry update on test data
    start_time = datetime.now()
    success = await update_player_rivalries(test_players)
    end_time = datetime.now()
    
    if success:
        logger.info(f"Successfully updated rivalries")
        logger.info(f"Time taken: {(end_time - start_time).total_seconds():.2f} seconds")
        
        # Check player data
        for player in test_players:
            if "rivalries" in player:
                player_name = player.get("player_name", "Unknown")
                rivalries = player.get("rivalries", {})
                
                logger.info(f"\nPlayer: {player_name}")
                logger.info(f"Rivalries data: {rivalries}")
                
                prey = rivalries.get("prey")
                nemesis = rivalries.get("nemesis")
                last_updated = rivalries.get("last_updated")
                
                if prey:
                    prey_kills = prey.get('kill_count', 0)
                    prey_deaths = max(prey.get('death_count', 0), 1)  # Treat 0 as 1 for KDR calculation
                    prey_kd = round(prey_kills / prey_deaths, 2)
                    logger.info(f"Prey: {prey.get('player_name')}  {prey_kills} Kills  {prey_kd} KD")
                else:
                    logger.info("No prey found")
                    
                if nemesis:
                    nemesis_deaths = nemesis.get('kill_count', 0)  # Their kills = player's deaths
                    nemesis_kills = nemesis.get('death_count', 0)  # Their deaths = player's kills
                    nemesis_kd = round(nemesis_kills / max(nemesis_deaths, 1), 2)
                    logger.info(f"Nemesis: {nemesis.get('player_name')}  {nemesis_deaths} Deaths  {nemesis_kd} KD")
                else:
                    logger.info("No nemesis found")
                    
                if last_updated:
                    logger.info(f"Last updated: {last_updated}")
    else:
        logger.error("Failed to update rivalries")

if __name__ == "__main__":
    asyncio.run(main())