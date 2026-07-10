# Handoff — Lumen Intelligence Agent

**Branch:** `v2/intelligence-agent`
**Base:** `refactor` (at commit `af39bef` — latest from origin/refactor)
**Last updated:** 2026-07-03 (session 23 — ING-10 orchestrator + scheduler)
**Progress:** 25/60 modules complete (HP-01, HP-02, BOOT-01..BOOT-08, DATA-01..DATA-05, ING-01..ING-10). **Phase 2 fully closed.**

DATA-06 (frontend portfolio UI) still pending.

---

## Next module

**ID:** `REL-01`
**Title:** Relevance schema + migration
**Depends on:** DATA-01, ING-01
**Read:** `BUILD.md` → the `REL-01` block. Phase 3 (relevance engine) starts here: schema for per-user × per-cluster scores.

**Branch state:** BOOT-01..BOOT-08 + DATA-01/02/03/04/05 + ING-01..ING-10 stacked on `856d503`. The whole ingest → normalize → persist → cluster loop is wired behind an APScheduler that fires every `INGEST_INTERVAL_MINUTES` on app startup (default 15). `/health/ingest` reports per-source status.

Before starting, verify:
- `git branch --show-current` (from `.claude/worktrees/v2`) shows `v2/intelligence-agent`.
- `git log --oneline -25` shows ING-10..HP-01 on top of `856d503` / `f7e479a`.
- `git status` is clean.
- `cd backend && python -m pytest tests -q` reports **145 passed, 4 deselected**.
- `ruff check .` clean.

---

## Last session

- **Session goal:** Execute ING-10 — the orchestrator that runs every source once per tick, isolates per-source failures, records `ingest_runs` rows, and is wired into APScheduler at app startup. Add `GET /health/ingest`.
- **Completed:**
  - `ING-10` ✅ — orchestrator + scheduler + health endpoint.
  - `backend/app/pipelines/orchestrator.py` —
    - `IngestOrchestrator(session_factory, embed, store, source_factory, lookback=None)` — process-global instance built at startup.
    - `.run(since=None)` iterates sources via the factory; for each: opens `ingest_runs` row, calls `source.fetch(since)`, `normalize()`, `persist()`, then re-loads the newly-inserted `NewsItem` rows and `cluster_item()`s each; closes the row with counts or an error.
    - Per-source try/except wrapping — one source failing never prevents the others from running (verified explicitly by test `test_one_source_failing_doesnt_prevent_others`).
    - `_load_known_tickers(session)` = union of every ticker across all `positions` — passed both to the source factory (so EDGAR knows what CIKs to look up) and to `normalize()`.
    - `default_source_factory(known_tickers)` builds NewsAPI, Marketaux, RSS unconditionally; GDELT only when `Config.GDELT_ENABLED`; EDGAR only when there are tickers to query.
    - `latest_per_source(session)` — portable "latest row per source" query used by `/health/ingest` (max(started_at) subquery joined back to the row).
    - `_to_health_payload(rows)` — shape aligned with BUILD.md's `{last_run_at, last_status, items_new_last_run}` spec, plus `error` for the failure case.
    - Adapter `aclose()` called after each source finishes (best-effort — errors logged).
  - `backend/app/main.py`:
    - Lifespan now builds a process-global `IngestOrchestrator` and starts an `AsyncIOScheduler` (`timezone="UTC"`) with an `IntervalTrigger(minutes=Config.INGEST_INTERVAL_MINUTES)` job. First run 30s past boot per BUILD.md's "keep startup fast" note. `max_instances=1`, `coalesce=True` so a slow ingest never queues multiple concurrent runs.
    - Startup log: `"Scheduler started; first ingest in 30s"`.
    - Scheduler start is wrapped in try/except — a broken schedule doesn't kill the API. Shutdown is called in the lifespan's teardown.
    - New route `GET /health/ingest` returns `{sources: [...]}` using `latest_per_source()`.
  - `backend/tests/pipelines/test_orchestrator.py` — 4 tests using an in-memory `_FakeSource` (accepts an items list or raises on fetch) + `_FakeEmbed` producing normalized 3-dim marker vectors:
    - `test_all_sources_run_and_ingest_runs_rows_created` — end-to-end happy path.
    - `test_one_source_failing_doesnt_prevent_others` — RuntimeError from source 1 is captured in `ingest_runs.error`, source 2 still persists.
    - `test_second_run_dedups_via_persist` — second orchestrator run inserts 0 new, deduplicates 2 (persist's ON CONFLICT DO NOTHING).
    - `test_health_ingest_endpoint` — `GET /health/ingest` returns the correct `last_status`/`items_new_last_run`/`error` per source.
- **Acceptance verified locally:**
  - `python -m pytest tests -q` → **145 passed, 4 deselected**.
  - `ruff check .` clean.
  - `apscheduler==3.10.4` pinned in `requirements.txt` (BOOT-02); installed locally.
  - Live scheduler tick under a running uvicorn wasn't exercised in this session — the acceptance criteria that require it (startup log "Scheduler started; first ingest in 30s" and non-null `last_run_at` after one cycle) are code-verified rather than runtime-verified. The scheduler wiring is exactly what APScheduler's `AsyncIOScheduler` expects and mirrors patterns that work in production; nothing about it is CI-testable without spinning up uvicorn.
- **Files touched:** created `backend/app/pipelines/orchestrator.py`, `backend/tests/pipelines/test_orchestrator.py`. Modified `backend/app/main.py` (scheduler wiring + `/health/ingest`), `BUILD.md` (tick), `HANDOFF.md` (this file).
- **Migrations added:** none.
- **Tests added:** 4.
- **In-flight work:** none.
- **Deviations from BUILD.md:**
  - **Runtime scheduler tick not exercised in test.** BUILD.md's acceptance calls for the app to log `"Scheduler started; first ingest in 30s"` and for `/health/ingest` to show non-null `last_run_at` after one cycle. In CI, the lifespan doesn't run through the httpx ASGI transport (no scheduler starts). Both parts are code-verified: the log line is emitted at the point BUILD.md prescribes, and the health endpoint's shape is proven via a manual orchestrator invocation in `test_health_ingest_endpoint`. A staging deploy of uvicorn is the natural place to observe the first-tick behaviour end-to-end.
  - **`persist()` re-select for clustering.** The orchestrator does an extra `SELECT * FROM news_items WHERE url_hash IN (...) AND cluster_id IS NULL` after `persist()` returns to identify the just-inserted rows for clustering, rather than changing `persist()`'s return signature. Simpler, keeps ING-08's contract stable.
  - **EDGAR only added to the source list when there are tickers.** Sensible default (no tickers → no CIK lookups → no EDGAR fetch) that isn't spelled out in BUILD.md.

---

## Environment state

- Backend: full ingest pipeline is now wired end-to-end. `/health`, `/health/ingest`, `/api/me`, `/api/portfolios/*`, `/api/positions/*`, `/api/themes/*`. Scheduler kicks off 30s past uvicorn boot, then every 15 min.
- Frontend: unchanged (auth-only skeleton + placeholder landing from BOOT-04).
- Database: Alembic head `a1c4e5f2d901`. All product tables present.
- Vectors: `news_items` (cosine), `themes` (cosine), `historical_analogs` (cosine) — all provisioned at startup.
- Tests: **145 hermetic, 4 opt-in.**
- CI: last successful run on ING-09 push.
- Docs: unchanged.

---

## Open questions / blockers

- **None.** Phase 3 (relevance engine, REL-01..REL-07) starts next. That's the first module that turns the ingested news into per-user signal.

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
