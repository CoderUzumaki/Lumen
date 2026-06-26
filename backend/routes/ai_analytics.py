"""
Flask API Routes for AI Analytics System
"""

from flask import Blueprint, request, jsonify
from ai.analytics_orchestrator import AnalyticsOrchestrator
from models.database import db

# Create blueprint
ai_analytics_bp = Blueprint('ai_analytics', __name__, url_prefix='/api/analytics')

# Initialize orchestrator (will be initialized within app context)
orchestrator = None

def init_analytics():
    """Initialize analytics orchestrator within Flask app context"""
    global orchestrator
    if orchestrator is None:
        orchestrator = AnalyticsOrchestrator()

@ai_analytics_bp.route('/analyze', methods=['POST'])
def run_analysis():
    """
    Trigger comprehensive analysis for user
    
    Request Body:
    {
        "user_id": 1,
        "include_fraud": true,
        "include_forecast": true,
        "include_risk": true,
        "use_llm": true
    }
    
    Response:
    {
        "success": true,
        "results": {
            "patterns": {...},
            "fraud_detection": {...},
            "forecast": {...},
            "risk_assessment": {...}
        },
        "insights": [...]
    }
    """
    try:
        init_analytics()  # Ensure orchestrator is initialized
        
        data = request.json or {}
        user_id = data.get('user_id', 1)  # Get from auth in production
        
        # Run analysis
        results = orchestrator.run_complete_analysis(
            user_id=user_id,
            include_fraud_detection=data.get('include_fraud', True),
            include_forecasting=data.get('include_forecast', True),
            include_risk_assessment=data.get('include_risk', True),
            use_llm_reasoning=data.get('use_llm', False)  # Default False for speed
        )
        
        # Generate insights
        insights = orchestrator.generate_insights_from_analysis(results)
        
        # Save insights to DB
        for insight in insights:
            orchestrator.save_insight(user_id, insight)
        
        return jsonify({
            'success': True,
            'results': results,
            'insights': insights
        }), 200
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@ai_analytics_bp.route('/dashboard', methods=['GET'])
def get_dashboard():
    """
    Get quick dashboard summary
    
    Query Params:
    - user_id: User ID (default: 1)
    
    Response:
    {
        "risk_score": 45,
        "risk_level": "MEDIUM",
        "health_status": "NEEDS ATTENTION",
        "active_reminders": 3,
        "reminders": [...],
        "high_risk_anomalies": 1,
        "patterns_detected": 5,
        "top_recommendations": [...]
    }
    """
    try:
        init_analytics()  # Ensure orchestrator is initialized
        
        user_id = request.args.get('user_id', 1, type=int)
        
        summary = orchestrator.get_dashboard_summary(user_id)
        
        return jsonify({
            'success': True,
            'data': summary
        }), 200
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@ai_analytics_bp.route('/reminders', methods=['GET'])
def get_reminders():
    """
    Get smart reminders
    
    Query Params:
    - user_id: User ID (default: 1)
    - days_ahead: Look ahead days (default: 7)
    
    Response:
    {
        "success": true,
        "reminders": [
            {
                "title": "Upcoming: Netflix",
                "description": "Your Netflix payment is typically due in 2 days...",
                "predicted_date": "2024-11-16",
                "days_until": 2,
                "confidence_score": 0.95
            }
        ]
    }
    """
    try:
        init_analytics()  # Ensure orchestrator is initialized
        
        user_id = request.args.get('user_id', 1, type=int)
        days_ahead = request.args.get('days_ahead', 7, type=int)
        
        reminders = orchestrator.get_reminders(user_id, days_ahead)
        
        return jsonify({
            'success': True,
            'reminders': reminders,
            'count': len(reminders)
        }), 200
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@ai_analytics_bp.route('/anomalies', methods=['GET'])
def get_anomalies():
    """
    Get detected anomalies
    
    Query Params:
    - user_id: User ID (default: 1)
    - risk_level: Filter by risk level (optional: HIGH, MEDIUM, LOW)
    
    Response:
    {
        "success": true,
        "anomalies": [
            {
                "transaction_id": 123,
                "vendor_name": "XYZ Store",
                "amount": 5000,
                "risk_level": "HIGH",
                "explanation": "Amount is 5x your average transaction..."
            }
        ]
    }
    """
    try:
        init_analytics()  # Ensure orchestrator is initialized
        
        user_id = request.args.get('user_id', 1, type=int)
        risk_level = request.args.get('risk_level', None)
        
        anomalies = orchestrator.get_anomalies(user_id, risk_level)
        
        return jsonify({
            'success': True,
            'anomalies': anomalies,
            'count': len(anomalies)
        }), 200
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@ai_analytics_bp.route('/forecast', methods=['GET'])
def get_forecast():
    """
    Get spending forecast
    
    Query Params:
    - user_id: User ID (default: 1)
    - days_ahead: Forecast period (default: 30)
    
    Response:
    {
        "success": true,
        "forecast": {
            "total_predicted": 15000,
            "trend": "increasing",
            "dates": [...],
            "values": [...],
            "category_forecast": [...]
        }
    }
    """
    try:
        init_analytics()  # Ensure orchestrator is initialized
        
        user_id = request.args.get('user_id', 1, type=int)
        days_ahead = request.args.get('days_ahead', 30, type=int)
        
        forecast = orchestrator.get_forecast(user_id, days_ahead)
        
        return jsonify({
            'success': forecast.get('success', True),
            'forecast': forecast
        }), 200
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@ai_analytics_bp.route('/risk-score', methods=['GET'])
def get_risk_score():
    """
    Get financial health risk score
    
    Query Params:
    - user_id: User ID (default: 1)
    
    Response:
    {
        "success": true,
        "risk_score": {
            "overall_score": 45,
            "risk_level": "MEDIUM",
            "health_status": "NEEDS ATTENTION",
            "factors": [...],
            "recommendations": [...]
        }
    }
    """
    try:
        init_analytics()  # Ensure orchestrator is initialized
        
        user_id = request.args.get('user_id', 1, type=int)
        
        risk_score = orchestrator.get_risk_score(user_id)
        
        return jsonify({
            'success': True,
            'risk_score': risk_score
        }), 200
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@ai_analytics_bp.route('/insights', methods=['GET'])
def get_insights():
    """
    Get all insights for user
    
    Query Params:
    - user_id: User ID (default: 1)
    - type: Filter by type (optional: reminder, anomaly, forecast, risk)
    - severity: Filter by severity (optional: info, low, medium, high, critical)
    - limit: Number of results (default: 20)
    
    Response:
    {
        "success": true,
        "insights": [...]
    }
    """
    try:
        user_id = request.args.get('user_id', 1, type=int)
        insight_type = request.args.get('type', None)
        severity = request.args.get('severity', None)
        limit = request.args.get('limit', 20, type=int)
        
        query_text = "SELECT * FROM insights WHERE user_id = :user_id"
        params = {'user_id': user_id}
        
        if insight_type:
            query_text += " AND insight_type = :insight_type"
            params['insight_type'] = insight_type
        
        if severity:
            query_text += " AND severity = :severity"
            params['severity'] = severity
        
        query_text += " ORDER BY created_at DESC LIMIT :limit"
        params['limit'] = limit
        
        result = db.session.execute(db.text(query_text), params)
        insights = [dict(row._mapping) for row in result]
        
        return jsonify({
            'success': True,
            'insights': insights,
            'count': len(insights)
        }), 200
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@ai_analytics_bp.route('/insights/<int:insight_id>/read', methods=['POST'])
def mark_insight_read(insight_id):
    """Mark an insight as read"""
    try:
        db.session.execute(db.text("""
            UPDATE insights
            SET is_read = 1
            WHERE id = :insight_id
        """), {'insight_id': insight_id})
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Insight marked as read'
        }), 200
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@ai_analytics_bp.route('/patterns', methods=['GET'])
def get_patterns():
    """
    Get detected spending patterns
    
    Query Params:
    - user_id: User ID (default: 1)
    - pattern_type: Filter by type (optional: recurring, day_of_month)
    
    Response:
    {
        "success": true,
        "patterns": [...]
    }
    """
    try:
        user_id = request.args.get('user_id', 1, type=int)
        pattern_type = request.args.get('pattern_type', None)
        
        query_text = "SELECT * FROM spending_patterns WHERE user_id = :user_id AND is_active = 1"
        params = {'user_id': user_id}
        
        if pattern_type:
            query_text += " AND pattern_type = :pattern_type"
            params['pattern_type'] = pattern_type
        
        query_text += " ORDER BY confidence_score DESC"
        
        result = db.session.execute(db.text(query_text), params)
        patterns = [dict(row._mapping) for row in result]
        
        return jsonify({
            'success': True,
            'patterns': patterns,
            'count': len(patterns)
        }), 200
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@ai_analytics_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'analytics',
        'agents': {
            'pattern_detection': 'ready',
            'fraud_detection': 'ready',
            'forecasting': 'ready',
            'risk_assessment': 'ready'
        }
    }), 200