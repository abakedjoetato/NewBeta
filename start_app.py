"""
Tower of Temptation PvP Statistics Platform - Unified Entry Point

This script provides a single entry point for the full Tower of Temptation PvP Statistics platform,
capable of launching either:
1. The Discord bot for game statistics tracking
2. The web dashboard for admin access and statistics visualization

Usage:
    python start_app.py                  # Start both the Discord bot and web app
    python start_app.py --bot-only       # Start only the Discord bot
    python start_app.py --web-only       # Start only the web app
    
The script handles environment validation, proper initialization sequences, and ensures
that the components are started in the correct order with proper error handling.
"""

import argparse
import asyncio
import logging
import os
import sys
import threading
import time
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("tower_of_temptation.log")
    ]
)
logger = logging.getLogger("TowerOfTemptation")

# Required environment variables
REQUIRED_ENV_VARS = {
    "discord_bot": [
        "DISCORD_TOKEN",
        "BOT_APPLICATION_ID", 
        "MONGODB_URI",
        "HOME_GUILD_ID"
    ],
    "web_app": [
        "DATABASE_URL",
        "FLASK_SECRET_KEY"
    ]
}

def validate_environment(component: str) -> Tuple[bool, List[str]]:
    """
    Validate environment variables for a specific component.
    
    Args:
        component: Either 'discord_bot' or 'web_app'
        
    Returns:
        Tuple of (is_valid, missing_vars)
    """
    if component not in REQUIRED_ENV_VARS:
        logger.error(f"Unknown component: {component}")
        return False, []
        
    required_vars = REQUIRED_ENV_VARS[component]
    missing_vars = [var for var in required_vars if not os.environ.get(var)]
    
    if missing_vars:
        logger.warning(f"Missing environment variables for {component}: {', '.join(missing_vars)}")
        return False, missing_vars
    
    logger.info(f"All required environment variables present for {component}")
    return True, []

def run_flask_app():
    """Start the Flask web application."""
    logger.info("Starting Flask web application...")
    
    try:
        # Import here to avoid circular imports and to make this module independent
        from app import app
        
        # Default to port 5000 if none is specified
        port = int(os.environ.get("PORT", 5000))
        
        # Use 0.0.0.0 to make the server externally visible
        app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
    except Exception as e:
        logger.error(f"Failed to start Flask web application: {e}", exc_info=True)
        return False
    
    return True

async def run_discord_bot():
    """Start the Discord bot."""
    logger.info("Starting Discord bot...")
    
    try:
        # Import the bot module functions here to avoid circular imports
        from bot import initialize_bot
        
        token = os.environ.get("DISCORD_TOKEN")
        if not token:
            logger.error("DISCORD_TOKEN environment variable not set")
            return False
        
        # Initialize and start the bot
        bot = await initialize_bot(force_sync=True)
        await bot.start(token)
    except Exception as e:
        logger.error(f"Failed to start Discord bot: {e}", exc_info=True)
        return False
    
    return True

def start_web_app_thread():
    """Start the web app in a separate thread."""
    is_valid, missing_vars = validate_environment("web_app")
    if not is_valid:
        logger.error(f"Cannot start web app due to missing environment variables: {', '.join(missing_vars)}")
        return None
    
    web_thread = threading.Thread(target=run_flask_app, daemon=True)
    web_thread.start()
    logger.info("Web application thread started")
    return web_thread

async def start_discord_bot():
    """Start the Discord bot."""
    is_valid, missing_vars = validate_environment("discord_bot")
    if not is_valid:
        logger.error(f"Cannot start Discord bot due to missing environment variables: {', '.join(missing_vars)}")
        return False
    
    return await run_discord_bot()

async def main():
    """Main entry point for the application."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Tower of Temptation PvP Statistics Platform")
    parser.add_argument("--bot-only", action="store_true", help="Start only the Discord bot")
    parser.add_argument("--web-only", action="store_true", help="Start only the web application")
    args = parser.parse_args()
    
    # Log startup information
    logger.info("=== Tower of Temptation PvP Statistics Platform ===")
    logger.info(f"Starting up at {datetime.now().isoformat()}")
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Operating system: {sys.platform}")
    
    # Determine which components to start
    start_bot = not args.web_only
    start_web = not args.bot_only
    
    if start_web:
        logger.info("Web application enabled")
        web_thread = start_web_app_thread()
        if not web_thread:
            logger.error("Failed to start web application")
            if not start_bot:
                return  # Exit if only web app was requested
    
    if start_bot:
        logger.info("Discord bot enabled")
        success = await start_discord_bot()
        if not success:
            logger.error("Failed to start Discord bot")
            if not start_web:
                return  # Exit if only bot was requested
    
    # Keep the main thread alive as long as any component is running
    web_thread = None  # Initialize to avoid unbound variable warning
    
    try:
        web_thread_active = False
        
        while True:
            # Check if web thread is active
            if start_web and web_thread and web_thread.is_alive():
                web_thread_active = True
                await asyncio.sleep(1)
            elif start_bot:
                # Bot runs in the main thread, we won't reach here unless it fails
                break
            elif not web_thread_active:
                # No components are running
                logger.warning("No components are running, shutting down")
                break
    except KeyboardInterrupt:
        logger.info("Received shutdown signal, shutting down...")
    except Exception as e:
        logger.error(f"Error in main thread: {e}", exc_info=True)
    
    logger.info("Tower of Temptation PvP Statistics Platform shutting down")

if __name__ == "__main__":
    asyncio.run(main())