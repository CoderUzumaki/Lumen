"""Seed the `historical_analogs` Chroma collection from curated JSON (IMP-02).

Reads `app/evals/data/analogs.json`, embeds each event with the local
`EmbeddingClient`, and upserts vectors into the `historical_analogs`
collection. Idempotent — re-runs replace rows keyed by a stable
`event_hash = sha1(f"{event_description}|{when}").hexdigest()[:16]`.

CLI:
    python -m app.evals.seed_analogs

The seeded corpus feeds the retrieval tool in `app/tools/historical_analogs.py`
which the IMP-04 impact-analyst agent calls when composing analog citations.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from app.db.vectorstore import VectorStore
from app.utils.embeddings import EmbeddingClient

log = logging.getLogger(__name__)

_DEFAULT_DATA_PATH = Path(__file__).resolve().parent / "data" / "analogs.json"


def _event_hash(event_description: str, when: str) -> str:
    """Stable id: 16 hex chars of sha1(description|when). Idempotent upserts."""
    payload = f"{event_description}|{when}".encode()
    return hashlib.sha1(payload).hexdigest()[:16]


def load_analogs(path: Path | None = None) -> list[dict[str, Any]]:
    src = path or _DEFAULT_DATA_PATH
    with src.open("r", encoding="utf-8") as fp:
        rows = json.load(fp)
    if not isinstance(rows, list):
        raise ValueError(f"expected a JSON list at {src}, got {type(rows).__name__}")
    return rows


async def _seed(
    rows: list[dict[str, Any]],
    *,
    embed: EmbeddingClient | None = None,
    store: VectorStore | None = None,
) -> tuple[int, int]:
    """Upsert `rows` into the historical_analogs collection.

    Returns `(seeded_count, pre_existing_count)` — pre-existing is the count
    observed BEFORE the upsert, useful for the CLI summary line.
    """
    ec = embed or EmbeddingClient()
    vs = store or VectorStore("historical_analogs")
    pre_existing = vs.count()

    ids: list[str] = []
    texts: list[str] = []
    metadatas: list[dict[str, Any]] = []
    documents: list[str] = []

    for row in rows:
        event_description = str(row["event_description"])
        when = str(row["when"])
        outcome_description = str(row["outcome_description"])
        sectors_affected = row.get("sectors_affected", [])
        if isinstance(sectors_affected, list):
            sectors_str = ",".join(str(s) for s in sectors_affected)
        else:
            sectors_str = str(sectors_affected)
        magnitude_percent = float(row.get("magnitude_percent", 0.0))

        eid = _event_hash(event_description, when)
        combined = f"{event_description} {outcome_description}"

        ids.append(eid)
        texts.append(combined)
        metadatas.append(
            {
                "event_description": event_description,
                "when": when,
                "outcome_description": outcome_description,
                "sectors_affected": sectors_str,
                "magnitude_percent": magnitude_percent,
            }
        )
        documents.append(combined)

    if not ids:
        return 0, pre_existing

    vectors = await ec.embed(texts)
    vs.upsert(
        ids=ids,
        embeddings=vectors,
        metadatas=metadatas,
        documents=documents,
    )
    return len(ids), pre_existing


async def main_async(
    path: Path | None = None,
    *,
    embed: EmbeddingClient | None = None,
    store: VectorStore | None = None,
) -> tuple[int, int]:
    rows = load_analogs(path)
    seeded, pre_existing = await _seed(rows, embed=embed, store=store)
    print(
        f"seeded {seeded} analogs into historical_analogs "
        f"({pre_existing} pre-existing)"
    )
    return seeded, pre_existing


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":  # pragma: no cover — CLI entry
    main()
