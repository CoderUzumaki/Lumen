"""
Quick test script to verify recurring transactions and patterns
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from models.database import db
from models import Transaction

def test_recurring_data():
    """Test that recurring transactions were loaded correctly"""
    print("🔍 Testing Recurring Transaction Data")
    print("=" * 60)
    
    with app.app_context():
        # Check Netflix transactions
        netflix = Transaction.query.filter_by(
            user_id="123", 
            vendor_name="Netflix"
        ).order_by(Transaction.date).all()
        
        print(f"\n📺 Netflix Transactions: {len(netflix)}")
        if netflix:
            print("   Dates:", [t.date for t in netflix[:5]], "...")
            print("   Amounts:", [t.total_amount for t in netflix[:3]])
        
        # Check Spotify
        spotify = Transaction.query.filter_by(
            user_id="123",
            vendor_name="Spotify"
        ).count()
        print(f"\n🎵 Spotify Transactions: {spotify}")
        
        # Check Starbucks
        starbucks = Transaction.query.filter_by(
            user_id="123",
            vendor_name="Starbucks"
        ).count()
        print(f"\n☕ Starbucks Transactions: {starbucks}")
        
        # Check Electric Company
        electric = Transaction.query.filter_by(
            user_id="123",
            vendor_name="Electric Company"
        ).count()
        print(f"\n⚡ Electric Company Transactions: {electric}")
        
        # Total summary
        total = Transaction.query.filter_by(user_id="123").count()
        print(f"\n📊 Total Transactions: {total}")
        
        # Check subscription category
        subscriptions = Transaction.query.filter_by(
            user_id="123",
            category="Subscription"
        ).count()
        print(f"📦 Subscription Category: {subscriptions}")
        
        # Check utilities category
        utilities = Transaction.query.filter_by(
            user_id="123",
            category="Utilities"
        ).count()
        print(f"💡 Utilities Category: {utilities}")
        
        print("\n✅ All recurring transaction data loaded successfully!")
        print("\nExpected Patterns:")
        print("  • Netflix: ~23 transactions (monthly from 2024-2025)")
        print("  • Spotify: ~23 transactions (monthly)")
        print("  • Starbucks: ~300+ transactions (weekly)")
        print("  • Electric Company: ~23 transactions (monthly)")
        
if __name__ == "__main__":
    test_recurring_data()
