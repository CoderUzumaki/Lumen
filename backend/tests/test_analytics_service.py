"""Analytics summary must run on Postgres too.

`Transaction.date` is a String column holding ISO `YYYY-MM-DD` text, but the
time-range filters were built by comparing it against Python `date` objects.
SQLite silently compares those as strings and the tests pass; Postgres refuses
with `operator does not exist: character varying >= date`. This module seeds
transactions through the ORM, hits `/analytics/summary`, and inspects the
actual parameters bound to the SQL statement so a regression is caught
regardless of which backend the suite happens to run against.
"""
import datetime

import pytest
from sqlalchemy import event

from tests.test_invoice_upload import AUTH, client  # noqa: F401  (fixture: empty db, rate limit off)


@pytest.fixture
def seeded(client):  # noqa: F811 (fixture name shadows import on purpose)
    """user-1 with September 2026 transactions plus one August control row."""
    from app import app
    from models import Transaction, User
    from models.database import db

    with app.app_context():
        db.session.add(User(id="user-1", email="u@example.com"))
        db.session.add_all(
            [
                Transaction(
                    id="t1",
                    user_id="user-1",
                    vendor_name="Reliance Fresh",
                    date="2026-09-05",
                    total_amount=2400.0,
                    category="Groceries",
                ),
                Transaction(
                    id="t2",
                    user_id="user-1",
                    vendor_name="Starbucks",
                    date="2026-09-11",
                    total_amount=650.0,
                    category="Restaurant",
                ),
                # Outside September: must not be counted in the monthly total.
                Transaction(
                    id="t3",
                    user_id="user-1",
                    vendor_name="Other Vendor",
                    date="2026-08-20",
                    total_amount=1000.0,
                    category="Other",
                ),
            ]
        )
        db.session.commit()
    return client


def _flatten(params):
    """Flatten a DBAPI parameter set (dict, tuple, or list of either) to values."""
    if isinstance(params, dict):
        return list(params.values())
    if isinstance(params, (list, tuple)):
        out = []
        for p in params:
            if isinstance(p, (dict, list, tuple)):
                out.extend(_flatten(p))
            else:
                out.append(p)
        return out
    return [params]


def _run_with_captured_params(seeded, url):
    """Call `url` while recording every bound parameter sent to the DB driver.

    We read `context.compiled_parameters` rather than the `parameters` the
    hook is also handed: on SQLite, a `Date`-typed bind is stringified by the
    dialect's own bind processor before it ever reaches the DBAPI, which would
    hide exactly the type-inference bug this test exists to catch (see
    `Transaction.date >= a_date_object` picking up a `Date` bind type from the
    compared value instead of the column's `String` type -- harmless on
    SQLite, `UndefinedFunction` on Postgres). `compiled_parameters` holds the
    raw values before that dialect-specific conversion, so a stray
    `datetime.date` shows up here on every backend alike.
    """
    from app import app
    from models.database import db

    captured = []

    def listener(conn, cursor, statement, parameters, context, executemany):
        for params in context.compiled_parameters:
            captured.append(params)

    with app.app_context():
        engine = db.engine
        event.listen(engine, "before_cursor_execute", listener)
        try:
            response = seeded.get(url, headers=AUTH)
        finally:
            event.remove(engine, "before_cursor_execute", listener)

    values = [v for params in captured for v in _flatten(params)]
    return response, values


# (url, expected current-period total, expected current-period transaction count)
# Week 36 of 2026 (Mon 2026-09-07 .. Sun 2026-09-13) covers only the Starbucks
# row (t2); the full year covers all three seeded rows.
TIME_RANGE_CASES = [
    ("/analytics/summary?time_range=monthly&year=2026&month=8", 3050.0, 2),
    ("/analytics/summary?time_range=weekly&year=2026&week=36", 650.0, 1),
    ("/analytics/summary?time_range=yearly&year=2026", 4050.0, 3),
]


@pytest.mark.parametrize("url, expected_total, expected_count", TIME_RANGE_CASES)
def test_time_range_analytics_binds_iso_date_strings(seeded, url, expected_total, expected_count):
    """The Postgres-only bug: binding datetime.date objects against a String column.

    Also checks the seeded September amounts come back correctly, so the fix
    (comparing ISO strings instead) doesn't silently change results on SQLite.
    """
    response, values = _run_with_captured_params(seeded, url)

    assert response.status_code == 200
    body = response.get_json()
    assert body["current_period"]["total_spending"] == expected_total
    assert body["current_period"]["transaction_count"] == expected_count

    for value in values:
        assert not isinstance(value, (datetime.date, datetime.datetime)), (
            f"bound a {type(value)} against Transaction.date: {value!r}"
        )
