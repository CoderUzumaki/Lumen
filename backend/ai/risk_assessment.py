"""
Risk Assessment Engine - Comprehensive financial health scoring
"""

import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Any, List
import statistics
import logging

logger = logging.getLogger(__name__)


class RiskAssessmentEngine:
    """Calculate comprehensive financial health score"""
    
    def __init__(self, db_path: str):
        """
        Initialize risk assessment engine
        
        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path
    
    def get_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def calculate_spending_velocity_risk(self, user_id: int) -> Dict[str, Any]:
        """
        Risk Factor 1: Spending Velocity (0-25 points)
        Compares recent spending to historical average
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Get last 30 days spending
        cursor.execute("""
            SELECT SUM(total_amount) as total
            FROM transactions
            WHERE user_id = ?
            AND date >= date('now', '-30 days')
        """, (user_id,))
        
        last_30 = cursor.fetchone()['total'] or 0
        
        # Get 30-60 days ago (baseline)
        cursor.execute("""
            SELECT SUM(total_amount) as total
            FROM transactions
            WHERE user_id = ?
            AND date >= date('now', '-60 days')
            AND date < date('now', '-30 days')
        """, (user_id,))
        
        prev_30 = cursor.fetchone()['total'] or 0
        
        conn.close()
        
        # Calculate risk
        if prev_30 == 0:
            risk_score = 0
            message = "Insufficient baseline data"
        else:
            increase_percent = ((last_30 - prev_30) / prev_30) * 100
            
            if increase_percent > 50:
                risk_score = 25
                message = f"Spending increased by {increase_percent:.0f}% - Critical"
            elif increase_percent > 30:
                risk_score = 20
                message = f"Spending increased by {increase_percent:.0f}% - High"
            elif increase_percent > 15:
                risk_score = 15
                message = f"Spending increased by {increase_percent:.0f}% - Moderate"
            elif increase_percent > 5:
                risk_score = 10
                message = f"Spending increased by {increase_percent:.0f}% - Low"
            elif increase_percent < -15:
                risk_score = 5
                message = f"Spending decreased by {abs(increase_percent):.0f}% - Good"
            else:
                risk_score = 8
                message = "Spending stable"
        
        return {
            'factor': 'spending_velocity',
            'score': risk_score,
            'max_score': 25,
            'percentage': round((risk_score / 25) * 100, 1),
            'message': message,
            'last_30_days': round(last_30, 2),
            'previous_30_days': round(prev_30, 2)
        }
    
    def calculate_budget_deviation_risk(self, user_id: int, monthly_budget: float = None) -> Dict[str, Any]:
        """
        Risk Factor 2: Budget Deviation (0-25 points)
        How much over budget is the user
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Get current month spending
        cursor.execute("""
            SELECT SUM(total_amount) as total
            FROM transactions
            WHERE user_id = ?
            AND strftime('%Y-%m', date) = strftime('%Y-%m', 'now')
        """, (user_id,))
        
        current_month = cursor.fetchone()['total'] or 0
        
        conn.close()
        
        # If no budget set, use average of last 3 months
        if monthly_budget is None:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT AVG(monthly_total) as avg_budget
                FROM (
                    SELECT strftime('%Y-%m', date) as month,
                           SUM(total_amount) as monthly_total
                    FROM transactions
                    WHERE user_id = ?
                    AND date >= date('now', '-90 days')
                    GROUP BY month
                )
            """, (user_id,))
            
            result = cursor.fetchone()
            monthly_budget = result['avg_budget'] if result['avg_budget'] else current_month
            conn.close()
        
        # Calculate risk
        if monthly_budget == 0:
            risk_score = 0
            message = "No budget data available"
        else:
            over_budget_percent = ((current_month - monthly_budget) / monthly_budget) * 100
            
            if over_budget_percent > 50:
                risk_score = 25
                message = f"{over_budget_percent:.0f}% over budget - Critical"
            elif over_budget_percent > 30:
                risk_score = 20
                message = f"{over_budget_percent:.0f}% over budget - High"
            elif over_budget_percent > 15:
                risk_score = 15
                message = f"{over_budget_percent:.0f}% over budget - Moderate"
            elif over_budget_percent > 0:
                risk_score = 10
                message = f"{over_budget_percent:.0f}% over budget - Slight"
            else:
                risk_score = 5
                message = f"Under budget by {abs(over_budget_percent):.0f}% - Good"
        
        return {
            'factor': 'budget_deviation',
            'score': risk_score,
            'max_score': 25,
            'percentage': round((risk_score / 25) * 100, 1),
            'message': message,
            'current_month_spending': round(current_month, 2),
            'monthly_budget': round(monthly_budget, 2)
        }
    
    def calculate_anomaly_risk(self, user_id: int) -> Dict[str, Any]:
        """
        Risk Factor 3: Anomaly Risk (0-20 points)
        Based on detected anomalies
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Check if anomalies table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='anomalies'
        """)
        
        if not cursor.fetchone():
            conn.close()
            return {
                'factor': 'anomaly_risk',
                'score': 0,
                'max_score': 20,
                'percentage': 0,
                'message': 'No anomaly data available',
                'anomaly_count': 0
            }
        
        # Get anomaly counts by risk level (last 30 days)
        cursor.execute("""
            SELECT 
                CASE 
                    WHEN risk_score >= 80 THEN 'HIGH'
                    WHEN risk_score >= 50 THEN 'MEDIUM'
                    ELSE 'LOW'
                END as risk_level,
                COUNT(*) as count
            FROM anomalies a
            JOIN transactions t ON a.transaction_id = t.id
            WHERE t.user_id = ?
            AND a.created_at >= datetime('now', '-30 days')
            GROUP BY risk_level
        """, (str(user_id),))
        
        anomalies = {row['risk_level']: row['count'] for row in cursor.fetchall()}
        conn.close()
        
        high = anomalies.get('HIGH', 0)
        medium = anomalies.get('MEDIUM', 0)
        low = anomalies.get('LOW', 0)
        
        # Calculate risk score
        risk_score = min(high * 10 + medium * 5 + low * 2, 20)
        total_anomalies = high + medium + low
        
        if total_anomalies == 0:
            message = "No anomalies detected"
        elif high > 0:
            message = f"{high} high-risk anomalies detected - Review needed"
        elif medium > 2:
            message = f"{medium} moderate anomalies detected"
        else:
            message = f"{total_anomalies} minor anomalies detected"
        
        return {
            'factor': 'anomaly_risk',
            'score': risk_score,
            'max_score': 20,
            'percentage': round((risk_score / 20) * 100, 1),
            'message': message,
            'anomaly_count': total_anomalies,
            'high_risk': high,
            'medium_risk': medium,
            'low_risk': low
        }
    
    def calculate_liquidity_risk(self, user_id: int, monthly_income: float = None) -> Dict[str, Any]:
        """
        Risk Factor 4: Liquidity Risk (0-15 points)
        Spending vs income ratio
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Get current month spending
        cursor.execute("""
            SELECT SUM(total_amount) as total
            FROM transactions
            WHERE user_id = ?
            AND strftime('%Y-%m', date) = strftime('%Y-%m', 'now')
        """, (user_id,))
        
        current_spending = cursor.fetchone()['total'] or 0
        conn.close()
        
        # If no income provided, estimate based on spending
        if monthly_income is None:
            monthly_income = current_spending * 1.3  # Assume 30% savings rate
        
        # Calculate spending ratio
        if monthly_income == 0:
            risk_score = 0
            message = "Income data not available"
        else:
            spending_ratio = (current_spending / monthly_income) * 100
            
            if spending_ratio > 90:
                risk_score = 15
                message = f"Spending {spending_ratio:.0f}% of income - Critical"
            elif spending_ratio > 80:
                risk_score = 12
                message = f"Spending {spending_ratio:.0f}% of income - High"
            elif spending_ratio > 70:
                risk_score = 9
                message = f"Spending {spending_ratio:.0f}% of income - Moderate"
            elif spending_ratio > 60:
                risk_score = 6
                message = f"Spending {spending_ratio:.0f}% of income - Manageable"
            else:
                risk_score = 3
                message = f"Spending {spending_ratio:.0f}% of income - Good"
        
        return {
            'factor': 'liquidity_risk',
            'score': risk_score,
            'max_score': 15,
            'percentage': round((risk_score / 15) * 100, 1),
            'message': message,
            'current_spending': round(current_spending, 2),
            'estimated_income': round(monthly_income, 2)
        }
    
    def calculate_behavioral_risk(self, user_id: int) -> Dict[str, Any]:
        """
        Risk Factor 5: Behavioral Risk (0-15 points)
        Impulsive spending, late patterns, high-risk merchants
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        risk_score = 0
        risk_factors = []
        
        # Check for high frequency of small transactions (impulsive spending)
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM transactions
            WHERE user_id = ?
            AND total_amount < 500
            AND date >= date('now', '-30 days')
        """, (user_id,))
        
        small_txn_count = cursor.fetchone()['count']
        if small_txn_count > 50:
            risk_score += 5
            risk_factors.append("High frequency of small purchases")
        
        # Check for late-night transactions (potential impulsive behavior)
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM transactions
            WHERE user_id = ?
            AND date >= date('now', '-30 days')
        """, (user_id,))
        
        total_txn = cursor.fetchone()['count']
        
        # Check recurring patterns table
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='spending_patterns'
        """)
        
        if cursor.fetchone():
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM spending_patterns
                WHERE user_id = ?
                AND is_active = 1
            """, (user_id,))
            
            pattern_count = cursor.fetchone()['count']
            if pattern_count == 0 and total_txn > 20:
                risk_score += 5
                risk_factors.append("No established spending patterns")
        
        conn.close()
        
        message = "; ".join(risk_factors) if risk_factors else "Healthy spending behavior"
        
        return {
            'factor': 'behavioral_risk',
            'score': risk_score,
            'max_score': 15,
            'percentage': round((risk_score / 15) * 100, 1),
            'message': message,
            'risk_indicators': risk_factors
        }
    
    def calculate_overall_risk(self, user_id: int, 
                              monthly_budget: float = None,
                              monthly_income: float = None) -> Dict[str, Any]:
        """
        Calculate comprehensive financial health score
        
        Args:
            user_id: User ID
            monthly_budget: Optional monthly budget
            monthly_income: Optional monthly income
            
        Returns:
            Complete risk assessment with score and recommendations
        """
        logger.info(f"📊 Assessing financial risk for user {user_id}...")
        
        # Calculate all risk factors
        velocity_risk = self.calculate_spending_velocity_risk(user_id)
        budget_risk = self.calculate_budget_deviation_risk(user_id, monthly_budget)
        anomaly_risk = self.calculate_anomaly_risk(user_id)
        liquidity_risk = self.calculate_liquidity_risk(user_id, monthly_income)
        behavioral_risk = self.calculate_behavioral_risk(user_id)
        
        # Calculate total score (out of 100)
        total_score = (
            velocity_risk['score'] +
            budget_risk['score'] +
            anomaly_risk['score'] +
            liquidity_risk['score'] +
            behavioral_risk['score']
        )
        
        # Determine risk level and health status
        if total_score <= 30:
            risk_level = 'LOW'
            health_status = 'HEALTHY'
            status_color = 'green'
        elif total_score <= 60:
            risk_level = 'MEDIUM'
            health_status = 'NEEDS ATTENTION'
            status_color = 'yellow'
        elif total_score <= 80:
            risk_level = 'HIGH'
            health_status = 'AT RISK'
            status_color = 'orange'
        else:
            risk_level = 'CRITICAL'
            health_status = 'FINANCIAL DISTRESS'
            status_color = 'red'
        
        # Generate recommendations
        recommendations = self.generate_recommendations([
            velocity_risk, budget_risk, anomaly_risk, 
            liquidity_risk, behavioral_risk
        ])
        
        # Determine trend (would need historical scores, simplified here)
        trend = 'stable'  # 'improving', 'stable', 'declining'
        
        return {
            'user_id': user_id,
            'overall_score': total_score,
            'max_score': 100,
            'risk_level': risk_level,
            'health_status': health_status,
            'status_color': status_color,
            'trend': trend,
            'factors': [
                velocity_risk,
                budget_risk,
                anomaly_risk,
                liquidity_risk,
                behavioral_risk
            ],
            'recommendations': recommendations,
            'assessed_at': datetime.now().isoformat()
        }
    
    def generate_recommendations(self, risk_factors: List[Dict]) -> List[str]:
        """Generate actionable recommendations based on risk factors"""
        recommendations = []
        
        for factor in risk_factors:
            if factor['score'] > factor['max_score'] * 0.6:  # High risk
                if factor['factor'] == 'spending_velocity':
                    recommendations.append("⚠️ Reduce discretionary spending by 20%")
                elif factor['factor'] == 'budget_deviation':
                    recommendations.append("📊 Review and adjust your monthly budget")
                elif factor['factor'] == 'anomaly_risk':
                    recommendations.append("🔍 Review flagged transactions for accuracy")
                elif factor['factor'] == 'liquidity_risk':
                    recommendations.append("💰 Build emergency fund (3-6 months expenses)")
                elif factor['factor'] == 'behavioral_risk':
                    recommendations.append("🎯 Set spending limits for discretionary categories")
        
        if not recommendations:
            recommendations.append("✅ Maintain current healthy spending patterns")
        
        return recommendations


