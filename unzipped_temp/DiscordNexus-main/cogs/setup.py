"""
Setup commands for configuring servers and channels
"""
import logging
import os
import re
import psutil
import discord
from discord.ext import commands
from discord import app_commands
from typing import Dict, List, Any, Optional
import asyncio
from datetime import datetime

from models.guild import Guild
from models.server import Server
from utils.sftp import SFTPClient
from utils.embed_builder import EmbedBuilder
from utils.helpers import has_admin_permission
from utils.parsers import CSVParser

logger = logging.getLogger(__name__)

# Cache for server list to improve autocomplete performance
SERVER_CACHE = {}
SERVER_CACHE_TIMEOUT = 300  # 5 minutes

async def server_id_autocomplete(interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
    """Autocomplete for server selection by name, returns server_id as value"""
    try:
        # Get guild data directly
        guild_data = await interaction.client.db.guilds.find_one({"guild_id": interaction.guild_id})
        if not guild_data or "servers" not in guild_data:
            return []

        choices = []
        for server in guild_data["servers"]:
            server_id = str(server.get("server_id", ""))  # Ensure string type
            server_name = server.get("server_name", server.get("name", "Unknown"))
            
            # Check if current input matches server name or ID
            if not current or current.lower() in server_name.lower() or current.lower() in server_id.lower():
                choices.append(app_commands.Choice(
                    name=f"{server_name} ({server_id})",
                    value=server_id
                ))

        return choices[:25]  # Discord has a limit of 25 choices

        # Get detailed information about the command structure
        if "options" in interaction.data:
            # Log all options data
            options = interaction.data["options"]
            for option in options:
                option_data = {
                    "name": option.get("name", "unknown"),
                    "type": option.get("type", "unknown"),
                    "focused": option.get("focused", False)
                }

                # If this option has suboptions (like a subcommand), extract those
                if "options" in option:
                    option_data["sub_options"] = []
                    for sub_option in option["options"]:
                        sub_option_data = {
                            "name": sub_option.get("name", "unknown"),
                            "type": sub_option.get("type", "unknown"),
                            "focused": sub_option.get("focused", False)
                        }
                        option_data["sub_options"].append(sub_option_data)

                command_info["options_data"].append(option_data)

        # Determine which subcommand we're in
        subcommand = None
        if command_info["command_name"] == "setup" and command_info["options_data"]:
            # The first option in setup commands is the subcommand
            subcommand = command_info["options_data"][0].get("name")

        # Log extensive debug information
        logger.info(f"Autocomplete call for: {command_info['command_name']}")
        logger.info(f"Subcommand detected: {subcommand}")
        logger.info(f"Current input: '{current}'")
        logger.info(f"Focused option: {command_info['focused_option']}")
        logger.info(f"Full command data: {command_info}")
        logger.info(f"Guild ID: {interaction.guild_id}")

        # Get user's guild ID
        guild_id = interaction.guild_id

        # Determine if we need to bypass cache based on subcommand
        # Safely get the subcommand name if available
        subcommand_detected = None
        if command_info["options_data"] and len(command_info["options_data"]) > 0:
            first_option = command_info["options_data"][0]
            if isinstance(first_option, dict):
                subcommand_detected = first_option.get("name")

        # These commands always need fresh data from the database
        force_fresh_data = subcommand_detected in ["historicalparse", "diagnose", "removeserver", "setupchannels"]

        # Log the detection information
        logger.info(f"Detected subcommand: {subcommand_detected}, forcing fresh data: {force_fresh_data}")

        if force_fresh_data:
            logger.info(f"Bypassing cache for {subcommand_detected} command to ensure latest data")

        # Get server data (either cached or fresh)
        cog = interaction.client.get_cog("Setup")
        if not cog:
            # Fall back to a simple fetch if cog not available
            bot = interaction.client

            # Use timeout protection for database operation
            try:
                guild_data = await asyncio.wait_for(
                    bot.db.guilds.find_one({"guild_id": guild_id}),
                    timeout=1.0  # 1 second timeout for autocomplete
                )
                servers = []

                if guild_data and "servers" in guild_data:
                    # Get server data
                    servers = guild_data["servers"]

                    # Ensure all server_ids are strings
                    for server in servers:
                        if "server_id" in server:
                            server["server_id"] = str(server["server_id"])

                    # Ensure all server_ids are strings
                    for server in servers:
                        if "server_id" in server:
                            server["server_id"] = str(server["server_id"])

                    # Ensure all server_ids are strings
                    for server in servers:
                        if "server_id" in server:
                            server["server_id"] = str(server["server_id"])
            except asyncio.TimeoutError:
                logger.warning(f"Timeout in server_id_autocomplete for guild {guild_id}")
                servers = []  # Empty result on timeout
            except Exception as e:
                logger.error(f"Error fetching guild data in autocomplete: {e}")
                servers = []
        else:
            # Try to get data from cache first (unless we're forcing fresh data)
            cache_key = f"servers_{guild_id}"
            cached_data = None if force_fresh_data else SERVER_CACHE.get(cache_key)

            use_cache = (not force_fresh_data and 
                         cached_data and 
                         (datetime.now() - cached_data["timestamp"]).total_seconds() < SERVER_CACHE_TIMEOUT)

            if use_cache:
                # Use cached data if it's still valid
                servers = cached_data["servers"]
                logger.info(f"Using cached server data for guild {guild_id}: {len(servers)} servers")
            else:
                # Fetch fresh data and update cache with timeout protection
                try:
                    # Log why we're fetching fresh data
                    if force_fresh_data:
                        logger.info(f"Fetching fresh server data for subcommand {subcommand_detected}")
                    elif not cached_data:
                        logger.info("No cached data available, fetching fresh data")
                    else:
                        logger.info("Cache expired, fetching fresh data")

                    guild_data = await asyncio.wait_for(
                        cog.bot.db.guilds.find_one({"guild_id": guild_id}),
                        timeout=1.0  # 1 second timeout for autocomplete
                    )
                    # Get servers from cache
                    servers = []

                    if guild_data and "servers" in guild_data:
                        # Get server data and ensure server_ids are strings
                        seen_server_ids = set()  # Track processed server IDs to avoid duplicates
                        for server in guild_data["servers"]:
                            server_copy = server.copy()
                            if "server_id" in server_copy:
                                server_copy["server_id"] = str(server_copy["server_id"])
                                # Only add if we haven't seen this server ID before
                                if server_copy["server_id"] not in seen_server_ids:
                                    seen_server_ids.add(server_copy["server_id"])
                                    servers.append(server_copy)
                        logger.info(f"Processed {len(servers)} unique servers for autocomplete")

                    # Update cache with deduped servers
                    SERVER_CACHE[cache_key] = {
                        "timestamp": datetime.now(),
                        "servers": servers
                    }
                    logger.info(f"Updated cache for guild {guild_id} with {len(servers)} unique servers")
                except asyncio.TimeoutError:
                    logger.warning(f"Timeout in server_id_autocomplete cache refresh for guild {guild_id}")
                    # Provide empty results on timeout
                    servers = []
                except Exception as e:
                    logger.error(f"Error refreshing guild data in autocomplete: {e}")
                    servers = []

        # Add timeout protection for response
        try:
            # Filter servers based on current input
            choices = []
            for server in servers:
                # Always ensure server_id is a string for consistent comparison
                raw_server_id = server.get("server_id", "")
                server_id = str(raw_server_id) if raw_server_id is not None else ""

            # Ensure we only process if interaction hasn't timed out
            if not interaction.response.is_done():
                for server in servers:
                    # Always ensure server_id is a string for consistent comparison
                    raw_server_id = server.get("server_id", "")
                    server_id = str(raw_server_id) if raw_server_id is not None else ""

                    # Get proper server name, check both keys: 'name' and 'server_name'
                    server_name = server.get("server_name", server.get("name", "Unknown"))

                    # Make sure we have a valid display name
                    if server_name == "Unknown" and server_id:
                        server_name = f"Server {server_id}"

                    # Check if current input matches server name or ID
                    # For empty input (very important for auto-complete), show all options
                    # For non-empty input, filter by server name or ID
                    if not current or current.lower() in server_name.lower() or current.lower() in server_id.lower():
                        # Format: "ServerName (ServerID)"
                        choices.append(app_commands.Choice(
                            name=f"{server_name} ({server_id})",
                            value=server_id  # Ensure this is a string
                        ))

                return choices[:25]  # Discord has a limit of 25 choices
        except asyncio.TimeoutError:
            logger.warning("Autocomplete response timed out.")
            return []
        except Exception as e:
            logger.error(f"Error in server_id_autocomplete: {e}", exc_info=True)
            return []

    except Exception as e:
        logger.error(f"Error in server_id_autocomplete: {e}", exc_info=True)
        return []

logger = logging.getLogger(__name__)

class Setup(commands.Cog):
    """Setup commands for configuring servers and channels"""

    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_group(name="setup", description="Server setup commands")
    @commands.guild_only()
    async def setup(self, ctx):
        """Setup command group"""
        if ctx.invoked_subcommand is None:
            await ctx.send("Please specify a subcommand.")

    @setup.command(name="addserver", description="Add a game server to track PvP stats")
    @app_commands.describe(
        server_name="Friendly name to display for this server",
        host="SFTP host address",
        port="SFTP port",
        username="SFTP username",
        password="SFTP password",
        server_id="Unique ID for the server (letters, numbers, underscores only)"
    )
    @app_commands.guild_only()
    async def add_server(self, ctx, server_name: str, host: str, port: int, username: str, password: str, server_id: str):
        """Add a new server to track"""
        try:
            # Defer response to prevent timeout
            await ctx.defer()
            # Get guild model for themed embed
            guild_data = None
            guild_model = None
            try:
                guild_data = await self.bot.db.guilds.find_one({"guild_id": ctx.guild.id})
                if guild_data:
                    guild_model = Guild(self.bot.db, guild_data)
            except Exception as e:
                logger.warning(f"Error getting guild model: {e}")

            # Check permissions
            if not await self._check_permission(ctx):
                return

            # Validate server ID (no spaces, special chars except underscore)
            if not re.match(r'^[a-zA-Z0-9_]+$', server_id):
                embed = EmbedBuilder.create_error_embed(
                    "Invalid Server ID",
                    "Server ID can only contain letters, numbers, and underscores."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return

            # Store SFTP information
            sftp_info = {
                "host": host,
                "port": port,
                "username": username,
                "password": password
            }

            # Validate SFTP info
            if not host or not username or not password:
                embed = EmbedBuilder.create_error_embed(
                    "Invalid SFTP Information",
                    "Please provide valid host, username, and password for SFTP connection."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return

            # Get or create guild
            guild = await Guild.get_by_id(self.bot.db, ctx.guild.id)
            if not guild:
                guild = await Guild.create(self.bot.db, ctx.guild.id, ctx.guild.name)

            # Check if we can add more servers (premium tier limit)
            if not guild.check_feature_access("killfeed"):
                embed = EmbedBuilder.create_error_embed(
                    "Feature Disabled",
                    "This guild does not have the Killfeed feature enabled. Please contact an administrator."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return

            # Check if we're at server limit
            max_servers = guild.get_max_servers()
            if len(guild.servers) >= max_servers:
                embed = EmbedBuilder.create_error_embed(
                    "Server Limit Reached",
                    f"This guild has reached the maximum number of servers ({max_servers}) for its premium tier."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return

            # Check if server ID already exists
            for server in guild.servers:
                if server.get("server_id") == server_id:
                    embed = EmbedBuilder.create_error_embed(
                        "Server Exists",
                        f"A server with ID '{server_id}' already exists in this guild."
                    , guild=guild_model)
                    await ctx.send(embed=embed)
                    return

            # Initial response
            embed = EmbedBuilder.create_base_embed(
                "Adding Server",
                f"Testing connection to {server_name}..."
            , guild=guild_model)
            message = await ctx.send(embed=embed)

            # Create SFTP client to test connection
            sftp_client = SFTPClient(
                host=sftp_info["host"],
                port=sftp_info["port"],
                username=sftp_info["username"],
                password=sftp_info["password"],
                server_id=server_id
            )

            # Test connection
            connected = await sftp_client.connect()
            if not connected:
                embed = EmbedBuilder.create_error_embed(
                    "Connection Failed",
                    f"Failed to connect to SFTP server: {sftp_client.last_error}"
                , guild=guild_model)
                await message.edit(embed=embed)
                return

            # Connection successful - skip CSV file check
            # The historical parser will find CSV files on its own
            # This eliminates redundant SFTP operations and reduces connection time
            logger.info(f"SFTP connection successful for server {server_id}. Skipping redundant CSV file check.")
            csv_files = []  # Empty placeholder since we don't need to check

            # Check if we can find log file
            embed = EmbedBuilder.create_base_embed(
                "Adding Server",
                f"Connection successful. Looking for log file..."
            , guild=guild_model)
            await message.edit(embed=embed)

            log_file = await sftp_client.get_log_file()
            log_found = log_file is not None

            # Create server object
            server_data = {
                "server_id": server_id,
                "server_name": server_name,
                "guild_id": ctx.guild.id,
                "sftp_host": sftp_info["host"],
                "sftp_port": sftp_info["port"],
                "sftp_username": sftp_info["username"],
                "sftp_password": sftp_info["password"],
                "last_csv_line": 0,
                "last_log_line": 0
            }

            # Add server to guild
            add_result = await guild.add_server(server_data)
            if not add_result:
                embed = EmbedBuilder.create_error_embed(
                    "Error Adding Server",
                    "Failed to add server to the database. This may be due to a server limit restriction."
                , guild=guild_model)
                await message.edit(embed=embed)
                await sftp_client.disconnect()
                return

            # Success message
            embed = EmbedBuilder.create_success_embed(
                "Server Added Successfully",
                f"Server '{server_name}' has been added and is ready for channel setup."
            , guild=guild_model)

            # Add connection details
            connection_status = [
                f"SFTP Connection: Successful",
                f"Log File: {'Found' if log_found else 'Not found'}",
                f"CSV Files: Will be located during historical parsing"
            ]
            embed.add_field(
                name="Connection Status", 
                value="\n".join(connection_status),
                inline=False
            )

            # Add next steps
            next_steps = [
                "Use `/setup channels <server>` to configure notification channels.",
                "Use `/killfeed start <server>` to start monitoring the killfeed.",
                "If you have premium, use `/events start <server>` to monitor game events."
            ]
            embed.add_field(
                name="Next Steps", 
                value="\n".join(next_steps),
                inline=False
            )

            await message.edit(embed=embed)
            await sftp_client.disconnect()

            # Check if guild has stats feature and start historical parsing if available
            try:
                if guild.check_feature_access("stats"):
                    # Update the message with parsing info
                    embed = EmbedBuilder.create_info_embed(
                        "Historical Parse Starting",
                        f"Starting automatic historical data parsing for server '{server_name}'."
                        + "\n\nThis process will run in the background and may take some time depending on the amount of data."
                    , guild=guild_model)
                    await message.edit(embed=embed)

                    # Create the server object for historical parsing
                    server = None
                    for s in guild.servers:
                        if s.get("server_id") == server_id:
                            server = Server(self.bot.db, s)
                            break

                    if server:
                        # Start background task for historical parsing
                        task = asyncio.create_task(self._historical_parse_task(server, message))

                        # Store task
                        task_name = f"historical_{ctx.guild.id}_{server_id}"
                        self.bot.background_tasks[task_name] = task

                        # Clean up task when done
                        task.add_done_callback(lambda t: self.bot.background_tasks.pop(task_name, None))
                        logger.info(f"Started automatic historical parsing for server {server_id} in guild {ctx.guild.id}")
            except Exception as parse_e:
                logger.error(f"Error starting automatic historical parse: {parse_e}", exc_info=True)
                # We don't want to fail the server add if historical parsing fails, so just log the error

        except Exception as e:
            logger.error(f"Error adding server: {e}", exc_info=True)
            embed = EmbedBuilder.create_error_embed(
                "Error",
                f"An error occurred while adding the server: {e}"
            , guild=guild_model)
            await ctx.send(embed=embed)

    @setup.command(name="removeserver", description="Remove a server")
    @app_commands.describe(server_id="Select a server by name to remove")
    @app_commands.autocomplete(server_id=server_id_autocomplete)
    async def remove_server(self, ctx, server_id: str):
        """Remove a server from tracking"""
        # Ensure server_id is a string for consistent comparison
        server_id = str(server_id) if server_id is not None else ""
        logger.info(f"Normalized server_id to string: {server_id}")

        try:
            # Defer response to prevent timeout
            await ctx.defer()

            # Get guild model for themed embed

            guild_data = None
            guild_model = None
            try:
                guild_data = await self.bot.db.guilds.find_one({"guild_id": ctx.guild.id})
                if guild_data:
                    guild_model = Guild(self.bot.db, guild_data)
            except Exception as e:
                logger.warning(f"Error getting guild model: {e}")

            # Check permissions
            if not await self._check_permission(ctx):
                return

            # Get guild
            guild = await Guild.get_by_id(self.bot.db, ctx.guild.id)
            if not guild:
                embed = EmbedBuilder.create_error_embed(
                    "Guild Not Set Up",
                    "This guild is not set up. Please add a server first."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return

            # Check if server exists
            server_exists = False
            server_name = server_id
            for server in guild.servers:
                server_id_from_db = server.get("server_id")
                # Ensure string comparison for compatibility with autocomplete
                if str(server_id_from_db) == str(server_id):
                    server_exists = True
                    server_name = server.get("server_name", server_id)
                    break

            if not server_exists:
                embed = EmbedBuilder.create_error_embed(
                    "Server Not Found",
                    f"Server with ID '{server_id}' not found in this guild."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return

            # Confirmation message
            embed = EmbedBuilder.create_base_embed(
                "Confirm Server Removal",
                f"Are you sure you want to remove server '{server_name}' ({server_id})?\n\n"
                "This will:\n"
                "• Stop all monitoring tasks\n"
                "• Delete ALL historical kill data\n"
                "• Delete ALL player statistics\n"
                "• Delete ALL economy data\n\n"
                "⚠️ This action CANNOT be undone and ALL statistics will be permanently lost! ⚠️"
            )

            # Create confirmation buttons
            class ConfirmView(discord.ui.View):
                def __init__(self, timeout=60):
                    super().__init__(timeout=timeout)
                    self.value = None

                @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger)
                async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
                    if interaction.user.id != ctx.author.id:
                        await interaction.response.send_message("You cannot use this button.", ephemeral=True)
                        return
                    self.value = True
                    self.stop()
                    await interaction.response.defer()

                @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
                async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
                    if interaction.user.id != ctx.author.id:
                        await interaction.response.send_message("You cannot use this button.", ephemeral=True)
                        return
                    self.value = False
                    self.stop()
                    await interaction.response.defer()

            # Send confirmation message
            view = ConfirmView()
            message = await ctx.send(embed=embed, view=view)

            # Wait for confirmation
            await view.wait()

            if view.value is None:
                # Timeout
                embed = EmbedBuilder.create_error_embed(
                    "Timed Out",
                    "Server removal cancelled due to timeout."
                , guild=guild_model)
                await message.edit(embed=embed, view=None)
                return

            if not view.value:
                # Cancelled
                embed = EmbedBuilder.create_error_embed(
                    "Cancelled",
                    "Server removal cancelled."
                , guild=guild_model)
                await message.edit(embed=embed, view=None)
                return

            # Update message
            embed = EmbedBuilder.create_base_embed(
                "Removing Server",
                f"Removing server '{server_name}' and stopping all monitoring tasks..."
            , guild=guild_model)
            await message.edit(embed=embed, view=None)

            # Stop running tasks
            for task_type in ["killfeed", "events"]:
                task_name = f"{task_type}_{ctx.guild.id}_{server_id}"
                if task_name in self.bot.background_tasks:
                    task = self.bot.background_tasks[task_name]
                    task.cancel()
                    self.bot.background_tasks.pop(task_name)

            # Remove SFTP connection if exists
            sftp_key = f"{ctx.guild.id}_{server_id}"
            if sftp_key in self.bot.sftp_connections:
                client = self.bot.sftp_connections.pop(sftp_key)
                await client.disconnect()

            # Remove server from database
            removed = await guild.remove_server(server_id)

            if removed:
                embed = EmbedBuilder.create_success_embed(
                    "Server Removed",
                    f"Server '{server_name}' has been completely removed.\n\n" +
                    "All related data has been permanently deleted including:\n" +
                    "• All kill records\n" +
                    "• All player statistics\n" +
                    "• All economy and currency data\n\n" +
                    "To add this server again, use the `/setup addserver` command."
                , guild=guild_model)
                await message.edit(embed=embed)
            else:
                embed = EmbedBuilder.create_error_embed(
                    "Error",
                    f"Failed to remove server '{server_name}' from the database."
                , guild=guild_model)
                await message.edit(embed=embed)

        except Exception as e:
            logger.error(f"Error removing server: {e}", exc_info=True)
            embed = EmbedBuilder.create_error_embed(
                "Error",
                f"An error occurred while removing the server: {e}"
            , guild=guild_model)
            await ctx.send(embed=embed)

    @setup.command(name="setupchannels", description="Configure notification channels for a server")
    @app_commands.describe(
        server_id="Select a server by name to configure",
        killfeed_channel="Channel for killfeed notifications",
        events_channel="Channel for event notifications",
        connections_channel="Channel for player connection notifications",
        economy_channel="Channel for economy notifications (premium tier 2+)",
        voice_status_channel="Voice channel to update with player count"
    )
    @app_commands.autocomplete(server_id=server_id_autocomplete)
    async def setup_channels(self, ctx, 
                            server_id: str,
                            killfeed_channel: discord.TextChannel = None,
                            events_channel: discord.TextChannel = None,
                            connections_channel: discord.TextChannel = None,
                            economy_channel: discord.TextChannel = None,
                            voice_status_channel: discord.VoiceChannel = None):
        """Configure notification channels for a server with optimized performance"""
        # Initialize guild_model at the start to avoid UnboundLocalError
        guild_model = None
        try:
            # Get guild model for themed embed before any operations
            try:
                guild_data = await self.bot.db.guilds.find_one({"guild_id": ctx.guild.id})
                if guild_data:
                    guild_model = Guild(self.bot.db, guild_data)
            except Exception as e:
                logger.warning(f"Error getting guild model: {e}")

            # Defer response immediately to prevent timeout
            await ctx.defer()

            # Initialize tracking for progress updates
            async def update_progress(message, step, total_steps, current_action):
                embed = discord.Embed(
                    title="Setting Up Channels",
                    description=f"Progress: {step}/{total_steps}\nCurrently: {current_action}",
                    color=discord.Color.blue()
                )
                embed.set_footer(text="Please wait while channels are being configured...")
                try:
                    await message.edit(embed=embed)
                except Exception as e:
                    logger.warning(f"Could not update progress: {e}")

            # Create initial progress message
            progress_embed = discord.Embed(
                title="Setting Up Channels",
                description="Starting channel configuration...",
                color=discord.Color.blue()
            )
            progress_message = await ctx.send(embed=progress_embed)

            # Step 1: Validate server ID and get server data
            await update_progress(progress_message, 1, 4, "Validating server configuration")

            # Get server with timeout protection
            try:
                async with asyncio.timeout(5.0):  # 5 second timeout
                    server = await Server.get_by_id(self.bot.db, server_id, ctx.guild.id)
                    if not server:
                        raise ValueError(f"Server {server_id} not found")
            except asyncio.TimeoutError:
                embed = discord.Embed(
                    title="Error",
                    description="Database operation timed out. Please try again.",
                    color=discord.Color.red()
                )
                await progress_message.edit(embed=embed)
                return
            except Exception as e:
                embed = discord.Embed(
                    title="Error",
                    description=f"Failed to find server: {e}",
                    color=discord.Color.red()
                )
                await progress_message.edit(embed=embed)
                return

            # Step 2: Prepare channel data
            await update_progress(progress_message, 2, 4, "Processing channel information")

            update_data = {}
            channel_updates = []

            def safe_channel_id(channel):
                return int(channel.id) if channel is not None else None

            # Process each channel type
            channels = {
                "killfeed_channel_id": killfeed_channel,
                "events_channel_id": events_channel,
                "connections_channel_id": connections_channel,
                "economy_channel_id": economy_channel,
                "voice_status_channel_id": voice_status_channel
            }

            for channel_type, channel in channels.items():
                if channel is not None:
                    channel_id = safe_channel_id(channel)
                    update_data[channel_type] = channel_id
                    channel_updates.append(f"{channel_type.replace('_id', '')}: {channel.mention}")

            if not update_data:
                embed = discord.Embed(
                    title="No Changes",
                    description="No channel updates were provided.",
                    color=discord.Color.orange()
                )
                await progress_message.edit(embed=embed)
                return

            # Step 3: Update database
            await update_progress(progress_message, 3, 4, "Updating database")

            try:
                async with asyncio.timeout(10.0):  # 10 second timeout for database operation
                    success = await server.update(update_data)
                    if not success:
                        raise Exception("Failed to update server configuration")
            except asyncio.TimeoutError:
                embed = discord.Embed(
                    title="Error",
                    description="Database update timed out. Please try again.",
                    color=discord.Color.red()
                )
                await progress_message.edit(embed=embed)
                return
            except Exception as e:
                embed = discord.Embed(
                    title="Error",
                    description=f"Failed to update server: {e}",
                    color=discord.Color.red()
                )
                await progress_message.edit(embed=embed)
                return

            # Step 4: Final success message
            await update_progress(progress_message, 4, 4, "Finalizing configuration")

            # Create success embed
            success_embed = discord.Embed(
                title="Channels Updated Successfully",
                description=f"Channel configuration for {server.name} has been updated.",
                color=discord.Color.green()
            )

            if channel_updates:
                success_embed.add_field(
                    name="Updated Channels",
                    value="\n".join(channel_updates),
                    inline=False
                )

            # Add next steps
            success_embed.add_field(
                name="Next Steps",
                value="• Use `/killfeed start` to start kill notifications\n"
                      "• Use `/events start` to start event monitoring\n"
                      "• Use `/stats help` to learn about statistics commands",
                inline=False
            )

            await progress_message.edit(embed=success_embed)

            # Restart any active monitors to pick up new channel configuration
            try:
                # Get monitor task names
                monitor_tasks = [
                    f"killfeed_{ctx.guild.id}_{server_id}",
                    f"events_{ctx.guild.id}_{server_id}"
                ]

                for task_name in monitor_tasks:
                    if task_name in self.bot.background_tasks:
                        task = self.bot.background_tasks[task_name]
                        task.cancel()
                        logger.info(f"Cancelled {task_name} for channel update")

                        # Start new task based on type
                        if "killfeed" in task_name:
                            from cogs.killfeed import start_killfeed_monitor
                            new_task = asyncio.create_task(
                                start_killfeed_monitor(self.bot, ctx.guild.id, server_id)
                            )
                        else:
                            from cogs.events import start_events_monitor
                            new_task = asyncio.create_task(
                                start_events_monitor(self.bot, ctx.guild.id, server_id)
                            )

                        self.bot.background_tasks[task_name] = new_task
                        logger.info(f"Started new {task_name} with updated channel configuration")

            except Exception as e:
                logger.error(f"Error restarting monitors: {e}")
                # Non-fatal error, continue

        except Exception as e:
            logger.error(f"Error in setup_channels: {e}", exc_info=True)
            try:
                error_embed = discord.Embed(
                    title="Error",
                    description=f"An unexpected error occurred: {e}",
                    color=discord.Color.red()
                )
                await progress_message.edit(embed=error_embed)
            except:
                await ctx.send("An error occurred while setting up channels.")
        """Configure notification channels for a server"""
        # Start with detailed diagnostic logging for troubleshooting type inconsistency
        # This will help verify our fixes are working
        logger.info(f"Configuring channels for server ID: {server_id} (type: {type(server_id).__name__})")
        logger.info(f"Setting up channels in guild ID: {ctx.guild.id} (type: {type(ctx.guild.id).__name__})")

        # Ensure server_id is a string for consistent comparison
        server_id = str(server_id) if server_id is not None else ""
        logger.info(f"Normalized server_id to string: {server_id}")

        # Diagnostics: Check for guild data with both string and int formats
        guild_data_string = await self.bot.db.guilds.find_one({"guild_id": str(ctx.guild.id)})
        guild_data_int = await self.bot.db.guilds.find_one({"guild_id": ctx.guild.id})

        logger.info(f"Guild data found with string ID lookup: {guild_data_string is not None}")
        logger.info(f"Guild data found with integer ID lookup: {guild_data_int is not None}")

        if guild_data_string:
            logger.info(f"String lookup found guild: {guild_data_string.get('name')} with guild_id type: {type(guild_data_string.get('guild_id')).__name__}")

        if guild_data_int:
            logger.info(f"Integer lookup found guild: {guild_data_int.get('name')} with guild_id type: {type(guild_data_int.get('guild_id')).__name__}")

        try:
            # Defer response to prevent timeout
            await ctx.defer()

            logger.info(f"Setting up channels for server {server_id} in guild {ctx.guild.id}")
            logger.info(f"Input channels - Killfeed: {killfeed_channel.id if killfeed_channel else None}, " +
                        f"Events: {events_channel.id if events_channel else None}, " +
                        f"Connections: {connections_channel.id if connections_channel else None}, " +
                        f"Economy: {economy_channel.id if economy_channel else None}, " +
                        f"Voice: {voice_status_channel.id if voice_status_channel else None}")

            # Get guild model for themed embed
            guild_data = None
            guild_model = None
            try:
                guild_data = await self.bot.db.guilds.find_one({"guild_id": ctx.guild.id})
                if guild_data:
                    logger.info(f"Found guild data in MongoDB: {guild_data.get('name')} with " +
                               f"{len(guild_data.get('servers', []))} servers")
                    guild_model = Guild(self.bot.db, guild_data)
                else:
                    logger.warning(f"Guild data not found for guild ID: {ctx.guild.id}")
            except Exception as e:
                logger.warning(f"Error getting guild model: {e}")

            # Check permissions
            if not await self._check_permission(ctx):
                return

            # Get guild
            guild = await Guild.get_by_id(self.bot.db, ctx.guild.id)
            if not guild:
                logger.error(f"Guild {ctx.guild.id} not found in database")
                embed = EmbedBuilder.create_error_embed(
                    "Guild Not Set Up",
                    "This guild is not set up. Please add a server first."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return

            # Check if server exists
            logger.info(f"Searching for server {server_id} in guild {ctx.guild.id}")
            server = None
            if hasattr(guild, 'servers') and guild.servers:
                logger.info(f"Guild has {len(guild.servers)} servers: {[s.get('server_id') for s in guild.servers]}")
                for s in guild.servers:
                    server_id_from_db = s.get('server_id')
                    logger.info(f"Checking server data: {server_id_from_db} == {server_id}?")
                    logger.info(f"Comparing server_id types: {type(server_id_from_db).__name__} vs {type(server_id).__name__}")
                    # Ensure string comparison for compatibility with autocomplete
                    if str(server_id_from_db) == str(server_id):
                        logger.info(f"Found matching server: {s.get('server_name')}")
                        server = Server(self.bot.db, s)
                        break
            else:
                logger.warning(f"Guild {ctx.guild.id} has no servers attribute or it's empty")

            if not server:
                logger.error(f"Server with ID '{server_id}' not found in guild {ctx.guild.id}")
                embed = EmbedBuilder.create_error_embed(
                    "Server Not Found",
                    f"Server with ID '{server_id}' not found in this guild."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return

            # Prepare update data
            update_data = {}
            update_desc = []

            # Update killfeed channel
            if killfeed_channel:
                update_data["killfeed_channel_id"] = killfeed_channel.id
                logger.info(f"Setting killfeed_channel_id to {update_data['killfeed_channel_id']} (type: {type(update_data['killfeed_channel_id']).__name__})")
                update_desc.append(f"Killfeed Channel: {killfeed_channel.mention}")

            # Check premium status for events and connections
            if (events_channel or connections_channel) and not guild.check_feature_access("events"):
                embed = EmbedBuilder.create_error_embed(
                    "Premium Feature",
                    "Events and connections monitoring are premium features. Please upgrade to access these features."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return

            # Update events channel
            if events_channel:
                update_data["events_channel_id"] = events_channel.id
                logger.info(f"Setting events_channel_id to {update_data['events_channel_id']} (type: {type(update_data['events_channel_id']).__name__})")
                update_desc.append(f"Events Channel: {events_channel.mention}")

            if connections_channel:
                update_data["connections_channel_id"] = connections_channel.id
                logger.info(f"Setting connections_channel_id to {update_data['connections_channel_id']} (type: {type(update_data['connections_channel_id']).__name__})")
                update_desc.append(f"Connections Channel: {connections_channel.mention}")

            # Update voice status channel
            if voice_status_channel:
                update_data["voice_status_channel_id"] = voice_status_channel.id
                logger.info(f"Setting voice_status_channel_id to {update_data['voice_status_channel_id']} (type: {type(update_data['voice_status_channel_id']).__name__})")
                update_desc.append(f"Voice Status Channel: {voice_status_channel.mention}")

            # Update economy channel (premium tier 2+ feature)
            if economy_channel:
                # Check if guild has economy feature (tier 2+)
                if not guild.check_feature_access("economy"):
                    embed = EmbedBuilder.create_error_embed(
                        "Premium Feature",
                        "Economy features require Premium Tier 2 or higher. Please upgrade to access these features."
                    , guild=guild_model)
                    await ctx.send(embed=embed)
                    return

                update_data["economy_channel_id"] = economy_channel.id
                logger.info(f"Setting economy_channel_id to {update_data['economy_channel_id']} (type: {type(update_data['economy_channel_id']).__name__})")
                update_desc.append(f"Economy Channel: {economy_channel.mention}")

            # Check if any updates were provided
            if not update_data:
                logger.warning("No channel updates provided")
                embed = EmbedBuilder.create_error_embed(
                    "No Changes",
                    "No channel updates were provided."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return

            # Log the update attempt
            logger.info(f"Attempting to update server {server_id} with channel data: {update_data}")

            # Convert channel IDs to integers before update
            if killfeed_channel:
                update_data["killfeed_channel_id"] = killfeed_channel.id
            if events_channel:
                update_data["events_channel_id"] = events_channel.id 
            if connections_channel:
                update_data["connections_channel_id"] = connections_channel.id
            if economy_channel:
                update_data["economy_channel_id"] = economy_channel.id
            if voice_status_channel:
                update_data["voice_status_channel_id"] = voice_status_channel.id

            # Update server with proper integer channel IDs
            updated = await server.update(update_data)

            if updated:
                logger.info(f"Successfully updated channels for server {server_id}")
                embed = EmbedBuilder.create_success_embed(
                    "Channels Updated",
                    f"Channels for '{server.name}' have been updated successfully."
                , guild=guild_model)

                # Add channel info
                if update_desc:
                    embed.add_field(
                        name="Updated Channels", 
                        value="\n".join(update_desc),
                        inline=False
                    )

                # Try to restart any running monitoring tasks to pick up the new channels
                try:
                    # Restart killfeed monitor if it's running
                    killfeed_task_name = f"killfeed_{ctx.guild.id}_{server_id}"
                    if killfeed_task_name in self.bot.background_tasks:
                        logger.info(f"Cancelling existing killfeed monitor for server {server_id}")
                        self.bot.background_tasks[killfeed_task_name].cancel()

                        # Import the necessary function
                        from cogs.killfeed import start_killfeed_monitor

                        # Start a new task
                        logger.info(f"Starting new killfeed monitor for server {server_id}")
                        new_task = asyncio.create_task(
                            start_killfeed_monitor(self.bot, ctx.guild.id, server_id)
                        )
                        self.bot.background_tasks[killfeed_task_name] = new_task

                    # Restart events monitor if it's running
                    events_task_name = f"events_{ctx.guild.id}_{server_id}"
                    if events_task_name in self.bot.background_tasks:
                        logger.info(f"Cancelling existing events monitor for server {server_id}")
                        self.bot.background_tasks[events_task_name].cancel()

                        # Import the necessary function
                        from cogs.events import start_events_monitor

                        # Start a new task
                        logger.info(f"Starting new events monitor for server {server_id}")
                        new_task = asyncio.create_task(
                            start_events_monitor(self.bot, ctx.guild.id, server_id)
                        )
                        self.bot.background_tasks[events_task_name] = new_task
                except Exception as restart_e:
                    logger.error(f"Error restarting monitors: {restart_e}")
                    # This is non-fatal, so we continue

                await ctx.send(embed=embed)
            else:
                logger.error(f"Failed to update channels for server {server_id}")
                embed = EmbedBuilder.create_error_embed(
                    "Update Failed",
                    "Failed to update server channels.Check the serverconfiguration."
                , guild=guild_model)
                await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error setting up channels: {e}", exc_info=True)
            embed = EmbedBuilder.create_error_embed(
                "Error",
                f"An error occurred while setting up channels: {e}"
            , guild=guild_model)
            await ctx.send(embed=embed)

    @setup.command(name="list", description="List all configured servers for this guild")
    async def list_servers(self, ctx):
        """List all configured servers for this guild"""

        try:
            # Initialize guild_model early to avoid UnboundLocalError
            guild_model = None

            # Get guild model for themed embed early - before any potential returns
            try:
                guild_data = await self.bot.db.guilds.find_one({"guild_id": ctx.guild.id})
                if guild_data:
                    guild_model = Guild(self.bot.db, guild_data)
            except Exception as e:
                logger.warning(f"Error getting guild model: {e}")

            # Defer response to prevent timeout
            await ctx.defer()

            # Get guild
            guild_data = await self.bot.db.guilds.find_one({"guild_id": ctx.guild.id})
            if not guild_data or not guild_data.get("servers"):
                embed = EmbedBuilder.create_error_embed(
                    "No Servers Found",
                    "No servers have been configured for this guild yet."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return

            # Get servers
            servers = guild_data.get("servers", [])

            # Create embed
            embed = EmbedBuilder.create_base_embed(
                f"Configured Servers for {ctx.guild.name}",
                f"Total servers: {len(servers)}"
            , guild=guild_model)

            # Add server info
            for i, server in enumerate(servers):
                server_id = server.get("server_id", "Unknown")
                server_name = server.get("server_name", "Unknown")

                # Get channel names
                killfeed_channel = None
                events_channel = None
                connections_channel = None
                economy_channel = None
                voice_channel = None

                # Helper function to get channel mention with type conversion
                def get_channel_mention(channel_id):
                    if channel_id is None:
                        return None
                    try:
                        # Ensure channel ID is an integer
                        if not isinstance(channel_id, int):
                            channel_id = int(channel_id)
                        channel = ctx.guild.get_channel(channel_id)
                        return channel.mention if channel else "Not found"
                    except (ValueError, TypeError):
                        logger.error(f"Error converting channel ID to integer: {channel_id}")
                        return "Invalid ID"

                if "killfeed_channel_id" in server and server["killfeed_channel_id"] is not None:
                    killfeed_channel = get_channel_mention(server["killfeed_channel_id"])

                if "events_channel_id" in server and server["events_channel_id"] is not None:
                    events_channel = get_channel_mention(server["events_channel_id"])

                if "connections_channel_id" in server and server["connections_channel_id"] is not None:
                    connections_channel = get_channel_mention(server["connections_channel_id"])

                if "economy_channel_id" in server and server["economy_channel_id"] is not None:
                    economy_channel = get_channel_mention(server["economy_channel_id"])

                if "voice_status_channel_id" in server and server["voice_status_channel_id"] is not None:
                    voice_channel = get_channel_mention(server["voice_status_channel_id"])

                # Check if monitoring tasks are running
                killfeed_running = f"killfeed_{ctx.guild.id}_{server_id}" in self.bot.background_tasks
                events_running = f"events_{ctx.guild.id}_{server_id}" in self.bot.background_tasks

                # Build field value
                field_value = []
                field_value.append(f"ID: `{server_id}`")

                if killfeed_channel:
                    field_value.append(f"Killfeed: {killfeed_channel} " +
                                      (f"({':green_circle:' if killfeed_running else ':red_circle:'})" 
                                       if killfeed_channel != "Not found" else ""))

                if events_channel:
                    field_value.append(f"Events: {events_channel} " +
                                      (f"({':green_circle:' if events_running else ':red_circle:'})" 
                                       if events_channel != "Not found" else ""))

                if connections_channel:
                    field_value.append(f"Connections: {connections_channel}")

                if economy_channel:
                    field_value.append(f"Economy: {economy_channel}")

                if voice_channel:
                    field_value.append(f"Voice Status: {voice_channel}")

                # Add monitor status if none of the channels have it yet
                if not killfeed_channel and not events_channel:
                    status = []
                    if killfeed_running:
                        status.append("Killfeed: :green_circle:")
                    else:
                        status.append("Killfeed: :red_circle:")

                    if events_running:
                        status.append("Events: :green_circle:")
                    else:
                        status.append("Events: :red_circle:")

                    if status:
                        field_value.append(" | ".join(status))

                # Add to embed
                embed.add_field(
                    name=f"{i+1}. {server_name}",
                    value="\n".join(field_value),
                    inline=False
                )

            # Add premium info
            guild = Guild(self.bot.db, guild_data)
            tier = guild.premium_tier
            max_servers = guild.get_max_servers()

            # Get available features
            features = guild.get_available_features()

            # Format features with emoji indicators
            feature_list = []
            feature_list.append(f"{'✅' if 'killfeed' in features else '❌'} Killfeed")
            feature_list.append(f"{'✅' if 'events' in features else '❌'} Events")
            feature_list.append(f"{'✅' if 'connections' in features else '❌'} Connections")
            feature_list.append(f"{'✅' if 'stats' in features else '❌'} Stats")
            feature_list.append(f"{'✅' if 'economy' in features else '❌'} Economy")
            feature_list.append(f"{'✅' if 'gambling' in features else '❌'} Gambling")

            # Format economy info if available
            if 'economy' in features:
                economy_info = []
                if tier >= 2:
                    economy_info.append("💰 Weekly Interest: Enabled")
                else:
                    economy_info.append("💰 Weekly Interest: Disabled (requires Tier 2+)")
            else:
                economy_info = ["💰 Economy features not available (requires Tier 1+)"]

            embed.add_field(
                name="Premium Status",
                value=f"Tier: {tier}\nMax Servers: {max_servers}\nUsed: {len(servers)}/{max_servers}",
                inline=False
            )

            embed.add_field(
                name="Available Features",
                value="\n".join(feature_list),
                inline=True
            )

            embed.add_field(
                name="Economy Status",
                value="\n".join(economy_info),
                inline=True
            )

            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error listing servers: {e}", exc_info=True)
            embed = EmbedBuilder.create_error_embed(
                "Error",
                f"An error occurred while listing servers: {e}"
            , guild=guild_model)
            await ctx.send(embed=embed)

    @setup.command(name="historicalparse", description="Parse all historical data for a server")
    @app_commands.describe(server_id="Select a server by name to parse historical data for")
    @app_commands.autocomplete(server_id=server_id_autocomplete)
    async def historical_parse(self, ctx, server_id: str):
        """Parse all historical data for a server"""
        # Ensure server_id is a string for consistent comparison
        server_id = str(server_id) if server_id is not None else ""
        logger.info(f"Historical_parse received server_id type: {type(server_id).__name__}, value: {server_id}")

        try:
            # Defer response to prevent timeout
            await ctx.defer()
            # Get guild model for themed embed
            guild_data = None
            guild_model = None
            try:
                guild_data = await self.bot.db.guilds.find_one({"guild_id": ctx.guild.id})
                if guild_data:
                    guild_model = Guild(self.bot.db, guild_data)
            except Exception as e:
                logger.warning(f"Error getting guild model: {e}")

            # Check permissions
            if not await self._check_permission(ctx):
                return

            # Check if guild has stats feature
            guild_data = await self.bot.db.guilds.find_one({"guild_id": ctx.guild.id})
            if not guild_data:
                embed = EmbedBuilder.create_error_embed(
                    "Guild Not Set Up",
                    "This guild is not set up. Please add a server first."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return

            guild = Guild(self.bot.db, guild_data)
            if not guild.check_feature_access("stats"):
                embed = EmbedBuilder.create_error_embed(
                    "Premium Feature",
                    "Historical parsing is a premium feature. Please upgrade to access this feature."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return

            # Get server
            server = None
            logger.info(f"Looking for server with ID '{server_id}' (type: {type(server_id).__name__}) in guild {ctx.guild.id}")

            # Log all available servers for debugging
            available_servers = []
            for s in guild_data.get("servers", []):
                server_id_from_db = s.get("server_id")
                server_id_type = type(server_id_from_db).__name__
                server_name = s.get("server_name", "Unknown")
                available_servers.append(f"{server_name}: '{server_id_from_db}' (type: {server_id_type})")

                # Convert both to strings for comparison
                db_id_str = str(server_id_from_db) if server_id_from_db is not None else ""
                input_id_str = str(server_id) if server_id is not None else ""

                logger.info(f"Comparing server: DB ID='{db_id_str}' with input ID='{input_id_str}'")

                if db_id_str == input_id_str:
                    logger.info(f"Match found! Server '{server_name}' with ID '{db_id_str}'")
                    server = Server(self.bot.db, s)
                    break
                else:
                    logger.debug(f"No match: DB ID '{db_id_str}' ≠ input ID '{input_id_str}'")

            # Log available servers if none matched
            if not server:
                logger.warning(f"No server found with ID '{server_id}'. Available servers: {available_servers}")

            if not server:
                embed = EmbedBuilder.create_error_embed(
                    "Server Not Found",
                    f"Server with ID '{server_id}' not found in this guild."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return

            # Initial response
            embed = EmbedBuilder.create_base_embed(
                "Historical Parse",
                f"Starting historical parse for server '{server.name}'.\n\n"
                "This process will parse all CSV files and may take a long time depending on the amount of data."
            )
            message = await ctx.send(embed=embed)

            # Start background task for historical parsing
            task = asyncio.create_task(self._historical_parse_task(server, message))

            # Store task
            task_name = f"historical_{ctx.guild.id}_{server_id}"
            self.bot.background_tasks[task_name] = task

            # Clean up task when done
            task.add_done_callback(lambda t: self.bot.background_tasks.pop(task_name, None))

        except Exception as e:
            logger.error(f"Error starting historical parse: {e}", exc_info=True)
            embed = EmbedBuilder.create_error_embed(
                "Error",
                f"An error occurred while starting historical parse: {e}"
            , guild=guild_model)
            await ctx.send(embed=embed)

    async def _historical_parse_task(self, server, message):
        """Background task for parsing historical data"""

        try:
            # Get guild model for themed embed
            guild_data = None
            guild_model = None
            try:
                # We don't have ctx in this task, so we use server's guild_id
                guild_data = await self.bot.db.guilds.find_one({"guild_id": server.guild_id})
                if guild_data:
                    guild_model = Guild(self.bot.db, guild_data)
            except Exception as e:
                logger.warning(f"Error getting guild model: {e}")

            # Create SFTP client
            sftp_client = SFTPClient(
                host=server.sftp_host,
                port=server.sftp_port,
                username=server.sftp_username,
                password=server.sftp_password,
                server_id=server.id
            )

            # Connect to SFTP
            connected = await sftp_client.connect()
            if not connected:
                embed = EmbedBuilder.create_error_embed(
                    "Connection Failed",
                    f"Failed to connect to SFTP server: {sftp_client.last_error}"
                , guild=guild_model)
                await message.edit(embed=embed)
                return

            # Get all CSV files
            embed = EmbedBuilder.create_base_embed(
                "Historical Parse",
                f"Connected to SFTP server. Retrieving CSV files..."
            , guild=guild_model)
            await message.edit(embed=embed)

            # Construct base path to deathlogs
            server_dir = f"{sftp_client.host.split(':')[0]}_{sftp_client.server_id}"
            deathlogs_path = os.path.join(".", server_dir, "actual1", "deathlogs")

            # Find all CSV files recursively
            csv_files = await sftp_client._find_csv_files_recursive(deathlogs_path)
            if not csv_files:
                embed = EmbedBuilder.create_error_embed(
                    "No CSV Files Found",
                    "Could not find any CSV files in the server."
                , guild=guild_model)
                await message.edit(embed=embed)
                await sftp_client.disconnect()
                return

            # Sort by timestamp from filename
            sorted_files = []
            for file_path in csv_files:
                try:
                    filename = os.path.basename(file_path)
                    # Parse timestamp from filename (YYYY.MM.DD-HH.MM.SS)
                    timestamp_str = filename.split('.csv')[0]
                    dt = datetime.strptime(timestamp_str, '%Y.%m.%d-%H.%M.%S')
                    sorted_files.append((file_path, dt.timestamp(), filename))
                    logger.info(f"Parsed CSV file: {filename} with timestamp {dt}")
                except Exception as e:
                    logger.warning(f"Could not parse timestamp from {filename}: {e}")
                    # Use file modification time as fallback
                    try:
                        attrs = await asyncio.to_thread(lambda: self.sftp.stat(file_path))
                        sorted_files.append((file_path, attrs.st_mtime, filename))
                    except Exception:
                        sorted_files.append((file_path, 0, filename))

            # Sort by timestamp (oldest first for historical processing)
            sorted_files.sort(key=lambda x: float(x[1]))
            logger.info(f"Processing {len(sorted_files)} files in chronological order")

            # Update progress
            embed = EmbedBuilder.create_base_embed(
                "Historical Parse",
                f"Found {len(sorted_files)} CSV file(s). Starting to parse data..."
            , guild=guild_model)
            await message.edit(embed=embed)

            # Process each file
            total_kills = 0
            total_lines = 0
            processed_files = 0
            last_progress_update = datetime.now()
            start_time = datetime.now()
            total_file_size = 0

            # First calculate total size for better progress reporting
            for file_path, timestamp, filename in sorted_files:
                size = await sftp_client.get_file_size(file_path)
                total_file_size += size

            # Create progress embed function for reuse
            async def update_progress(current_size, current_files, kills, lines_processed=0, estimated=None):
                elapsed = (datetime.now() - start_time).total_seconds()
                progress_pct = min(99.9, (current_size / max(1, total_file_size)) * 100) if total_file_size > 0 else 0

                # Calculate rates and ETA
                kill_rate = kills / max(1, elapsed) * 60  # kills per minute
                line_rate = lines_processed / max(1, elapsed) * 60  # lines per minute

                status_lines = [
                    f"Files: {current_files}/{len(sorted_files)} ({progress_pct:.1f}%)",
                    f"Lines processed: {lines_processed:,} lines",
                    f"Events: {kills:,} kill events processed",
                    f"Rate: {kill_rate:.1f} events/min, {line_rate:.1f} lines/min"
                ]

                if estimated:
                    status_lines.append(f"Estimated time remaining: {estimated}")

                embed = EmbedBuilder.create_progress_embed(
                    "Historical Parse In Progress",
                    "\n".join(status_lines),
                    progress=current_size,
                    total=total_file_size
                , guild=guild_model)
                await message.edit(embed=embed)

            current_size = 0
            batch_size = 1000  # Process this many events before committing to DB

            for i, (file_path, timestamp, filename) in enumerate(sorted_files):
                # Check file size
                file_size = await sftp_client.get_file_size(file_path)
                logger.info(f"Processing file {i+1}/{len(sorted_files)}: {file_path} (size: {file_size} lines)")

                # Update initial progress
                if i == 0 or (datetime.now() - last_progress_update).total_seconds() > 15:
                    await update_progress(current_size, processed_files, total_kills, lines_processed=total_lines)
                    last_progress_update = datetime.now()

                # Read file in chunks - larger size for better scaling with many servers
                chunk_size = 5000  # Balanced for performance and memory
                total_chunks = (file_size + chunk_size - 1) // chunk_size  # Ceiling division
                logger.info(f"Processing file {file_path} in {total_chunks} chunks of {chunk_size} lines each")
                processing_start = datetime.now()

                # Track batch for bulk inserts
                kill_batch = []

                for chunk in range(total_chunks):
                    start_line = chunk * chunk_size
                    lines = await sftp_client.read_file(file_path, start_line, chunk_size)
                    total_lines += len(lines)

                    # Parse lines
                    kill_events = CSVParser.parse_kill_lines(lines)

                    # Logdetails about parsed events
                    if len(kill_events) > 0:
                        logger.info(f"Successfully parsed {len(kill_events)} kill events from chunk of {len(lines)} lines")
                    else:
                        # Log a sample of lines for debugging if no events were parsed
                        sample_lines = lines[:3] if len(lines) > 3 else lines
                        logger.warning(f"No kill events parsed from chunk of {len(lines)} lines. Sample: {sample_lines}")

                    # Process kill events
                    for kill_event in kill_events:
                        # Add server ID
                        kill_event["server_id"] = server.id

                        # Ensure timestamp is serializable for MongoDB
                        # Convert datetime objects to ISO format strings
                        if isinstance(kill_event["timestamp"], datetime.datetime):
                            kill_event["timestamp"] = kill_event["timestamp"].isoformat()

                        kill_batch.append(kill_event)

                        # When batch is full, insert and process
                        if len(kill_batch) >= batch_size:
                            # Bulk insert
                            if kill_batch:  # Make sure batch isn't empty
                                await self.bot.db.kills.insert_many(kill_batch)

                                # Update player stats (bulk operation)
                                from cogs.killfeed import update_player_stats
                                for event in kill_batch:
                                    await update_player_stats(self.bot, server.id, event)

                                # Update stats and clear batch
                                total_kills += len(kill_batch)
                                kill_batch = []

                    # Update progress and log performance metrics
                    current_chunk_size = min(chunk_size, file_size - start_line)
                    current_size += current_chunk_size

                    chunk_duration = (datetime.now() - processing_start).total_seconds()
                    lines_per_second = total_lines / max(chunk_duration, 1)
                    logger.info(f"Processing performance - Lines/sec: {lines_per_second:.2f}, Memory usage: {psutil.Process().memory_info().rss / 1024 / 1024:.2f}MB")

                    # Update progress every 60 seconds or every 3 chunks
                    if (datetime.now() - last_progress_update).total_seconds() > 60 or chunk % 3 == 0:
                        # Calculate ETA
                        if current_size > 0:
                            elapsed = (datetime.now() - start_time).total_seconds()
                            bytes_per_second = current_size / elapsed
                            remaining_bytes = total_file_size - current_size

                            if bytes_per_second > 0:
                                eta_seconds = remaining_bytes / bytes_per_second
                                eta_str = f"{int(eta_seconds//60)}m {int(eta_seconds%60)}s"
                            else:
                                eta_str = "calculating..."
                        else:
                            eta_str = "calculating..."

                        # Update progress with ETA
                        await update_progress(current_size, processed_files, total_kills, lines_processed=total_lines, estimated=eta_str)
                        last_progress_update = datetime.now()

                # Process any remaining events in the batch
                if kill_batch:
                    # Ensure all timestamps are serializable
                    for event in kill_batch:
                        if isinstance(event.get("timestamp"), datetime):
                            event["timestamp"] = event["timestamp"].isoformat()

                    await self.bot.db.kills.insert_many(kill_batch)

                    # Update player stats (bulk operation)
                    from cogs.killfeed import update_player_stats
                    for event in kill_batch:
                        await update_player_stats(self.bot, server.id, event)

                    # Update stats
                    total_kills += len(kill_batch)
                    kill_batch = []

                # Mark file as processed
                processed_files += 1

                # Update progress after each file
                await update_progress(current_size, processed_files, total_kills, lines_processed=total_lines)
                last_progress_update = datetime.now()

            # Final update
            elapsed_time = (datetime.now() - start_time).total_seconds()
            elapsed_min = int(elapsed_time // 60)
            elapsed_sec = int(elapsed_time % 60)

            embed = EmbedBuilder.create_success_embed(
                "Historical Parse Complete",
                f"Successfully parsed {len(sorted_files)} CSV file(s) with {total_lines:,} lines and processed {total_kills:,} kill events.\n\n" +
                f"Elapsed time: {elapsed_min}m {elapsed_sec}s"
            , guild=guild_model)
            await message.edit(embed=embed)

            # Disconnect
            await sftp_client.disconnect()

        except asyncio.CancelledError:
            logger.info(f"Historical parse for server {server.id} cancelled")
            embed = EmbedBuilder.create_error_embed(
                "Parse Cancelled",
                "The historical parse has been cancelled."
            , guild=guild_model)
            await message.edit(embed=embed)

        except Exception as e:
            logger.error(f"Error in historical parse for server {server.id}: {e}", exc_info=True)
            embed = EmbedBuilder.create_error_embed(
                "Error",
                f"An error occurred during the historical parse: {e}"
            , guild=guild_model)
            await message.edit(embed=embed)

    async def _check_permission(self, ctx) -> bool:
        """Check if user has permission to use the command"""
        # Initialize guild_model to None first to avoid UnboundLocalError
        guild_model = None

        # Check if user has admin permission
        if has_admin_permission(ctx):
            return True

        # If not, send error message
        # Get the guild model for theme
        try:
            guild_model = await Guild.get_by_id(self.bot.db, ctx.guild.id)
        except Exception as e:
            logger.warning(f"Error getting guild model in permission check: {e}")

        embed = EmbedBuilder.create_error_embed(
            "Permission Denied",
            "You need administrator permission or the designated admin role to use this command.",
            guild=guild_model)
        await ctx.send(embed=embed, ephemeral=True)
        return False

    @setup.command(name="diagnose", description="Diagnose database type consistency issues")
    async def diagnose_db(self, ctx, server_id: str = None):
        """Diagnose database type consistency issues."""
        # Defer response to prevent timeout
        await ctx.defer()

        guild_id = ctx.guild.id
        str_guild_id = str(guild_id)

        # Summary to be shown to the user
        results = []
        results.append(f"Guild ID: {guild_id} (type: {type(guild_id).__name__})")

        # Test guild lookup with different types
        results.append("\n**Guild Lookup Tests:**")

        guild_data_int = await self.bot.db.guilds.find_one({"guild_id": guild_id})
        guild_data_str = await self.bot.db.guilds.find_one({"guild_id": str_guild_id})

        results.append(f"- Integer lookup: {'✅ Success' if guild_data_int else '❌ Failed'}")
        results.append(f"- String lookup: {'✅ Success' if guild_data_str else '❌ Failed'}")

        # Test with our new OR query
        or_query = {
            "$or": [
                {"guild_id": guild_id},
                {"guild_id": str_guild_id},
                {"guild_id": int(str_guild_id) if str_guild_id.isdigit() else guild_id}
            ]
        }
        guild_data_flex = await self.bot.db.guilds.find_one(or_query)
        results.append(f"- Flexible OR query: {'✅ Success' if guild_data_flex else '❌ Failed'}")

        # If we found guild data, check stored guild ID type
        if guild_data_flex:
            db_guild_id = guild_data_flex.get("guild_id")
            results.append(f"\nStored guild ID: {db_guild_id} (type: {type(db_guild_id).__name__})")

        # If server_id provided, test server lookup
        if server_id:
            results.append(f"\n**Server Lookup Tests for ID: {server_id}**")

            # Get Guild model with our new flexible lookup
            guild = await Guild.get_by_id(self.bot.db, guild_id)

            if guild:
                # Test get_server with exact match
                server = await guild.get_server(server_id)
                results.append(f"- Guild.get_server(): {'✅ Success' if server else '❌ Failed'}")

                # Test direct database query
                db_server = None
                if guild_data_flex:
                    for srv in guild_data_flex.get("servers", []):
                        srv_id = srv.get("server_id")
                        results.append(f"  - DB server ID: {srv_id} (type: {type(srv_id).__name__})")
                        if str(srv_id) == str(server_id):
                            db_server = srv
                            break

                results.append(f"- Direct DB lookup: {'✅ Success' if db_server else '❌ Failed'}")

                # If server found, check channel config
                if server:
                    results.append("\n**Channel Configuration:**")
                    results.append(f"- Killfeed channel: {server.get('killfeed_channel_id')}")
                    results.append(f"- Events channel: {server.get('events_channel_id')}")
                    results.append(f"- Connections channel: {server.get('connections_channel_id')}")
            else:
                results.append("- Guild not found in database")

        # Send diagnostic results
        embed = discord.Embed(
            title="Database Diagnosis Results", 
            description="Results of database type consistency tests",
            color=discord.Color.blue()
        )

        # Split results into chunks to avoid hitting embed field value limits
        chunk_size = 1024  # Discord's limit for field values
        chunks = []
        current_chunk = ""

        for line in results:
            if len(current_chunk) + len(line) + 1 > chunk_size:
                chunks.append(current_chunk)
                current_chunk = line
            else:
                if current_chunk:
                    current_chunk += "\n"
                current_chunk += line

        if current_chunk:
            chunks.append(current_chunk)

        # Add chunks as fields
        for i, chunk in enumerate(chunks):
            embed.add_field(
                name=f"Results {i+1}/{len(chunks)}", 
                value=chunk, 
                inline=False
            )

        await ctx.send(embed=embed)


async def setup(bot):
    """Set up the Setup cog"""
    await bot.add_cog(Setup(bot))