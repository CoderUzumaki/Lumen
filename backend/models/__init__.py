from sqlalchemy import (
    Column, String, Integer, Float, DateTime, ForeignKey, 
    UniqueConstraint, JSON
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Receipt(Base):
    __tablename__ = "receipts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    file_url = Column(String, nullable=False)
    raw_text = Column(String, nullable=True)
    file_type = Column(String, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    receipt_id = Column(UUID(as_uuid=True), ForeignKey("receipts.id"), nullable=True)

    vendor_name = Column(String, nullable=True)
    invoice_number = Column(String, nullable=True)

    date = Column(String, nullable=True)

    total_amount = Column(Float, nullable=True)
    tax_amount = Column(Float, nullable=True)
    payment_method = Column(String, nullable=True)

    address = Column(String, nullable=True)
    category = Column(String, nullable=True)  # Grocery, Electronics, etc.

    created_at = Column(DateTime, default=datetime.utcnow)

    # Prevent duplicate invoice numbers across same vendor
    __table_args__ = (
        UniqueConstraint("vendor_name", "invoice_number", name="u_vendor_invoice"),
    )

    items = relationship("TransactionItem", backref="transaction")
    anomalies = relationship("Anomaly", backref="transaction")


class TransactionItem(Base):
    __tablename__ = "transaction_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transaction_id = Column(UUID(as_uuid=True), ForeignKey("transactions.id"), nullable=False)

    item_name = Column(String, nullable=False)
    quantity = Column(Integer, default=1)
    unit_price = Column(Float, nullable=True)
    total_price = Column(Float, nullable=True)


class Anomaly(Base):
    __tablename__ = "anomalies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transaction_id = Column(UUID(as_uuid=True), ForeignKey("transactions.id"), nullable=False)

    risk_score = Column(Integer, nullable=False)
    anomalies = Column(JSONB)
    explanation = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)


class Insight(Base):
    __tablename__ = "insights"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    transaction_id = Column(UUID(as_uuid=True), ForeignKey("transactions.id"))

    insight = Column(String, nullable=True)
    reminder = Column(String, nullable=True)
    advice = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)


class EmbeddingMeta(Base):
    __tablename__ = "embeddings_metadata"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transaction_id = Column(UUID(as_uuid=True), ForeignKey("transactions.id"))

    embedding_vector_id = Column(String, nullable=False)  # stores the Vector DB ID
    chunk_text = Column(String, nullable=True)
    metadata = Column(JSONB)

    created_at = Column(DateTime, default=datetime.utcnow)
