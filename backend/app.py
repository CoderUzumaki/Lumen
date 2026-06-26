"""LUMEN Financial Intelligence API - Main Application Entry Point"""
import logging

from flask import Flask
from flask_cors import CORS

# config.py calls load_dotenv() at import time, so importing Config first
# guarantees env vars are loaded before any other module reads them.
from config import Config
from utils.logging_config import configure_logging, mask_secret

configure_logging()
logger = logging.getLogger(__name__)

# Fail fast on missing required configuration (e.g. OPENROUTER_API_KEY).
Config.validate()

from routes import register_routes
from utils.openrouter import get_api_config
from models.database import init_db
from utils.scheduler import scheduler

# Initialize Flask app
app = Flask(__name__)
app.config["SECRET_KEY"] = Config.SECRET_KEY

# CORS: restrict to the configured allowlist. Defaults to FRONTEND_URL; in
# production set ALLOWED_ORIGINS to a comma-separated list of permitted
# origins. `supports_credentials=True` lets the browser send cookies / the
# Authorization header on cross-origin requests once auth lands (Phase 2).
CORS(
    app,
    origins=Config.ALLOWED_ORIGINS,
    supports_credentials=True,
)
logger.info("CORS allowlist: %s", Config.ALLOWED_ORIGINS)

# Initialize database
init_db(app)

# Register all routes
register_routes(app)

# Configure scheduler with app
scheduler.app = app




if __name__ == '__main__':
    # Get API configuration
    config = get_api_config()
    
    # Log key status without exposing the secret (last 4 chars only).
    if config['api_key']:
        logger.info("OpenRouter API key loaded (%s)", mask_secret(config['api_key']))
    else:
        logger.error("OpenRouter API key NOT loaded - LLM features will fail")
    logger.info("Using model: %s", config['model'])
    
    logger.info("\n🚀 Starting LUMEN Financial Intelligence API...")
    logger.info("📝 Endpoints available:")
    logger.info("   GET / - API documentation")
    logger.info("   POST /extract - Extract invoice from image/PDF and store to DB (requires user_id)")
    logger.info("   POST /extract-batch - Multi-page PDF extraction")
    logger.info("   POST /chat - Natural language query interface (requires user_id)")
    logger.info("   GET /chat/suggestions - Get sample query suggestions")
    logger.info("   GET /analytics/summary?user_id=X - Get spending analytics")
    logger.info("   GET /health - Health check")
    logger.info("   📧 Email Polling: /api/v1/email-config/* - Configure automatic invoice polling")
    
    # Start email polling scheduler
    scheduler.start()
    
    try:
        app.run(debug=Config.DEBUG, host=Config.HOST, port=Config.PORT)
    finally:
        # Cleanup on shutdown
        scheduler.stop()