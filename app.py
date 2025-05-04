"""
Tower of Temptation PvP Statistics Discord Bot - Bot Status Helper

This simple module provides status tracking functions for the Discord bot.
It has been modified to remove all web application functionality and 
SQL database dependencies as per project requirements.
"""
import logging
import os
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
BOT_VERSION = "1.0.0"

# In-memory status tracking (no SQL dependency)
bot_start_time = None
guild_count = 0
recent_errors = []
command_count = 0

def record_bot_start():
    """Record the bot start time"""
    global bot_start_time
    bot_start_time = datetime.utcnow()
    logger.info(f"Bot start time recorded: {bot_start_time}")

def update_guild_count(count):
    """Update the current guild count"""
    global guild_count
    guild_count = count
    logger.info(f"Guild count updated to: {count}")

def get_uptime_seconds():
    """Get the current bot uptime in seconds"""
    if bot_start_time:
        return (datetime.utcnow() - bot_start_time).total_seconds()
    return 0

def log_error(error_message, source="discord_bot", level="ERROR"):
    """Log an error to the in-memory error log"""
    global recent_errors
    error_data = {
        "timestamp": datetime.utcnow(),
        "message": error_message,
        "source": source,
        "level": level
    }
    recent_errors.append(error_data)
    # Keep only the most recent 100 errors
    if len(recent_errors) > 100:
        recent_errors = recent_errors[-100:]
    logger.error(f"{level} from {source}: {error_message}")

def get_recent_errors(limit=10):
    """Get the most recent errors"""
    global recent_errors
    return recent_errors[-limit:] if recent_errors else []

def increment_command_count():
    """Increment the command counter"""
    global command_count
    command_count += 1

def get_status_summary():
    """Get a summary of the bot's current status"""
    return {
        "version": BOT_VERSION,
        "uptime_seconds": get_uptime_seconds(),
        "guild_count": guild_count,
        "command_count": command_count,
        "error_count": len(recent_errors)
    }