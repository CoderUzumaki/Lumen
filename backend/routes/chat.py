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
from utils.llm import LLMError

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


def _save_exchange(user_id: str, question: str, answer: str) -> None:
    for role, content in (("user", question), ("assistant", answer)):
        db.session.add(
            ChatMessage(
                id=str(uuid.uuid4()),
                user_id=user_id,
                role=role,
                content=content,
            )
        )
    db.session.commit()


# What the user sees for each provider failure. Operator detail (which key,
# which model) goes to the server log via LLMError, never to the client. None
# of these may be 401: the frontend treats 401 as "session expired" and signs
# the user out.
_LLM_ERROR_RESPONSES = {
    LLMError.RATE_LIMITED: (
        429,
        "llm_rate_limited",
        "Lumen's assistant is handling too many requests right now. Please try again in a minute.",
    ),
    LLMError.BAD_RESPONSE: (
        502,
        "llm_bad_response",
        "The assistant didn't return an answer. Please try again.",
    ),
}
_LLM_DEFAULT_RESPONSE = (
    503,
    "llm_unavailable",
    "Lumen's assistant is unavailable right now. Please try again shortly.",
)


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
        logger.info("Processing chat query for user=%s", user_id)
        result = engine.query(query, user_id)
    except LLMError as e:
        status, code, message = _LLM_ERROR_RESPONSES.get(e.kind, _LLM_DEFAULT_RESPONSE)
        logger.error("Chat failed for user=%s: LLM %s: %s", user_id, e.kind, e.detail)
        return api_error(message, status=status, code=code)
    except Exception as e:
        return api_error("Chat request failed", code="chat_failed", log=e)

    try:
        _save_exchange(user_id, query, result["response"])
    except Exception as e:
        # Losing history shouldn't cost the user their answer.
        db.session.rollback()
        logger.exception("Failed to save chat history for user=%s: %s", user_id, e)

    return jsonify({"success": True, "data": _sanitize_chat_result(result)}), 200


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
