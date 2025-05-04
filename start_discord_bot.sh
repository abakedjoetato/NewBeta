#!/bin/bash

# Comprehensive startup script for the Tower of Temptation PvP Statistics Discord Bot
# This script implements robust error handling, logging, and monitoring

# Set environment variables if not already set
export PYTHONUNBUFFERED=1
export DEBUG=${DEBUG:-false}

# Log file configuration
LOG_DIR="./logs"
LOG_FILE="${LOG_DIR}/discord_bot_$(date +%Y%m%d_%H%M%S).log"

# Create logs directory if it doesn't exist
mkdir -p "$LOG_DIR"

echo "----------------------------------------"
echo "Tower of Temptation PvP Statistics Bot"
echo "Starting bot process: $(date)"
echo "----------------------------------------"

# Function to handle cleanup on exit
cleanup() {
    echo "Received shutdown signal. Cleaning up..."
    echo "Bot process terminated at: $(date)" | tee -a "$LOG_FILE"
    exit 0
}

# Trap signals
trap cleanup SIGINT SIGTERM

# Run the bot with proper error handling
echo "Starting bot process with logs at: $LOG_FILE"

# Use python executable directly, fall back to python3 if python not found
PYTHON_CMD="python"
if ! command -v python &> /dev/null; then
    PYTHON_CMD="python3"
fi

# Execute with proper error handling and logging
$PYTHON_CMD run_discord_bot.py 2>&1 | tee -a "$LOG_FILE"

# Check exit status
if [ ${PIPESTATUS[0]} -ne 0 ]; then
    echo "Bot process exited with error. Check logs at: $LOG_FILE" | tee -a "$LOG_FILE"
    exit 1
else
    echo "Bot process exited normally at: $(date)" | tee -a "$LOG_FILE"
    exit 0
fi