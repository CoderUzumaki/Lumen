"""
Test pattern detection with recurring data
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from ai.pattern_detection import PatternDetectionAgent

def test_patterns():
    """Test pattern detection on recurring transactions"""
    print("🔍 Testing Pattern Detection")
    print("=" * 60)
    
    with app.app_context():
        db_path = os.path.join(os.path.dirname(__file__), 'instance', 'lumen.db')
        agent = PatternDetectionAgent(db_path)
        
        print("\n📊 Analyzing patterns for user 123...")
        results = agent.analyze_user(123)
        
        print(f"\n✅ Analysis Complete!")
        print(f"   Patterns Detected: {results['patterns_detected']}")
        print(f"   Recurring Patterns: {results['recurring_patterns']}")
        print(f"   Day of Month Patterns: {results['day_of_month_patterns']}")
        print(f"   Active Reminders: {results['active_reminders']}")
        
        print("\n📋 Top 5 Recurring Patterns:")
        recurring = [p for p in results['patterns'] if p.get('pattern_type') == 'recurring']
        for i, pattern in enumerate(recurring[:5], 1):
            print(f"\n{i}. {pattern.get('vendor_name', 'Unknown')}")
            print(f"   Category: {pattern.get('category', 'N/A')}")
            print(f"   Frequency: Every {pattern.get('frequency_days', 0)} days")
            print(f"   Occurrences: {pattern.get('occurrence_count', 0)}")
            print(f"   Avg Amount: €{pattern.get('average_amount', 0)}")
            print(f"   Next Predicted: {pattern.get('next_predicted_date', 'N/A')}")
            print(f"   Confidence: {pattern.get('confidence_score', 0):.2%}")
        
        print("\n📅 Smart Reminders (next 30 days):")
        reminders = agent.generate_reminders(123, days_ahead=30)
        print(f"Total Reminders: {len(reminders)}\n")
        for reminder in reminders[:8]:
            print(f"• {reminder['title']}")
            print(f"  Due: {reminder['predicted_date']} ({reminder['days_until']} days)")
            if 'expected_amount' in reminder:
                print(f"  Amount: ~€{reminder['expected_amount']}")
            print(f"  Confidence: {reminder['confidence_score']:.0%}")
            print()

if __name__ == "__main__":
    test_patterns()
