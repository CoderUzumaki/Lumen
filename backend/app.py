"""LUMEN Financial Intelligence API - Main Application Entry Point"""
from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv
from routes import register_routes
from utils.openrouter import get_api_config
from models.database import init_db

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Initialize database
init_db(app)

# Register all routes
register_routes(app)




if __name__ == '__main__':
    # Get API configuration
    config = get_api_config()
    
    # Debug: Print API key status (first few chars only for security)
    if config['api_key']:
        print(f"✅ OpenRouter API Key loaded: {config['api_key'][:15]}...")
    else:
        print("❌ OpenRouter API Key NOT loaded!")
    print(f"✅ Using model: {config['model']}")
    
    print("\n🚀 Starting LUMEN Financial Intelligence API...")
    print("📝 Endpoints available:")
    print("   GET / - API documentation")
    print("   POST /extract - Extract invoice from image/PDF and store to DB (requires user_id)")
    print("   POST /extract-batch - Multi-page PDF extraction")
    print("   GET /health - Health check")
    
    app.run(debug=True, host='0.0.0.0', port=5000)