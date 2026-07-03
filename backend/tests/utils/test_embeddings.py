"""ING-07 acceptance: local embeddings via sentence-transformers.

Hermetic tests use a monkey-patched fake model so the suite doesn't need to
download ~90MB of weights every run. The `@pytest.mark.integration` case
exercises the real path — enable with `pytest -m integration`.
"""
from __future__ import annotations

import numpy as np
import pytest

import app.utils.embeddings as emb


class _FakeModel:
    """Deterministic stand-in for SentenceTransformer.

    encode(list[str]) → an N × 3 numpy array where each row is a hand-crafted
    embedding keyed on substring presence. Used to verify EmbeddingClient's
    plumbing without downloading real weights.
    """

    def __init__(self, *_, **__):
        pass

    def encode(self, texts, **_kw):
        rows = []
        for t in texts:
            lo = t.lower()
            rows.append(
                [
                    1.0 if "fed" in lo else 0.0,
                    1.0 if "oil" in lo else 0.0,
                    1.0 if "nvda" in lo or "nvidia" in lo else 0.0,
                ]
            )
        return np.array(rows, dtype=np.float32)


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Reset the module-level cached model between tests."""
    original = emb._model
    emb._model = None
    yield
    emb._model = original


async def test_embed_returns_row_per_input(monkeypatch):
    monkeypatch.setattr(emb, "_load_model", lambda: _FakeModel())
    client = emb.EmbeddingClient()
    vectors = await client.embed(["Fed hikes", "Oil spikes", "NVDA reports"])
    assert len(vectors) == 3
    assert vectors[0] == [1.0, 0.0, 0.0]
    assert vectors[1] == [0.0, 1.0, 0.0]
    assert vectors[2] == [0.0, 0.0, 1.0]


async def test_empty_input_short_circuits(monkeypatch):
    called = {"n": 0}

    def _fake_loader():
        called["n"] += 1
        return _FakeModel()

    monkeypatch.setattr(emb, "_load_model", _fake_loader)
    client = emb.EmbeddingClient()
    assert await client.embed([]) == []
    assert called["n"] == 0  # never touched the model


async def test_batching_returns_expected_count(monkeypatch):
    monkeypatch.setattr(emb, "_load_model", lambda: _FakeModel())
    client = emb.EmbeddingClient(batch_size=4)
    texts = [f"item {i}" for i in range(11)]
    vectors = await client.embed(texts)
    assert len(vectors) == 11


@pytest.mark.integration
async def test_real_sentence_transformers_fed_retrieves_fed():
    """Live semantic check with the real model. First run downloads ~90MB."""
    client = emb.EmbeddingClient()
    texts = [
        "Fed raises rates by 25bps",
        "Federal Reserve holds steady on interest rates",
        "Oil surges past $100 as OPEC signals cuts",
        "NVDA earnings beat expectations",
        "Bitcoin rallies to new all-time high",
    ]
    query = "Federal Reserve rate decision"
    vectors = await client.embed(texts)
    query_vec = (await client.embed([query]))[0]

    def cosine(a, b):
        na = np.array(a)
        nb = np.array(b)
        return float(np.dot(na, nb) / (np.linalg.norm(na) * np.linalg.norm(nb)))

    scores = [(i, cosine(query_vec, v)) for i, v in enumerate(vectors)]
    scores.sort(key=lambda x: -x[1])
    # Top-2 should be the two Fed items (indices 0 and 1) in either order.
    assert set(s[0] for s in scores[:2]) == {0, 1}
