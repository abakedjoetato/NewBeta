"""
Test script for the Bounty System in Tower of Temptation PvP Statistics Discord Bot.

This script:
1. Sets up the bounty collection in MongoDB
2. Creates a test bounty
3. Retrieves and displays active bounties
"""
import asyncio
import logging
from datetime import datetime, timedelta

from models.bounty import Bounty
from models.player import Player
from models.economy import Economy
from utils.database import get_db, initialize_db
from setup_bounty_collection import main as setup_bounty_collection

# Configure logging
logging.basicConfig(level=logging.INFO, 
                  format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def create_test_bounty():
    """Create a test bounty in the database"""
    logger.info("Creating test bounty...")
    
    # Guild and server IDs
    guild_id = "123456789"  # Test guild ID
    server_id = "test_server_1"  # Test server ID
    
    # Target player info
    target_id = "player123"
    target_name = "TestTarget"
    
    # Placer info
    placed_by = "discord_user_456"
    placed_by_name = "TestPlacer"
    
    # Create the bounty
    bounty = await Bounty.create(
        guild_id=guild_id,
        server_id=server_id,
        target_id=target_id,
        target_name=target_name,
        placed_by=placed_by,
        placed_by_name=placed_by_name,
        reason="Testing the bounty system",
        reward=100,
        source=Bounty.SOURCE_PLAYER,
        lifespan_hours=1.0
    )
    
    logger.info(f"Created test bounty with ID: {bounty.id}")
    return bounty

async def get_test_bounties():
    """Retrieve and display active bounties"""
    logger.info("Retrieving active bounties...")
    
    # Guild and server IDs
    guild_id = "123456789"  # Test guild ID
    server_id = "test_server_1"  # Test server ID
    
    # Get active bounties
    bounties = await Bounty.get_active_bounties(guild_id, server_id)
    
    # Display bounties
    logger.info(f"Found {len(bounties)} active bounties:")
    for i, bounty in enumerate(bounties):
        logger.info(f"Bounty {i+1}:")
        logger.info(f"  Target: {bounty.target_name} ({bounty.target_id})")
        logger.info(f"  Reward: {bounty.reward} coins")
        logger.info(f"  Reason: {bounty.reason}")
        logger.info(f"  Placed by: {bounty.placed_by_name}")
        
        # Calculate time remaining
        now = datetime.utcnow()
        if bounty.expires_at and bounty.expires_at > now:
            time_remaining = bounty.expires_at - now
            minutes = time_remaining.seconds // 60
            logger.info(f"  Expires in: {minutes} minutes")
        else:
            logger.info("  Expired")
    
    return bounties

async def test_claim_bounty(bounty):
    """Test claiming a bounty"""
    logger.info("Testing bounty claim...")
    
    # Claimer info
    claimed_by = "discord_user_789"
    claimed_by_name = "TestClaimer"
    
    # Claim the bounty
    claimed = await bounty.claim(claimed_by, claimed_by_name)
    
    if claimed:
        logger.info(f"Successfully claimed bounty! Reward: {bounty.reward} coins")
    else:
        logger.info("Failed to claim bounty")

async def main():
    """Main test function"""
    logger.info("Starting bounty system test...")
    
    # Initialize the database connection with explicit db_name
    await initialize_db(db_name="pvp_stats_bot")
    
    # Setup the bounty collection
    logger.info("Setting up bounty collection...")
    await setup_bounty_collection()
    
    # Create a test bounty
    bounty = await create_test_bounty()
    
    # Retrieve active bounties
    bounties = await get_test_bounties()
    
    # Test claiming a bounty
    if bounties:
        await test_claim_bounty(bounties[0])
    
    logger.info("Bounty system test completed!")

if __name__ == "__main__":
    asyncio.run(main())