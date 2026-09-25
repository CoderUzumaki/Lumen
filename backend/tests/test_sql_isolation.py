"""Ask Lumen runs model-written SQL on the app database, which also holds other
users' transactions, `users`, `email_configs` (IMAP/OAuth secrets) and
`chat_messages`. Whatever SQL the model writes, the answer may only ever be
built from the signed-in user's own transactions.

generate_sql is replaced with a fixed reply; nothing here calls OpenRouter.
"""
import sqlite3

import pytest

# Strings found only in rows user-1 must never see: user-2's transactions and
# items, and every row of users, email_configs and chat_messages.
LEAKS = (
    "user-2",
    "Other Tenant",
    "99999",
    "Secret Item",
    "u1@example.com",
    "victim@example.com",
    "imap.victim.example",
    "hunter2",
    "oauth-secret",
    "private chat",
)
FALLBACK_IDS = {"t1", "t2"}  # user-1's recent transactions


@pytest.fixture
def db_path(tmp_path):
    """Scratch SQLite database with the app's real tables and two users' rows."""
    from sqlalchemy import create_engine

    from models import ChatMessage, EmailConfig, Transaction, TransactionItem, User
    from models.database import db

    path = tmp_path / "isolation.db"
    engine = create_engine(f"sqlite:///{path}")
    db.metadata.create_all(
        engine,
        tables=[m.__table__ for m in (User, Transaction, TransactionItem, EmailConfig, ChatMessage)],
    )
    engine.dispose()

    conn = sqlite3.connect(path)
    conn.executemany(
        "insert into users (id, email) values (?, ?)",
        [("user-1", "u1@example.com"), ("user-2", "victim@example.com")],
    )
    conn.executemany(
        "insert into transactions (id, user_id, vendor_name, date, total_amount, category) "
        "values (?, ?, ?, ?, ?, ?)",
        [
            ("t1", "user-1", "Reliance Fresh", "2026-09-05", 2400.0, "Groceries"),
            ("t2", "user-1", "Starbucks", "2026-09-11", 650.0, "Restaurant"),
            ("t3", "user-2", "Other Tenant", "2026-09-12", 99999.0, "Groceries"),
            ("t4", "user-2", "Other Tenant Cafe", "2026-09-13", 99999.5, "Restaurant"),
        ],
    )
    conn.executemany(
        "insert into transaction_items (id, transaction_id, item_name, quantity, unit_price, total_price) "
        "values (?, ?, ?, ?, ?, ?)",
        [
            ("i1", "t1", "Basmati Rice", 2, 600.0, 1200.0),
            ("i3", "t3", "Secret Item", 1, 99999.0, 99999.0),
        ],
    )
    conn.execute(
        "insert into email_configs (id, user_id, email_address, imap_server, imap_password, oauth_token) "
        "values (?, ?, ?, ?, ?, ?)",
        ("e2", "user-2", "victim@example.com", "imap.victim.example", "hunter2", "oauth-secret"),
    )
    conn.execute(
        "insert into chat_messages (id, user_id, role, content) values (?, ?, ?, ?)",
        ("c2", "user-2", "user", "private chat about my salary"),
    )
    conn.commit()
    conn.close()
    return str(path)


def _ask(db_path, monkeypatch, sql, user_id="user-1"):
    from ai.sql_agent import SQLAgent

    agent = SQLAgent(db_path)
    monkeypatch.setattr(agent, "generate_sql", lambda q, uid: sql)
    return agent.query("question", user_id)


def _assert_only_user_1(result):
    assert result["success"], result
    text = repr(result["data"])
    for leak in LEAKS:
        assert leak not in text, f"{leak!r} leaked: {text}"
    for row in result["data"]:
        assert row.get("user_id", "user-1") == "user-1"


def _assert_fallback(result):
    _assert_only_user_1(result)
    assert "note" in result
    assert {row["id"] for row in result["data"]} == FALLBACK_IDS


