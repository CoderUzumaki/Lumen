"""
Script to populate the database with sample transaction data
"""
import sys
import os
from datetime import datetime, timedelta
import random

# Add the backend directory (parent of scripts/) to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models.database import db
from models import Transaction, User, Anomaly

# Sample data for realistic transactions
VENDORS = [
    "Amazon", "Walmart", "Target", "Best Buy", "Home Depot",
    "Starbucks", "McDonald's", "Whole Foods", "Costco", "Apple Store",
    "Shell Gas Station", "BP Gas Station", "CVS Pharmacy", "Walgreens",
    "Netflix", "Spotify", "Adobe", "Microsoft", "Google Cloud",
    "Electric Company", "Water Utility", "Internet Provider", "Phone Company",
    "Local Restaurant", "Pizza Hut", "Subway", "Chipotle", "Uber Eats"
]

CATEGORIES = [
    "Groceries", "Electronics", "Gas", "Utilities", "Entertainment",
    "Food & Dining", "Shopping", "Healthcare", "Subscription", "Home Improvement",
    "Transportation", "Services", "Personal Care"
]

PAYMENT_METHODS = ["Credit Card", "Debit Card", "Cash", "Digital Wallet", "Bank Transfer"]

def generate_date(year, month_range=None):
    """Generate a random date in the specified year"""
    if month_range:
        month = random.randint(month_range[0], month_range[1])
    else:
        month = random.randint(1, 12)
    
    day = random.randint(1, 28)  # Safe for all months
    return f"{year}-{month:02d}-{day:02d}"

def generate_amount(category):
    """Generate realistic amounts based on category"""
    amount_ranges = {
        "Groceries": (30, 250),
        "Electronics": (100, 1500),
        "Gas": (35, 85),
        "Utilities": (50, 200),
        "Entertainment": (15, 150),
        "Food & Dining": (10, 120),
        "Shopping": (25, 500),
        "Healthcare": (30, 300),
        "Subscription": (5, 50),
        "Home Improvement": (50, 800),
        "Transportation": (15, 100),
        "Services": (40, 300),
        "Personal Care": (20, 150)
    }
    
    min_amt, max_amt = amount_ranges.get(category, (20, 200))
    return round(random.uniform(min_amt, max_amt), 2)

def clear_database():
    """Clear all existing data"""
    print("🗑️  Clearing database...")
    try:
        # Delete in order to respect foreign key constraints
        Anomaly.query.delete()
        Transaction.query.delete()
        db.session.commit()
        print("✅ Database cleared successfully")
    except Exception as e:
        print(f"❌ Error clearing database: {e}")
        db.session.rollback()
        raise

def create_user_if_not_exists():
    """Create user with id='123' if it doesn't exist"""
    user = User.query.filter_by(id="123").first()
    if not user:
        user = User(
            id="123",
            email="test@lumen.com",
            created_at=datetime.utcnow()
        )
        db.session.add(user)
        db.session.commit()
        print("✅ Created user with id='123'")
    else:
        print("✅ User with id='123' already exists")
    return user

