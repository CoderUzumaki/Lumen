import logging

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect, text

from config import Config

logger = logging.getLogger(__name__)

db = SQLAlchemy()


def _migrate_transaction_unique_index(app: Flask) -> None:
    """Move dedup constraint from global (vendor, invoice) to per-user."""
    with app.app_context():
        try:
            inspector = inspect(db.engine)
            indexes = {idx["name"] for idx in inspector.get_indexes("transactions")}
            if "u_vendor_invoice" in indexes:
                db.session.execute(text("DROP INDEX u_vendor_invoice"))
            db.session.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS u_user_vendor_invoice "
                    "ON transactions (user_id, vendor_name, invoice_number)"
                )
            )
            db.session.commit()
            logger.info("Transaction unique index migration applied")
        except Exception as e:
            db.session.rollback()
            logger.warning("Transaction index migration skipped: %s", e)


def init_db(app: Flask):
    app.config["SQLALCHEMY_DATABASE_URI"] = Config.DATABASE_URI
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["MAX_CONTENT_LENGTH"] = Config.MAX_UPLOAD_BYTES

    db.init_app(app)

    try:
        with app.app_context():
            db.create_all()
            _migrate_transaction_unique_index(app)
            logger.info("Database connected and tables initialized")
    except Exception as e:
        logger.warning("Could not connect to database: %s", e)
        logger.info("Database features will be unavailable")
