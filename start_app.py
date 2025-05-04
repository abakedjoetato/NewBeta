#!/usr/bin/env python
"""
Script to start the Flask web application for the Tower of Temptation PvP Statistics Bot
"""
import os
import sys
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("start_app")

def main():
    """Start the Flask web application"""
    try:
        # Import and run the Flask app
        logger.info("Starting Flask web application on port 5000")
        from app import app
        app.run(host='0.0.0.0', port=5000, debug=True)
    except Exception as e:
        logger.error(f"Failed to start web application: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()