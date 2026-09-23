# routes/chat.py
import logging
import uuid

from flask import Blueprint, g, request, jsonify

from ai.hybrid_query_engine import HybridQueryEngine
from config import Config
from models import ChatMessage
from models.database import db
from utils.auth import require_auth
from utils.errors import api_error
from utils.limiter import limiter

logger = logging.getLogger(__name__)

chat_bp = Blueprint("chat", __name__)

engine = HybridQueryEngine(db_path=str(Config.DATABASE_PATH))


def _sanitize_chat_result(result: dict) -> dict:
    safe = {
        "query": result.get("query"),
        "query_type": result.get("query_type"),
        "response": result.get("response"),
    }
    raw = result.get("raw_results") or {}
    if raw.get("success") is False:
        safe["data_error"] = raw.get("error", "Query failed")
    elif "data" in raw:
        safe["row_count"] = raw.get("row_count", len(raw.get("data", [])))
    return safe


def _save_message(user_id: str, role: str, content: str) -> None:
    db.session.add(
        ChatMessage(
            id=str(uuid.uuid4()),
            user_id=user_id,
            role=role,
            content=content,
        )
    )
    db.session.commit()


@chat_bp.route("/chat", methods=["POST"])
@limiter.limit("30 per minute")
@require_auth
def chat():
    """Natural language query interface. Identity from JWT only."""
    data = request.json or {}
    query = (data.get("query") or "").strip()

    if not query:
        return jsonify({"error": "Query is required"}), 400

    user_id = str(g.user_id)

    try:
        _save_message(user_id, "user", query)
        logger.info("Processing chat query for user=%s", user_id)
        result = engine.query(query, user_id)
        response_text = result.get("response") or ""
        if response_text:
            _save_message(user_id, "assistant", response_text)
        return jsonify({"success": True, "data": _sanitize_chat_result(result)}), 200
    except Exception as e:
        db.session.rollback()
        return api_error("Chat request failed", code="chat_failed", log=e)


@chat_bp.route("/chat/history", methods=["GET"])
@require_auth
def chat_history():
    """Return recent chat messages for the authenticated user."""
    limit = min(int(request.args.get("limit", 50)), 200)
    user_id = str(g.user_id)

    rows = (
        ChatMessage.query.filter_by(user_id=user_id)
        .order_by(ChatMessage.created_at.asc())
        .limit(limit)
        .all()
    )

    return jsonify(
        {
            "success": True,
            "messages": [
                {
                    "id": row.id,
                    "role": row.role,
                    "content": row.content,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                }
                for row in rows
            ],
        }
    ), 200


@chat_bp.route("/chat/history", methods=["DELETE"])
@require_auth
def clear_chat_history():
    """Clear chat history for the authenticated user."""
    user_id = str(g.user_id)
    ChatMessage.query.filter_by(user_id=user_id).delete()
    db.session.commit()
    return jsonify({"success": True, "message": "Chat history cleared"}), 200


@chat_bp.route("/chat/suggestions", methods=["GET"])
@require_auth
def get_suggestions():
    suggestions = [
        "Where did I spend the most last month?",
        "Show me all grocery purchases",
        "What's my average restaurant spending?",
        "Find transactions above ₹1000",
        "Show me coffee-related purchases",
        "What's my spending trend over the last 3 months?",
        "Which category is the cheapest?",
    ]
    return jsonify({"suggestions": suggestions}), 200
