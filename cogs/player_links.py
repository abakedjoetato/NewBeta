"""
Player Links cog for Tower of Temptation PvP Statistics Discord Bot.

This cog provides commands for linking Discord users to in-game players, including:
1. Creating and managing player links
2. Verifying link ownership
3. Managing linked players
"""
import asyncio
import logging
import random
import string
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union

import discord
from discord import app_commands
from discord.ext import commands

from models.player_link import PlayerLink
from utils.embed_builder import EmbedBuilder
from utils.helpers import paginate_embeds, has_admin_permission, has_mod_permission, confirm
from utils.async_utils import BackgroundTask

logger = logging.getLogger(__name__)

class PlayerLinksCog(commands.Cog):
    """Commands for managing player links in Tower of Temptation"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.ctx_menu = app_commands.ContextMenu(
            name="View Linked Players",
            callback=self.context_view_linked_players,
        )
        self.bot.tree.add_command(self.ctx_menu)
    
    async def cog_unload(self) -> None:
        self.bot.tree.remove_command(self.ctx_menu.name, type=self.ctx_menu.type)
    
    async def context_view_linked_players(self, interaction: discord.Interaction, member: discord.Member) -> None:
        """Context menu command to view a user's linked players
        
        Args:
            interaction: Discord interaction
            member: Discord member
        """
        await interaction.response.defer(ephemeral=True)
        
        # Check permissions - only admins or the user themselves can view linked players
        is_admin = has_admin_permission(interaction)
        is_self = interaction.user.id == member.id
        
        if not (is_admin or is_self):
            embed = EmbedBuilder.error(
                title="Permission Denied",
                description="You can only view your own linked players unless you are an administrator."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Get player link
        player_link = await PlayerLink.get_by_discord_id(member.id)
        if not player_link:
            embed = EmbedBuilder.info(
                title="No Linked Players",
                description=f"{member.display_name} doesn't have any linked players."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Get linked players
        linked_players = player_link.get_all_linked_players()
        
        if not linked_players:
            embed = EmbedBuilder.info(
                title="No Linked Players",
                description=f"{member.display_name} doesn't have any linked players."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Create embed
        embed = EmbedBuilder.info(
            title=f"{member.display_name}'s Linked Players",
            description=f"Discord Account: {member.mention}",
            thumbnail=member.display_avatar.url
        )
        
        # Add server info
        for i, player in enumerate(linked_players, 1):
            server_id = player.get("server_id", "Unknown")
            player_id = player.get("player_id", "Unknown")
            linked_at = player.get("linked_at")
            
            # Format linked time
            linked_time = ""
            if linked_at:
                # Calculate days ago
                days_ago = (datetime.utcnow() - linked_at).days
                if days_ago == 0:
                    linked_time = "Today"
                elif days_ago == 1:
                    linked_time = "Yesterday"
                else:
                    linked_time = f"{days_ago} days ago"
            
            embed.add_field(
                name=f"Server {i}: {server_id}",
                value=f"Player ID: `{player_id}`\nLinked: {linked_time}",
                inline=True
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    # Group command for player linking
    link_group = app_commands.Group(name="link", description="Manage player links")
    
    @link_group.command(name="player")
    @app_commands.describe(
        server_id="The server ID (default: first available server)",
        player_name="Your in-game player name"
    )
    async def _link_player(
        self,
        interaction: discord.Interaction,
        server_id: Optional[str] = None,
        player_name: Optional[str] = None
    ) -> None:
        """Link your Discord account to an in-game player
        
        Args:
            interaction: Discord interaction
            server_id: Server ID (optional)
            player_name: Player name
        """
        await interaction.response.defer(ephemeral=True)
        
        # Get server ID from guild config if not provided
        if not server_id:
            # For now, hardcode a test server ID
            server_id = "test_server"
        
        # Get or create player link
        player_link = await PlayerLink.get_by_discord_id(interaction.user.id)
        if not player_link:
            player_link = await PlayerLink.create(interaction.user.id)
        
        # Check if player name was provided
        if not player_name:
            # Show currently linked players
            linked_players = player_link.get_all_linked_players()
            
            if not linked_players:
                embed = EmbedBuilder.info(
                    title="No Linked Players",
                    description="You don't have any linked players. Use `/link player <player_name>` to link your Discord account to an in-game player.",
                    footer="Your Discord ID is used to identify you in the game."
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # Show linked players
            embed = EmbedBuilder.info(
                title="Your Linked Players",
                description="Here are your currently linked players:"
            )
            
            # Add server info
            for i, player in enumerate(linked_players, 1):
                player_server_id = player.get("server_id", "Unknown")
                player_id = player.get("player_id", "Unknown")
                linked_at = player.get("linked_at")
                
                # Format linked time
                linked_time = ""
                if linked_at:
                    # Calculate days ago
                    days_ago = (datetime.utcnow() - linked_at).days
                    if days_ago == 0:
                        linked_time = "Today"
                    elif days_ago == 1:
                        linked_time = "Yesterday"
                    else:
                        linked_time = f"{days_ago} days ago"
                
                embed.add_field(
                    name=f"Server {i}: {player_server_id}",
                    value=f"Player ID: `{player_id}`\nLinked: {linked_time}",
                    inline=True
                )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Check if player is already linked for this server
        existing_player_id = player_link.get_player_id_for_server(server_id)
        if existing_player_id:
            # Player is already linked, ask if they want to update
            embed = EmbedBuilder.warning(
                title="Player Already Linked",
                description=f"You already have a linked player on this server (ID: `{existing_player_id}`).\n\nDo you want to replace it with `{player_name}`?"
            )
            
            confirmed = await confirm(interaction, embed=embed, ephemeral=True)
            if not confirmed:
                embed = EmbedBuilder.info(
                    title="Link Cancelled",
                    description="Your player link remains unchanged."
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
        
        # TODO: In a real implementation, we would verify the player name
        # For now, we'll just assume player_name is valid and is the player ID
        player_id = player_name
        
        # Create verification token
        token = await player_link.create_verification_token(server_id, player_id)
        
        # Create embed with verification instructions
        embed = EmbedBuilder.info(
            title="Verification Required",
            description="To complete linking your Discord account to your in-game player, you need to verify ownership."
        )
        
        embed.add_field(
            name="Verification Token",
            value=f"`{token}`",
            inline=False
        )
        
        embed.add_field(
            name="Instructions",
            value=(
                "1. Log into the game\n"
                "2. Type `/verify " + token + "` in the in-game chat\n"
                "3. Once verified, use `/link verify " + token + "` in Discord"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Expiration",
            value="This token will expire in 1 hour.",
            inline=False
        )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @link_group.command(name="verify")
    @app_commands.describe(
        token="The verification token you received in-game"
    )
    async def _link_verify(
        self,
        interaction: discord.Interaction,
        token: str
    ) -> None:
        """Verify your player link using a token
        
        Args:
            interaction: Discord interaction
            token: Verification token
        """
        await interaction.response.defer(ephemeral=True)
        
        # Get player link
        player_link = await PlayerLink.get_by_discord_id(interaction.user.id)
        if not player_link:
            embed = EmbedBuilder.error(
                title="No Link Found",
                description="You don't have a pending player link. Use `/link player` first."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Verify token
        result = await player_link.verify_token(token)
        if not result:
            embed = EmbedBuilder.error(
                title="Invalid Token",
                description="The verification token is invalid or has expired. Please try linking again."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Token verified, get server and player info
        server_id = result.get("server_id")
        player_id = result.get("player_id")
        
        # Create success embed
        embed = EmbedBuilder.success(
            title="Link Verified",
            description=f"Your Discord account has been successfully linked to player `{player_id}` on server `{server_id}`."
        )
        
        await interaction.followup.send(embed=embed, ephemeral=False)
    
    @link_group.command(name="unlink")
    @app_commands.describe(
        server_id="The server ID to unlink from (default: all servers)"
    )
    async def _link_unlink(
        self,
        interaction: discord.Interaction,
        server_id: Optional[str] = None
    ) -> None:
        """Unlink your Discord account from an in-game player
        
        Args:
            interaction: Discord interaction
            server_id: Server ID (optional)
        """
        await interaction.response.defer(ephemeral=True)
        
        # Get player link
        player_link = await PlayerLink.get_by_discord_id(interaction.user.id)
        if not player_link:
            embed = EmbedBuilder.error(
                title="No Link Found",
                description="You don't have any linked players."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Get linked players
        linked_players = player_link.get_all_linked_players()
        if not linked_players:
            embed = EmbedBuilder.error(
                title="No Linked Players",
                description="You don't have any linked players."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # If server ID is not provided, ask which server to unlink from
        if not server_id:
            # Create embed with linked servers
            embed = EmbedBuilder.info(
                title="Select Server to Unlink",
                description="You have linked players on the following servers. Which one would you like to unlink from?"
            )
            
            # Add server info
            for i, player in enumerate(linked_players, 1):
                player_server_id = player.get("server_id", "Unknown")
                player_id = player.get("player_id", "Unknown")
                
                embed.add_field(
                    name=f"Server {i}: {player_server_id}",
                    value=f"Player ID: `{player_id}`",
                    inline=True
                )
            
            embed.add_field(
                name="Unlink All",
                value="To unlink from all servers, use `/link unlink all`",
                inline=False
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Check if "all" servers
        if server_id.lower() == "all":
            confirmed = await confirm(
                interaction,
                "Are you sure you want to unlink from **all** servers? This action cannot be undone.",
                ephemeral=True
            )
            
            if not confirmed:
                embed = EmbedBuilder.info(
                    title="Unlink Cancelled",
                    description="Your player links remain unchanged."
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # Delete the entire player link
            await player_link.delete()
            
            embed = EmbedBuilder.success(
                title="All Links Removed",
                description="Your Discord account has been unlinked from all game servers."
            )
            
            await interaction.followup.send(embed=embed, ephemeral=False)
            return
        
        # Check if the specified server is linked
        player_id = player_link.get_player_id_for_server(server_id)
        if not player_id:
            embed = EmbedBuilder.error(
                title="Server Not Linked",
                description=f"You don't have a linked player on server `{server_id}`."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Confirm unlink
        confirmed = await confirm(
            interaction,
            f"Are you sure you want to unlink player `{player_id}` from server `{server_id}`? This action cannot be undone.",
            ephemeral=True
        )
        
        if not confirmed:
            embed = EmbedBuilder.info(
                title="Unlink Cancelled",
                description="Your player link remains unchanged."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Remove player link
        await player_link.remove_player(server_id)
        
        embed = EmbedBuilder.success(
            title="Link Removed",
            description=f"Your Discord account has been unlinked from player `{player_id}` on server `{server_id}`."
        )
        
        await interaction.followup.send(embed=embed, ephemeral=False)
    
    @link_group.command(name="list")
    @app_commands.describe(
        user="The user to list links for (admin only)"
    )
    async def _link_list(
        self,
        interaction: discord.Interaction,
        user: Optional[discord.User] = None
    ) -> None:
        """List your linked players
        
        Args:
            interaction: Discord interaction
            user: User to list links for (admin only)
        """
        await interaction.response.defer(ephemeral=True)
        
        # Check permissions if listing another user's links
        if user and user.id != interaction.user.id:
            if not has_admin_permission(interaction):
                embed = EmbedBuilder.error(
                    title="Permission Denied",
                    description="You can only view your own linked players unless you are an administrator."
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
        
        # Default to self
        target_user = user or interaction.user
        
        # Get player link
        player_link = await PlayerLink.get_by_discord_id(target_user.id)
        if not player_link:
            embed = EmbedBuilder.info(
                title="No Linked Players",
                description=f"{target_user.display_name} doesn't have any linked players."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Get linked players
        linked_players = player_link.get_all_linked_players()
        
        if not linked_players:
            embed = EmbedBuilder.info(
                title="No Linked Players",
                description=f"{target_user.display_name} doesn't have any linked players."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Create embed
        embed = EmbedBuilder.info(
            title=f"{target_user.display_name}'s Linked Players",
            description=f"Discord Account: {target_user.mention}",
            thumbnail=target_user.display_avatar.url
        )
        
        # Add server info
        for i, player in enumerate(linked_players, 1):
            server_id = player.get("server_id", "Unknown")
            player_id = player.get("player_id", "Unknown")
            linked_at = player.get("linked_at")
            
            # Format linked time
            linked_time = ""
            if linked_at:
                # Calculate days ago
                days_ago = (datetime.utcnow() - linked_at).days
                if days_ago == 0:
                    linked_time = "Today"
                elif days_ago == 1:
                    linked_time = "Yesterday"
                else:
                    linked_time = f"{days_ago} days ago"
            
            embed.add_field(
                name=f"Server {i}: {server_id}",
                value=f"Player ID: `{player_id}`\nLinked: {linked_time}",
                inline=True
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="whois")
    @app_commands.describe(
        player_name="The in-game player name",
        server_id="The server ID (default: first available server)"
    )
    async def _whois(
        self,
        interaction: discord.Interaction,
        player_name: str,
        server_id: Optional[str] = None
    ) -> None:
        """Find the Discord user linked to an in-game player
        
        Args:
            interaction: Discord interaction
            player_name: Player name
            server_id: Server ID (optional)
        """
        await interaction.response.defer()
        
        # Get server ID from guild config if not provided
        if not server_id:
            # For now, hardcode a test server ID
            server_id = "test_server"
        
        # TODO: In a real implementation, we would verify the player name
        # For now, we'll just assume player_name is valid and is the player ID
        player_id = player_name
        
        # Get player link by player ID
        player_link = await PlayerLink.get_by_player_id(server_id, player_id)
        if not player_link:
            embed = EmbedBuilder.info(
                title="Player Not Linked",
                description=f"Player `{player_name}` on server `{server_id}` is not linked to any Discord user."
            )
            await interaction.followup.send(embed=embed)
            return
        
        # Get Discord user
        discord_id = player_link.discord_id
        discord_user = self.bot.get_user(discord_id)
        
        if not discord_user:
            try:
                discord_user = await self.bot.fetch_user(discord_id)
            except:
                discord_user = None
        
        # Create embed
        if discord_user:
            embed = EmbedBuilder.info(
                title="Player Link Found",
                description=f"Player `{player_name}` on server `{server_id}` is linked to {discord_user.mention}",
                thumbnail=discord_user.display_avatar.url
            )
            
            # Add Discord info
            embed.add_field(
                name="Discord User",
                value=f"Username: {discord_user.name}\nID: {discord_id}",
                inline=False
            )
        else:
            embed = EmbedBuilder.info(
                title="Player Link Found",
                description=f"Player `{player_name}` on server `{server_id}` is linked to a Discord user.",
                thumbnail=None
            )
            
            # Add Discord info
            embed.add_field(
                name="Discord User",
                value=f"ID: {discord_id}\n(User not found in this server)",
                inline=False
            )
        
        await interaction.followup.send(embed=embed)
    
    @link_group.command(name="admin_add")
    @app_commands.describe(
        discord_user="The Discord user to link",
        server_id="The server ID",
        player_name="The in-game player name"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def _link_admin_add(
        self,
        interaction: discord.Interaction,
        discord_user: discord.User,
        server_id: str,
        player_name: str
    ) -> None:
        """Add a player link (Admin only)
        
        Args:
            interaction: Discord interaction
            discord_user: Discord user
            server_id: Server ID
            player_name: Player name
        """
        await interaction.response.defer(ephemeral=True)
        
        # Check admin permissions
        if not has_admin_permission(interaction):
            embed = EmbedBuilder.error(
                title="Permission Denied",
                description="You don't have permission to use this command."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # TODO: In a real implementation, we would verify the player name
        # For now, we'll just assume player_name is valid and is the player ID
        player_id = player_name
        
        # Get or create player link
        player_link = await PlayerLink.get_by_discord_id(discord_user.id)
        if not player_link:
            player_link = await PlayerLink.create(discord_user.id)
        
        # Add player to link
        try:
            await player_link.add_player(server_id, player_id)
            
            # Create success embed
            embed = EmbedBuilder.success(
                title="Link Added",
                description=f"Successfully linked {discord_user.mention} to player `{player_name}` on server `{server_id}`."
            )
            
            await interaction.followup.send(embed=embed)
            
        except ValueError as e:
            embed = EmbedBuilder.error(
                title="Error Adding Link",
                description=str(e)
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    @link_group.command(name="admin_remove")
    @app_commands.describe(
        discord_user="The Discord user to unlink",
        server_id="The server ID (default: all servers)"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def _link_admin_remove(
        self,
        interaction: discord.Interaction,
        discord_user: discord.User,
        server_id: Optional[str] = None
    ) -> None:
        """Remove a player link (Admin only)
        
        Args:
            interaction: Discord interaction
            discord_user: Discord user
            server_id: Server ID (optional - default: all servers)
        """
        await interaction.response.defer(ephemeral=True)
        
        # Check admin permissions
        if not has_admin_permission(interaction):
            embed = EmbedBuilder.error(
                title="Permission Denied",
                description="You don't have permission to use this command."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Get player link
        player_link = await PlayerLink.get_by_discord_id(discord_user.id)
        if not player_link:
            embed = EmbedBuilder.error(
                title="No Link Found",
                description=f"{discord_user.mention} doesn't have any linked players."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Get linked players
        linked_players = player_link.get_all_linked_players()
        if not linked_players:
            embed = EmbedBuilder.error(
                title="No Linked Players",
                description=f"{discord_user.mention} doesn't have any linked players."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Check if removing all links
        if not server_id or server_id.lower() == "all":
            # Delete the entire player link
            await player_link.delete()
            
            embed = EmbedBuilder.success(
                title="All Links Removed",
                description=f"{discord_user.mention} has been unlinked from all game servers."
            )
            
            await interaction.followup.send(embed=embed)
            return
        
        # Check if the specified server is linked
        player_id = player_link.get_player_id_for_server(server_id)
        if not player_id:
            embed = EmbedBuilder.error(
                title="Server Not Linked",
                description=f"{discord_user.mention} doesn't have a linked player on server `{server_id}`."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Remove player link
        await player_link.remove_player(server_id)
        
        embed = EmbedBuilder.success(
            title="Link Removed",
            description=f"{discord_user.mention} has been unlinked from player `{player_id}` on server `{server_id}`."
        )
        
        await interaction.followup.send(embed=embed)

async def setup(bot: commands.Bot) -> None:
    """Set up the player links cog"""
    await bot.add_cog(PlayerLinksCog(bot))