# sql_agent.py
import logging
import re
from typing import Any, Dict

from sqlalchemy import create_engine

from config import Config
from utils.llm import LLMError, chat_completion

logger = logging.getLogger(__name__)

_FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|REPLACE|ATTACH|DETACH|"
    r"PRAGMA|VACUUM|REINDEX|GRANT|REVOKE|TRUNCATE)\b",
    re.IGNORECASE,
)
_ALLOWED_TABLES = frozenset({"transactions", "transaction_items"})
_MAX_ROWS = 100

# Matches every `user_id = 'X'` or `user_id="X"` occurrence (case-insensitive,
# tolerant of surrounding whitespace). Used to enforce that the LLM cannot smuggle
# a second user's id into an OR clause. Group 1 is the quoted value.
_USER_ID_LITERAL_RE = re.compile(
    r"""user_id \s* = \s* (?:'([^']*)'|"([^"]*)")""",
    re.IGNORECASE | re.VERBOSE,
)
# Catches non-equality comparisons on user_id (e.g. `user_id != 'me'`,
# `user_id IN (...)`, `user_id LIKE '%'`) — the LLM is expected to use plain
# equality only; anything else may be a bypass attempt.
_USER_ID_OTHER_OP_RE = re.compile(
    r"""user_id \s* (?: != | <> | \bLIKE\b | \bIN\b | \bNOT\b )""",
    re.IGNORECASE | re.VERBOSE,
)


class SQLValidationError(ValueError):
    pass


def _first_select_statement(text: str) -> str:
    """Keep only the first SELECT statement from a model reply.

    Models often wrap the query in prose or append a second statement. What
    this returns is still validated by _validate_sql before it runs.
    """
    match = re.search(r"\bSELECT\b", text, re.IGNORECASE)
    if not match:
        return text
    return text[match.start():].split(";", 1)[0].strip()


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

    uid = str(user_id)

    # Reject anything other than plain `user_id = '...'` equality. Without this,
    # constructs like `user_id IN ('me','you')` or `user_id != 'me'` bypass the
    # authenticated-user check further down.
    if _USER_ID_OTHER_OP_RE.search(cleaned):
        raise SQLValidationError("Query must compare user_id with plain equality only")

    # Every user_id reference must equal the authenticated user. This rules out
    # `WHERE user_id = 'me' OR user_id = 'someone-else'`, which the previous
    # substring check would accept because the authenticated id does appear.
    matches = _USER_ID_LITERAL_RE.findall(cleaned)
    if not matches:
        raise SQLValidationError("Query must filter by authenticated user_id")
    for single, double in matches:
        value = single or double
        if value != uid:
            raise SQLValidationError(
                "Query references a user_id other than the authenticated one"
            )

    if "limit" not in lower:
        cleaned = f"{cleaned} LIMIT {_MAX_ROWS}"

    return cleaned


