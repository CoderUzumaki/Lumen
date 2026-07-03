"""Backfill existing transactions into ChromaDB for semantic search"""
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask

from config import Config
from models.database import db
from models import Transaction, TransactionItem
from ai.rag_system import RAGSystem

# Initialize Flask app pointing at the same DB the running app uses.
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = Config.DATABASE_URI
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

with app.app_context():
    print("🔄 Backfilling ChromaDB with existing transactions...")
    
    # Initialize RAG system
    rag = RAGSystem()
    
    # Get all transactions
    transactions = Transaction.query.all()
    print(f"Found {len(transactions)} transactions to process")
    
    success_count = 0
    error_count = 0
    
    for tx in transactions:
        try:
            # Get transaction items
            items = []
            for item in tx.items:
                items.append({
                    'item_name': item.item_name,
                    'quantity': item.quantity,
                    'unit_price': item.unit_price,
                    'total_price': item.total_price
                })
            
            # Add to ChromaDB
            rag.add_transaction({
                'id': tx.id,
                'user_id': tx.user_id,
                'vendor_name': tx.vendor_name,
                'category': tx.category,
                'total_amount': tx.total_amount,
                'date': tx.date,
                'items': items,
                'payment_method': tx.payment_method,
                'invoice_number': tx.invoice_number,
                'address': tx.address
            })
            success_count += 1
            
            if success_count % 10 == 0:
                print(f"  Processed {success_count} transactions...")
                
        except Exception as e:
            error_count += 1
            print(f"❌ Error processing transaction {tx.id}: {e}")
    
    print(f"\n✅ Backfill complete!")
    print(f"   Success: {success_count}")
    print(f"   Errors: {error_count}")
    print(f"   Total in ChromaDB: {rag.collection.count()}")