# (model SQL, "scoped" = runs and sees only user-1's rows, "fallback" = refused
# or failed, answered from user-1's recent transactions instead)
ATTACKS = [
    # Precedence slips and tautologies: the WHERE can't widen what the scoping CTE lets through.
    ("SELECT * FROM transactions WHERE user_id = 'user-1' OR 1=1", "scoped"),
    ("SELECT * FROM transactions WHERE user_id = 'user-1' OR TRUE", "scoped"),
    ("SELECT * FROM transactions WHERE user_id = 'user-1' OR user_id > ''", "scoped"),
    (
        "SELECT * FROM transactions WHERE user_id = 'user-1' AND category = 'Restaurant' "
        "OR category = 'Groceries'",
        "scoped",
    ),
    # Other tables, however they are joined in.
    ("SELECT u.email FROM transactions t, users u WHERE t.user_id = 'user-1'", "fallback"),
    ("SELECT * FROM transactions t JOIN \"users\" u ON 1=1 WHERE t.user_id = 'user-1'", "fallback"),
    ("SELECT e.* FROM transactions t, email_configs e WHERE t.user_id = 'user-1'", "fallback"),
    ("SELECT c.content FROM transactions t, chat_messages c WHERE t.user_id = 'user-1'", "fallback"),
    ("SELECT * FROM main.transactions WHERE user_id = 'user-1' OR 1=1", "fallback"),
    ("SELECT * FROM transactions WHERE user_id = 'user-1' AND id IN (SELECT id FROM users)", "fallback"),
    ("WITH RECURSIVE r AS (SELECT 1) SELECT * FROM transactions WHERE user_id = 'user-1'", "fallback"),
    # Only the first statement is kept, and it is scoped.
    ("SELECT * FROM transactions WHERE user_id = 'user-1'; SELECT * FROM users", "scoped"),
    # Mixed case and quoted names still resolve to the scoped CTE.
    ("SELECT * FROM TRANSACTIONS WHERE user_id = 'user-1' OR 1=1", "scoped"),
    ("SELECT * FROM \"Transactions\" WHERE user_id = 'user-1' OR 1=1", "scoped"),
    ("SELECT * FROM \"USERS\" u, transactions t WHERE t.user_id = 'user-1'", "fallback"),
    # Set operations: each side is scoped, other tables are refused.
    (
        "SELECT vendor_name FROM transactions WHERE user_id = 'user-1' "
        "UNION SELECT vendor_name FROM transactions",
        "scoped",
    ),
    (
        "SELECT vendor_name FROM transactions WHERE user_id = 'user-1' UNION SELECT email FROM users",
        "fallback",
    ),
    # Items of other users' transactions are hidden too.
    (
        "SELECT * FROM transaction_items WHERE EXISTS "
        "(SELECT 1 FROM transactions WHERE user_id = 'user-1')",
        "scoped",
    ),
    # CTE scoping: a CTE named like a real table is visible only where SQL
    # says it is. Outside its subquery, after a later sibling, or inside its
    # own body the name means the real table.
    (
        "SELECT vendor_name FROM transactions WHERE user_id = 'user-1' AND EXISTS "
        "(WITH users AS (SELECT 1 AS id) SELECT id FROM users) UNION SELECT email FROM users",
        "fallback",
    ),
    (
        "WITH a AS (SELECT email FROM users), users AS "
        "(SELECT id FROM transactions WHERE user_id = 'user-1') SELECT * FROM a",
        "fallback",
    ),
    ("WITH users AS (SELECT * FROM users) SELECT * FROM transactions WHERE user_id = 'user-1'", "fallback"),
    # A CTE may not replace the scoping CTEs.
    (
        "WITH transactions AS (SELECT * FROM transaction_items) "
        "SELECT * FROM transactions WHERE user_id = 'user-1'",
        "fallback",
    ),
    # SQLite reads tables without FROM: `x IN table`, table-valued functions.
    ("SELECT * FROM transactions WHERE user_id = 'user-1' AND 'user-2' IN users", "fallback"),
    (
        "SELECT p.name FROM transactions t, pragma_table_info('users') p WHERE t.user_id = 'user-1'",
        "fallback",
    ),
    ("SELECT m.sql FROM transactions t, sqlite_master m WHERE t.user_id = 'user-1'", "fallback"),
    (
        "SELECT * FROM transactions t, (SELECT * FROM main.users) u WHERE t.user_id = 'user-1'",
        "fallback",
    ),
]


@pytest.mark.parametrize("sql, outcome", ATTACKS)
def test_model_sql_only_sees_the_users_own_rows(db_path, monkeypatch, sql, outcome):
    result = _ask(db_path, monkeypatch, sql)
    if outcome == "scoped":
        _assert_only_user_1(result)
        assert "note" not in result
        assert result["row_count"] > 0
    else:
        _assert_fallback(result)


