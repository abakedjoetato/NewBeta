"""
Simple script to run the Discord bot
"""
import asyncio
import sys
from run_discord_bot import main

if __name__ == "__main__":
    print("Starting Discord bot...")
    asyncio.run(main())
    print("Bot execution completed.")