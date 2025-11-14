from models import Transaction, TransactionItem
from models.database import db
import uuid

def save_transaction(user_id, normalized):
    """Save transaction to SQLite database with string UUIDs"""
    tx = Transaction(
        id=str(uuid.uuid4()),
        user_id=str(user_id),  # Ensure user_id is string
        vendor_name=normalized["vendor_name"],
        invoice_number=normalized["invoice_number"],
        date=normalized["date"],
        total_amount=normalized["total_amount"],
        tax_amount=normalized.get("tax_amount"),
        payment_method=normalized.get("payment_method"),
        address=normalized.get("address"),
        category=normalized.get("category")
    )

    db.session.add(tx)
    db.session.commit()

    for item in normalized["items"]:
        db.session.add(TransactionItem(
            id=str(uuid.uuid4()),
            transaction_id=tx.id,
            item_name=item["item_name"],
            quantity=item["quantity"],
            unit_price=item["unit_price"],
            total_price=item["total_price"]
        ))

    db.session.commit()
    
    # Add to ChromaDB for semantic search
    try:
        from ai.rag_system import RAGSystem
        rag = RAGSystem()
        rag.add_transaction({
            'id': tx.id,
            'user_id': str(user_id),
            'vendor_name': tx.vendor_name,
            'category': tx.category,
            'total_amount': tx.total_amount,
            'date': tx.date,
            'items': normalized["items"],
            'payment_method': tx.payment_method,
            'invoice_number': tx.invoice_number,
            'address': tx.address
        })
    except Exception as e:
        print(f"⚠️  Warning: Failed to add transaction to ChromaDB: {e}")
        print("   Transaction saved to SQLite but not available for semantic search")

    return tx.id
