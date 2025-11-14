import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv

load_dotenv()

db = SQLAlchemy()

def init_db(app: Flask):
    db_url = os.getenv("SUPABASE_DB_URL")
    
    if not db_url:
        print("⚠️  Warning: SUPABASE_DB_URL not found in environment variables")
        print("   Database features will be unavailable")
        return
    
    # Ensure we're using the synchronous psycopg2 driver, not asyncpg
    if "postgresql+asyncpg://" in db_url:
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
    elif db_url.startswith("postgresql://") and "+psycopg2" not in db_url:
        db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    # Create tables (with error handling for connection issues)
    try:
        with app.app_context():
            db.create_all()
            print("✅ Database connected and tables initialized")
    except Exception as e:
        print(f"⚠️  Warning: Could not connect to database: {e}")
        print("   Database features will be unavailable")
