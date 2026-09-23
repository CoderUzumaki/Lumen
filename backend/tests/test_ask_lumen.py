"""Ask Lumen pipeline: LLM provider failures must surface as clear errors."""

import pytest


class _FakeResponse:
    def __init__(self, status, body):
        self.status_code = status
        self._body = body
        self.text = str(body)

    def json(self):
        return self._body


@pytest.mark.parametrize(
    "status, body, kind",
    [
        (401, {"error": {"message": "User not found.", "code": 401}}, "auth"),
        (402, {"error": {"message": "Insufficient credits", "code": 402}}, "insufficient_credits"),
        (429, {"error": {"message": "Rate limit exceeded", "code": 429}}, "rate_limited"),
        (404, {"error": {"message": "No endpoints found for x:free.", "code": 404}}, "config"),
        (502, {"error": {"message": "Provider returned error", "code": 502}}, "unavailable"),
        # OpenRouter sometimes reports failures with HTTP 200 and an error body.
        (200, {"error": {"message": "Rate limit exceeded", "code": 429}}, "rate_limited"),
        (200, {"choices": [{"message": {"content": "   "}}]}, "bad_response"),
    ],
)
def test_chat_completion_maps_provider_failures(monkeypatch, status, body, kind):
    from utils import llm

    monkeypatch.setattr(llm.requests, "post", lambda *a, **k: _FakeResponse(status, body))
    with pytest.raises(llm.LLMError) as excinfo:
        llm.chat_completion("hello")
    assert excinfo.value.kind == kind


def test_chat_completion_retries_once_after_empty_reply(monkeypatch):
    from utils import llm

    replies = iter(
        [
            _FakeResponse(200, {"choices": [{"message": {"content": ""}}]}),
            _FakeResponse(200, {"choices": [{"message": {"content": "ANALYTICAL"}}]}),
        ]
    )
    monkeypatch.setattr(llm.requests, "post", lambda *a, **k: next(replies))
    assert llm.chat_completion("classify") == "ANALYTICAL"


def test_chat_completion_does_not_retry_fatal_errors(monkeypatch):
    from utils import llm

    calls = []

    def dead_key(*a, **k):
        calls.append(1)
        return _FakeResponse(401, {"error": {"message": "User not found.", "code": 401}})

    monkeypatch.setattr(llm.requests, "post", dead_key)
    with pytest.raises(llm.LLMError):
        llm.chat_completion("hi")
    assert len(calls) == 1


def test_chat_completion_sends_fallback_chain(monkeypatch):
    from utils import llm

    monkeypatch.setenv("LLM_TEXT_MODEL", "primary/model:free")
    monkeypatch.setenv("LLM_TEXT_FALLBACK_MODELS", "backup/one:free, primary/model:free,backup/two,backup/three")
    sent = []

    def capture(url, headers, json, timeout):
        sent.append(json)
        return _FakeResponse(200, {"choices": [{"message": {"content": "ok"}}]})

    monkeypatch.setattr(llm.requests, "post", capture)
    llm.chat_completion("hi")
    llm.chat_completion("hi", model="explicit/model")

    # Deduplicated, primary first, capped at OpenRouter's limit of 3.
    assert sent[0]["models"] == ["primary/model:free", "backup/one:free", "backup/two"]
    assert "model" not in sent[0]
    assert sent[1]["model"] == "explicit/model" and "models" not in sent[1]


def test_chat_completion_returns_text(monkeypatch):
    from utils import llm

    body = {"choices": [{"message": {"content": "  42 transactions  "}}]}
    monkeypatch.setattr(llm.requests, "post", lambda *a, **k: _FakeResponse(200, body))
    assert llm.chat_completion("hello") == "42 transactions"


def test_classifier_raises_on_fatal_error_and_falls_back_otherwise(monkeypatch):
    import ai.query_classifier as qc
    from utils.llm import LLMError

    def fail(kind):
        def _raise(*a, **k):
            raise LLMError(kind, "boom")
        return _raise

    # No analytical keyword, so the LLM path is taken.
    question = "coffee at starbucks"

    monkeypatch.setattr(qc, "chat_completion", fail(LLMError.AUTH))
    with pytest.raises(LLMError):
        qc.QueryClassifier().classify(question)

    monkeypatch.setattr(qc, "chat_completion", fail(LLMError.BAD_RESPONSE))
    assert qc.QueryClassifier().classify(question) == "ANALYTICAL"

    monkeypatch.setattr(qc, "chat_completion", lambda *a, **k: "**SEMANTIC**")
    assert qc.QueryClassifier().classify(question) == "SEMANTIC"


