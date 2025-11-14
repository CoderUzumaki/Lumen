"""Routes package initialization"""
from flask import Blueprint

# Import blueprints
from .ocr import ocr_bp
from .batch import batch_bp
from .health import health_bp
from .chat import chat_bp


def register_routes(app):
    """Register all blueprints with the Flask app"""
    app.register_blueprint(ocr_bp)
    app.register_blueprint(batch_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(chat_bp)
