"""
Flask API Routes for AI Analytics System
"""

from flask import Blueprint, g, request, jsonify
from ai.analytics_orchestrator import AnalyticsOrchestrator
from models.database import db
from utils.auth import require_auth
from utils.errors import api_error
from utils.limiter import limiter

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
@limiter.limit("5 per minute")
@require_auth
def run_analysis():
    """
    Trigger comprehensive analysis for the authenticated user.

    Request Body:
    {
        "include_fraud": true,
        "include_forecast": true,
        "include_risk": true,
        "use_llm": true
    }
    """
    try:
        init_analytics()  # Ensure orchestrator is initialized

        data = request.json or {}
        user_id = g.user_id
        
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
        return api_error("Analysis failed", code="analysis_failed", log=e)


@ai_analytics_bp.route('/dashboard', methods=['GET'])
@require_auth
def get_dashboard():
    """Get quick dashboard summary for the authenticated user."""
    try:
        init_analytics()  # Ensure orchestrator is initialized

        user_id = g.user_id

        summary = orchestrator.get_dashboard_summary(user_id)
        
        return jsonify({
            'success': True,
            'data': summary
        }), 200
    
    except Exception as e:
        return api_error("Could not load dashboard", code="dashboard_failed", log=e)
@require_auth
def get_reminders():
    """Get smart reminders for the authenticated user.

    Query Params:
    - days_ahead: Look ahead days (default: 7)
    """
    try:
        init_analytics()  # Ensure orchestrator is initialized

        user_id = g.user_id
        days_ahead = request.args.get('days_ahead', 7, type=int)

        reminders = orchestrator.get_reminders(user_id, days_ahead)
        
        return jsonify({
            'success': True,
            'reminders': reminders,
            'count': len(reminders)
        }), 200
    
    except Exception as e:
        return api_error("Could not load reminders", code="reminders_failed", log=e)
@require_auth
def get_anomalies():
    """Get detected anomalies for the authenticated user.

    Query Params:
    - risk_level: Filter by risk level (optional: HIGH, MEDIUM, LOW)
    """
    try:
        init_analytics()  # Ensure orchestrator is initialized

        user_id = g.user_id
        risk_level = request.args.get('risk_level', None)

        anomalies = orchestrator.get_anomalies(user_id, risk_level)
        
        return jsonify({
            'success': True,
            'anomalies': anomalies,
            'count': len(anomalies)
        }), 200
    
    except Exception as e:
        return api_error("Could not load anomalies", code="anomalies_failed", log=e)
@require_auth
def get_forecast():
    """Get spending forecast for the authenticated user.

    Query Params:
    - days_ahead: Forecast period (default: 30)
    """
    try:
        init_analytics()  # Ensure orchestrator is initialized

        user_id = g.user_id
        days_ahead = request.args.get('days_ahead', 30, type=int)

        forecast = orchestrator.get_forecast(user_id, days_ahead)
        
        return jsonify({
            'success': forecast.get('success', True),
            'forecast': forecast
        }), 200
    
    except Exception as e:
        return api_error("Could not load forecast", code="forecast_failed", log=e)
@require_auth
def get_risk_score():
    """Get financial health risk score for the authenticated user."""
    try:
        init_analytics()  # Ensure orchestrator is initialized

        user_id = g.user_id

        risk_score = orchestrator.get_risk_score(user_id)
        
        return jsonify({
            'success': True,
            'risk_score': risk_score
        }), 200
    
    except Exception as e:
        return api_error("Could not load risk score", code="risk_score_failed", log=e)
@require_auth
def get_insights():
    """Get all insights for the authenticated user.

    Query Params:
    - type: Filter by type (optional: reminder, anomaly, forecast, risk)
    - severity: Filter by severity (optional: info, low, medium, high, critical)
    - limit: Number of results (default: 20)
    """
    try:
        user_id = g.user_id
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
        return api_error("Could not load insights", code="insights_failed", log=e)
@require_auth
def mark_insight_read(insight_id):
    """Mark an insight as read. Only succeeds if the insight belongs to the
    authenticated user — otherwise the UPDATE no-ops (0 rows affected) and we
    return 404 so a malicious caller can't probe for other users' insight ids."""
    try:
        result = db.session.execute(db.text("""
            UPDATE insights
            SET is_read = 1
            WHERE id = :insight_id AND user_id = :user_id
        """), {'insight_id': insight_id, 'user_id': g.user_id})

        if result.rowcount == 0:
            db.session.rollback()
            return jsonify({'success': False, 'error': 'not_found'}), 404

        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Insight marked as read'
        }), 200
    
    except Exception as e:
        return api_error("Could not update insight", code="insight_update_failed", log=e)
@require_auth
def get_patterns():
    """Get detected spending patterns for the authenticated user.

    Query Params:
    - pattern_type: Filter by type (optional: recurring, day_of_month)
    """
    try:
        user_id = g.user_id
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
        return api_error("Could not load patterns", code="patterns_failed", log=e)
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy'}), 200