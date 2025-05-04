"""
Web application models for the Tower of Temptation PvP Statistics Discord Bot
"""
from datetime import datetime
from app import db

class BotStatus(db.Model):
    """
    Represents the current status of the Discord bot.
    
    This table stores periodic snapshots of the bot's status.
    """
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    is_online = db.Column(db.Boolean, default=False, nullable=False)
    uptime_seconds = db.Column(db.Integer, default=0, nullable=False)
    guild_count = db.Column(db.Integer, default=0, nullable=False)
    version = db.Column(db.String(20), default='0.1.0', nullable=False)
    
    def __repr__(self):
        return f"<BotStatus id={self.id} online={self.is_online} guilds={self.guild_count}>"

class ErrorLog(db.Model):
    """
    Represents an error log entry from the Discord bot.
    
    This table stores errors encountered by the bot.
    """
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    level = db.Column(db.String(10), default='ERROR', nullable=False)
    source = db.Column(db.String(50), nullable=False)
    message = db.Column(db.Text, nullable=False)
    traceback = db.Column(db.Text, nullable=True)
    
    def __repr__(self):
        return f"<ErrorLog id={self.id} level={self.level} source={self.source}>"

class StatsSnapshot(db.Model):
    """
    Represents a periodic snapshot of bot statistics.
    
    This table stores metrics about bot usage.
    """
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    commands_used = db.Column(db.Integer, default=0, nullable=False)
    active_users = db.Column(db.Integer, default=0, nullable=False)
    kills_tracked = db.Column(db.Integer, default=0, nullable=False)
    bounties_placed = db.Column(db.Integer, default=0, nullable=False)
    bounties_claimed = db.Column(db.Integer, default=0, nullable=False)
    
    def __repr__(self):
        return f"<StatsSnapshot id={self.id} commands={self.commands_used} users={self.active_users}>"

class ServerConfig(db.Model):
    """
    Represents configuration settings for a specific server.
    
    This table stores web-configurable settings for Discord servers.
    """
    id = db.Column(db.Integer, primary_key=True)
    server_id = db.Column(db.String(20), nullable=False, unique=True, index=True)
    guild_id = db.Column(db.String(20), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    sftp_host = db.Column(db.String(255), nullable=True)
    sftp_port = db.Column(db.Integer, default=22, nullable=True)
    sftp_username = db.Column(db.String(100), nullable=True)
    sftp_password = db.Column(db.String(255), nullable=True)
    sftp_directory = db.Column(db.String(255), nullable=True)
    log_pattern = db.Column(db.String(100), default='*.csv', nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    
    def __repr__(self):
        return f"<ServerConfig id={self.id} name={self.name} server={self.server_id}>"

class FactionConfig(db.Model):
    """
    Represents configuration for a faction in a specific game server.
    
    This table stores faction information for display in stats.
    """
    id = db.Column(db.Integer, primary_key=True)
    server_id = db.Column(db.String(20), db.ForeignKey('server_config.server_id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    identifier = db.Column(db.String(50), nullable=False)
    color = db.Column(db.String(7), default='#FFFFFF', nullable=False)
    icon_url = db.Column(db.String(255), nullable=True)
    
    # Relationship
    server = db.relationship('ServerConfig', backref=db.backref('factions', lazy=True))
    
    def __repr__(self):
        return f"<FactionConfig id={self.id} name={self.name} server={self.server_id}>"