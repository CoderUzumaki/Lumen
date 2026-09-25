from models import Transaction, TransactionItem, User
from models.database import db
import uuid
import logging

logger = logging.getLogger(__name__)


def _ensure_user(uid, email=None):
    """Lazy-create the local mirror of the Supabase user.

    `transactions.user_id` is a foreign key to `users.id`. SQLite doesn't
    enforce it, but Postgres does, so without this row a new user's first
    invoice fails to save in production.
    """
    if db.session.get(User, uid):
        return
    if not email or User.query.filter_by(email=email).first():
        email = f"{uid}@users.lumen.local"  # email is NOT NULL and unique
    db.session.add(User(id=uid, email=email))
    db.session.flush()


def find_duplicate(uid, normalized):
    """An earlier upload of the same invoice, or None.

    Only invoices with a number can be matched: two receipts from the same shop
    without one are different purchases, not a re-upload.
    """
    if not normalized.get("invoice_number"):
        return None
    return Transaction.query.filter_by(
        user_id=uid,
        vendor_name=normalized["vendor_name"],
        invoice_number=normalized["invoice_number"],
    ).first()


def save_transaction(user_id, normalized, email=None):
    """Save transaction atomically with per-user deduplication. Returns its id."""
    transaction_id, _created = save_transaction_detailed(user_id, normalized, email=email)
    return transaction_id


def save_transaction_detailed(user_id, normalized, email=None):
    """Like save_transaction, but returns (id, created); created is False for a re-upload."""
    uid = str(user_id)
    try:
        existing = find_duplicate(uid, normalized)
        if existing:
            logger.info(
                "Invoice %s from %s already exists for user %s (ID: %s)",
                normalized["invoice_number"],
                normalized["vendor_name"],
                uid,
                existing.id,
            )
            return existing.id, False

        _ensure_user(uid, email)

        tx = Transaction(
            id=str(uuid.uuid4()),
            user_id=uid,
            vendor_name=normalized["vendor_name"],
            invoice_number=normalized["invoice_number"],
            date=normalized["date"],
            total_amount=normalized["total_amount"],
            tax_amount=normalized.get("tax_amount"),
            payment_method=normalized.get("payment_method"),
            address=normalized.get("address"),
            category=normalized.get("category"),
        )

        db.session.add(tx)

        for item in normalized["items"]:
            db.session.add(
                TransactionItem(
                    id=str(uuid.uuid4()),
                    transaction_id=tx.id,
                    item_name=item["item_name"],
                    quantity=item["quantity"],
                    unit_price=item["unit_price"],
                    total_price=item["total_price"],
                )
            )

        db.session.commit()

        try:
            from ai.rag_system import RAGSystem

            rag = RAGSystem()
            rag.add_transaction(
                {
                    "id": tx.id,
                    "user_id": uid,
                    "vendor_name": tx.vendor_name,
                    "category": tx.category,
                    "total_amount": tx.total_amount,
                    "date": tx.date,
                    "items": normalized["items"],
                    "payment_method": tx.payment_method,
                    "invoice_number": tx.invoice_number,
                    "address": tx.address,
                }
            )
        except Exception as e:
            logger.warning("Failed to add transaction to ChromaDB: %s", e)

        logger.info(
            "Created transaction %s for user %s (invoice %s)",
            tx.id,
            uid,
            normalized["invoice_number"],
        )
        return tx.id, True

    except Exception as e:
        db.session.rollback()
        logger.error("Failed to save transaction: %s", e)
        raise
