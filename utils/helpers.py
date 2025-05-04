"""
Helper utilities for the Discord bot
"""
import logging
import os
import asyncio
from typing import Any, Dict, List, Optional, Union, Callable
import discord
from discord.ext import commands, pages

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

def is_feature_enabled(guild_doc: Dict[str, Any], feature_name: str) -> bool:
    """Check if a feature is enabled for a guild
    
    Args:
        guild_doc: Guild document from the database
        feature_name: Name of the feature to check
        
    Returns:
        True if the feature is enabled, False otherwise
    """
    # Premium tier requirements for different features
    feature_requirements = {
        'bounties': 2,
        'rivalries': 1,
        'factions': 2,
        'events': 1,
        'leaderboards': 0,
        'history': 0,
        'stats': 0,
        'kill_feed': 0,
    }
    
    # Get required tier for the feature
    required_tier = feature_requirements.get(feature_name, 3)
    
    # Get guild premium tier (default to 0)
    guild_tier = guild_doc.get('premium_tier', 0)
    
    # Check if the guild meets the required tier
    return guild_tier >= required_tier

async def paginate_embeds(ctx, embeds: List[discord.Embed], timeout: int = 180):
    """Create a paginated view of embeds
    
    Args:
        ctx: Command context
        embeds: List of embeds to paginate
        timeout: Timeout in seconds for the pagination controls
    """
    if not embeds:
        await ctx.send("No data to display.")
        return
        
    if len(embeds) == 1:
        await ctx.send(embed=embeds[0])
        return
        
    paginator = pages.Paginator(pages=embeds, timeout=timeout)
    await paginator.respond(ctx.interaction if hasattr(ctx, 'interaction') else ctx)

def chunk_list(lst: List[Any], chunk_size: int) -> List[List[Any]]:
    """Split a list into chunks of specified size
    
    Args:
        lst: List to split
        chunk_size: Size of each chunk
        
    Returns:
        List of chunks
    """
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]

def normalize_weapon_name(weapon: str) -> str:
    """Normalize weapon name to consistent format
    
    Args:
        weapon: Raw weapon name from logs
        
    Returns:
        Normalized weapon name
    """
    if not weapon:
        return "Unknown"
        
    # Convert to lowercase for comparison
    weapon = weapon.lower().strip()
    
    # Handle common variations
    if 'suicide' in weapon or 'killed_self' in weapon:
        return "Suicide"
    elif 'vehicle' in weapon:
        return "Vehicle"
    elif 'fall' in weapon:
        return "Fall Damage"
    elif 'relocation' in weapon:
        return "Relocation"
    
    # Remove unnecessary prefixes
    prefixes = ['weapon_', 'item_', 'gadget_']
    for prefix in prefixes:
        if weapon.startswith(prefix):
            weapon = weapon[len(prefix):]
    
    # Capitalize for display
    return weapon.title()

async def throttle(coro, max_calls: int, interval: float, key: Optional[Callable] = None):
    """Throttle a coroutine to limit execution rate
    
    Args:
        coro: Coroutine to throttle
        max_calls: Maximum number of calls in the interval
        interval: Interval in seconds
        key: Optional function to generate a key for tracking calls
        
    Returns:
        Result of the coroutine
    """
    # Use default key function if none provided
    if key is None:
        key = lambda: "default"
    
    # Initialize throttling state if not already done
    if not hasattr(throttle, "_state"):
        throttle._state = {}
    
    # Get or create throttling state for this key
    key_value = key()
    if key_value not in throttle._state:
        throttle._state[key_value] = {"calls": 0, "reset_at": asyncio.get_event_loop().time() + interval}
    
    state = throttle._state[key_value]
    
    # Check if we need to reset the counter
    now = asyncio.get_event_loop().time()
    if now >= state["reset_at"]:
        state["calls"] = 0
        state["reset_at"] = now + interval
    
    # Check if we're at the limit
    if state["calls"] >= max_calls:
        wait_time = state["reset_at"] - now
        logger.debug(f"Throttling {coro.__name__}: waiting {wait_time:.2f}s")
        await asyncio.sleep(wait_time)
        # Recursively call ourselves after waiting
        return await throttle(coro, max_calls, interval, key)
    
    # Increment counter and run the coroutine
    state["calls"] += 1
    return await coro