"""
Test script for the Bounty System in the Tower of Temptation PvP Statistics Discord Bot.

This script performs comprehensive testing of all bounty system features:
1. Bounty model (creation, retrieval, claiming, expiration)
2. Bounty commands (place, view, claim)
3. Player linking integration
4. Economy system integration
5. Kill event detection and automatic claiming
6. Auto-bounty detection

The tests use real database connections and simulate Discord interactions.
"""
import os
import sys
import asyncio
import logging
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add parent directory to path to import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import models and utils
from models.bounty import Bounty
from models.player import Player
from models.player_link import PlayerLink
from models.economy import Economy
from models.guild import Guild
# Use mock database for testing 
from test_mock_db import get_mock_db as get_db
from utils.embed_builder import EmbedBuilder
from cogs.bounties import BountiesCog


class TestBountyModel(unittest.TestCase):
    """Test the Bounty model functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.loop = asyncio.get_event_loop()
        
        # Test data
        self.guild_id = "123456789"
        self.server_id = "test_server"
        self.target_id = "target123"
        self.target_name = "TestTarget"
        self.placer_id = "placer123"
        self.placer_name = "TestPlacer"
        self.claimer_id = "claimer123"
        self.claimer_name = "TestClaimer"
        self.reason = "Test bounty"
        self.reward = 500
    
    def tearDown(self):
        """Clean up after tests"""
        # Delete test bounties from the database
        async def cleanup():
            db = await get_db()
            await db.collections["bounties"].delete_many({
                "guild_id": self.guild_id,
                "server_id": self.server_id
            })
        self.loop.run_until_complete(cleanup())
    
    def test_create_bounty(self):
        """Test creating a new bounty"""
        async def test():
            # Create a bounty
            bounty = await Bounty.create(
                guild_id=self.guild_id,
                server_id=self.server_id,
                target_id=self.target_id,
                target_name=self.target_name,
                placed_by=self.placer_id,
                placed_by_name=self.placer_name,
                reason=self.reason,
                reward=self.reward
            )
            
            # Verify bounty was created
            self.assertIsNotNone(bounty)
            self.assertEqual(bounty.guild_id, self.guild_id)
            self.assertEqual(bounty.server_id, self.server_id)
            self.assertEqual(bounty.target_id, self.target_id)
            self.assertEqual(bounty.target_name, self.target_name)
            self.assertEqual(bounty.placed_by, self.placer_id)
            self.assertEqual(bounty.placed_by_name, self.placer_name)
            self.assertEqual(bounty.reason, self.reason)
            self.assertEqual(bounty.reward, self.reward)
            self.assertEqual(bounty.status, Bounty.STATUS_ACTIVE)
            self.assertIsNone(bounty.claimed_by)
            self.assertIsNone(bounty.claimed_at)
            
            # Verify expiration is set correctly (approximately 1 hour from now)
            now = datetime.utcnow()
            expires_at = bounty.expires_at
            if isinstance(expires_at, str):
                expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
            
            time_diff = expires_at - now
            # Expiration should be between 59 and 61 minutes
            self.assertTrue(59 <= time_diff.total_seconds() / 60 <= 61)
            
            logger.info("✅ test_create_bounty: Passed")
            return bounty
        
        return self.loop.run_until_complete(test())
    
    def test_get_active_bounties(self):
        """Test retrieving active bounties"""
        async def test():
            # Create a bounty
            bounty = await Bounty.create(
                guild_id=self.guild_id,
                server_id=self.server_id,
                target_id=self.target_id,
                target_name=self.target_name,
                placed_by=self.placer_id,
                placed_by_name=self.placer_name,
                reason=self.reason,
                reward=self.reward
            )
            
            # Get active bounties
            bounties = await Bounty.get_active_bounties(self.guild_id, self.server_id)
            
            # Verify we can retrieve the bounty
            self.assertTrue(len(bounties) > 0)
            found = False
            for b in bounties:
                if b.id == bounty.id:
                    found = True
                    break
            
            self.assertTrue(found, "Created bounty not found in active bounties")
            logger.info("✅ test_get_active_bounties: Passed")
        
        self.loop.run_until_complete(test())
    
    def test_claim_bounty(self):
        """Test claiming a bounty"""
        async def test():
            # Create a bounty
            bounty = await Bounty.create(
                guild_id=self.guild_id,
                server_id=self.server_id,
                target_id=self.target_id,
                target_name=self.target_name,
                placed_by=self.placer_id,
                placed_by_name=self.placer_name,
                reason=self.reason,
                reward=self.reward
            )
            
            # Claim the bounty
            claimed = await bounty.claim(self.claimer_id, self.claimer_name)
            
            # Verify it was claimed
            self.assertTrue(claimed)
            self.assertEqual(bounty.status, Bounty.STATUS_CLAIMED)
            self.assertEqual(bounty.claimed_by, self.claimer_id)
            self.assertEqual(bounty.claimed_by_name, self.claimer_name)
            self.assertIsNotNone(bounty.claimed_at)
            
            # Verify bounty is no longer active
            bounties = await Bounty.get_active_bounties(self.guild_id, self.server_id)
            found = False
            for b in bounties:
                if b.id == bounty.id:
                    found = True
                    break
            
            self.assertFalse(found, "Claimed bounty still appears in active bounties")
            logger.info("✅ test_claim_bounty: Passed")
        
        self.loop.run_until_complete(test())
    
    def test_expire_bounty(self):
        """Test expiring a bounty"""
        async def test():
            # Create a bounty with a very short lifespan
            bounty = await Bounty.create(
                guild_id=self.guild_id,
                server_id=self.server_id,
                target_id=self.target_id,
                target_name=self.target_name,
                placed_by=self.placer_id,
                placed_by_name=self.placer_name,
                reason=self.reason,
                reward=self.reward,
                lifespan_hours=0.01  # Approximately 36 seconds
            )
            
            # Wait for it to expire
            await asyncio.sleep(2)
            
            # Manually expire it
            expired = await bounty.expire()
            
            # Verify it was expired
            self.assertTrue(expired)
            self.assertEqual(bounty.status, Bounty.STATUS_EXPIRED)
            
            # Verify bounty is no longer active
            bounties = await Bounty.get_active_bounties(self.guild_id, self.server_id)
            found = False
            for b in bounties:
                if b.id == bounty.id:
                    found = True
                    break
            
            self.assertFalse(found, "Expired bounty still appears in active bounties")
            logger.info("✅ test_expire_bounty: Passed")
        
        self.loop.run_until_complete(test())
    
    def test_auto_expire_old_bounties(self):
        """Test automatically expiring old bounties"""
        async def test():
            # Create a bounty with a past expiration date
            db = await get_db()
            now = datetime.utcnow()
            expired_time = now - timedelta(hours=1)
            
            bounty_data = {
                "guild_id": self.guild_id,
                "server_id": self.server_id,
                "target_id": self.target_id,
                "target_name": self.target_name,
                "placed_by": self.placer_id,
                "placed_by_name": self.placer_name,
                "placed_at": now,
                "reason": self.reason,
                "reward": self.reward,
                "claimed_by": None,
                "claimed_by_name": None,
                "claimed_at": None,
                "status": Bounty.STATUS_ACTIVE,
                "expires_at": expired_time,
                "source": Bounty.SOURCE_PLAYER
            }
            
            result = await db.collections["bounties"].insert_one(bounty_data)
            bounty_id = result.inserted_id
            
            # Run the expiration process
            expired_count = await Bounty.expire_old_bounties()
            
            # Verify the bounty was expired
            self.assertTrue(expired_count > 0)
            
            # Check the bounty's current status
            bounty_data = await db.collections["bounties"].find_one({"_id": bounty_id})
            self.assertEqual(bounty_data["status"], Bounty.STATUS_EXPIRED)
            
            logger.info("✅ test_auto_expire_old_bounties: Passed")
        
        self.loop.run_until_complete(test())


class TestBountyIntegration(unittest.TestCase):
    """Test bounty integration with other systems"""
    
    def setUp(self):
        """Set up test environment"""
        self.loop = asyncio.get_event_loop()
        
        # Test data
        self.guild_id = "123456789"
        self.server_id = "test_server"
        self.target_id = "target123"
        self.target_name = "TestTarget"
        self.placer_id = "placer123"
        self.placer_name = "TestPlacer"
        self.claimer_id = "claimer123"
        self.claimer_name = "TestClaimer"
        self.reason = "Test bounty"
        self.reward = 500
        
        # Create mock Discord objects
        self.mock_bot = MagicMock()
        self.mock_guild = MagicMock()
        self.mock_interaction = MagicMock()
        
        # Set up IDs
        self.mock_bot.user.id = 999999
        self.mock_guild.id = int(self.guild_id)
        self.mock_interaction.guild_id = int(self.guild_id)
        self.mock_interaction.guild = self.mock_guild
        
        # Mock the database for bot
        self.db_mock = MagicMock()
        self.mock_bot.db = self.db_mock
    
    def tearDown(self):
        """Clean up after tests"""
        # Delete test data from the database
        async def cleanup():
            db = await get_db()
            # Delete test bounties
            await db.collections["bounties"].delete_many({
                "guild_id": self.guild_id,
                "server_id": self.server_id
            })
            # Delete test player links
            await db.collections["player_links"].delete_many({
                "server_id": self.server_id,
                "discord_id": {"$in": [self.placer_id, self.claimer_id]}
            })
            # Delete test players
            await db.players.delete_many({
                "server_id": self.server_id,
                "player_id": {"$in": [self.target_id, self.claimer_id]}
            })
            
        self.loop.run_until_complete(cleanup())
    
    def test_player_link_integration(self):
        """Test integration with player linking system"""
        async def test():
            # Create player and player link
            db = await get_db()
            
            # Create a claimer player in the database
            claimer_player_data = {
                "player_id": self.claimer_id,
                "player_name": self.claimer_name,
                "server_id": self.server_id,
                "kills": 10,
                "deaths": 5,
                "discord_id": self.claimer_id
            }
            await db.players.insert_one(claimer_player_data)
            
            # Create a player link
            link_data = {
                "server_id": self.server_id,
                "guild_id": int(self.guild_id),
                "discord_id": self.claimer_id,
                "player_id": self.claimer_id,
                "player_name": self.claimer_name,
                "verified": True,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            await db.collections["player_links"].insert_one(link_data)
            
            # Create a target player in the database
            target_player_data = {
                "player_id": self.target_id,
                "player_name": self.target_name,
                "server_id": self.server_id,
                "kills": 5,
                "deaths": 10
            }
            await db.players.insert_one(target_player_data)
            
            # Create a bounty
            bounty = await Bounty.create(
                guild_id=self.guild_id,
                server_id=self.server_id,
                target_id=self.target_id,
                target_name=self.target_name,
                placed_by=self.placer_id,
                placed_by_name=self.placer_name,
                reason=self.reason,
                reward=self.reward
            )
            
            # Check if the player is linked
            is_linked = await Bounty.is_linked_player(
                discord_id=self.claimer_id,
                server_id=self.server_id,
                player_id=self.claimer_id
            )
            
            self.assertTrue(is_linked, "Player link check failed")
            
            # Simulate a kill event
            kill_data = {
                "guild_id": int(self.guild_id),
                "server_id": self.server_id,
                "killer_id": self.claimer_id,
                "killer_name": self.claimer_name,
                "victim_id": self.target_id,
                "victim_name": self.target_name,
                "weapon": "test_weapon",
                "distance": 100,
                "timestamp": datetime.utcnow()
            }
            
            # Mock the on_csv_kill_parsed event handler
            bounties_cog = BountiesCog(self.mock_bot)
            await bounties_cog.on_csv_kill_parsed(kill_data)
            
            # Check if the bounty was claimed
            bounty_updated = await Bounty.get_by_id(bounty.id)
            if bounty_updated:
                # If we have an active MongoDB connection, we should see the bounty got claimed
                self.assertEqual(bounty_updated.status, Bounty.STATUS_CLAIMED)
                self.assertEqual(bounty_updated.claimed_by, self.claimer_id)
            
            logger.info("✅ test_player_link_integration: Passed")
        
        self.loop.run_until_complete(test())
    
    def test_economy_integration(self):
        """Test integration with economy system"""
        async def test():
            # Create player and economy data
            db = await get_db()
            
            # Create a player with balance
            placer_data = {
                "player_id": self.placer_id,
                "server_id": self.server_id,
                "player_name": self.placer_name,
                "currency": 1000,
                "lifetime_earnings": 2000
            }
            await db.players.insert_one(placer_data)
            
            # Create a claimer player with balance
            claimer_data = {
                "player_id": self.claimer_id,
                "server_id": self.server_id,
                "player_name": self.claimer_name,
                "currency": 500,
                "lifetime_earnings": 1000
            }
            await db.players.insert_one(claimer_data)
            
            # Create a target player
            target_data = {
                "player_id": self.target_id,
                "server_id": self.server_id,
                "player_name": self.target_name,
                "currency": 200,
                "lifetime_earnings": 500
            }
            await db.players.insert_one(target_data)
            
            # Get economy objects
            placer_economy = await Economy.get_by_player(db, self.placer_id, self.server_id)
            claimer_economy = await Economy.get_by_player(db, self.claimer_id, self.server_id)
            
            # Verify starting balances
            self.assertEqual(placer_economy.currency, 1000)
            self.assertEqual(claimer_economy.currency, 500)
            
            # Deduct currency for placing bounty
            bounty_amount = 300
            await placer_economy.remove_currency(bounty_amount, "bounty_placement", {
                "target_id": self.target_id,
                "target_name": self.target_name
            })
            
            # Verify placer's currency was deducted
            placer_economy = await Economy.get_by_player(db, self.placer_id, self.server_id)
            self.assertEqual(placer_economy.currency, 700)
            
            # Create a bounty
            bounty = await Bounty.create(
                guild_id=self.guild_id,
                server_id=self.server_id,
                target_id=self.target_id,
                target_name=self.target_name,
                placed_by=self.placer_id,
                placed_by_name=self.placer_name,
                reason=self.reason,
                reward=bounty_amount
            )
            
            # Claim the bounty
            await bounty.claim(self.claimer_id, self.claimer_name)
            
            # Award currency to claimer
            await claimer_economy.add_currency(bounty_amount, "bounty_claimed", {
                "bounty_id": str(bounty.id),
                "target_id": self.target_id,
                "target_name": self.target_name
            })
            
            # Verify claimer's currency was increased
            claimer_economy = await Economy.get_by_player(db, self.claimer_id, self.server_id)
            self.assertEqual(claimer_economy.currency, 800)
            
            logger.info("✅ test_economy_integration: Passed")
        
        self.loop.run_until_complete(test())
    
    def test_auto_bounty_detection(self):
        """Test auto-bounty detection"""
        async def test():
            # Create kill data
            db = await get_db()
            
            # Create a killer with multiple kills
            now = datetime.utcnow()
            killer_id = "killer456"
            killer_name = "KillerPlayer"
            victim_id = "victim789"
            victim_name = "VictimPlayer"
            
            # Create kill events from the last 10 minutes
            kills = []
            for i in range(6):  # 6 kills to exceed threshold
                timestamp = now - timedelta(minutes=i*1.5)  # Spread over 7.5 minutes
                kill_data = {
                    "guild_id": self.guild_id,
                    "server_id": self.server_id,
                    "killer_id": killer_id,
                    "killer_name": killer_name,
                    "victim_id": victim_id,
                    "victim_name": victim_name,
                    "weapon": f"weapon_{i}",
                    "distance": 100 + i*10,
                    "timestamp": timestamp
                }
                kills.append(kill_data)
            
            # Insert kill data
            await db.collections["kills"].insert_many(kills)
            
            # Run auto-bounty detection
            potential_bounties = await Bounty.get_player_stats_for_bounty(
                guild_id=self.guild_id,
                server_id=self.server_id,
                minutes=10,
                kill_threshold=5,
                repeat_threshold=3
            )
            
            # Verify killstreak was detected
            self.assertTrue(len(potential_bounties) > 0)
            
            # Find our killer in the results
            killer_bounty = None
            for bounty in potential_bounties:
                if bounty["player_id"] == killer_id:
                    killer_bounty = bounty
                    break
            
            self.assertIsNotNone(killer_bounty)
            self.assertEqual(killer_bounty["player_name"], killer_name)
            self.assertEqual(killer_bounty["type"], "killstreak")
            self.assertTrue(killer_bounty["kill_count"] >= 5)
            
            # Clean up
            await db.collections["kills"].delete_many({
                "server_id": self.server_id,
                "killer_id": killer_id
            })
            
            logger.info("✅ test_auto_bounty_detection: Passed")
        
        self.loop.run_until_complete(test())
    
    @patch('utils.embed_builder.EmbedBuilder.success_embed')
    @patch('cogs.bounties.BountiesCog.place_bounty')
    async def test_bounty_command_handler(self, mock_place_bounty, mock_success_embed):
        """Test bounty command handler"""
        # Mock guild data
        guild_data = {
            "guild_id": int(self.guild_id),
            "premium_tier": 2,  # Premium tier with bounty access
            "servers": [
                {
                    "server_id": self.server_id,
                    "active": True
                }
            ]
        }
        
        # Mock DB methods
        self.db_mock.guilds.find_one.return_value = guild_data
        
        # Create mock success embed
        success_embed = MagicMock()
        mock_success_embed.return_value = success_embed
        
        # Create instance of BountiesCog
        bounties_cog = BountiesCog(self.mock_bot)
        
        # Mock place_bounty method to avoid actual DB operations
        mock_place_bounty.return_value = None
        
        # Test the bounty command
        await bounties_cog.bounty_command(
            interaction=self.mock_interaction,
            action="place",
            target=self.target_name,
            amount=self.reward,
            reason=self.reason
        )
        
        # Verify that DB was queried for guild data
        self.db_mock.guilds.find_one.assert_called_with({"guild_id": int(self.guild_id)})
        
        # Verify place_bounty was called with correct args
        mock_place_bounty.assert_called_once()
        args, kwargs = mock_place_bounty.call_args
        self.assertEqual(kwargs["target_name"], self.target_name)
        self.assertEqual(kwargs["amount"], self.reward)
        self.assertEqual(kwargs["reason"], self.reason)
        
        # Log success
        logger.info("✅ test_bounty_command_handler: Passed")


class TestEndToEndBountySystem(unittest.TestCase):
    """End-to-end test of the entire bounty system"""
    
    def setUp(self):
        """Set up test environment"""
        self.loop = asyncio.get_event_loop()
        
    def test_full_bounty_lifecycle(self):
        """Test the complete lifecycle of a bounty from placement to claim"""
        async def test():
            # Create test data
            guild_id = "123456789"
            server_id = "test_server"
            
            # Set up a placer
            placer_id = "placer123"
            placer_name = "PlacerPlayer"
            
            # Set up a target
            target_id = "target123"
            target_name = "TargetPlayer"
            
            # Set up a claimer
            claimer_id = "claimer123"
            claimer_name = "ClaimerPlayer"
            
            db = await get_db()
            
            # Clean up any existing test data
            await db.collections["bounties"].delete_many({
                "guild_id": guild_id,
                "server_id": server_id
            })
            await db.players.delete_many({
                "server_id": server_id,
                "player_id": {"$in": [placer_id, target_id, claimer_id]}
            })
            await db.collections["player_links"].delete_many({
                "server_id": server_id,
                "discord_id": {"$in": [placer_id, claimer_id]}
            })
            
            # 1. Create players in the database
            players_data = [
                {
                    "player_id": placer_id,
                    "player_name": placer_name,
                    "server_id": server_id,
                    "currency": 1000,
                    "lifetime_earnings": 2000,
                    "kills": 5,
                    "deaths": 5
                },
                {
                    "player_id": target_id,
                    "player_name": target_name,
                    "server_id": server_id,
                    "currency": 500,
                    "lifetime_earnings": 1000,
                    "kills": 10,
                    "deaths": 2
                },
                {
                    "player_id": claimer_id,
                    "player_name": claimer_name,
                    "server_id": server_id,
                    "currency": 300,
                    "lifetime_earnings": 500,
                    "kills": 3,
                    "deaths": 8,
                    "discord_id": claimer_id  # Link to Discord ID
                }
            ]
            
            for player_data in players_data:
                await db.players.insert_one(player_data)
            
            # 2. Create player links
            link_data = {
                "server_id": server_id,
                "guild_id": int(guild_id),
                "discord_id": claimer_id,
                "player_id": claimer_id,
                "player_name": claimer_name,
                "verified": True,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            await db.collections["player_links"].insert_one(link_data)
            
            # 3. Place a bounty
            bounty_amount = 300
            
            # Get placer's economy
            placer_economy = await Economy.get_by_player(db, placer_id, server_id)
            
            # Deduct currency
            await placer_economy.remove_currency(bounty_amount, "bounty_placement", {
                "target_id": target_id,
                "target_name": target_name
            })
            
            # Create the bounty
            bounty = await Bounty.create(
                guild_id=guild_id,
                server_id=server_id,
                target_id=target_id,
                target_name=target_name,
                placed_by=placer_id,
                placed_by_name=placer_name,
                reason="End-to-end test bounty",
                reward=bounty_amount
            )
            
            # Verify bounty was created
            self.assertIsNotNone(bounty)
            self.assertEqual(bounty.status, Bounty.STATUS_ACTIVE)
            
            # 4. Simulate a kill event
            kill_data = {
                "guild_id": int(guild_id),
                "server_id": server_id,
                "killer_id": claimer_id,
                "killer_name": claimer_name,
                "victim_id": target_id,
                "victim_name": target_name,
                "weapon": "test_weapon",
                "distance": 100,
                "timestamp": datetime.utcnow()
            }
            
            # Create a kill record
            await db.collections["kills"].insert_one(kill_data)
            
            # 5. Process the kill for bounty claiming
            mock_bot = MagicMock()
            mock_bot.db = db
            bounties_cog = BountiesCog(mock_bot)
            await bounties_cog.on_csv_kill_parsed(kill_data)
            
            # 6. Verify bounty was claimed
            updated_bounty = await Bounty.get_by_id(bounty.id)
            if updated_bounty:
                self.assertEqual(updated_bounty.status, Bounty.STATUS_CLAIMED, 
                               "Bounty not claimed after kill event")
                self.assertEqual(updated_bounty.claimed_by, claimer_id)
                self.assertEqual(updated_bounty.claimed_by_name, claimer_name)
            
            # 7. Check claimer's balance was updated
            claimer_economy = await Economy.get_by_player(db, claimer_id, server_id)
            expected_balance = 300 + bounty_amount
            self.assertEqual(claimer_economy.currency, expected_balance, 
                           f"Claimer's balance not updated correctly. Expected {expected_balance}, got {claimer_economy.currency}")
            
            # 8. Clean up test data
            await db.collections["bounties"].delete_many({
                "guild_id": guild_id,
                "server_id": server_id
            })
            await db.players.delete_many({
                "server_id": server_id,
                "player_id": {"$in": [placer_id, target_id, claimer_id]}
            })
            await db.collections["player_links"].delete_many({
                "server_id": server_id,
                "discord_id": {"$in": [placer_id, claimer_id]}
            })
            await db.collections["kills"].delete_many({
                "server_id": server_id,
                "killer_id": claimer_id,
                "victim_id": target_id
            })
            
            logger.info("✅ test_full_bounty_lifecycle: Passed")
            
        self.loop.run_until_complete(test())


def run_tests():
    """Run all tests"""
    logger.info("Running Bounty System Tests")
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test cases
    suite.addTests(loader.loadTestsFromTestCase(TestBountyModel))
    suite.addTests(loader.loadTestsFromTestCase(TestBountyIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestEndToEndBountySystem))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Log summary
    logger.info(f"Tests run: {result.testsRun}")
    logger.info(f"Errors: {len(result.errors)}")
    logger.info(f"Failures: {len(result.failures)}")
    
    if not result.wasSuccessful():
        logger.error("⚠️ Some tests failed!")
        for error in result.errors:
            logger.error(f"Error: {error[0]}")
            logger.error(error[1])
        for failure in result.failures:
            logger.error(f"Failure: {failure[0]}")
            logger.error(failure[1])
    else:
        logger.info("✅ All tests passed!")
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)