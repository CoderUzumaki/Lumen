"""
Script to fix the insights table schema
"""
import sys
import os

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from models.database import db

def fix_insights_table():
    """Drop and recreate insights table with correct schema"""
    print("🔧 Fixing insights table schema...")
    
    with app.app_context():
        try:
            # Drop existing table
            db.session.execute(db.text("DROP TABLE IF EXISTS insights"))
            print("   ✓ Dropped old insights table")
            
            # Create new table with correct schema
            db.session.execute(db.text("""
                CREATE TABLE insights (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    insight_type VARCHAR(50) NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    severity VARCHAR(20),
                    metadata TEXT,
                    confidence_score REAL,
                    is_actionable BOOLEAN DEFAULT 0,
                    action_taken BOOLEAN DEFAULT 0,
                    is_read BOOLEAN DEFAULT 0,
                    expires_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            
            db.session.commit()
            print("   ✓ Created new insights table with correct schema")
            print("✅ Insights table fixed successfully!")
            
        except Exception as e:
            print(f"❌ Error: {e}")
            db.session.rollback()
            raise

if __name__ == "__main__":
    fix_insights_table()
