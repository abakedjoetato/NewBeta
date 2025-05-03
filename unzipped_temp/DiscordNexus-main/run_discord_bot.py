"""
Entry point script for the Discord bot to be used with deployment services like Railway
"""
import asyncio
import logging
import os
import sys
import traceback
from dotenv import load_dotenv
from bot import initialize_bot

# Load environment variables from .env file (helpful for local dev)
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot.log")
    ]
)

logger = logging.getLogger(__name__)

async def main():
    """Main function to run the Discord bot"""
    try:
        logger.info("Starting Tower of Temptation PvP Statistics Discord Bot")
        
        # Force a global sync of commands when starting the bot
        force_sync = True
        
        # Check for all required environment variables
        required_vars = ["MONGODB_URI", "DISCORD_TOKEN", "HOME_GUILD_ID"]
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            logger.critical(f"Missing required environment variables: {', '.join(missing_vars)}. Exiting.")
            return
        else:
            logger.info("All required environment variables are set")
            
        # Get the Discord token (without logging it)
        token = os.getenv("DISCORD_TOKEN")
        
        # Initialize and start the bot
        logger.info("Initializing bot...")
        bot = await initialize_bot(force_sync=force_sync)
        
        # Command syncing is handled in bot.py on_ready event
        logger.info("Starting bot...")
        await bot.start(token)
    except Exception as e:
        logger.critical(f"Failed to start bot: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    # Run the Discord bot
    logger.info("Starting bot process")
    asyncio.run(main())