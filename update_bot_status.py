"""
Script to update the bot's status in the in-memory tracking system.

This script is meant to be run periodically to provide status updates about the Discord bot.
It has been updated to remove any web interface or SQL database dependencies.
"""
import os
import sys
import logging
import time
from datetime import datetime
import asyncio
import discord
from utils.sql_db import update_bot_status, log_error, increment_stat

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

async def update_status_tracking():
    """Update the bot status in the in-memory tracking system."""
    try:
        logger.info('Updating bot status...')
        
        # Connect to Discord to get real data
        client, status_values = await get_bot_client()
        
        # Calculate uptime
        uptime = 0
        if status_values['is_connected']:
            uptime = int(time.time() - status_values['start_time'])
        
        # Get version from environment or use default
        version = os.environ.get('BOT_VERSION', '1.0.0')
        
        # Update the status tracking
        update_bot_status(
            is_online=status_values['is_connected'],
            guild_count=status_values['guild_count'],
            uptime_seconds=uptime,
            version=version
        )
        
        logger.info(f'Status updated. Online: {status_values["is_connected"]}, Guilds: {status_values["guild_count"]}')
        
        # If we have real data, update stats as well
        if status_values['is_connected']:
            # In a real implementation, we would query MongoDB for current stats
            # but for now we'll just increment some counters
            increment_stat("command_checks")
            logger.info('Stats tracking updated')
        
        return True
    except Exception as e:
        error_message = f'Error updating status: {e}'
        logger.error(error_message)
        
        # Log the error
        log_error('status_updater', error_message, str(sys.exc_info()))
        
        return False

if __name__ == "__main__":
    logger.info('Bot status updater started')
    asyncio.run(update_status_tracking())
    logger.info('Bot status updater finished')