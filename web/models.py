"""
Database models for the Tower of Temptation PvP Statistics Bot web dashboard.

This module provides:
1. User model for authentication
2. API keys for external access
3. Webhook configurations
"""
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any, Union

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from web.app import db

class User(UserMixin, db.Model):
    """User model for web dashboard authentication"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    api_keys = db.relationship('ApiKey', backref='user', lazy=True, cascade="all, delete-orphan")
    
    def set_password(self, password: str) -> None:
        """Set user password"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password: str) -> bool:
        """Check if password is correct"""
        return check_password_hash(self.password_hash, password)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert user to dictionary"""
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'is_admin': self.is_admin,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

class ApiKey(db.Model):
    """API key model for external access to the API"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    key = db.Column(db.String(64), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_used_at = db.Column(db.DateTime)
    expires_at = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    
    @classmethod
    def generate_key(cls) -> str:
        """Generate a new API key"""
        return str(uuid.uuid4())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert API key to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'key': self.key,
            'user_id': self.user_id,
            'created_at': self.created_at.isoformat(),
            'last_used_at': self.last_used_at.isoformat() if self.last_used_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'is_active': self.is_active
        }

class WebhookConfig(db.Model):
    """Webhook configuration for Discord event notifications"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    url = db.Column(db.String(255), nullable=False)
    server_id = db.Column(db.String(64), nullable=False)
    events = db.Column(db.String(255), nullable=False)  # Comma-separated event types
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    def get_events(self) -> List[str]:
        """Get list of events"""
        return self.events.split(',')
    
    def set_events(self, events: List[str]) -> None:
        """Set events from list"""
        self.events = ','.join(events)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert webhook configuration to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'url': self.url,
            'server_id': self.server_id,
            'events': self.get_events(),
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'is_active': self.is_active
        }