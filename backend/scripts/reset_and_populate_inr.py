"""Reset database and populate with Indian currency transactions"""
import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from config import Config
from models.database import db
from models import Transaction, TransactionItem, User
from datetime import datetime, timedelta
import random
import uuid

# Indian vendors and realistic data
INDIAN_VENDORS = [
    ("Reliance Fresh", "Groceries", ["Rice", "Dal", "Vegetables", "Milk", "Bread", "Eggs"]),
    ("Big Bazaar", "Shopping", ["T-Shirt", "Jeans", "Shoes", "Towels", "Bedsheet"]),
    ("Domino's Pizza", "Food & Dining", ["Margherita Pizza", "Garlic Bread", "Coke", "Pasta"]),
    ("Swiggy", "Food & Dining", ["Biryani", "Butter Chicken", "Roti", "Dal Makhani"]),
    ("Café Coffee Day", "Food & Dining", ["Cappuccino", "Sandwich", "Muffin", "Cold Coffee"]),
    ("Flipkart", "E-commerce", ["Mobile Phone", "Headphones", "Power Bank", "USB Cable"]),
    ("Amazon India", "E-commerce", ["Books", "Laptop Bag", "Mouse", "Keyboard"]),
    ("DMart", "Groceries", ["Detergent", "Shampoo", "Soap", "Toothpaste", "Oil"]),
    ("More Supermarket", "Groceries", ["Fruits", "Vegetables", "Cheese", "Butter", "Juice"]),
    ("Pantaloons", "Shopping", ["Shirt", "Trousers", "Belt", "Wallet", "Socks"]),
    ("Zomato", "Food & Dining", ["Dosa", "Idli", "Vada", "Coffee", "Sambar"]),
    ("BookMyShow", "Entertainment", ["Movie Ticket", "Snacks Combo", "Parking"]),
    ("Uber", "Transportation", ["Ride Charge", "Service Fee"]),
    ("Ola Cabs", "Transportation", ["Cab Ride", "Toll Charge"]),
    ("Airtel", "Utilities", ["Mobile Recharge", "Data Pack"]),
    ("BSNL", "Utilities", ["Broadband", "Landline"]),
    ("Tanishq", "Shopping", ["Gold Chain", "Earrings", "Ring"]),
    ("Crossword", "Books & Stationery", ["Novel", "Notebook", "Pen", "Diary"]),
    ("Decathlon", "Sports & Fitness", ["Running Shoes", "Yoga Mat", "Dumbbell", "Sports Bottle"]),
    ("Apollo Pharmacy", "Healthcare", ["Medicines", "Vitamins", "First Aid Kit", "Sanitizer"]),
]

PAYMENT_METHODS = ["UPI", "Credit Card", "Debit Card", "Cash", "Net Banking", "Paytm", "PhonePe", "Google Pay"]

def random_date(start_date, end_date):
    """Generate a random date between start_date and end_date"""
    time_between = end_date - start_date
    days_between = time_between.days
    random_days = random.randint(0, days_between)
    return start_date + timedelta(days=random_days)

def generate_transactions():
    """Generate 35 realistic Indian transactions"""
    transactions = []
    
    start_date = datetime(2024, 4, 5)
    end_date = datetime(2025, 11, 7)
    
    for i in range(35):
        vendor_name, category, items_pool = random.choice(INDIAN_VENDORS)
        
        # Generate transaction date
        txn_date = random_date(start_date, end_date)
        
        # Generate items (1-4 items per transaction)
        num_items = random.randint(1, 4)
        items = []
        subtotal = 0
        
        for _ in range(num_items):
            item_name = random.choice(items_pool)
            quantity = random.randint(1, 3)
            
            # Realistic pricing in INR based on category
            if category == "Groceries":
                unit_price = round(random.uniform(20, 500), 2)
            elif category == "Food & Dining":
                unit_price = round(random.uniform(50, 800), 2)
            elif category == "Shopping":
                unit_price = round(random.uniform(300, 3000), 2)
            elif category == "E-commerce":
                unit_price = round(random.uniform(500, 15000), 2)
            elif category == "Entertainment":
                unit_price = round(random.uniform(200, 500), 2)
            elif category == "Transportation":
                unit_price = round(random.uniform(50, 300), 2)
            elif category == "Utilities":
                unit_price = round(random.uniform(200, 1500), 2)
            elif category == "Healthcare":
                unit_price = round(random.uniform(100, 2000), 2)
            elif category == "Sports & Fitness":
                unit_price = round(random.uniform(500, 5000), 2)
            elif category == "Books & Stationery":
                unit_price = round(random.uniform(50, 800), 2)
            else:
                unit_price = round(random.uniform(100, 1000), 2)
            
            total_price = round(unit_price * quantity, 2)
            subtotal += total_price
            
            items.append({
                "item_name": item_name,
                "quantity": quantity,
                "unit_price": unit_price,
                "total_price": total_price
            })
        
        # Calculate tax (GST 5%, 12%, or 18%)
        gst_rates = [0.05, 0.12, 0.18]
        gst_rate = random.choice(gst_rates)
        tax_amount = round(subtotal * gst_rate, 2)
        total_amount = round(subtotal + tax_amount, 2)
        
        # Generate invoice number
        invoice_number = f"INV-{txn_date.strftime('%Y%m%d')}-{random.randint(1000, 9999)}"
        
        # Random Indian addresses
        addresses = [
            "MG Road, Bangalore, Karnataka 560001",
            "Connaught Place, New Delhi 110001",
            "Marine Drive, Mumbai, Maharashtra 400002",
            "Park Street, Kolkata, West Bengal 700016",
            "Anna Salai, Chennai, Tamil Nadu 600002",
            "Banjara Hills, Hyderabad, Telangana 500034",
            "Sarkhej-Gandhinagar Highway, Ahmedabad, Gujarat 380015",
            "Camp Area, Pune, Maharashtra 411001",
            "Residency Road, Indore, Madhya Pradesh 452001",
            "Civil Lines, Jaipur, Rajasthan 302006"
        ]
        
        transactions.append({
            "vendor_name": vendor_name,
            "invoice_number": invoice_number,
            "date": txn_date.strftime("%Y-%m-%d"),
            "total_amount": total_amount,
            "tax_amount": tax_amount,
            "payment_method": random.choice(PAYMENT_METHODS),
            "address": random.choice(addresses),
            "category": category,
            "items": items,
            "created_at": txn_date  # Use transaction date as created_at
        })
    
    # Sort by date to ensure proper ordering
    transactions.sort(key=lambda x: x["created_at"])
    
    return transactions

