"""
Flask web app for the Tower of Temptation PvP Statistics Discord Bot
"""
import os
import logging
from flask import Flask, render_template, jsonify, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Create the base class for SQLAlchemy models
class Base(DeclarativeBase):
    pass

# Initialize SQLAlchemy with the base class
db = SQLAlchemy(model_class=Base)

# Create the Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")

# Configure SQLAlchemy
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# Initialize the Flask app with SQLAlchemy
db.init_app(app)

# Import routes after app initialization to avoid circular imports
from web.routes import register_routes

# Register routes with the app
register_routes(app)

@app.route('/')
def index():
    """Display a simple web page explaining that this is a Discord bot"""
    return render_template('index.html')

@app.errorhandler(404)
def page_not_found(e):
    """Handle 404 errors"""
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    """Handle 500 errors"""
    logger.error(f"Server error: {e}")
    return render_template('500.html'), 500

# Create database tables
with app.app_context():
    # Import models
    from web.models import User, BotStat, ServerStat
    
    # Create tables
    db.create_all()
    logger.info("Database tables created")

if __name__ == "__main__":
    # Start the Flask app
    app.run(host='0.0.0.0', port=5000, debug=True)