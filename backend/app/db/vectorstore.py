"""Chroma vector store wrapper (ING-07).

Three canonical collections managed here:
- `news_items`        — one doc per news item; metadata carries cluster_id,
                        source, published_at_iso, tickers.
- `themes`            — one doc per user theme; metadata carries user_id.
- `historical_analogs`— IMP-02 populates; kept in the shared registry so
                        `init_collections()` provisions all three at startup.

The client is a `PersistentClient` writing to `Config.CHROMA_PATH`. Tests can
inject a custom client to point at a temp directory.
"""
from __future__ import annotations

import logging
from typing import Any

from app.utils.config import Config

log = logging.getLogger(__name__)


COLLECTIONS: tuple[str, ...] = ("news_items", "themes", "historical_analogs")

# Per-collection Chroma settings. Cosine everywhere because EmbeddingClient
# normalizes on encode (ING-07). ING-09 depends on `distance = 1 - similarity`
# semantics so the 0.87 threshold in BUILD.md carries over directly.
_COLLECTION_METADATA: dict[str, dict[str, str]] = {
    "news_items": {"hnsw:space": "cosine"},
    "themes": {"hnsw:space": "cosine"},
    "historical_analogs": {"hnsw:space": "cosine"},
}


_client: Any | None = None


def get_client(path: str | None = None) -> Any:
    """Return the process-global Chroma client, creating it on first call.

    Passing a `path` at call time is ONLY honored on first construction; it's
    a convenience for tests that need a specific directory. Callers who need
    fresh isolation should use `_ChromaClientFactory` (see tests).
    """
    global _client
    if _client is None:
        import chromadb
        from chromadb.config import Settings

        target = path or Config.CHROMA_PATH
        log.info("chroma: opening persistent client at %s", target)
        _client = chromadb.PersistentClient(
            path=target, settings=Settings(anonymized_telemetry=False)
        )
    return _client


def init_collections(client: Any | None = None) -> None:
    """Idempotent: create each canonical collection if it doesn't exist."""
    c = client or get_client()
    for name in COLLECTIONS:
        c.get_or_create_collection(
            name=name, metadata=_COLLECTION_METADATA[name]
        )


class VectorStore:
    """Thin wrapper around a single Chroma collection."""

    def __init__(self, collection: str, *, client: Any | None = None):
        if collection not in COLLECTIONS:
            raise ValueError(
                f"unknown collection {collection!r}; expected one of {COLLECTIONS}"
            )
        self._client = client or get_client()
        self._collection = self._client.get_or_create_collection(
            name=collection, metadata=_COLLECTION_METADATA[collection]
        )
        self._collection_name = collection

    @property
    def name(self) -> str:
        return self._collection_name

    def upsert(
        self,
        *,
        ids: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]] | None = None,
        documents: list[str] | None = None,
    ) -> None:
        """Insert or replace vectors keyed by id."""
        self._collection.upsert(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=documents,
        )

    def query(
        self,
        *,
        query_embeddings: list[list[float]],
        n_results: int = 10,
        where: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Cosine-similarity search."""
        return self._collection.query(
            query_embeddings=query_embeddings,
            n_results=n_results,
            where=where,
        )

    def delete(self, ids: list[str]) -> None:
        self._collection.delete(ids=ids)

    def count(self) -> int:
        return self._collection.count()

    def get(
        self,
        *,
        ids: list[str],
        include: list[str] | None = None,
    ) -> dict[str, Any]:
        """Fetch specific docs by id. `include` names extra fields
        (`embeddings`, `metadatas`, `documents`)."""
        return self._collection.get(ids=ids, include=include or ["metadatas"])

    def update_metadata(
        self, *, ids: list[str], metadatas: list[dict[str, Any]]
    ) -> None:
        """Update metadata for existing docs without re-embedding."""
        self._collection.update(ids=ids, metadatas=metadatas)
