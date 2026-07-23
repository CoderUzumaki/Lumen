"""EVAL-02 acceptance: LangSmith project naming, run metadata, share helper."""
from __future__ import annotations

import logging
import sys
import uuid
from unittest.mock import MagicMock, patch

import pytest

import app.utils.langsmith as ls
from app.utils.config import Config


# --- project_name ----------------------------------------------------------


def test_project_name_maps_development_to_dev(monkeypatch):
    monkeypatch.setattr(Config, "FLASK_ENV", "development", raising=False)
    assert ls.project_name() == "lumen-dev"


def test_project_name_maps_production_to_prod(monkeypatch):
    monkeypatch.setattr(Config, "FLASK_ENV", "production", raising=False)
    assert ls.project_name() == "lumen-prod"


def test_project_name_maps_staging_verbatim(monkeypatch):
    monkeypatch.setattr(Config, "FLASK_ENV", "staging", raising=False)
    assert ls.project_name() == "lumen-staging"


def test_project_name_unknown_env_defaults_to_dev(monkeypatch):
    monkeypatch.setattr(Config, "FLASK_ENV", "weird-env", raising=False)
    assert ls.project_name() == "lumen-dev"


def test_project_name_explicit_override_wins(monkeypatch):
    monkeypatch.setattr(Config, "FLASK_ENV", "development", raising=False)
    assert ls.project_name("prod") == "lumen-prod"
    assert ls.project_name("staging") == "lumen-staging"


# --- is_tracing_enabled ----------------------------------------------------


def test_is_tracing_enabled_requires_both_env_vars(monkeypatch):
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    assert ls.is_tracing_enabled() is False

    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    # Missing API key → still False.
    assert ls.is_tracing_enabled() is False

    monkeypatch.setenv("LANGSMITH_API_KEY", "ls_test")
    assert ls.is_tracing_enabled() is True


def test_is_tracing_enabled_rejects_falsey_tracing_var(monkeypatch):
    monkeypatch.setenv("LANGSMITH_API_KEY", "ls_test")
    for val in ("false", "0", "no", "", "off"):
        monkeypatch.setenv("LANGSMITH_TRACING", val)
        assert ls.is_tracing_enabled() is False, (
            f"expected disabled for LANGSMITH_TRACING={val!r}"
        )


def test_is_tracing_enabled_accepts_multiple_truthy(monkeypatch):
    monkeypatch.setenv("LANGSMITH_API_KEY", "ls_test")
    for val in ("true", "1", "yes", "on", "TRUE", "Yes"):
        monkeypatch.setenv("LANGSMITH_TRACING", val)
        assert ls.is_tracing_enabled() is True, (
            f"expected enabled for LANGSMITH_TRACING={val!r}"
        )


# --- run_metadata ----------------------------------------------------------


def test_run_metadata_populates_tags_and_metadata(monkeypatch):
    monkeypatch.setattr(Config, "FLASK_ENV", "development", raising=False)
    uid = uuid.uuid4()
    md = ls.run_metadata(
        agent_name="impact-analyst", user_id=uid, git_sha="abc123def456"
    )
    assert "tags" in md and "metadata" in md
    assert "impact-analyst" in md["tags"]
    assert "env:dev" in md["tags"]
    assert "abc123d" in md["tags"]  # short sha (7 chars)
    assert md["metadata"]["user_id"] == str(uid)
    assert md["metadata"]["agent_name"] == "impact-analyst"
    assert md["metadata"]["git_sha"] == "abc123def456"


def test_run_metadata_short_sha_when_git_sha_long(monkeypatch):
    monkeypatch.setattr(Config, "FLASK_ENV", "production", raising=False)
    md = ls.run_metadata(agent_name="a", git_sha="0123456789abcdef")
    assert "0123456" in md["tags"]
    assert md["metadata"]["git_sha"] == "0123456789abcdef"


def test_run_metadata_git_sha_defaults_to_env(monkeypatch):
    monkeypatch.setenv("GIT_SHA", "xyz789abcdef")
    md = ls.run_metadata(agent_name="a")
    assert md["metadata"]["git_sha"] == "xyz789abcdef"
    assert "xyz789a" in md["tags"]


def test_run_metadata_git_sha_defaults_to_dev_when_unset(monkeypatch):
    monkeypatch.delenv("GIT_SHA", raising=False)
    md = ls.run_metadata(agent_name="a")
    assert md["metadata"]["git_sha"] == "dev"


def test_run_metadata_omits_user_id_when_not_provided(monkeypatch):
    md = ls.run_metadata(agent_name="briefing")
    assert "user_id" not in md["metadata"]


def test_run_metadata_extra_merges_into_metadata(monkeypatch):
    md = ls.run_metadata(
        agent_name="a", extra={"cluster_id": "some-uuid", "count": 5}
    )
    assert md["metadata"]["cluster_id"] == "some-uuid"
    assert md["metadata"]["count"] == 5


def test_run_metadata_extra_cannot_clobber_reserved_keys(caplog):
    with caplog.at_level(logging.WARNING, logger="app.utils.langsmith"):
        md = ls.run_metadata(
            agent_name="a", extra={"agent_name": "hijack", "git_sha": "bad"}
        )
    assert md["metadata"]["agent_name"] == "a"
    assert md["metadata"]["git_sha"] != "bad"
    assert any("collides" in r.getMessage() for r in caplog.records)


# --- mark_public -----------------------------------------------------------


def test_mark_public_returns_none_when_tracing_disabled(monkeypatch):
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    assert ls.mark_public("run-abc") is None


def test_mark_public_returns_none_when_sdk_missing(monkeypatch):
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGSMITH_API_KEY", "ls_test")
    # Poison the import: langsmith module resolves to a bare object without
    # `Client`. The function catches ImportError; we simulate a MISSING
    # attribute equivalently by patching sys.modules to a stub then relying
    # on the import machinery's ImportError inside the try.
    #
    # Cleanest simulation: patch sys.modules to raise on attribute access via
    # a dedicated stub, but the ImportError branch is what we care about.
    real = sys.modules.pop("langsmith", None)
    sys.modules["langsmith"] = None  # forces ImportError on `from langsmith import Client`
    try:
        assert ls.mark_public("run-abc") is None
    finally:
        if real is not None:
            sys.modules["langsmith"] = real
        else:
            sys.modules.pop("langsmith", None)


def test_mark_public_returns_url_on_success(monkeypatch):
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGSMITH_API_KEY", "ls_test")
    fake_client = MagicMock()
    fake_client.share_run.return_value = "https://smith.langchain.com/public/xyz"
    with patch("langsmith.Client", return_value=fake_client):
        url = ls.mark_public("run-abc")
    assert url == "https://smith.langchain.com/public/xyz"
    fake_client.share_run.assert_called_once_with("run-abc")


def test_mark_public_swallows_share_run_exceptions(monkeypatch, caplog):
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGSMITH_API_KEY", "ls_test")
    fake_client = MagicMock()
    fake_client.share_run.side_effect = RuntimeError("boom")
    with (
        patch("langsmith.Client", return_value=fake_client),
        caplog.at_level(logging.WARNING, logger="app.utils.langsmith"),
    ):
        url = ls.mark_public("run-abc")
    assert url is None
    assert any("share_run failed" in r.getMessage() for r in caplog.records)


def test_mark_public_returns_none_when_share_run_returns_none(monkeypatch):
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGSMITH_API_KEY", "ls_test")
    fake_client = MagicMock()
    fake_client.share_run.return_value = None
    with patch("langsmith.Client", return_value=fake_client):
        assert ls.mark_public("run-abc") is None


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
