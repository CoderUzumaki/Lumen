# Handoff — Lumen Intelligence Agent

**Branch:** `v2/intelligence-agent`
**Base:** `refactor` (at commit `af39bef` — latest from origin/refactor)
**Last updated:** 2026-07-03 (session 22 — ING-09 semantic dedup + clustering)
**Progress:** 24/60 modules complete (HP-01, HP-02, BOOT-01..BOOT-08, DATA-01..DATA-05, ING-01..ING-09). Only ING-10 (orchestrator) remains for Phase 2.

**Worktree note:** v2 branch checked out at `.claude/worktrees/v2`.

---

## Next module

**ID:** `ING-10`
**Title:** Ingestion orchestrator + APScheduler
**Depends on:** ING-01..ING-09
**Read:** `BUILD.md` → the `ING-10` block.

**Branch state:** BOOT-01..BOOT-08 + DATA-01/02/03/04/05 + ING-01..ING-09 stacked on `856d503`. Full ingest → normalize → persist → cluster pipeline is available in Python. ING-10 wires it into a scheduled run via APScheduler (`INGEST_INTERVAL_MINUTES` = 15 by default, per BUILD.md §Environment variables).

Before starting, verify:
- `git branch --show-current` (from `.claude/worktrees/v2`) shows `v2/intelligence-agent`.
- `git log --oneline -24` shows ING-09..HP-01 on top of `856d503` / `f7e479a`.
- `git status` is clean.
- `cd backend && python -m pytest tests -q` reports **141 passed, 4 deselected**.
- `ruff check .` clean.

---

## Last session

- **Session goal:** Execute ING-09 — assign each newly-inserted `news_items` row to an existing `news_clusters` (if similarity ≥ 0.87 to a neighbor from the last 48h) or create a fresh cluster.
- **Completed:**
  - `ING-09` ✅ — clusterer.
  - **Config:** added `SOURCE_AUTHORITY` dict (`newsapi/marketaux=0.60, gdelt=0.50, edgar=0.95, rss=0.70`) via `_env_json` — override via env with a full JSON object. Also documented in `backend/.env.example`.
  - **Model:** `NewsCluster.member_sources` — `list[str]` column tracking which source ids have contributed to this cluster. `ARRAY(String)` on Postgres, `JSON` on sqlite via `.with_variant()`.
  - **Migration `a1c4e5f2d901_ing09_news_clusters_member_sources.py`:** dialect-dispatched ADD COLUMN. Postgres uses `server_default '{}'::text[]`; sqlite adds nullable, backfills `[]`, then `batch_alter_table` sets NOT NULL.
  - **Vectorstore:** `_COLLECTION_METADATA` now specifies `{"hnsw:space": "cosine"}` for all three collections. `init_collections()` and `VectorStore.__init__` pass it to `get_or_create_collection(metadata=...)`. Added `VectorStore.get(ids, include)` and `VectorStore.update_metadata(ids, metadatas)` methods for clusterer's read/tag flow.
  - `backend/app/pipelines/clusterer.py` — `cluster_item(item, *, session, store, tickers, threshold, now)`:
    - Fetches the item's own embedding from Chroma.
    - Queries top-6 nearest neighbors, filters client-side to the 48h window (Chroma's `$gte` operator requires int/float, so a string ISO comparison isn't viable — client-side filter is portable).
    - Excludes self, picks the best neighbor with a valid `cluster_id` metadata field.
    - `similarity = 1 - distance` (cosine-space collection ⇒ distance in [0,2], similarity in [-1,1]).
    - Threshold ≥ 0.87 (default from `Config.CLUSTER_SIMILARITY_THRESHOLD`) → attach to that cluster. Else → new cluster.
    - `_attach_to_cluster`: bumps `last_seen_at`, adds source to `member_sources`, recomputes authority = max of member weights, novelty = clamp(1 - member_count/10, [0.1, 1.0]).
    - `_create_new_cluster`: seeds canonical_title/summary from `item.title`/`item.body[:500]`, entity_tickers from caller-supplied list, authority from item's source, novelty at count=1.
    - Chroma metadata gets stamped with the new `cluster_id` so future queries see it.
    - `cluster_items()` convenience wrapper for batches.
    - `_to_naive_utc()` helper — sqlite drops tzinfo on round-trip; comparing `item.published_at` (aware) to a re-loaded `cluster.last_seen_at` (naive) would raise; coercing both to naive UTC keeps the comparison portable.
  - `backend/tests/pipelines/test_clusterer.py` — 6 tests:
    - `test_three_near_duplicates_end_up_in_one_cluster` — the primary acceptance case; verifies `member_sources` grew to {newsapi, rss, gdelt} and authority_score = 0.70 (max).
    - `test_unrelated_articles_end_up_in_different_clusters` — orthogonal vectors, distinct clusters.
    - `test_similarity_below_threshold_gets_new_cluster` — belt-and-suspenders confirmation of the threshold.
    - `test_second_article_beyond_48h_starts_new_cluster` — 48h client-side filter.
    - `test_novelty_score_decays_with_members` — 5 members ⇒ novelty=0.50.
    - `test_chroma_metadata_gets_cluster_id_stamped` — verifies the update_metadata call sticks.
