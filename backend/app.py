from flask import Flask, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Configure CORS
CORS(app, resources={
    r"/api/*": {
        "origins": os.getenv("FRONTEND_URL", "http://localhost:3000"),
        "methods": ["GET", "POST", "PUT", "DELETE"],
        "allow_headers": ["Content-Type"]
    }
})

# Import routes
from routes import api_routes

# Register blueprints
app.register_blueprint(api_routes.bp)

@app.route('/')
def home():
    return jsonify({
        "status": "running",
        "message": "Lumen Backend API"
    })

if __name__ == '__main__':
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_ENV", "development") == "development"
    app.run(host='0.0.0.0', port=port, debug=debug)
