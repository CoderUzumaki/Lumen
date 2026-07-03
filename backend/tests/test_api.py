"""Basic tests for Lumen backend."""

import pytest


@pytest.fixture
def app():
    from app import app as flask_app

    flask_app.config.update({"TESTING": True})
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "healthy"
    assert "OPENROUTER" not in str(data).upper()


def test_chat_requires_auth(client):
    response = client.post("/chat", json={"query": "hello"})
    assert response.status_code == 401


def test_sql_agent_rejects_unsafe_query():
    from ai.sql_agent import _validate_sql, SQLValidationError

    with pytest.raises(SQLValidationError):
        _validate_sql("DELETE FROM transactions", "user-uuid")

    with pytest.raises(SQLValidationError):
        _validate_sql("SELECT * FROM transactions", "user-uuid")

    safe = _validate_sql(
        "SELECT vendor_name FROM transactions WHERE user_id = 'user-uuid'",
        "user-uuid",
    )
    assert "SELECT" in safe.upper()
    assert "LIMIT" in safe.upper()
