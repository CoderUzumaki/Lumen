"""Reasoning defaults and per-call latency/telemetry logging in utils/llm.py."""

import logging

import pytest


class _FakeResponse:
    def __init__(self, status, body):
        self.status_code = status
        self._body = body
        self.text = str(body)

    def json(self):
        return self._body


def test_default_call_turns_reasoning_off(monkeypatch):
    from utils import llm

    sent = []

    def capture(url, headers, json, timeout):
        sent.append(json)
        return _FakeResponse(200, {"choices": [{"message": {"content": "ok"}}]})

    monkeypatch.setattr(llm.requests, "post", capture)
    llm.chat_completion("hi")
    assert sent[0]["reasoning"] == {"enabled": False}


def test_reasoning_none_omits_the_key(monkeypatch):
    from utils import llm

    sent = []

    def capture(url, headers, json, timeout):
        sent.append(json)
        return _FakeResponse(200, {"choices": [{"message": {"content": "ok"}}]})

    monkeypatch.setattr(llm.requests, "post", capture)
    llm.chat_completion("hi", reasoning=None)
    assert "reasoning" not in sent[0]


def test_explicit_reasoning_is_sent_as_is(monkeypatch):
    from utils import llm

    sent = []

    def capture(url, headers, json, timeout):
        sent.append(json)
        return _FakeResponse(200, {"choices": [{"message": {"content": "ok"}}]})

    monkeypatch.setattr(llm.requests, "post", capture)
    llm.chat_completion("hi", reasoning={"effort": "low"})
    assert sent[0]["reasoning"] == {"effort": "low"}


def test_empty_reply_hitting_max_tokens_reports_reasoning_budget(monkeypatch):
    from utils import llm

    body = {
        "model": "nvidia/nemotron-3-ultra-550b-a55b:free",
        "choices": [{"message": {"content": ""}, "finish_reason": "length"}],
        "usage": {
            "prompt_tokens": 42,
            "completion_tokens": 10,
            "completion_tokens_details": {"reasoning_tokens": 10},
        },
    }
    # chat_completion retries BAD_RESPONSE once; the fake returns the same reply both times.
    monkeypatch.setattr(llm.requests, "post", lambda *a, **k: _FakeResponse(200, body))

    with pytest.raises(llm.LLMError) as excinfo:
        llm.chat_completion("classify", max_tokens=10)
    assert excinfo.value.kind == llm.LLMError.BAD_RESPONSE
    assert "hit max_tokens=10" in excinfo.value.detail
    assert "reasoning_tokens=10" in excinfo.value.detail


def test_successful_call_logs_served_model_and_latency(monkeypatch, caplog):
    from utils import llm

    body = {
        "model": "cohere/north-mini-code:free",
        "choices": [{"message": {"content": "ANALYTICAL"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 12, "completion_tokens": 3},
    }
    monkeypatch.setattr(llm.requests, "post", lambda *a, **k: _FakeResponse(200, body))

    with caplog.at_level(logging.INFO, logger="utils.llm"):
        result = llm.chat_completion("classify")

    assert result == "ANALYTICAL"
    records = [r for r in caplog.records if r.name == "utils.llm"]
    assert any(
        "served=cohere/north-mini-code:free" in r.getMessage() and "latency=" in r.getMessage()
        for r in records
    )


def test_malformed_choice_element_raises_bad_response_not_attributeerror(monkeypatch):
    from utils import llm

    # A malformed choices[0] (None instead of a dict) must still surface as a
    # typed LLMError, not an unhandled AttributeError from .get() on None.
    body = {"model": "x", "choices": [None], "usage": {"prompt_tokens": 1, "completion_tokens": 0}}
    # chat_completion retries BAD_RESPONSE once; the fake returns the same reply both times.
    monkeypatch.setattr(llm.requests, "post", lambda *a, **k: _FakeResponse(200, body))

    with pytest.raises(llm.LLMError) as excinfo:
        llm.chat_completion("hi")
    assert excinfo.value.kind == llm.LLMError.BAD_RESPONSE


def test_non_dict_usage_degrades_telemetry_to_none_counts(monkeypatch, caplog):
    from utils import llm

    body = {
        "model": "x",
        "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
        "usage": "not-a-dict",
    }
    monkeypatch.setattr(llm.requests, "post", lambda *a, **k: _FakeResponse(200, body))

    with caplog.at_level(logging.INFO, logger="utils.llm"):
        result = llm.chat_completion("hi")

    assert result == "ok"
    records = [r for r in caplog.records if r.name == "utils.llm"]
    assert any(
        "tokens(prompt=None, completion=None, reasoning=None)" in r.getMessage() for r in records
    )


def test_non_dict_completion_tokens_details_degrades_reasoning_count_to_none(monkeypatch, caplog):
    from utils import llm

    body = {
        "model": "x",
        "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
        "usage": {
            "prompt_tokens": 5,
            "completion_tokens": 2,
            "completion_tokens_details": ["not", "a", "dict"],
        },
    }
    monkeypatch.setattr(llm.requests, "post", lambda *a, **k: _FakeResponse(200, body))

    with caplog.at_level(logging.INFO, logger="utils.llm"):
        result = llm.chat_completion("hi")

    assert result == "ok"
    records = [r for r in caplog.records if r.name == "utils.llm"]
    assert any(
        "tokens(prompt=5, completion=2, reasoning=None)" in r.getMessage() for r in records
    )


@pytest.mark.parametrize("retries, calls", [(0, 1), (1, 2), (2, 3)])
def test_retries_sets_extra_attempts_after_empty_reply(monkeypatch, retries, calls):
    from utils import llm

    sent = []

    def empty(*a, **k):
        sent.append(1)
        return _FakeResponse(200, {"choices": [{"message": {"content": ""}}]})

    monkeypatch.setattr(llm.requests, "post", empty)
    with pytest.raises(llm.LLMError) as excinfo:
        llm.chat_completion("hi", retries=retries)
    assert excinfo.value.kind == llm.LLMError.BAD_RESPONSE
    assert len(sent) == calls


def test_default_is_one_retry(monkeypatch):
    from utils import llm

    sent = []

    def empty(*a, **k):
        sent.append(1)
        return _FakeResponse(200, {"choices": [{"message": {"content": ""}}]})

    monkeypatch.setattr(llm.requests, "post", empty)
    with pytest.raises(llm.LLMError):
        llm.chat_completion("hi")
    assert len(sent) == 2