@pytest.mark.parametrize("dialect", ["postgresql", "sqlite"])
@pytest.mark.parametrize(
    "sql",
    [
        "SELECT query_to_xml('select * from users', true, true, '') FROM transactions WHERE user_id = 'user-1'",
        "SELECT pg_sleep(600) FROM transactions WHERE user_id = 'user-1'",
        "SELECT PG_SLEEP(600) FROM transactions WHERE user_id = 'user-1'",
        "SELECT pg_catalog.pg_sleep(600) FROM transactions WHERE user_id = 'user-1'",
        "SELECT \"pg_sleep\"(600) FROM transactions WHERE user_id = 'user-1'",
        "SELECT pg_read_file('/etc/passwd') FROM transactions WHERE user_id = 'user-1'",
        "SELECT current_setting('app.settings.jwt_secret') FROM transactions WHERE user_id = 'user-1'",
        "SELECT set_config('statement_timeout', '0', true) FROM transactions WHERE user_id = 'user-1'",
        "SELECT table_to_xml('users', true, true, '') FROM transactions WHERE user_id = 'user-1'",
        "SELECT ts_stat('select to_tsvector(email) from users') FROM transactions WHERE user_id = 'user-1'",
        "SELECT dblink('host=x', 'select 1') FROM transactions WHERE user_id = 'user-1'",
        "SELECT lo_import('/etc/passwd') FROM transactions WHERE user_id = 'user-1'",
        "SELECT net.http_get('http://example.com') FROM transactions WHERE user_id = 'user-1'",
        "SELECT * FROM generate_series(1, 3) WHERE 'user-1' = 'user-1'",
        "SELECT * FROM transactions t, LATERAL (SELECT email FROM users) u WHERE t.user_id = 'user-1'",
        "SELECT * FROM public.transactions WHERE user_id = 'user-1'",
        "SELECT * FROM transactions WHERE user_id = 'user-1' FOR UPDATE",
        "SELECT * INTO stolen FROM transactions WHERE user_id = 'user-1'",
        "SELECT * FROM transactions WHERE user_id = 'user-1'; SELECT * FROM users",
        "DELETE FROM transactions WHERE user_id = 'user-1'",
        "WITH d AS (DELETE FROM users RETURNING *) SELECT * FROM transactions WHERE user_id = 'user-1'",
        "SELECT * FROM transactions WHERE user_id = 'user-1' AND",  # parse error
    ],
)
def test_validator_rejects_dangerous_sql(sql, dialect):
    from ai.sql_agent import SQLValidationError, _scope_to_user

    with pytest.raises(SQLValidationError):
        _scope_to_user(sql, "user-1", dialect)


def test_normal_aggregate(db_path, monkeypatch):
    result = _ask(
        db_path,
        monkeypatch,
        "SELECT COALESCE(SUM(total_amount), 0) AS total, COUNT(*) AS n "
        "FROM transactions WHERE user_id = 'user-1'",
    )
    assert result["data"] == [{"total": 3050.0, "n": 2}]
    assert "note" not in result


def test_models_own_cte(db_path, monkeypatch):
    result = _ask(
        db_path,
        monkeypatch,
        "WITH monthly AS (SELECT strftime('%Y-%m', date) AS month, SUM(total_amount) AS total "
        "FROM transactions WHERE user_id = 'user-1' OR 1=1 GROUP BY month) "
        "SELECT month, total FROM monthly ORDER BY month",
    )
    assert result["data"] == [{"month": "2026-09", "total": 3050.0}]
    assert "note" not in result


def test_models_cte_named_like_a_real_table_is_its_own(db_path, monkeypatch):
    result = _ask(
        db_path,
        monkeypatch,
        "WITH users AS (SELECT vendor_name FROM transactions WHERE user_id = 'user-1') "
        "SELECT vendor_name FROM users ORDER BY vendor_name",
    )
    assert result["data"] == [{"vendor_name": "Reliance Fresh"}, {"vendor_name": "Starbucks"}]


def test_transaction_items_join(db_path, monkeypatch):
    result = _ask(
        db_path,
        monkeypatch,
        "SELECT ti.item_name, ti.total_price FROM transaction_items ti "
        "JOIN transactions t ON t.id = ti.transaction_id WHERE t.user_id = 'user-1' OR 1=1",
    )
    assert result["data"] == [{"item_name": "Basmati Rice", "total_price": 1200.0}]


def test_rows_are_capped_whatever_the_limit(db_path, monkeypatch):
    # 2**7 = 128 rows from a cross join of user-1's two transactions.
    joins = ", ".join(f"transactions t{i}" for i in range(7))
    result = _ask(db_path, monkeypatch, f"SELECT t0.id FROM {joins} WHERE t0.user_id = 'user-1' LIMIT 1000")
    assert result["success"]
    assert result["row_count"] == 100


def test_execution_error_falls_back_to_recent_transactions(db_path, monkeypatch):
    result = _ask(db_path, monkeypatch, "SELECT no_such_column FROM transactions WHERE user_id = 'user-1'")
    _assert_fallback(result)


