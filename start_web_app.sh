#!/bin/bash

# Script to start the Flask web application for Tower of Temptation PvP Statistics Bot

echo "Starting Tower of Temptation PvP Statistics Bot Web App..."

# Ensure required environment variables are set
if [ -z "$DATABASE_URL" ]; then
    echo "Error: DATABASE_URL environment variable is not set."
    exit 1
fi

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
fi

# Make sure Flask and dependencies are installed
echo "Checking dependencies..."
pip install -r requirements.txt

# Run the application
echo "Starting Flask application on port 5000..."
gunicorn --bind 0.0.0.0:5000 main:app