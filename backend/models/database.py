import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv

load_dotenv()

db = SQLAlchemy()

def init_db(app: Flask):

    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///lumen.db"
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
