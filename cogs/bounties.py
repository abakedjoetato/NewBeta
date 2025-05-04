"""
Bounties Cog for Tower of Temptation PvP Statistics Discord Bot

This cog provides commands for managing player bounties:
1. Place a bounty on a player
2. View active bounties
3. View placed/claimed bounties
4. Configure auto-bounties (admin only)
"""
import logging
import random
import discord
from discord import app_commands
from discord.ext import commands, tasks
from typing import Optional, Dict, List, Any, Union
from datetime import datetime, timedelta

from models.player import Player
from models.guild import Guild
from models.bounty import Bounty
from models.player_link import PlayerLink
from models.economy import Economy
from utils.embed_builder import EmbedBuilder
from utils.helpers import has_admin_permission, has_mod_permission, confirm, get_bot_name
from utils.async_utils import BackgroundTask

logger = logging.getLogger(__name__)

# Constants
MIN_BOUNTY_AMOUNT = 100
MAX_BOUNTY_AMOUNT = 10000
AUTO_BOUNTY_CHECK_INTERVAL = 5 * 60  # 5 minutes
DEFAULT_AUTO_BOUNTY_AMOUNT_MIN = 100
DEFAULT_AUTO_BOUNTY_AMOUNT_MAX = 500
AUTO_BOUNTY_KILLSTREAK_THRESHOLD = 5
AUTO_BOUNTY_REPEAT_THRESHOLD = 3
AUTO_BOUNTY_TIME_WINDOW_MINUTES = 10

