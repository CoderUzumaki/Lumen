# sql_agent.py
import logging
import re
import sqlite3
from typing import Any, Dict

import requests

from config import Config

logger = logging.getLogger(__name__)

_FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|REPLACE|ATTACH|DETACH|"
    r"PRAGMA|VACUUM|REINDEX|GRANT|REVOKE|TRUNCATE)\b",
    re.IGNORECASE,
)
_ALLOWED_TABLES = frozenset({"transactions", "transaction_items"})
_MAX_ROWS = 100


class SQLValidationError(ValueError):
    pass


def _validate_sql(sql: str, user_id: str) -> str:
    """Validate LLM-generated SQL before execution."""
    cleaned = sql.strip().rstrip(";").strip()
    if not cleaned:
        raise SQLValidationError("Empty SQL query")

    if ";" in cleaned:
        raise SQLValidationError("Multiple SQL statements are not allowed")

    if not re.match(r"^\s*SELECT\b", cleaned, re.IGNORECASE):
        raise SQLValidationError("Only SELECT queries are allowed")

    if _FORBIDDEN.search(cleaned):
        raise SQLValidationError("Query contains forbidden SQL keywords")

    # Only allow known tables (rough check — blocks sqlite_master etc.)
    lower = cleaned.lower()
    for token in re.findall(r"\bFROM\b\s+(\w+)", cleaned, re.IGNORECASE):
        if token.lower() not in _ALLOWED_TABLES:
            raise SQLValidationError(f"Table {token!r} is not allowed")
    for token in re.findall(r"\bJOIN\b\s+(\w+)", cleaned, re.IGNORECASE):
        if token.lower() not in _ALLOWED_TABLES:
            raise SQLValidationError(f"Table {token!r} is not allowed")

    uid = str(user_id).replace("'", "''")
    if f"user_id = '{uid}'" not in lower and f'user_id="{uid}"' not in lower:
        raise SQLValidationError("Query must filter by authenticated user_id")

    if "limit" not in lower:
        cleaned = f"{cleaned} LIMIT {_MAX_ROWS}"

    return cleaned


class SQLAgent:
    """Converts natural language to SQL and executes queries safely."""

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or str(Config.DATABASE_PATH)

    SQL_GENERATION_PROMPT = """
    You are an expert SQL query generator for a financial transactions database using SQLite.

    Database Schema:
    - Table: transactions
    - Columns:
      * id (TEXT) - UUID as string
      * user_id (TEXT) - UUID as string
      * date (TEXT) - Date as string in YYYY-MM-DD format
      * total_amount (REAL)
      * tax_amount (REAL)
      * vendor_name (TEXT)
      * invoice_number (TEXT)
      * category (TEXT)
      * payment_method (TEXT)
      * address (TEXT)
      * created_at (TEXT) - Timestamp

    - Table: transaction_items
    - Columns:
      * id (TEXT)
      * transaction_id (TEXT) - Foreign key to transactions.id
      * item_name (TEXT)
      * quantity (INTEGER)
      * unit_price (REAL)
      * total_price (REAL)

    Rules:
    1. ALWAYS include: user_id = '{user_id}'
    2. Use SQLite date functions (date(), datetime(), strftime())
    3. Return ONLY the SQL query, no explanation
    4. Use LIMIT 100 or less
    5. SELECT only — never INSERT, UPDATE, DELETE, or DDL
    6. Only query tables: transactions, transaction_items
    7. Use single quotes for string literals

    User Question: {query}
    Current Date: {current_date}

    Generate SQL query:
    """

    def generate_sql(self, query: str, user_id: str) -> str:
        from datetime import datetime

        uid = str(user_id)
        try:
            response = requests.post(
                Config.OPENROUTER_CHAT_URL,
                headers={
                    "Authorization": f"Bearer {Config.OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": Config.get_llm_text_model(),
                    "messages": [
                        {
                            "role": "user",
                            "content": self.SQL_GENERATION_PROMPT.format(
                                query=query,
                                user_id=uid.replace("'", "''"),
                                current_date=datetime.now().strftime("%Y-%m-%d"),
                            ),
                        }
                    ],
                    "temperature": 0,
                    "max_tokens": 500,
                },
                timeout=60,
            )

            result = response.json()

            if "error" in result:
                logger.warning("OpenRouter API error in SQL generation: %s", result["error"])
                safe_uid = uid.replace("'", "''")
                return (
                    f"SELECT id, vendor_name, total_amount, date, category "
                    f"FROM transactions WHERE user_id = '{safe_uid}' "
                    f"ORDER BY date DESC LIMIT 10"
                )

            sql = result["choices"][0]["message"]["content"].strip()
            sql = sql.replace("```sql", "").replace("```", "").strip()
            return sql

        except Exception as e:
            logger.warning("Error generating SQL: %s", e)
            safe_uid = uid.replace("'", "''")
            return (
                f"SELECT id, vendor_name, total_amount, date, category "
                f"FROM transactions WHERE user_id = '{safe_uid}' "
                f"ORDER BY date DESC LIMIT 10"
            )

    def execute_sql(self, sql: str, user_id: str) -> Dict[str, Any]:
        """Validate and execute SQL, returning results."""
        try:
            safe_sql = _validate_sql(sql, user_id)
        except SQLValidationError as e:
            logger.warning("Rejected unsafe SQL for user %s: %s", user_id, e)
            return {"success": False, "error": "Query could not be executed safely"}

        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(safe_sql)

            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            rows = cursor.fetchall()
            results = [dict(zip(columns, row)) for row in rows]

            cursor.close()
            conn.close()

            return {"success": True, "data": results, "row_count": len(results)}

        except Exception as e:
            logger.warning("SQL execution failed: %s", e)
            return {"success": False, "error": "Query execution failed"}

    def query(self, natural_language_query: str, user_id: str) -> Dict[str, Any]:
        """Full pipeline: NL → SQL → Results (SQL never returned to clients)."""
        sql = self.generate_sql(natural_language_query, user_id)
        return self.execute_sql(sql, user_id)
