"""Health check and documentation routes"""
from flask import Blueprint, jsonify

from models.database import db
from sqlalchemy import text

health_bp = Blueprint("health", __name__)


@health_bp.route("/health", methods=["GET"])
def health_check():
    """Health check with database connectivity."""
    payload = {"status": "healthy", "database": "ok"}
    try:
        db.session.execute(text("SELECT 1"))
        db.session.commit()
    except Exception:
        db.session.rollback()
        payload["status"] = "degraded"
        payload["database"] = "unavailable"
        return jsonify(payload), 503

    return jsonify(payload), 200


@health_bp.route("/", methods=["GET"])
def home():
    return (
        jsonify(
            {
                "name": "LUMEN Financial Intelligence API",
                "version": "1.0.0",
                "endpoints": {
                    "POST /extract": "Extract invoice from image/PDF",
                    "POST /extract-batch": "Extract all PDF pages and save",
                    "POST /chat": "Natural language financial queries",
                    "GET /chat/history": "Chat message history",
                    "GET /health": "Health check",
                    "GET /": "API documentation",
                },
            }
        ),
        200,
    )
