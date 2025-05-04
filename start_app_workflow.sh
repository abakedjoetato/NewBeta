#!/bin/bash

# Script to start the Tower of Temptation PvP Statistics Bot web application
# Run this script to start the Flask web application with a workflow

echo "Starting Tower of Temptation PvP Statistics Bot Web App..."

# Make the script executable
chmod +x start_web_app.sh

# Check for PostgreSQL database
if [ -z "$DATABASE_URL" ]; then
    echo "DATABASE_URL not set. Using default PostgreSQL URL."
    export DATABASE_URL="postgresql://$(whoami):@localhost:5432/pvp_stats_bot"
fi

# Create data directories if they don't exist
mkdir -p data/logs

# Set up environment variables
export FLASK_APP=main.py
export FLASK_ENV=development

# Start the web application
echo "Starting web application..."
./start_web_app.sh