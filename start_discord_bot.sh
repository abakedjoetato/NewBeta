#!/bin/bash

# Start Discord bot
echo "Starting Tower of Temptation PvP Statistics Discord Bot..."

# Ensure Python environment is activated
if [ -d ".venv" ]; then
  source .venv/bin/activate
fi

# Run the bot 
python bot.py