"""
SQL database models for the Tower of Temptation PvP Statistics Bot Web App

These models are separate from the MongoDB models used by the Discord bot.
They are used exclusively for web app functionality.
"""
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from app import db

class User(UserMixin, db.Model):
    """Web app user model"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    is_admin = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    last_login = db.Column(db.DateTime, default=None)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, password):
        """Set hashed password"""
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        """Check password"""
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.username}>'


class WebConfig(db.Model):
    """Web app configuration model"""
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(64), unique=True, nullable=False)
    value = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<WebConfig {self.key}>'


class ApiToken(db.Model):
    """API token model"""
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(64), unique=True, nullable=False)
    description = db.Column(db.String(256))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    # Relationships
    created_by = db.relationship('User', backref=db.backref('api_tokens', lazy=True))
    
    def __repr__(self):
        return f'<ApiToken {self.description}>'