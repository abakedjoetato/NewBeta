#!/bin/bash
# Full-Service Startup Script for Tower of Temptation PvP Statistics Platform
# This script handles proper environment detection, component selection,
# and contains enhanced error handling for production environments.

# Set strict error handling
set -e

# Function to display errors clearly
error_exit() {
  echo -e "\033[31mERROR: $1\033[0m" >&2
  exit 1
}

# Detect Python executable
PYTHON_CMD="python"
if ! command -v python &> /dev/null; then
    PYTHON_CMD="python3"
    if ! command -v python3 &> /dev/null; then
        error_exit "Could not find Python executable. Please install Python 3.8+ and try again."
    fi
fi

# Display version info for logging purposes
echo "---------- System Information ----------"
echo "Using Python: $($PYTHON_CMD --version)"
echo "System: $(uname -a)"
echo "Date: $(date)"
echo "---------------------------------------"

# Verify that the start_app.py script exists
if [ ! -f "start_app.py" ]; then
    error_exit "Could not find start_app.py in the current directory."
fi

# Check for passed arguments
MODE="full"  # Default to full mode (bot + web)

while [[ "$#" -gt 0 ]]; do
    case $1 in
        --bot-only) MODE="bot"; shift ;;
        --web-only) MODE="web"; shift ;;
        --help|-h) 
            echo "Usage: $0 [--bot-only|--web-only]"
            echo ""
            echo "Options:"
            echo "  --bot-only    Start only the Discord bot component"
            echo "  --web-only    Start only the web application component"
            echo "  --help, -h    Show this help message"
            exit 0 ;;
        *) error_exit "Unknown parameter: $1. Use --help to see available options." ;;
    esac
done

# Ensure critical environment variables are accessible
echo "Verifying environment variables..."

if [ "$MODE" = "bot" ] || [ "$MODE" = "full" ]; then
    # Check Discord bot environment variables
    if [ -z "$DISCORD_TOKEN" ]; then
        error_exit "DISCORD_TOKEN environment variable is required but not set."
    fi
    if [ -z "$BOT_APPLICATION_ID" ]; then
        error_exit "BOT_APPLICATION_ID environment variable is required but not set."
    fi
    if [ -z "$MONGODB_URI" ]; then
        error_exit "MONGODB_URI environment variable is required but not set."
    fi
    # HOME_GUILD_ID is important but technically optional, so just warn
    if [ -z "$HOME_GUILD_ID" ]; then
        echo -e "\033[33mWARNING: HOME_GUILD_ID is not set. Some bot functions may be limited.\033[0m"
    fi
fi

if [ "$MODE" = "web" ] || [ "$MODE" = "full" ]; then
    # Check web app environment variables
    if [ -z "$DATABASE_URL" ]; then
        error_exit "DATABASE_URL environment variable is required but not set."
    fi
    # FLASK_SECRET_KEY is important for security, but we can generate one if missing
    if [ -z "$FLASK_SECRET_KEY" ]; then
        echo -e "\033[33mWARNING: FLASK_SECRET_KEY is not set. Generating a random secret key.\033[0m"
        export FLASK_SECRET_KEY=$(openssl rand -hex 24)
    fi
fi

# Start the application with appropriate mode
echo "Starting Tower of Temptation PvP Statistics Platform in $MODE mode..."

case $MODE in
    "bot")
        $PYTHON_CMD start_app.py --bot-only
        ;;
    "web")
        $PYTHON_CMD start_app.py --web-only
        ;;
    "full")
        $PYTHON_CMD start_app.py
        ;;
esac

# The script should not normally reach this point unless there's an error
# (the Python process should keep running)
echo "Process has exited. Check logs for details."