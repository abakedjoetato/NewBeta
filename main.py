"""
Powered By Discord.gg/EmeraldServers Discord Bot
Main file that handles both the Discord bot and the web app
"""
import os
import threading
import subprocess
from flask import Flask, render_template

# Create the Flask app to satisfy Replit's hosting requirements
app = Flask(__name__)

@app.route('/')
def index():
    """Display a simple web page explaining that this is a Discord bot"""
    return render_template('index.html')

# Start the Discord bot in a separate thread
def start_discord_bot():
    """Start the Discord bot as a separate process"""
    subprocess.call(["python", "clone_bot.py"])

if __name__ == "__main__":
    # Start the Discord bot in a background thread
    bot_thread = threading.Thread(target=start_discord_bot)
    bot_thread.daemon = True
    bot_thread.start()
    
    # Start the Flask app 
    app.run(host='0.0.0.0', port=5000)