def add_recurring_transactions():
    """Add recurring subscription and utility transactions for pattern detection"""
    print("\n🔄 Adding recurring transactions...")
    
    recurring_vendors = [
        # Monthly subscriptions - same amount, same day of month
        ("Netflix", "Subscription", 15.99, 5),  # 5th of each month
        ("Spotify", "Subscription", 9.99, 10),  # 10th of each month
        ("Adobe", "Subscription", 52.99, 15),   # 15th of each month
        ("Microsoft", "Subscription", 6.99, 1),  # 1st of each month
        
        # Monthly utilities - varying amounts, same day range
        ("Electric Company", "Utilities", (80, 150), 20),  # Around 20th
        ("Water Utility", "Utilities", (45, 75), 25),      # Around 25th
        ("Internet Provider", "Utilities", 89.99, 1),      # 1st of month
        ("Phone Company", "Utilities", 65.00, 12),         # 12th of month
        
        # Weekly patterns
        ("Starbucks", "Food & Dining", (4.50, 7.50), None),  # Multiple times per week
    ]
    
    recurring_count = 0
    
    # Add recurring transactions for last 12 months (2024-2025)
    for year in [2024, 2025]:
        # Determine month range based on year
        month_range = (1, 12) if year == 2024 else (1, 11)  # Up to November 2025
        
        for month in range(month_range[0], month_range[1] + 1):
            for vendor, category, amount, day in recurring_vendors:
                # Skip if day is None (weekly pattern, handled separately)
                if day is None:
                    continue
                
                # Generate amount (handle tuple for varying amounts)
                if isinstance(amount, tuple):
                    txn_amount = round(random.uniform(amount[0], amount[1]), 2)
                else:
                    txn_amount = amount
                
                # Create date
                # Add some variance to the day (±2 days) to simulate real-world patterns
                actual_day = max(1, min(28, day + random.randint(-2, 2)))
                date = f"{year}-{month:02d}-{actual_day:02d}"
                
                transaction = Transaction(
                    user_id="123",
                    vendor_name=vendor,
                    invoice_number=f"INV-REC-{year}-{month:02d}-{vendor[:4].upper()}",
                    date=date,
                    total_amount=txn_amount,
                    tax_amount=round(txn_amount * 0.08, 2),
                    payment_method="Credit Card",
                    category=category,
                    address=f"Recurring Payment - {vendor}",
                    created_at=datetime.strptime(date, "%Y-%m-%d")
                )
                
                db.session.add(transaction)
                recurring_count += 1
    
    # Add weekly Starbucks purchases (3-4 times per week)
    for year in [2024, 2025]:
        month_range = (1, 12) if year == 2024 else (1, 11)
        
        for month in range(month_range[0], month_range[1] + 1):
            # 3-4 purchases per week, roughly 14-16 per month
            num_purchases = random.randint(14, 16)
            days = random.sample(range(1, 29), num_purchases)
            
            for day in days:
                date = f"{year}-{month:02d}-{day:02d}"
                amount = round(random.uniform(4.50, 7.50), 2)
                
                transaction = Transaction(
                    user_id="123",
                    vendor_name="Starbucks",
                    invoice_number=f"INV-REC-{year}-{month:02d}-{day:02d}-STAR",
                    date=date,
                    total_amount=amount,
                    tax_amount=round(amount * 0.08, 2),
                    payment_method="Credit Card",
                    category="Food & Dining",
                    address="Local Starbucks",
                    created_at=datetime.strptime(date, "%Y-%m-%d")
                )
                
                db.session.add(transaction)
                recurring_count += 1
    
    print(f"   ✓ Added {recurring_count} recurring transactions")
    return recurring_count