class SQLAgent:
    """Converts natural language to SQL and executes queries safely."""

    def __init__(self, db_path: str | None = None):
        # No path: the app's own database (Postgres on Render via DATABASE_URL,
        # local SQLite otherwise). A path forces that SQLite file (tests).
        uri = f"sqlite:///{db_path}" if db_path else Config.DATABASE_URI
        self.engine = create_engine(uri, pool_pre_ping=True)
        self.dialect = "postgresql" if self.engine.dialect.name == "postgresql" else "sqlite"

    # Rules 2 and 8 differ by database; see _DIALECT_RULES.
    _DIALECT_RULES = {
        "sqlite": {
            "name": "SQLite",
            "date_rule": "Use SQLite date functions (date(), datetime(), strftime())",
            "case_rule": (
                "SQLite `=` on text is case-sensitive: compare category, vendor_name and\n"
                "       payment_method case-insensitively, e.g. LOWER(category) = 'groceries'\n"
                "       or vendor_name LIKE '%starbucks%'"
            ),
        },
        "postgresql": {
            "name": "PostgreSQL",
            "date_rule": (
                "Use PostgreSQL date functions. `date` is TEXT, so cast it: date::date,\n"
                "       e.g. to_char(date::date, 'YYYY-MM') or date::date >= CURRENT_DATE - INTERVAL '30 days'.\n"
                "       Never use strftime() or date('now')"
            ),
            "case_rule": (
                "Text `=` is case-sensitive: compare category, vendor_name and\n"
                "       payment_method case-insensitively, e.g. LOWER(category) = 'groceries'\n"
                "       or vendor_name ILIKE '%starbucks%'"
            ),
        },
    }

    SQL_GENERATION_PROMPT = """
    You are an expert SQL query generator for a financial transactions database using {dialect_name}.

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
      * category (TEXT) - Title Case, e.g. Groceries, Restaurant, Utilities,
        Transport, Healthcare, Shopping, Entertainment, Other
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
    2. {date_rule}
    3. Return ONLY the SQL query, no explanation
    4. Use LIMIT 100 or less
    5. SELECT only — never INSERT, UPDATE, DELETE, or DDL
    6. Only query tables: transactions, transaction_items
    7. Use single quotes for string literals
    8. {case_rule}
    9. Wrap aggregates in COALESCE so empty results read as 0, e.g.
       COALESCE(SUM(total_amount), 0) AS total_spent

    User Question: {query}
    Current Date: {current_date}

    Generate SQL query:
    """

    @staticmethod
    def _fallback_sql(user_id: str) -> str:
        """Server-built query for the user's recent transactions, used when the
        model's SQL is unusable so the answer is based on real data."""
        safe_uid = str(user_id).replace("'", "''")
        return (
            f"SELECT id, vendor_name, total_amount, date, category "
            f"FROM transactions WHERE user_id = '{safe_uid}' "
            f"ORDER BY date DESC LIMIT 10"
        )

    def generate_sql(self, query: str, user_id: str) -> str:
        from datetime import datetime

        safe_uid = str(user_id).replace("'", "''")
        fallback = self._fallback_sql(user_id)
        rules = self._DIALECT_RULES[self.dialect]
        try:
            sql = chat_completion(
                self.SQL_GENERATION_PROMPT.format(
                    dialect_name=rules["name"],
                    date_rule=rules["date_rule"],
                    case_rule=rules["case_rule"],
                    query=query,
                    user_id=safe_uid,
                    current_date=datetime.now().strftime("%Y-%m-%d"),
                ),
                temperature=0,
                max_tokens=500,
            )
        except LLMError as e:
            if e.is_fatal:
                # Provider is down or the key is bad; the answer step would fail
                # too, so let the caller report it instead of guessing.
                raise
            logger.warning("SQL generation returned nothing usable (%s); using recent-transactions fallback", e)
            return fallback

        return sql.replace("```sql", "").replace("```", "").strip()

    def execute_sql(self, sql: str, user_id: str) -> Dict[str, Any]:
        """Validate and execute SQL, returning results."""
        try:
            safe_sql = _validate_sql(sql, user_id)
        except SQLValidationError as e:
            logger.warning("Rejected unsafe SQL for user %s: %s", user_id, e)
            return {"success": False, "rejected": True, "error": "Query could not be executed safely"}

        try:
            with self.engine.connect() as conn:
                # Send the model's SQL to the driver verbatim. Without
                # no_parameters, psycopg2 would read the % in ILIKE '%x%' as a
                # placeholder.
                result = conn.execution_options(no_parameters=True).exec_driver_sql(safe_sql)
                rows = result.mappings().all()
            results = [dict(row) for row in rows]

            return {"success": True, "data": results, "row_count": len(results)}

        except Exception as e:
            logger.warning("SQL execution failed: %s", e)
            return {"success": False, "error": "Query execution failed"}

    def query(self, natural_language_query: str, user_id: str) -> Dict[str, Any]:
        """Full pipeline: NL → SQL → Results (SQL never returned to clients)."""
        sql = _first_select_statement(self.generate_sql(natural_language_query, user_id))
        result = self.execute_sql(sql, user_id)
        if result.get("rejected"):
            # Don't let a malformed model reply turn into "you have no data".
            result = self.execute_sql(self._fallback_sql(user_id), user_id)
            result["note"] = (
                "The question could not be turned into a precise query; these "
                "are the user's most recent transactions."
            )
        return result
