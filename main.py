"""
Tower of Temptation PvP Statistics Discord Bot Main Entry

This file serves as a simple redirector to launch the Discord bot from bot.py
"""
import asyncio
import os
import sys
from bot import startup

# Main entry point for the Discord Bot
if __name__ == "__main__":
    # Run the bot startup process
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(startup())
    except KeyboardInterrupt:
        print("Shutting down bot...")
    except Exception as e:
        print(f"Error starting bot: {e}")
        sys.exit(1)
    finally:
        loop.close()