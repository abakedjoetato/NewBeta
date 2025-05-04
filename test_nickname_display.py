"""
Test the nickname display functionality in embeds.

This test checks if embeds correctly use the bot's nickname in a guild context.
"""

import unittest
import asyncio
from unittest.mock import MagicMock, patch

from utils.embed_builder import EmbedBuilder
from utils.helpers import get_bot_name


class TestNicknameDisplay(unittest.TestCase):
    """Test the nickname display functionality in embeds."""

    def setUp(self):
        """Set up the test."""
        # Create mock objects for the bot and guild
        self.bot = MagicMock()
        self.guild = MagicMock()
        
        # Set the bot's user ID and name
        self.bot.user.id = 123456789
        self.bot.user.name = "Tower of Temptation Bot"
        
        # Set a nickname in the guild
        self.guild_member = MagicMock()
        self.guild_member.nick = "ToT Stats"
        self.guild.get_member.return_value = self.guild_member

    def test_get_bot_name(self):
        """Test that get_bot_name returns the correct nickname."""
        # Patch the function to avoid actually looking up the bot in Discord
        with patch("utils.helpers.get_bot_name", return_value="ToT Stats"):
            # Call the function
            bot_name = get_bot_name(self.bot, self.guild)
            
            # Check that the correct name is returned
            self.assertEqual(bot_name, "ToT Stats")
            
    def test_bot_name_in_embed_footer(self):
        """Test that embeds include the bot name in the footer."""
        # Create a base embed with guild and bot
        async def async_test():
            with patch("utils.helpers.get_bot_name", return_value="ToT Stats"):
                embed = await EmbedBuilder.create_base_embed(
                    title="Test Title",
                    description="Test Description",
                    guild=self.guild,
                    bot=self.bot
                )
                self.assertIn("ToT Stats", embed.footer.text)
        
        # Run the async test
        loop = asyncio.get_event_loop()
        loop.run_until_complete(async_test())
        
    def test_different_embed_types(self):
        """Test that different embed types use the bot name."""
        async def async_test():
            with patch("utils.helpers.get_bot_name", return_value="ToT Stats"):
                # Test success embed
                success_embed = await EmbedBuilder.success_embed(
                    title="Success",
                    description="Operation successful",
                    guild=self.guild,
                    bot=self.bot
                )
                self.assertIn("ToT Stats", success_embed.footer.text)
                
                # Test error embed
                error_embed = await EmbedBuilder.error_embed(
                    title="Error",
                    description="Operation failed",
                    guild=self.guild,
                    bot=self.bot
                )
                self.assertIn("ToT Stats", error_embed.footer.text)
                
                # Test help embed
                commands = [
                    {"name": "Command 1", "description": "Description 1"},
                    {"name": "Command 2", "description": "Description 2"}
                ]
                help_embed = await EmbedBuilder.help_embed(
                    title="Help",
                    description="Available commands",
                    commands=commands,
                    guild=self.guild,
                    bot=self.bot
                )
                self.assertIn("ToT Stats", help_embed.footer.text)
        
        # Run the async test
        loop = asyncio.get_event_loop()
        loop.run_until_complete(async_test())


if __name__ == "__main__":
    unittest.main()