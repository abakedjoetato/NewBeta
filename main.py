"""
Main entry point for the Tower of Temptation PvP Statistics Discord Bot.

This module provides:
1. Bot initialization
2. Command-line arguments
3. Environment setup
"""
import os
import sys
import logging
import argparse
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f"logs/bot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log", encoding="utf-8", mode="w"),
    ]
)
logger = logging.getLogger("main")

def parse_arguments():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(description="Tower of Temptation PvP Statistics Discord Bot")
    
    # Add arguments
    parser.add_argument("--mode", choices=["bot", "web", "both"], default="both",
                        help="Run mode: 'bot', 'web', or 'both' (default)")
    parser.add_argument("--maintenance", action="store_true",
                        help="Run in maintenance mode (limited functionality)")
    parser.add_argument("--debug", action="store_true",
                        help="Enable debug logging")
    parser.add_argument("--no-db", action="store_true",
                        help="Run without database connection")
    
    return parser.parse_args()

def setup_environment():
    """Set up environment"""
    # Ensure required directories exist
    os.makedirs("logs", exist_ok=True)
    os.makedirs("cogs", exist_ok=True)
    os.makedirs("data", exist_ok=True)

def main():
    """Main entry point"""
    # Parse command-line arguments
    args = parse_arguments()
    
    # Set up environment
    setup_environment()
    
    # Set log level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")
    
    # Run in appropriate mode
    if args.mode in ["bot", "both"]:
        logger.info("Starting Discord bot...")
        
        if args.no_db:
            os.environ["SKIP_DB_CONNECTION"] = "1"
            logger.warning("Running without database connection")
            
        if args.maintenance:
            os.environ["MAINTENANCE_MODE"] = "1"
            logger.warning("Running in maintenance mode")
        
        try:
            from bot import run_bot
            run_bot()
        except ImportError as e:
            logger.error(f"Failed to import bot module: {e}")
            return 1
        except Exception as e:
            logger.error(f"Error running bot: {e}")
            return 1
            
    if args.mode in ["web", "both"]:
        logger.info("Starting web server...")
        
        try:
            import web.app
            from web.app import app
            
            # Only run web server if not already running from bot
            if args.mode == "web":
                host = os.environ.get("HOST", "0.0.0.0")
                port = int(os.environ.get("PORT", 5000))
                debug = bool(os.environ.get("FLASK_DEBUG", args.debug))
                
                app.run(host=host, port=port, debug=debug)
                
        except ImportError as e:
            logger.error(f"Failed to import web module: {e}")
            return 1
        except Exception as e:
            logger.error(f"Error running web server: {e}")
            return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())