"""Idempotent persistence of normalized news items (ING-08).

`persist(items)` bulk-inserts into `news_items` with ON CONFLICT DO NOTHING
on `url_hash` (dialect-dispatched between Postgres and sqlite), then indexes
the newly-inserted rows in Chroma's `news_items` collection with the row's
UUID as the doc id. Returns `(inserted_count, skipped_count)`.

Duplicate `url_hash`s within a single call are de-duped in Python before the
INSERT so the counts stay correct.
"""
from __future__ import annotations

import logging
import uuid

from sqlalchemy import insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.news import NewsItem
from app.db.vectorstore import VectorStore
from app.pipelines.normalizer import NormalizedItem
from app.utils.embeddings import EmbeddingClient

log = logging.getLogger(__name__)


async def persist(
    items: list[NormalizedItem],
    *,
    session: AsyncSession,
    embed: EmbeddingClient,
    store: VectorStore,
) -> tuple[int, int]:
    """Returns (inserted_count, skipped_count)."""
    if not items:
        return (0, 0)

    # Deduplicate within the batch by url_hash — preserves first-seen order.
    seen: set[str] = set()
    unique_items: list[NormalizedItem] = []
    for item in items:
        if item.url_hash in seen:
            continue
        seen.add(item.url_hash)
        unique_items.append(item)

    # Pre-compute which url_hashes are already in the DB so we can (a) count
    # skipped accurately and (b) hand only the new rows to Chroma.
    hashes = [i.url_hash for i in unique_items]
    existing_q = select(NewsItem.url_hash).where(NewsItem.url_hash.in_(hashes))
    existing_hashes: set[str] = set(
        (await session.execute(existing_q)).scalars().all()
    )

    to_insert = [i for i in unique_items if i.url_hash not in existing_hashes]

    rows = [
        {
            "id": uuid.uuid4(),
            "source": i.source,
            "source_id": i.source_id,
            "url": i.url,
            "url_hash": i.url_hash,
            "title": i.title,
            "body": i.body,
            "published_at": i.published_at,
            "raw_payload": i.raw_payload,
        }
        for i in to_insert
    ]

    if rows:
        dialect = session.get_bind().dialect.name
        if dialect == "postgresql":
            stmt = (
                pg_insert(NewsItem)
                .values(rows)
                .on_conflict_do_nothing(index_elements=["url_hash"])
            )
        elif dialect == "sqlite":
            stmt = (
                sqlite_insert(NewsItem)
                .values(rows)
                .on_conflict_do_nothing(index_elements=["url_hash"])
            )
        else:
            stmt = insert(NewsItem).values(rows)
        await session.execute(stmt)
        await session.commit()

    # Fetch back the newly-inserted rows so we can embed and index them.
    inserted_hashes = [i.url_hash for i in to_insert]
    inserted_rows: list[NewsItem] = []
    if inserted_hashes:
        result = await session.execute(
            select(NewsItem).where(NewsItem.url_hash.in_(inserted_hashes))
        )
        inserted_rows = list(result.scalars().all())

    if inserted_rows:
        try:
            texts = [
                f"{n.title}\n\n{(n.body or '')[:1500]}" for n in inserted_rows
            ]
            vectors = await embed.embed(texts)
            store.upsert(
                ids=[str(n.id) for n in inserted_rows],
                embeddings=vectors,
                metadatas=[
                    {
                        "cluster_id": str(n.cluster_id) if n.cluster_id else "",
                        "source": n.source,
                        "published_at_iso": n.published_at.isoformat(),
                    }
                    for n in inserted_rows
                ],
                documents=[n.title for n in inserted_rows],
            )
        except Exception:
            log.exception(
                "persist: failed to index %d items in chroma", len(inserted_rows)
            )

    return (len(inserted_rows), len(unique_items) - len(inserted_rows))