class BountiesCog(commands.Cog):
    """Bounty commands for the Tower of Temptation PvP Statistics Discord Bot"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.auto_bounty_task = BackgroundTask(self.auto_bounty_check, AUTO_BOUNTY_CHECK_INTERVAL)
        self.auto_bounty_settings = {}  # guild_id -> settings
        self.load_auto_bounty_settings.start()
    
    def cog_unload(self):
        """Called when the cog is unloaded"""
        self.auto_bounty_task.cancel()
        self.load_auto_bounty_settings.cancel()
    
    @tasks.loop(minutes=30)
    async def load_auto_bounty_settings(self):
        """Load auto-bounty settings from the database"""
        try:
            db = self.bot.db
            cursor = db.guilds.find({})
            
            async for guild_data in cursor:
                guild_id = str(guild_data.get("guild_id"))
                auto_bounty = guild_data.get("auto_bounty", {
                    "enabled": True,
                    "min_reward": DEFAULT_AUTO_BOUNTY_AMOUNT_MIN,
                    "max_reward": DEFAULT_AUTO_BOUNTY_AMOUNT_MAX,
                    "kill_threshold": AUTO_BOUNTY_KILLSTREAK_THRESHOLD,
                    "repeat_threshold": AUTO_BOUNTY_REPEAT_THRESHOLD,
                    "time_window": AUTO_BOUNTY_TIME_WINDOW_MINUTES
                })
                
                self.auto_bounty_settings[guild_id] = auto_bounty
        except Exception as e:
            logger.error(f"Error loading auto-bounty settings: {e}", exc_info=True)
    
    @load_auto_bounty_settings.before_loop
    async def before_load_settings(self):
        """Wait for bot to be ready before loading settings"""
        await self.bot.wait_until_ready()
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Called when the bot is ready"""
        logger.info("Starting auto-bounty task")
        await self.auto_bounty_task.start()
        
        # Also expire old bounties
        try:
            expired_count = await Bounty.expire_old_bounties()
            logger.info(f"Expired {expired_count} old bounties")
        except Exception as e:
            logger.error(f"Error expiring old bounties: {e}", exc_info=True)
    
    async def auto_bounty_check(self):
        """Check for auto-bounty conditions and create bounties as needed"""
        try:
            db = self.bot.db
            
            # Get all premium guilds
            guilds_cursor = db.guilds.find({"premium_tier": {"$gt": 0}})
            
            async for guild_data in guilds_cursor:
                guild_id = str(guild_data.get("guild_id"))
                guild = Guild(db, guild_data)
                
                # Check if bounty feature is enabled for this guild
                if not guild.check_feature_access("bounty"):
                    continue
                
                # Check if auto-bounty is enabled for this guild
                settings = self.auto_bounty_settings.get(guild_id, {})
                if not settings.get("enabled", True):
                    continue
                
                # Get settings
                min_reward = settings.get("min_reward", DEFAULT_AUTO_BOUNTY_AMOUNT_MIN)
                max_reward = settings.get("max_reward", DEFAULT_AUTO_BOUNTY_AMOUNT_MAX)
                kill_threshold = settings.get("kill_threshold", AUTO_BOUNTY_KILLSTREAK_THRESHOLD)
                repeat_threshold = settings.get("repeat_threshold", AUTO_BOUNTY_REPEAT_THRESHOLD)
                time_window = settings.get("time_window", AUTO_BOUNTY_TIME_WINDOW_MINUTES)
                
                # Check each server in the guild
                for server in guild.servers:
                    server_id = server.get("server_id")
                    
                    # Get player stats for potential bounties
                    potential_bounties = await Bounty.get_player_stats_for_bounty(
                        guild_id, server_id, time_window, kill_threshold, repeat_threshold)
                    
                    for target in potential_bounties:
                        # Check if player already has an active bounty
                        existing_bounty = await Bounty.get_active_bounty_for_target(
                            guild_id, server_id, target["player_id"])
                        
                        if existing_bounty:
                            continue
                        
                        # Determine reward amount
                        if target["type"] == "killstreak":
                            # Higher reward for killstreaks
                            reward = random.randint(
                                min(min_reward * 2, max_reward), 
                                max_reward
                            )
                        else:
                            reward = random.randint(min_reward, max_reward)
                        
                        # Create bounty
                        await Bounty.create(
                            guild_id=guild_id,
                            server_id=server_id,
                            target_id=target["player_id"],
                            target_name=target["player_name"],
                            placed_by=Bounty.SOURCE_AI,
                            placed_by_name="AI Bounty System",
                            reason=target["reason"],
                            reward=reward,
                            source=Bounty.SOURCE_AI
                        )
                        
                        logger.info(
                            f"Created auto-bounty on {target['player_name']} in guild {guild_id}, "
                            f"server {server_id} for {reward} currency"
                        )
                        
                        # Notify guild with announcement if a channel is configured
                        try:
                            channel_id = server.get("bounty_channel")
                            if channel_id:
                                channel = self.bot.get_channel(int(channel_id))
                                if channel:
                                    embed = await EmbedBuilder.info_embed(
                                        title="New Bounty Posted",
                                        description=f"**{target['player_name']}** has a bounty on their head!",
                                        guild=channel.guild,
                                        bot=self.bot
                                    )
                                    
                                    embed.add_field(
                                        name="Reason",
                                        value=target["reason"],
                                        inline=False
                                    )
                                    
                                    embed.add_field(
                                        name="Reward",
                                        value=f"{reward} currency",
                                        inline=True
                                    )
                                    
                                    embed.add_field(
                                        name="Posted By",
                                        value="AI Bounty System",
                                        inline=True
                                    )
                                    
                                    embed.add_field(
                                        name="Expires",
                                        value=f"<t:{int((datetime.utcnow() + timedelta(hours=1)).timestamp())}:R>",
                                        inline=True
                                    )
                                    
                                    await channel.send(embed=embed)
                        except Exception as e:
                            logger.error(f"Error sending bounty notification: {e}", exc_info=True)
        
        except Exception as e:
            logger.error(f"Error in auto-bounty check: {e}", exc_info=True)
    
    @app_commands.command(name="bounty")
    @app_commands.describe(
        action="Action to perform (place, collect, view)",
        target="Target player name (for place action)",
        amount="Amount to place as bounty (for place action)",
        reason="Reason for placing the bounty (for place action)"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="place", value="place"),
        app_commands.Choice(name="view", value="view")
    ])
    async def bounty_command(
        self,
        interaction: discord.Interaction,
        action: str,
        target: Optional[str] = None,
        amount: Optional[int] = None,
        reason: Optional[str] = None
    ) -> None:
        """Manage bounties on players
        
        Args:
            interaction: Discord interaction
            action: Action to perform (place, view)
            target: Target player name (for place action)
            amount: Amount to place as bounty (for place action)
            reason: Reason for placing the bounty (for place action)
        """
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Get guild data
            guild_data = await self.bot.db.guilds.find_one({"guild_id": interaction.guild_id})
            if not guild_data:
                embed = await EmbedBuilder.error_embed(
                    title="Guild Not Found",
                    description="This guild is not registered with the bot.",
                    guild=interaction.guild,
                    bot=self.bot
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # Check if the guild has access to bounty feature
            guild = Guild(self.bot.db, guild_data)
            if not guild.check_feature_access("bounty"):
                embed = await EmbedBuilder.error_embed(
                    title="Premium Feature",
                    description="Bounty system is a premium feature. Please upgrade to access this feature.",
                    guild=interaction.guild,
                    bot=self.bot
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # Get active server
            server = None
            server_id = None
            for s in guild_data.get("servers", []):
                if s.get("active", False):
                    server = s
                    server_id = s.get("server_id")
                    break
            
            if not server or not server_id:
                if guild_data.get("servers"):
                    # Use the first server if no active server
                    server = guild_data.get("servers")[0]
                    server_id = server.get("server_id")
                else:
                    embed = await EmbedBuilder.error_embed(
                        title="No Server Configured",
                        description="No game server has been configured for this guild.",
                        guild=interaction.guild,
                        bot=self.bot
                    )
                    await interaction.followup.send(embed=embed, ephemeral=True)
                    return
            
            # Handle actions
            if action == "place":
                await self.place_bounty(interaction, guild, server_id, target, amount, reason)
            elif action == "view":
                await self.view_bounties(interaction, guild, server_id)
            else:
                embed = await EmbedBuilder.error_embed(
                    title="Invalid Action",
                    description="Valid actions are: place, view",
                    guild=interaction.guild,
                    bot=self.bot
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
        
        except Exception as e:
            logger.error(f"Error in bounty command: {e}", exc_info=True)
            embed = await EmbedBuilder.error_embed(
                title="Error",
                description=f"An error occurred while processing the command: {e}",
                guild=interaction.guild,
                bot=self.bot
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    async def place_bounty(
        self,
        interaction: discord.Interaction,
        guild: Guild,
        server_id: str,
        target_name: Optional[str],
        amount: Optional[int],
        reason: Optional[str]
    ) -> None:
        """Place a bounty on a player
        
        Args:
            interaction: Discord interaction
            guild: Guild model
            server_id: Server ID
            target_name: Target player name
            amount: Amount to place as bounty
            reason: Reason for placing the bounty
        """
        # Validate inputs
        if not target_name:
            embed = await EmbedBuilder.error_embed(
                title="Missing Target",
                description="You must specify a target player name.",
                guild=interaction.guild,
                bot=self.bot
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        if not amount:
            embed = await EmbedBuilder.error_embed(
                title="Missing Amount",
                description="You must specify an amount to place as bounty.",
                guild=interaction.guild,
                bot=self.bot
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        if amount < MIN_BOUNTY_AMOUNT:
            embed = await EmbedBuilder.error_embed(
                title="Invalid Amount",
                description=f"Minimum bounty amount is {MIN_BOUNTY_AMOUNT} currency.",
                guild=interaction.guild,
                bot=self.bot
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        if amount > MAX_BOUNTY_AMOUNT:
            embed = await EmbedBuilder.error_embed(
                title="Invalid Amount",
                description=f"Maximum bounty amount is {MAX_BOUNTY_AMOUNT} currency.",
                guild=interaction.guild,
                bot=self.bot
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Get target player
        target_player = await Player.get_by_player_name(server_id, target_name)
        if not target_player:
            embed = await EmbedBuilder.error_embed(
                title="Player Not Found",
                description=f"Player '{target_name}' not found on this server.",
                guild=interaction.guild,
                bot=self.bot
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Cannot place bounty on yourself
        discord_id = str(interaction.user.id)
        player_link = await PlayerLink.get_by_discord_id(server_id, discord_id)
        if player_link and player_link.player_id == target_player.player_id:
            embed = await EmbedBuilder.error_embed(
                title="Invalid Target",
                description="You cannot place a bounty on yourself.",
                guild=interaction.guild,
                bot=self.bot
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Check if user has enough currency
        user_economy = await Economy.get_by_player(self.bot.db, discord_id, server_id)
        if not user_economy:
            # Create new economy account
            user_economy = await Economy.create_or_update(self.bot.db, discord_id, server_id)
        
        if user_economy.currency < amount:
            embed = await EmbedBuilder.error_embed(
                title="Insufficient Currency",
                description=f"You don't have enough currency to place this bounty. Your balance: {user_economy.currency}",
                guild=interaction.guild,
                bot=self.bot
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Use default reason if none provided
        if not reason:
            reason = "Wanted dead."
        
        # Confirm the bounty placement
        confirm_embed = await EmbedBuilder.warning_embed(
            title="Confirm Bounty",
            description=f"Are you sure you want to place a bounty of **{amount}** currency on **{target_name}**?",
            guild=interaction.guild,
            bot=self.bot
        )
        
        confirmed = await confirm(interaction, confirm_embed)
        if not confirmed:
            embed = await EmbedBuilder.info_embed(
                title="Bounty Cancelled",
                description="Bounty placement cancelled.",
                guild=interaction.guild,
                bot=self.bot
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Deduct currency from user
        if not await user_economy.remove_currency(amount, "bounty_placement", {
            "target_id": target_player.player_id,
            "target_name": target_player.player_name
        }):
            embed = await EmbedBuilder.error_embed(
                title="Transaction Failed",
                description="Failed to deduct currency from your account.",
                guild=interaction.guild,
                bot=self.bot
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Create bounty
        await Bounty.create(
            guild_id=str(interaction.guild_id),
            server_id=server_id,
            target_id=target_player.player_id,
            target_name=target_player.player_name,
            placed_by=discord_id,
            placed_by_name=interaction.user.display_name,
            reason=reason,
            reward=amount,
            source=Bounty.SOURCE_PLAYER
        )
        
        # Send confirmation
        embed = await EmbedBuilder.success_embed(
            title="Bounty Placed",
            description=f"You have placed a bounty of **{amount}** currency on **{target_player.player_name}**.",
            guild=interaction.guild,
            bot=self.bot
        )
        
        embed.add_field(
            name="Reason",
            value=reason,
            inline=False
        )
        
        embed.add_field(
            name="Expires",
            value=f"<t:{int((datetime.utcnow() + timedelta(hours=1)).timestamp())}:R>",
            inline=True
        )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        
        # Notify guild in bounty channel if configured
        try:
            channel_id = guild.data.get("bounty_channel")
            if channel_id:
                channel = interaction.guild.get_channel(int(channel_id))
                if channel:
                    public_embed = await EmbedBuilder.info_embed(
                        title="New Bounty Posted",
                        description=f"**{target_player.player_name}** has a bounty on their head!",
                        guild=interaction.guild,
                        bot=self.bot
                    )
                    
                    public_embed.add_field(
                        name="Reason",
                        value=reason,
                        inline=False
                    )
                    
                    public_embed.add_field(
                        name="Reward",
                        value=f"{amount} currency",
                        inline=True
                    )
                    
                    public_embed.add_field(
                        name="Posted By",
                        value=interaction.user.display_name,
                        inline=True
                    )
                    
                    public_embed.add_field(
                        name="Expires",
                        value=f"<t:{int((datetime.utcnow() + timedelta(hours=1)).timestamp())}:R>",
                        inline=True
                    )
                    
                    await channel.send(embed=public_embed)
        except Exception as e:
            logger.error(f"Error sending bounty notification: {e}", exc_info=True)
    
    async def view_bounties(
        self,
        interaction: discord.Interaction,
        guild: Guild,
        server_id: str
    ) -> None:
        """View active bounties
        
        Args:
            interaction: Discord interaction
            guild: Guild model
            server_id: Server ID
        """
        # Get active bounties
        bounties = await Bounty.get_active_bounties(str(interaction.guild_id), server_id)
        
        if not bounties:
            embed = await EmbedBuilder.info_embed(
                title="No Active Bounties",
                description="There are no active bounties at this time.",
                guild=interaction.guild,
                bot=self.bot
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Create embed with bounty list
        embed = await EmbedBuilder.info_embed(
            title="Active Bounties",
            description=f"There are {len(bounties)} active bounties.",
            guild=interaction.guild,
            bot=self.bot
        )
        
        for bounty in bounties:
            # Calculate remaining time
            now = datetime.utcnow()
            if isinstance(bounty.expires_at, str):
                expires_at = datetime.fromisoformat(bounty.expires_at.replace('Z', '+00:00'))
            else:
                expires_at = bounty.expires_at
                
            remaining = expires_at - now
            hours, remainder = divmod(remaining.seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            time_str = f"{hours}h {minutes}m"
            
            # Add field for this bounty
            embed.add_field(
                name=f"{bounty.target_name} - {bounty.reward} currency",
                value=f"**Reason:** {bounty.reason}\n"
                      f"**Posted by:** {bounty.placed_by_name}\n"
                      f"**Expires:** {time_str} (<t:{int(expires_at.timestamp())}:R>)",
                inline=False
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="bounties")
    @app_commands.describe(
        category="Category of bounties to view"
    )
    @app_commands.choices(category=[
        app_commands.Choice(name="active", value="active"),
        app_commands.Choice(name="my", value="my"),
        app_commands.Choice(name="claimed", value="claimed")
    ])
    async def bounties_command(
        self,
        interaction: discord.Interaction,
        category: str
    ) -> None:
        """View different categories of bounties
        
        Args:
            interaction: Discord interaction
            category: Category of bounties to view (active, my, claimed)
        """
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Get guild data
            guild_data = await self.bot.db.guilds.find_one({"guild_id": interaction.guild_id})
            if not guild_data:
                embed = await EmbedBuilder.error_embed(
                    title="Guild Not Found",
                    description="This guild is not registered with the bot.",
                    guild=interaction.guild,
                    bot=self.bot
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # Check if the guild has access to bounty feature
            guild = Guild(self.bot.db, guild_data)
            if not guild.check_feature_access("bounty"):
                embed = await EmbedBuilder.error_embed(
                    title="Premium Feature",
                    description="Bounty system is a premium feature. Please upgrade to access this feature.",
                    guild=interaction.guild,
                    bot=self.bot
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # Get active server
            server = None
            server_id = None
            for s in guild_data.get("servers", []):
                if s.get("active", False):
                    server = s
                    server_id = s.get("server_id")
                    break
            
            if not server or not server_id:
                if guild_data.get("servers"):
                    # Use the first server if no active server
                    server = guild_data.get("servers")[0]
                    server_id = server.get("server_id")
                else:
                    embed = await EmbedBuilder.error_embed(
                        title="No Server Configured",
                        description="No game server has been configured for this guild.",
                        guild=interaction.guild,
                        bot=self.bot
                    )
                    await interaction.followup.send(embed=embed, ephemeral=True)
                    return
            
            # Handle categories
            if category == "active":
                await self.view_bounties(interaction, guild, server_id)
            elif category == "my":
                await self.view_my_bounties(interaction, guild, server_id)
            elif category == "claimed":
                await self.view_claimed_bounties(interaction, guild, server_id)
            else:
                embed = await EmbedBuilder.error_embed(
                    title="Invalid Category",
                    description="Valid categories are: active, my, claimed",
                    guild=interaction.guild,
                    bot=self.bot
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
        
        except Exception as e:
            logger.error(f"Error in bounties command: {e}", exc_info=True)
            embed = await EmbedBuilder.error_embed(
                title="Error",
                description=f"An error occurred while processing the command: {e}",
                guild=interaction.guild,
                bot=self.bot
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    async def view_my_bounties(
        self,
        interaction: discord.Interaction,
        guild: Guild,
        server_id: str
    ) -> None:
        """View bounties placed by the user
        
        Args:
            interaction: Discord interaction
            guild: Guild model
            server_id: Server ID
        """
        discord_id = str(interaction.user.id)
        
        # Get bounties placed by user
        placed_bounties = await Bounty.get_bounties_by_placed_by(str(interaction.guild_id), server_id, discord_id)
        
        if not placed_bounties:
            embed = await EmbedBuilder.info_embed(
                title="No Bounties Placed",
                description="You haven't placed any bounties yet.",
                guild=interaction.guild,
                bot=self.bot
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Create embed with bounty list
        embed = await EmbedBuilder.info_embed(
            title="Your Placed Bounties",
            description=f"You have placed {len(placed_bounties)} bounties.",
            guild=interaction.guild,
            bot=self.bot
        )
        
        for bounty in placed_bounties[:10]:  # Limit to 10 for display
            # Determine status
            status_str = ""
            if bounty.status == Bounty.STATUS_ACTIVE:
                if isinstance(bounty.expires_at, str):
                    expires_at = datetime.fromisoformat(bounty.expires_at.replace('Z', '+00:00'))
                else:
                    expires_at = bounty.expires_at
                status_str = f"**Status:** Active - Expires <t:{int(expires_at.timestamp())}:R>"
            elif bounty.status == Bounty.STATUS_CLAIMED:
                status_str = f"**Status:** Claimed by {bounty.claimed_by_name}"
            else:
                status_str = "**Status:** Expired"
            
            # Add field for this bounty
            embed.add_field(
                name=f"{bounty.target_name} - {bounty.reward} currency",
                value=f"**Reason:** {bounty.reason}\n"
                      f"**Placed on:** <t:{int(datetime.fromisoformat(str(bounty.placed_at).replace('Z', '+00:00')).timestamp())}:f>\n"
                      f"{status_str}",
                inline=False
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    async def view_claimed_bounties(
        self,
        interaction: discord.Interaction,
        guild: Guild,
        server_id: str
    ) -> None:
        """View bounties claimed by the user
        
        Args:
            interaction: Discord interaction
            guild: Guild model
            server_id: Server ID
        """
        discord_id = str(interaction.user.id)
        
        # Check if user has linked players
        player_links = await PlayerLink.get_by_discord_id(server_id, discord_id)
        if not player_links:
            embed = await EmbedBuilder.warning_embed(
                title="No Linked Players",
                description="You don't have any linked players. Please link your in-game player first with `/link`.",
                guild=interaction.guild,
                bot=self.bot
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Get bounties claimed by user
        claimed_bounties = await Bounty.get_bounties_by_claimed_by(str(interaction.guild_id), server_id, discord_id)
        
        if not claimed_bounties:
            embed = await EmbedBuilder.info_embed(
                title="No Bounties Claimed",
                description="You haven't claimed any bounties yet.",
                guild=interaction.guild,
                bot=self.bot
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Create embed with bounty list
        embed = await EmbedBuilder.info_embed(
            title="Your Claimed Bounties",
            description=f"You have claimed {len(claimed_bounties)} bounties.",
            guild=interaction.guild,
            bot=self.bot
        )
        
        for bounty in claimed_bounties[:10]:  # Limit to 10 for display
            # Format claimed date
            claimed_at = bounty.claimed_at
            if isinstance(claimed_at, str):
                claimed_at = datetime.fromisoformat(claimed_at.replace('Z', '+00:00'))
            
            # Add field for this bounty
            embed.add_field(
                name=f"{bounty.target_name} - {bounty.reward} currency",
                value=f"**Reason:** {bounty.reason}\n"
                      f"**Placed by:** {bounty.placed_by_name}\n"
                      f"**Claimed on:** <t:{int(claimed_at.timestamp())}:f>",
                inline=False
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="bounty_settings")
    @app_commands.describe(
        setting="Setting to change",
        value="New value for the setting"
    )
    @app_commands.choices(setting=[
        app_commands.Choice(name="auto_bounty_enabled", value="auto_bounty_enabled"),
        app_commands.Choice(name="auto_bounty_min_reward", value="auto_bounty_min_reward"),
        app_commands.Choice(name="auto_bounty_max_reward", value="auto_bounty_max_reward"),
        app_commands.Choice(name="auto_bounty_kill_threshold", value="auto_bounty_kill_threshold"),
        app_commands.Choice(name="auto_bounty_repeat_threshold", value="auto_bounty_repeat_threshold"),
        app_commands.Choice(name="auto_bounty_time_window", value="auto_bounty_time_window"),
        app_commands.Choice(name="bounty_channel", value="bounty_channel")
    ])
    async def bounty_settings_command(
        self,
        interaction: discord.Interaction,
        setting: str,
        value: Optional[str] = None
    ) -> None:
        """Configure bounty system settings (admin only)
        
        Args:
            interaction: Discord interaction
            setting: Setting to change
            value: New value for the setting
        """
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Check admin permission
            if not await has_admin_permission(self.bot, interaction.guild, interaction.user):
                embed = await EmbedBuilder.error_embed(
                    title="Permission Denied",
                    description="You need admin permission to change bounty settings.",
                    guild=interaction.guild,
                    bot=self.bot
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # Get guild data
            guild_data = await self.bot.db.guilds.find_one({"guild_id": interaction.guild_id})
            if not guild_data:
                embed = await EmbedBuilder.error_embed(
                    title="Guild Not Found",
                    description="This guild is not registered with the bot.",
                    guild=interaction.guild,
                    bot=self.bot
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # Check if the guild has access to bounty feature
            guild = Guild(self.bot.db, guild_data)
            if not guild.check_feature_access("bounty"):
                embed = await EmbedBuilder.error_embed(
                    title="Premium Feature",
                    description="Bounty system is a premium feature. Please upgrade to access this feature.",
                    guild=interaction.guild,
                    bot=self.bot
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # Handle settings
            if setting == "bounty_channel":
                await self.set_bounty_channel(interaction, guild, value)
            else:
                await self.set_auto_bounty_setting(interaction, guild, setting, value)
        
        except Exception as e:
            logger.error(f"Error in bounty settings command: {e}", exc_info=True)
            embed = await EmbedBuilder.error_embed(
                title="Error",
                description=f"An error occurred while processing the command: {e}",
                guild=interaction.guild,
                bot=self.bot
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    async def set_bounty_channel(
        self,
        interaction: discord.Interaction,
        guild: Guild,
        channel_id: Optional[str]
    ) -> None:
        """Set the channel for bounty notifications
        
        Args:
            interaction: Discord interaction
            guild: Guild model
            channel_id: Channel ID or channel mention
        """
        if not channel_id:
            # Display current setting
            current_channel_id = guild.data.get("bounty_channel")
            if current_channel_id:
                channel = interaction.guild.get_channel(int(current_channel_id))
                channel_name = f"<#{current_channel_id}>" if channel else f"Unknown ({current_channel_id})"
            else:
                channel_name = "Not set"
            
            embed = await EmbedBuilder.info_embed(
                title="Bounty Channel Setting",
                description=f"Current bounty notification channel: {channel_name}",
                guild=interaction.guild,
                bot=self.bot
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Extract channel ID from mention if needed
        if channel_id.startswith("<#") and channel_id.endswith(">"):
            channel_id = channel_id[2:-1]
        
        # Validate channel
        try:
            channel = interaction.guild.get_channel(int(channel_id))
            if not channel:
                embed = await EmbedBuilder.error_embed(
                    title="Invalid Channel",
                    description="The specified channel was not found in this guild.",
                    guild=interaction.guild,
                    bot=self.bot
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # Check permissions
            bot_member = interaction.guild.get_member(self.bot.user.id)
            if not channel.permissions_for(bot_member).send_messages:
                embed = await EmbedBuilder.error_embed(
                    title="Permission Error",
                    description=f"The bot doesn't have permission to send messages in {channel.mention}.",
                    guild=interaction.guild,
                    bot=self.bot
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # Update setting
            result = await self.bot.db.guilds.update_one(
                {"guild_id": interaction.guild_id},
                {"$set": {"bounty_channel": channel_id}}
            )
            
            if result.modified_count > 0:
                embed = await EmbedBuilder.success_embed(
                    title="Setting Updated",
                    description=f"Bounty notifications will now be sent to {channel.mention}.",
                    guild=interaction.guild,
                    bot=self.bot
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                
                # Send test message
                test_embed = await EmbedBuilder.info_embed(
                    title="Bounty System Configured",
                    description=f"This channel will now receive bounty notifications.",
                    guild=interaction.guild,
                    bot=self.bot
                )
                await channel.send(embed=test_embed)
            else:
                embed = await EmbedBuilder.warning_embed(
                    title="No Change",
                    description="The setting was not updated.",
                    guild=interaction.guild,
                    bot=self.bot
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
        
        except ValueError:
            embed = await EmbedBuilder.error_embed(
                title="Invalid Channel ID",
                description="Please provide a valid channel ID or mention.",
                guild=interaction.guild,
                bot=self.bot
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    async def set_auto_bounty_setting(
        self,
        interaction: discord.Interaction,
        guild: Guild,
        setting: str,
        value: Optional[str]
    ) -> None:
        """Set an auto-bounty setting
        
        Args:
            interaction: Discord interaction
            guild: Guild model
            setting: Setting to change
            value: New value for the setting
        """
        guild_id = str(interaction.guild_id)
        
        # Initialize settings if needed
        if guild_id not in self.auto_bounty_settings:
            self.auto_bounty_settings[guild_id] = {
                "enabled": True,
                "min_reward": DEFAULT_AUTO_BOUNTY_AMOUNT_MIN,
                "max_reward": DEFAULT_AUTO_BOUNTY_AMOUNT_MAX,
                "kill_threshold": AUTO_BOUNTY_KILLSTREAK_THRESHOLD,
                "repeat_threshold": AUTO_BOUNTY_REPEAT_THRESHOLD,
                "time_window": AUTO_BOUNTY_TIME_WINDOW_MINUTES
            }
        
        # Map command setting names to internal setting names
        setting_map = {
            "auto_bounty_enabled": "enabled",
            "auto_bounty_min_reward": "min_reward",
            "auto_bounty_max_reward": "max_reward",
            "auto_bounty_kill_threshold": "kill_threshold",
            "auto_bounty_repeat_threshold": "repeat_threshold",
            "auto_bounty_time_window": "time_window"
        }
        
        internal_setting = setting_map.get(setting)
        if not internal_setting:
            embed = await EmbedBuilder.error_embed(
                title="Invalid Setting",
                description=f"Unknown setting: {setting}",
                guild=interaction.guild,
                bot=self.bot
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # If no value provided, just show the current setting
        if not value:
            current_value = self.auto_bounty_settings[guild_id].get(internal_setting, "Not set")
            
            # Format boolean values
            if internal_setting == "enabled":
                current_value = "Enabled" if current_value else "Disabled"
            
            embed = await EmbedBuilder.info_embed(
                title=f"Auto-Bounty Setting: {setting}",
                description=f"Current value: **{current_value}**",
                guild=interaction.guild,
                bot=self.bot
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Update the setting based on type
        try:
            if internal_setting == "enabled":
                # Boolean setting
                if value.lower() in ["true", "yes", "on", "enable", "enabled", "1"]:
                    new_value = True
                elif value.lower() in ["false", "no", "off", "disable", "disabled", "0"]:
                    new_value = False
                else:
                    embed = await EmbedBuilder.error_embed(
                        title="Invalid Value",
                        description="Please use 'true' or 'false' for this setting.",
                        guild=interaction.guild,
                        bot=self.bot
                    )
                    await interaction.followup.send(embed=embed, ephemeral=True)
                    return
            else:
                # Numeric settings
                new_value = int(value)
                
                # Validate ranges
                if internal_setting == "min_reward" and (new_value < 10 or new_value > 1000):
                    embed = await EmbedBuilder.error_embed(
                        title="Invalid Value",
                        description="Minimum reward must be between 10 and 1000.",
                        guild=interaction.guild,
                        bot=self.bot
                    )
                    await interaction.followup.send(embed=embed, ephemeral=True)
                    return
                
                if internal_setting == "max_reward" and (new_value < 100 or new_value > 10000):
                    embed = await EmbedBuilder.error_embed(
                        title="Invalid Value",
                        description="Maximum reward must be between 100 and 10000.",
                        guild=interaction.guild,
                        bot=self.bot
                    )
                    await interaction.followup.send(embed=embed, ephemeral=True)
                    return
                
                if (internal_setting == "kill_threshold" or internal_setting == "repeat_threshold") and (new_value < 1 or new_value > 20):
                    embed = await EmbedBuilder.error_embed(
                        title="Invalid Value",
                        description="Threshold values must be between 1 and 20.",
                        guild=interaction.guild,
                        bot=self.bot
                    )
                    await interaction.followup.send(embed=embed, ephemeral=True)
                    return
                
                if internal_setting == "time_window" and (new_value < 1 or new_value > 60):
                    embed = await EmbedBuilder.error_embed(
                        title="Invalid Value",
                        description="Time window must be between 1 and 60 minutes.",
                        guild=interaction.guild,
                        bot=self.bot
                    )
                    await interaction.followup.send(embed=embed, ephemeral=True)
                    return
            
            # Check min/max reward relationship
            if internal_setting == "min_reward" and new_value > self.auto_bounty_settings[guild_id].get("max_reward", DEFAULT_AUTO_BOUNTY_AMOUNT_MAX):
                embed = await EmbedBuilder.error_embed(
                    title="Invalid Value",
                    description="Minimum reward cannot be greater than maximum reward.",
                    guild=interaction.guild,
                    bot=self.bot
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            if internal_setting == "max_reward" and new_value < self.auto_bounty_settings[guild_id].get("min_reward", DEFAULT_AUTO_BOUNTY_AMOUNT_MIN):
                embed = await EmbedBuilder.error_embed(
                    title="Invalid Value",
                    description="Maximum reward cannot be less than minimum reward.",
                    guild=interaction.guild,
                    bot=self.bot
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # Update setting in memory
            self.auto_bounty_settings[guild_id][internal_setting] = new_value
            
            # Update setting in database
            auto_bounty_field = f"auto_bounty.{internal_setting}"
            result = await self.bot.db.guilds.update_one(
                {"guild_id": interaction.guild_id},
                {"$set": {auto_bounty_field: new_value}}
            )
            
            # Ensure auto_bounty field exists
            if result.matched_count == 0:
                await self.bot.db.guilds.update_one(
                    {"guild_id": interaction.guild_id},
                    {"$set": {"auto_bounty": self.auto_bounty_settings[guild_id]}}
                )
            
            # Format display value
            display_value = "Enabled" if new_value is True else "Disabled" if new_value is False else str(new_value)
            
            embed = await EmbedBuilder.success_embed(
                title="Setting Updated",
                description=f"Auto-bounty setting `{setting}` has been updated to: **{display_value}**",
                guild=interaction.guild,
                bot=self.bot
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        
        except ValueError:
            embed = await EmbedBuilder.error_embed(
                title="Invalid Value",
                description="Please provide a valid numeric value for this setting.",
                guild=interaction.guild,
                bot=self.bot
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    @commands.Cog.listener()
    async def on_csv_kill_parsed(self, kill_data: Dict[str, Any]):
        """Handle newly parsed kill events from CSV files for bounty claims
        
        This event is emitted by the CSV parser when a new kill is parsed.
        
        Args:
            kill_data: Kill data dictionary
        """
        try:
            # Extract relevant data
            guild_id = kill_data.get("guild_id")
            server_id = kill_data.get("server_id")
            killer_id = kill_data.get("killer_id")
            killer_name = kill_data.get("killer_name")
            victim_id = kill_data.get("victim_id")
            victim_name = kill_data.get("victim_name")
            timestamp = kill_data.get("timestamp")
            
            # Skip if any required data is missing
            if not all([guild_id, server_id, killer_id, victim_id]):
                return
            
            # Skip self-kills
            if killer_id == victim_id:
                return
            
            # Check if victim has an active bounty
            bounty = await Bounty.get_active_bounty_for_target(str(guild_id), server_id, victim_id)
            if not bounty:
                return
            
            # Get killer's linked Discord account
            killer_link = await PlayerLink.get_by_player_id(server_id, killer_id)
            if not killer_link:
                logger.debug(f"Killer {killer_name} not linked to any Discord account, cannot claim bounty")
                return
            
            # Claim bounty
            discord_id = killer_link.discord_id
            claimed = await bounty.claim(discord_id, killer_name)
            
            if claimed:
                logger.info(f"Bounty on {victim_name} claimed by {killer_name} for {bounty.reward} currency")
                
                # Award currency to killer
                killer_economy = await Economy.get_by_player(self.bot.db, discord_id, server_id)
                if not killer_economy:
                    # Create new economy account
                    killer_economy = await Economy.create_or_update(self.bot.db, discord_id, server_id)
                
                await killer_economy.add_currency(bounty.reward, "bounty_claimed", {
                    "bounty_id": str(bounty.id),
                    "target_id": victim_id,
                    "target_name": victim_name
                })
                
                # Notify in bounty channel if configured
                try:
                    guild_data = await self.bot.db.guilds.find_one({"guild_id": guild_id})
                    if guild_data:
                        bounty_channel_id = guild_data.get("bounty_channel")
                        if bounty_channel_id:
                            guild = self.bot.get_guild(int(guild_id))
                            if guild:
                                channel = guild.get_channel(int(bounty_channel_id))
                                if channel:
                                    bot_name = get_bot_name(self.bot, guild)
                                    
                                    # Create claim notification
                                    embed = discord.Embed(
                                        title="Bounty Claimed!",
                                        description=f"**{killer_name}** has claimed the bounty on **{victim_name}**!",
                                        color=0xFFD700,  # Gold color
                                        timestamp=datetime.utcnow()
                                    )
                                    
                                    embed.add_field(
                                        name="Reward",
                                        value=f"{bounty.reward} currency",
                                        inline=True
                                    )
                                    
                                    embed.add_field(
                                        name="Originally Posted By",
                                        value=bounty.placed_by_name,
                                        inline=True
                                    )
                                    
                                    embed.add_field(
                                        name="Reason",
                                        value=bounty.reason,
                                        inline=False
                                    )
                                    
                                    embed.set_footer(text=f"Powered By {bot_name}")
                                    
                                    # Add trophy icon
                                    embed.set_thumbnail(url="https://i.imgur.com/6BU5RCu.png")
                                    
                                    await channel.send(embed=embed)
                except Exception as e:
                    logger.error(f"Error sending bounty claim notification: {e}", exc_info=True)
        
        except Exception as e:
            logger.error(f"Error processing kill for bounty claim: {e}", exc_info=True)


async def setup(bot: commands.Bot):
    """Set up the Bounties cog"""
    await bot.add_cog(BountiesCog(bot))