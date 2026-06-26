# routes/chat.py
import logging

from flask import Blueprint, g, request, jsonify

from ai.hybrid_query_engine import HybridQueryEngine
from config import Config
from utils.auth import require_auth

logger = logging.getLogger(__name__)

chat_bp = Blueprint('chat', __name__)

# Initialize engine with the configured SQLite database path.
engine = HybridQueryEngine(db_path=str(Config.DATABASE_PATH))


@chat_bp.route('/chat', methods=['POST'])
@require_auth
def chat():
    """
    Main chat endpoint. Identity comes from the JWT (g.user_id); the request
    body must NOT include a user_id (any value is ignored).

    Request:
    { "query": "Where did I spend most last month?" }
    """
    data = request.json or {}

    if not data.get('query'):
        return jsonify({'error': 'Query is required'}), 400

    user_id = g.user_id

    try:
        logger.info("Processing chat query for user=%s", user_id)
        result = engine.query(data['query'], str(user_id))

        return jsonify({
            'success': True,
            'data': result
        }), 200

    except Exception as e:
        logger.exception("Error in chat endpoint: %s", e)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@chat_bp.route('/chat/suggestions', methods=['GET'])
@require_auth
def get_suggestions():
    """Get sample questions"""
    suggestions = [
        "Where did I spend the most last month?",
        "Show me all grocery purchases",
        "What's my average restaurant spending?",
        "Find transactions above ₹1000",
        "Show me coffee-related purchases",
        "What's my spending trend over the last 3 months?",
        "Which category is the cheapest?"
    ]
    
    return jsonify({'suggestions': suggestions}), 200