"""Semantic dedup + clustering into `news_clusters` (ING-09).

For each newly-persisted `news_items` row (already embedded in Chroma by
ING-08), decide whether it belongs to an existing cluster or gets its own.

Algorithm per BUILD.md:
1. Fetch this item's embedding from Chroma.
2. Query the `news_items` Chroma collection for its top-5 nearest neighbors
   published within the last 48h (excluding self).
3. If the best neighbor's similarity > `CLUSTER_SIMILARITY_THRESHOLD`
   (default 0.87) and it has a cluster_id, attach the new item to that
   cluster. Update `last_seen_at` + `member_sources` + `authority_score` +
   `novelty_score`. Bump ticker set.
4. Otherwise, create a fresh cluster with the item's title / body[:500] /
   tickers.

Similarity comes from Chroma's cosine distance: `similarity = 1 - distance`
(vectors are already normalized by ING-07's EmbeddingClient).

Authority per cluster = max of member sources' `Config.SOURCE_AUTHORITY`
weight. Novelty = clamp(1.0 - member_count / 10, 0.1, 1.0). Both recomputed
whenever a cluster gains a member.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.news import NewsCluster, NewsItem
from app.db.vectorstore import VectorStore
from app.utils.config import Config

log = logging.getLogger(__name__)

_LOOKBACK = timedelta(hours=48)
_TOP_K = 6  # 5 neighbors + self
_MIN_NOVELTY = 0.1
_MAX_NOVELTY = 1.0
_SUMMARY_MAX_CHARS = 500


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _to_naive_utc(dt: datetime) -> datetime:
    """Coerce tz-aware or naive datetimes to naive UTC for cross-DB safety."""
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def _authority_for(source: str) -> float:
    return float(Config.SOURCE_AUTHORITY.get(source, 0.5))


def _novelty_for(member_count: int) -> Decimal:
    raw = 1.0 - (member_count / 10.0)
    clamped = max(_MIN_NOVELTY, min(_MAX_NOVELTY, raw))
    return Decimal(f"{clamped:.2f}")


def _clone_metadata_with_cluster(
    md: dict, cluster_id: UUID | None
) -> dict:
    """Return a new metadata dict with cluster_id updated (avoid mutating Chroma's copy)."""
    new_md = dict(md)
    new_md["cluster_id"] = str(cluster_id) if cluster_id else ""
    return new_md


async def cluster_item(
    item: NewsItem,
    *,
    session: AsyncSession,
    store: VectorStore,
    tickers: list[str] | None = None,
    threshold: float | None = None,
    now: datetime | None = None,
) -> UUID:
    """Assign `item` to an existing or new cluster. Returns the cluster id.

    `item` MUST already be in `news_items` (DB) and Chroma (per ING-08). The
    function mutates `item.cluster_id`, upserts the Chroma metadata, and
    commits. `tickers` is the extracted-tickers list from the normalizer
    (used only when creating a new cluster).
    """
    threshold = Config.CLUSTER_SIMILARITY_THRESHOLD if threshold is None else threshold
    tickers = tickers or []
    now_utc = (now or _now()).astimezone(timezone.utc)
    since_dt = now_utc - _LOOKBACK

    # 1. Fetch our own embedding out of Chroma. `embeddings` comes back as a
    # numpy array — use `len(...)` checks so numpy truthiness doesn't bite.
    got = store.get(ids=[str(item.id)], include=["embeddings", "metadatas"])
    embeddings = got.get("embeddings")
    if embeddings is None or len(embeddings) == 0:
        log.warning(
            "clusterer: no embedding for item %s; starting new cluster", item.id
        )
        return await _create_new_cluster(
            item, tickers=tickers, session=session, store=store, now=now_utc
        )
    vec = list(embeddings[0])
    metadatas_field = got.get("metadatas") or []
    self_md = dict(metadatas_field[0]) if len(metadatas_field) > 0 else {}

    # 2. Nearest neighbors. Chroma's `$gte` operator requires int/float, and
    # our metadata `published_at_iso` is a string, so filter client-side.
    result = store.query(
        query_embeddings=[vec],
        n_results=_TOP_K,
    )
    ids = result.get("ids", [[]])[0]
    distances = result.get("distances", [[]])[0]
    metadatas = result.get("metadatas", [[]])[0]

    best_cluster_id: UUID | None = None
    best_similarity: float = -1.0
    for i, doc_id in enumerate(ids):
        if doc_id == str(item.id):
            continue
        md = metadatas[i] or {}
        # Enforce 48h lookback client-side.
        published_iso = md.get("published_at_iso")
        if published_iso:
            try:
                pub_dt = datetime.fromisoformat(published_iso)
            except ValueError:
                continue
            if pub_dt < since_dt:
                continue
        cluster_id_str = (md.get("cluster_id") or "").strip()
        if not cluster_id_str:
            continue
        similarity = 1.0 - float(distances[i])
        if similarity > best_similarity:
            best_similarity = similarity
            try:
                best_cluster_id = UUID(cluster_id_str)
            except ValueError:
                continue

    if best_cluster_id is not None and best_similarity >= threshold:
        return await _attach_to_cluster(
            item,
            cluster_id=best_cluster_id,
            self_md=self_md,
            session=session,
            store=store,
            now=now_utc,
        )

    return await _create_new_cluster(
        item, tickers=tickers, session=session, store=store, now=now_utc, self_md=self_md
    )


# --- Cluster mutation helpers -----------------------------------------------


async def _create_new_cluster(
    item: NewsItem,
    *,
    tickers: list[str],
    session: AsyncSession,
    store: VectorStore,
    now: datetime,
    self_md: dict | None = None,
) -> UUID:
    summary = (item.body or "")[:_SUMMARY_MAX_CHARS] or None
    cluster = NewsCluster(
        canonical_title=item.title,
        canonical_summary=summary,
        first_seen_at=item.published_at,
        last_seen_at=item.published_at,
        entity_tickers=list(tickers),
        entity_topics=[],
        authority_score=Decimal(f"{_authority_for(item.source):.2f}"),
        novelty_score=_novelty_for(1),
        member_sources=[item.source],
    )
    session.add(cluster)
    await session.flush()
    item.cluster_id = cluster.id
    await session.commit()

    _mark_chroma_cluster(store, item.id, cluster.id, self_md)
    return cluster.id


async def _attach_to_cluster(
    item: NewsItem,
    *,
    cluster_id: UUID,
    self_md: dict | None,
    session: AsyncSession,
    store: VectorStore,
    now: datetime,
) -> UUID:
    cluster = (
        await session.execute(
            select(NewsCluster).where(NewsCluster.id == cluster_id)
        )
    ).scalar_one_or_none()
    if cluster is None:
        # Neighbor's cluster_id points at a row that isn't in the DB anymore.
        # Fall back to a fresh cluster to keep the pipeline moving.
        log.warning(
            "clusterer: neighbor referenced missing cluster %s; creating new",
            cluster_id,
        )
        return await _create_new_cluster(
            item, tickers=[], session=session, store=store, now=now, self_md=self_md
        )

    # sqlite drops tzinfo on round-trip; normalize both sides to naive UTC
    # for the comparison so downstream doesn't hit "can't compare naive+aware".
    item_pub = _to_naive_utc(item.published_at)
    cluster_last = _to_naive_utc(cluster.last_seen_at)
    if item_pub > cluster_last:
        cluster.last_seen_at = item.published_at

    sources = list(cluster.member_sources or [])
    if item.source not in sources:
        sources.append(item.source)
    cluster.member_sources = sources

    count_members = await _count_members(session, cluster.id) + 1  # +1 for the item being added
    cluster.authority_score = max(
        cluster.authority_score,
        Decimal(f"{_authority_for(item.source):.2f}"),
    )
    cluster.novelty_score = _novelty_for(count_members)

    item.cluster_id = cluster.id
    await session.commit()

    _mark_chroma_cluster(store, item.id, cluster.id, self_md)
    return cluster.id


async def _count_members(session: AsyncSession, cluster_id: UUID) -> int:
    result = await session.execute(
        select(NewsItem).where(NewsItem.cluster_id == cluster_id)
    )
    return len(list(result.scalars().all()))


def _mark_chroma_cluster(
    store: VectorStore, item_id: UUID, cluster_id: UUID, self_md: dict | None
) -> None:
    try:
        md = _clone_metadata_with_cluster(self_md or {}, cluster_id)
        store.update_metadata(ids=[str(item_id)], metadatas=[md])
    except Exception:
        log.exception(
            "clusterer: failed to update chroma metadata for %s", item_id
        )


# --- Convenience batch entrypoint -------------------------------------------


async def cluster_items(
    items: Iterable[NewsItem],
    *,
    session: AsyncSession,
    store: VectorStore,
    tickers_by_item_id: dict[UUID, list[str]] | None = None,
    threshold: float | None = None,
    now: datetime | None = None,
) -> list[UUID]:
    """Cluster a batch of items in order. Returns the cluster id for each."""
    tickers_by_item_id = tickers_by_item_id or {}
    out: list[UUID] = []
    for item in items:
        cluster_id = await cluster_item(
            item,
            session=session,
            store=store,
            tickers=tickers_by_item_id.get(item.id, []),
            threshold=threshold,
            now=now,
        )
        out.append(cluster_id)
    return out
