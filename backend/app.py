"""LUMEN Financial Intelligence API - Main Application Entry Point"""
import logging

from flask import Flask, jsonify
from flask_cors import CORS
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge

from config import Config
from utils.logging_config import configure_logging, mask_secret
from utils.limiter import limiter
from utils.errors import api_error

configure_logging()
logger = logging.getLogger(__name__)

Config.validate()

from routes import register_routes
from utils.openrouter import get_api_config
from models.database import init_db
from utils.scheduler import scheduler

app = Flask(__name__)
app.config["SECRET_KEY"] = Config.SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = Config.MAX_UPLOAD_BYTES

CORS(
    app,
    origins=Config.ALLOWED_ORIGINS,
    supports_credentials=True,
)
logger.info("CORS allowlist: %s", Config.ALLOWED_ORIGINS)

limiter.init_app(app)

init_db(app)
register_routes(app)

scheduler.app = app


@app.errorhandler(RequestEntityTooLarge)
def handle_file_too_large(_e):
    return api_error("File too large", status=413, code="payload_too_large")


@app.errorhandler(HTTPException)
def handle_http_exception(e: HTTPException):
    return jsonify({"success": False, "error": e.description, "code": "http_error"}), e.code


@app.errorhandler(Exception)
def handle_unexpected_exception(e: Exception):
    return api_error("An internal error occurred", code="internal_error", log=e)


if __name__ == "__main__":
    config = get_api_config()

    if config["api_key"]:
        logger.info("OpenRouter API key loaded (%s)", mask_secret(config["api_key"]))
    else:
        logger.error("OpenRouter API key NOT loaded - LLM features will fail")
    logger.info("Using model: %s", config["model"])

    logger.info("Starting LUMEN Financial Intelligence API...")
    scheduler.start()

    try:
        app.run(debug=Config.DEBUG, host=Config.HOST, port=Config.PORT)
    finally:
        scheduler.stop()
