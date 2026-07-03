"""Local embeddings client using sentence-transformers (ING-07).

`sentence-transformers/all-MiniLM-L6-v2` benchmarks within ~5% of OpenAI's
`text-embedding-3-small` on English retrieval quality and is free forever —
no API key, no per-token cost, no rate limits. It's the single largest
cost-cut in Lumen's stack. Trade-off: first call downloads ~90MB and loads
the model into memory; subsequent calls are fast on CPU (batch of 100 titles
completes in <1s on a modern laptop, well inside the <3s target from
BUILD.md).

The model is loaded once into a process-global singleton (`_load_model()`).
`EmbeddingClient.embed()` runs the sync encoder in the default executor to
keep the async event loop unblocked.
"""
from __future__ import annotations

import logging
from typing import Any

import asyncio

from app.utils.config import Config

log = logging.getLogger(__name__)

_model: Any | None = None


def _load_model() -> Any:
    """Load the sentence-transformers model once and cache it."""
    global _model
    if _model is not None:
        return _model
    from sentence_transformers import SentenceTransformer  # lazy import; torch is heavy

    log.info(
        "embeddings: loading %s on %s",
        Config.EMBEDDING_MODEL,
        Config.EMBEDDING_DEVICE,
    )
    _model = SentenceTransformer(
        Config.EMBEDDING_MODEL, device=Config.EMBEDDING_DEVICE
    )
    return _model


class EmbeddingClient:
    """Async wrapper around sentence-transformers.

    Callers should share a single instance per process. `embed()` batches
    internally at `batch_size` (default 64 per BUILD.md ING-07 spec).
    """

    def __init__(self, *, batch_size: int = 64):
        self._batch_size = batch_size

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._encode_sync, texts)

    def _encode_sync(self, texts: list[str]) -> list[list[float]]:
        model = _load_model()
        arr = model.encode(
            texts,
            batch_size=self._batch_size,
            convert_to_numpy=True,
            show_progress_bar=False,
            normalize_embeddings=True,
        )
        # numpy array → nested lists so callers don't need numpy on their side.
        return arr.tolist()
