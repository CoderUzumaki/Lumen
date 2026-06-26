"""Create email_configs table"""
from app import app
from models.database import db
from models import EmailConfig

if __name__ == '__main__':
    with app.app_context():
        # Create all tables
        db.create_all()
        print("✅ Database tables created successfully!")
        print("✅ EmailConfig table is ready")
