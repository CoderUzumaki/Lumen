# sql_agent.py
import logging
import re
from typing import Any, Dict

import sqlglot
from sqlglot import exp
from sqlglot.errors import ErrorLevel
from sqlalchemy import create_engine, event

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

# Supabase user ids are UUIDs; tests use ids like "user-1". The id is written
# into SQL as a literal, so anything else is refused before SQL is built.
_USER_ID_RE = re.compile(r"[A-Za-z0-9-]{1,64}")

_REJECTED = {"success": False, "rejected": True, "error": "Query could not be executed safely"}

# SQLAgent.dialect -> sqlglot dialect name, and the schema holding the real tables.
_SQLGLOT_DIALECTS = {"postgresql": "postgres", "sqlite": "sqlite"}
_SCHEMAS = {"postgresql": "public", "sqlite": "main"}

# Table and CTE names must be plain identifiers; they are rewritten unquoted
# and lower-cased so the database resolves exactly the name that was checked.
_PLAIN_NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

# Functions that read server files or settings, sleep, lock, open connections,
# or run SQL passed to them as text (query_to_xml, ts_stat, crosstab, dblink).
_FORBIDDEN_FUNCTION_PREFIXES = (
    "pg_", "lo_", "dblink", "current_setting", "set_config",
    "ts_stat", "ts_rewrite", "crosstab", "connectby", "http",
    "load_extension", "fts3_tokenizer", "readfile", "writefile",
)

# Nodes that change data or state; none belong anywhere in a read query.
_FORBIDDEN_NODES = (
    exp.DML, exp.DDL, exp.Command, exp.Drop, exp.Alter, exp.Pragma, exp.Set,
    exp.Into, exp.Lock, exp.Transaction, exp.Commit, exp.Rollback, exp.Use,
    exp.Describe,
)

# Server-side timeout for one Ask Lumen query on Postgres.
_STATEMENT_TIMEOUT = "5s"

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


# Where the query starts in a model reply: a CTE header (`WITH name AS (`)
# or the first SELECT, whichever comes first.
_QUERY_START_RE = re.compile(
    r"""\bWITH \s+ (?:RECURSIVE\s+)? (?:\w+|"[^"]+") \s* (?:\([^()]*\)\s*)?
        AS \s* (?:NOT\s+)? (?:MATERIALIZED\s*)? \(
      | \bSELECT\b""",
    re.IGNORECASE | re.VERBOSE,
)
# Names the query defines as CTEs (`WITH name AS (`, `, name AS (`).
_CTE_NAME_RE = re.compile(
    r"""(?:\bWITH\s+(?:RECURSIVE\s+)?|,\s*) (\w+) \s* (?:\([^()]*\)\s*)?
        AS \s* (?:NOT\s+)? (?:MATERIALIZED\s*)? \(""",
    re.IGNORECASE | re.VERBOSE,
)


class SQLValidationError(ValueError):
    pass


def _is_valid_user_id(user_id) -> bool:
    return isinstance(user_id, str) and _USER_ID_RE.fullmatch(user_id) is not None


def _first_select_statement(text: str) -> str:
    """Keep only the first query (SELECT, or WITH ... SELECT) from a model reply.

    Models often wrap the query in prose or append a second statement. What
    this returns is still validated by _validate_sql before it runs.
    """
    match = _QUERY_START_RE.search(text)
    if not match:
        return text
    return text[match.start():].split(";", 1)[0].strip()


def _validate_sql(sql: str, user_id: str) -> str:
    """Validate LLM-generated SQL before execution.

    A first, textual layer only. Isolation comes from _scope_to_user, which
    parses the query and runs it against per-user CTEs.
    """
    cleaned = sql.strip().rstrip(";").strip()
    if not cleaned:
        raise SQLValidationError("Empty SQL query")

    if ";" in cleaned:
        raise SQLValidationError("Multiple SQL statements are not allowed")

    if not re.match(r"^\s*(?:SELECT|WITH)\b", cleaned, re.IGNORECASE):
        raise SQLValidationError("Only SELECT queries are allowed")

    if _FORBIDDEN.search(cleaned):
        raise SQLValidationError("Query contains forbidden SQL keywords")

    # Only allow known tables and the query's own CTEs (rough check; blocks
    # sqlite_master etc.). _scope_to_user checks every table properly.
    lower = cleaned.lower()
    allowed = _ALLOWED_TABLES | {name.lower() for name in _CTE_NAME_RE.findall(cleaned)}
    for token in re.findall(r"\bFROM\b\s+(\w+)", cleaned, re.IGNORECASE):
        if token.lower() not in allowed:
            raise SQLValidationError(f"Table {token!r} is not allowed")
    for token in re.findall(r"\bJOIN\b\s+(\w+)", cleaned, re.IGNORECASE):
        if token.lower() not in allowed:
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