- **Acceptance verified locally:**
  - `alembic upgrade head` → `alembic downgrade -1` → `alembic upgrade head` runs cleanly on sqlite.
  - `python -m pytest tests -q` → **141 passed, 4 deselected**.
  - `ruff check .` clean.
- **Files touched:** created `backend/app/pipelines/clusterer.py`, `backend/tests/pipelines/test_clusterer.py`, `backend/alembic/versions/a1c4e5f2d901_ing09_news_clusters_member_sources.py`. Modified `backend/app/db/models/news.py` (`member_sources` column), `backend/app/db/vectorstore.py` (cosine metadata + `get`/`update_metadata`), `backend/app/utils/config.py` (`SOURCE_AUTHORITY`), `backend/.env.example` (`SOURCE_AUTHORITY`), `BUILD.md` (tick), `HANDOFF.md` (this file).
- **Migrations added:** 1 — `a1c4e5f2d901`.
- **Tests added:** 6.
- **In-flight work:** none.
- **Deviations from BUILD.md:**
  - **48h lookback filter is client-side.** BUILD.md says "query Chroma news_items for the top-5 nearest neighbors published within the last 48h." Chroma's `$gte` requires int/float, and my `published_at_iso` metadata is a string, so the WHERE-clause filter isn't viable without a schema change to store `published_at_ts` as a float. Post-query Python filter is portable and correct at portfolio-project scale; a follow-up module can add the numeric metadata field for large-scale query performance.
  - **Chroma collections are now cosine-space.** ING-07 originally created collections without an explicit `hnsw:space`, defaulting to L2. Since the ING-07 tests pass identical assertions under either metric (orthogonal fake vectors), this change is transparent to them; fresh dev/CI runs use cosine as intended. Any existing production Chroma index would need a re-embed to migrate — non-issue pre-production.
  - **Similarity threshold is applied to `1 - distance` in code rather than natively via Chroma.** Straightforward given cosine-space collections; documented in the clusterer.
  - **`_to_naive_utc()` normalizer for the last-seen-at comparison.** Not spec'd; sqlite's DateTime column doesn't preserve tzinfo on round-trip, so a fresh-in-memory tz-aware `item.published_at` can't be compared directly to a reloaded `cluster.last_seen_at` without coercion.

---

## Environment state

- Backend: full fetch → normalize → persist → cluster pipeline. `news_clusters.member_sources` growing per source. Chroma cosine-space collections.
- Frontend: unchanged.
- Database: Alembic head `a1c4e5f2d901`.
- Vectors: three collections in cosine space.
- Tests: **141 hermetic, 4 opt-in.**
- CI: last run on ING-08 push. ING-09 push will trigger a fresh one.
- Docs: unchanged.

---

## Open questions / blockers

- **None.** ING-10 (orchestrator + APScheduler) is the last piece of Phase 2. Then the DB is fed continuously and Phase 3 (REL-01..REL-07 relevance engine) can start turning it into scored per-user signal.

---

## Rules for the next session

1. **Read `HANDOFF.md` first** (this file). Do this before anything else.
2. **Read `PRD.md`** (all of it — it's short). Non-goals and principles are vetoes.
3. **Read the `BUILD.md` block for the "Next module" ID above.** Do NOT read other module blocks unless the current one lists them as dependencies.
4. **Do NOT re-read the entire repo.** Files outside the module's scope are irrelevant.
5. **Implement the module and only the module.** Match Acceptance criteria literally.
6. **Do NOT expand scope.** If you notice an adjacent problem, add it as a new module ID in `BUILD.md` — don't fold it into the current work.
7. **Before ending the session:**
   - Tick the module's checkbox in `BUILD.md` (append ` ✅` to the module heading).
   - Add a one-line deviation note if reality diverged from spec.
   - Update this `HANDOFF.md` (rewrite "Last session", advance "Next module", update "Progress" count).
   - Commit with message: `<MODULE-ID>: <one-line summary>`.
8. **If blocked on a decision that requires human judgment,** stop and ask. Do not silently pick.

---

## Reference

- **PRD:** `PRD.md`
- **Build plan:** `BUILD.md`
- **This file:** `HANDOFF.md`
- **Discarded trajectory's TODO:** `TODO.md` (preserved for historical reference — do not delete, do not follow).
