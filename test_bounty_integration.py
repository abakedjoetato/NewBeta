"""
Integration test for the Tower of Temptation PvP Statistics Discord Bot bounty system.

This script tests:
1. Creating and retrieving bounties
2. Checking active bounties
3. Claiming bounties
4. Auto-bounty generation
5. Bounty lifecycle (creation, claim, expiration)
6. Economy integration with bounties
7. Bounty settings management

Run with: python test_bounty_integration.py
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union

from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file

# Ensure MongoDB environment variables are set
if not os.getenv("MONGODB_DB"):
    os.environ["MONGODB_DB"] = "tower_of_temptation"

# Make sure MongoDB URI is set
if not os.getenv("MONGODB_URI"):
    mongo_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    os.environ["MONGODB_URI"] = mongo_uri

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import models and utility functions
from models.bounty import Bounty
from models.economy import Economy
from models.guild import Guild
from models.player import Player
from models.player_link import PlayerLink
from utils.database import get_db

# Test Data
TEST_GUILD_ID = os.getenv("HOME_GUILD_ID", "123456789")  # Use real guild ID from env vars
TEST_SERVER_ID = "test-server-1"
TEST_SERVER_NAME = "Test Server 1"

TEST_DISCORD_ID_1 = "111222333444555666"  # Discord ID of the bounty placer
TEST_DISCORD_NAME_1 = "TestUser1"

TEST_DISCORD_ID_2 = "222333444555666777"  # Discord ID of the bounty claimer
TEST_DISCORD_NAME_2 = "TestUser2"

TEST_PLAYER_ID_1 = "player-1"  # Player ID of the victim/target
TEST_PLAYER_NAME_1 = "TargetPlayer"

TEST_PLAYER_ID_2 = "player-2"  # Player ID of the killer/claimer
TEST_PLAYER_NAME_2 = "KillerPlayer"

# Test constants
INITIAL_BALANCE = 1000  # Initial balance for test users
BOUNTY_AMOUNT = 100  # Amount for test bounties
BOUNTY_REASON = "Test bounty reason"


async def setup_test_environment():
    """Set up the test environment with required data"""
    logger.info("Setting up test environment...")
    
    db = await get_db()
    
    # Create test guild if not exists
    guild_data = await db.db.guilds.find_one({"guild_id": TEST_GUILD_ID})
    if not guild_data:
        logger.info(f"Creating test guild: {TEST_GUILD_ID}")
        await db.db.guilds.insert_one({
            "guild_id": TEST_GUILD_ID,
            "name": "Test Guild",
            "premium_tier": 3,  # Premium tier for bounty features
            "auto_bounty": True,
            "auto_bounty_settings": {
                "kill_threshold": 3,
                "repeat_threshold": 2,
                "time_window": 5,
                "reward_amount": 100
            },
            "bounty_channel": None
        })
    
    # Create test server if not exists
    server_data = await db.db.game_servers.find_one({
        "guild_id": TEST_GUILD_ID,
        "server_id": TEST_SERVER_ID
    })
    if not server_data:
        logger.info(f"Creating test server: {TEST_SERVER_ID}")
        await db.db.game_servers.insert_one({
            "guild_id": TEST_GUILD_ID,
            "server_id": TEST_SERVER_ID,
            "name": TEST_SERVER_NAME,
            "sftp_host": "dummy.host",
            "sftp_port": 22,
            "sftp_username": "dummy",
            "sftp_password": "dummy",
            "sftp_directory": "/logs",
            "active": True
        })
    
    # Create test players if not exist
    for player_id, player_name in [
        (TEST_PLAYER_ID_1, TEST_PLAYER_NAME_1),
        (TEST_PLAYER_ID_2, TEST_PLAYER_NAME_2)
    ]:
        player_data = await db.db.players.find_one({
            "server_id": TEST_SERVER_ID,
            "player_id": player_id
        })
        if not player_data:
            logger.info(f"Creating test player: {player_name}")
            await db.db.players.insert_one({
                "server_id": TEST_SERVER_ID,
                "player_id": player_id,
                "name": player_name,
                "kills": 10,
                "deaths": 5,
                "kd_ratio": 2.0,
                "first_seen": datetime.utcnow() - timedelta(days=30),
                "last_seen": datetime.utcnow()
            })
    
    # Create test player links if not exist
    for discord_id, player_id in [
        (TEST_DISCORD_ID_1, TEST_PLAYER_ID_1),
        (TEST_DISCORD_ID_2, TEST_PLAYER_ID_2)
    ]:
        link_data = await db.db.player_links.find_one({
            "discord_id": discord_id,
            "server_id": TEST_SERVER_ID,
            "player_id": player_id
        })
        if not link_data:
            logger.info(f"Creating test player link: Discord {discord_id} -> Player {player_id}")
            await db.db.player_links.insert_one({
                "discord_id": discord_id,
                "server_id": TEST_SERVER_ID,
                "player_id": player_id,
                "verified": True,
                "linked_at": datetime.utcnow() - timedelta(days=15)
            })
    
    # Create test economy data if not exist
    for discord_id in [TEST_DISCORD_ID_1, TEST_DISCORD_ID_2]:
        economy_data = await db.db.economy.find_one({
            "discord_id": discord_id,
            "server_id": TEST_SERVER_ID
        })
        if not economy_data:
            logger.info(f"Creating test economy data for Discord ID: {discord_id}")
            await db.db.economy.insert_one({
                "discord_id": discord_id,
                "server_id": TEST_SERVER_ID,
                "balance": INITIAL_BALANCE,
                "total_earned": INITIAL_BALANCE,
                "total_spent": 0,
                "transactions": [{
                    "type": "initial",
                    "amount": INITIAL_BALANCE,
                    "timestamp": datetime.utcnow() - timedelta(days=10),
                    "description": "Initial balance for testing"
                }]
            })
        else:
            # Reset the balance for testing
            logger.info(f"Resetting economy balance for Discord ID: {discord_id}")
            await db.db.economy.update_one(
                {"discord_id": discord_id, "server_id": TEST_SERVER_ID},
                {"$set": {"balance": INITIAL_BALANCE}}
            )
    
    # Clear all existing bounties for clean testing
    await db.db.bounties.delete_many({
        "guild_id": TEST_GUILD_ID,
        "server_id": TEST_SERVER_ID
    })
    logger.info("Cleared existing bounties for testing")
    
    logger.info("Test environment setup complete!")


async def test_bounty_creation():
    """Test creating a new bounty"""
    logger.info("Testing bounty creation...")
    
    # Create a new bounty
    bounty = await Bounty.create(
        guild_id=TEST_GUILD_ID,
        server_id=TEST_SERVER_ID,
        target_id=TEST_PLAYER_ID_1,
        target_name=TEST_PLAYER_NAME_1,
        placed_by=TEST_DISCORD_ID_1,
        placed_by_name=TEST_DISCORD_NAME_1,
        reason=BOUNTY_REASON,
        reward=BOUNTY_AMOUNT,
        source=Bounty.SOURCE_PLAYER,
        lifespan_hours=1.0
    )
    
    logger.info(f"Created bounty with ID: {bounty.id}")
    
    # Verify the created bounty
    assert bounty.guild_id == TEST_GUILD_ID, "Guild ID doesn't match"
    assert bounty.server_id == TEST_SERVER_ID, "Server ID doesn't match"
    assert bounty.target_id == TEST_PLAYER_ID_1, "Target ID doesn't match"
    assert bounty.target_name == TEST_PLAYER_NAME_1, "Target name doesn't match"
    assert bounty.placed_by == TEST_DISCORD_ID_1, "Placer ID doesn't match"
    assert bounty.placed_by_name == TEST_DISCORD_NAME_1, "Placer name doesn't match"
    assert bounty.reason == BOUNTY_REASON, "Reason doesn't match"
    assert bounty.reward == BOUNTY_AMOUNT, "Reward amount doesn't match"
    assert bounty.status == Bounty.STATUS_ACTIVE, "Status should be active"
    
    # Retrieve the bounty from the database
    retrieved_bounty = await Bounty.get_by_id(bounty.id)
    assert retrieved_bounty is not None, "Failed to retrieve bounty"
    assert retrieved_bounty.id == bounty.id, "Retrieved bounty ID doesn't match"
    
    logger.info("Bounty creation test passed!")
    return bounty


async def test_active_bounties():
    """Test retrieving active bounties"""
    logger.info("Testing active bounties retrieval...")
    
    # Create a second bounty for testing
    bounty2 = await Bounty.create(
        guild_id=TEST_GUILD_ID,
        server_id=TEST_SERVER_ID,
        target_id=TEST_PLAYER_ID_1,
        target_name=TEST_PLAYER_NAME_1,
        placed_by=TEST_DISCORD_ID_1,
        placed_by_name=TEST_DISCORD_NAME_1,
        reason="Another test bounty",
        reward=BOUNTY_AMOUNT * 2,
        source=Bounty.SOURCE_PLAYER,
        lifespan_hours=1.0
    )
    
    # Get active bounties
    active_bounties = await Bounty.get_active_bounties(TEST_GUILD_ID, TEST_SERVER_ID)
    
    # Verify active bounties
    assert len(active_bounties) >= 2, f"Expected at least 2 active bounties, got {len(active_bounties)}"
    
    # Verify active bounties for specific target
    target_bounties = await Bounty.get_active_bounties_for_target(
        TEST_GUILD_ID, TEST_SERVER_ID, TEST_PLAYER_ID_1
    )
    assert len(target_bounties) >= 2, f"Expected at least 2 active bounties for target, got {len(target_bounties)}"
    
    logger.info("Active bounties test passed!")
    return bounty2


async def test_bounty_claim():
    """Test claiming a bounty"""
    logger.info("Testing bounty claiming...")
    
    # Get initial balance for the claimer
    db = await get_db()
    economy_data = await db.db.economy.find_one({
        "discord_id": TEST_DISCORD_ID_2,
        "server_id": TEST_SERVER_ID
    })
    initial_balance = economy_data["balance"]
    
    # Create a bounty to claim
    bounty = await Bounty.create(
        guild_id=TEST_GUILD_ID,
        server_id=TEST_SERVER_ID,
        target_id=TEST_PLAYER_ID_1,
        target_name=TEST_PLAYER_NAME_1,
        placed_by=TEST_DISCORD_ID_1,
        placed_by_name=TEST_DISCORD_NAME_1,
        reason="Bounty to claim",
        reward=BOUNTY_AMOUNT,
        source=Bounty.SOURCE_PLAYER,
        lifespan_hours=1.0
    )
    
    # Check bounties for a kill
    claimed_bounties = await Bounty.check_bounties_for_kill(
        TEST_GUILD_ID,
        TEST_SERVER_ID,
        TEST_DISCORD_ID_2,
        TEST_DISCORD_NAME_2,
        TEST_PLAYER_ID_1
    )
    
    # Verify claim
    assert len(claimed_bounties) > 0, "No bounties were claimed"
    
    # Check that the bounty status was updated
    updated_bounty = await Bounty.get_by_id(bounty.id)
    assert updated_bounty.status == Bounty.STATUS_CLAIMED, f"Expected status CLAIMED, got {updated_bounty.status}"
    assert updated_bounty.claimed_by == TEST_DISCORD_ID_2, "Claimer ID doesn't match"
    assert updated_bounty.claimed_by_name == TEST_DISCORD_NAME_2, "Claimer name doesn't match"
    
    # Check that the economy was updated
    updated_economy = await db.db.economy.find_one({
        "discord_id": TEST_DISCORD_ID_2,
        "server_id": TEST_SERVER_ID
    })
    expected_balance = initial_balance + BOUNTY_AMOUNT
    assert updated_economy["balance"] == expected_balance, f"Expected balance {expected_balance}, got {updated_economy['balance']}"
    
    logger.info("Bounty claim test passed!")
    return claimed_bounties


async def test_bounty_expiration():
    """Test bounty expiration"""
    logger.info("Testing bounty expiration...")
    
    # Create a bounty with a very short lifespan
    bounty = await Bounty.create(
        guild_id=TEST_GUILD_ID,
        server_id=TEST_SERVER_ID,
        target_id=TEST_PLAYER_ID_1,
        target_name=TEST_PLAYER_NAME_1,
        placed_by=TEST_DISCORD_ID_1,
        placed_by_name=TEST_DISCORD_NAME_1,
        reason="Short-lived bounty",
        reward=BOUNTY_AMOUNT,
        source=Bounty.SOURCE_PLAYER,
        lifespan_hours=0.001  # Just a few seconds
    )
    
    # Wait for the bounty to expire
    logger.info("Waiting for bounty to expire...")
    await asyncio.sleep(2)
    
    # Run the expiration check
    expired_count = await Bounty.expire_old_bounties()
    logger.info(f"Expired {expired_count} bounties")
    
    # Verify the bounty is expired
    updated_bounty = await Bounty.get_by_id(bounty.id)
    assert updated_bounty.status == Bounty.STATUS_EXPIRED, f"Expected status EXPIRED, got {updated_bounty.status}"
    
    logger.info("Bounty expiration test passed!")


async def test_auto_bounty_detection():
    """Test auto-bounty detection logic"""
    logger.info("Testing auto-bounty detection...")
    
    db = await get_db()
    
    # Clear existing kill data for this test
    await db.db.kills.delete_many({
        "guild_id": TEST_GUILD_ID,
        "server_id": TEST_SERVER_ID,
        "killer_id": TEST_PLAYER_ID_2,
    })
    
    # Add simulated kill events to trigger auto-bounty detection
    now = datetime.utcnow()
    
    # Add multiple kills of the same player to simulate a killstreak
    kills = []
    for i in range(5):
        kills.append({
            "guild_id": TEST_GUILD_ID,
            "server_id": TEST_SERVER_ID,
            "kill_id": f"test-kill-{i}",
            "timestamp": now - timedelta(minutes=i),
            "killer_id": TEST_PLAYER_ID_2,
            "killer_name": TEST_PLAYER_NAME_2,
            "victim_id": f"victim-{i}",
            "victim_name": f"Victim{i}",
            "weapon": "Test Weapon",
            "distance": 100,
        })
    
    # Add multiple kills of the same player to simulate target fixation
    for i in range(3):
        kills.append({
            "guild_id": TEST_GUILD_ID,
            "server_id": TEST_SERVER_ID,
            "kill_id": f"test-repeat-kill-{i}",
            "timestamp": now - timedelta(minutes=i),
            "killer_id": TEST_PLAYER_ID_2,
            "killer_name": TEST_PLAYER_NAME_2,
            "victim_id": "repeat-victim",
            "victim_name": "RepeatVictim",
            "weapon": "Test Weapon",
            "distance": 100,
        })
    
    # Insert kills
    for kill in kills:
        await db.db.kills.insert_one(kill)
    
    logger.info(f"Added {len(kills)} simulated kill events")
    
    # Get player stats for bounty
    stats = await Bounty.get_player_stats_for_bounty(
        TEST_GUILD_ID,
        TEST_SERVER_ID,
        minutes=10,
        kill_threshold=5,
        repeat_threshold=3
    )
    
    # Verify stats
    assert len(stats) > 0, "No auto-bounty candidates found"
    
    found_killstreak = False
    found_repeat = False
    
    for stat in stats:
        logger.info(f"Auto-bounty candidate: {stat}")
        if stat["bounty_type"] == "killstreak" and stat["player_id"] == TEST_PLAYER_ID_2:
            found_killstreak = True
        if stat["bounty_type"] == "fixation" and stat["player_id"] == TEST_PLAYER_ID_2:
            found_repeat = True
    
    assert found_killstreak, "Killstreak bounty not detected"
    assert found_repeat, "Target fixation bounty not detected"
    
    logger.info("Auto-bounty detection test passed!")


async def test_bounty_lifecycle():
    """Test full bounty lifecycle (place, claim, economy integration)"""
    logger.info("Testing complete bounty lifecycle...")
    
    db = await get_db()
    
    # Get initial balances
    placer_economy = await db.db.economy.find_one({
        "discord_id": TEST_DISCORD_ID_1,
        "server_id": TEST_SERVER_ID
    })
    claimer_economy = await db.db.economy.find_one({
        "discord_id": TEST_DISCORD_ID_2,
        "server_id": TEST_SERVER_ID
    })
    
    placer_initial_balance = placer_economy["balance"]
    claimer_initial_balance = claimer_economy["balance"]
    
    # Create economy objects
    placer_econ = await Economy.get_by_player(db, TEST_DISCORD_ID_1, TEST_SERVER_ID)
    
    # Place bounty (deduct from placer)
    success = await placer_econ.remove_currency(BOUNTY_AMOUNT, "bounty_placed", {
        "target_id": TEST_PLAYER_ID_1,
        "target_name": TEST_PLAYER_NAME_1,
        "reason": "Lifecycle test bounty"
    })
    
    assert success, "Failed to deduct currency for bounty"
    
    # Create the bounty
    bounty = await Bounty.create(
        guild_id=TEST_GUILD_ID,
        server_id=TEST_SERVER_ID,
        target_id=TEST_PLAYER_ID_1,
        target_name=TEST_PLAYER_NAME_1,
        placed_by=TEST_DISCORD_ID_1,
        placed_by_name=TEST_DISCORD_NAME_1,
        reason="Lifecycle test bounty",
        reward=BOUNTY_AMOUNT,
        source=Bounty.SOURCE_PLAYER,
        lifespan_hours=1.0
    )
    
    # Verify the placer's balance was reduced
    updated_placer = await db.db.economy.find_one({
        "discord_id": TEST_DISCORD_ID_1,
        "server_id": TEST_SERVER_ID
    })
    assert updated_placer["balance"] == placer_initial_balance - BOUNTY_AMOUNT, "Placer balance not updated correctly"
    
    # Claim the bounty
    claim_success = await bounty.claim(TEST_DISCORD_ID_2, TEST_DISCORD_NAME_2)
    assert claim_success, "Failed to claim bounty"
    
    # Add reward to claimer
    claimer_econ = await Economy.get_by_player(db, TEST_DISCORD_ID_2, TEST_SERVER_ID)
    add_success = await claimer_econ.add_currency(BOUNTY_AMOUNT, "bounty_claimed", {
        "bounty_id": str(bounty.id),
        "target_id": TEST_PLAYER_ID_1,
        "target_name": TEST_PLAYER_NAME_1
    })
    
    assert add_success, "Failed to add reward to claimer"
    
    # Verify the claimer's balance was increased
    updated_claimer = await db.db.economy.find_one({
        "discord_id": TEST_DISCORD_ID_2,
        "server_id": TEST_SERVER_ID
    })
    assert updated_claimer["balance"] == claimer_initial_balance + BOUNTY_AMOUNT, "Claimer balance not updated correctly"
    
    # Verify the bounty is marked as claimed
    updated_bounty = await Bounty.get_by_id(bounty.id)
    assert updated_bounty.status == Bounty.STATUS_CLAIMED, "Bounty not marked as claimed"
    assert updated_bounty.claimed_by == TEST_DISCORD_ID_2, "Bounty claimed_by field not updated correctly"
    
    # Verify the claimed bounty appears in the claimed list
    claimed_bounties = await Bounty.get_bounties_claimed_by(
        TEST_GUILD_ID, TEST_SERVER_ID, TEST_DISCORD_ID_2
    )
    
    found_bounty = False
    for b in claimed_bounties:
        if b.id == bounty.id:
            found_bounty = True
            break
    
    assert found_bounty, "Bounty not found in claimed bounties list"
    
    logger.info("Bounty lifecycle test passed!")


async def cleanup():
    """Clean up test data"""
    logger.info("Cleaning up test data...")
    
    db = await get_db()
    
    # You might want to keep this commented out if you want to inspect
    # the test data after running the tests
    
    # Remove test bounties
    # await db.db.bounties.delete_many({
    #     "guild_id": TEST_GUILD_ID,
    #     "server_id": TEST_SERVER_ID
    # })
    
    # Remove test kills
    # await db.db.kills.delete_many({
    #     "guild_id": TEST_GUILD_ID,
    #     "server_id": TEST_SERVER_ID,
    #     "kill_id": {"$regex": "^test-"}
    # })
    
    logger.info("Test data cleanup complete!")


async def main():
    """Run all tests"""
    try:
        # Setup test environment
        await setup_test_environment()
        
        # Run all tests
        await test_bounty_creation()
        await test_active_bounties()
        await test_bounty_claim()
        await test_bounty_expiration()
        await test_auto_bounty_detection()
        await test_bounty_lifecycle()
        
        # Clean up
        await cleanup()
        
        logger.info("All tests passed!")
        
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        raise
    finally:
        # Close any open connections
        db = await get_db()
        if hasattr(db, 'client') and db.client:
            db.client.close()


if __name__ == "__main__":
    # Run the test
    asyncio.run(main())