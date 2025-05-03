"""
Flask Web Application for the Tower of Temptation PvP Statistics Discord Bot.

This module provides:
1. Web dashboard for managing the Discord bot
2. API endpoints for accessing bot data
3. Authentication for secure access
"""
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Set

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from werkzeug.middleware.proxy_fix import ProxyFix

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("web.log", encoding="utf-8"),
    ]
)
logger = logging.getLogger("web")

# Create Flask app
app = Flask(__name__)

# Set up app configuration
app.config.update(
    SECRET_KEY=os.environ.get("SESSION_SECRET", "dev-secret-key"),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=True if os.environ.get("PRODUCTION") else False,
    PERMANENT_SESSION_LIFETIME=timedelta(days=7),
    SQLALCHEMY_DATABASE_URI=os.environ.get("DATABASE_URL", "sqlite:///web.db"),
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    SQLALCHEMY_ENGINE_OPTIONS={
        "pool_pre_ping": True,
        "pool_recycle": 300,
    },
    MAX_CONTENT_LENGTH=10 * 1024 * 1024,  # 10 MB max upload size
    TEMPLATES_AUTO_RELOAD=True
)

# Set up proxy fix for proper IP handling behind proxy
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Initialize SQLAlchemy
db = SQLAlchemy(app)

# Register template context processor
@app.context_processor
def inject_now():
    """Inject current time into templates"""
    return {'now': datetime.utcnow()}

# Import and register routes after app is created
from web.routes import register_routes
register_routes(app)

# Create all tables
with app.app_context():
    db.create_all()

# Run app if executed directly
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)