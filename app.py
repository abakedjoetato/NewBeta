"""
Flask web application for Tower of Temptation PvP Statistics Bot

This provides:
1. Bot statistics dashboard
2. Admin interface for bot management
3. Player leaderboards and rivalry data
4. Guild configuration interface
"""
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import generate_password_hash, check_password_hash

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "pvpstats_dev_secret")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Configure the database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# Initialize the app with extensions
db.init_app(app)

# Routes
@app.route('/')
def home():
    """Home page"""
    return render_template('index.html', title="Tower of Temptation PvP Stats")

@app.route('/stats')
def stats():
    """Bot statistics page"""
    return render_template('stats.html', title="Bot Statistics")

@app.route('/leaderboards')
def leaderboards():
    """Player leaderboards page"""
    return render_template('leaderboards.html', title="Leaderboards")

@app.route('/rivalries')
def rivalries():
    """Rivalries page"""
    return render_template('rivalries.html', title="Rivalries")

@app.route('/admin')
def admin():
    """Admin dashboard"""
    # Check if user is authenticated
    if not session.get('is_authenticated'):
        return redirect(url_for('login'))
    
    return render_template('admin.html', title="Admin Dashboard")

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Simple authentication for dev
        if username == 'admin' and password == 'temppassword':
            session['is_authenticated'] = True
            flash('Login successful', 'success')
            return redirect(url_for('admin'))
        else:
            flash('Invalid credentials', 'error')
    
    return render_template('login.html', title="Login")

@app.route('/logout')
def logout():
    """Logout"""
    session.pop('is_authenticated', None)
    flash('You have been logged out', 'info')
    return redirect(url_for('home'))

# API Routes
@app.route('/api/bot-status')
def api_bot_status():
    """API endpoint for bot status"""
    # Mock data for now
    status = {
        'is_online': True,
        'uptime': '3 days, 4 hours',
        'guilds': 12,
        'commands_used': 1458,
        'version': '1.2.3'
    }
    return jsonify(status)

@app.route('/api/recent-activity')
def api_recent_activity():
    """API endpoint for recent activity"""
    # Mock data for now
    activity = [
        {'event': 'kill', 'player': 'Player1', 'target': 'Player2', 'time': '2 minutes ago'},
        {'event': 'bounty_claimed', 'player': 'Player3', 'reward': 500, 'time': '15 minutes ago'},
        {'event': 'bounty_placed', 'player': 'Player4', 'target': 'Player1', 'reward': 1000, 'time': '30 minutes ago'},
    ]
    return jsonify(activity)

# Error handlers
@app.errorhandler(404)
def page_not_found(e):
    """Handle 404 errors"""
    return render_template('404.html', title="Not Found"), 404

@app.errorhandler(500)
def server_error(e):
    """Handle 500 errors"""
    return render_template('500.html', title="Server Error"), 500

# Create needed directories
def ensure_directories():
    """Ensure needed directories exist"""
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static/css', exist_ok=True)
    os.makedirs('static/js', exist_ok=True)

# Initialize tables
with app.app_context():
    ensure_directories()
    from models_sql import User, WebConfig, ApiToken
    db.create_all()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)