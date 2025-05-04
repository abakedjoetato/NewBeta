"""
Helper Functions for the Tower of Temptation PvP Statistics Discord Bot.

This module provides:
1. General utility functions for the bot
2. Discord-specific utilities
3. Text formatting helpers
4. Common conversion functions
5. Bot naming and reference helpers
"""
import re
import logging
import random
import string
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Set, Tuple, cast

import discord
from discord.ext import commands

from models.server_config import ServerConfig

logger = logging.getLogger(__name__)

def format_time_ago_str(timestamp_str: Optional[str]) -> str:
    """Format a timestamp string as a human-readable time ago string
    
    Args:
        timestamp_str: ISO format timestamp string
        
    Returns:
        str: Human-readable time ago (e.g. "5 minutes ago", "2 hours ago")
    """
    if not timestamp_str:
        return "unknown"
        
    try:
        # Parse the ISO timestamp
        dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        
        # Use the datetime version of the function
        return format_time_ago(dt)
        
    except (ValueError, TypeError):
        return "unknown"

def generate_random_code(length: int = 6) -> str:
    """Generate random verification code
    
    Args:
        length: Code length (default: 6)
        
    Returns:
        str: Random code
    """
    # Generate random code using uppercase letters and digits
    # Exclude similar looking characters like O, 0, I, 1, etc.
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return ''.join(random.choice(chars) for _ in range(length))

def format_timedelta(delta: timedelta) -> str:
    """Format timedelta as human-readable string
    
    Args:
        delta: Timedelta to format
        
    Returns:
        str: Formatted string
    """
    # Convert to total seconds
    total_seconds = int(delta.total_seconds())
    
    # Calculate components
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    # Build string
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0 or days > 0:
        parts.append(f"{hours}h")
    if minutes > 0 or hours > 0 or days > 0:
        parts.append(f"{minutes}m")
    parts.append(f"{seconds}s")
    
    return " ".join(parts)

def format_time_ago(dt: datetime) -> str:
    """Format datetime as time ago string
    
    Args:
        dt: Datetime to format
        
    Returns:
        str: Formatted string
    """
    # Calculate time difference
    now = datetime.utcnow()
    delta = now - dt
    
    # Format based on range
    if delta.total_seconds() < 60:
        return "just now"
    elif delta.total_seconds() < 3600:
        minutes = int(delta.total_seconds() / 60)
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    elif delta.total_seconds() < 86400:
        hours = int(delta.total_seconds() / 3600)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    elif delta.days < 7:
        return f"{delta.days} day{'s' if delta.days != 1 else ''} ago"
    elif delta.days < 30:
        weeks = int(delta.days / 7)
        return f"{weeks} week{'s' if weeks != 1 else ''} ago"
    elif delta.days < 365:
        months = int(delta.days / 30)
        return f"{months} month{'s' if months != 1 else ''} ago"
    else:
        years = int(delta.days / 365)
        return f"{years} year{'s' if years != 1 else ''} ago"

async def get_prefix(bot: commands.Bot, message: discord.Message) -> Union[List[str], str]:
    """Get command prefix for guild
    
    Args:
        bot: Bot instance
        message: Message
        
    Returns:
        Union[List[str], str]: Command prefix(es)
    """
    # DM channel has no guild
    if message.guild is None:
        return commands.when_mentioned_or("!")(bot, message)
        
    # Get server config
    server_config = await ServerConfig.get_by_guild_id(message.guild.id)
    if server_config and server_config.prefix:
        # Use custom prefix
        return commands.when_mentioned_or(server_config.prefix)(bot, message)
        
    # Default prefix
    return commands.when_mentioned_or("!")(bot, message)

async def check_admin_permissions(ctx: commands.Context) -> bool:
    """Check if user has admin permissions
    
    Args:
        ctx: Command context
        
    Returns:
        bool: True if user has admin permissions
    """
    # Bot owner always has admin permissions
    if await ctx.bot.is_owner(ctx.author):
        return True
        
    # DM channel has no guild
    if ctx.guild is None:
        return False
        
    # Server owner always has admin permissions
    if ctx.guild.owner_id == ctx.author.id:
        return True
        
    # Check for admin role
    server_config = await ServerConfig.get_by_guild_id(ctx.guild.id)
    if server_config and server_config.admin_role_id:
        # Check if user has admin role
        member = ctx.guild.get_member(ctx.author.id)
        if member and any(role.id == server_config.admin_role_id for role in member.roles):
            return True
            
    # Check for administrator permission
    if ctx.author.guild_permissions.administrator:
        return True
        
    return False

def get_bot_name(bot: commands.Bot, guild: Optional[discord.Guild] = None) -> str:
    """Get the bot's name or nickname in a guild
    
    Args:
        bot: The bot instance
        guild: The guild to check nickname in (optional)
        
    Returns:
        str: The bot's nickname in the guild, or its username if no nickname or no guild
    """
    # First check if we have a guild and if the bot has a nickname in it
    if guild is not None:
        # Try to get the bot's member object in the guild
        bot_member = guild.get_member(bot.user.id)
        if bot_member and bot_member.nick:
            return bot_member.nick
    
    # Default to the bot's username
    return bot.user.name

