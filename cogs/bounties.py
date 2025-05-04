"""
Bounty system commands for the Tower of Temptation PvP Statistics Bot.

This module provides commands to place, view, and claim bounties on players.
Bounties are a premium feature (Tier 2+) that allow players to place rewards
for killing specific targets.
"""
import asyncio
import random
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union, Any

import discord
from discord import app_commands
from discord.ext import commands, tasks

from models.bounty import Bounty
from models.player import Player
from models.economy import Economy
from models.guild import Guild
from utils.embed_builder import EmbedBuilder
from utils.helpers import get_bot_name
from utils.decorators import premium_tier_required, has_admin_permission, has_mod_permission
from utils.discord_utils import get_server_selection

logger = logging.getLogger(__name__)

class BountiesCog(commands.Cog):
    """Commands for managing player bounties."""
    
    def __init__(self, bot):
        self.bot = bot
        self.name = "Bounties"
        self.description = "Place and claim bounties on players"
        
        # Start the background task for expiring bounties
        self.expire_bounties_task.start()
        
        # Start the auto-bounty detection task
        self.auto_bounty_detection_task.start()
    
    def cog_unload(self):
        """Called when the cog is unloaded."""
        self.expire_bounties_task.cancel()
        self.auto_bounty_detection_task.cancel()
    
    @tasks.loop(minutes=5)
    async def expire_bounties_task(self):
        """Background task to expire old bounties."""
        try:
            expired_count = await Bounty.expire_old_bounties()
            if expired_count > 0:
                logger.info(f"Expired {expired_count} bounties")
        except Exception as e:
            logger.error(f"Error in expire_bounties_task: {e}", exc_info=True)
    
    @tasks.loop(minutes=5)
    async def auto_bounty_detection_task(self):
        """Background task to detect and place bounties on players with killstreaks."""
        try:
            # Check all guilds with premium tier 2+
            cursor = self.bot.db.guilds.find({"premium_tier": {"$gt": 1}})
            
            async for guild_doc in cursor:
                guild_id = guild_doc.get("guild_id")
                if not guild_id:
                    continue
                
                # Skip guilds without auto-bounty enabled
                auto_bounty_settings = guild_doc.get("auto_bounty", {})
                if not auto_bounty_settings.get("enabled", False):
                    continue
                
                # Get settings
                min_reward = int(auto_bounty_settings.get("min_reward", 100))
                max_reward = int(auto_bounty_settings.get("max_reward", 500))
                kill_threshold = int(auto_bounty_settings.get("kill_threshold", 5))
                repeat_threshold = int(auto_bounty_settings.get("repeat_threshold", 3))
                time_window = int(auto_bounty_settings.get("time_window", 10))
                
                # Process each server in the guild
                for server in guild_doc.get("servers", []):
                    server_id = server.get("server_id")
                    if not server_id or not server.get("active", False):
                        continue
                    
                    # Get potential bounty targets
                    potential_bounties = await Bounty.get_player_stats_for_bounty(
                        guild_id=str(guild_id),
                        server_id=server_id,
                        minutes=time_window,
                        kill_threshold=kill_threshold,
                        repeat_threshold=repeat_threshold
                    )
                    
                    if not potential_bounties:
                        continue
                    
                    # Randomly pick one potential bounty
                    target = random.choice(potential_bounties)
                    
                    # Check if target already has an active bounty
                    active_bounties = await Bounty.get_active_bounties_for_target(
                        guild_id=str(guild_id),
                        server_id=server_id,
                        target_id=target["player_id"]
                    )
                    
                    if active_bounties:
                        continue
                    
                    # Generate a random reward
                    reward = random.randint(min_reward, max_reward)
                    
                    # Place a bounty
                    bounty = await Bounty.create(
                        guild_id=str(guild_id),
                        server_id=server_id,
                        target_id=target["player_id"],
                        target_name=target["player_name"],
                        placed_by=str(self.bot.user.id),
                        placed_by_name=get_bot_name(self.bot, guild_id),
                        reason=target["reason"],
                        reward=reward,
                        source=Bounty.SOURCE_AUTO
                    )
                    
                    # Send notification to the bounty channel if configured
                    bounty_channel_id = server.get("bounty_channel")
                    if bounty_channel_id:
                        try:
                            channel = self.bot.get_channel(int(bounty_channel_id))
                            if not channel:
                                continue
                            
                            # Create an embed for the auto-bounty
                            embed = discord.Embed(
                                title="🎯 Auto-Bounty Placed!",
                                description=f"A bounty has been automatically placed on **{target['player_name']}**!",
                                color=0xFF5500
                            )
                            embed.add_field(name="Reason", value=target["reason"], inline=False)
                            embed.add_field(name="Reward", value=f"{reward} credits", inline=True)
                            embed.add_field(name="Expires", value="In 1 hour", inline=True)
                            embed.set_footer(text=f"Kill {target['player_name']} to claim this bounty • ID: {bounty.id}")
                            
                            await channel.send(embed=embed)
                        except Exception as e:
                            logger.error(f"Error sending auto-bounty notification: {e}")
        
        except Exception as e:
            logger.error(f"Error in auto_bounty_detection_task: {e}", exc_info=True)
    
    @expire_bounties_task.before_loop
    @auto_bounty_detection_task.before_loop
    async def before_task(self):
        """Wait until the bot is ready before starting tasks."""
        await self.bot.wait_until_ready()
    
    # === Event Handlers ===
    
    @commands.Cog.listener()
    async def on_csv_kill_parsed(self, kill_data: Dict[str, Any]):
        """Event handler for when a kill is parsed from CSV.
        
        This is used to automatically claim bounties when a target is killed.
        """
        try:
            guild_id = kill_data.get("guild_id")
            server_id = kill_data.get("server_id")
            killer_id = kill_data.get("killer_id")
            killer_name = kill_data.get("killer_name")
            victim_id = kill_data.get("victim_id")
            
            if not all([guild_id, server_id, killer_id, killer_name, victim_id]):
                return
            
            # Check if there are any bounties on the victim
            claimed_bounties = await Bounty.check_bounties_for_kill(
                guild_id=str(guild_id),
                server_id=str(server_id),
                killer_id=str(killer_id),
                killer_name=str(killer_name),
                victim_id=str(victim_id)
            )
            
            if not claimed_bounties:
                return
            
            # Send notification to the bounty channel for each claimed bounty
            for bounty in claimed_bounties:
                try:
                    # Get the server config
                    guild_doc = await self.bot.db.guilds.find_one({"guild_id": int(guild_id)})
                    if not guild_doc:
                        continue
                    
                    server = None
                    for s in guild_doc.get("servers", []):
                        if s.get("server_id") == server_id:
                            server = s
                            break
                    
                    if not server:
                        continue
                    
                    # Check if the server has a bounty channel configured
                    bounty_channel_id = server.get("bounty_channel")
                    if not bounty_channel_id:
                        continue
                    
                    # Get the channel
                    channel = self.bot.get_channel(int(bounty_channel_id))
                    if not channel:
                        continue
                    
                    # Create an embed for the claimed bounty
                    embed = discord.Embed(
                        title="🏆 Bounty Claimed!",
                        description=f"**{killer_name}** has claimed a bounty by killing **{bounty.target_name}**!",
                        color=0x00FF00
                    )
                    embed.add_field(name="Reason", value=bounty.reason, inline=False)
                    embed.add_field(name="Reward", value=f"{bounty.reward} credits", inline=True)
                    embed.add_field(name="Placed By", value=bounty.placed_by_name, inline=True)
                    embed.set_footer(text=f"Bounty claimed • ID: {bounty.id}")
                    
                    await channel.send(embed=embed)
                except Exception as e:
                    logger.error(f"Error sending bounty claim notification: {e}")
        
        except Exception as e:
            logger.error(f"Error processing kill for bounties: {e}", exc_info=True)
    
    # === Command Group ===
    
    bounty_group = app_commands.Group(
        name="bounty",
        description="Place or manage bounties on players"
    )
    
    @bounty_group.command(name="place")
    @app_commands.describe(
        target="The player to place a bounty on",
        amount="The amount of credits to offer as a reward",
        reason="The reason for placing this bounty (optional)"
    )
    @premium_tier_required(2)
    async def bounty_place_command(self, interaction: discord.Interaction,
                               target: str, amount: int, reason: str = "No reason provided"):
        """Place a bounty on a player"""
        guild_id = interaction.guild_id
        
        # Make sure we have a valid guild
        if not guild_id:
            await interaction.response.send_message(
                embed=EmbedBuilder.error(
                    "This command can only be used in a guild.",
                    get_bot_name(self.bot, guild_id)
                )
            )
            return
        
        # Select the server to use
        server_id = await get_server_selection(interaction, self.bot)
        if not server_id:
            return
        
        # Find the target player
        db = self.bot.db
        target_player = await Player.get_by_player_name(db, target, server_id)
        
        if not target_player:
            await interaction.response.send_message(
                embed=EmbedBuilder.error(
                    f"Could not find player '{target}' on this server.",
                    get_bot_name(self.bot, guild_id)
                )
            )
            return
        
        # Prevent placing bounties on yourself
        player_link = await db.collections["player_links"].find_one({
            "guild_id": guild_id,
            "server_id": server_id,
            "discord_id": str(interaction.user.id),
            "verified": True
        })
        
        if player_link and player_link.get("player_id") == target_player.player_id:
            await interaction.response.send_message(
                embed=EmbedBuilder.error(
                    "You cannot place a bounty on yourself!",
                    get_bot_name(self.bot, guild_id)
                )
            )
            return
        
        # Validate bounty amount
        if amount < 50:
            await interaction.response.send_message(
                embed=EmbedBuilder.error(
                    "Bounty amount must be at least 50 credits.",
                    get_bot_name(self.bot, guild_id)
                )
            )
            return
        
        if amount > 10000:
            await interaction.response.send_message(
                embed=EmbedBuilder.error(
                    "Bounty amount cannot exceed 10,000 credits.",
                    get_bot_name(self.bot, guild_id)
                )
            )
            return
        
        # Make sure the user has enough balance
        user_economy = None
        
        # Check if the user has a linked player account
        if player_link:
            user_economy = await Economy.get_by_player(
                db, player_link.get("player_id"), server_id
            )
        
        # If no linked account or not enough balance
        if not user_economy or user_economy.currency < amount:
            await interaction.response.send_message(
                embed=EmbedBuilder.error(
                    f"You don't have enough credits to place this bounty. Link your player account and earn more credits!",
                    get_bot_name(self.bot, guild_id)
                )
            )
            return
        
        # At this point, we can place the bounty
        await interaction.response.defer()
        
        try:
            # Deduct the bounty amount from the user's balance
            await user_economy.remove_currency(amount, "bounty_placement", {
                "target_id": target_player.player_id,
                "target_name": target_player.player_name
            })
            
            # Create the bounty
            bounty = await Bounty.create(
                guild_id=str(guild_id),
                server_id=server_id,
                target_id=target_player.player_id,
                target_name=target_player.player_name,
                placed_by=str(interaction.user.id),
                placed_by_name=interaction.user.display_name,
                reason=reason,
                reward=amount
            )
            
            # Send a success message
            embed = EmbedBuilder.success(
                f"Bounty of {amount} credits placed on {target_player.player_name}!",
                get_bot_name(self.bot, guild_id)
            )
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.add_field(name="Reward", value=f"{amount} credits", inline=True)
            embed.add_field(name="Expires", value="In 1 hour", inline=True)
            
            await interaction.followup.send(embed=embed)
            
            # Send a notification to the bounty channel if configured
            guild_doc = await db.guilds.find_one({"guild_id": guild_id})
            if guild_doc:
                for server in guild_doc.get("servers", []):
                    if server.get("server_id") == server_id:
                        # Check if the server has a bounty channel configured
                        bounty_channel_id = server.get("bounty_channel")
                        if bounty_channel_id:
                            try:
                                channel = interaction.guild.get_channel(int(bounty_channel_id))
                                if channel and channel.id != interaction.channel_id:
                                    # Create an embed for the bounty notification
                                    notify_embed = discord.Embed(
                                        title="🎯 New Bounty!",
                                        description=f"A bounty has been placed on **{target_player.player_name}**!",
                                        color=0xFF5500
                                    )
                                    notify_embed.add_field(name="Placed By", value=interaction.user.display_name, inline=True)
                                    notify_embed.add_field(name="Reason", value=reason, inline=False)
                                    notify_embed.add_field(name="Reward", value=f"{amount} credits", inline=True)
                                    notify_embed.add_field(name="Expires", value="In 1 hour", inline=True)
                                    notify_embed.set_footer(text=f"Kill {target_player.player_name} to claim this bounty • ID: {bounty.id}")
                                    
                                    await channel.send(embed=notify_embed)
                            except Exception as e:
                                logger.error(f"Error sending bounty notification: {e}")
                        break
        
        except Exception as e:
            logger.error(f"Error placing bounty: {e}", exc_info=True)
            await interaction.followup.send(
                embed=EmbedBuilder.error(
                    "An error occurred while placing the bounty. Please try again later.",
                    get_bot_name(self.bot, guild_id)
                )
            )
    
    bounties_group = app_commands.Group(
        name="bounties",
        description="View and manage bounties"
    )
    
    @bounties_group.command(name="active")
    @app_commands.describe(
        server="The server to check (if you have multiple configured)"
    )
    @premium_tier_required(2)
    async def bounties_active_command(self, interaction: discord.Interaction, server: str = None):
        """View all active bounties"""
        guild_id = interaction.guild_id
        
        # Make sure we have a valid guild
        if not guild_id:
            await interaction.response.send_message(
                embed=EmbedBuilder.error(
                    "This command can only be used in a guild.",
                    get_bot_name(self.bot, guild_id)
                )
            )
            return
        
        # Select the server to use
        server_id = await get_server_selection(interaction, self.bot, server)
        if not server_id:
            return
        
        await interaction.response.defer()
        
        # Get all active bounties
        bounties = await Bounty.get_active_bounties(str(guild_id), server_id)
        
        if not bounties:
            await interaction.followup.send(
                embed=EmbedBuilder.info(
                    "There are no active bounties at the moment.",
                    get_bot_name(self.bot, guild_id)
                )
            )
            return
        
        # Create an embed to display the bounties
        embed = discord.Embed(
            title="🎯 Active Bounties",
            description=f"There are {len(bounties)} active bounties on this server.",
            color=0xFF5500
        )
        
        # Add fields for each bounty
        for i, bounty in enumerate(bounties[:10], 1):
            expires_in = bounty.expires_at - datetime.utcnow()
            expires_minutes = max(0, int(expires_in.total_seconds() / 60))
            
            embed.add_field(
                name=f"{i}. {bounty.target_name}",
                value=(
                    f"**Reward:** {bounty.reward} credits\n"
                    f"**Reason:** {bounty.reason}\n"
                    f"**Placed by:** {bounty.placed_by_name}\n"
                    f"**Expires in:** {expires_minutes} minutes"
                ),
                inline=False
            )
        
        # Add a note if there are more bounties
        if len(bounties) > 10:
            embed.add_field(
                name="Note",
                value=f"Showing 10 of {len(bounties)} bounties. Use '/bounties search' to find specific bounties.",
                inline=False
            )
        
        embed.set_footer(text=f"Powered by {get_bot_name(self.bot, guild_id)}")
        
        await interaction.followup.send(embed=embed)
    
    @bounties_group.command(name="my")
    @app_commands.describe(
        server="The server to check (if you have multiple configured)"
    )
    @premium_tier_required(2)
    async def bounties_my_command(self, interaction: discord.Interaction, server: str = None):
        """View bounties you've placed"""
        guild_id = interaction.guild_id
        
        # Make sure we have a valid guild
        if not guild_id:
            await interaction.response.send_message(
                embed=EmbedBuilder.error(
                    "This command can only be used in a guild.",
                    get_bot_name(self.bot, guild_id)
                )
            )
            return
        
        # Select the server to use
        server_id = await get_server_selection(interaction, self.bot, server)
        if not server_id:
            return
        
        await interaction.response.defer()
        
        # Get bounties placed by the user
        bounties = await Bounty.get_bounties_placed_by(
            str(guild_id), server_id, str(interaction.user.id)
        )
        
        if not bounties:
            await interaction.followup.send(
                embed=EmbedBuilder.info(
                    "You haven't placed any bounties yet.",
                    get_bot_name(self.bot, guild_id)
                )
            )
            return
        
        # Create an embed to display the bounties
        embed = discord.Embed(
            title="🎯 Your Bounties",
            description=f"You have placed {len(bounties)} bounties.",
            color=0xFF5500
        )
        
        # Group bounties by status
        active_bounties = [b for b in bounties if b.status == Bounty.STATUS_ACTIVE]
        claimed_bounties = [b for b in bounties if b.status == Bounty.STATUS_CLAIMED]
        expired_bounties = [b for b in bounties if b.status == Bounty.STATUS_EXPIRED]
        
        # Add fields for active bounties
        if active_bounties:
            embed.add_field(
                name="Active Bounties",
                value=f"You have {len(active_bounties)} active bounties.",
                inline=False
            )
            
            for i, bounty in enumerate(active_bounties[:5], 1):
                expires_in = bounty.expires_at - datetime.utcnow()
                expires_minutes = max(0, int(expires_in.total_seconds() / 60))
                
                embed.add_field(
                    name=f"{i}. {bounty.target_name}",
                    value=(
                        f"**Reward:** {bounty.reward} credits\n"
                        f"**Reason:** {bounty.reason}\n"
                        f"**Expires in:** {expires_minutes} minutes"
                    ),
                    inline=False
                )
        
        # Add fields for recently claimed bounties
        if claimed_bounties:
            embed.add_field(
                name="Claimed Bounties",
                value=f"You have {len(claimed_bounties)} claimed bounties.",
                inline=False
            )
            
            for i, bounty in enumerate(claimed_bounties[:3], 1):
                embed.add_field(
                    name=f"{i}. {bounty.target_name}",
                    value=(
                        f"**Reward:** {bounty.reward} credits\n"
                        f"**Claimed by:** {bounty.claimed_by_name}\n"
                        f"**Claimed at:** {bounty.claimed_at.strftime('%Y-%m-%d %H:%M:%S')}"
                    ),
                    inline=False
                )
        
        # Add note about expired bounties
        if expired_bounties:
            embed.add_field(
                name="Expired Bounties",
                value=f"You have {len(expired_bounties)} expired bounties.",
                inline=False
            )
        
        embed.set_footer(text=f"Powered by {get_bot_name(self.bot, guild_id)}")
        
        await interaction.followup.send(embed=embed)
    
    @bounties_group.command(name="claimed")
    @app_commands.describe(
        server="The server to check (if you have multiple configured)"
    )
    @premium_tier_required(2)
    async def bounties_claimed_command(self, interaction: discord.Interaction, server: str = None):
        """View bounties you've claimed"""
        guild_id = interaction.guild_id
        
        # Make sure we have a valid guild
        if not guild_id:
            await interaction.response.send_message(
                embed=EmbedBuilder.error(
                    "This command can only be used in a guild.",
                    get_bot_name(self.bot, guild_id)
                )
            )
            return
        
        # Select the server to use
        server_id = await get_server_selection(interaction, self.bot, server)
        if not server_id:
            return
        
        # Check if the user has a linked player account
        player_link = await self.bot.db.collections["player_links"].find_one({
            "guild_id": guild_id,
            "server_id": server_id,
            "discord_id": str(interaction.user.id),
            "verified": True
        })
        
        if not player_link:
            await interaction.response.send_message(
                embed=EmbedBuilder.error(
                    "You need to link your player account to view claimed bounties.",
                    get_bot_name(self.bot, guild_id)
                )
            )
            return
        
        await interaction.response.defer()
        
        # Get bounties claimed by the user
        bounties = await Bounty.get_bounties_claimed_by(
            str(guild_id), server_id, str(interaction.user.id)
        )
        
        if not bounties:
            await interaction.followup.send(
                embed=EmbedBuilder.info(
                    "You haven't claimed any bounties yet.",
                    get_bot_name(self.bot, guild_id)
                )
            )
            return
        
        # Create an embed to display the bounties
        embed = discord.Embed(
            title="🏆 Your Claimed Bounties",
            description=f"You have claimed {len(bounties)} bounties.",
            color=0x00FF00
        )
        
        # Add fields for each bounty
        for i, bounty in enumerate(bounties[:10], 1):
            embed.add_field(
                name=f"{i}. {bounty.target_name}",
                value=(
                    f"**Reward:** {bounty.reward} credits\n"
                    f"**Reason:** {bounty.reason}\n"
                    f"**Placed by:** {bounty.placed_by_name}\n"
                    f"**Claimed at:** {bounty.claimed_at.strftime('%Y-%m-%d %H:%M:%S')}"
                ),
                inline=False
            )
        
        # Add a note if there are more bounties
        if len(bounties) > 10:
            embed.add_field(
                name="Note",
                value=f"Showing 10 of {len(bounties)} claimed bounties.",
                inline=False
            )
        
        # Calculate total earnings
        total_earnings = sum(b.reward for b in bounties)
        embed.add_field(
            name="Total Earnings",
            value=f"You've earned a total of {total_earnings} credits from bounties!",
            inline=False
        )
        
        embed.set_footer(text=f"Powered by {get_bot_name(self.bot, guild_id)}")
        
        await interaction.followup.send(embed=embed)
    
    # === Admin Commands ===
    
    @bounty_group.command(name="settings")
    @app_commands.describe(
        action="The action to perform",
        channel="The channel to use for bounty notifications",
        enabled="Whether auto-bounties should be enabled",
        min_reward="Minimum reward for auto-bounties",
        max_reward="Maximum reward for auto-bounties",
        kill_threshold="Minimum kills to trigger a killstreak bounty",
        repeat_threshold="Minimum kills on the same victim to trigger a repeat bounty",
        time_window="Time window (in minutes) to check for killstreaks"
    )
    @has_admin_permission()
    @premium_tier_required(2)
    async def bounty_settings_command(
        self, interaction: discord.Interaction,
        action: str,
        channel: discord.TextChannel = None,
        enabled: bool = None,
        min_reward: int = None,
        max_reward: int = None,
        kill_threshold: int = None,
        repeat_threshold: int = None,
        time_window: int = None
    ):
        """Configure bounty system settings (Admin only)"""
        guild_id = interaction.guild_id
        
        # Make sure we have a valid guild
        if not guild_id:
            await interaction.response.send_message(
                embed=EmbedBuilder.error(
                    "This command can only be used in a guild.",
                    get_bot_name(self.bot, guild_id)
                )
            )
            return
        
        # Select the server to use
        server_id = await get_server_selection(interaction, self.bot)
        if not server_id:
            return
        
        await interaction.response.defer()
        
        if action.lower() == "show":
            # Show current settings
            guild_doc = await self.bot.db.guilds.find_one({"guild_id": guild_id})
            if not guild_doc:
                await interaction.followup.send(
                    embed=EmbedBuilder.error(
                        "Guild not found in database.",
                        get_bot_name(self.bot, guild_id)
                    )
                )
                return
            
            # Find the server
            server = None
            for s in guild_doc.get("servers", []):
                if s.get("server_id") == server_id:
                    server = s
                    break
            
            if not server:
                await interaction.followup.send(
                    embed=EmbedBuilder.error(
                        "Server not found in guild configuration.",
                        get_bot_name(self.bot, guild_id)
                    )
                )
                return
            
            # Get bounty channel
            bounty_channel_id = server.get("bounty_channel")
            bounty_channel_name = "None"
            if bounty_channel_id:
                channel = interaction.guild.get_channel(int(bounty_channel_id))
                if channel:
                    bounty_channel_name = f"#{channel.name}"
            
            # Get auto-bounty settings
            auto_bounty = guild_doc.get("auto_bounty", {})
            enabled = auto_bounty.get("enabled", False)
            min_reward = auto_bounty.get("min_reward", 100)
            max_reward = auto_bounty.get("max_reward", 500)
            kill_threshold = auto_bounty.get("kill_threshold", 5)
            repeat_threshold = auto_bounty.get("repeat_threshold", 3)
            time_window = auto_bounty.get("time_window", 10)
            
            # Create an embed to display settings
            embed = discord.Embed(
                title="⚙️ Bounty System Settings",
                description="Current configuration for the bounty system.",
                color=0x4287f5
            )
            
            embed.add_field(
                name="Bounty Channel",
                value=bounty_channel_name,
                inline=False
            )
            
            embed.add_field(
                name="Auto-Bounty Settings",
                value=(
                    f"**Enabled:** {'Yes' if enabled else 'No'}\n"
                    f"**Reward Range:** {min_reward} - {max_reward} credits\n"
                    f"**Kill Threshold:** {kill_threshold} kills\n"
                    f"**Repeat Threshold:** {repeat_threshold} kills on same victim\n"
                    f"**Time Window:** {time_window} minutes"
                ),
                inline=False
            )
            
            embed.set_footer(text=f"Powered by {get_bot_name(self.bot, guild_id)}")
            
            await interaction.followup.send(embed=embed)
            return
        
        if action.lower() == "setchannel":
            # Set bounty channel
            if not channel:
                await interaction.followup.send(
                    embed=EmbedBuilder.error(
                        "You must specify a channel to use for bounty notifications.",
                        get_bot_name(self.bot, guild_id)
                    )
                )
                return
            
            # Update the server configuration
            result = await self.bot.db.guilds.update_one(
                {
                    "guild_id": guild_id,
                    "servers.server_id": server_id
                },
                {
                    "$set": {
                        "servers.$.bounty_channel": str(channel.id)
                    }
                }
            )
            
            if result.modified_count > 0:
                await interaction.followup.send(
                    embed=EmbedBuilder.success(
                        f"Bounty channel set to {channel.mention}.",
                        get_bot_name(self.bot, guild_id)
                    )
                )
            else:
                await interaction.followup.send(
                    embed=EmbedBuilder.error(
                        "Failed to update bounty channel. Please try again later.",
                        get_bot_name(self.bot, guild_id)
                    )
                )
            
            return
        
        if action.lower() == "autobounty":
            # Set auto-bounty settings
            if all(param is None for param in [enabled, min_reward, max_reward, kill_threshold, repeat_threshold, time_window]):
                await interaction.followup.send(
                    embed=EmbedBuilder.error(
                        "You must specify at least one setting to update.",
                        get_bot_name(self.bot, guild_id)
                    )
                )
                return
            
            # Get existing settings
            guild_doc = await self.bot.db.guilds.find_one({"guild_id": guild_id})
            auto_bounty = guild_doc.get("auto_bounty", {})
            
            # Update settings
            update_data = {}
            
            if enabled is not None:
                update_data["auto_bounty.enabled"] = enabled
            
            if min_reward is not None:
                if min_reward < 50 or min_reward > 10000:
                    await interaction.followup.send(
                        embed=EmbedBuilder.error(
                            "Minimum reward must be between 50 and 10,000 credits.",
                            get_bot_name(self.bot, guild_id)
                        )
                    )
                    return
                update_data["auto_bounty.min_reward"] = min_reward
            
            if max_reward is not None:
                if max_reward < 50 or max_reward > 10000:
                    await interaction.followup.send(
                        embed=EmbedBuilder.error(
                            "Maximum reward must be between 50 and 10,000 credits.",
                            get_bot_name(self.bot, guild_id)
                        )
                    )
                    return
                update_data["auto_bounty.max_reward"] = max_reward
            
            # Check if min > max
            effective_min = min_reward if min_reward is not None else auto_bounty.get("min_reward", 100)
            effective_max = max_reward if max_reward is not None else auto_bounty.get("max_reward", 500)
            
            if effective_min > effective_max:
                await interaction.followup.send(
                    embed=EmbedBuilder.error(
                        "Minimum reward cannot be greater than maximum reward.",
                        get_bot_name(self.bot, guild_id)
                    )
                )
                return
            
            if kill_threshold is not None:
                if kill_threshold < 3 or kill_threshold > 20:
                    await interaction.followup.send(
                        embed=EmbedBuilder.error(
                            "Kill threshold must be between 3 and 20.",
                            get_bot_name(self.bot, guild_id)
                        )
                    )
                    return
                update_data["auto_bounty.kill_threshold"] = kill_threshold
            
            if repeat_threshold is not None:
                if repeat_threshold < 2 or repeat_threshold > 10:
                    await interaction.followup.send(
                        embed=EmbedBuilder.error(
                            "Repeat threshold must be between 2 and 10.",
                            get_bot_name(self.bot, guild_id)
                        )
                    )
                    return
                update_data["auto_bounty.repeat_threshold"] = repeat_threshold
            
            if time_window is not None:
                if time_window < 5 or time_window > 60:
                    await interaction.followup.send(
                        embed=EmbedBuilder.error(
                            "Time window must be between 5 and 60 minutes.",
                            get_bot_name(self.bot, guild_id)
                        )
                    )
                    return
                update_data["auto_bounty.time_window"] = time_window
            
            # Update the settings
            result = await self.bot.db.guilds.update_one(
                {"guild_id": guild_id},
                {"$set": update_data}
            )
            
            if result.modified_count > 0:
                await interaction.followup.send(
                    embed=EmbedBuilder.success(
                        "Auto-bounty settings updated successfully.",
                        get_bot_name(self.bot, guild_id)
                    )
                )
            else:
                await interaction.followup.send(
                    embed=EmbedBuilder.error(
                        "Failed to update auto-bounty settings. Please try again later.",
                        get_bot_name(self.bot, guild_id)
                    )
                )
            
            return
        
        # If we get here, the action was invalid
        await interaction.followup.send(
            embed=EmbedBuilder.error(
                f"Invalid action: {action}. Valid actions are: show, setchannel, autobounty",
                get_bot_name(self.bot, guild_id)
            )
        )
    
    # === Utility Methods ===
    
    async def place_bounty(self, interaction, server_id: str, target_name: str,
                        amount: int, reason: str, source: str = Bounty.SOURCE_PLAYER):
        """Place a bounty on a player.
        
        This method is used internally by the command handlers.
        """
        guild_id = interaction.guild_id
        db = self.bot.db
        
        # Find the target player
        target_player = await Player.get_by_player_name(db, target_name, server_id)
        
        if not target_player:
            await interaction.followup.send(
                embed=EmbedBuilder.error(
                    f"Could not find player '{target_name}' on this server.",
                    get_bot_name(self.bot, guild_id)
                )
            )
            return None
        
        # Prevent placing bounties on yourself
        player_link = await db.collections["player_links"].find_one({
            "guild_id": guild_id,
            "server_id": server_id,
            "discord_id": str(interaction.user.id),
            "verified": True
        })
        
        if player_link and player_link.get("player_id") == target_player.player_id:
            await interaction.followup.send(
                embed=EmbedBuilder.error(
                    "You cannot place a bounty on yourself!",
                    get_bot_name(self.bot, guild_id)
                )
            )
            return None
        
        # Validate bounty amount
        if amount < 50 or amount > 10000:
            await interaction.followup.send(
                embed=EmbedBuilder.error(
                    "Bounty amount must be between 50 and 10,000 credits.",
                    get_bot_name(self.bot, guild_id)
                )
            )
            return None
        
        # Make sure the user has enough balance (if it's a player-placed bounty)
        if source == Bounty.SOURCE_PLAYER:
            user_economy = None
            
            # Check if the user has a linked player account
            if player_link:
                user_economy = await Economy.get_by_player(
                    db, player_link.get("player_id"), server_id
                )
            
            # If no linked account or not enough balance
            if not user_economy or user_economy.currency < amount:
                await interaction.followup.send(
                    embed=EmbedBuilder.error(
                        f"You don't have enough credits to place this bounty. Link your player account and earn more credits!",
                        get_bot_name(self.bot, guild_id)
                    )
                )
                return None
            
            # Deduct the bounty amount from the user's balance
            await user_economy.remove_currency(amount, "bounty_placement", {
                "target_id": target_player.player_id,
                "target_name": target_player.player_name
            })
        
        # Create the bounty
        bounty = await Bounty.create(
            guild_id=str(guild_id),
            server_id=server_id,
            target_id=target_player.player_id,
            target_name=target_player.player_name,
            placed_by=str(interaction.user.id),
            placed_by_name=interaction.user.display_name,
            reason=reason,
            reward=amount,
            source=source
        )
        
        return bounty
    
    # === Command Mapping ===
    
    @app_commands.command(name="bounty")
    @app_commands.describe(
        action="The action to perform",
        target="The player to place a bounty on",
        amount="The amount of credits to offer as a reward",
        reason="The reason for placing this bounty (optional)"
    )
    @premium_tier_required(2)
    async def bounty_command(self, interaction: discord.Interaction,
                         action: str,
                         target: str = None,
                         amount: int = None,
                         reason: str = None):
        """Place or manage bounties on players"""
        # This command just maps to the appropriate subcommand
        if action.lower() == "place":
            if not target or not amount:
                await interaction.response.send_message(
                    embed=EmbedBuilder.error(
                        "You must specify a target and amount when placing a bounty.",
                        get_bot_name(self.bot, interaction.guild_id)
                    )
                )
                return
            
            await self.bounty_place_command(interaction, target, amount, reason or "No reason provided")
        else:
            await interaction.response.send_message(
                embed=EmbedBuilder.error(
                    f"Invalid action: {action}. Valid actions are: place",
                    get_bot_name(self.bot, interaction.guild_id)
                )
            )


async def setup(bot):
    """Add the cog to the bot."""
    await bot.add_cog(BountiesCog(bot))