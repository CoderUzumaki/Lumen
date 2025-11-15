import uuid
from datetime import datetime
from sqlalchemy import String, Text, Integer, Float, DateTime, ForeignKey
from models.database import db
import json


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = db.Column(db.String, unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Receipt(db.Model):
    __tablename__ = "receipts"

    id = db.Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(String(36), db.ForeignKey("users.id"), nullable=False)

    file_url = db.Column(db.String, nullable=False)
    raw_text = db.Column(db.Text, nullable=True)
    file_type = db.Column(db.String, nullable=True)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User")


class Transaction(db.Model):
    __tablename__ = "transactions"

    id = db.Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(String(36), db.ForeignKey("users.id"), nullable=False)
    receipt_id = db.Column(String(36), db.ForeignKey("receipts.id"), nullable=True)

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

    id = db.Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    transaction_id = db.Column(String(36), db.ForeignKey("transactions.id"), nullable=False)

    item_name = db.Column(db.String, nullable=False)
    quantity = db.Column(db.Integer, default=1)
    unit_price = db.Column(db.Float, nullable=True)
    total_price = db.Column(db.Float, nullable=True)


class Anomaly(db.Model):
    __tablename__ = "anomalies"

    id = db.Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    transaction_id = db.Column(String(36), db.ForeignKey("transactions.id"), nullable=False)

    risk_score = db.Column(db.Integer, nullable=False)
    anomalies = db.Column(db.Text)  # Store JSON as TEXT in SQLite
    explanation = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Insight(db.Model):
    __tablename__ = "insights"

    id = db.Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(String(36), db.ForeignKey("users.id"))
    transaction_id = db.Column(String(36), db.ForeignKey("transactions.id"))

    insight = db.Column(db.Text, nullable=True)
    reminder = db.Column(db.Text, nullable=True)
    advice = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class EmbeddingMeta(db.Model):
    __tablename__ = "embeddings_metadata"

    id = db.Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    transaction_id = db.Column(String(36), db.ForeignKey("transactions.id"))

    # This is the ID you get when adding docs to ChromaDB
    chroma_doc_id = db.Column(db.String, nullable=False)

    chunk_text = db.Column(db.Text, nullable=True)
    # `metadata` is a reserved attribute name on Declarative classes (SQLAlchemy).
    # use `meta` as the Python attribute but keep the DB column name as "metadata"
    # Store JSON as TEXT in SQLite
    meta = db.Column("metadata", db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class EmailConfig(db.Model):
    """Email configuration for automated invoice polling"""
    __tablename__ = "email_configs"

    id = db.Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(String(36), db.ForeignKey("users.id"), nullable=False, unique=True)
    
    # Email settings
    email_address = db.Column(db.String, nullable=False)
    provider = db.Column(db.String, default="gmail")  # gmail, outlook, yahoo, custom
    
    # IMAP settings
    imap_server = db.Column(db.String, nullable=False)
    imap_port = db.Column(Integer, default=993)
    imap_username = db.Column(db.String, nullable=True)
    imap_password = db.Column(db.String, nullable=True)  # Encrypted in production
    use_ssl = db.Column(db.Boolean, default=True)
    
    # OAuth settings (for Gmail OAuth)
    oauth_token = db.Column(Text, nullable=True)  # JSON stored as text
    oauth_refresh_token = db.Column(db.String, nullable=True)
    oauth_token_expiry = db.Column(db.DateTime, nullable=True)
    
    # Polling settings
    polling_enabled = db.Column(db.Boolean, default=True)
    polling_interval_minutes = db.Column(Integer, default=5)
    folder_to_watch = db.Column(db.String, default="INBOX")
    mark_as_read = db.Column(db.Boolean, default=True)
    
    # Status tracking
    last_poll_time = db.Column(db.DateTime, nullable=True)
    last_successful_poll = db.Column(db.DateTime, nullable=True)
    last_error = db.Column(Text, nullable=True)
    emails_processed = db.Column(Integer, default=0)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = db.relationship("User")
