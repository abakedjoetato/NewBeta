"""
Database models for the Flask web app
"""
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

# Import db from a separate module to avoid circular imports
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import db

class User(UserMixin, db.Model):
    """User model for authentication"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, password):
        """Set password hash"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check password against hash"""
        return check_password_hash(self.password_hash, password)
        
    def __repr__(self):
        return f'<User {self.username}>'

class BotStat(db.Model):
    """Statistics about the bot's operation"""
    id = db.Column(db.Integer, primary_key=True)
    guild_count = db.Column(db.Integer, default=0)
    user_count = db.Column(db.Integer, default=0)
    command_count = db.Column(db.Integer, default=0)
    uptime = db.Column(db.Float, default=0)  # in seconds
    cpu_usage = db.Column(db.Float, default=0)  # percentage
    memory_usage = db.Column(db.Float, default=0)  # in MB
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<BotStat {self.timestamp}>'

class ServerStat(db.Model):
    """Statistics about specific game servers"""
    id = db.Column(db.Integer, primary_key=True)
    server_id = db.Column(db.String(64), nullable=False)
    guild_id = db.Column(db.BigInteger, nullable=False)
    player_count = db.Column(db.Integer, default=0)
    kill_count = db.Column(db.Integer, default=0)
    death_count = db.Column(db.Integer, default=0)
    suicide_count = db.Column(db.Integer, default=0)
    faction_count = db.Column(db.Integer, default=0)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Create index on server_id and timestamp for faster lookups
    __table_args__ = (
        db.Index('idx_server_timestamp', 'server_id', 'timestamp'),
    )
    
    def __repr__(self):
        return f'<ServerStat {self.server_id} {self.timestamp}>'