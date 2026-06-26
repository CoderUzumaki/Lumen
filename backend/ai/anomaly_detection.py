
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any
import statistics
import json
import requests
import os
from models.database import db
import logging

logger = logging.getLogger(__name__)



try:
    from sklearn.ensemble import IsolationForest
    from sklearn.svm import OneClassSVM
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logger.warning("⚠️  scikit-learn not installed. ML models disabled.")

class FraudDetectionAgent:
    """Multi-layer anomaly detection system"""

    from config import Config as _Config  # local import to avoid module-level cycles
    OPENROUTER_API_KEY = _Config.OPENROUTER_API_KEY
    OPENROUTER_MODEL = _Config.LLM_TEXT_MODEL
    OPENROUTER_CHAT_URL = _Config.OPENROUTER_CHAT_URL
    
    def __init__(self):
        """
        Initialize fraud detection agent
        """
        self.scaler = StandardScaler() if SKLEARN_AVAILABLE else None
    
    def get_user_transactions(self, user_id: int, days_back: int = 90) -> List[Dict]:
        """Get recent transactions for user"""
        cutoff_date = (datetime.now() - timedelta(days=days_back)).date().isoformat()
        
        result = db.session.execute(db.text("""
            SELECT * FROM transactions
            WHERE user_id = :user_id
            AND date >= :cutoff_date
            ORDER BY date DESC
        """), {'user_id': str(user_id), 'cutoff_date': cutoff_date})
        
        transactions = [dict(row._mapping) for row in result]
        
        return transactions
    
    def statistical_anomaly_detection(self, transactions: List[Dict]) -> List[Dict]:
        """
        Layer 1: Statistical anomaly detection
        Uses Z-score and IQR methods
        """
        if len(transactions) < 10:
            return []  # Need minimum data
        
        anomalies = []
        amounts = [t.get('total_amount', t.get('amount', 0)) for t in transactions]
        
        # Calculate statistics
        mean_amount = statistics.mean(amounts)
        stdev_amount = statistics.stdev(amounts) if len(amounts) > 1 else 0
        
        # IQR calculation
        sorted_amounts = sorted(amounts)
        q1 = sorted_amounts[len(sorted_amounts) // 4]
        q3 = sorted_amounts[3 * len(sorted_amounts) // 4]
        iqr = q3 - q1
        
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        
        for txn in transactions:
            flags = []
            risk_score = 0.0
            txn_amount = txn.get('total_amount', txn.get('amount', 0))
            
            # Z-score check
            if stdev_amount > 0:
                z_score = abs((txn_amount - mean_amount) / stdev_amount)
                if z_score > 3:
                    flags.append(f"amount_{z_score:.1f}_stdev")
                    risk_score += min(z_score / 10, 0.3)  # Cap at 0.3
            

            if txn_amount < lower_bound or txn_amount > upper_bound:
                flags.append("amount_outside_iqr")
                risk_score += 0.2

            if txn_amount in [1000, 2000, 5000, 10000, 20000, 50000, 100000]:
                flags.append("suspicious_round_number")
                risk_score += 0.1
            
            if flags:
                anomalies.append({
                    'transaction_id': txn['id'],
                    'transaction': txn,
                    'anomaly_type': 'amount',
                    'detection_method': 'statistical',
                    'flags': flags,
                    'risk_score': min(risk_score, 1.0),
                    'explanation': f"Amount €{txn_amount} is unusual (mean: €{mean_amount:.0f})"
                })
        
        return anomalies
    
    def rule_based_detection(self, transactions: List[Dict]) -> List[Dict]:
        """
        Layer 2: Rule-based anomaly detection
        """
        anomalies = []
        
        # Build merchant history
        merchant_counts = {}
        for txn in transactions:
            vendor = txn.get('vendor_name', 'Unknown')
            merchant_counts[vendor] = merchant_counts.get(vendor, 0) + 1
        
        # Track recent transactions for duplicate detection
        recent_txns = {}
        
        for txn in transactions:
            flags = []
            risk_score = 0.0
            
            # First-time merchant (only 1 transaction)
            vendor = txn.get('vendor_name', 'Unknown')
            if merchant_counts.get(vendor, 0) == 1:
                flags.append("first_time_merchant")
                risk_score += 0.15
            
            # Time-based anomaly (midnight to 5am)
            try:
                txn_datetime = datetime.fromisoformat(txn['date'])
                if 0 <= txn_datetime.hour < 5:
                    flags.append("unusual_time_midnight")
                    risk_score += 0.2
            except:
                pass
            
            # Duplicate detection (same amount within 24 hours)
            key = f"{vendor}_{txn['total_amount']}"
            if key in recent_txns:
                prev_txn = recent_txns[key]
                try:
                    time_diff = abs((datetime.fromisoformat(txn['date']) - 
                                datetime.fromisoformat(prev_txn['date'])).total_seconds())
                    if time_diff < 86400:  # 24 hours
                        flags.append("potential_duplicate")
                        risk_score += 0.25
                except:
                    pass
            
            recent_txns[key] = txn
            
            if flags:
                anomalies.append({
                    'transaction_id': txn['id'],
                    'transaction': txn,
                    'anomaly_type': 'behavioral',
                    'detection_method': 'rule_based',
                    'flags': flags,
                    'risk_score': min(risk_score, 1.0),
                    'explanation': f"Suspicious pattern detected: {', '.join(flags)}"
                })
        
        return anomalies
    
    def ml_anomaly_detection(self, transactions: List[Dict]) -> List[Dict]:
        """
        Layer 3: ML-based anomaly detection
        Uses Isolation Forest
        """
        if not SKLEARN_AVAILABLE or len(transactions) < 20:
            return []
        
        anomalies = []
        
        # Feature engineering
        features = []
        for txn in transactions:
            # Extract hour from datetime
            try:
                txn_dt = datetime.fromisoformat(txn['date'])
                hour = txn_dt.hour
                day_of_week = txn_dt.weekday()
            except:
                hour = 12
                day_of_week = 0
            
            feature_vector = [
                txn['total_amount'],
                hour,
                day_of_week,
                len(txn.get('vendor_name', '')),  # Vendor name length
                1 if txn.get('payment_method') == 'Cash' else 0
            ]
            features.append(feature_vector)
        
        X = np.array(features)
        
        # Standardize features
        X_scaled = self.scaler.fit_transform(X)
        
        # Train Isolation Forest
        iso_forest = IsolationForest(
            contamination=0.05,  # Expect 5% anomalies
            random_state=42
        )
        
        predictions = iso_forest.fit_predict(X_scaled)
        anomaly_scores = iso_forest.score_samples(X_scaled)
        
        # Collect anomalies
        for idx, (pred, score) in enumerate(zip(predictions, anomaly_scores)):
            if pred == -1:  # Anomaly detected
                txn = transactions[idx]
                
                # Convert score to risk (score is negative, more negative = more anomalous)
                risk_score = min(abs(score) / 0.5, 1.0)
                
                anomalies.append({
                    'transaction_id': txn['id'],
                    'transaction': txn,
                    'anomaly_type': 'ml_detected',
                    'detection_method': 'isolation_forest',
                    'flags': ['ml_anomaly'],
                    'risk_score': risk_score,
                    'ml_score': float(score),
                    'explanation': f"ML model flagged as anomalous (score: {score:.3f})"
                })
        
        return anomalies
    
    def llm_reasoning(self, anomaly: Dict) -> Dict:
        """
        Layer 4: LLM contextual reasoning
        Provides human-readable explanations
        """
        if not self.OPENROUTER_API_KEY:
            anomaly['llm_explanation'] = anomaly['explanation']
            anomaly['risk_level'] = self._calculate_risk_level(anomaly['risk_score'])
            return anomaly
        
        txn = anomaly['transaction']
        
        prompt = f"""You are a fraud detection expert analyzing a flagged transaction.

Transaction Details:
- Amount: ₹{txn['total_amount']}
- Vendor: {txn.get('vendor_name', 'Unknown')}
- Category: {txn.get('category', 'Unknown')}
- Date: {txn['date']}
- Payment Method: {txn.get('payment_method', 'Unknown')}

Flags Raised:
{', '.join(anomaly['flags'])}

Initial Risk Score: {anomaly['risk_score']:.2f}

Tasks:
1. Assess if this is genuinely suspicious or likely a false positive
2. Provide a clear, concise explanation (2-3 sentences)
3. Recommend action: MONITOR, REVIEW, or ALERT

Respond in JSON format:
{{
  "is_suspicious": true/false,
  "confidence": 0.0-1.0,
  "explanation": "clear explanation",
  "recommendation": "MONITOR/REVIEW/ALERT",
  "risk_level": "LOW/MEDIUM/HIGH"
}}"""
        
        try:
            response = requests.post(
                self.OPENROUTER_CHAT_URL,
                headers={
                    "Authorization": f"Bearer {self.OPENROUTER_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.OPENROUTER_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 300
                },
                timeout=30
            )
            
            result = response.json()
            content = result['choices'][0]['message']['content'].strip()
            
            # Clean JSON
            content = content.replace('```json', '').replace('```', '').strip()
            llm_result = json.loads(content)
            
            # Update anomaly with LLM reasoning
            anomaly['llm_explanation'] = llm_result['explanation']
            anomaly['llm_confidence'] = llm_result['confidence']
            anomaly['recommendation'] = llm_result['recommendation']
            anomaly['risk_level'] = llm_result['risk_level']
            
            # Adjust risk score based on LLM
            if not llm_result['is_suspicious']:
                anomaly['risk_score'] *= 0.5  # Reduce if LLM thinks it's false positive
        
        except Exception as e:
            logger.info(f"LLM reasoning failed: {str(e)}")
            anomaly['llm_explanation'] = anomaly['explanation']
            anomaly['risk_level'] = self._calculate_risk_level(anomaly['risk_score'])
        
        return anomaly
    
    def _calculate_risk_level(self, risk_score: float) -> str:
        """Calculate risk level from score"""
        if risk_score >= 0.7:
            return 'HIGH'
        elif risk_score >= 0.4:
            return 'MEDIUM'
        else:
            return 'LOW'
    
    def detect_anomalies(self, user_id: int, use_llm: bool = True) -> Dict[str, Any]:
        """
        Complete anomaly detection pipeline
        
        Args:
            user_id: User ID to analyze
            use_llm: Whether to use LLM reasoning (slower but better)
            
        Returns:
            Anomaly detection results
        """
        logger.info(f"🔍 Detecting anomalies for user {user_id}...")
        
        # Get transactions
        transactions = self.get_user_transactions(user_id, days_back=90)
        logger.info(f"   Analyzing {len(transactions)} transactions")
        
        if len(transactions) < 5:
            return {
                'user_id': user_id,
                'anomalies_detected': 0,
                'anomalies': [],
                'message': 'Insufficient data for analysis'
            }
        
        # Layer 1: Statistical
        stat_anomalies = self.statistical_anomaly_detection(transactions)
        logger.info(f"   Statistical: {len(stat_anomalies)} anomalies")
        
        # Layer 2: Rule-based
        rule_anomalies = self.rule_based_detection(transactions)
        logger.info(f"   Rule-based: {len(rule_anomalies)} anomalies")
        
        # Layer 3: ML (if available)
        ml_anomalies = []
        if SKLEARN_AVAILABLE:
            ml_anomalies = self.ml_anomaly_detection(transactions)
            logger.info(f"   ML: {len(ml_anomalies)} anomalies")
        
        # Combine and deduplicate anomalies
        all_anomalies = {}
        for anomaly in stat_anomalies + rule_anomalies + ml_anomalies:
            txn_id = anomaly['transaction_id']
            if txn_id in all_anomalies:
                # Merge flags and increase risk score
                all_anomalies[txn_id]['flags'].extend(anomaly['flags'])
                all_anomalies[txn_id]['risk_score'] = min(
                    all_anomalies[txn_id]['risk_score'] + anomaly['risk_score'] * 0.5,
                    1.0
                )
            else:
                all_anomalies[txn_id] = anomaly
        
        # Convert to list
        final_anomalies = list(all_anomalies.values())
        
        # Sort by risk score
        final_anomalies.sort(key=lambda x: x['risk_score'], reverse=True)
        
        # Layer 4: LLM reasoning on top anomalies (limit to save time/cost)
        if use_llm:
            logger.info(f"   Applying LLM reasoning to top {min(len(final_anomalies), 5)} anomalies...")
            for anomaly in final_anomalies[:5]:
                self.llm_reasoning(anomaly)
        else:
            for anomaly in final_anomalies:
                anomaly['risk_level'] = self._calculate_risk_level(anomaly['risk_score'])
        
        # Save to database
        self.save_anomalies_to_db(user_id, final_anomalies)
        
        return {
            'user_id': user_id,
            'transactions_analyzed': len(transactions),
            'anomalies_detected': len(final_anomalies),
            'high_risk_count': sum(1 for a in final_anomalies if a.get('risk_level') == 'HIGH'),
            'medium_risk_count': sum(1 for a in final_anomalies if a.get('risk_level') == 'MEDIUM'),
            'low_risk_count': sum(1 for a in final_anomalies if a.get('risk_level') == 'LOW'),
            'anomalies': final_anomalies
        }
    
    def save_anomalies_to_db(self, user_id: int, anomalies: List[Dict]):
        """Save anomalies to database"""
        # Create anomalies table
        db.session.execute(db.text("""
            CREATE TABLE IF NOT EXISTS anomalies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transaction_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                anomaly_type VARCHAR(50),
                detection_method VARCHAR(50),
                risk_score REAL,
                risk_level VARCHAR(20),
                explanation TEXT,
                flags TEXT,
                llm_explanation TEXT,
                recommendation VARCHAR(20),
                is_false_positive BOOLEAN,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (transaction_id) REFERENCES transactions(id)
            )
        """))
        
        # Insert anomalies
        import uuid
        for anomaly in anomalies:
            db.session.execute(db.text("""
                INSERT INTO anomalies 
                (id, transaction_id, user_id, anomaly_type, detection_method,
                 risk_score, risk_level, explanation, flags, llm_explanation, recommendation)
                VALUES (:id, :transaction_id, :user_id, :anomaly_type, :detection_method,
                        :risk_score, :risk_level, :explanation, :flags, :llm_explanation, :recommendation)
            """), {
                'id': str(uuid.uuid4()),
                'transaction_id': anomaly['transaction_id'],
                'user_id': str(user_id),
                'anomaly_type': anomaly['anomaly_type'],
                'detection_method': anomaly['detection_method'],
                'risk_score': int(anomaly['risk_score'] * 100),  # Convert to 0-100 scale
                'risk_level': anomaly.get('risk_level', 'LOW'),
                'explanation': anomaly['explanation'],
                'flags': json.dumps(anomaly['flags']),
                'llm_explanation': anomaly.get('llm_explanation'),
                'recommendation': anomaly.get('recommendation')
            })
        
        db.session.commit()


# Test/Example Usage
if __name__ == "__main__":
    logger.info("="*60)
    logger.info("Fraud Detection Agent Module")
    logger.info("="*60)
    logger.info("\n⚠️  This module should be imported and used within the Flask app context.")
    logger.info("\n📘 Example usage:")
    logger.info("""
    from flask import Flask
    from models.database import init_db
    from ai.anomaly_detection import FraudDetectionAgent

    # Use the existing Flask app from app.py
    with app.app_context():
        agent = FraudDetectionAgent()
        results = agent.detect_anomalies(user_id=123, use_llm=True)
        >>> results['anomalies_detected']
    """)
    logger.info("\n✅ See app.py for proper Flask application initialization.")
    logger.info("="*60)