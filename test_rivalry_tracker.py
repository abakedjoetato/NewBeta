"""
Test script for the rivalry tracker functionality with mock data
"""
import asyncio
import logging
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock
from utils.rivalry_tracker import RivalryTracker

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MockCursor:
    """Mock database cursor with to_list method"""
    def __init__(self, items):
        self.items = items
        
    async def to_list(self, length=None):
        return self.items

class MockResult:
    """Mock update result"""
    def __init__(self, modified_count=0):
        self.modified_count = modified_count

class MockDB:
    """Mock database for testing"""
    def __init__(self):
        # Test data
        self.test_players = [
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
        
        # Create players collection as a simple object
        self.players = self

    async def find(self, query=None):
        """Mock find method that returns a cursor"""
        if not query:
            return MockCursor(self.test_players)
            
        filtered_players = []
        for player in self.test_players:
            match = True
            for key, value in query.items():
                if key not in player or player[key] != value:
                    match = False
                    break
            if match:
                filtered_players.append(player)
                
        return MockCursor(filtered_players)
            
    async def find_one(self, query):
        """Mock find_one method"""
        for player in self.test_players:
            match = True
            for key, value in query.items():
                if key not in player:
                    match = False
                    break
                if key == "rivalries" and "$exists" in value:
                    # Special handling for rivalries.$exists
                    has_rivalries = "rivalries" in player
                    if has_rivalries != value["$exists"]:
                        match = False
                        break
                elif player[key] != value:
                    match = False
                    break
            
            if match:
                return player
                
        return None
        
    async def update_one(self, filter_dict, update_dict):
        """Mock update_one method"""
        result = MockResult()
        
        for player in self.test_players:
            if all(player.get(key) == value for key, value in filter_dict.items()):
                # Process $set operation
                if "$set" in update_dict:
                    for key, value in update_dict["$set"].items():
                        player[key] = value
                    result.modified_count = 1
                break
                    
        return result

async def main():
    """Test rivalry tracker functionality with mock data"""
    logger.info("Testing rivalry tracker with mock data...")
    
    # Create mock database
    db = MockDB()
    server_id = "server1"
    
    logger.info(f"Testing rivalry tracker for server {server_id}")
    
    # Run rivalry update
    start_time = datetime.now()
    success = await RivalryTracker.update_player_rivalries(db, server_id)
    end_time = datetime.now()
    
    if success:
        logger.info(f"Successfully updated rivalries for server {server_id}")
        logger.info(f"Time taken: {(end_time - start_time).total_seconds():.2f} seconds")
        
        # Check player data
        for player in db.test_players:
            if "rivalries" in player:
                player_name = player.get("player_name", "Unknown")
                rivalries = player.get("rivalries", {})
                
                logger.info(f"\nPlayer: {player_name}")
                logger.info(f"Rivalries data: {rivalries}")
                
                prey = rivalries.get("prey")
                nemesis = rivalries.get("nemesis")
                last_updated = rivalries.get("last_updated")
                
                if prey:
                    logger.info(f"Prey: {prey.get('player_name')} ({prey.get('kill_count')} kills)")
                else:
                    logger.info("No prey found")
                    
                if nemesis:
                    logger.info(f"Nemesis: {nemesis.get('player_name')} ({nemesis.get('kill_count')} kills)")
                else:
                    logger.info("No nemesis found")
                    
                if last_updated:
                    logger.info(f"Last updated: {last_updated}")
    else:
        logger.error("Failed to update rivalries")

if __name__ == "__main__":
    asyncio.run(main())