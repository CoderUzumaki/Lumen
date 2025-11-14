# routes/chat.py

from flask import Blueprint, request, jsonify
from ai.hybrid_query_engine import HybridQueryEngine
import os

chat_bp = Blueprint('chat', __name__)

# Initialize engine with SQLite database path
engine = HybridQueryEngine(
    db_path="instance/lumen.db"
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
    
    user_id = data.get('user_id', '1')  # Get from auth in production, default to '1' as string
    
    try:
        print(f"Processing query: {data['query']} for user: {user_id}")
        result = engine.query(data['query'], str(user_id))  # Ensure user_id is string
        
        return jsonify({
            'success': True,
            'data': result
        }), 200
    
    except Exception as e:
        print(f"Error in chat endpoint: {e}")
        import traceback
        traceback.print_exc()
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