"""Routes package initialization.

Note: there are two analytics blueprints with distinct URL prefixes:
  - analytics_bp     -> /analytics/*       (basic time-range summaries, utils.analytics_service)
  - ai_analytics_bp  -> /api/analytics/*   (AI-driven analysis, ai.analytics_orchestrator)
They are not duplicates; both are registered.
"""

# Import blueprints
from .ocr import ocr_bp
from .batch import batch_bp
from .health import health_bp
from .chat import chat_bp
from .ai_analytics import ai_analytics_bp
from .analytics import analytics_bp
from .database_query import database_query_bp
from .email_config import email_config_bp
from .auth import auth_bp


def register_routes(app):
    """Register all blueprints with the Flask app"""
    app.register_blueprint(ocr_bp)
    app.register_blueprint(batch_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(ai_analytics_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(database_query_bp)
    app.register_blueprint(email_config_bp)
    app.register_blueprint(auth_bp)
