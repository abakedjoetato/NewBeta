"""
Rivalries cog for the Tower of Temptation PvP Statistics Discord Bot.

This module provides commands for viewing and managing player rivalries.
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Tuple

import discord
from discord.ext import commands
from discord import app_commands

from models.rivalry import Rivalry
from models.player_link import PlayerLink
from utils.database import get_db
from utils.async_utils import BackgroundTask
from utils.helpers import has_admin_permission, paginate_embeds
from utils.embed_builder import EmbedBuilder

logger = logging.getLogger(__name__)

class Rivalries(commands.Cog):
    """Commands for viewing and tracking player rivalries"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @app_commands.command(
        name="rivalries",
        description="View player rivalries and rivalry statistics"
    )
    @app_commands.describe(
        subcommand="Rivalry action to perform",
        player_name="Player name to check rivalries for",
        server_id="Server ID (optional - uses default if not provided)",
        limit="Number of rivalries to show (1-25, default 10)",
        days="Number of days to look back for recent rivalries (default 7)"
    )
    @app_commands.choices(subcommand=[
        app_commands.Choice(name="list", value="list"),
        app_commands.Choice(name="player", value="player"),
        app_commands.Choice(name="top", value="top"),
        app_commands.Choice(name="closest", value="closest"),
        app_commands.Choice(name="recent", value="recent")
    ])
    async def rivalries_command(
        self,
        interaction: discord.Interaction,
        subcommand: str,
        player_name: Optional[str] = None,
        server_id: Optional[str] = None,
        limit: Optional[int] = 10,
        days: Optional[int] = 7
    ):
        """Rivalries command
        
        Args:
            interaction: Discord interaction
            subcommand: Rivalries action to perform
            player_name: Player name to check rivalries for (optional)
            server_id: Server ID (optional)
            limit: Number of rivalries to show (optional)
            days: Number of days to look back for recent rivalries (optional)
        """
        # Validate limit
        if limit < 1:
            limit = 1
        elif limit > 25:
            limit = 25
        
        # Validate days
        if days < 1:
            days = 1
        elif days > 90:
            days = 90
        
        # Set up default server_id if not provided
        if not server_id:
            db = await get_db()
            guild_config = await db.get_guild_config(interaction.guild_id)
            
            if not guild_config or not guild_config.get("default_server"):
                await interaction.response.send_message(
                    "No server has been set up for this Discord guild. Please use the server_id parameter or ask an admin to set a default server.",
                    ephemeral=True
                )
                return
            
            server_id = guild_config.get("default_server")
        
        # Commands that require player_name
        if subcommand == "player" and not player_name:
            # If player name not provided, try to use linked player
            player_link = await PlayerLink.get_by_discord_id(interaction.user.id)
            
            if not player_link or not player_link.get_player_id_for_server(server_id):
                await interaction.response.send_message(
                    "Player name is required for this command, or you must have a linked character on this server.",
                    ephemeral=True
                )
                return
            
            # Get player name from link
            db = await get_db()
            player_id = player_link.get_player_id_for_server(server_id)
            player = await db.collections["players"].find_one({"_id": player_id})
            
            if not player:
                await interaction.response.send_message(
                    "Could not find your linked character on this server.",
                    ephemeral=True
                )
                return
            
            player_name = player.get("name")
        
        # Process based on subcommand
        if subcommand == "list":
            await self._rivalries_list(interaction, server_id, limit)
        elif subcommand == "player":
            await self._rivalries_player(interaction, server_id, player_name)
        elif subcommand == "top":
            await self._rivalries_top(interaction, server_id, limit)
        elif subcommand == "closest":
            await self._rivalries_closest(interaction, server_id, limit)
        elif subcommand == "recent":
            await self._rivalries_recent(interaction, server_id, limit, days)
    
    async def _rivalries_list(
        self,
        interaction: discord.Interaction,
        server_id: str,
        limit: int = 10
    ):
        """List all rivalries on a server
        
        Args:
            interaction: Discord interaction
            server_id: Server ID
            limit: Maximum number of rivalries to show
        """
        # Defer response for potentially long DB operations
        await interaction.response.defer(ephemeral=False)
        
        try:
            db = await get_db()
            
            # Get server info
            server = await db.get_server_by_id(server_id)
            server_name = server['name'] if server else f"Server {server_id}"
            
            # Query all rivalries
            cursor = db.collections["rivalries"].find({"server_id": server_id})
            cursor = cursor.sort("total_kills", -1).limit(limit)
            
            rivalries = await cursor.to_list(length=None)
            
            if not rivalries:
                await interaction.followup.send(
                    f"No rivalries found on server **{server_name}**.",
                    ephemeral=False
                )
                return
            
            # Create embeds
            embeds = []
            current_embed = EmbedBuilder.create_base_embed(
                title=f"Rivalries on {server_name}",
                description=f"Showing {len(rivalries)} rivalries sorted by total kills:",
                guild=interaction.guild
            )
            
            field_count = 0
            for i, rivalry in enumerate(rivalries):
                player1_name = rivalry.get("player1_name", "Unknown")
                player2_name = rivalry.get("player2_name", "Unknown")
                player1_kills = rivalry.get("player1_kills", 0)
                player2_kills = rivalry.get("player2_kills", 0)
                total_kills = rivalry.get("total_kills", 0)
                
                # Determine who's leading
                if player1_kills > player2_kills:
                    title = f"{player1_name} vs {player2_name}"
                    value = f"{player1_kills} - {player2_kills} ({total_kills} total)"
                elif player2_kills > player1_kills:
                    title = f"{player2_name} vs {player1_name}"
                    value = f"{player2_kills} - {player1_kills} ({total_kills} total)"
                else:
                    title = f"{player1_name} vs {player2_name}"
                    value = f"TIED {player1_kills} - {player2_kills} ({total_kills} total)"
                
                # Add last kill info if available
                last_kill = rivalry.get("last_kill")
                if last_kill:
                    timestamp = last_kill.timestamp() if isinstance(last_kill, datetime) else last_kill
                    value += f"\nLast kill: <t:{int(timestamp)}:R>"
                
                # Add field to current embed
                current_embed.add_field(
                    name=f"{i+1}. {title}",
                    value=value,
                    inline=False
                )
                field_count += 1
                
                # Create new embed if we hit the field limit
                if field_count >= 8:
                    embeds.append(current_embed)
                    current_embed = EmbedBuilder.create_base_embed(
                        title=f"Rivalries on {server_name} (continued)",
                        description=f"Showing {len(rivalries)} rivalries sorted by total kills:",
                        guild=interaction.guild
                    )
                    field_count = 0
            
            # Add final embed if it has fields
            if field_count > 0:
                embeds.append(current_embed)
            
            # Send paginated embeds if needed
            if len(embeds) > 1:
                await paginate_embeds(interaction, embeds)
            else:
                await interaction.followup.send(embed=embeds[0])
            
        except Exception as e:
            logger.error(f"Error listing rivalries: {e}")
            await interaction.followup.send(
                "An error occurred while listing rivalries. Please try again later.",
                ephemeral=True
            )
    
    async def _rivalries_player(
        self,
        interaction: discord.Interaction,
        server_id: str,
        player_name: str
    ):
        """Show rivalries for a specific player
        
        Args:
            interaction: Discord interaction
            server_id: Server ID
            player_name: Player name to check rivalries for
        """
        # Defer response for potentially long DB operations
        await interaction.response.defer(ephemeral=False)
        
        try:
            db = await get_db()
            
            # Get server info
            server = await db.get_server_by_id(server_id)
            server_name = server['name'] if server else f"Server {server_id}"
            
            # Get player info
            player = await db.collections["players"].find_one({
                "server_id": server_id,
                "name": player_name
            })
            
            if not player:
                await interaction.followup.send(
                    f"Player **{player_name}** not found on server **{server_name}**.",
                    ephemeral=True
                )
                return
            
            player_id = str(player["_id"])
            
            # Get rivalries involving this player
            rivalries = await Rivalry.get_for_player(server_id, player_id)
            
            if not rivalries:
                await interaction.followup.send(
                    f"No rivalries found for player **{player_name}** on server **{server_name}**.",
                    ephemeral=False
                )
                return
            
            # Create embed
            embed = EmbedBuilder.create_base_embed(
                title=f"Rivalries for {player_name}",
                description=f"Showing {len(rivalries)} rivalries on server **{server_name}**:",
                guild=interaction.guild
            )
            
            # Add player stats
            kills = player.get("kills", 0)
            deaths = player.get("deaths", 0)
            kd_ratio = kills / max(deaths, 1)
            
            embed.add_field(name="Total Kills", value=str(kills), inline=True)
            embed.add_field(name="Total Deaths", value=str(deaths), inline=True)
            embed.add_field(name="K/D Ratio", value=f"{kd_ratio:.2f}", inline=True)
            
            # Process rivalries
            for rivalry in rivalries[:8]:  # Limit to 8 rivalries per embed
                # Get rivalry from player's perspective
                stats = rivalry.get_stats_for_player(player_id)
                
                # Create field for rivalry
                title = f"vs {stats['opponent_name']}"
                
                if stats['is_leading']:
                    value = f"LEADING {stats['kills']} - {stats['deaths']}"
                elif stats['kills'] == stats['deaths']:
                    value = f"TIED {stats['kills']} - {stats['deaths']}"
                else:
                    value = f"TRAILING {stats['kills']} - {stats['deaths']}"
                
                value += f" (K/D: {stats['kd_ratio']:.2f})"
                
                # Add field
                embed.add_field(
                    name=title,
                    value=value,
                    inline=False
                )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error showing player rivalries: {e}")
            await interaction.followup.send(
                "An error occurred while retrieving player rivalries. Please try again later.",
                ephemeral=True
            )
    
    async def _rivalries_top(
        self,
        interaction: discord.Interaction,
        server_id: str,
        limit: int = 10
    ):
        """Show top rivalries by total kills
        
        Args:
            interaction: Discord interaction
            server_id: Server ID
            limit: Maximum number of rivalries to show
        """
        # Defer response for potentially long DB operations
        await interaction.response.defer(ephemeral=False)
        
        try:
            # Get server info
            db = await get_db()
            server = await db.get_server_by_id(server_id)
            server_name = server['name'] if server else f"Server {server_id}"
            
            # Get top rivalries
            rivalries = await Rivalry.get_top_rivalries(server_id, limit)
            
            if not rivalries:
                await interaction.followup.send(
                    f"No significant rivalries found on server **{server_name}**.",
                    ephemeral=False
                )
                return
            
            # Create embed
            embed = EmbedBuilder.create_base_embed(
                title=f"Top Rivalries on {server_name}",
                description=f"Showing top {len(rivalries)} rivalries by total kills:",
                guild=interaction.guild
            )
            
            # Process rivalries
            for i, rivalry in enumerate(rivalries):
                # Get leader
                leader_id, leader_name = rivalry.get_leader()
                
                # Determine opponent
                if leader_id == rivalry.player1_id:
                    opponent_name = rivalry.player2_name
                    leader_kills = rivalry.player1_kills
                    opponent_kills = rivalry.player2_kills
                else:
                    opponent_name = rivalry.player1_name
                    leader_kills = rivalry.player2_kills
                    opponent_kills = rivalry.player1_kills
                
                # Create field title and value
                title = f"{i+1}. {leader_name} vs {opponent_name}"
                value = f"{leader_kills} - {opponent_kills} ({rivalry.total_kills} total)"
                
                # Add more stats
                if rivalry.last_kill:
                    timestamp = int(rivalry.last_kill.timestamp())
                    value += f"\nLast kill: <t:{timestamp}:R>"
                
                value += f"\nWeapon: {rivalry.last_weapon}" if rivalry.last_weapon else ""
                
                # Add field
                embed.add_field(
                    name=title,
                    value=value,
                    inline=False
                )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error showing top rivalries: {e}")
            await interaction.followup.send(
                "An error occurred while retrieving top rivalries. Please try again later.",
                ephemeral=True
            )
    
    async def _rivalries_closest(
        self,
        interaction: discord.Interaction,
        server_id: str,
        limit: int = 10
    ):
        """Show closest (most evenly matched) rivalries
        
        Args:
            interaction: Discord interaction
            server_id: Server ID
            limit: Maximum number of rivalries to show
        """
        # Defer response for potentially long DB operations
        await interaction.response.defer(ephemeral=False)
        
        try:
            # Get server info
            db = await get_db()
            server = await db.get_server_by_id(server_id)
            server_name = server['name'] if server else f"Server {server_id}"
            
            # Get closest rivalries
            rivalries = await Rivalry.get_closest_rivalries(server_id, limit)
            
            if not rivalries:
                await interaction.followup.send(
                    f"No significant rivalries found on server **{server_name}**.",
                    ephemeral=False
                )
                return
            
            # Create embed
            embed = EmbedBuilder.create_base_embed(
                title=f"Most Evenly Matched Rivalries on {server_name}",
                description=f"Showing {len(rivalries)} closest rivalries by score difference:",
                guild=interaction.guild
            )
            
            # Process rivalries
            for i, rivalry in enumerate(rivalries):
                # Format names and scores
                difference = abs(rivalry.score_difference)
                
                if rivalry.player1_kills >= rivalry.player2_kills:
                    title = f"{i+1}. {rivalry.player1_name} vs {rivalry.player2_name}"
                    value = f"{rivalry.player1_kills} - {rivalry.player2_kills} (Diff: {difference})"
                else:
                    title = f"{i+1}. {rivalry.player2_name} vs {rivalry.player1_name}"
                    value = f"{rivalry.player2_kills} - {rivalry.player1_kills} (Diff: {difference})"
                
                # Add more stats
                value += f"\nTotal Fights: {rivalry.total_kills}"
                
                if rivalry.last_kill:
                    timestamp = int(rivalry.last_kill.timestamp())
                    value += f"\nLast kill: <t:{timestamp}:R>"
                
                # Add field
                embed.add_field(
                    name=title,
                    value=value,
                    inline=False
                )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error showing closest rivalries: {e}")
            await interaction.followup.send(
                "An error occurred while retrieving closest rivalries. Please try again later.",
                ephemeral=True
            )
    
    async def _rivalries_recent(
        self,
        interaction: discord.Interaction,
        server_id: str,
        limit: int = 10,
        days: int = 7
    ):
        """Show recently active rivalries
        
        Args:
            interaction: Discord interaction
            server_id: Server ID
            limit: Maximum number of rivalries to show
            days: Number of days to look back
        """
        # Defer response for potentially long DB operations
        await interaction.response.defer(ephemeral=False)
        
        try:
            # Get server info
            db = await get_db()
            server = await db.get_server_by_id(server_id)
            server_name = server['name'] if server else f"Server {server_id}"
            
            # Get recent rivalries
            rivalries = await Rivalry.get_recent_rivalries(server_id, limit, days)
            
            if not rivalries:
                await interaction.followup.send(
                    f"No recent rivalry activity found on server **{server_name}** in the last {days} days.",
                    ephemeral=False
                )
                return
            
            # Create embed
            embed = EmbedBuilder.create_base_embed(
                title=f"Recent Rivalry Activity on {server_name}",
                description=f"Showing {len(rivalries)} rivalries with activity in the last {days} days:",
                guild=interaction.guild
            )
            
            # Process rivalries
            for i, rivalry in enumerate(rivalries):
                # Get recent activity
                recent_kills = rivalry.recent_kills or []
                
                if not recent_kills:
                    continue
                
                # Sort by timestamp (newest first)
                sorted_kills = sorted(
                    recent_kills, 
                    key=lambda k: k.get("timestamp", datetime.min), 
                    reverse=True
                )
                
                # Get latest kill
                latest = sorted_kills[0]
                killer_name = latest.get("killer_name", "Unknown")
                victim_name = latest.get("victim_name", "Unknown")
                weapon = latest.get("weapon", "Unknown")
                timestamp = latest.get("timestamp")
                
                # Format title and value
                title = f"{i+1}. {rivalry.player1_name} vs {rivalry.player2_name}"
                
                value = [
                    f"Score: {rivalry.player1_kills} - {rivalry.player2_kills}",
                    f"Latest: **{killer_name}** killed **{victim_name}** with **{weapon}**"
                ]
                
                if timestamp:
                    ts = int(timestamp.timestamp()) if isinstance(timestamp, datetime) else int(timestamp)
                    value.append(f"When: <t:{ts}:R>")
                
                # Add field
                embed.add_field(
                    name=title,
                    value="\n".join(value),
                    inline=False
                )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error showing recent rivalries: {e}")
            await interaction.followup.send(
                "An error occurred while retrieving recent rivalries. Please try again later.",
                ephemeral=True
            )

async def setup(bot: commands.Bot):
    """Add the Rivalries cog to the bot
    
    Args:
        bot: Bot instance
    """
    await bot.add_cog(Rivalries(bot))