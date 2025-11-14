"""
Analytics Orchestrator - Coordinates all AI agents and analysis tasks
"""

from pattern_detection import PatternDetectionAgent
from anomaly_detection import FraudDetectionAgent
from forecasting_agent import ForecastingAgent
from risk_assessment import RiskAssessmentEngine
from typing import Dict, Any,List
import json
from datetime import datetime

class AnalyticsOrchestrator:
    """Coordinates all analytics agents and provides unified interface"""
    
    def __init__(self, db_path: str):
        """
        Initialize analytics orchestrator
        
        Args:
            db_path: Path to SQLite database
        """
        print("🚀 Initializing Analytics Orchestrator...")
        
        self.db_path = db_path
        
        # Initialize all agents
        self.pattern_agent = PatternDetectionAgent(db_path)
        print("   ✅ Pattern Detection Agent ready")
        
        self.fraud_agent = FraudDetectionAgent(db_path)
        print("   ✅ Fraud Detection Agent ready")
        
        self.forecast_agent = ForecastingAgent(db_path)
        print("   ✅ Forecasting Agent ready")
        
        self.risk_engine = RiskAssessmentEngine(db_path)
        print("   ✅ Risk Assessment Engine ready")
        
        print("✅ Analytics Orchestrator initialized!\n")
    
    def run_complete_analysis(self, 
                             user_id: int,
                             include_fraud_detection: bool = True,
                             include_forecasting: bool = True,
                             include_risk_assessment: bool = True,
                             use_llm_reasoning: bool = True) -> Dict[str, Any]:
        """
        Run comprehensive analysis for a user
        
        Args:
            user_id: User ID to analyze
            include_fraud_detection: Run fraud detection (slower with ML)
            include_forecasting: Generate spending forecasts
            include_risk_assessment: Calculate risk score
            use_llm_reasoning: Use LLM for deeper insights (costs API calls)
            
        Returns:
            Complete analysis results
        """
        print("="*60)
        print(f"🔍 Running Complete Analysis for User {user_id}")
        print("="*60)
        
        results = {
            'user_id': user_id,
            'analysis_timestamp': datetime.now().isoformat(),
            'status': 'success'
        }
        
        # 1. Pattern Detection (always run - needed for reminders)
        print("\n[1/4] Pattern Detection...")
        try:
            pattern_results = self.pattern_agent.analyze_user(user_id)
            results['patterns'] = pattern_results
            print(f"      ✅ Detected {pattern_results['patterns_detected']} patterns")
            print(f"      ✅ Generated {pattern_results['active_reminders']} reminders")
        except Exception as e:
            print(f"      ❌ Error: {str(e)}")
            results['patterns'] = {'error': str(e)}
        
        # 2. Fraud Detection (optional, slower)
        if include_fraud_detection:
            print("\n[2/4] Fraud Detection...")
            try:
                fraud_results = self.fraud_agent.detect_anomalies(
                    user_id, 
                    use_llm=use_llm_reasoning
                )
                results['fraud_detection'] = fraud_results
                print(f"      ✅ Analyzed {fraud_results['transactions_analyzed']} transactions")
                print(f"      ✅ Detected {fraud_results['anomalies_detected']} anomalies")
                if fraud_results['high_risk_count'] > 0:
                    print(f"      ⚠️  {fraud_results['high_risk_count']} HIGH RISK anomalies found!")
            except Exception as e:
                print(f"      ❌ Error: {str(e)}")
                results['fraud_detection'] = {'error': str(e)}
        
        # 3. Forecasting (optional)
        if include_forecasting:
            print("\n[3/4] Spending Forecast...")
            try:
                forecast_results = self.forecast_agent.forecast_spending(user_id, days_ahead=30)
                results['forecast'] = forecast_results
                if forecast_results.get('success'):
                    total = forecast_results['forecast']['total_predicted']
                    print(f"      ✅ 30-day forecast: ₹{total:.0f}")
                    print(f"      ✅ Trend: {forecast_results['trend'].upper()}")
            except Exception as e:
                print(f"      ❌ Error: {str(e)}")
                results['forecast'] = {'error': str(e)}
        
        # 4. Risk Assessment (always run - critical metric)
        if include_risk_assessment:
            print("\n[4/4] Risk Assessment...")
            try:
                risk_results = self.risk_engine.calculate_overall_risk(user_id)
                results['risk_assessment'] = risk_results
                print(f"      ✅ Financial Health Score: {risk_results['overall_score']}/100")
                print(f"      ✅ Status: {risk_results['health_status']}")
                print(f"      ✅ Risk Level: {risk_results['risk_level']}")
            except Exception as e:
                print(f"      ❌ Error: {str(e)}")
                results['risk_assessment'] = {'error': str(e)}
        
        print("\n" + "="*60)
        print("✅ Complete Analysis Finished!")
        print("="*60)
        
        return results
    
    def get_dashboard_summary(self, user_id: int) -> Dict[str, Any]:
        """
        Get quick dashboard summary (fast, no LLM calls)
        
        Returns:
            Summary with key metrics for dashboard display
        """
        # Quick pattern check
        pattern_results = self.pattern_agent.analyze_user(user_id)
        
        # Quick risk score (no deep analysis)
        risk_results = self.risk_engine.calculate_overall_risk(user_id)
        
        # Get active reminders
        reminders = pattern_results['reminders'][:5]  # Top 5
        
        # Check for recent anomalies
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM anomalies
            WHERE user_id = ?
            AND created_at >= datetime('now', '-7 days')
            AND risk_level = 'HIGH'
        """, (user_id,))
        
        high_risk_anomalies = cursor.fetchone()[0]
        conn.close()
        
        return {
            'user_id': user_id,
            'risk_score': risk_results['overall_score'],
            'risk_level': risk_results['risk_level'],
            'health_status': risk_results['health_status'],
            'active_reminders': len(reminders),
            'reminders': reminders,
            'high_risk_anomalies': high_risk_anomalies,
            'patterns_detected': pattern_results['patterns_detected'],
            'top_recommendations': risk_results['recommendations'][:3]
        }
    
    def get_reminders(self, user_id: int, days_ahead: int = 7) -> List[Dict]:
        """Get smart reminders for user"""
        return self.pattern_agent.generate_reminders(user_id, days_ahead)
    
    def get_anomalies(self, user_id: int, risk_level: str = None) -> List[Dict]:
        """
        Get detected anomalies
        
        Args:
            user_id: User ID
            risk_level: Filter by risk level ('HIGH', 'MEDIUM', 'LOW')
        """
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = """
            SELECT a.*, t.vendor_name, t.amount, t.transaction_date
            FROM anomalies a
            JOIN transactions t ON a.transaction_id = t.id
            WHERE a.user_id = ?
        """
        params = [user_id]
        
        if risk_level:
            query += " AND a.risk_level = ?"
            params.append(risk_level)
        
        query += " ORDER BY a.created_at DESC LIMIT 20"
        
        cursor.execute(query, params)
        anomalies = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return anomalies
    
    def get_forecast(self, user_id: int, days_ahead: int = 30) -> Dict:
        """Get spending forecast"""
        return self.forecast_agent.forecast_spending(user_id, days_ahead)
    
    def get_risk_score(self, user_id: int) -> Dict:
        """Get financial health risk score"""
        return self.risk_engine.calculate_overall_risk(user_id)
    
    def save_insight(self, user_id: int, insight: Dict):
        """
        Save an insight to database for display
        
        Args:
            user_id: User ID
            insight: Insight dictionary with type, title, description, etc.
        """
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create insights table if not exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS insights (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                insight_type VARCHAR(50) NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                severity VARCHAR(20),
                metadata TEXT,
                confidence_score REAL,
                is_actionable BOOLEAN DEFAULT 0,
                action_taken BOOLEAN DEFAULT 0,
                is_read BOOLEAN DEFAULT 0,
                expires_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            INSERT INTO insights 
            (user_id, insight_type, title, description, severity, 
             metadata, confidence_score, is_actionable)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            insight.get('type', 'general'),
            insight.get('title', ''),
            insight.get('description', ''),
            insight.get('severity', 'info'),
            json.dumps(insight.get('metadata', {})),
            insight.get('confidence', 1.0),
            insight.get('is_actionable', False)
        ))
        
        conn.commit()
        conn.close()
    
    def generate_insights_from_analysis(self, analysis_results: Dict) -> List[Dict]:
        """
        Convert analysis results into actionable insights
        
        Returns:
            List of insight objects ready for display
        """
        insights = []
        user_id = analysis_results['user_id']
        
        # 1. Reminders as insights
        if 'patterns' in analysis_results and 'reminders' in analysis_results['patterns']:
            for reminder in analysis_results['patterns']['reminders'][:3]:
                insights.append({
                    'type': 'reminder',
                    'title': reminder['title'],
                    'description': reminder['description'],
                    'severity': 'info',
                    'confidence': reminder['confidence_score'],
                    'is_actionable': True,
                    'metadata': reminder
                })
        
        # 2. High-risk anomalies as insights
        if 'fraud_detection' in analysis_results:
            fraud_data = analysis_results['fraud_detection']
            if fraud_data.get('high_risk_count', 0) > 0:
                for anomaly in fraud_data['anomalies'][:3]:
                    if anomaly.get('risk_level') == 'HIGH':
                        txn = anomaly['transaction']
                        insights.append({
                            'type': 'anomaly',
                            'title': f"⚠️ Suspicious Transaction Detected",
                            'description': f"₹{txn['amount']} at {txn.get('vendor_name', 'Unknown')} - {anomaly.get('llm_explanation', anomaly['explanation'])}",
                            'severity': 'high',
                            'confidence': anomaly['risk_score'],
                            'is_actionable': True,
                            'metadata': anomaly
                        })
        
        # 3. Risk assessment insights
        if 'risk_assessment' in analysis_results:
            risk_data = analysis_results['risk_assessment']
            if risk_data['risk_level'] in ['HIGH', 'CRITICAL']:
                insights.append({
                    'type': 'risk',
                    'title': f"Financial Health: {risk_data['health_status']}",
                    'description': f"Your financial health score is {risk_data['overall_score']}/100. {risk_data['recommendations'][0] if risk_data['recommendations'] else ''}",
                    'severity': 'high' if risk_data['risk_level'] == 'CRITICAL' else 'medium',
                    'confidence': 1.0,
                    'is_actionable': True,
                    'metadata': risk_data
                })
        
        # 4. Forecast insights
        if 'forecast' in analysis_results and analysis_results['forecast'].get('success'):
            forecast_data = analysis_results['forecast']
            insights.append({
                'type': 'forecast',
                'title': "30-Day Spending Forecast",
                'description': f"Predicted spending: ₹{forecast_data['forecast']['total_predicted']:.0f}. Trend: {forecast_data['trend']}",
                'severity': 'info',
                'confidence': 0.8,
                'is_actionable': False,
                'metadata': forecast_data
            })
        
        return insights


# Test
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python analytics_orchestrator.py <db_path> [user_id]")
        sys.exit(1)
    
    db_path = sys.argv[1]
    user_id = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    
    orchestrator = AnalyticsOrchestrator(db_path)
    
    print("\n" + "="*60)
    print("TEST 1: Quick Dashboard Summary")
    print("="*60)
    
    summary = orchestrator.get_dashboard_summary(user_id)
    print(f"\n📊 Dashboard Summary:")
    print(f"   Risk Score: {summary['risk_score']}/100 ({summary['risk_level']})")
    print(f"   Status: {summary['health_status']}")
    print(f"   Active Reminders: {summary['active_reminders']}")
    print(f"   High-Risk Anomalies: {summary['high_risk_anomalies']}")
    print(f"   Patterns Detected: {summary['patterns_detected']}")
    
    print("\n" + "="*60)
    print("TEST 2: Complete Analysis (with LLM)")
    print("="*60)
    
    results = orchestrator.run_complete_analysis(
        user_id,
        include_fraud_detection=True,
        include_forecasting=True,
        include_risk_assessment=True,
        use_llm_reasoning=True  # Set to False for faster testing
    )
    
    print("\n" + "="*60)
    print("GENERATING INSIGHTS")
    print("="*60)
    
    insights = orchestrator.generate_insights_from_analysis(results)
    print(f"\n📝 Generated {len(insights)} insights:")
    for i, insight in enumerate(insights, 1):
        print(f"\n{i}. [{insight['type'].upper()}] {insight['title']}")
        print(f"   {insight['description']}")
        print(f"   Severity: {insight['severity']} | Confidence: {insight['confidence']:.1%}")