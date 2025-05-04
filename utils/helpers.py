"""
Helper utilities for the Discord bot
"""
import logging
import os
from typing import Any, Optional, Union

logger = logging.getLogger(__name__)

def is_home_guild_admin(bot, user_id: int) -> bool:
    """Check if a user is an admin of the home guild
    
    Args:
        bot: Discord bot instance
        user_id: Discord user ID to check
        
    Returns:
        True if the user is an admin of the home guild, False otherwise
    """
    # Check if bot has home_guild_id attribute
    if not hasattr(bot, 'home_guild_id') or not bot.home_guild_id:
        # Try to get home_guild_id from environment
        home_guild_id = os.environ.get('HOME_GUILD_ID')
        if not home_guild_id:
            # No home guild set
            return False
        try:
            bot.home_guild_id = int(home_guild_id)
        except (ValueError, TypeError):
            # Invalid home_guild_id
            return False
    
    # Get home guild
    home_guild = bot.get_guild(bot.home_guild_id)
    if not home_guild:
        # Bot is not in home guild
        return False
    
    # Get member
    member = home_guild.get_member(user_id)
    if not member:
        # User is not in home guild
        return False
    
    # Check if user is an admin
    return member.guild_permissions.administrator or member.id == bot.owner_id

def format_datetime(dt) -> str:
    """Format a datetime object into a string
    
    Args:
        dt: Datetime object
        
    Returns:
        Formatted datetime string
    """
    if not dt:
        return "Unknown"
        
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")

def format_duration(seconds: int) -> str:
    """Format a duration in seconds into a human-readable string
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        Formatted duration string
    """
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes = seconds // 60
        sec = seconds % 60
        return f"{minutes}m {sec}s"
    elif seconds < 86400:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h {minutes}m"
    else:
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        return f"{days}d {hours}h"

def format_currency(amount: Union[int, float]) -> str:
    """Format a currency amount
    
    Args:
        amount: Currency amount
        
    Returns:
        Formatted currency string
    """
    return f"{amount:,}"

def calculate_kd_ratio(kills: int, deaths: int) -> float:
    """Calculate a K/D ratio
    
    Args:
        kills: Number of kills
        deaths: Number of deaths
        
    Returns:
        K/D ratio (kills / deaths, with deaths=1 if deaths=0)
    """
    if deaths == 0:
        deaths = 1
    return kills / deaths