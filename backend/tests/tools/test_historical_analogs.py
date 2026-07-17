"""IMP-02 acceptance: analog seed + retrieval round-trip.

Uses the REAL `EmbeddingClient` (`sentence-transformers/all-MiniLM-L6-v2`) —
local, CPU-viable. First test loads the model (~a few seconds); subsequent
tests reuse the process-global singleton.
"""
from __future__ import annotations

import json
import shutil
import tempfile
from collections.abc import Iterator
from pathlib import Path

import chromadb
import pytest
from chromadb.config import Settings

import app.db.vectorstore as vs
from app.evals import seed_analogs
from app.tools.historical_analogs import retrieve_analogs
from app.utils.embeddings import EmbeddingClient


# A minimal fixture corpus. Enough Federal Reserve rows so the acceptance
# ("Federal Reserve rate cut" → ≥2 Fed hits) has room to breathe even under
# minor embedding noise.
_FIXTURE_ROWS = [
    {
        "event_description": (
            "Federal Reserve cuts rates by 50bps in emergency response to COVID"
        ),
        "when": "2020-03-03",
        "outcome_description": (
            "SPX rallied briefly then resumed its slide as pandemic scale became "
            "clear."
        ),
        "sectors_affected": ["equities", "rates"],
        "magnitude_percent": -20.0,
    },
    {
        "event_description": (
            "Federal Reserve raises rates by 75bps, largest hike since 1994, to "
            "fight inflation"
        ),
        "when": "2022-06-15",
        "outcome_description": (
            "SPX fell 6% over the week; growth stocks led decline as discount "
            "rates jumped."
        ),
        "sectors_affected": ["equities", "rates"],
        "magnitude_percent": -6.0,
    },
    {
        "event_description": (
            "Federal Reserve delivers 50bps rate cut, first cut of the easing "
            "cycle"
        ),
        "when": "2024-09-18",
        "outcome_description": (
            "SPX gained 1.7% next session; small-caps outperformed; USD softened."
        ),
        "sectors_affected": ["equities", "rates"],
        "magnitude_percent": 1.7,
    },
    {
        "event_description": (
            "Fed pauses rate hikes for first time in 15 months, holds Fed Funds "
            "at 5.25%"
        ),
        "when": "2023-06-14",
        "outcome_description": (
            "Equities flat as hawkish dot plot offset the pause; 2Y yields "
            "jumped 10bps."
        ),
        "sectors_affected": ["equities", "rates"],
        "magnitude_percent": 0.0,
    },
    {
        "event_description": (
            "OPEC+ announces surprise 1.16 million barrel per day production cut"
        ),
        "when": "2023-04-02",
        "outcome_description": (
            "Brent gapped up 6% Monday; energy sector rose 4%; airlines weakened."
        ),
        "sectors_affected": ["oil", "energy"],
        "magnitude_percent": 6.0,
    },
    {
        "event_description": (
            "Silicon Valley Bank collapses, largest US bank failure since 2008"
        ),
        "when": "2023-03-10",
        "outcome_description": (
            "KRE regional bank ETF fell 20% in a week; short-end Treasuries "
            "rallied 100bps."
        ),
        "sectors_affected": ["banks", "regional-banks"],
        "magnitude_percent": -20.0,
    },
    {
        "event_description": (
            "United Kingdom votes to leave European Union in Brexit referendum"
        ),
        "when": "2016-06-23",
        "outcome_description": (
            "GBP crashed 8% overnight to 30-year lows; FTSE 250 fell 7% next "
            "session."
        ),
        "sectors_affected": ["fx", "equities"],
        "magnitude_percent": -8.0,
    },
]


@pytest.fixture
def fixture_json(tmp_path: Path) -> Path:
    """Write the in-test JSON corpus to a tempfile and return its path."""
    p = tmp_path / "analogs.json"
    p.write_text(json.dumps(_FIXTURE_ROWS), encoding="utf-8")
    return p


@pytest.fixture
def env() -> Iterator[vs.VectorStore]:
    """Fresh Chroma at a tempdir, wired into the vs module singleton."""
    chroma_path = Path(tempfile.mkdtemp(prefix="lumen-test-analogs-"))
    chroma_client = chromadb.PersistentClient(
        path=str(chroma_path), settings=Settings(anonymized_telemetry=False)
    )
    original = vs._client
    vs._client = chroma_client
    vs.init_collections(client=chroma_client)
    store = vs.VectorStore("historical_analogs", client=chroma_client)
    try:
        yield store
    finally:
        vs._client = original
        shutil.rmtree(chroma_path, ignore_errors=True)


@pytest.fixture(scope="module")
def embed() -> EmbeddingClient:
    """One shared real EmbeddingClient; loads the model once for the module."""
    return EmbeddingClient()


async def test_seed_upserts_expected_count(
    env: vs.VectorStore, fixture_json: Path, embed: EmbeddingClient
) -> None:
    seeded, pre_existing = await seed_analogs.main_async(
        fixture_json, embed=embed, store=env
    )
    assert seeded == len(_FIXTURE_ROWS)
    assert pre_existing == 0
    assert env.count() == len(_FIXTURE_ROWS)


async def test_seed_is_idempotent(
    env: vs.VectorStore, fixture_json: Path, embed: EmbeddingClient
) -> None:
    await seed_analogs.main_async(fixture_json, embed=embed, store=env)
    first_count = env.count()
    # second run — same rows, same hashes, same collection
    seeded, pre_existing = await seed_analogs.main_async(
        fixture_json, embed=embed, store=env
    )
    assert seeded == len(_FIXTURE_ROWS)
    assert pre_existing == first_count
    assert env.count() == first_count


async def test_retrieve_federal_reserve_query_finds_fed_events(
    env: vs.VectorStore, fixture_json: Path, embed: EmbeddingClient
) -> None:
    """BUILD.md acceptance: 'Federal Reserve rate cut' returns ≥2 Fed hits."""
    await seed_analogs.main_async(fixture_json, embed=embed, store=env)

    results = await retrieve_analogs(
        "Federal Reserve rate cut",
        k=4,
        min_similarity=0.0,  # don't drop anything for the acceptance count
        embed=embed,
        store=env,
    )
    fed_hits = [
        r
        for r in results
        if "federal reserve" in r.event_description.lower()
        or "fed " in r.event_description.lower()
        or r.event_description.lower().startswith("fed ")
    ]
    assert len(fed_hits) >= 2, (
        f"expected ≥2 Fed-flavored hits, got {[r.event_description for r in results]}"
    )


async def test_min_similarity_filter_drops_unrelated(
    env: vs.VectorStore, fixture_json: Path, embed: EmbeddingClient
) -> None:
    """A high threshold + gibberish query should return few or zero rows."""
    await seed_analogs.main_async(fixture_json, embed=embed, store=env)

    results = await retrieve_analogs(
        "xqzptv wnbkjf plsdrj fbzmnr",  # random tokens — no signal
        k=5,
        min_similarity=0.6,
        embed=embed,
        store=env,
    )
    # MiniLM cosine of random tokens vs real events sits near 0-0.2 in practice.
    assert len(results) <= 1


async def test_results_sorted_by_descending_similarity(
    env: vs.VectorStore, fixture_json: Path, embed: EmbeddingClient
) -> None:
    await seed_analogs.main_async(fixture_json, embed=embed, store=env)

    results = await retrieve_analogs(
        "central bank policy rate decision",
        k=5,
        min_similarity=0.0,
        embed=embed,
        store=env,
    )
    assert len(results) >= 2
    scores = [r.similarity_score for r in results]
    assert scores == sorted(scores, reverse=True)
