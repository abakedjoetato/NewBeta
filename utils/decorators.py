"""
Decorators for the Tower of Temptation PvP Statistics Discord Bot.

This module provides decorators for:
1. Permission checking
2. Premium tier requirements
3. Command cooldowns
4. Error handling
"""
import logging
import functools
from typing import Any, Callable, Optional, TypeVar, cast

import discord
from discord import app_commands
from discord.ext import commands

from models.guild import Guild
# from models.user import User (not needed yet)
from utils.embed_builder import EmbedBuilder

logger = logging.getLogger(__name__)

# Type for command callbacks
T = TypeVar('T')

def premium_tier_required(tier: int) -> Callable[[T], T]:
    """Decorator that checks if guild has required premium tier
    
    Args:
        tier: Required premium tier (1, 2, or 3)
        
    Returns:
        Decorator function
    """
    def decorator(func: T) -> T:
        @functools.wraps(func)
        async def wrapper(self: Any, interaction: discord.Interaction, *args: Any, **kwargs: Any) -> Any:
            # Get guild from database
            guild_data = await Guild.get_by_guild_id(str(interaction.guild_id))
            
            # Check premium tier
            if not guild_data or guild_data.premium_tier < tier:
                # Build embed with premium tier info
                embed = EmbedBuilder.error(
                    title="Premium Feature",
                    description=f"This feature requires Premium Tier {tier} or higher.\n\n"
                              f"Current premium tier: {guild_data.premium_tier if guild_data else 0}\n\n"
                              "Use `/premium info` to learn more about premium features."
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
                
            # Call original function
            return await func(self, interaction, *args, **kwargs)
            
        return cast(T, wrapper)
    return decorator

def has_admin_permission() -> Callable[[T], T]:
    """Decorator that checks if user has admin permissions
    
    Returns:
        Decorator function
    """
    def decorator(func: T) -> T:
        @functools.wraps(func)
        async def wrapper(self: Any, interaction: discord.Interaction, *args: Any, **kwargs: Any) -> Any:
            # Bot owner always has admin permissions
            if await self.bot.is_owner(interaction.user):
                return await func(self, interaction, *args, **kwargs)
                
            # Server owner always has admin permissions
            if interaction.guild and interaction.guild.owner_id == interaction.user.id:
                return await func(self, interaction, *args, **kwargs)
                
            # Check for admin role
            guild_data = await Guild.get_by_guild_id(str(interaction.guild_id))
            if guild_data and guild_data.admin_role_id:
                # Check if user has admin role
                member = interaction.guild.get_member(interaction.user.id)
                if member and any(role.id == int(guild_data.admin_role_id) for role in member.roles):
                    return await func(self, interaction, *args, **kwargs)
                    
            # Check for administrator permission
            if interaction.user.guild_permissions.administrator:
                return await func(self, interaction, *args, **kwargs)
                
            # User doesn't have permissions
            embed = EmbedBuilder.error(
                title="Permission Denied",
                description="You need administrator permissions to use this command."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
            
        return cast(T, wrapper)
    return decorator

def has_mod_permission() -> Callable[[T], T]:
    """Decorator that checks if user has moderator permissions
    
    Returns:
        Decorator function
    """
    def decorator(func: T) -> T:
        @functools.wraps(func)
        async def wrapper(self: Any, interaction: discord.Interaction, *args: Any, **kwargs: Any) -> Any:
            # Admins always have mod permissions
            if await self.bot.is_owner(interaction.user):
                return await func(self, interaction, *args, **kwargs)
                
            # Server owner always has mod permissions
            if interaction.guild and interaction.guild.owner_id == interaction.user.id:
                return await func(self, interaction, *args, **kwargs)
                
            # Check for admin or mod roles
            guild_data = await Guild.get_by_guild_id(str(interaction.guild_id))
            if guild_data:
                member = interaction.guild.get_member(interaction.user.id)
                if member:
                    # Check admin role
                    if guild_data.admin_role_id and any(role.id == int(guild_data.admin_role_id) for role in member.roles):
                        return await func(self, interaction, *args, **kwargs)
                        
                    # Check mod role
                    if guild_data.mod_role_id and any(role.id == int(guild_data.mod_role_id) for role in member.roles):
                        return await func(self, interaction, *args, **kwargs)
                        
            # Check for administrator or manage server permissions
            if interaction.user.guild_permissions.administrator or interaction.user.guild_permissions.manage_guild:
                return await func(self, interaction, *args, **kwargs)
                
            # User doesn't have permissions
            embed = EmbedBuilder.error(
                title="Permission Denied",
                description="You need moderator permissions to use this command."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
            
        return cast(T, wrapper)
    return decorator

def command_cooldown(seconds: int, user_based: bool = True) -> Callable[[T], T]:
    """Decorator that adds cooldown to commands
    
    Args:
        seconds: Cooldown in seconds
        user_based: Whether cooldown is per user (True) or per guild (False)
        
    Returns:
        Decorator function
    """
    def decorator(func: T) -> T:
        # Create cooldowns dictionary if it doesn't exist
        if not hasattr(func, "_cooldowns"):
            setattr(func, "_cooldowns", {})
            
        @functools.wraps(func)
        async def wrapper(self: Any, interaction: discord.Interaction, *args: Any, **kwargs: Any) -> Any:
            import time
            
            # Get cooldowns dictionary
            cooldowns = getattr(func, "_cooldowns")
            
            # Get key based on cooldown type
            if user_based:
                key = str(interaction.user.id)
            else:
                key = str(interaction.guild_id)
                
            # Check cooldown
            now = time.time()
            if key in cooldowns:
                time_left = cooldowns[key] + seconds - now
                if time_left > 0:
                    # Cooldown active
                    embed = EmbedBuilder.warning(
                        title="Command Cooldown",
                        description=f"This command is on cooldown. Please try again in {int(time_left)} seconds."
                    )
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return
                    
            # Update cooldown and call function
            cooldowns[key] = now
            return await func(self, interaction, *args, **kwargs)
            
        return cast(T, wrapper)
    return decorator