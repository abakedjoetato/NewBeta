"""
Test script to verify that new features (factions, rivalries, player linking) are integrated properly
"""
import asyncio
import importlib
import sys
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_player_model():
    """Test that the player model supports faction and discord linking"""
    from models.player import Player
    
    # Create mock database and player data
    class MockDB:
        async def update_one(self, query, update):
            return type('obj', (object,), {'modified_count': 1})
        
        async def find_one(self, query):
            return None
    
    mock_db = MockDB()
    mock_db.players = mock_db
    
    player_data = {
        "player_id": "test123",
        "player_name": "TestPlayer",
        "server_id": "server456",
        "kills": 10,
        "deaths": 5,
        "faction_id": None,
        "discord_id": None
    }
    
    # Create player instance
    player = Player(mock_db, player_data)
    
    # Test faction integration
    logger.info("Testing faction integration...")
    await player.set_faction("faction789")
    if player.faction_id == "faction789":
        logger.info("✅ Faction integration working")
    else:
        logger.error(f"❌ Faction integration failed, faction_id={player.faction_id}")
    
    # Test player linking
    logger.info("Testing player linking...")
    await player.set_discord_id("discord123")
    if player.discord_id == "discord123":
        logger.info("✅ Player linking working")
    else:
        logger.error(f"❌ Player linking failed, discord_id={player.discord_id}")
    
    return player.faction_id == "faction789" and player.discord_id == "discord123"

async def test_cog_imports():
    """Test that the new cogs can be imported"""
    logger.info("Testing cog imports...")
    
    try:
        # Import factions cog
        import cogs.factions
        logger.info("✅ Factions cog imported successfully")
        factions_success = True
    except ImportError as e:
        logger.error(f"❌ Failed to import factions cog: {e}")
        factions_success = False
    
    try:
        # Import rivalries cog
        import cogs.rivalries
        logger.info("✅ Rivalries cog imported successfully")
        rivalries_success = True
    except ImportError as e:
        logger.error(f"❌ Failed to import rivalries cog: {e}")
        rivalries_success = False
    
    try:
        # Import player_links cog
        import cogs.player_links
        logger.info("✅ Player links cog imported successfully")
        player_links_success = True
    except ImportError as e:
        logger.error(f"❌ Failed to import player_links cog: {e}")
        player_links_success = False
    
    return factions_success and rivalries_success and player_links_success

async def main():
    """Run all tests"""
    logger.info("Testing new features integration...")
    
    player_model_ok = await test_player_model()
    cog_imports_ok = await test_cog_imports()
    
    if player_model_ok and cog_imports_ok:
        logger.info("✅ All tests passed! New features are properly integrated")
        return 0
    else:
        logger.error("❌ Some tests failed. New features may not be properly integrated")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)