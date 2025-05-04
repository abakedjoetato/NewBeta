#!/bin/bash

# Script to run both the Discord bot and the web application for the
# Tower of Temptation PvP Statistics Bot

echo "Starting Tower of Temptation PvP Statistics Bot System..."

# Make scripts executable
chmod +x start_discord_bot.sh
chmod +x start_web_app.sh

# Check for required environment variables
echo "Checking environment variables..."

if [ -z "$DISCORD_TOKEN" ]; then
    echo "Error: DISCORD_TOKEN environment variable is not set."
    echo "Please set the DISCORD_TOKEN environment variable to your Discord bot token."
    exit 1
fi

if [ -z "$DATABASE_URL" ]; then
    echo "Error: DATABASE_URL environment variable is not set."
    echo "Please set the DATABASE_URL environment variable for your PostgreSQL database."
    exit 1
fi

if [ -z "$MONGODB_URI" ]; then
    echo "Error: MONGODB_URI environment variable is not set."
    echo "Please set the MONGODB_URI environment variable for your MongoDB database."
    exit 1
fi

# Create data directories if they don't exist
mkdir -p data/logs

# Start both services in the background
echo "Starting Discord bot..."
./start_discord_bot.sh &
BOT_PID=$!

echo "Starting web application..."
./start_web_app.sh &
WEB_PID=$!

# Handle shutdown
function cleanup {
    echo "Shutting down services..."
    kill $BOT_PID
    kill $WEB_PID
    exit 0
}

# Register the cleanup function for signals
trap cleanup SIGINT SIGTERM

# Keep the script running
echo "Both services started. Press Ctrl+C to stop."
wait