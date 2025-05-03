"""
Factions cog for the Tower of Temptation PvP Statistics Discord Bot.

This module provides commands for creating, managing, and using factions.
"""
import asyncio
import logging
from typing import Dict, List, Optional, Any, Union, Tuple

import discord
from discord.ext import commands
from discord import app_commands

from models.faction import Faction
from models.player_link import PlayerLink
from utils.database import get_db
from utils.async_utils import BackgroundTask
from utils.helpers import has_admin_permission, confirm, paginate_embeds
from utils.embed_builder import EmbedBuilder

logger = logging.getLogger(__name__)

class Factions(commands.Cog):
    """Commands for faction creation and management"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @app_commands.command(
        name="faction",
        description="Manage factions on your server"
    )
    @app_commands.describe(
        subcommand="Faction action to perform",
        name="Faction name",
        tag="Faction tag (3-5 characters)",
        description="Faction description",
        player="Player to add/remove/promote",
        role="Role to assign",
        server_id="Server ID (admin only)"
    )
    @app_commands.choices(subcommand=[
        app_commands.Choice(name="create", value="create"),
        app_commands.Choice(name="info", value="info"),
        app_commands.Choice(name="list", value="list"),
        app_commands.Choice(name="join", value="join"),
        app_commands.Choice(name="leave", value="leave"),
        app_commands.Choice(name="add", value="add"),
        app_commands.Choice(name="remove", value="remove"),
        app_commands.Choice(name="promote", value="promote"),
        app_commands.Choice(name="edit", value="edit"),
        app_commands.Choice(name="stats", value="stats"),
        app_commands.Choice(name="delete", value="delete")
    ])
    @app_commands.choices(role=[
        app_commands.Choice(name="member", value="member"),
        app_commands.Choice(name="officer", value="officer"),
        app_commands.Choice(name="leader", value="leader")
    ])
    async def faction_command(
        self,
        interaction: discord.Interaction,
        subcommand: str,
        name: Optional[str] = None,
        tag: Optional[str] = None,
        description: Optional[str] = None,
        player: Optional[str] = None,
        role: Optional[str] = None,
        server_id: Optional[str] = None
    ):
        """Faction management command
        
        Args:
            interaction: Discord interaction
            subcommand: Faction action to perform
            name: Faction name (optional)
            tag: Faction tag (optional)
            description: Faction description (optional)
            player: Player to add/remove/promote (optional)
            role: Role to assign (optional)
            server_id: Server ID (optional, admin only)
        """
        # Ensure basic requirements are met
        if subcommand not in ["list", "info", "stats"] and not name:
            await interaction.response.send_message(
                "Faction name is required for this command.",
                ephemeral=True
            )
            return
        
        # Set up default server_id if not provided
        if not server_id:
            db = await get_db()
            guild_config = await db.get_guild_config(interaction.guild_id)
            
            if not guild_config or not guild_config.get("default_server"):
                await interaction.response.send_message(
                    "No server has been set up for this Discord guild. Please ask an admin to set one up.",
                    ephemeral=True
                )
                return
            
            server_id = guild_config.get("default_server")
        
        # Process based on subcommand
        if subcommand == "create":
            await self._faction_create(interaction, server_id, name, tag, description)
        elif subcommand == "info":
            await self._faction_info(interaction, server_id, name)
        elif subcommand == "list":
            await self._faction_list(interaction, server_id)
        elif subcommand == "join":
            await self._faction_join(interaction, server_id, name)
        elif subcommand == "leave":
            await self._faction_leave(interaction, server_id)
        elif subcommand == "add":
            await self._faction_add(interaction, server_id, name, player)
        elif subcommand == "remove":
            await self._faction_remove(interaction, server_id, name, player)
        elif subcommand == "promote":
            await self._faction_promote(interaction, server_id, name, player, role)
        elif subcommand == "edit":
            await self._faction_edit(interaction, server_id, name, tag, description)
        elif subcommand == "stats":
            await self._faction_stats(interaction, server_id, name)
        elif subcommand == "delete":
            await self._faction_delete(interaction, server_id, name)
    
    async def _faction_create(
        self,
        interaction: discord.Interaction,
        server_id: str,
        name: str,
        tag: Optional[str] = None,
        description: Optional[str] = None
    ):
        """Create a new faction
        
        Args:
            interaction: Discord interaction
            server_id: Server ID
            name: Faction name
            tag: Faction tag (optional)
            description: Faction description (optional)
        """
        # Defer response for potentially long DB operations
        await interaction.response.defer(ephemeral=False)
        
        try:
            # Get player link for the user
            player_link = await PlayerLink.get_by_discord_id(interaction.user.id)
            
            if not player_link:
                await interaction.followup.send(
                    "You need to link your Discord account to an in-game character first. "
                    "Use `/player link` command.",
                    ephemeral=True
                )
                return
            
            # Get player ID for this server
            player_id = player_link.get_player_id_for_server(server_id)
            
            if not player_id:
                await interaction.followup.send(
                    f"You don't have a character linked to server {server_id}. "
                    "Please link to a character on that server first.",
                    ephemeral=True
                )
                return
            
            # Check if player is already in a faction
            existing_faction = await Faction.get_player_faction(player_id)
            
            if existing_faction:
                await interaction.followup.send(
                    f"You're already a member of faction {existing_faction.name}. "
                    "Leave that faction first with `/faction leave`.",
                    ephemeral=True
                )
                return
            
            # Validate faction tag if provided
            if tag and (len(tag) < 2 or len(tag) > 5):
                await interaction.followup.send(
                    "Faction tag must be between 2 and 5 characters.",
                    ephemeral=True
                )
                return
            
            # Create the faction
            faction = await Faction.create(
                server_id=server_id,
                name=name,
                leader_id=player_id,
                tag=tag or name[:3].upper(),
                description=description or f"Official faction of {name}"
            )
            
            # Send confirmation embed
            embed = EmbedBuilder.create_success_embed(
                title="Faction Created",
                description=f"Faction **{faction.name}** has been created and you've been assigned as leader.",
                guild=interaction.guild
            )
            
            embed.add_field(name="Name", value=faction.name, inline=True)
            embed.add_field(name="Tag", value=faction.tag, inline=True)
            embed.add_field(name="Members", value="1", inline=True)
            
            if description:
                embed.add_field(name="Description", value=description, inline=False)
            
            await interaction.followup.send(embed=embed)
            
        except ValueError as e:
            await interaction.followup.send(
                f"Error creating faction: {str(e)}",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error creating faction: {e}")
            await interaction.followup.send(
                "An error occurred while creating the faction. Please try again later.",
                ephemeral=True
            )
    
    async def _faction_info(
        self,
        interaction: discord.Interaction,
        server_id: str,
        name: Optional[str] = None
    ):
        """Show faction information
        
        Args:
            interaction: Discord interaction
            server_id: Server ID
            name: Faction name (optional - if not provided, shows user's faction)
        """
        # Defer response for potentially long DB operations
        await interaction.response.defer(ephemeral=False)
        
        try:
            faction = None
            
            if name:
                # Get faction by name
                faction = await Faction.get_by_name(server_id, name)
            else:
                # Get player's linked faction
                player_link = await PlayerLink.get_by_discord_id(interaction.user.id)
                
                if player_link:
                    player_id = player_link.get_player_id_for_server(server_id)
                    
                    if player_id:
                        faction = await Faction.get_player_faction(player_id)
            
            if not faction:
                await interaction.followup.send(
                    f"Faction {'not specified' if not name else name} not found.",
                    ephemeral=True
                )
                return
            
            # Start background task to get member details
            members_task = asyncio.create_task(faction.get_member_details())
            
            # Create base faction embed
            embed = faction.to_embed()
            
            # Get faction stats
            stats = await faction.get_stats()
            
            # Add stats to embed
            if stats:
                stats_text = [
                    f"**Kills**: {stats.get('kills', 0)}",
                    f"**Deaths**: {stats.get('deaths', 0)}",
                    f"**K/D Ratio**: {stats.get('kd_ratio', 0):.2f}",
                    f"**Score**: {stats.get('total_score', 0)}"
                ]
                
                embed.add_field(
                    name="Statistics",
                    value="\n".join(stats_text),
                    inline=False
                )
            
            # Wait for members task to complete
            members = await members_task
            
            # Add members to embed if not too many
            if members and len(members) <= 15:
                members_text = []
                
                for member in members:
                    role_emoji = "👑" if member["role"] == "leader" else "🛡️" if member["role"] == "officer" else "👤"
                    members_text.append(f"{role_emoji} **{member['name']}** - K: {member['kills']} D: {member['deaths']}")
                
                if members_text:
                    embed.add_field(
                        name=f"Members ({len(members)})",
                        value="\n".join(members_text),
                        inline=False
                    )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error showing faction info: {e}")
            await interaction.followup.send(
                "An error occurred while retrieving faction information. Please try again later.",
                ephemeral=True
            )
    
    async def _faction_list(self, interaction: discord.Interaction, server_id: str):
        """List all factions on the server
        
        Args:
            interaction: Discord interaction
            server_id: Server ID
        """
        # Defer response for potentially long DB operations
        await interaction.response.defer(ephemeral=False)
        
        try:
            # Get all factions for the server
            factions = await Faction.get_factions_for_server(server_id)
            
            if not factions:
                await interaction.followup.send(
                    "No factions have been created on this server yet.",
                    ephemeral=False
                )
                return
            
            # Create list embed
            embed = EmbedBuilder.create_base_embed(
                title="Factions",
                description=f"There are {len(factions)} factions on this server.",
                guild=interaction.guild
            )
            
            # Add faction entries
            for i, faction in enumerate(factions[:15]):  # Limit to 15 factions per embed
                # Get faction stats
                stats = faction.data.get("stats", {})
                
                # Create faction entry
                value = [
                    f"**Members**: {faction.member_count}",
                    f"**Kills**: {stats.get('kills', 0)}",
                    f"**K/D**: {stats.get('kills', 0) / max(stats.get('deaths', 1), 1):.2f}"
                ]
                
                embed.add_field(
                    name=f"{faction.name} [{faction.tag}]",
                    value="\n".join(value),
                    inline=True
                )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error listing factions: {e}")
            await interaction.followup.send(
                "An error occurred while listing factions. Please try again later.",
                ephemeral=True
            )
    
    async def _faction_join(
        self,
        interaction: discord.Interaction,
        server_id: str,
        name: str
    ):
        """Join a faction
        
        Args:
            interaction: Discord interaction
            server_id: Server ID
            name: Faction name
        """
        # Defer response for potentially long DB operations
        await interaction.response.defer(ephemeral=False)
        
        try:
            # Get faction by name
            faction = await Faction.get_by_name(server_id, name)
            
            if not faction:
                await interaction.followup.send(
                    f"Faction {name} not found.",
                    ephemeral=True
                )
                return
            
            # Check if faction is open for joining
            if not faction.is_open:
                await interaction.followup.send(
                    f"Faction {faction.name} is not open for joining. "
                    "Please ask a faction leader or officer to add you.",
                    ephemeral=True
                )
                return
            
            # Get player link for the user
            player_link = await PlayerLink.get_by_discord_id(interaction.user.id)
            
            if not player_link:
                await interaction.followup.send(
                    "You need to link your Discord account to an in-game character first. "
                    "Use `/player link` command.",
                    ephemeral=True
                )
                return
            
            # Get player ID for this server
            player_id = player_link.get_player_id_for_server(server_id)
            
            if not player_id:
                await interaction.followup.send(
                    f"You don't have a character linked to server {server_id}. "
                    "Please link to a character on that server first.",
                    ephemeral=True
                )
                return
            
            # Check if player is already in a faction
            existing_faction = await Faction.get_player_faction(player_id)
            
            if existing_faction and existing_faction.id == faction.id:
                await interaction.followup.send(
                    f"You're already a member of faction {faction.name}.",
                    ephemeral=True
                )
                return
            elif existing_faction:
                # Confirm leaving current faction
                confirmed = await confirm(
                    interaction,
                    f"You're already a member of faction {existing_faction.name}. "
                    f"Do you want to leave it and join {faction.name}?",
                    timeout=30
                )
                
                if not confirmed:
                    await interaction.followup.send(
                        "Faction join cancelled.",
                        ephemeral=True
                    )
                    return
            
            # Add player to faction
            added = await faction.add_member(player_id)
            
            if added:
                embed = EmbedBuilder.create_success_embed(
                    title="Faction Joined",
                    description=f"You've successfully joined faction **{faction.name}**.",
                    guild=interaction.guild
                )
                
                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send(
                    "Failed to join faction. You may already be a member.",
                    ephemeral=True
                )
            
        except Exception as e:
            logger.error(f"Error joining faction: {e}")
            await interaction.followup.send(
                "An error occurred while joining the faction. Please try again later.",
                ephemeral=True
            )
    
    async def _faction_leave(
        self,
        interaction: discord.Interaction,
        server_id: str
    ):
        """Leave current faction
        
        Args:
            interaction: Discord interaction
            server_id: Server ID
        """
        # Defer response for potentially long DB operations
        await interaction.response.defer(ephemeral=False)
        
        try:
            # Get player link for the user
            player_link = await PlayerLink.get_by_discord_id(interaction.user.id)
            
            if not player_link:
                await interaction.followup.send(
                    "You need to link your Discord account to an in-game character first. "
                    "Use `/player link` command.",
                    ephemeral=True
                )
                return
            
            # Get player ID for this server
            player_id = player_link.get_player_id_for_server(server_id)
            
            if not player_id:
                await interaction.followup.send(
                    f"You don't have a character linked to server {server_id}.",
                    ephemeral=True
                )
                return
            
            # Get player's faction
            faction = await Faction.get_player_faction(player_id)
            
            if not faction:
                await interaction.followup.send(
                    "You're not a member of any faction.",
                    ephemeral=True
                )
                return
            
            # Check if player is faction leader
            db = await get_db()
            member = await db.collections["faction_members"].find_one({
                "faction_id": faction.id,
                "player_id": player_id,
                "is_active": True
            })
            
            if member and member["role"] == "leader":
                # Leaders cannot leave, they must transfer leadership or delete
                await interaction.followup.send(
                    "As the faction leader, you cannot leave the faction. "
                    "You must either transfer leadership to another member using `/faction promote` "
                    "or delete the faction with `/faction delete`.",
                    ephemeral=True
                )
                return
            
            # Confirm leaving faction
            confirmed = await confirm(
                interaction,
                f"Are you sure you want to leave faction {faction.name}?",
                timeout=30
            )
            
            if not confirmed:
                await interaction.followup.send(
                    "Faction leave cancelled.",
                    ephemeral=True
                )
                return
            
            # Remove player from faction
            removed = await faction.remove_member(player_id)
            
            if removed:
                embed = EmbedBuilder.create_success_embed(
                    title="Faction Left",
                    description=f"You've successfully left faction **{faction.name}**.",
                    guild=interaction.guild
                )
                
                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send(
                    "Failed to leave faction. You may not be a member.",
                    ephemeral=True
                )
            
        except Exception as e:
            logger.error(f"Error leaving faction: {e}")
            await interaction.followup.send(
                "An error occurred while leaving the faction. Please try again later.",
                ephemeral=True
            )
    
    async def _faction_add(
        self,
        interaction: discord.Interaction,
        server_id: str,
        faction_name: str,
        player_name: str
    ):
        """Add a player to a faction
        
        Args:
            interaction: Discord interaction
            server_id: Server ID
            faction_name: Faction name
            player_name: Player to add
        """
        # Defer response for potentially long DB operations
        await interaction.response.defer(ephemeral=False)
        
        try:
            # Get faction by name
            faction = await Faction.get_by_name(server_id, faction_name)
            
            if not faction:
                await interaction.followup.send(
                    f"Faction {faction_name} not found.",
                    ephemeral=True
                )
                return
            
            # Check if user has permission to add members
            await self._check_faction_permission(interaction, faction)
            
            # Get player ID from name
            db = await get_db()
            player = await db.collections["players"].find_one({
                "server_id": server_id,
                "name": player_name
            })
            
            if not player:
                await interaction.followup.send(
                    f"Player {player_name} not found on this server.",
                    ephemeral=True
                )
                return
            
            player_id = str(player["_id"])
            
            # Check if player is already in a faction
            existing_faction = await Faction.get_player_faction(player_id)
            
            if existing_faction and existing_faction.id == faction.id:
                await interaction.followup.send(
                    f"Player {player_name} is already a member of faction {faction.name}.",
                    ephemeral=True
                )
                return
            elif existing_faction:
                # Player is in another faction, confirm addition
                confirmed = await confirm(
                    interaction,
                    f"Player {player_name} is already a member of faction {existing_faction.name}. "
                    f"Do you want to remove them from that faction and add them to {faction.name}?",
                    timeout=30
                )
                
                if not confirmed:
                    await interaction.followup.send(
                        "Faction add cancelled.",
                        ephemeral=True
                    )
                    return
            
            # Add player to faction
            added = await faction.add_member(player_id)
            
            if added:
                embed = EmbedBuilder.create_success_embed(
                    title="Member Added",
                    description=f"Player **{player_name}** has been added to faction **{faction.name}**.",
                    guild=interaction.guild
                )
                
                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send(
                    f"Failed to add {player_name} to faction. They may already be a member.",
                    ephemeral=True
                )
            
        except PermissionError as e:
            await interaction.followup.send(str(e), ephemeral=True)
        except Exception as e:
            logger.error(f"Error adding member to faction: {e}")
            await interaction.followup.send(
                "An error occurred while adding the member. Please try again later.",
                ephemeral=True
            )
    
    async def _faction_remove(
        self,
        interaction: discord.Interaction,
        server_id: str,
        faction_name: str,
        player_name: str
    ):
        """Remove a player from a faction
        
        Args:
            interaction: Discord interaction
            server_id: Server ID
            faction_name: Faction name
            player_name: Player to remove
        """
        # Defer response for potentially long DB operations
        await interaction.response.defer(ephemeral=False)
        
        try:
            # Get faction by name
            faction = await Faction.get_by_name(server_id, faction_name)
            
            if not faction:
                await interaction.followup.send(
                    f"Faction {faction_name} not found.",
                    ephemeral=True
                )
                return
            
            # Check if user has permission to remove members
            await self._check_faction_permission(interaction, faction)
            
            # Get player ID from name
            db = await get_db()
            player = await db.collections["players"].find_one({
                "server_id": server_id,
                "name": player_name
            })
            
            if not player:
                await interaction.followup.send(
                    f"Player {player_name} not found on this server.",
                    ephemeral=True
                )
                return
            
            player_id = str(player["_id"])
            
            # Check if player is in the faction
            member = await db.collections["faction_members"].find_one({
                "faction_id": faction.id,
                "player_id": player_id,
                "is_active": True
            })
            
            if not member:
                await interaction.followup.send(
                    f"Player {player_name} is not a member of faction {faction.name}.",
                    ephemeral=True
                )
                return
            
            # Check if removing faction leader
            if member["role"] == "leader":
                await interaction.followup.send(
                    f"Cannot remove {player_name} because they are the faction leader. "
                    "Transfer leadership to another member first.",
                    ephemeral=True
                )
                return
            
            # Confirm removal
            confirmed = await confirm(
                interaction,
                f"Are you sure you want to remove {player_name} from faction {faction.name}?",
                timeout=30
            )
            
            if not confirmed:
                await interaction.followup.send(
                    "Faction removal cancelled.",
                    ephemeral=True
                )
                return
            
            # Remove player from faction
            removed = await faction.remove_member(player_id)
            
            if removed:
                embed = EmbedBuilder.create_success_embed(
                    title="Member Removed",
                    description=f"Player **{player_name}** has been removed from faction **{faction.name}**.",
                    guild=interaction.guild
                )
                
                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send(
                    f"Failed to remove {player_name} from faction.",
                    ephemeral=True
                )
            
        except PermissionError as e:
            await interaction.followup.send(str(e), ephemeral=True)
        except Exception as e:
            logger.error(f"Error removing member from faction: {e}")
            await interaction.followup.send(
                "An error occurred while removing the member. Please try again later.",
                ephemeral=True
            )
    
    async def _faction_promote(
        self,
        interaction: discord.Interaction,
        server_id: str,
        faction_name: str,
        player_name: str,
        role: str
    ):
        """Promote a player in a faction
        
        Args:
            interaction: Discord interaction
            server_id: Server ID
            faction_name: Faction name
            player_name: Player to promote
            role: Role to assign
        """
        # Defer response for potentially long DB operations
        await interaction.response.defer(ephemeral=False)
        
        try:
            # Get faction by name
            faction = await Faction.get_by_name(server_id, faction_name)
            
            if not faction:
                await interaction.followup.send(
                    f"Faction {faction_name} not found.",
                    ephemeral=True
                )
                return
            
            # Check if user has permission to promote members
            await self._check_faction_permission(interaction, faction, leader_only=True)
            
            # Get player ID from name
            db = await get_db()
            player = await db.collections["players"].find_one({
                "server_id": server_id,
                "name": player_name
            })
            
            if not player:
                await interaction.followup.send(
                    f"Player {player_name} not found on this server.",
                    ephemeral=True
                )
                return
            
            player_id = str(player["_id"])
            
            # Check if player is in the faction
            member = await db.collections["faction_members"].find_one({
                "faction_id": faction.id,
                "player_id": player_id,
                "is_active": True
            })
            
            if not member:
                await interaction.followup.send(
                    f"Player {player_name} is not a member of faction {faction.name}.",
                    ephemeral=True
                )
                return
            
            # If promoting to leader, confirm the action
            if role == "leader":
                confirmed = await confirm(
                    interaction,
                    f"Are you sure you want to transfer leadership of {faction.name} to {player_name}? "
                    "You will be demoted to officer.",
                    timeout=30
                )
                
                if not confirmed:
                    await interaction.followup.send(
                        "Leadership transfer cancelled.",
                        ephemeral=True
                    )
                    return
            
            # Update member's role
            await faction.update_role(player_id, role)
            
            # If promoting to leader, demote current leader to officer
            if role == "leader":
                # Get the user's player ID
                player_link = await PlayerLink.get_by_discord_id(interaction.user.id)
                
                if player_link:
                    current_leader_id = player_link.get_player_id_for_server(server_id)
                    
                    if current_leader_id:
                        await faction.update_role(current_leader_id, "officer")
            
            # Send confirmation
            role_name = role.capitalize()
            embed = EmbedBuilder.create_success_embed(
                title="Member Promoted",
                description=f"Player **{player_name}** has been promoted to **{role_name}** in faction **{faction.name}**.",
                guild=interaction.guild
            )
            
            await interaction.followup.send(embed=embed)
            
        except PermissionError as e:
            await interaction.followup.send(str(e), ephemeral=True)
        except Exception as e:
            logger.error(f"Error promoting member in faction: {e}")
            await interaction.followup.send(
                "An error occurred while promoting the member. Please try again later.",
                ephemeral=True
            )
    
    async def _faction_edit(
        self,
        interaction: discord.Interaction,
        server_id: str,
        faction_name: str,
        tag: Optional[str] = None,
        description: Optional[str] = None
    ):
        """Edit faction details
        
        Args:
            interaction: Discord interaction
            server_id: Server ID
            faction_name: Faction name
            tag: New faction tag (optional)
            description: New faction description (optional)
        """
        # Defer response for potentially long DB operations
        await interaction.response.defer(ephemeral=False)
        
        try:
            # Get faction by name
            faction = await Faction.get_by_name(server_id, faction_name)
            
            if not faction:
                await interaction.followup.send(
                    f"Faction {faction_name} not found.",
                    ephemeral=True
                )
                return
            
            # Check if user has permission to edit faction
            await self._check_faction_permission(interaction, faction, leader_only=True)
            
            # Prepare updates
            updates = {}
            
            if tag:
                if len(tag) < 2 or len(tag) > 5:
                    await interaction.followup.send(
                        "Faction tag must be between 2 and 5 characters.",
                        ephemeral=True
                    )
                    return
                updates["tag"] = tag
            
            if description:
                updates["description"] = description
            
            if not updates:
                await interaction.followup.send(
                    "No changes specified.",
                    ephemeral=True
                )
                return
            
            # Update faction
            await faction.update(**updates)
            
            # Confirm changes
            embed = EmbedBuilder.create_success_embed(
                title="Faction Updated",
                description=f"Faction **{faction.name}** has been updated.",
                guild=interaction.guild
            )
            
            for field, value in updates.items():
                embed.add_field(name=field.capitalize(), value=value, inline=True)
            
            await interaction.followup.send(embed=embed)
            
        except PermissionError as e:
            await interaction.followup.send(str(e), ephemeral=True)
        except Exception as e:
            logger.error(f"Error editing faction: {e}")
            await interaction.followup.send(
                "An error occurred while editing the faction. Please try again later.",
                ephemeral=True
            )
    
    async def _faction_stats(
        self,
        interaction: discord.Interaction,
        server_id: str,
        faction_name: Optional[str] = None
    ):
        """Show faction statistics
        
        Args:
            interaction: Discord interaction
            server_id: Server ID
            faction_name: Faction name (optional - if not provided, shows user's faction)
        """
        # Defer response for potentially long DB operations
        await interaction.response.defer(ephemeral=False)
        
        try:
            faction = None
            
            if faction_name:
                # Get faction by name
                faction = await Faction.get_by_name(server_id, faction_name)
            else:
                # Get player's linked faction
                player_link = await PlayerLink.get_by_discord_id(interaction.user.id)
                
                if player_link:
                    player_id = player_link.get_player_id_for_server(server_id)
                    
                    if player_id:
                        faction = await Faction.get_player_faction(player_id)
            
            if not faction:
                await interaction.followup.send(
                    f"Faction {'not specified' if not faction_name else faction_name} not found.",
                    ephemeral=True
                )
                return
            
            # Get faction stats
            stats = await faction.get_stats()
            
            # Get member details
            members = await faction.get_member_details()
            
            # Create stats embed
            embed = EmbedBuilder.create_base_embed(
                title=f"{faction.name} [{faction.tag}] Statistics",
                description=f"Statistics for faction {faction.name}",
                color=faction.color,
                guild=interaction.guild
            )
            
            # Add thumbnail if available
            if faction.icon_url:
                embed.set_thumbnail(url=faction.icon_url)
            
            # Add overall stats
            kills = stats.get("kills", 0)
            deaths = stats.get("deaths", 0)
            kd_ratio = kills / max(deaths, 1)
            
            embed.add_field(name="Members", value=str(faction.member_count), inline=True)
            embed.add_field(name="Total Kills", value=str(kills), inline=True)
            embed.add_field(name="Total Deaths", value=str(deaths), inline=True)
            embed.add_field(name="K/D Ratio", value=f"{kd_ratio:.2f}", inline=True)
            embed.add_field(name="Total Score", value=str(stats.get("total_score", 0)), inline=True)
            
            if "wins" in stats and "losses" in stats:
                wins = stats.get("wins", 0)
                losses = stats.get("losses", 0)
                embed.add_field(name="Win/Loss", value=f"{wins}/{losses}", inline=True)
            
            # Add top members section if we have members
            if members:
                # Sort by kills
                top_killers = sorted(members, key=lambda x: x.get("kills", 0), reverse=True)[:5]
                
                # Create top members text
                top_text = []
                for i, member in enumerate(top_killers):
                    top_text.append(
                        f"{i+1}. **{member['name']}** - "
                        f"K: {member.get('kills', 0)} "
                        f"D: {member.get('deaths', 0)} "
                        f"KD: {member.get('kills', 0) / max(member.get('deaths', 1), 1):.2f}"
                    )
                
                if top_text:
                    embed.add_field(
                        name="Top Members",
                        value="\n".join(top_text),
                        inline=False
                    )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error showing faction stats: {e}")
            await interaction.followup.send(
                "An error occurred while retrieving faction statistics. Please try again later.",
                ephemeral=True
            )
    
    async def _faction_delete(
        self,
        interaction: discord.Interaction,
        server_id: str,
        faction_name: str
    ):
        """Delete a faction
        
        Args:
            interaction: Discord interaction
            server_id: Server ID
            faction_name: Faction name
        """
        # Defer response for potentially long DB operations
        await interaction.response.defer(ephemeral=False)
        
        try:
            # Get faction by name
            faction = await Faction.get_by_name(server_id, faction_name)
            
            if not faction:
                await interaction.followup.send(
                    f"Faction {faction_name} not found.",
                    ephemeral=True
                )
                return
            
            # Check if user has permission to delete faction
            await self._check_faction_permission(interaction, faction, leader_only=True)
            
            # Confirm deletion
            confirmed = await confirm(
                interaction,
                f"Are you sure you want to delete faction {faction.name}? "
                "This action cannot be undone and all members will be removed from the faction.",
                timeout=30
            )
            
            if not confirmed:
                await interaction.followup.send(
                    "Faction deletion cancelled.",
                    ephemeral=True
                )
                return
            
            # Delete faction
            await faction.delete()
            
            # Confirm deletion
            embed = EmbedBuilder.create_success_embed(
                title="Faction Deleted",
                description=f"Faction **{faction.name}** has been deleted.",
                guild=interaction.guild
            )
            
            await interaction.followup.send(embed=embed)
            
        except PermissionError as e:
            await interaction.followup.send(str(e), ephemeral=True)
        except Exception as e:
            logger.error(f"Error deleting faction: {e}")
            await interaction.followup.send(
                "An error occurred while deleting the faction. Please try again later.",
                ephemeral=True
            )
    
    async def _check_faction_permission(
        self,
        interaction: discord.Interaction,
        faction: Faction,
        leader_only: bool = False
    ) -> bool:
        """Check if user has permission to manage the faction
        
        Args:
            interaction: Discord interaction
            faction: Faction to check
            leader_only: Whether only leader has permission
            
        Returns:
            bool: True if user has permission
            
        Raises:
            PermissionError: If user does not have permission
        """
        # Check if user is admin
        if has_admin_permission(interaction):
            return True
        
        # Get player link for the user
        player_link = await PlayerLink.get_by_discord_id(interaction.user.id)
        
        if not player_link:
            raise PermissionError(
                "You need to link your Discord account to an in-game character first. "
                "Use `/player link` command."
            )
        
        # Get player ID for this server
        player_id = player_link.get_player_id_for_server(faction.server_id)
        
        if not player_id:
            raise PermissionError(
                f"You don't have a character linked to server {faction.server_id}."
            )
        
        # Check if player is in the faction
        db = await get_db()
        member = await db.collections["faction_members"].find_one({
            "faction_id": faction.id,
            "player_id": player_id,
            "is_active": True
        })
        
        if not member:
            raise PermissionError(
                f"You're not a member of faction {faction.name}."
            )
        
        # Check if player has required role
        role = member["role"]
        
        if leader_only and role != "leader":
            raise PermissionError(
                f"Only the faction leader can perform this action."
            )
        
        if not leader_only and role not in ["leader", "officer"]:
            raise PermissionError(
                f"Only faction leaders and officers can perform this action."
            )
        
        return True

async def setup(bot: commands.Bot):
    """Add the Factions cog to the bot
    
    Args:
        bot: Bot instance
    """
    await bot.add_cog(Factions(bot))