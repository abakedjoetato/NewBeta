"""
Discord-specific utility functions for the Tower of Temptation PvP Statistics Bot.

This module provides:
1. Server selection utilities
2. Command autocompletion helpers
3. Command response formatters
4. User interaction helpers
"""
import logging
import discord
from discord import app_commands
from typing import List, Optional, Dict, Any, Union, Tuple, Callable

from models.guild import Guild

logger = logging.getLogger(__name__)

async def get_server_selection(
    interaction: discord.Interaction, 
    current: str = None
) -> List[app_commands.Choice[str]]:
    """Get available server choices for command autocompletion
    
    Args:
        interaction: Discord interaction
        current: Current input value (partial server name)
        
    Returns:
        List of server choices
    """
    # Get guild settings
    guild_data = await Guild.get_by_guild_id(str(interaction.guild_id))
    
    if not guild_data or not guild_data.servers:
        # No servers configured for this guild
        return [
            app_commands.Choice(name="No servers configured", value="none")
        ]
    
    # Filter by current input if provided
    choices = []
    for server_id, server_data in guild_data.servers.items():
        name = server_data.get("name", server_id)
        
        # Skip if doesn't match current input
        if current and current.lower() not in name.lower() and current.lower() not in server_id.lower():
            continue
            
        # Add to choices
        choices.append(app_commands.Choice(name=name, value=server_id))
        
        # Discord limits to 25 choices
        if len(choices) >= 25:
            break
            
    return choices

async def get_server_id_from_name(guild_id: str, server_name: str) -> Optional[str]:
    """Get server ID from name
    
    Args:
        guild_id: Discord guild ID
        server_name: Server name
        
    Returns:
        Server ID if found, None otherwise
    """
    guild_data = await Guild.get_by_guild_id(guild_id)
    
    if not guild_data or not guild_data.servers:
        return None
        
    # Try exact match first
    for server_id, server_data in guild_data.servers.items():
        name = server_data.get("name", server_id)
        if name.lower() == server_name.lower():
            return server_id
            
    # Try partial match
    for server_id, server_data in guild_data.servers.items():
        name = server_data.get("name", server_id)
        if server_name.lower() in name.lower():
            return server_id
            
    # Try server ID itself
    if server_name in guild_data.servers:
        return server_name
        
    return None

async def get_all_server_ids(guild_id: str) -> List[str]:
    """Get all server IDs for a guild
    
    Args:
        guild_id: Discord guild ID
        
    Returns:
        List of server IDs
    """
    guild_data = await Guild.get_by_guild_id(guild_id)
    
    if not guild_data or not guild_data.servers:
        return []
        
    return list(guild_data.servers.keys())

def format_server_name(server_data: Dict[str, Any]) -> str:
    """Format server name with additional info
    
    Args:
        server_data: Server data
        
    Returns:
        Formatted server name
    """
    name = server_data.get("name", "Unknown")
    game_mode = server_data.get("game_mode", "")
    player_count = server_data.get("player_count", 0)
    max_players = server_data.get("max_players", 0)
    
    if game_mode and player_count and max_players:
        return f"{name} ({game_mode}, {player_count}/{max_players} players)"
    elif game_mode:
        return f"{name} ({game_mode})"
    else:
        return name