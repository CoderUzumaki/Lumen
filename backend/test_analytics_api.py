"""
Test the full analytics API endpoint
"""
import sys
import os
import json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app

def test_analytics_api():
    """Test the /api/analytics/analyze endpoint"""
    print("🔍 Testing Analytics API")
    print("=" * 60)
    
    with app.test_client() as client:
        # Test the analyze endpoint
        response = client.post('/api/analytics/analyze', 
                              json={'user_id': '123'},
                              content_type='application/json')
        
        print(f"\nStatus Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.get_json()
            print("\n✅ Analysis Results:")
            print(f"   Status: {data.get('status')}")
            
            # Patterns
            if 'patterns' in data:
                patterns = data['patterns']
                print(f"\n📊 Patterns:")
                print(f"   Total Detected: {patterns.get('patterns_detected')}")
                print(f"   Recurring: {patterns.get('recurring_patterns')}")
                print(f"   Day-of-Month: {patterns.get('day_of_month_patterns')}")
                print(f"   Active Reminders: {patterns.get('active_reminders')}")
            
            # Fraud Detection
            if 'fraud_detection' in data:
                fraud = data['fraud_detection']
                print(f"\n🚨 Fraud Detection:")
                print(f"   Anomalies Detected: {fraud.get('anomalies_detected')}")
                print(f"   High Risk: {fraud.get('high_risk_count')}")
                print(f"   Medium Risk: {fraud.get('medium_risk_count')}")
            
            # Risk Assessment
            if 'risk_assessment' in data:
                risk = data['risk_assessment']
                print(f"\n⚠️ Risk Assessment:")
                print(f"   Risk Level: {risk.get('risk_level')}")
                print(f"   Risk Score: {risk.get('risk_score')}")
                print(f"   Health Status: {risk.get('health_status')}")
            
            # Insights
            if 'insights' in data:
                insights = data['insights']
                print(f"\n💡 Insights Generated: {len(insights)}")
                for i, insight in enumerate(insights[:3], 1):
                    print(f"   {i}. {insight.get('title')} ({insight.get('severity')})")
            
        else:
            print(f"\n❌ Error: {response.get_data(as_text=True)}")
        
        # Test dashboard endpoint
        print("\n" + "=" * 60)
        print("Testing Dashboard API")
        print("=" * 60)
        
        response = client.get('/api/analytics/dashboard?user_id=123')
        print(f"\nStatus Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.get_json()
            data = result.get('data', {})
            print("\n✅ Dashboard Data:")
            print(f"   Risk Score: {data.get('risk_score')}")
            print(f"   Health Status: {data.get('health_status')}")
            print(f"   Patterns Count: {data.get('patterns_count')}")
            print(f"   Active Reminders: {data.get('active_reminders')}")
            print(f"   Anomalies: {data.get('anomalies_count')}")
        else:
            print(f"\n❌ Error: {response.get_data(as_text=True)}")

if __name__ == "__main__":
    test_analytics_api()
