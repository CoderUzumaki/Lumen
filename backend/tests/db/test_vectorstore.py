"""ING-07 acceptance: Chroma collections + upsert/query round-trip."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

import app.db.vectorstore as vs


@pytest.fixture
def fresh_chroma_client():
    """Isolated Chroma client per test using a tempdir. Resets module singleton."""
    import chromadb
    from chromadb.config import Settings

    path = Path(tempfile.mkdtemp(prefix="lumen-chroma-"))
    original = vs._client
    vs._client = None
    client = chromadb.PersistentClient(
        path=str(path), settings=Settings(anonymized_telemetry=False)
    )
    vs._client = client
    yield client
    vs._client = original
    # Chroma keeps files locked briefly on Windows; best-effort cleanup.
    try:
        import shutil

        shutil.rmtree(path, ignore_errors=True)
    except OSError:
        pass


def test_init_collections_creates_all_three(fresh_chroma_client):
    vs.init_collections(client=fresh_chroma_client)
    names = {c.name for c in fresh_chroma_client.list_collections()}
    assert names == {"news_items", "themes", "historical_analogs"}


def test_init_collections_is_idempotent(fresh_chroma_client):
    vs.init_collections(client=fresh_chroma_client)
    # second call must not raise or duplicate
    vs.init_collections(client=fresh_chroma_client)
    names = [c.name for c in fresh_chroma_client.list_collections()]
    assert len(names) == 3


def test_upsert_query_delete_roundtrip(fresh_chroma_client):
    vs.init_collections(client=fresh_chroma_client)
    store = vs.VectorStore("news_items", client=fresh_chroma_client)

    # 3-dim fake embeddings — deterministic, useful for verifying nearest match.
    store.upsert(
        ids=["a", "b", "c"],
        embeddings=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        metadatas=[
            {"source": "newsapi", "cluster_id": "cl-1"},
            {"source": "gdelt", "cluster_id": "cl-2"},
            {"source": "rss", "cluster_id": "cl-3"},
        ],
        documents=["about x", "about y", "about z"],
    )
    assert store.count() == 3

    # Query with a vector very close to `a`.
    result = store.query(query_embeddings=[[0.95, 0.1, 0.05]], n_results=2)
    top_ids = result["ids"][0]
    assert top_ids[0] == "a"

    # Metadata filter narrows down.
    result_filtered = store.query(
        query_embeddings=[[1.0, 0.0, 0.0]],
        n_results=5,
        where={"source": "gdelt"},
    )
    assert result_filtered["ids"][0] == ["b"]

    # Delete
    store.delete(ids=["a"])
    assert store.count() == 2


def test_upsert_overwrites_existing_id(fresh_chroma_client):
    vs.init_collections(client=fresh_chroma_client)
    store = vs.VectorStore("themes", client=fresh_chroma_client)

    store.upsert(
        ids=["theme-1"],
        embeddings=[[1.0, 0.0]],
        metadatas=[{"user_id": "u1", "description": "AI capex"}],
    )
    store.upsert(
        ids=["theme-1"],
        embeddings=[[0.0, 1.0]],
        metadatas=[{"user_id": "u1", "description": "AI capex REVISED"}],
    )
    assert store.count() == 1
    got = store._collection.get(ids=["theme-1"])
    assert got["metadatas"][0]["description"] == "AI capex REVISED"


def test_unknown_collection_raises(fresh_chroma_client):
    with pytest.raises(ValueError):
        vs.VectorStore("bogus", client=fresh_chroma_client)