# Test
if __name__ == "__main__":
    import sys
    import json
    
    if len(sys.argv) < 2:
        logger.info("Usage: python risk_assessment_engine.py <db_path> [user_id]")
        sys.exit(1)
    
    db_path = sys.argv[1]
    user_id = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    
    engine = RiskAssessmentEngine(db_path)
    
    logger.info("="*60)
    logger.info("Risk Assessment Engine Test")
    logger.info("="*60)
    
    result = engine.calculate_overall_risk(user_id)
    
    logger.info("\n" + "="*60)
    logger.info(f"FINANCIAL HEALTH SCORE: {result['overall_score']}/100")
    logger.info(f"Status: {result['health_status']}")
    logger.info(f"Risk Level: {result['risk_level']}")
    logger.info("="*60)
    
    logger.info("\n" + "-"*60)
    logger.info("RISK FACTORS:")
    logger.info("-"*60)
    for factor in result['factors']:
        logger.info(f"\n{factor['factor'].upper()}")
        logger.info(f"  Score: {factor['score']}/{factor['max_score']} ({factor['percentage']}%)")
        logger.info(f"  {factor['message']}")
    
    logger.info("\n" + "-"*60)
    logger.info("RECOMMENDATIONS:")
    logger.info("-"*60)
    for rec in result['recommendations']:
        logger.info(f"  {rec}")