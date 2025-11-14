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

    return tx.id
