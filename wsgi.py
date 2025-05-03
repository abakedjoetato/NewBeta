"""
WSGI entry point for the Tower of Temptation PvP Statistics web interface.

This module provides:
1. Web application initialization
2. WSGI entry point for production servers
"""
import logging
import os

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger("wsgi")

# Import Flask app
try:
    from web.app import app as application
    logger.info("Web application initialized successfully")
except ImportError as e:
    logger.error(f"Failed to import web application: {e}")
    
    # Create a simple placeholder app for environments where the web component is not set up
    from flask import Flask, jsonify
    
    application = Flask(__name__)
    
    @application.route('/')
    def index():
        return jsonify({
            "status": "error",
            "message": "Web interface not configured properly",
            "error": str(e)
        }), 500
    
    logger.warning("Created placeholder application due to import error")

# Run application if executed directly
if __name__ == '__main__':
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 5000))
    debug = bool(os.environ.get("FLASK_DEBUG", False))
    
    application.run(host=host, port=port, debug=debug)