"""
Database models for the web interface of the Tower of Temptation PvP Statistics Bot
"""
from datetime import datetime
from app import db
from flask_login import UserMixin

class User(UserMixin, db.Model):
    """User model for web interface authentication"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)

class Server(db.Model):
    """Server model representing game servers monitored by the bot"""
    id = db.Column(db.Integer, primary_key=True)
    server_id = db.Column(db.String(64), unique=True, nullable=False)
    discord_guild_id = db.Column(db.BigInteger, nullable=False)
    name = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(64), nullable=True)
    port = db.Column(db.Integer, nullable=True)
    sftp_username = db.Column(db.String(64), nullable=True)
    sftp_password = db.Column(db.String(256), nullable=True)
    sftp_path = db.Column(db.String(256), nullable=True)
    premium_tier = db.Column(db.Integer, default=0)
    online_players = db.Column(db.Integer, default=0)
    max_players = db.Column(db.Integer, default=0)
    status = db.Column(db.String(32), default="Offline")
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    statistics = db.relationship('ServerStatistics', backref='server', lazy='dynamic')
    kill_events = db.relationship('KillEvent', backref='server', lazy='dynamic')
    connection_events = db.relationship('ConnectionEvent', backref='server', lazy='dynamic')

class BotStatistics(db.Model):
    """Global bot statistics"""
    id = db.Column(db.Integer, primary_key=True)
    guild_count = db.Column(db.Integer, default=0)
    server_count = db.Column(db.Integer, default=0)
    monitored_players = db.Column(db.Integer, default=0)
    total_kills = db.Column(db.Integer, default=0)
    total_connections = db.Column(db.Integer, default=0)
    premium_guilds = db.Column(db.Integer, default=0)
    commands_used = db.Column(db.Integer, default=0)
    uptime_seconds = db.Column(db.Integer, default=0)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class ServerStatistics(db.Model):
    """Statistics for each server by day"""
    id = db.Column(db.Integer, primary_key=True)
    server_id = db.Column(db.Integer, db.ForeignKey('server.id'), nullable=False)
    kills = db.Column(db.Integer, default=0)
    deaths = db.Column(db.Integer, default=0)
    suicides = db.Column(db.Integer, default=0)
    connections = db.Column(db.Integer, default=0)
    disconnections = db.Column(db.Integer, default=0)
    unique_players = db.Column(db.Integer, default=0)
    peak_players = db.Column(db.Integer, default=0)
    average_players = db.Column(db.Float, default=0.0)
    date = db.Column(db.Date, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class KillEvent(db.Model):
    """Individual kill events recorded from servers"""
    id = db.Column(db.Integer, primary_key=True)
    server_id = db.Column(db.Integer, db.ForeignKey('server.id'), nullable=False)
    killer_name = db.Column(db.String(64), nullable=True)
    killer_id = db.Column(db.String(64), nullable=True)
    victim_name = db.Column(db.String(64), nullable=False)
    victim_id = db.Column(db.String(64), nullable=False)
    weapon = db.Column(db.String(64), nullable=True)
    distance = db.Column(db.Float, nullable=True)
    killer_console = db.Column(db.String(16), nullable=True)
    victim_console = db.Column(db.String(16), nullable=True)
    is_suicide = db.Column(db.Boolean, default=False)
    suicide_type = db.Column(db.String(32), nullable=True)
    timestamp = db.Column(db.DateTime, nullable=False)
    original_data = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ConnectionEvent(db.Model):
    """Player connection/disconnection events"""
    id = db.Column(db.Integer, primary_key=True)
    server_id = db.Column(db.Integer, db.ForeignKey('server.id'), nullable=False)
    player_name = db.Column(db.String(64), nullable=False)
    player_id = db.Column(db.String(64), nullable=False)
    event_type = db.Column(db.String(16), nullable=False)  # "connect" or "disconnect"
    console = db.Column(db.String(16), nullable=True)  # Platform (PC, XSX, PS5)
    ip_address = db.Column(db.String(64), nullable=True)
    timestamp = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class WebhookConfig(db.Model):
    """Discord webhook configuration for servers"""
    id = db.Column(db.Integer, primary_key=True)
    server_id = db.Column(db.Integer, db.ForeignKey('server.id'), nullable=False)
    webhook_url = db.Column(db.String(256), nullable=False)
    webhook_type = db.Column(db.String(32), nullable=False)  # killfeed, connections, events
    is_enabled = db.Column(db.Boolean, default=True)
    embed_color = db.Column(db.String(8), default="#50C878")  # Emerald green
    embed_theme = db.Column(db.String(32), default="default")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_triggered = db.Column(db.DateTime, nullable=True)