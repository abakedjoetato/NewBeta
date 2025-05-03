import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import json

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
# create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "tower-of-temptation-dev-key")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)  # needed for url_for to generate with https

# configure the database, relative to the app instance folder
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
# initialize the app with the extension, flask-sqlalchemy >= 3.0.x
db.init_app(app)

# Import models after initializing db
from models.web_models import User, Server, BotStatistics, ServerStatistics, KillEvent, ConnectionEvent

@app.route('/')
def index():
    """Display a web page explaining that this is a Discord bot with admin panel"""
    stats = None
    try:
        stats = BotStatistics.query.order_by(BotStatistics.timestamp.desc()).first()
    except Exception as e:
        app.logger.error(f"Error fetching statistics: {e}")
    
    return render_template('index.html', stats=stats)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password.', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('You have been logged out.', 'success')
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        flash('Please login to access the dashboard.', 'warning')
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    if not user:
        session.pop('user_id', None)
        flash('User not found. Please login again.', 'warning')
        return redirect(url_for('login'))
    
    # Get bot statistics
    bot_stats = BotStatistics.query.order_by(BotStatistics.timestamp.desc()).first()
    
    # Get server statistics
    servers = Server.query.all()
    
    # Recent kill events for activity feed
    recent_kills = KillEvent.query.order_by(KillEvent.timestamp.desc()).limit(10).all()
    
    return render_template(
        'dashboard.html', 
        user=user, 
        bot_stats=bot_stats, 
        servers=servers, 
        recent_kills=recent_kills
    )

@app.route('/api/servers')
def api_servers():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    servers = Server.query.all()
    return jsonify({
        'servers': [
            {
                'id': server.id,
                'name': server.name,
                'server_id': server.server_id,
                'online_players': server.online_players,
                'status': server.status
            } for server in servers
        ]
    })

@app.route('/api/server/<int:server_id>/stats')
def api_server_stats(server_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    # Get the last 7 days of statistics for this server
    stats = ServerStatistics.query.filter_by(server_id=server_id).order_by(ServerStatistics.timestamp.desc()).limit(7).all()
    
    return jsonify({
        'stats': [
            {
                'timestamp': stat.timestamp.isoformat(),
                'kills': stat.kills,
                'deaths': stat.deaths,
                'connections': stat.connections,
                'unique_players': stat.unique_players
            } for stat in stats
        ]
    })

@app.route('/server/<int:server_id>')
def server_details(server_id):
    if 'user_id' not in session:
        flash('Please login to access server details.', 'warning')
        return redirect(url_for('login'))
    
    server = Server.query.get_or_404(server_id)
    
    # Get recent statistics
    stats = ServerStatistics.query.filter_by(server_id=server_id).order_by(ServerStatistics.timestamp.desc()).limit(7).all()
    
    # Get recent kills
    kills = KillEvent.query.filter_by(server_id=server_id).order_by(KillEvent.timestamp.desc()).limit(50).all()
    
    # Get recent connections
    connections = ConnectionEvent.query.filter_by(server_id=server_id).order_by(ConnectionEvent.timestamp.desc()).limit(50).all()
    
    return render_template(
        'server_details.html', 
        server=server, 
        stats=stats, 
        kills=kills, 
        connections=connections
    )

@app.route('/admin')
def admin():
    if 'user_id' not in session:
        flash('Please login to access admin features.', 'warning')
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    if not user or not user.is_admin:
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('dashboard'))
    
    users = User.query.all()
    return render_template('admin.html', users=users)

@app.route('/admin/create_user', methods=['POST'])
def create_user():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    user = User.query.get(session['user_id'])
    if not user or not user.is_admin:
        return jsonify({'error': 'Forbidden'}), 403
    
    username = request.form.get('username')
    password = request.form.get('password')
    email = request.form.get('email')
    is_admin = True if request.form.get('is_admin') == 'on' else False
    
    if not username or not password or not email:
        flash('All fields are required.', 'danger')
        return redirect(url_for('admin'))
    
    # Check if username already exists
    if User.query.filter_by(username=username).first():
        flash('Username already exists.', 'danger')
        return redirect(url_for('admin'))
    
    # Create new user
    new_user = User(
        username=username,
        email=email,
        password_hash=generate_password_hash(password),
        is_admin=is_admin
    )
    
    db.session.add(new_user)
    db.session.commit()
    
    flash(f'User {username} created successfully.', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    if 'user_id' not in session:
        flash('Please login to perform this action.', 'warning')
        return redirect(url_for('login'))
    
    current_user = User.query.get(session['user_id'])
    if not current_user or not current_user.is_admin:
        flash('You do not have permission to perform this action.', 'danger')
        return redirect(url_for('dashboard'))
    
    # Cannot delete yourself
    if current_user.id == user_id:
        flash('You cannot delete your own account.', 'danger')
        return redirect(url_for('admin'))
    
    user_to_delete = User.query.get_or_404(user_id)
    db.session.delete(user_to_delete)
    db.session.commit()
    
    flash(f'User {user_to_delete.username} deleted successfully.', 'success')
    return redirect(url_for('admin'))

# Error handlers
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500

with app.app_context():
    # Import models here
    from models.web_models import User, Server, BotStatistics, ServerStatistics, KillEvent, ConnectionEvent
    
    # Create all tables
    db.create_all()
    
    # Check if admin user exists, create one if not
    admin_user = User.query.filter_by(username='admin').first()
    if not admin_user:
        admin_password = os.environ.get('ADMIN_INITIAL_PASSWORD', 'tower-admin-password')
        admin_user = User(
            username='admin',
            email='admin@toweroftemptation.com',
            password_hash=generate_password_hash(admin_password),
            is_admin=True
        )
        db.session.add(admin_user)
        db.session.commit()
        app.logger.info("Created default admin user")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)