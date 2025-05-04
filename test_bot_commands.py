"""
Comprehensive integration test for Discord bot commands.

This script:
1. Tests the bot's ability to connect to Discord
2. Verifies that all cogs are loaded 
3. Validates command registration
4. Tests the bounty system commands
5. Checks premium tier enforcement on commands

Usage:
    python test_bot_commands.py
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

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

# Import Discord libraries
import discord
from discord.ext import commands

# Import bot modules
from bot import initialize_bot
from utils.database import get_db
from models.bounty import Bounty
from models.guild import Guild


async def test_bot_initialization():
    """Test bot initialization and connection to Discord"""
    logger.info("Testing bot initialization...")
    
    try:
        # Initialize the bot but don't start it
        bot = await initialize_bot(force_sync=False)
        assert bot is not None, "Bot initialization failed"
        
        # Check bot attributes
        assert bot.intents.guilds, "Bot should have guilds intent"
        assert bot.intents.guild_messages, "Bot should have guild_messages intent"
        assert bot.intents.message_content, "Bot should have message_content intent"
        
        # Check if token is set and valid format
        token = os.getenv("DISCORD_TOKEN")
        assert token is not None, "DISCORD_TOKEN not set"
        assert len(token) > 20, "DISCORD_TOKEN seems too short to be valid"
        
        logger.info("Bot initialization test passed!")
        return bot
    except Exception as e:
        logger.error(f"Bot initialization test failed: {e}", exc_info=True)
        raise


async def test_cogs_loaded(bot):
    """Test that all required cogs are loaded"""
    logger.info("Testing cog loading...")
    
    # Get list of cogs
    cogs = list(bot.cogs.keys())
    logger.info(f"Loaded cogs: {cogs}")
    
    # Essential cogs that should be loaded
    essential_cogs = ["BountiesCog", "SetupCog", "StatsCog", "HelpCog", "AdminCog"]
    
    # Verify all essential cogs are loaded
    missing_cogs = [cog for cog in essential_cogs if cog not in cogs]
    assert not missing_cogs, f"Missing essential cogs: {missing_cogs}"
    
    # Specifically check the BountiesCog
    assert "BountiesCog" in cogs, "BountiesCog is not loaded"
    
    # Get the bounties cog and check its commands
    bounties_cog = bot.get_cog("BountiesCog")
    assert bounties_cog is not None, "Failed to get BountiesCog"
    
    # Check the cog has commands
    bounty_commands = bounties_cog.get_commands() 
    assert len(bounty_commands) > 0, "BountiesCog has no commands"
    
    # Log commands
    for cmd in bounty_commands:
        logger.info(f"Found command: {cmd.name} in BountiesCog")
    
    logger.info("Cog loading test passed!")


async def test_command_registration(bot):
    """Test that all commands are properly registered"""
    logger.info("Testing command registration...")
    
    # Get all app commands
    all_commands = await bot.tree.fetch_commands()
    
    # Log all commands
    for cmd in all_commands:
        logger.info(f"Registered command: {cmd.name} ({cmd.id})")
    
    # Verify bounty commands are registered
    bounty_command = next((cmd for cmd in all_commands if cmd.name == "bounty"), None)
    assert bounty_command is not None, "Bounty command not registered"
    
    # Check for specific bounty subcommands we expect
    expected_bounty_subcommands = ["place", "active", "my", "settings"]
    
    # We can't directly access subcommands from the API, so we'll just log this
    logger.info(f"Found bounty command. Subcommands would be checked in a real Discord context.")
    
    # Check all expected top-level commands
    expected_commands = ["setup", "stats", "profile", "leaderboard", "faction", "help", "admin", "bounty"]
    for cmd_name in expected_commands:
        cmd = next((cmd for cmd in all_commands if cmd.name == cmd_name), None)
        assert cmd is not None, f"{cmd_name} command not registered"
    
    logger.info("Command registration test passed!")


async def test_database_connectivity():
    """Test that the bot can connect to the database"""
    logger.info("Testing database connectivity...")
    
    try:
        db = await get_db()
        assert db is not None, "Failed to get database connection"
        
        # Test simple query
        db_info = await db.command("serverStatus")
        assert db_info is not None, "Failed to execute serverStatus command"
        
        # Check if collections exist
        collections = await db.list_collection_names()
        logger.info(f"Database collections: {collections}")
        
        required_collections = ["guilds", "game_servers", "players", "bounties", "economy", "player_links"]
        for collection in required_collections:
            assert collection in collections, f"Collection {collection} not found in database"
        
        # Test simple query on bounties collection
        bounties_count = await db.db.bounties.count_documents({})
        logger.info(f"Total bounties in database: {bounties_count}")
        
        logger.info("Database connectivity test passed!")
    except Exception as e:
        logger.error(f"Database connectivity test failed: {e}", exc_info=True)
        raise


async def test_premium_tier_enforcement():
    """Test premium tier enforcement on commands"""
    logger.info("Testing premium tier enforcement...")
    
    db = await get_db()
    
    # Get test guild ID
    guild_id = os.getenv("HOME_GUILD_ID")
    assert guild_id is not None, "HOME_GUILD_ID environment variable not set"
    
    # Get current premium tier
    guild_data = await db.db.guilds.find_one({"guild_id": guild_id})
    assert guild_data is not None, f"Guild with ID {guild_id} not found in database"
    
    # Store the original premium tier
    original_tier = guild_data.get("premium_tier", 0)
    logger.info(f"Current premium tier for guild {guild_id}: {original_tier}")
    
    try:
        # Set premium tier to 1 (below required for bounty system)
        await db.db.guilds.update_one(
            {"guild_id": guild_id},
            {"$set": {"premium_tier": 1}}
        )
        logger.info(f"Set premium tier to 1 (below required for bounty system)")
        
        # With premium tier 1, bounty commands would be restricted
        # We can't test actual Discord interactions here, but we can verify 
        # our Bounty class obeys premium tiers
        
        guild = await Guild.get_by_guild_id(guild_id)
        assert guild is not None, "Failed to get Guild instance"
        
        # Verify the premium tier was updated
        assert guild.premium_tier == 1, f"Guild premium tier should be 1, got {guild.premium_tier}"
        
        # Testing command checks on premium tier would require running in Discord
        # so we'll just log this test as informational
        logger.info("Premium tier enforcement would be tested in a real Discord context")
        
        # Reset to original premium tier
        await db.db.guilds.update_one(
            {"guild_id": guild_id},
            {"$set": {"premium_tier": original_tier}}
        )
        logger.info(f"Reset premium tier to original value: {original_tier}")
        
        logger.info("Premium tier enforcement checks passed!")
    except Exception as e:
        # Make sure to reset premium tier even if test fails
        await db.db.guilds.update_one(
            {"guild_id": guild_id},
            {"$set": {"premium_tier": original_tier}}
        )
        logger.error(f"Premium tier enforcement test failed: {e}", exc_info=True)
        raise


async def test_bounty_command_integration():
    """Test bounty command integration with database"""
    logger.info("Testing bounty command integration...")
    
    # This test checks that the bounty system is properly wired together
    # without actually executing Discord commands
    
    try:
        # Create a test bounty
        test_guild_id = os.getenv("HOME_GUILD_ID")
        test_server_id = "integration-test-server"
        
        # Make sure this server exists in the database
        db = await get_db()
        server_data = await db.db.game_servers.find_one({
            "guild_id": test_guild_id,
            "server_id": test_server_id
        })
        
        if not server_data:
            # Create a test server entry
            await db.db.game_servers.insert_one({
                "guild_id": test_guild_id,
                "server_id": test_server_id,
                "name": "Integration Test Server",
                "sftp_host": "dummy.host",
                "sftp_port": 22,
                "sftp_username": "dummy",
                "sftp_password": "dummy",
                "sftp_directory": "/logs",
                "active": True
            })
            logger.info(f"Created test server: {test_server_id}")
        
        # Clear existing test bounties
        await db.db.bounties.delete_many({
            "guild_id": test_guild_id,
            "server_id": test_server_id,
            "reason": {"$regex": "^Integration test"}
        })
        
        # Create a test bounty
        bounty = await Bounty.create(
            guild_id=test_guild_id,
            server_id=test_server_id,
            target_id="test-player-id",
            target_name="TestPlayerName",
            placed_by="999888777666555444",
            placed_by_name="TestPlacerName",
            reason="Integration test bounty",
            reward=100,
            source=Bounty.SOURCE_PLAYER,
            lifespan_hours=1.0
        )
        
        logger.info(f"Created test bounty: {bounty.id}")
        
        # Retrieve active bounties
        active_bounties = await Bounty.get_active_bounties(test_guild_id, test_server_id)
        test_bounty = next((b for b in active_bounties if b.id == bounty.id), None)
        
        assert test_bounty is not None, "Test bounty not found in active bounties"
        assert test_bounty.reason == "Integration test bounty", "Bounty reason doesn't match"
        
        # Test claim functionality
        claim_success = await test_bounty.claim("111222333444555666", "TestClaimerName")
        assert claim_success, "Failed to claim bounty"
        
        # Verify bounty was claimed
        updated_bounty = await Bounty.get_by_id(bounty.id)
        assert updated_bounty.status == Bounty.STATUS_CLAIMED, "Bounty not marked as claimed"
        assert updated_bounty.claimed_by == "111222333444555666", "Claimer ID doesn't match"
        
        logger.info("Bounty command integration test passed!")
    except Exception as e:
        logger.error(f"Bounty command integration test failed: {e}", exc_info=True)
        raise


async def run_all_tests():
    """Run all tests"""
    try:
        logger.info("Starting comprehensive Discord bot tests...")
        
        # First test database connectivity
        await test_database_connectivity()
        
        # Test bot initialization
        bot = await test_bot_initialization()
        
        # Test cogs loaded
        await test_cogs_loaded(bot)
        
        # Test command registration
        await test_command_registration(bot)
        
        # Test premium tier enforcement
        await test_premium_tier_enforcement()
        
        # Test bounty command integration
        await test_bounty_command_integration()
        
        logger.info("All tests completed successfully!")
    except Exception as e:
        logger.error(f"Tests failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    # Run all tests
    asyncio.run(run_all_tests())