def _plain_name(identifier) -> str:
    """Lower-case a table or CTE name and write it back unquoted.

    Postgres treats "Users" and users as different names, so the name the
    checks compare must be the name the database resolves.
    """
    name = identifier.name if isinstance(identifier, exp.Identifier) else ""
    if not _PLAIN_NAME_RE.fullmatch(name):
        raise SQLValidationError(f"Unsupported table name {name!r}")
    name = name.lower()
    identifier.set("this", name)
    identifier.set("quoted", False)
    return name


def _check_function(node: exp.Func) -> None:
    if isinstance(node, (exp.Anonymous, exp.AnonymousAggFunc)):
        if isinstance(node.this, exp.Identifier) and node.this.quoted:
            raise SQLValidationError("Quoted function names are not allowed")
        names = {node.name.lower()}
    else:
        # Functions sqlglot knows; match its names for them too (e.g. xmltable).
        names = {node.key, *(n.lower() for n in node.sql_names())}
    for name in names:
        if name.startswith(_FORBIDDEN_FUNCTION_PREFIXES) or "xml" in name:
            raise SQLValidationError(f"Function {name!r} is not allowed")


def _check_nodes(tree: exp.Expression) -> None:
    for node in tree.walk():
        if isinstance(node, _FORBIDDEN_NODES):
            raise SQLValidationError(f"{node.key.upper()} is not allowed")
        if isinstance(node, exp.With) and any(
            node.args.get(k) for k in ("recursive", "search", "udfs")
        ):
            raise SQLValidationError("WITH RECURSIVE is not allowed")
        if isinstance(node, exp.Func):
            _check_function(node)
        if isinstance(node, exp.Dot) and isinstance(node.expression, exp.Func):
            raise SQLValidationError("Schema-qualified functions are not allowed")
        if isinstance(node, exp.In) and node.args.get("field") is not None:
            # SQLite's `x IN users` reads a table without a FROM.
            raise SQLValidationError("IN <table> is not allowed")


def _check_tables(node: exp.Expression, ctes: frozenset) -> None:
    """Every table must be transactions, transaction_items or a CTE visible
    where it is used.

    A CTE body sees only the CTEs defined before it: Postgres resolves a later
    (or its own) name to the real table of that name, and a CTE defined inside
    a subquery is not visible outside it.
    """
    if isinstance(node, exp.Table):
        if not isinstance(node.this, exp.Identifier):
            raise SQLValidationError("Table functions are not allowed")
        if node.args.get("db") is not None or node.args.get("catalog") is not None:
            raise SQLValidationError("Schema-qualified tables are not allowed")
        name = _plain_name(node.this)
        if name not in _ALLOWED_TABLES and name not in ctes:
            raise SQLValidationError(f"Table {name!r} is not allowed")

    with_ = node.args.get("with_")
    if isinstance(with_, exp.With):
        visible = set(ctes)
        for cte in with_.expressions:
            _check_tables(cte.this, frozenset(visible))
            alias = cte.args.get("alias")
            name = _plain_name(alias.this if alias is not None else None)
            if name in _ALLOWED_TABLES:
                raise SQLValidationError(f"CTE {name!r} would replace a scoped table")
            visible.add(name)
        ctes = frozenset(visible)

    for child in node.iter_expressions():
        if child is not with_:
            _check_tables(child, ctes)


