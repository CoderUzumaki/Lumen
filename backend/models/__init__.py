import uuid
from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from models.database import db


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = db.Column(db.String, unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Receipt(db.Model):
    __tablename__ = "receipts"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("users.id"), nullable=False)

    file_url = db.Column(db.String, nullable=False)
    raw_text = db.Column(db.Text, nullable=True)
    file_type = db.Column(db.String, nullable=True)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User")


class Transaction(db.Model):
    __tablename__ = "transactions"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("users.id"), nullable=False)
    receipt_id = db.Column(UUID(as_uuid=True), db.ForeignKey("receipts.id"), nullable=True)

    vendor_name = db.Column(db.String, nullable=True)
    invoice_number = db.Column(db.String, nullable=True)
    date = db.Column(db.String, nullable=True)

    total_amount = db.Column(db.Float, nullable=True)
    tax_amount = db.Column(db.Float, nullable=True)
    payment_method = db.Column(db.String, nullable=True)

    address = db.Column(db.String, nullable=True)
    category = db.Column(db.String, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("vendor_name", "invoice_number", name="u_vendor_invoice"),
    )

    items = db.relationship("TransactionItem", backref="transaction")
    anomalies = db.relationship("Anomaly", backref="transaction")


class TransactionItem(db.Model):
    __tablename__ = "transaction_items"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transaction_id = db.Column(UUID(as_uuid=True), db.ForeignKey("transactions.id"), nullable=False)

    item_name = db.Column(db.String, nullable=False)
    quantity = db.Column(db.Integer, default=1)
    unit_price = db.Column(db.Float, nullable=True)
    total_price = db.Column(db.Float, nullable=True)


class Anomaly(db.Model):
    __tablename__ = "anomalies"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transaction_id = db.Column(UUID(as_uuid=True), db.ForeignKey("transactions.id"), nullable=False)

    risk_score = db.Column(db.Integer, nullable=False)
    anomalies = db.Column(JSONB)
    explanation = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Insight(db.Model):
    __tablename__ = "insights"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("users.id"))
    transaction_id = db.Column(UUID(as_uuid=True), db.ForeignKey("transactions.id"))

    insight = db.Column(db.Text, nullable=True)
    reminder = db.Column(db.Text, nullable=True)
    advice = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class EmbeddingMeta(db.Model):
    __tablename__ = "embeddings_metadata"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transaction_id = db.Column(UUID(as_uuid=True), db.ForeignKey("transactions.id"))

    # This is the ID you get when adding docs to ChromaDB
    chroma_doc_id = db.Column(db.String, nullable=False)

    chunk_text = db.Column(db.Text, nullable=True)
    # `metadata` is a reserved attribute name on Declarative classes (SQLAlchemy).
    # use `meta` as the Python attribute but keep the DB column name as "metadata"
    meta = db.Column("metadata", JSONB)
<<<<<<< HEAD
    embedding_metadata = db.Column(JSONB)
=======
>>>>>>> 27869b7f88f4aecc2beb6c9ada3c4a2b1e72c57e

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
