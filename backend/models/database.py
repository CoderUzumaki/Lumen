import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv

load_dotenv()

db = SQLAlchemy()

def init_db(app: Flask):
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("SUPABASE_DB_URL")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    # Create tables
    with app.app_context():
        db.create_all()
