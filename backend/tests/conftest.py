import os
import sys
import tempfile
from pathlib import Path

import pytest

# Ensure the Lumen backend package wins over any other `app` on PYTHONPATH.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# Tests must never write to the developer's real database or vector index.
# `config` reads these at import time and load_dotenv doesn't override them,
# so set them before any test imports the app. DATABASE_URL is set to empty
# (Config treats that as unset) rather than removed: removed, load_dotenv
# would fill it in from backend/.env.
TEST_DB_DIR = Path(tempfile.mkdtemp(prefix="lumen-tests-"))
os.environ["DATABASE_URL"] = ""
os.environ["DATABASE_PATH"] = str(TEST_DB_DIR / "lumen-test.db")
os.environ["ENABLE_CHROMA"] = "false"


@pytest.fixture
def authed_client(monkeypatch):
    """Test client whose requests are signed in as user-1 (token check mocked)."""
    import utils.auth
    from app import app

    monkeypatch.setattr(
        utils.auth,
        "verify_token",
        lambda token: {"sub": "user-1", "email": "u@example.com", "role": "authenticated"},
    )
    app.config.update({"TESTING": True})
    return app.test_client()
