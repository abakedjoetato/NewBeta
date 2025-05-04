"""
Flask web app for the Tower of Temptation PvP Statistics Discord Bot
"""
import os
import logging
from datetime import datetime, timedelta

from flask import Flask, render_template, jsonify, request, redirect, url_for, flash, abort
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
# create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", os.urandom(24))
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)  # needed for url_for to generate with https

# configure the database, relative to the app instance folder
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
# initialize the app with the extension
db.init_app(app)

# Import models after db initialization
from models.web import BotStatus, ErrorLog, StatsSnapshot

with app.app_context():
    # Create tables if they don't exist
    db.create_all()

@app.route('/')
def index():
    """Display a simple web page explaining that this is a Discord bot"""
    return render_template('index.html')

@app.route('/status')
def status():
    """Display the current status of the Discord bot"""
    bot_status = BotStatus.query.order_by(BotStatus.timestamp.desc()).first()
    recent_errors = ErrorLog.query.order_by(ErrorLog.timestamp.desc()).limit(10).all()
    
    # Get stats from the last 24 hours
    one_day_ago = datetime.utcnow() - timedelta(days=1)
    stats = StatsSnapshot.query.filter(StatsSnapshot.timestamp >= one_day_ago).order_by(StatsSnapshot.timestamp.desc()).all()
    
    return render_template('status.html', 
                          bot_status=bot_status, 
                          recent_errors=recent_errors,
                          stats=stats)

@app.route('/api/status')
def api_status():
    """Return the current status of the Discord bot as JSON"""
    bot_status = BotStatus.query.order_by(BotStatus.timestamp.desc()).first()
    
    if bot_status:
        status_data = {
            'online': bot_status.is_online,
            'uptime': bot_status.uptime_seconds,
            'guilds': bot_status.guild_count,
            'last_update': bot_status.timestamp.isoformat(),
            'version': bot_status.version
        }
    else:
        status_data = {
            'online': False,
            'uptime': 0,
            'guilds': 0,
            'last_update': None,
            'version': 'Unknown'
        }
    
    return jsonify(status_data)

@app.route('/api/errors')
def api_errors():
    """Return recent errors as JSON"""
    limit = request.args.get('limit', 10, type=int)
    recent_errors = ErrorLog.query.order_by(ErrorLog.timestamp.desc()).limit(limit).all()
    
    errors_data = [{
        'timestamp': error.timestamp.isoformat(),
        'level': error.level,
        'message': error.message,
        'source': error.source
    } for error in recent_errors]
    
    return jsonify(errors_data)

@app.route('/api/stats')
def api_stats():
    """Return recent stats as JSON"""
    days = request.args.get('days', 1, type=int)
    time_ago = datetime.utcnow() - timedelta(days=days)
    
    stats = StatsSnapshot.query.filter(StatsSnapshot.timestamp >= time_ago).order_by(StatsSnapshot.timestamp).all()
    
    stats_data = [{
        'timestamp': stat.timestamp.isoformat(),
        'commands_used': stat.commands_used,
        'active_users': stat.active_users,
        'kills_tracked': stat.kills_tracked,
        'bounties_placed': stat.bounties_placed,
        'bounties_claimed': stat.bounties_claimed
    } for stat in stats]
    
    return jsonify(stats_data)

@app.route('/documentation')
def documentation():
    """Display documentation about the Discord bot"""
    return render_template('documentation.html')

@app.errorhandler(404)
def page_not_found(e):
    """Handle 404 errors"""
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    """Handle 500 errors"""
    return render_template('500.html'), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)