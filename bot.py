"""
Discord Bot for the Tower of Temptation PvP Statistics Discord Bot.

This module provides:
1. Discord bot setup and configuration
2. Command handling
3. Event handling
4. Scheduled tasks
"""
import os
import re
import sys
import asyncio
import logging
import traceback
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Set, Tuple, Callable, Awaitable, TypeVar, cast

import discord
from discord import app_commands
from discord.ext import commands, tasks

from utils.database import initialize_db, get_db, close_db
from utils.sftp import get_sftp_manager, close_sftp_connections
from utils.async_utils import AsyncCache
from utils.helpers import get_prefix, check_admin_permissions
from utils.embed_builder import EmbedBuilder

from models.server_config import ServerConfig

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot.log", encoding="utf-8"),
    ]
)
logger = logging.getLogger("bot")

# Configure discord.py logging
discord_logger = logging.getLogger("discord")
discord_logger.setLevel(logging.WARNING)

# Define custom bot class
class PvPStatsBot(commands.Bot):
    """Custom Discord bot for PvP statistics"""
    
    def __init__(self):
        """Initialize bot"""
        # Set up intents
        intents = discord.Intents.default()
        intents.message_content = True  # Needed for prefix commands
        intents.members = True          # Needed for member-related features
        
        # Initialize bot with dynamic prefix
        super().__init__(
            command_prefix=get_prefix,
            intents=intents,
            help_command=None,  # Custom help command will be added later
            case_insensitive=True,
            description="Tower of Temptation PvP Statistics Discord Bot"
        )
        
        # Bot state
        self.startup_time = datetime.utcnow()
        self.synced = False
        self.loaded_extensions = False
        self.ready = False
        self.maintenance_mode = False
        self.db_connected = False
        
        # Last error for logging
        self.last_error: Optional[Exception] = None
        self.last_error_time: Optional[datetime] = None
        
        # Extension and cog tracking
        self.extension_state: Dict[str, bool] = {}
        self.failed_extensions: Dict[str, str] = {}
        
    async def setup_hook(self) -> None:
        """Bot setup hook - runs before bot starts"""
        # Initialize database connection
        self.db_connected = await initialize_db()
        if not self.db_connected:
            logger.error("Failed to connect to database, some features may not work")
        
        # Start background tasks
        self.update_stats_task.start()
        self.cleanup_task.start()
        
    async def on_ready(self):
        """Event handler for when bot is ready"""
        if self.ready:
            # Reconnection event
            logger.info(f"Bot reconnected as {self.user} (ID: {self.user.id})")
            return
            
        # First ready event
        logger.info(f"Bot started as {self.user} (ID: {self.user.id})")
        
        # Load extensions
        if not self.loaded_extensions:
            await self.load_extensions()
        
        # Sync app commands
        if not self.synced:
            await self.tree.sync()
            self.synced = True
            logger.info("Synced application commands")
        
        # Set bot status
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="PvP statistics | !help"
            )
        )
        
        # Mark bot as ready
        self.ready = True
        
        # Log guild count
        logger.info(f"Bot is in {len(self.guilds)} guilds")
        
    async def load_extensions(self) -> None:
        """Load cog extensions"""
        # Define extension directories
        cog_dir = "cogs"
        
        # Track extension status
        self.extension_state = {}
        self.failed_extensions = {}
        
        # Create cogs directory if it doesn't exist
        os.makedirs(cog_dir, exist_ok=True)
        
        # Find and load extensions
        for filename in os.listdir(cog_dir):
            # Skip non-Python files and special files
            if not filename.endswith(".py") or filename.startswith("_"):
                continue
                
            # Get extension name
            extension = f"{cog_dir}.{filename[:-3]}"
            
            try:
                # Load extension
                await self.load_extension(extension)
                self.extension_state[extension] = True
                logger.info(f"Loaded extension: {extension}")
                
            except Exception as e:
                self.extension_state[extension] = False
                self.failed_extensions[extension] = str(e)
                logger.error(f"Failed to load extension {extension}: {str(e)}")
                logger.error(traceback.format_exc())
        
        # Mark extensions as loaded
        self.loaded_extensions = True
        
        # Log extension status
        loaded_count = sum(1 for status in self.extension_state.values() if status)
        total_count = len(self.extension_state)
        logger.info(f"Loaded {loaded_count}/{total_count} extensions")
    
    async def on_error(self, event_method: str, *args, **kwargs) -> None:
        """Global error handler for bot events
        
        Args:
            event_method: Event method name
            *args: Event arguments
            **kwargs: Event keyword arguments
        """
        # Get exception info
        exc_type, exc_value, exc_traceback = sys.exc_info()
        
        # Store last error
        self.last_error = exc_value
        self.last_error_time = datetime.utcnow()
        
        # Log error
        logger.error(f"Error in {event_method}")
        logger.error(''.join(traceback.format_exception(exc_type, exc_value, exc_traceback)))
    
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        """Error handler for commands
        
        Args:
            ctx: Command context
            error: Command error
        """
        # Store last error
        self.last_error = error
        self.last_error_time = datetime.utcnow()
        
        # Get original error if wrapped
        error = getattr(error, "original", error)
        
        if isinstance(error, commands.CommandNotFound):
            # Command not found error
            return
            
        elif isinstance(error, commands.UserInputError):
            # User input error
            embed = await EmbedBuilder.error_embed(
                title="Command Error",
                description=f"Invalid command usage: {str(error)}",
                footer_text=f"Type {ctx.prefix}help {ctx.command} for help" if ctx.command else None
            )
            
        elif isinstance(error, commands.CheckFailure):
            # Check failure (permissions, etc.)
            embed = await EmbedBuilder.error_embed(
                title="Permission Denied",
                description="You don't have permission to use this command."
            )
            
        elif isinstance(error, commands.CommandOnCooldown):
            # Command on cooldown
            embed = await EmbedBuilder.warning_embed(
                title="Command Cooldown",
                description=f"This command is on cooldown. Try again in {error.retry_after:.1f} seconds."
            )
            
        elif isinstance(error, commands.DisabledCommand):
            # Disabled command
            embed = await EmbedBuilder.warning_embed(
                title="Command Disabled",
                description="This command is currently disabled."
            )
            
        else:
            # Generic error
            logger.error(f"Command error in {ctx.command}: {str(error)}")
            logger.error(traceback.format_exc())
            
            embed = await EmbedBuilder.error_embed(
                title="Command Error",
                description=f"An error occurred: {str(error)}"
            )
        
        # Send error message
        await ctx.send(embed=embed)
    
    async def on_guild_join(self, guild: discord.Guild) -> None:
        """Event handler for when bot joins a guild
        
        Args:
            guild: Guild that bot joined
        """
        logger.info(f"Bot joined guild: {guild.name} (ID: {guild.id}) | Members: {guild.member_count}")
        
        # Check if server config exists
        server_config = await ServerConfig.get_by_guild_id(guild.id)
        
        if not server_config:
            # Create server config
            server_config = await ServerConfig.create(
                guild_id=guild.id,
                guild_name=guild.name
            )
            
            # Log creation
            if server_config:
                logger.info(f"Created server config for guild: {guild.name} (ID: {guild.id})")
            else:
                logger.error(f"Failed to create server config for guild: {guild.name} (ID: {guild.id})")
    
    async def on_guild_remove(self, guild: discord.Guild) -> None:
        """Event handler for when bot leaves a guild
        
        Args:
            guild: Guild that bot left
        """
        logger.info(f"Bot left guild: {guild.name} (ID: {guild.id}) | Members: {guild.member_count}")
        
        # Note: We don't delete the server config in case the bot is re-added later
    
    async def on_guild_update(self, before: discord.Guild, after: discord.Guild) -> None:
        """Event handler for when guild is updated
        
        Args:
            before: Guild before update
            after: Guild after update
        """
        # Check if name changed
        if before.name != after.name:
            logger.info(f"Guild renamed: {before.name} -> {after.name} (ID: {after.id})")
            
            # Update server config
            server_config = await ServerConfig.get_by_guild_id(after.id)
            
            if server_config:
                server_config.guild_name = after.name
                await server_config.update()
                logger.info(f"Updated server config for guild: {after.name} (ID: {after.id})")
    
    async def on_message(self, message: discord.Message) -> None:
        """Event handler for messages
        
        Args:
            message: Message received
        """
        # Ignore bot messages
        if message.author.bot:
            return
            
        # Process commands
        await self.process_commands(message)
    
    @tasks.loop(minutes=30)
    async def update_stats_task(self) -> None:
        """Scheduled task to update statistics from SFTP servers"""
        # Skip if in maintenance mode
        if self.maintenance_mode:
            return
            
        logger.info("Running scheduled statistics update task")
        
        try:
            # Get all server configurations
            server_configs = await ServerConfig.get_all()
            
            # Filter enabled servers with SFTP configuration
            configured_servers = [
                config for config in server_configs 
                if config.enabled and config.sftp_host and config.sftp_username
            ]
            
            # Update statistics for each server
            for config in configured_servers:
                # Check if update is due
                if (
                    config.last_stats_post and
                    datetime.utcnow() - config.last_stats_post < timedelta(minutes=config.update_interval)
                ):
                    # Skip if update not due
                    continue
                    
                logger.info(f"Updating statistics for server: {config.guild_name} (ID: {config.guild_id})")
                
                try:
                    # Update statistics (placeholder for now)
                    # This will be implemented in the appropriate cog
                    # await self.get_cog("StatisticsManager").update_server_statistics(config)
                    
                    # Update last stats post timestamp
                    config.last_stats_post = datetime.utcnow()
                    await config.update()
                    
                except Exception as e:
                    logger.error(f"Error updating statistics for server {config.guild_id}: {str(e)}")
        
        except Exception as e:
            logger.error(f"Error in update_stats_task: {str(e)}")
            logger.error(traceback.format_exc())
    
    @update_stats_task.before_loop
    async def before_update_stats_task(self) -> None:
        """Run before update_stats_task starts"""
        await self.wait_until_ready()
    
    @tasks.loop(hours=24)
    async def cleanup_task(self) -> None:
        """Scheduled task to clean up database and cache"""
        # Skip if in maintenance mode
        if self.maintenance_mode:
            return
            
        logger.info("Running scheduled cleanup task")
        
        try:
            # Clear cache
            AsyncCache.clear()
            logger.info("Cleared cache")
            
            # Close and reopen database connection
            if self.db_connected:
                await close_db()
                self.db_connected = await initialize_db()
                logger.info("Refreshed database connection")
            
            # Close SFTP connections
            closed = await close_sftp_connections()
            logger.info(f"Closed {closed} SFTP connections")
            
        except Exception as e:
            logger.error(f"Error in cleanup_task: {str(e)}")
            logger.error(traceback.format_exc())
    
    @cleanup_task.before_loop
    async def before_cleanup_task(self) -> None:
        """Run before cleanup_task starts"""
        await self.wait_until_ready()
        
    async def close(self) -> None:
        """Close bot and clean up resources"""
        # Cancel tasks
        self.update_stats_task.cancel()
        self.cleanup_task.cancel()
        
        # Close connections
        await close_db()
        await close_sftp_connections()
        
        # Close bot
        await super().close()

# Create and run bot
def run_bot() -> None:
    """Create and run bot instance"""
    # Create bot instance
    bot = PvPStatsBot()
    
    # Get token from environment
    token = os.environ.get("DISCORD_TOKEN")
    
    if not token:
        logger.error("DISCORD_TOKEN environment variable not set")
        return
    
    # Run bot
    try:
        bot.run(token)
    except discord.LoginFailure:
        logger.error("Invalid Discord token")
    except Exception as e:
        logger.error(f"Error starting bot: {str(e)}")
        logger.error(traceback.format_exc())

# Run bot if executed directly
if __name__ == "__main__":
    run_bot()