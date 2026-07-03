# Handoff — Lumen Intelligence Agent

**Branch:** `v2/intelligence-agent`
**Base:** `refactor` (at commit `af39bef` — latest from origin/refactor)
**Last updated:** 2026-07-03 (session 13 — ING-01 news schema)
**Progress:** 15/60 modules complete (HP-01, HP-02, BOOT-01..BOOT-08, DATA-01, DATA-02, DATA-03, DATA-05, ING-01). Phase 2 started.

DATA-04 remains postponed (needs ING-07).

---

## Next module

**ID:** `ING-02`
**Title:** NewsAPI adapter
**Depends on:** ING-01
**Read:** `BUILD.md` → the `ING-02` block.

**Branch state:** BOOT-01..BOOT-08 + DATA-01/02/03/05 + ING-01 stacked on `856d503`. `news_items`, `news_clusters`, and `ingest_runs` tables exist. Pydantic `NewsItemIn` is the target shape adapters produce. ING-02..ING-06 are the five source adapters; each returns `list[NewsItemIn]` and lets ING-08 do the URL hashing + upsert.

Before starting, verify:
- `git branch --show-current` shows `v2/intelligence-agent`.
- `git log --oneline -15` shows ING-01..HP-01 on top of `856d503` / `f7e479a`.
- `git status` is clean.
- `cd backend && python -m pytest tests -q` reports **74 passed, 1 deselected**.
- `ruff check .` clean.

---

## Last session

- **Session goal:** Execute ING-01 — three ingest tables (`news_clusters`, `news_items`, `ingest_runs`) + Pydantic schemas + migration that runs on both Postgres and sqlite CI. Prove url_hash unique constraint prevents duplicate inserts.
- **Completed:**
  - `ING-01` ✅ — news schema.
  - `backend/app/db/models/news.py` — three mapped classes:
    - `NewsCluster (IdMixin, CreatedAtMixin, Base)` — `canonical_title`, `canonical_summary`, `first_seen_at`, `last_seen_at`, `entity_tickers: list[str]`, `entity_topics: list[str]`, `authority_score` (Numeric 3,2), `novelty_score` (Numeric 3,2). Array columns use `postgresql.ARRAY(String).with_variant(JSON, "sqlite")`.
    - `NewsItem (IdMixin, Base)` — `cluster_id` FK to `news_clusters` `ON DELETE SET NULL`, `source` (CHECK against the 5-value allow-list), `source_id`, `url`, `url_hash` (UNIQUE), `title`, `body`, `published_at`, `ingested_at` (server_default now()), `raw_payload` (JSONB / JSON variant).
    - `IngestRun (IdMixin, Base)` — `source`, `started_at`, `finished_at`, `items_fetched`, `items_new`, `items_deduped`, `error`.
    - Composite index `idx_ingest_runs_source_started` on (source, started_at).
  - `backend/app/schemas/news.py` — Pydantic models `NewsItemIn`, `NewsItemRead`, `NewsClusterRead` (embeds `items: list[NewsItemRead]`), `IngestRunRead`.
  - `backend/app/db/models/__init__.py` — registered the three new classes.
  - `backend/alembic/versions/d2a235b04a85_ing01_news_items_clusters_ingest_runs.py` — hand-written migration. Variant helpers `_string_array()` / `_jsonb()` render as ARRAY / JSONB on Postgres and JSON on sqlite. `_is_postgres()` guard adds the GIN index on `entity_tickers` for Postgres only. Stripped the spurious `NUMERIC → UUID` alter_columns that autogenerate produces from sqlite's reflection quirk.
  - `backend/tests/db/test_news.py` — 4 tests: `test_news_item_insert_and_unique_url_hash` (proves url_hash UNIQUE), `test_source_check_constraint` (rejects `source="twitter"`), `test_cluster_delete_sets_item_cluster_id_null` (ON DELETE SET NULL round-trip, with `session.expire_all()` to force a fresh read since the fixture uses `expire_on_commit=False`), `test_ingest_run_row` (round-trip on the heartbeat table).
- **Acceptance verified locally:**
  - `alembic upgrade head` → `alembic downgrade -1` → `alembic upgrade head` runs cleanly on sqlite.
  - `python -m pytest tests -q` → **74 passed, 1 deselected**.
  - `ruff check .` clean.
- **Files touched:** created `backend/app/db/models/news.py`, `backend/app/schemas/news.py`, `backend/alembic/versions/d2a235b04a85_ing01_news_items_clusters_ingest_runs.py`, `backend/tests/db/test_news.py`. Modified `backend/app/db/models/__init__.py`, `BUILD.md` (tick), `HANDOFF.md` (this file).
- **Migrations added:** 1 — `d2a235b04a85`.
- **Tests added:** 4.
- **In-flight work:** none.
- **Deviations from BUILD.md:**
  - **`entity_tickers` / `entity_topics` dropped their `server_default '{}'`.** Postgres accepts `'{}'` for an empty ARRAY literal, but on sqlite (JSON variant) that string isn't valid JSON. Application-side `default=list` covers both dialects; NOT NULL is preserved so callers still have to pass a value at insert (or the default fires).
  - **GIN index on `entity_tickers` is Postgres-only.** Guarded by `if _is_postgres()` in the migration. sqlite CI runs without it; the query pattern that GIN accelerates (does any of my tickers match this cluster?) works via scan at portfolio-project scale.
  - **`entity_tickers` / `entity_topics` are `postgresql.ARRAY(String)` on Postgres and `JSON` on sqlite** (via `.with_variant()`). Downstream code that reads these fields gets `list[str]` in both dialects — the ORM handles the JSON→list conversion transparently. The Postgres-native `TEXT[]` shape matches BUILD.md's SQL spec.
  - **`raw_payload` is `JSONB` on Postgres, `JSON` on sqlite.** Same portability pattern.

---

## Environment state

- Backend: FastAPI app boots. Product tables now include the three ingest tables. `/api/*` routes: portfolios, positions, me. LLM wrapper live. Alembic head is `d2a235b04a85`.
- Frontend: unchanged.
- Database: three new tables on top of DATA-01. FKs / CHECKs work on both dialects (Postgres-only pieces guarded).
- Vectors: unchanged (none). ING-07 provisions Chroma.
- Tests: **74 hermetic, 1 opt-in.**
- CI: green on DATA-05 push.
- Docs: unchanged.

---

## Open questions / blockers

- **None.** ING-02..ING-06 are the five source adapters; ING-07 the vector store; ING-08 the normalizer; ING-09 the semantic-dedup; ING-10 the orchestrator. Order is roughly sequential per BUILD.md's dependency graph, though many adapters can be built independently.

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
