from flask import Flask, render_template

app = Flask(__name__)

@app.route('/')
def index():
    """Display a simple web page explaining that this is a Discord bot"""
    return render_template('index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)