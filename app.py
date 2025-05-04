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
from datetime import datetime

from flask import Flask, render_template, redirect, url_for, flash, request, jsonify, session, abort
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix


class Base(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)
# create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1) # needed for url_for to generate with https

# configure the database, relative to the app instance folder
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
# initialize the app with the extension, flask-sqlalchemy >= 3.0.x
db.init_app(app)

with app.app_context():
    # Make sure to import the models here or their tables won't be created
    import models_sql  # noqa: F401

    db.create_all()

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


@app.route('/')
def home():
    """Home page"""
    return render_template('index.html')


@app.route('/stats')
def stats():
    """Bot statistics page"""
    return render_template('stats.html')


@app.route('/leaderboards')
def leaderboards():
    """Player leaderboards page"""
    return render_template('leaderboards.html')


@app.route('/rivalries')
def rivalries():
    """Rivalries page"""
    return render_template('rivalries.html')


@app.route('/admin')
def admin():
    """Admin dashboard"""
    # Check if user is logged in and is admin
    # if not logged in, redirect to login page
    return render_template('admin.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if request.method == 'POST':
        # Handle login
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Handle login logic here
        flash('Login successful', 'success')
        return redirect(url_for('home'))
        
    return render_template('login.html')


@app.route('/logout')
def logout():
    """Logout"""
    # Clear session
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('home'))


@app.route('/api/bot-status')
def api_bot_status():
    """API endpoint for bot status"""
    status = {
        'status': 'online',
        'uptime': '3 days, 2 hours',
        'guilds': 5,
        'commands_processed': 1250,
        'last_updated': datetime.now().isoformat()
    }
    return jsonify(status)


@app.route('/api/recent-activity')
def api_recent_activity():
    """API endpoint for recent activity"""
    activity = [
        {
            'type': 'kill',
            'killer': 'Player1',
            'victim': 'Player2',
            'weapon': 'Sniper Rifle',
            'timestamp': datetime.now().isoformat()
        },
        {
            'type': 'bounty_placed',
            'target': 'Player3',
            'placed_by': 'Player1',
            'amount': 500,
            'timestamp': datetime.now().isoformat()
        }
    ]
    return jsonify(activity)


@app.errorhandler(404)
def page_not_found(e):
    """Handle 404 errors"""
    return render_template('errors/404.html'), 404


@app.errorhandler(500)
def server_error(e):
    """Handle 500 errors"""
    return render_template('errors/500.html'), 500


def ensure_directories():
    """Ensure needed directories exist"""
    os.makedirs('logs', exist_ok=True)
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static', exist_ok=True)
    os.makedirs('static/css', exist_ok=True)
    os.makedirs('static/js', exist_ok=True)
    os.makedirs('static/img', exist_ok=True)


if __name__ == '__main__':
    ensure_directories()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)