def populate_transactions():
    """Populate the database with 30 transactions for 2024 and 30 for 2025"""
    print("\n📝 Creating transaction records...")
    
    transactions_created = 0
    
    # Generate 30 transactions for 2024
    print("\n📅 Generating 2024 transactions...")
    for i in range(30):
        vendor = random.choice(VENDORS)
        category = random.choice(CATEGORIES)
        amount = generate_amount(category)
        date = generate_date(2024)
        
        transaction = Transaction(
            user_id="123",
            vendor_name=vendor,
            invoice_number=f"INV-2024-{random.randint(1000, 9999)}",
            date=date,
            total_amount=amount,
            tax_amount=round(amount * 0.08, 2),  # 8% tax
            payment_method=random.choice(PAYMENT_METHODS),
            category=category,
            address=f"{random.randint(100, 9999)} Main St, City, State {random.randint(10000, 99999)}",
            created_at=datetime.strptime(date, "%Y-%m-%d")
        )
        
        db.session.add(transaction)
        transactions_created += 1
        
        if (i + 1) % 10 == 0:
            print(f"   ✓ Created {i + 1} transactions for 2024")
    
    # Generate 30 transactions for 2025
    print("\n📅 Generating 2025 transactions...")
    for i in range(30):
        vendor = random.choice(VENDORS)
        category = random.choice(CATEGORIES)
        amount = generate_amount(category)
        date = generate_date(2025, month_range=(1, 11))  # Up to November 2025
        
        transaction = Transaction(
            user_id="123",
            vendor_name=vendor,
            invoice_number=f"INV-2025-{random.randint(1000, 9999)}",
            date=date,
            total_amount=amount,
            tax_amount=round(amount * 0.08, 2),
            payment_method=random.choice(PAYMENT_METHODS),
            category=category,
            address=f"{random.randint(100, 9999)} Main St, City, State {random.randint(10000, 99999)}",
            created_at=datetime.strptime(date, "%Y-%m-%d")
        )
        
        db.session.add(transaction)
        transactions_created += 1
        
        if (i + 1) % 10 == 0:
            print(f"   ✓ Created {i + 1} transactions for 2025")
    
    # Add anomalous transactions
    print("\n⚠️  Adding anomalous transactions...")
    anomalous_txns = [
        # Unusually high amounts
        ("Amazon", "Electronics", 2500.00, "2025-11-10", "Unusually high electronics purchase"),
        ("Best Buy", "Electronics", 3200.00, "2025-11-12", "Another high electronics purchase"),
        # Duplicate-like transactions
        ("Netflix", "Subscription", 15.99, "2025-11-05", "Duplicate subscription charge"),
        ("Netflix", "Subscription", 15.99, "2025-11-05", "Duplicate subscription charge"),
        # Unusual time
        ("Walmart", "Groceries", 450.00, "2025-11-14", "Unusually large grocery purchase"),
        # High frequency vendor
        ("Starbucks", "Food & Dining", 12.50, "2025-11-10", "Multiple coffee purchases"),
        ("Starbucks", "Food & Dining", 11.75, "2025-11-10", "Multiple coffee purchases"),
        ("Starbucks", "Food & Dining", 13.25, "2025-11-11", "Multiple coffee purchases"),
    ]
    
    for vendor, category, amount, date, description in anomalous_txns:
        transaction = Transaction(
            user_id="123",
            vendor_name=vendor,
            invoice_number=f"INV-ANOM-{random.randint(1000, 9999)}",
            date=date,
            total_amount=amount,
            tax_amount=round(amount * 0.08, 2),
            payment_method=random.choice(PAYMENT_METHODS),
            category=category,
            address=f"{random.randint(100, 9999)} Main St, City, State {random.randint(10000, 99999)}",
            created_at=datetime.strptime(date, "%Y-%m-%d")
        )
        db.session.add(transaction)
        transactions_created += 1
    
    print(f"   ✓ Added {len(anomalous_txns)} anomalous transactions")
    
    try:
        db.session.commit()
        print(f"\n✅ Successfully created {transactions_created} total transactions")
    except Exception as e:
        print(f"❌ Error creating transactions: {e}")
        db.session.rollback()
        raise

def verify_data():
    """Verify the data was created correctly"""
    print("\n🔍 Verifying data...")
    
    total_count = Transaction.query.filter_by(user_id="123").count()
    count_2024 = Transaction.query.filter_by(user_id="123").filter(
        Transaction.date.like("2024%")
    ).count()
    count_2025 = Transaction.query.filter_by(user_id="123").filter(
        Transaction.date.like("2025%")
    ).count()
    
    print(f"\n📊 Summary:")
    print(f"   Total transactions: {total_count}")
    print(f"   2024 transactions: {count_2024}")
    print(f"   2025 transactions: {count_2025}")
    
    # Show sample transactions
    print("\n📋 Sample transactions:")
    samples = Transaction.query.filter_by(user_id="123").order_by(Transaction.date.desc()).limit(5).all()
    for txn in samples:
        print(f"   • {txn.date} - {txn.vendor_name} - €{txn.total_amount} - {txn.category}")

def main():
    """Main execution function"""
    print("=" * 60)
    print("🚀 Database Population Script")
    print("=" * 60)
    
    with app.app_context():
        # Step 1: Clear existing data
        clear_database()
        
        # Step 2: Ensure user exists
        create_user_if_not_exists()
        
        # Step 3: Add recurring transactions (for pattern detection)
        add_recurring_transactions()
        
        # Step 4: Populate random transactions
        populate_transactions()
        
        # Step 5: Verify
        verify_data()
    
    print("\n" + "=" * 60)
    print("✨ Database population complete!")
    print("=" * 60)

if __name__ == "__main__":
    main()
