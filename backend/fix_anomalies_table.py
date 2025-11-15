"""
Script to fix the anomalies table schema
"""
import sys
import os

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from models.database import db

def fix_anomalies_table():
    """Drop and recreate anomalies table with correct schema"""
    print("🔧 Fixing anomalies table schema...")
    
    with app.app_context():
        try:
            # Drop existing table
            db.session.execute(db.text("DROP TABLE IF EXISTS anomalies"))
            print("   ✓ Dropped old anomalies table")
            
            # Create new table with correct schema
            db.session.execute(db.text("""
                CREATE TABLE anomalies (
                    id TEXT PRIMARY KEY,
                    transaction_id TEXT NOT NULL,
                    user_id TEXT,
                    anomaly_type TEXT,
                    detection_method TEXT,
                    risk_score INTEGER NOT NULL,
                    risk_level TEXT,
                    explanation TEXT,
                    flags TEXT,
                    llm_explanation TEXT,
                    recommendation TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (transaction_id) REFERENCES transactions (id)
                )
            """))
            
            db.session.commit()
            print("   ✓ Created new anomalies table with correct schema")
            print("✅ Anomalies table fixed successfully!")
            
        except Exception as e:
            print(f"❌ Error: {e}")
            db.session.rollback()
            raise

if __name__ == "__main__":
    fix_anomalies_table()