def test_semantic_question_falls_back_to_sql_when_index_unavailable(monkeypatch):
    import ai.hybrid_query_engine as hqe

    class Classifier:
        def classify(self, q):
            return "SEMANTIC"

    class Rag:
        def search(self, q, uid):
            return {"success": False, "error": "Semantic search is unavailable", "data": []}

    class Sql:
        called = False

        def query(self, q, uid):
            Sql.called = True
            return {"success": True, "data": [], "row_count": 0}

    engine = hqe.HybridQueryEngine.__new__(hqe.HybridQueryEngine)
    engine.classifier, engine.rag_system, engine.sql_agent = Classifier(), Rag(), Sql()
    monkeypatch.setattr(hqe, "chat_completion", lambda *a, **k: "No transactions yet.")

    result = engine.query("coffee purchases", "user-1")
    assert Sql.called
    assert result["response"] == "No transactions yet."


@pytest.fixture
def authed_client(monkeypatch):
    import utils.auth
    from app import app

    monkeypatch.setattr(
        utils.auth,
        "verify_token",
        lambda token: {"sub": "user-1", "email": "u@example.com", "role": "authenticated"},
    )
    app.config.update({"TESTING": True})
    return app.test_client()


def test_chat_llm_auth_failure_is_503_not_401(authed_client, monkeypatch):
    # A 401 would make the frontend sign the user out; a dead API key is our
    # problem, not an expired session.
    import routes.chat as chat
    from utils.llm import LLMError

    saved = []
    monkeypatch.setattr(chat, "_save_exchange", lambda *a: saved.append(a))

    def dead_key(q, uid):
        raise LLMError(LLMError.AUTH, "OpenRouter HTTP 401: User not found.")

    monkeypatch.setattr(chat.engine, "query", dead_key)

    resp = authed_client.post(
        "/chat", json={"query": "hi"}, headers={"Authorization": "Bearer x.y.z"}
    )
    assert resp.status_code == 503
    body = resp.get_json()
    assert body["code"] == "llm_unavailable"
    assert "User not found" not in body["error"]
    assert saved == []


def test_chat_success_returns_answer_and_saves_history(authed_client, monkeypatch):
    import routes.chat as chat

    saved = []
    monkeypatch.setattr(chat, "_save_exchange", lambda *a: saved.append(a))
    monkeypatch.setattr(
        chat.engine,
        "query",
        lambda q, uid: {
            "query": q,
            "query_type": "ANALYTICAL",
            "raw_results": {"success": True, "data": [], "row_count": 0},
            "response": "You have no transactions yet.",
        },
    )

    resp = authed_client.post(
        "/chat", json={"query": "total spend"}, headers={"Authorization": "Bearer x.y.z"}
    )
    assert resp.status_code == 200
    assert resp.get_json()["data"]["response"] == "You have no transactions yet."
    assert saved == [("user-1", "total spend", "You have no transactions yet.")]


@pytest.fixture
def txn_db(tmp_path):
    import sqlite3

    path = tmp_path / "txns.db"
    conn = sqlite3.connect(path)
    conn.execute(
        "create table transactions (id text, user_id text, date text, total_amount real, "
        "vendor_name text, category text)"
    )
    conn.executemany(
        "insert into transactions values (?,?,?,?,?,?)",
        [
            ("t1", "user-1", "2026-09-05", 2400.0, "Reliance Fresh", "Groceries"),
            ("t2", "user-1", "2026-09-11", 650.0, "Starbucks", "Restaurant"),
            ("t3", "user-2", "2026-09-12", 99999.0, "Other Tenant", "Groceries"),
        ],
    )
    conn.commit()
    conn.close()
    return str(path)


def test_sql_agent_keeps_only_first_statement_from_chatty_reply(txn_db, monkeypatch):
    from ai.sql_agent import SQLAgent

    agent = SQLAgent(txn_db)
    monkeypatch.setattr(
        agent,
        "generate_sql",
        lambda q, uid: (
            "Here is the query:\nSELECT COALESCE(SUM(total_amount), 0) AS total FROM transactions "
            "WHERE user_id = 'user-1' AND LOWER(category) = 'groceries'; "
            "SELECT * FROM transactions"
        ),
    )
    result = agent.query("grocery total", "user-1")
    assert result["success"]
    assert result["data"] == [{"total": 2400.0}]


def test_sql_agent_falls_back_to_recent_transactions_when_sql_rejected(txn_db, monkeypatch):
    from ai.sql_agent import SQLAgent

    agent = SQLAgent(txn_db)
    # No user_id filter: must be rejected, then replaced by the safe fallback.
    monkeypatch.setattr(agent, "generate_sql", lambda q, uid: "SELECT * FROM transactions")
    result = agent.query("coffee purchases", "user-1")
    assert result["success"]
    assert {row["vendor_name"] for row in result["data"]} == {"Reliance Fresh", "Starbucks"}
    assert "note" in result


def test_find_shadowed_keys():
    from config import find_shadowed_keys

    file_values = {"OPENROUTER_API_KEY": "from-file", "PORT": "5000", "EMPTY": ""}
    environ = {"OPENROUTER_API_KEY": "stale-system-key", "PORT": "5000", "EMPTY": "x"}
    assert find_shadowed_keys(file_values, environ) == ["OPENROUTER_API_KEY"]