def sanitize_string(text: str) -> str:
    """Sanitize string for database storage
    
    Args:
        text: Text to sanitize
        
    Returns:
        str: Sanitized string
    """
    # Limit length
    if len(text) > 100:
        text = text[:100]
        
    # Remove control characters
    text = ''.join(c for c in text if c.isprintable())
    
    # Trim whitespace
    text = text.strip()
    
    return text

def truncate_string(text: str, max_length: int = 100, ellipsis: bool = True) -> str:
    """Truncate string to maximum length
    
    Args:
        text: Text to truncate
        max_length: Maximum length (default: 100)
        ellipsis: Add ellipsis if truncated (default: True)
        
    Returns:
        str: Truncated string
    """
    if len(text) <= max_length:
        return text
        
    if ellipsis:
        return text[:max_length - 3] + "..."
    else:
        return text[:max_length]

def validate_steam_id(steam_id: str) -> bool:
    """Validate Steam ID format
    
    Args:
        steam_id: Steam ID
        
    Returns:
        bool: True if valid
    """
    # Check format (Steam64 ID)
    return bool(re.match(r'^7656119\d{10}$', steam_id))

def validate_discord_id(discord_id: str) -> bool:
    """Validate Discord ID format
    
    Args:
        discord_id: Discord ID
        
    Returns:
        bool: True if valid
    """
    # Check format
    return bool(re.match(r'^\d{17,20}$', discord_id))

def format_kd_ratio(kills: int, deaths: int) -> float:
    """Calculate and format K/D ratio
    
    Args:
        kills: Kill count
        deaths: Death count
        
    Returns:
        float: K/D ratio
    """
    if deaths == 0:
        return float(kills)
    else:
        return round(kills / deaths, 2)

def get_level_for_kills(kills: int) -> int:
    """Get player level based on kills
    
    Args:
        kills: Kill count
        
    Returns:
        int: Level
    """
    # Level formula
    level = 1
    
    if kills >= 10:
        level = 2
    if kills >= 25:
        level = 3
    if kills >= 50:
        level = 4
    if kills >= 100:
        level = 5
    if kills >= 200:
        level = 6
    if kills >= 350:
        level = 7
    if kills >= 500:
        level = 8
    if kills >= 750:
        level = 9
    if kills >= 1000:
        level = 10
    if kills >= 1500:
        level = 11
    if kills >= 2000:
        level = 12
    if kills >= 3000:
        level = 13
    if kills >= 4000:
        level = 14
    if kills >= 5000:
        level = 15
        
    return level

def format_large_number(num: int) -> str:
    """Format large number with suffix
    
    Args:
        num: Number to format
        
    Returns:
        str: Formatted number
    """
    if num < 1000:
        return str(num)
    elif num < 1000000:
        return f"{num / 1000:.1f}K".replace(".0K", "K")
    else:
        return f"{num / 1000000:.1f}M".replace(".0M", "M")

def friendly_duration(seconds: int) -> str:
    """Format seconds as friendly duration
    
    Args:
        seconds: Seconds
        
    Returns:
        str: Friendly duration
    """
    if seconds < 60:
        return f"{seconds} second{'s' if seconds != 1 else ''}"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"{minutes} minute{'s' if minutes != 1 else ''}"
    elif seconds < 86400:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        if minutes == 0:
            return f"{hours} hour{'s' if hours != 1 else ''}"
        else:
            return f"{hours} hour{'s' if hours != 1 else ''} and {minutes} minute{'s' if minutes != 1 else ''}"
    else:
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        if hours == 0:
            return f"{days} day{'s' if days != 1 else ''}"
        else:
            return f"{days} day{'s' if days != 1 else ''} and {hours} hour{'s' if hours != 1 else ''}"

def dict_to_table(data: List[Dict[str, Any]], columns: List[str], headers: Optional[List[str]] = None) -> str:
    """Convert list of dictionaries to ASCII table
    
    Args:
        data: List of dictionaries
        columns: Columns to include
        headers: Custom headers (default: None)
        
    Returns:
        str: ASCII table
    """
    if not data:
        return "No data available"
        
    # Use column names as headers if not provided
    if headers is None:
        headers = columns
        
    # Calculate column widths
    widths = [len(header) for header in headers]
    for row in data:
        for i, col in enumerate(columns):
            if col in row:
                width = len(str(row[col]))
                widths[i] = max(widths[i], width)
                
    # Build header
    header = " | ".join(f"{headers[i]:{widths[i]}}" for i in range(len(headers)))
    separator = "-+-".join("-" * width for width in widths)
    
    # Build rows
    rows = []
    for row in data:
        formatted_row = " | ".join(
            f"{str(row.get(columns[i], '')):{widths[i]}}" for i in range(len(columns))
        )
        rows.append(formatted_row)
        
    # Combine parts
    return f"{header}\n{separator}\n" + "\n".join(rows)