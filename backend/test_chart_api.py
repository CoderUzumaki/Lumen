"""
Test the analytics API chart data
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app

def test_chart_api():
    """Test the chart data endpoint"""
    print("🔍 Testing Analytics Chart Data API")
    print("=" * 60)
    
    with app.test_client() as client:
        # Test monthly chart data
        response = client.get('/api/analytics/summary?user_id=123&time_range=monthly&year=2024&month=10')
        
        print(f"\nStatus Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.get_json()
            print("\n✅ Monthly Chart Data:")
            
            if 'chart_data' in data:
                chart_data = data['chart_data']
                print(f"   Data Points: {len(chart_data)}")
                
                if chart_data:
                    print("\n   First 5 data points:")
                    for i, point in enumerate(chart_data[:5], 1):
                        print(f"   {i}. Date: {point['date']}, Current: ${point['currentSpending']:.2f}, Previous: ${point['previousSpending']:.2f}")
                    
                    total_current = sum(p['currentSpending'] for p in chart_data)
                    total_previous = sum(p['previousSpending'] for p in chart_data)
                    print(f"\n   Total Current: ${total_current:.2f}")
                    print(f"   Total Previous: ${total_previous:.2f}")
            else:
                print("   ❌ No chart_data in response!")
                print(f"   Response keys: {data.keys()}")
        else:
            print(f"\n❌ Error: {response.get_data(as_text=True)}")

if __name__ == "__main__":
    test_chart_api()
