"""Retrieval tool over the curated historical-analog corpus (IMP-02).

The IMP-04 impact-analyst agent calls `retrieve_analogs(...)` to cite past
events like "similar to March 2020 rate response". Vectors and metadata are
seeded by `app.evals.seed_analogs` into the `historical_analogs` Chroma
collection.

Chroma is configured with cosine distance in `app/db/vectorstore.py`, so
Chroma returns `distance = 1 - similarity`; we convert back with
`similarity = 1 - distance` and filter below `min_similarity`.
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

from app.db.vectorstore import VectorStore
from app.schemas.impact import HistoricalAnalog
from app.utils.embeddings import EmbeddingClient

log = logging.getLogger(__name__)


def _parse_date(value: Any) -> date:
    """Metadata dates are ISO strings; the schema needs `date`."""
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    return date.fromisoformat(str(value))


async def retrieve_analogs(
    query_text: str,
    k: int = 3,
    *,
    min_similarity: float = 0.6,
    embed: EmbeddingClient | None = None,
    store: VectorStore | None = None,
) -> list[HistoricalAnalog]:
    """Return up to `k` `HistoricalAnalog` records ranked by cosine similarity.

    - Embeds `query_text` with `EmbeddingClient` (injected in tests).
    - Filters results whose similarity is below `min_similarity`.
    - Results ordered descending by `similarity_score`.
    """
    if not query_text or not query_text.strip():
        return []

    ec = embed or EmbeddingClient()
    vs = store or VectorStore("historical_analogs")

    query_vec = await ec.embed([query_text])
    if not query_vec:
        return []

    result = vs.query(query_embeddings=query_vec, n_results=max(1, k))
    ids_list = (result.get("ids") or [[]])[0]
    distances = (result.get("distances") or [[]])[0]
    metadatas = (result.get("metadatas") or [[]])[0]

    analogs: list[tuple[float, HistoricalAnalog]] = []
    for _id, dist, meta in zip(ids_list, distances, metadatas):
        if meta is None:
            continue
        try:
            similarity = 1.0 - float(dist)
        except (TypeError, ValueError):
            continue
        # Cosine similarity is theoretically in [-1, 1]; clamp for schema.
        similarity = max(0.0, min(1.0, similarity))
        if similarity < min_similarity:
            continue
        try:
            analog = HistoricalAnalog(
                event_description=str(meta["event_description"]),
                when=_parse_date(meta["when"]),
                outcome_description=str(meta["outcome_description"]),
                similarity_score=similarity,
            )
        except (KeyError, ValueError) as exc:
            log.warning("historical_analogs: skipping malformed row %s: %s", _id, exc)
            continue
        analogs.append((similarity, analog))

    analogs.sort(key=lambda pair: pair[0], reverse=True)
    return [a for _, a in analogs]
