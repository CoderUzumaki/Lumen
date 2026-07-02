"""Pytest bootstrap.

Sets env defaults so `app.utils.config.Config` and its consumers can be
imported inside unit tests without a real `.env` file. Individual tests
override via `monkeypatch.setenv` when the value matters.
"""
from __future__ import annotations

import os

os.environ.setdefault("FLASK_ENV", "development")
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("OPENROUTER_API_KEY", "test-openrouter-key")
os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./_test.db")
