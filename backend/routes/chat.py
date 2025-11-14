# routes/chat.py

from flask import Blueprint, request, jsonify
from ai.hybrid_query_engine import HybridQueryEngine
import os

chat_bp = Blueprint('chat', __name__)

# Initialize engine
engine = HybridQueryEngine(
    db_connection_string=os.getenv('DATABASE_URL')
)

@chat_bp.route('/chat', methods=['POST'])
def chat():
    """
    Main chat endpoint
    
    Request:
    {
        "query": "Where did I spend most last month?",
        "user_id": 1
    }
    """
    data = request.json
    
    if not data.get('query'):
        return jsonify({'error': 'Query is required'}), 400
    
    user_id = data.get('user_id', 1)  # Get from auth in production
    
    try:
        result = engine.query(data['query'], user_id)
        
        return jsonify({
            'success': True,
            'data': result
        }), 200
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@chat_bp.route('/chat/suggestions', methods=['GET'])
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