def ensure_user_exists(user_id: str, email: str | None = None) -> None:
    """Create a users row so transactions satisfy the FK constraint."""
    if db.session.get(User, user_id):
        print(f"✅ User {user_id} already exists")
        return

    user = User(
        id=user_id,
        email=email or f"seed+{user_id[:8]}@lumen.local",
        created_at=datetime.utcnow(),
    )
    db.session.add(user)
    db.session.commit()
    print(f"✅ Created user row for {user_id}")


def reset_database():
    """Clear all transactions and items"""
    with app.app_context():
        print("🗑️  Deleting all transaction items...")
        TransactionItem.query.delete()
        
        print("🗑️  Deleting all transactions...")
        Transaction.query.delete()
        
        db.session.commit()
        print("✅ Database cleared!")

def populate_database(user_id: str, email: str | None = None):
    """Populate database with new Indian transactions"""
    with app.app_context():
        ensure_user_exists(user_id, email)

        transactions = generate_transactions()
        
        print(f"📝 Creating {len(transactions)} transactions for user {user_id}...")
        
        for txn_data in transactions:
            items_data = txn_data.pop("items")
            created_at = txn_data.pop("created_at")
            
            # Create transaction
            txn = Transaction(
                id=str(uuid.uuid4()),
                user_id=user_id,
                vendor_name=txn_data["vendor_name"],
                invoice_number=txn_data["invoice_number"],
                date=txn_data["date"],
                total_amount=txn_data["total_amount"],
                tax_amount=txn_data["tax_amount"],
                payment_method=txn_data["payment_method"],
                address=txn_data["address"],
                category=txn_data["category"],
                created_at=created_at
            )
            
            db.session.add(txn)
            
            # Create transaction items
            for item_data in items_data:
                item = TransactionItem(
                    id=str(uuid.uuid4()),
                    transaction_id=txn.id,
                    item_name=item_data["item_name"],
                    quantity=item_data["quantity"],
                    unit_price=item_data["unit_price"],
                    total_price=item_data["total_price"]
                )
                db.session.add(item)
            
            print(f"  ✅ {txn_data['vendor_name']} - ₹{txn_data['total_amount']} ({txn_data['date']})")
        
        db.session.commit()
        print(f"\n🎉 Successfully created {len(transactions)} Indian transactions!")
        
        # Show summary
        total = sum(t['total_amount'] for t in transactions)
        print(f"💰 Total amount: ₹{total:,.2f}")
        print(f"📅 Date range: {transactions[0]['date']} to {transactions[-1]['date']}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reset and seed Indian INR demo data")
    parser.add_argument(
        "--user-id",
        default=Config.DEV_USER_ID,
        help="Supabase user UUID to assign transactions to",
    )
    parser.add_argument(
        "--email",
        default=None,
        help="Optional email for the users row (defaults to seed+<id>@lumen.local)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("🇮🇳 INDIAN CURRENCY DATABASE RESET & POPULATION")
    print("=" * 60)
    
    reset_database()
    print()
    populate_database(args.user_id, args.email)
    
    print("\n" + "=" * 60)
    print("✨ Database reset complete!")
    print("=" * 60)
