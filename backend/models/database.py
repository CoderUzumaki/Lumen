import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv

load_dotenv()

db = SQLAlchemy()

def init_db(app: Flask):
    # Get database URL and replace asyncpg with psycopg2 for synchronous operations
    db_url = os.getenv("SUPABASE_DB_URL", "")
    
    # Replace asyncpg driver with psycopg2 for synchronous Flask app
    if "postgresql+asyncpg://" in db_url:
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    elif "postgresql://" not in db_url and "postgresql+psycopg2://" not in db_url:
        # If no postgresql prefix, ensure it's added
        if db_url and not db_url.startswith("postgresql"):
            db_url = f"postgresql://{db_url}"
    
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    # Create tables
    with app.app_context():
        db.create_all()
