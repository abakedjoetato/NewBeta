"""
Script to update the bot's status in the database.

This script is meant to be run periodically to provide status updates about the Discord bot
for the web interface.
"""
import os
import sys
import logging
import time
from datetime import datetime
import asyncio
import discord
from app import app, db
from models.web import BotStatus, ErrorLog, StatsSnapshot

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('bot_status_updater.log')
    ]
)
logger = logging.getLogger(__name__)

async def get_bot_client():
    """
    Create a Discord client and connect it to get bot status.
    """
    intents = discord.Intents.default()
    intents.guilds = True
    client = discord.Client(intents=intents)
    
    # Store values to be accessible in the on_ready event
    status_values = {
        'guild_count': 0,
        'is_connected': False,
        'start_time': time.time()
    }
    
    @client.event
    async def on_ready():
        logger.info(f'Logged in as {client.user.name} (ID: {client.user.id})')
        status_values['guild_count'] = len(client.guilds)
        status_values['is_connected'] = True
    
    # Start the client
    try:
        token = os.environ.get('DISCORD_TOKEN')
        if not token:
            logger.error('DISCORD_TOKEN environment variable not set')
            return None, status_values
        
        # We need to create a task and cancel it when we have the info
        # since we don't want to keep the bot running
        task = asyncio.create_task(client.start(token))
        
        # Wait a bit for the on_ready event
        timeout = 30  # seconds
        start_time = time.time()
        while not status_values['is_connected'] and time.time() - start_time < timeout:
            await asyncio.sleep(1)
        
        # Once we're ready or timed out, close the connection
        await client.close()
        task.cancel()
        
        return client, status_values
    except Exception as e:
        logger.error(f'Error connecting to Discord: {e}')
        return None, status_values

async def update_status():
    """Update the bot status in the database."""
    try:
        with app.app_context():
            logger.info('Updating bot status...')
            
            # Connect to Discord to get real data
            client, status_values = await get_bot_client()
            
            # Create a new status entry
            uptime = 0
            if status_values['is_connected']:
                uptime = int(time.time() - status_values['start_time'])
            
            # Get version from environment or use default
            version = os.environ.get('BOT_VERSION', '0.1.0')
            
            status = BotStatus(
                timestamp=datetime.utcnow(),
                is_online=status_values['is_connected'],
                uptime_seconds=uptime,
                guild_count=status_values['guild_count'],
                version=version
            )
            
            # Add to database
            db.session.add(status)
            db.session.commit()
            
            logger.info(f'Status updated. Online: {status.is_online}, Guilds: {status.guild_count}')
            
            # If we have real data, update stats as well
            if status_values['is_connected']:
                # This is just a placeholder for now
                # In a real implementation, we would query MongoDB for current stats
                stats = StatsSnapshot(
                    timestamp=datetime.utcnow(),
                    commands_used=0,
                    active_users=0,
                    kills_tracked=0,
                    bounties_placed=0,
                    bounties_claimed=0
                )
                
                db.session.add(stats)
                db.session.commit()
                logger.info('Stats snapshot created')
            
            return True
    except Exception as e:
        logger.error(f'Error updating status: {e}')
        
        # Log the error in the database
        try:
            with app.app_context():
                error_log = ErrorLog(
                    timestamp=datetime.utcnow(),
                    level='ERROR',
                    source='status_updater',
                    message=str(e),
                    traceback=str(sys.exc_info())
                )
                db.session.add(error_log)
                db.session.commit()
        except Exception as db_error:
            logger.error(f'Error logging to database: {db_error}')
        
        return False

if __name__ == "__main__":
    logger.info('Bot status updater started')
    asyncio.run(update_status())
    logger.info('Bot status updater finished')