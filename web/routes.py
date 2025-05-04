"""
Routes for the Flask web app
"""
from flask import render_template, jsonify, request, redirect, url_for
from web.models import User, BotStat, ServerStat

def register_routes(app):
    """Register routes with the Flask app"""
    
    @app.route('/api/stats/bot')
    def bot_stats():
        """Get the latest bot statistics"""
        stat = BotStat.query.order_by(BotStat.timestamp.desc()).first()
        if not stat:
            return jsonify({
                "error": "No bot statistics available"
            }), 404
        
        return jsonify({
            "guild_count": stat.guild_count,
            "user_count": stat.user_count,
            "command_count": stat.command_count,
            "uptime": stat.uptime,
            "cpu_usage": stat.cpu_usage,
            "memory_usage": stat.memory_usage,
            "timestamp": stat.timestamp.isoformat()
        })
    
    @app.route('/api/stats/server/<server_id>')
    def server_stats(server_id):
        """Get the latest statistics for a specific server"""
        stat = ServerStat.query.filter_by(server_id=server_id).order_by(ServerStat.timestamp.desc()).first()
        if not stat:
            return jsonify({
                "error": f"No statistics available for server {server_id}"
            }), 404
        
        return jsonify({
            "server_id": stat.server_id,
            "guild_id": stat.guild_id,
            "player_count": stat.player_count,
            "kill_count": stat.kill_count,
            "death_count": stat.death_count,
            "suicide_count": stat.suicide_count,
            "faction_count": stat.faction_count,
            "timestamp": stat.timestamp.isoformat()
        })
    
    @app.route('/api/stats/factions/<server_id>')
    def faction_stats(server_id):
        """Get faction statistics for a specific server
        
        This endpoint connects to the MongoDB database to retrieve
        faction information that is stored by the Discord bot.
        """
        # This would normally connect to MongoDB, but for now we'll return a placeholder
        return jsonify({
            "message": "Faction statistics API endpoint is available",
            "server_id": server_id,
            "note": "This endpoint requires connection to the MongoDB database used by the Discord bot"
        })
    
    @app.route('/api/stats/rivalries/<server_id>')
    def rivalry_stats(server_id):
        """Get rivalry statistics for a specific server
        
        This endpoint connects to the MongoDB database to retrieve
        rivalry information that is stored by the Discord bot.
        """
        # This would normally connect to MongoDB, but for now we'll return a placeholder
        return jsonify({
            "message": "Rivalry statistics API endpoint is available",
            "server_id": server_id,
            "note": "This endpoint requires connection to the MongoDB database used by the Discord bot"
        })
        
    @app.route('/api/stats/playerlinks/<server_id>')
    def player_link_stats(server_id):
        """Get player link statistics for a specific server
        
        This endpoint connects to the MongoDB database to retrieve
        player link information that is stored by the Discord bot.
        """
        # This would normally connect to MongoDB, but for now we'll return a placeholder
        return jsonify({
            "message": "Player link statistics API endpoint is available",
            "server_id": server_id,
            "note": "This endpoint requires connection to the MongoDB database used by the Discord bot"
        })