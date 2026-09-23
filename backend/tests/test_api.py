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


def test_malformed_token_returns_401_not_500(client):
    # PyJWKClient parses the token header before looking up a key, so junk
    # tokens raise DecodeError there. That must map to 401, not a 500.
    response = client.get(
        "/transactions", headers={"Authorization": "Bearer not.a.jwt"}
    )
    assert response.status_code == 401
    assert response.get_json()["code"] == "malformed_token"


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM transactions WHERE user_id = 'user-uuid' OR user_id = 'other-uuid'",
        "SELECT * FROM transactions WHERE user_id IN ('user-uuid', 'other-uuid')",
        "SELECT * FROM transactions WHERE user_id != 'other-uuid'",
        "SELECT * FROM transactions WHERE user_id LIKE '%'",
    ],
)
def test_sql_agent_rejects_cross_tenant_filters(sql):
    from ai.sql_agent import _validate_sql, SQLValidationError

    with pytest.raises(SQLValidationError):
        _validate_sql(sql, "user-uuid")


def test_rate_limit_key_is_per_user(app):
    import jwt
    from utils.limiter import _rate_limit_key

    token = jwt.encode({"sub": "alice"}, "k" * 32, algorithm="HS256")
    with app.test_request_context("/", headers={"Authorization": f"Bearer {token}"}):
        assert _rate_limit_key() == "user:alice"
    with app.test_request_context("/"):
        assert _rate_limit_key().startswith("ip:")
