"""
MongoDB status tracking utilities for the Tower of Temptation PvP Statistics Discord Bot.

This module provides functions to interact with the MongoDB database to track bot statistics 
and errors. All PostgreSQL and SQLAlchemy dependencies have been removed as they are not needed.
"""
import os
import logging
from datetime import datetime
import traceback as tb

logger = logging.getLogger(__name__)

# In-memory status tracking for the bot
_bot_status = {
    "is_online": False,
    "guild_count": 0,
    "uptime_seconds": 0,
    "version": "1.0.0",
    "start_time": None,
    "last_update": None
}

# In-memory error log
_error_logs = []
_warning_logs = []

# Statistics tracking
_stats = {
    "commands_used": 0,
    "active_users": set(),  # Using a set to avoid duplicates
    "kills_tracked": 0,
    "bounties_placed": 0,
    "bounties_claimed": 0,
}

def log_error(source: str, message: str, traceback_str: str = None):
    """
    Log an error to the in-memory log.
    
    Args:
        source: Source of the error (e.g., 'discord_bot', 'csv_parser')
        message: Error message
        traceback_str: Optional traceback
    
    Returns:
        True
    """
    global _error_logs
    
    if traceback_str is None and tb.format_stack():
        traceback_str = "".join(tb.format_stack())
    
    error_log = {
        "timestamp": datetime.utcnow(),
        "level": "ERROR",
        "source": source,
        "message": message,
        "traceback": traceback_str
    }
    
    _error_logs.append(error_log)
    # Keep only the most recent 100 errors
    if len(_error_logs) > 100:
        _error_logs = _error_logs[-100:]
        
    logger.error(f"{source}: {message}")
    return True

def log_warning(source: str, message: str):
    """
    Log a warning to the in-memory log.
    
    Args:
        source: Source of the warning (e.g., 'discord_bot', 'csv_parser')
        message: Warning message
    
    Returns:
        True
    """
    global _warning_logs
    
    warning_log = {
        "timestamp": datetime.utcnow(),
        "level": "WARNING",
        "source": source,
        "message": message
    }
    
    _warning_logs.append(warning_log)
    # Keep only the most recent 100 warnings
    if len(_warning_logs) > 100:
        _warning_logs = _warning_logs[-100:]
        
    logger.warning(f"{source}: {message}")
    return True

def update_bot_status(is_online: bool, guild_count: int, uptime_seconds: int, version: str = "1.0.0"):
    """
    Update the bot's status in memory.
    
    Args:
        is_online: Whether the bot is currently online
        guild_count: Number of guilds the bot is in
        uptime_seconds: Bot uptime in seconds
        version: Bot version
    
    Returns:
        True
    """
    global _bot_status
    
    _bot_status["is_online"] = is_online
    _bot_status["guild_count"] = guild_count
    _bot_status["uptime_seconds"] = uptime_seconds
    _bot_status["version"] = version
    _bot_status["last_update"] = datetime.utcnow()
    
    logger.info(f"Bot status updated: Online={is_online}, Guilds={guild_count}, Uptime={uptime_seconds}s")
    return True

def get_bot_status():
    """
    Get the current bot status.
    
    Returns:
        Dict containing bot status
    """
    return _bot_status

def increment_stat(stat_name: str, increment: int = 1):
    """
    Increment a statistic.
    
    Args:
        stat_name: Name of the statistic to increment
        increment: Amount to increment by
    
    Returns:
        True if successful, False if the statistic doesn't exist
    """
    global _stats
    
    if stat_name in _stats:
        if isinstance(_stats[stat_name], int):
            _stats[stat_name] += increment
            return True
    return False

def add_active_user(user_id: str):
    """
    Add a user to the active users set.
    
    Args:
        user_id: Discord user ID
    
    Returns:
        True
    """
    global _stats
    
    _stats["active_users"].add(user_id)
    return True

def get_stats():
    """
    Get the current statistics.
    
    Returns:
        Dict containing statistics
    """
    stats_copy = _stats.copy()
    stats_copy["active_users"] = len(_stats["active_users"])
    return stats_copy

def get_recent_errors(limit: int = 10):
    """
    Get the most recent errors.
    
    Args:
        limit: Maximum number of errors to return
    
    Returns:
        List of error logs
    """
    return _error_logs[-limit:] if _error_logs else []

def get_recent_warnings(limit: int = 10):
    """
    Get the most recent warnings.
    
    Args:
        limit: Maximum number of warnings to return
    
    Returns:
        List of warning logs
    """
    return _warning_logs[-limit:] if _warning_logs else []