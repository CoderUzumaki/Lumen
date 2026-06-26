import logging

from flask import Flask
from flask_sqlalchemy import SQLAlchemy

from config import Config

logger = logging.getLogger(__name__)

db = SQLAlchemy()


def init_db(app: Flask):

    app.config["SQLALCHEMY_DATABASE_URI"] = Config.DATABASE_URI
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    # Create tables (with error handling for connection issues)
    try:
        with app.app_context():
            db.create_all()
            logger.info("✅ Database connected and tables initialized")
    except Exception as e:
        logger.warning(f"⚠️  Warning: Could not connect to database: {e}")
        logger.info("   Database features will be unavailable")
