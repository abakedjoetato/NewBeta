"""
Player Links cog for the Tower of Temptation PvP Statistics Discord Bot.

This module provides commands for linking Discord accounts to in-game players.
"""
import asyncio
import logging
import re
from typing import Dict, List, Optional, Any, Union, Tuple

import discord
from discord.ext import commands
from discord import app_commands

from models.player_link import PlayerLink
from utils.database import get_db
from utils.async_utils import BackgroundTask
from utils.helpers import has_admin_permission, confirm, paginate_embeds
from utils.embed_builder import EmbedBuilder

logger = logging.getLogger(__name__)

class PlayerLinks(commands.Cog):
    """Commands for linking Discord accounts to in-game players"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @app_commands.command(
        name="player",
        description="Manage your player links and view statistics"
    )
    @app_commands.describe(
        subcommand="Player command to perform",
        player_name="In-game player name",
        server_id="Server ID (required for link operations)",
        user="Discord user to manage links for (admin only)"
    )
    @app_commands.choices(subcommand=[
        app_commands.Choice(name="link", value="link"),
        app_commands.Choice(name="unlink", value="unlink"),
        app_commands.Choice(name="info", value="info"),
        app_commands.Choice(name="stats", value="stats"),
        app_commands.Choice(name="search", value="search"),
        app_commands.Choice(name="verify", value="verify")
    ])
    async def player_command(
        self,
        interaction: discord.Interaction,
        subcommand: str,
        player_name: Optional[str] = None,
        server_id: Optional[str] = None,
        user: Optional[discord.User] = None
    ):
        """Player command
        
        Args:
            interaction: Discord interaction
            subcommand: Player action to perform
            player_name: In-game player name (optional)
            server_id: Server ID (optional)
            user: Discord user (optional, admin only)
        """
        # Check if user is specified and ensure admin permission
        target_user = user or interaction.user
        
        if user and user.id != interaction.user.id:
            if not has_admin_permission(interaction):
                await interaction.response.send_message(
                    "Only administrators can manage links for other users.",
                    ephemeral=True
                )
                return
        
        # Commands that require server_id
        if subcommand in ["link", "unlink"] and not server_id:
            # Try to get default server_id if not provided
            db = await get_db()
            guild_config = await db.get_guild_config(interaction.guild_id)
            
            if guild_config and guild_config.get("default_server"):
                server_id = guild_config.get("default_server")
            else:
                await interaction.response.send_message(
                    "Server ID is required for this command and no default server is configured.",
                    ephemeral=True
                )
                return
        
        # Commands that require player_name
        if subcommand in ["link", "search"] and not player_name:
            await interaction.response.send_message(
                "Player name is required for this command.",
                ephemeral=True
            )
            return
        
        # Process based on subcommand
        if subcommand == "link":
            await self._player_link(interaction, target_user, player_name, server_id)
        elif subcommand == "unlink":
            await self._player_unlink(interaction, target_user, server_id)
        elif subcommand == "info":
            await self._player_info(interaction, target_user)
        elif subcommand == "stats":
            await self._player_stats(interaction, target_user, server_id)
        elif subcommand == "search":
            await self._player_search(interaction, player_name, server_id)
        elif subcommand == "verify":
            await self._player_verify(interaction, target_user)
    
    async def _player_link(
        self,
        interaction: discord.Interaction,
        user: discord.User,
        player_name: str,
        server_id: str
    ):
        """Link a Discord user to an in-game player
        
        Args:
            interaction: Discord interaction
            user: Discord user to link
            player_name: In-game player name
            server_id: Server ID
        """
        # Defer response for potentially long DB operations
        await interaction.response.defer(ephemeral=False)
        
        try:
            db = await get_db()
            
            # Check if server exists
            server = await db.get_server_by_id(server_id)
            if not server:
                await interaction.followup.send(
                    f"Server {server_id} not found. Please use a valid server ID.",
                    ephemeral=True
                )
                return
            
            # Check if player exists
            player = await db.collections["players"].find_one({
                "server_id": server_id,
                "name": player_name
            })
            
            # If player doesn't exist, create placeholder
            if not player:
                result = await db.collections["players"].insert_one({
                    "server_id": server_id,
                    "name": player_name,
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                    "kills": 0,
                    "deaths": 0,
                    "last_seen": datetime.utcnow()
                })
                player_id = str(result.inserted_id)
                
                logger.info(f"Created placeholder player {player_name} on server {server_id}")
            else:
                player_id = str(player["_id"])
            
            # Create or update player link
            player_link = await PlayerLink.create(
                discord_id=user.id,
                server_id=server_id,
                player_id=player_id,
                username=user.name,
                display_name=user.display_name,
                avatar_url=user.display_avatar.url if user.display_avatar else None
            )
            
            # Send confirmation embed
            embed = EmbedBuilder.create_success_embed(
                title="Player Linked",
                description=f"Successfully linked Discord user {user.mention} to player **{player_name}** on server **{server['name']}**.",
                guild=interaction.guild
            )
            
            embed.add_field(name="Server", value=server['name'], inline=True)
            embed.add_field(name="Player", value=player_name, inline=True)
            
            # Add link count if user has multiple links
            player_ids = player_link.get_all_player_ids()
            if len(player_ids) > 1:
                embed.add_field(
                    name="Total Links",
                    value=f"{user.display_name} has {len(player_ids)} linked characters.",
                    inline=False
                )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error linking player: {e}")
            await interaction.followup.send(
                "An error occurred while linking the player. Please try again later.",
                ephemeral=True
            )
    
    async def _player_unlink(
        self,
        interaction: discord.Interaction,
        user: discord.User,
        server_id: str
    ):
        """Unlink a Discord user from an in-game player
        
        Args:
            interaction: Discord interaction
            user: Discord user to unlink
            server_id: Server ID
        """
        # Defer response for potentially long DB operations
        await interaction.response.defer(ephemeral=False)
        
        try:
            # Get existing player link
            player_link = await PlayerLink.get_by_discord_id(user.id)
            
            if not player_link:
                await interaction.followup.send(
                    f"No player link found for {user.mention}.",
                    ephemeral=True
                )
                return
            
            if server_id not in player_link.player_ids:
                await interaction.followup.send(
                    f"No player linked for {user.mention} on server {server_id}.",
                    ephemeral=True
                )
                return
            
            db = await get_db()
            
            # Get server and player info for confirmation
            server = await db.get_server_by_id(server_id)
            server_name = server['name'] if server else server_id
            
            player_id = player_link.player_ids[server_id]
            player = await db.collections["players"].find_one({"_id": player_id})
            player_name = player['name'] if player else "Unknown Player"
            
            # Confirm unlinking
            confirmed = await confirm(
                interaction,
                f"Are you sure you want to unlink {user.mention} from **{player_name}** on server **{server_name}**?",
                timeout=30
            )
            
            if not confirmed:
                await interaction.followup.send(
                    "Player unlink cancelled.",
                    ephemeral=True
                )
                return
            
            # Remove player link
            removed = await player_link.remove_player(server_id)
            
            if removed:
                embed = EmbedBuilder.create_success_embed(
                    title="Player Unlinked",
                    description=f"Successfully unlinked Discord user {user.mention} from player **{player_name}** on server **{server_name}**.",
                    guild=interaction.guild
                )
                
                # Add remaining links count if any
                player_ids = player_link.get_all_player_ids()
                if player_ids:
                    embed.add_field(
                        name="Remaining Links",
                        value=f"{user.display_name} still has {len(player_ids)} linked characters.",
                        inline=False
                    )
                
                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send(
                    "Failed to unlink player. Please try again later.",
                    ephemeral=True
                )
            
        except Exception as e:
            logger.error(f"Error unlinking player: {e}")
            await interaction.followup.send(
                "An error occurred while unlinking the player. Please try again later.",
                ephemeral=True
            )
    
    async def _player_info(
        self,
        interaction: discord.Interaction,
        user: discord.User
    ):
        """Show player link information
        
        Args:
            interaction: Discord interaction
            user: Discord user to show info for
        """
        # Defer response for potentially long DB operations
        await interaction.response.defer(ephemeral=False)
        
        try:
            # Get existing player link
            player_link = await PlayerLink.get_by_discord_id(user.id)
            
            if not player_link or not player_link.player_ids:
                await interaction.followup.send(
                    f"No player links found for {user.mention}. Use `/player link` to link to an in-game character.",
                    ephemeral=True
                )
                return
            
            # Get player names for all linked servers
            player_names = await player_link.get_player_names()
            
            # Create embed
            embed = EmbedBuilder.create_base_embed(
                title=f"Player Links for {user.display_name}",
                description=f"Discord user {user.mention} is linked to the following in-game characters:",
                guild=interaction.guild
            )
            
            # Add user avatar if available
            if user.display_avatar:
                embed.set_thumbnail(url=user.display_avatar.url)
            
            # Get server info for all linked players
            db = await get_db()
            for server_id, player_name in player_names.items():
                server = await db.get_server_by_id(server_id)
                server_name = server['name'] if server else f"Server {server_id}"
                
                embed.add_field(
                    name=server_name,
                    value=f"**{player_name}**",
                    inline=True
                )
            
            # Add linked timestamp
            created_at = player_link.created_at
            if created_at:
                embed.add_field(
                    name="First Linked",
                    value=f"<t:{int(created_at.timestamp())}:R>",
                    inline=False
                )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error showing player info: {e}")
            await interaction.followup.send(
                "An error occurred while retrieving player information. Please try again later.",
                ephemeral=True
            )
    
    async def _player_stats(
        self,
        interaction: discord.Interaction,
        user: discord.User,
        server_id: Optional[str] = None
    ):
        """Show player statistics
        
        Args:
            interaction: Discord interaction
            user: Discord user to show stats for
            server_id: Server ID (optional - if provided, only shows stats for that server)
        """
        # Defer response for potentially long DB operations
        await interaction.response.defer(ephemeral=False)
        
        try:
            # Get existing player link
            player_link = await PlayerLink.get_by_discord_id(user.id)
            
            if not player_link or not player_link.player_ids:
                await interaction.followup.send(
                    f"No player links found for {user.mention}. Use `/player link` to link to an in-game character.",
                    ephemeral=True
                )
                return
            
            # Get stats for all linked players
            stats = await player_link.get_player_stats(server_id)
            
            if not stats["servers"]:
                if server_id:
                    await interaction.followup.send(
                        f"No player links found for {user.mention} on server {server_id}.",
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        f"No statistics found for {user.mention}'s linked players.",
                        ephemeral=True
                    )
                return
            
            # Get server info for linked servers
            db = await get_db()
            server_names = []
            
            for sid in stats["servers"]:
                server = await db.get_server_by_id(sid)
                server_names.append(server['name'] if server else f"Server {sid}")
            
            # Create embed
            title = f"Player Statistics for {user.display_name}"
            description = (f"Statistics for {user.mention}'s linked characters on "
                           f"{server_names[0] if len(server_names) == 1 else 'multiple servers'}")
            
            # Calculate derived stats
            kills = stats.get("kills", 0)
            deaths = stats.get("deaths", 0)
            kd_ratio = kills / max(deaths, 1)
            
            embed = EmbedBuilder.create_base_embed(
                title=title,
                description=description,
                guild=interaction.guild
            )
            
            # Add user avatar if available
            if user.display_avatar:
                embed.set_thumbnail(url=user.display_avatar.url)
            
            # Add main stats
            embed.add_field(name="Kills", value=str(kills), inline=True)
            embed.add_field(name="Deaths", value=str(deaths), inline=True)
            embed.add_field(name="K/D Ratio", value=f"{kd_ratio:.2f}", inline=True)
            
            # Add secondary stats if available
            if stats.get("assists", 0) > 0:
                embed.add_field(name="Assists", value=str(stats.get("assists", 0)), inline=True)
            if stats.get("revives", 0) > 0:
                embed.add_field(name="Revives", value=str(stats.get("revives", 0)), inline=True)
            if stats.get("suicides", 0) > 0:
                embed.add_field(name="Suicides", value=str(stats.get("suicides", 0)), inline=True)
            
            # Add top weapons if available
            weapons = stats.get("weapons", {})
            if weapons:
                # Get top 3 weapons
                top_weapons = sorted(weapons.items(), key=lambda x: x[1], reverse=True)[:3]
                
                weapons_text = "\n".join([f"**{name}**: {count} kills" for name, count in top_weapons])
                embed.add_field(name="Top Weapons", value=weapons_text, inline=False)
            
            # Add servers field if multiple servers
            if len(server_names) > 1:
                embed.add_field(
                    name="Servers",
                    value=", ".join(server_names),
                    inline=False
                )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error showing player stats: {e}")
            await interaction.followup.send(
                "An error occurred while retrieving player statistics. Please try again later.",
                ephemeral=True
            )
    
    async def _player_search(
        self,
        interaction: discord.Interaction,
        player_name: str,
        server_id: Optional[str] = None
    ):
        """Search for players by name
        
        Args:
            interaction: Discord interaction
            player_name: Player name or partial name to search for
            server_id: Server ID (optional - if provided, only searches that server)
        """
        # Defer response for potentially long DB operations
        await interaction.response.defer(ephemeral=False)
        
        try:
            db = await get_db()
            
            # Create search query
            query = {"name": {"$regex": re.escape(player_name), "$options": "i"}}
            
            if server_id:
                query["server_id"] = server_id
            
            # Find matching players
            cursor = db.collections["players"].find(query).sort("kills", -1).limit(25)
            players = await cursor.to_list(length=None)
            
            if not players:
                await interaction.followup.send(
                    f"No players found matching '{player_name}'.",
                    ephemeral=True
                )
                return
            
            # Create embed
            server_str = f" on server {server_id}" if server_id else ""
            embed = EmbedBuilder.create_base_embed(
                title=f"Player Search: {player_name}",
                description=f"Found {len(players)} players matching '{player_name}'{server_str}:",
                guild=interaction.guild
            )
            
            # Add player entries
            for i, player in enumerate(players[:15]):  # Limit to 15 players per embed
                # Check if player is linked to a Discord user
                player_id = str(player["_id"])
                link = None
                
                if server_id:
                    link = await PlayerLink.get_by_player_id(server_id, player_id)
                
                # Add player info
                name = player.get("name", "Unknown")
                kills = player.get("kills", 0)
                deaths = player.get("deaths", 0)
                kd_ratio = kills / max(deaths, 1)
                
                value = [
                    f"Kills: {kills}",
                    f"Deaths: {deaths}",
                    f"K/D: {kd_ratio:.2f}"
                ]
                
                if link:
                    discord_user = self.bot.get_user(link.discord_id)
                    if discord_user:
                        value.append(f"Linked to: {discord_user.mention}")
                
                embed.add_field(
                    name=f"{i+1}. {name}",
                    value="\n".join(value),
                    inline=True
                )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error searching for players: {e}")
            await interaction.followup.send(
                "An error occurred while searching for players. Please try again later.",
                ephemeral=True
            )
    
    async def _player_verify(
        self,
        interaction: discord.Interaction,
        user: discord.User
    ):
        """Verify player links and refresh info
        
        Args:
            interaction: Discord interaction
            user: Discord user to verify
        """
        # Defer response for potentially long DB operations
        await interaction.response.defer(ephemeral=False)
        
        try:
            # Get existing player link
            player_link = await PlayerLink.get_by_discord_id(user.id)
            
            if not player_link or not player_link.player_ids:
                await interaction.followup.send(
                    f"No player links found for {user.mention}. Use `/player link` to link to an in-game character.",
                    ephemeral=True
                )
                return
            
            # Verify each linked player exists and is valid
            db = await get_db()
            verified_links = {}
            invalid_links = {}
            
            for server_id, player_id in player_link.player_ids.items():
                player = await db.collections["players"].find_one({"_id": player_id})
                
                if player:
                    verified_links[server_id] = player.get("name", "Unknown")
                else:
                    invalid_links[server_id] = player_id
                    
                    # Remove invalid link
                    await player_link.remove_player(server_id)
            
            # Update Discord user info
            await player_link.update_user_info(
                username=user.name,
                display_name=user.display_name,
                avatar_url=user.display_avatar.url if user.display_avatar else None
            )
            
            # Create embed
            embed = EmbedBuilder.create_success_embed(
                title="Player Links Verified",
                description=f"Verification complete for {user.mention}'s linked characters.",
                guild=interaction.guild
            )
            
            # Add verification results
            if verified_links:
                verified_text = []
                for server_id, player_name in verified_links.items():
                    server = await db.get_server_by_id(server_id)
                    server_name = server['name'] if server else f"Server {server_id}"
                    verified_text.append(f"**{server_name}**: {player_name}")
                
                embed.add_field(
                    name=f"Verified Links ({len(verified_links)})",
                    value="\n".join(verified_text),
                    inline=False
                )
            
            if invalid_links:
                embed.add_field(
                    name=f"Removed Invalid Links ({len(invalid_links)})",
                    value="Some linked players were not found in the database and have been removed.",
                    inline=False
                )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error verifying player links: {e}")
            await interaction.followup.send(
                "An error occurred while verifying player links. Please try again later.",
                ephemeral=True
            )

async def setup(bot: commands.Bot):
    """Add the PlayerLinks cog to the bot
    
    Args:
        bot: Bot instance
    """
    await bot.add_cog(PlayerLinks(bot))