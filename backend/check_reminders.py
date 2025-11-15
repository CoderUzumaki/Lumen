"""
Check why reminders aren't being generated
"""
import sys
import os
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from ai.pattern_detection import PatternDetectionAgent

def check_reminders():
    """Check reminder generation"""
    print("🔍 Checking Reminder Generation")
    print("=" * 60)
    
    with app.app_context():
        db_path = os.path.join(os.path.dirname(__file__), 'instance', 'lumen.db')
        agent = PatternDetectionAgent(db_path)
        
        today = datetime.now().date()
        print(f"\nToday's Date: {today}")
        
        # Check patterns in database
        conn = agent.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT vendor_name, next_predicted_date, confidence_score, pattern_type
            FROM spending_patterns
            WHERE user_id = 123
            ORDER BY next_predicted_date
        """)
        
        patterns = cursor.fetchall()
        print(f"\nTotal Patterns: {len(patterns)}")
        print("\nPattern Dates:")
        for p in patterns[:10]:
            vendor = p[0] or 'N/A'
            next_date = datetime.fromisoformat(p[1]).date()
            days_until = (next_date - today).days
            print(f"  {vendor}: {next_date} ({days_until} days from now)")
        
        conn.close()
        
        # Try different day ranges
        for days in [7, 14, 30, 60]:
            reminders = agent.generate_reminders(123, days_ahead=days)
            print(f"\nReminders with {days} days ahead: {len(reminders)}")
            if reminders:
                for r in reminders[:3]:
                    print(f"  • {r['title']} - {r['predicted_date']} ({r['days_until']} days)")

if __name__ == "__main__":
    check_reminders()
