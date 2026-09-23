"""
Migrate legacy demo user_id='123' rows to the configured DEV_USER_ID UUID.

Usage:
    python scripts/migrate_demo_user_id.py
    python scripts/migrate_demo_user_id.py --from 123 --to 00000000-0000-0000-0000-000000000123
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from config import Config
from models.database import db
from models import Transaction, AnalyticsInsight, SpendingPattern, ChatMessage, EmailConfig, User


TABLES = [
    (Transaction, "user_id"),
    (AnalyticsInsight, "user_id"),
    (SpendingPattern, "user_id"),
    (ChatMessage, "user_id"),
    (EmailConfig, "user_id"),
]


def migrate(from_id: str, to_id: str) -> None:
    with app.app_context():
        total = 0
        for model, column in TABLES:
            count = model.query.filter_by(**{column: from_id}).update({column: to_id})
            total += count
            if count:
                print(f"  {model.__tablename__}: {count} rows")

        # Ensure a local User mirror exists for the target id
        if not db.session.get(User, to_id):
            db.session.add(User(id=to_id, email=f"dev+{to_id[:8]}@lumen.local"))

        db.session.commit()
        print(f"Migrated {total} rows from user_id={from_id!r} -> {to_id!r}")


def main():
    parser = argparse.ArgumentParser(description="Migrate legacy demo user_id")
    parser.add_argument("--from", dest="from_id", default="123", help="Legacy user id")
    parser.add_argument(
        "--to",
        dest="to_id",
        default=Config.DEV_USER_ID,
        help="Target Supabase-compatible UUID",
    )
    args = parser.parse_args()
    migrate(args.from_id, args.to_id)


if __name__ == "__main__":
    main()