@pytest.mark.parametrize("user_id", ["x' OR '1'='1", "user-1\n", "", "a" * 65, "user_1", None])
def test_malformed_user_id_is_rejected_before_any_sql(db_path, monkeypatch, user_id):
    from ai.sql_agent import SQLAgent

    agent = SQLAgent(db_path)

    def must_not_run(*a, **k):
        raise AssertionError("no SQL may be generated or run for a malformed user id")

    monkeypatch.setattr(agent, "generate_sql", must_not_run)
    monkeypatch.setattr(agent.engine, "connect", must_not_run)

    result = agent.query("question", user_id)
    assert result["success"] is False and result["rejected"] is True
    assert "data" not in result
    assert agent.execute_sql("SELECT * FROM transactions", user_id)["rejected"] is True


def test_sqlite_connection_is_read_only(db_path):
    from sqlalchemy.exc import OperationalError

    from ai.sql_agent import SQLAgent

    agent = SQLAgent(db_path)
    with agent.engine.connect() as conn:
        with pytest.raises(OperationalError, match="readonly"):
            conn.exec_driver_sql("DELETE FROM users")


def test_postgres_query_runs_read_only_with_a_timeout():
    from ai.sql_agent import SQLAgent

    class Result:
        def mappings(self):
            return self

        def fetchmany(self, size):
            conn.fetched = size
            return [{"total": 1.0}]

    class Conn:
        def __init__(self):
            self.sql, self.options, self.fetched = [], {}, None

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def execution_options(self, **options):
            self.options.update(options)
            return self

        def exec_driver_sql(self, sql):
            self.sql.append(sql)
            return Result()

    conn = Conn()
    agent = SQLAgent.__new__(SQLAgent)
    agent.dialect = "postgresql"
    agent.engine = type("Engine", (), {"connect": lambda self: conn})()

    result = agent.execute_sql(
        "SELECT ROUND(SUM(total_amount)::numeric, 2) AS total FROM transactions "
        "WHERE user_id = 'user-1' AND vendor_name ILIKE '%star%'",
        "user-1",
    )
    assert result == {"success": True, "data": [{"total": 1.0}], "row_count": 1}
    assert conn.sql[:2] == ["SET TRANSACTION READ ONLY", "SET LOCAL statement_timeout = '5s'"]
    assert conn.sql[2].startswith(
        "WITH transactions AS MATERIALIZED (SELECT * FROM public.transactions WHERE user_id = 'user-1'), "
        "transaction_items AS MATERIALIZED (SELECT ti.* FROM public.transaction_items AS ti "
        "JOIN public.transactions AS t ON t.id = ti.transaction_id WHERE t.user_id = 'user-1') SELECT "
    )
    assert "ILIKE '%star%'" in conn.sql[2]
    assert conn.options == {"no_parameters": True}
    assert conn.fetched == 100


def test_scoping_ctes_come_before_the_models_own():
    from ai.sql_agent import _scope_to_user

    sql = _scope_to_user(
        "WITH monthly AS (SELECT 1 AS n FROM transactions WHERE user_id = 'user-1') SELECT n FROM monthly",
        "user-1",
        "sqlite",
    )
    assert sql.startswith(
        "WITH transactions AS (SELECT * FROM main.transactions WHERE user_id = 'user-1'), "
        "transaction_items AS (SELECT ti.* FROM main.transaction_items AS ti "
        "JOIN main.transactions AS t ON t.id = ti.transaction_id WHERE t.user_id = 'user-1'), "
        "monthly AS ("
    )


def test_table_names_are_rewritten_as_checked():
    # Postgres reads "Users" and users as different tables; the query must use
    # the lower-case, unquoted names that were checked.
    from ai.sql_agent import _scope_to_user

    sql = _scope_to_user(
        'WITH "Mine" AS (SELECT * FROM "TRANSACTIONS" WHERE user_id = \'user-1\') SELECT * FROM "MINE"',
        "user-1",
        "postgresql",
    )
    assert '"' not in sql
    assert "mine AS (SELECT * FROM transactions WHERE" in sql
    assert sql.endswith("SELECT * FROM mine LIMIT 100")


@pytest.mark.parametrize(
    "sql, limit",
    [
        ("SELECT id FROM transactions WHERE user_id = 'user-1' LIMIT 10", "LIMIT 10"),
        ("SELECT id FROM transactions WHERE user_id = 'user-1' LIMIT 5000", "LIMIT 100"),
        ("SELECT id FROM transactions WHERE user_id = 'user-1'", "LIMIT 100"),
    ],
)
def test_limit_is_capped(sql, limit):
    from ai.sql_agent import _scope_to_user

    assert _scope_to_user(sql, "user-1", "sqlite").endswith(limit)


def test_query_start_includes_a_cte_header():
    from ai.sql_agent import _first_select_statement

    reply = "Here is the query with totals as asked:\nWITH m AS (SELECT 1) SELECT * FROM m; SELECT 2"
    assert _first_select_statement(reply) == "WITH m AS (SELECT 1) SELECT * FROM m"
