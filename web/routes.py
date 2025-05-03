"""
Routes for the Tower of Temptation PvP Statistics Discord Bot web dashboard.

This module provides:
1. Main routes for dashboard
2. API routes for data access
3. Authentication routes
4. Server management routes
5. Statistics routes
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union

from flask import Blueprint, render_template, request, redirect, url_for, jsonify, flash, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

from web.app import app, db
from web.models import User, ApiKey, WebhookConfig

# Import MongoDB models - we'll convert them to JSON for the frontend
from models.player import Player
from models.faction import Faction
from models.rivalry import Rivalry
from models.player_link import PlayerLink
from models.server_config import ServerConfig

# Set up logging
logger = logging.getLogger(__name__)

def register_routes(app):
    """Register all routes with the app"""
    
    # Set up login manager
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'login'
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Main routes
    @app.route('/')
    def index():
        """Dashboard home page"""
        return render_template('index.html')
    
    @app.route('/dashboard')
    @login_required
    def dashboard():
        """Main dashboard after login"""
        return render_template('dashboard.html')
    
    # Authentication routes
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        """User login page"""
        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')
            remember = 'remember' in request.form
            
            user = User.query.filter_by(username=username).first()
            
            if user and user.check_password(password):
                login_user(user, remember=remember)
                next_page = request.args.get('next')
                if not next_page or next_page.startswith('/'):
                    next_page = url_for('dashboard')
                return redirect(next_page)
            
            flash('Invalid username or password')
        
        return render_template('login.html')
    
    @app.route('/logout')
    @login_required
    def logout():
        """User logout"""
        logout_user()
        return redirect(url_for('index'))
    
    @app.route('/register', methods=['GET', 'POST'])
    def register():
        """User registration page"""
        if request.method == 'POST':
            username = request.form.get('username')
            email = request.form.get('email')
            password = request.form.get('password')
            
            # Check if user already exists
            existing_user = User.query.filter(
                (User.username == username) | (User.email == email)
            ).first()
            
            if existing_user:
                flash('Username or email already exists')
                return render_template('register.html')
            
            # Create new user
            user = User(
                username=username,
                email=email,
                is_admin=False
            )
            user.set_password(password)
            
            # If this is the first user, make them an admin
            if User.query.count() == 0:
                user.is_admin = True
            
            db.session.add(user)
            db.session.commit()
            
            flash('Registration successful, please login')
            return redirect(url_for('login'))
        
        return render_template('register.html')
    
    # Server routes
    @app.route('/servers')
    @login_required
    def servers():
        """Server management page"""
        return render_template('servers.html')
    
    @app.route('/servers/<server_id>')
    @login_required
    def server_details(server_id):
        """Server details page"""
        return render_template('server_details.html', server_id=server_id)
    
    # Player routes
    @app.route('/players')
    @login_required
    def players():
        """Player management page"""
        return render_template('players.html')
    
    @app.route('/players/<player_id>')
    @login_required
    def player_details(player_id):
        """Player details page"""
        return render_template('player_details.html', player_id=player_id)
    
    # Faction routes
    @app.route('/factions')
    @login_required
    def factions():
        """Faction management page"""
        return render_template('factions.html')
    
    @app.route('/factions/<faction_id>')
    @login_required
    def faction_details(faction_id):
        """Faction details page"""
        return render_template('faction_details.html', faction_id=faction_id)
    
    # API routes for the frontend
    @app.route('/api/players')
    @login_required
    def api_players():
        """Get players"""
        server_id = request.args.get('server_id')
        sort_by = request.args.get('sort_by', 'kills')
        limit = request.args.get('limit', 50, type=int)
        
        # This is async but we're running in Flask, so we'll use a synchronous approach
        # We'll use the DB directly instead of the models
        # This is just a stub for now
        return jsonify({
            'players': []
        })
    
    @app.route('/api/factions')
    @login_required
    def api_factions():
        """Get factions"""
        server_id = request.args.get('server_id')
        
        # This is just a stub for now
        return jsonify({
            'factions': []
        })
    
    @app.route('/api/rivalries')
    @login_required
    def api_rivalries():
        """Get rivalries"""
        server_id = request.args.get('server_id')
        
        # This is just a stub for now
        return jsonify({
            'rivalries': []
        })
    
    @app.route('/api/servers')
    @login_required
    def api_servers():
        """Get servers"""
        # This is just a stub for now
        return jsonify({
            'servers': []
        })
    
    @app.route('/api/stats')
    @login_required
    def api_stats():
        """Get bot statistics"""
        # This is just a stub for now
        return jsonify({
            'stats': {
                'total_servers': 0,
                'total_players': 0,
                'total_kills': 0,
                'total_factions': 0
            }
        })
    
    # Admin routes
    @app.route('/admin')
    @login_required
    def admin():
        """Admin panel"""
        if not current_user.is_admin:
            flash('Admin access required')
            return redirect(url_for('dashboard'))
        
        return render_template('admin.html')
    
    @app.route('/admin/users')
    @login_required
    def admin_users():
        """User management"""
        if not current_user.is_admin:
            flash('Admin access required')
            return redirect(url_for('dashboard'))
        
        users = User.query.all()
        return render_template('admin_users.html', users=users)
    
    @app.route('/admin/apikeys')
    @login_required
    def admin_apikeys():
        """API key management"""
        if not current_user.is_admin:
            flash('Admin access required')
            return redirect(url_for('dashboard'))
        
        apikeys = ApiKey.query.all()
        return render_template('admin_apikeys.html', apikeys=apikeys)
    
    @app.route('/admin/webhooks')
    @login_required
    def admin_webhooks():
        """Webhook management"""
        if not current_user.is_admin:
            flash('Admin access required')
            return redirect(url_for('dashboard'))
        
        webhooks = WebhookConfig.query.all()
        return render_template('admin_webhooks.html', webhooks=webhooks)
    
    # Error handlers
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('404.html'), 404
    
    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template('500.html'), 500