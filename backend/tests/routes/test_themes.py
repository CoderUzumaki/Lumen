"""DATA-04 acceptance: themes CRUD + Chroma round-trip + ownership scoping."""
from __future__ import annotations

import tempfile
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import chromadb
import pytest_asyncio
from chromadb.config import Settings
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

import app.db.vectorstore as vs
from app.db.base import Base, get_db_session
from app.db.models import Theme  # noqa: F401 — register with Base.metadata
from app.main import app
from app.routes.themes import get_embed_client, get_themes_vector_store
from app.utils.auth import UserContext, require_auth
from app.utils.embeddings import EmbeddingClient


ALICE = uuid.uuid4()
BOB = uuid.uuid4()


class _FakeEmbed(EmbeddingClient):
    """Deterministic 3-dim embeddings keyed on substring markers."""

    async def embed(self, texts):
        rows = []
        for t in texts:
            lo = t.lower()
            rows.append(
                [
                    1.0 if "recession" in lo else 0.0,
                    1.0 if "capex" in lo else 0.0,
                    1.0 if "energy" in lo or "oil" in lo else 0.0,
                ]
            )
        return rows


def _fake_user(user_id: uuid.UUID):
    async def _fake() -> UserContext:
        return UserContext(
            user_id=user_id, email=f"{user_id}@test", role="authenticated"
        )

    return _fake


@pytest_asyncio.fixture
async def client() -> AsyncIterator[tuple[AsyncClient, chromadb.PersistentClient]]:
    """Fresh sqlite + fresh Chroma tempdir per test."""
    db_path = Path(tempfile.mkstemp(suffix=".db")[1])
    chroma_path = Path(tempfile.mkdtemp(prefix="lumen-test-chroma-"))

    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", future=True)

    @event.listens_for(engine.sync_engine, "connect")
    def _fk_on(dbapi_conn, _):  # noqa: ARG001
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async def _session_override() -> AsyncIterator[AsyncSession]:
        async with session_factory() as s:
            yield s

    # Isolate Chroma per test.
    chroma_client = chromadb.PersistentClient(
        path=str(chroma_path),
        settings=Settings(anonymized_telemetry=False),
    )
    original_vs_client = vs._client
    vs._client = chroma_client
    vs.init_collections(client=chroma_client)

    fake_store = vs.VectorStore("themes", client=chroma_client)
    fake_embed = _FakeEmbed()

    app.dependency_overrides[get_db_session] = _session_override
    app.dependency_overrides[require_auth] = _fake_user(ALICE)
    app.dependency_overrides[get_embed_client] = lambda: fake_embed
    app.dependency_overrides[get_themes_vector_store] = lambda: fake_store

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c, chroma_client

    app.dependency_overrides.clear()
    vs._client = original_vs_client
    await engine.dispose()
    try:
        db_path.unlink()
    except OSError:
        pass
    import shutil
    shutil.rmtree(chroma_path, ignore_errors=True)


async def _as_user(user_id: uuid.UUID):
    app.dependency_overrides[require_auth] = _fake_user(user_id)


async def test_create_indexes_theme_in_chroma(client):
    http, chroma = client
    r = await http.post(
        "/api/themes", json={"description": "US recession risk", "weight": "0.8"}
    )
    assert r.status_code == 201
    body = r.json()
    theme_id = body["id"]
    assert body["description"] == "US recession risk"
    assert body["embedding_id"] == theme_id

    themes_col = chroma.get_or_create_collection("themes")
    got = themes_col.get(ids=[theme_id])
    assert got["ids"] == [theme_id]
    assert got["metadatas"][0]["user_id"] == str(ALICE)


async def test_list_and_get_scoped_to_owner(client):
    http, _ = client
    r = await http.post("/api/themes", json={"description": "AI capex cycle"})
    assert r.status_code == 201
    r = await http.post("/api/themes", json={"description": "Energy prices"})
    assert r.status_code == 201

    r = await http.get("/api/themes")
    assert r.status_code == 200
    assert len(r.json()) == 2

    await _as_user(BOB)
    r = await http.get("/api/themes")
    assert r.status_code == 200
    assert r.json() == []  # bob sees his own list


async def test_update_reembeds_when_description_changes(client):
    http, chroma = client
    r = await http.post("/api/themes", json={"description": "AI capex cycle"})
    theme_id = r.json()["id"]

    themes_col = chroma.get_or_create_collection("themes")
    before = themes_col.get(ids=[theme_id], include=["embeddings", "metadatas"])
    before_vec = before["embeddings"][0]
    before_desc = before["metadatas"][0]["description"]

    r = await http.put(
        f"/api/themes/{theme_id}", json={"description": "Energy prices"}
    )
    assert r.status_code == 200
    assert r.json()["description"] == "Energy prices"

    after = themes_col.get(ids=[theme_id], include=["embeddings", "metadatas"])
    after_vec = after["embeddings"][0]
    after_desc = after["metadatas"][0]["description"]

    assert before_desc != after_desc
    # Our fake embed differs across those two descriptions.
    assert list(before_vec) != list(after_vec)


async def test_update_only_weight_does_not_reembed(client):
    http, chroma = client
    r = await http.post("/api/themes", json={"description": "AI capex cycle"})
    theme_id = r.json()["id"]

    themes_col = chroma.get_or_create_collection("themes")
    before_vec = themes_col.get(ids=[theme_id], include=["embeddings"])["embeddings"][0]

    r = await http.put(f"/api/themes/{theme_id}", json={"weight": "0.3"})
    assert r.status_code == 200
    assert r.json()["weight"] == "0.30"

    after_vec = themes_col.get(ids=[theme_id], include=["embeddings"])["embeddings"][0]
    assert list(before_vec) == list(after_vec)


async def test_delete_removes_chroma_doc(client):
    http, chroma = client
    r = await http.post("/api/themes", json={"description": "AI capex cycle"})
    theme_id = r.json()["id"]

    themes_col = chroma.get_or_create_collection("themes")
    assert themes_col.count() == 1

    r = await http.delete(f"/api/themes/{theme_id}")
    assert r.status_code == 204
    assert themes_col.count() == 0

    r = await http.get("/api/themes")
    assert r.json() == []


async def test_cross_user_access_returns_404(client):
    http, _ = client
    r = await http.post("/api/themes", json={"description": "Alice's theme"})
    theme_id = r.json()["id"]

    await _as_user(BOB)
    r = await http.put(
        f"/api/themes/{theme_id}", json={"description": "Bob's takeover"}
    )
    assert r.status_code == 404
    r = await http.delete(f"/api/themes/{theme_id}")
    assert r.status_code == 404


async def test_validation_error_on_short_description(client):
    http, _ = client
    r = await http.post("/api/themes", json={"description": "ab"})
    assert r.status_code == 400
    body = r.json()
    assert body["error"]["code"] == "validation_error"