def _scope_to_user(sql: str, user_id: str, dialect: str) -> str:
    """Check the model's query and return it rewritten to see one user's rows.

    Raises SQLValidationError unless `sql` is one SELECT (or a set operation of
    SELECTs) that reads only transactions, transaction_items and its own CTEs
    and calls none of the forbidden functions. Parse errors are rejections.
    """
    if not _is_valid_user_id(user_id):
        raise SQLValidationError("Malformed user id")
    read = _SQLGLOT_DIALECTS[dialect]
    try:
        statements = [s for s in sqlglot.parse(sql, read=read) if s is not None]
    except Exception as e:  # ParseError, TokenError, RecursionError on absurd nesting
        raise SQLValidationError(f"Query could not be parsed: {e}") from e
    if len(statements) != 1:
        raise SQLValidationError("Exactly one statement is allowed")
    tree = statements[0]
    if not isinstance(tree, (exp.Select, exp.SetOperation)):
        raise SQLValidationError("Only SELECT queries are allowed")
    try:
        _check_nodes(tree)
        _check_tables(tree, frozenset())
    except RecursionError as e:
        raise SQLValidationError("Query is nested too deeply") from e

    # The model's query runs under two CTEs named after the real tables. A CTE
    # name wins over a table name, so every `transactions` / `transaction_items`
    # it mentions (joins, subqueries, set operations, its own CTEs) reads only
    # this user's rows, and a filter like `user_id = 'me' OR 1=1` can't widen
    # that. The real tables are reachable only schema-qualified, which the
    # checks above refuse in the model's SQL. On Postgres the CTEs are
    # MATERIALIZED so the planner can't push the model's conditions below the
    # user filter and evaluate them on other users' rows.
    schema = _SCHEMAS[dialect]
    as_ = "AS MATERIALIZED" if dialect == "postgresql" else "AS"
    scope = sqlglot.parse_one(
        f"WITH transactions {as_} (SELECT * FROM {schema}.transactions "
        f"WHERE user_id = '{user_id}'), "
        f"transaction_items {as_} (SELECT ti.* FROM {schema}.transaction_items ti "
        f"JOIN {schema}.transactions t ON t.id = ti.transaction_id "
        f"WHERE t.user_id = '{user_id}') SELECT 1",
        read=read,
    ).args["with_"]
    own = tree.args.get("with_")
    if own is not None:
        own.set("expressions", [*scope.expressions, *own.expressions])
    else:
        tree.set("with_", scope)

    # Also cap the rows the database sends; execute_sql caps what it fetches.
    limit = tree.args.get("limit")
    limit_value = limit.expression if isinstance(limit, exp.Limit) else None
    if not (
        isinstance(limit_value, exp.Literal)
        and limit_value.is_int
        and int(limit_value.this) <= _MAX_ROWS
    ):
        tree.set("limit", exp.Limit(expression=exp.Literal.number(_MAX_ROWS)))

    # Run the checked tree, not the model's text: comments and quoting tricks
    # that sqlglot and the database might read differently don't survive.
    try:
        return tree.sql(dialect=read, comments=False, unsupported_level=ErrorLevel.RAISE)
    except Exception as e:
        raise SQLValidationError(f"Query could not be rebuilt: {e}") from e


def _sqlite_query_only(dbapi_conn, _record):
    dbapi_conn.execute("PRAGMA query_only = ON")


class SQLAgent:
    """Converts natural language to SQL and executes queries safely."""

    def __init__(self, db_path: str | None = None):
        # No path: the app's own database (Postgres on Render via DATABASE_URL,
        # local SQLite otherwise). A path forces that SQLite file (tests).
        uri = f"sqlite:///{db_path}" if db_path else Config.DATABASE_URI
        self.engine = create_engine(uri, pool_pre_ping=True)
        self.dialect = "postgresql" if self.engine.dialect.name == "postgresql" else "sqlite"
        if self.dialect == "sqlite":
            # Only model-written SQL runs on this engine; the app's own engine
            # still writes. Postgres gets a read-only transaction per query.
            event.listen(self.engine, "connect", _sqlite_query_only)

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
                # A bad reply already has a fallback query; don't spend a
                # retry of the request's time budget on it.
                timeout=30,
                retries=0,
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
        """Validate, scope to the user and execute SQL, returning results."""
        if not _is_valid_user_id(user_id):
            logger.warning("Refusing to run SQL for a malformed user id")
            return dict(_REJECTED)
        try:
            safe_sql = _scope_to_user(_validate_sql(sql, user_id), user_id, self.dialect)
        except SQLValidationError as e:
            logger.warning("Rejected unsafe SQL for user %s: %s", user_id, e)
            return dict(_REJECTED)

        try:
            with self.engine.connect() as conn:
                if self.dialect == "postgresql":
                    # Behind the checks above: whatever the model wrote can't
                    # write, and can't hold the worker for long.
                    conn.exec_driver_sql("SET TRANSACTION READ ONLY")
                    conn.exec_driver_sql(f"SET LOCAL statement_timeout = '{_STATEMENT_TIMEOUT}'")
                # Send the model's SQL to the driver verbatim. Without
                # no_parameters, psycopg2 would read the % in ILIKE '%x%' as a
                # placeholder.
                result = conn.execution_options(no_parameters=True).exec_driver_sql(safe_sql)
                # Cap by fetching, whatever LIMIT the query has.
                results = [dict(row) for row in result.mappings().fetchmany(_MAX_ROWS)]

            return {"success": True, "data": results, "row_count": len(results)}

        except Exception as e:
            logger.warning("SQL execution failed: %s", e)
            return {"success": False, "error": "Query execution failed"}

    def query(self, natural_language_query: str, user_id: str) -> Dict[str, Any]:
        """Full pipeline: NL → SQL → Results (SQL never returned to clients)."""
        if not _is_valid_user_id(user_id):
            logger.warning("Refusing Ask Lumen SQL for a malformed user id")
            return dict(_REJECTED)
        sql = _first_select_statement(self.generate_sql(natural_language_query, user_id))
        result = self.execute_sql(sql, user_id)
        if not result.get("success"):
            # Rejected, or failed on the database (e.g. SQLite syntax on
            # Postgres). Don't let that turn into "you have no data".
            result = self.execute_sql(self._fallback_sql(user_id), user_id)
            result["note"] = (
                "The question could not be turned into a precise query; these "
                "are the user's most recent transactions."
            )
        return result
