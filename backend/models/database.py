import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv

load_dotenv()

db = SQLAlchemy()

def init_db(app: Flask):
<<<<<<< HEAD
    # Get database URL and replace asyncpg with psycopg2 for synchronous operations
    db_url = os.getenv("SUPABASE_DB_URL", "")
    
    # Replace asyncpg driver with psycopg2 for synchronous Flask app
    if "postgresql+asyncpg://" in db_url:
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    elif "postgresql://" not in db_url and "postgresql+psycopg2://" not in db_url:
        # If no postgresql prefix, ensure it's added
        if db_url and not db_url.startswith("postgresql"):
            db_url = f"postgresql://{db_url}"
=======
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
>>>>>>> 27869b7f88f4aecc2beb6c9ada3c4a2b1e72c57e
    
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
