"""
Database models for the Tower of Temptation PvP Statistics Discord Bot
"""
import os
from datetime import datetime
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

class Guild(db.Model):
    """Discord Guild (Server) information"""
    id = db.Column(db.Integer, primary_key=True)
    guild_id = db.Column(db.String(20), unique=True, nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    premium_tier = db.Column(db.Integer, default=0)
    join_date = db.Column(db.DateTime, default=datetime.utcnow)
    last_activity = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    servers = db.relationship('GameServer', backref='guild', lazy=True)
    
    def __repr__(self):
        return f"<Guild {self.name}>"

class GameServer(db.Model):
    """Game server configuration"""
    id = db.Column(db.Integer, primary_key=True)
    guild_id = db.Column(db.Integer, db.ForeignKey('guild.id'), nullable=False)
    server_id = db.Column(db.String(50), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    sftp_host = db.Column(db.String(255), nullable=True)
    sftp_port = db.Column(db.Integer, nullable=True)
    sftp_username = db.Column(db.String(100), nullable=True)
    sftp_password = db.Column(db.String(100), nullable=True)
    sftp_directory = db.Column(db.String(255), nullable=True)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_sync = db.Column(db.DateTime, nullable=True)
    
    # Unique constraint
    __table_args__ = (
        db.UniqueConstraint('guild_id', 'server_id', name='uix_guild_server'),
    )
    
    # Relationships
    players = db.relationship('Player', backref='server', lazy=True)
    bounties = db.relationship('Bounty', backref='server', lazy=True)
    
    def __repr__(self):
        return f"<GameServer {self.name}>"

class Player(db.Model):
    """Player information from game servers"""
    id = db.Column(db.Integer, primary_key=True)
    server_id = db.Column(db.Integer, db.ForeignKey('game_server.id'), nullable=False)
    player_id = db.Column(db.String(50), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    kills = db.Column(db.Integer, default=0)
    deaths = db.Column(db.Integer, default=0)
    kd_ratio = db.Column(db.Float, default=0.0)
    first_seen = db.Column(db.DateTime, default=datetime.utcnow)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Unique constraint
    __table_args__ = (
        db.UniqueConstraint('server_id', 'player_id', name='uix_server_player'),
    )
    
    # Relationships
    links = db.relationship('PlayerLink', backref='player', lazy=True)
    target_bounties = db.relationship('Bounty', foreign_keys='Bounty.target_id', backref='target', lazy=True)
    
    def __repr__(self):
        return f"<Player {self.name}>"

class PlayerLink(db.Model):
    """Links between Discord users and in-game players"""
    id = db.Column(db.Integer, primary_key=True)
    discord_id = db.Column(db.String(20), nullable=False)
    player_id = db.Column(db.Integer, db.ForeignKey('player.id'), nullable=False)
    server_id = db.Column(db.Integer, db.ForeignKey('game_server.id'), nullable=False)
    verified = db.Column(db.Boolean, default=False)
    linked_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Unique constraint
    __table_args__ = (
        db.UniqueConstraint('discord_id', 'player_id', 'server_id', name='uix_discord_player_server'),
    )
    
    def __repr__(self):
        return f"<PlayerLink Discord:{self.discord_id} -> Player:{self.player_id}>"

class Bounty(db.Model):
    """Bounty information"""
    id = db.Column(db.Integer, primary_key=True)
    guild_id = db.Column(db.Integer, db.ForeignKey('guild.id'), nullable=False)
    server_id = db.Column(db.Integer, db.ForeignKey('game_server.id'), nullable=False)
    target_id = db.Column(db.Integer, db.ForeignKey('player.id'), nullable=False)
    placed_by = db.Column(db.String(20), nullable=False)  # Discord ID
    placed_by_name = db.Column(db.String(100), nullable=False)
    reason = db.Column(db.String(255), nullable=True)
    reward = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default='active', nullable=False)
    source = db.Column(db.String(20), default='player', nullable=False)  # player, auto
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    claimed_by = db.Column(db.String(20), nullable=True)  # Discord ID of claimer
    claimed_by_name = db.Column(db.String(100), nullable=True)
    claimed_at = db.Column(db.DateTime, nullable=True)
    
    def __repr__(self):
        return f"<Bounty {self.id}: {self.status}>"

class Kill(db.Model):
    """Kill events tracked from game logs"""
    id = db.Column(db.Integer, primary_key=True)
    guild_id = db.Column(db.Integer, db.ForeignKey('guild.id'), nullable=False)
    server_id = db.Column(db.Integer, db.ForeignKey('game_server.id'), nullable=False)
    kill_id = db.Column(db.String(100), nullable=False, unique=True)
    timestamp = db.Column(db.DateTime, nullable=False)
    killer_id = db.Column(db.Integer, db.ForeignKey('player.id'), nullable=False)
    killer_name = db.Column(db.String(100), nullable=False)
    victim_id = db.Column(db.Integer, db.ForeignKey('player.id'), nullable=False)
    victim_name = db.Column(db.String(100), nullable=False)
    weapon = db.Column(db.String(100), nullable=True)
    distance = db.Column(db.Float, nullable=True)
    console = db.Column(db.String(10), nullable=True)  # XSX, PS5, etc.
    
    # Relationships
    killer = db.relationship('Player', foreign_keys=[killer_id], backref='kills')
    victim = db.relationship('Player', foreign_keys=[victim_id], backref='deaths_by')
    
    def __repr__(self):
        return f"<Kill {self.killer_name} -> {self.victim_name}>"

class BotStatus(db.Model):
    """Tracks the Discord bot's status"""
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    is_online = db.Column(db.Boolean, default=False, nullable=False)
    uptime_seconds = db.Column(db.Integer, default=0, nullable=False)
    guild_count = db.Column(db.Integer, default=0, nullable=False)
    command_count = db.Column(db.Integer, default=0, nullable=False)
    error_count = db.Column(db.Integer, default=0, nullable=False)
    
    def __repr__(self):
        return f"<BotStatus {self.timestamp}: Online={self.is_online}>"

class EconomyTransaction(db.Model):
    """Tracks in-game currency transactions"""
    id = db.Column(db.Integer, primary_key=True)
    discord_id = db.Column(db.String(20), nullable=False)
    server_id = db.Column(db.Integer, db.ForeignKey('game_server.id'), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    type = db.Column(db.String(50), nullable=False)  # bounty_placed, bounty_claimed, etc.
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    description = db.Column(db.String(255), nullable=True)
    
    def __repr__(self):
        return f"<Transaction {self.discord_id}: {self.amount} ({self.type})>"