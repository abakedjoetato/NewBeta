"""
SQLAlchemy database utilities for the Tower of Temptation PvP Statistics Bot.

This module provides functions to interact with the PostgreSQL database used by the web application,
allowing the Discord bot to access and update shared data.
"""
import os
import logging
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)

# Get database URL from environment
DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    logger.error('DATABASE_URL environment variable not set')
    raise ValueError('DATABASE_URL environment variable not set')

# Create SQLAlchemy engine and session
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
Base = declarative_base()

def get_session():
    """
    Get a new database session.
    
    Returns:
        SQLAlchemy Session object
    """
    return Session()

def log_error(source: str, message: str, traceback: str = None):
    """
    Log an error to the database.
    
    Args:
        source: Source of the error (e.g., 'discord_bot', 'csv_parser')
        message: Error message
        traceback: Optional traceback
    
    Returns:
        True if logged successfully, False otherwise
    """
    from models.web import ErrorLog
    
    try:
        session = get_session()
        error_log = ErrorLog(
            timestamp=datetime.utcnow(),
            level='ERROR',
            source=source,
            message=message,
            traceback=traceback
        )
        session.add(error_log)
        session.commit()
        return True
    except SQLAlchemyError as e:
        logger.error(f'Error logging to database: {e}')
        return False
    finally:
        session.close()

def log_warning(source: str, message: str):
    """
    Log a warning to the database.
    
    Args:
        source: Source of the warning (e.g., 'discord_bot', 'csv_parser')
        message: Warning message
    
    Returns:
        True if logged successfully, False otherwise
    """
    from models.web import ErrorLog
    
    try:
        session = get_session()
        error_log = ErrorLog(
            timestamp=datetime.utcnow(),
            level='WARNING',
            source=source,
            message=message
        )
        session.add(error_log)
        session.commit()
        return True
    except SQLAlchemyError as e:
        logger.error(f'Error logging to database: {e}')
        return False
    finally:
        session.close()

def update_bot_status(is_online: bool, guild_count: int, uptime_seconds: int, version: str = '0.1.0'):
    """
    Update the bot's status in the database.
    
    Args:
        is_online: Whether the bot is currently online
        guild_count: Number of guilds the bot is in
        uptime_seconds: Bot uptime in seconds
        version: Bot version
    
    Returns:
        True if updated successfully, False otherwise
    """
    from models.web import BotStatus
    
    try:
        session = get_session()
        status = BotStatus(
            timestamp=datetime.utcnow(),
            is_online=is_online,
            uptime_seconds=uptime_seconds,
            guild_count=guild_count,
            version=version
        )
        session.add(status)
        session.commit()
        return True
    except SQLAlchemyError as e:
        logger.error(f'Error updating bot status: {e}')
        return False
    finally:
        session.close()

def update_stats_snapshot(commands_used: int, active_users: int, kills_tracked: int, 
                          bounties_placed: int, bounties_claimed: int):
    """
    Update the stats snapshot in the database.
    
    Args:
        commands_used: Number of commands used
        active_users: Number of active users
        kills_tracked: Number of kills tracked
        bounties_placed: Number of bounties placed
        bounties_claimed: Number of bounties claimed
    
    Returns:
        True if updated successfully, False otherwise
    """
    from models.web import StatsSnapshot
    
    try:
        session = get_session()
        stats = StatsSnapshot(
            timestamp=datetime.utcnow(),
            commands_used=commands_used,
            active_users=active_users,
            kills_tracked=kills_tracked,
            bounties_placed=bounties_placed,
            bounties_claimed=bounties_claimed
        )
        session.add(stats)
        session.commit()
        return True
    except SQLAlchemyError as e:
        logger.error(f'Error updating stats snapshot: {e}')
        return False
    finally:
        session.close()

def get_server_configs():
    """
    Get all server configurations.
    
    Returns:
        List of ServerConfig objects
    """
    from models.web import ServerConfig
    
    try:
        session = get_session()
        configs = session.query(ServerConfig).filter_by(is_active=True).all()
        return configs
    except SQLAlchemyError as e:
        logger.error(f'Error getting server configs: {e}')
        return []
    finally:
        session.close()

def get_factions(server_id: str):
    """
    Get all factions for a server.
    
    Args:
        server_id: Server ID
    
    Returns:
        List of FactionConfig objects
    """
    from models.web import FactionConfig
    
    try:
        session = get_session()
        factions = session.query(FactionConfig).filter_by(server_id=server_id).all()
        return factions
    except SQLAlchemyError as e:
        logger.error(f'Error getting factions: {e}')
        return []
    finally:
        session.close()