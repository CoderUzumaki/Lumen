# Handoff — Lumen Intelligence Agent

**Branch:** `v2/intelligence-agent`
**Base:** `refactor` (at commit `af39bef` — latest from origin/refactor)
**Last updated:** 2026-07-03 (session 21 — ING-08 normalizer + idempotent persist)
**Progress:** 23/60 modules complete (HP-01, HP-02, BOOT-01..BOOT-08, DATA-01..DATA-05, ING-01..ING-08).

**Worktree note:** The v2 branch is now checked out at `.claude/worktrees/v2` (was previously at `brave-benz-6b19f2`). If you're continuing from a fresh session, `cd` there.

---

## Next module

**ID:** `ING-09`
**Title:** Semantic dedup + clustering into `news_clusters`
**Depends on:** ING-07, ING-08
**Read:** `BUILD.md` → the `ING-09` block.

**Branch state:** BOOT-01..BOOT-08 + DATA-01/02/03/04/05 + ING-01..ING-08 stacked on `856d503`. Fetch layer + normalizer + idempotent DB persist + Chroma indexing all live. ING-09's job is: for each newly-inserted `news_items` row, find its nearest neighbours in the last 48h via Chroma, and either attach it to an existing `news_clusters` row (if similarity > `CLUSTER_SIMILARITY_THRESHOLD`) or create a new cluster.

Before starting, verify:
- `git branch --show-current` (from `.claude/worktrees/v2`) shows `v2/intelligence-agent`.
- `git log --oneline -23` shows ING-08..HP-01 on top of `856d503` / `f7e479a`.
- `git status` is clean.
- `cd backend && python -m pytest tests -q` reports **135 passed, 4 deselected**.
- `ruff check .` clean.

---

## Last session

- **Session goal:** Execute ING-08 — the normalizer that turns `NewsItemIn` into a `NormalizedItem` (canonical URL, url_hash, HTML-stripped body, ticker extraction) plus the idempotent bulk-insert into `news_items` with Chroma indexing.
- **Completed:**
  - `ING-08` ✅ — normalizer + persist.
  - `backend/app/pipelines/normalizer.py` — `_canonical_url()` lowercases host, drops fragment, drops every query param except `id`. `_url_hash()` = SHA-256 of canonical URL. `_strip_html()` uses `selectolax` (best-effort; falls back to raw on parse failure). `_extract_tickers()` finds `\b[A-Z]{1,5}(?:\.[A-Z])?\b` matches intersected with a caller-supplied `known_tickers` set (from the union of user positions). `normalize()` composes them, merges regex-extracted tickers with adapter-hinted `hints["tickers"]` (also filtered by `known_tickers`), truncates body to 8000 chars, returns a `NormalizedItem` dataclass.
  - `backend/app/pipelines/persist.py` — `persist(items, *, session, embed, store)`:
    - Intra-batch dedup by `url_hash` (preserves first-seen order).
    - Pre-SELECT existing `url_hash`es to compute skipped-count and to only re-index new rows in Chroma.
    - Dialect-dispatched `ON CONFLICT DO NOTHING`: `postgresql.insert(...).on_conflict_do_nothing(index_elements=["url_hash"])` on Postgres, `sqlite_insert(...)` on sqlite, plain `insert(...)` fallback for other dialects.
    - Fetches back the inserted rows, embeds `title + body[:1500]` via the injected `EmbeddingClient`, upserts into the `news_items` Chroma collection with the row's UUID as the doc id. Metadata: `cluster_id, source, published_at_iso`.
    - Chroma indexing wrapped in try/except (log-and-continue) so a vector-store outage doesn't fail the persist call after the DB commit.
    - Returns `(inserted_count, skipped_count)`.
  - `backend/tests/pipelines/test_normalizer.py` — 12 tests covering canonical URL, url_hash stability across tracking params, hash differs for different id, ticker intersection with known, empty known → empty tickers, url_hash from canonical URL, HTML stripping, tickers from title+body, body truncation at 8000, hint-tickers merge, other-fields preserved.
  - `backend/tests/pipelines/test_persist.py` — 5 tests: first persist inserts all, second persist skips all, Chroma docs have matching ids, empty input returns (0,0), intra-batch duplicate counted once.
  - **Fixed a wall-clock-sensitive GDELT test.** `tests/pipelines/sources/test_gdelt.py::test_429_retried_then_succeeds` was using `since=datetime.now(timezone.utc)` while the sample article's `seendate` is stamped `2026-07-03T13:00:00Z`. As real UTC time moved past that hour, the article filtered out of the fetch result. Pinned to `datetime(2026, 7, 3, tzinfo=timezone.utc)` (midnight) so drift doesn't affect it. Not caused by ING-08; unrelated latent bug surfaced during the full-suite run.
- **Acceptance verified locally:**
  - `python -m pytest tests -q` → **135 passed, 4 deselected**.
  - `ruff check .` clean.
- **Files touched:** created `backend/app/pipelines/normalizer.py`, `backend/app/pipelines/persist.py`, `backend/tests/pipelines/test_normalizer.py`, `backend/tests/pipelines/test_persist.py`. Modified `backend/tests/pipelines/sources/test_gdelt.py` (drift fix), `BUILD.md` (tick), `HANDOFF.md` (this file).
- **Migrations added:** none.
- **Tests added:** 17.
- **In-flight work:** none.
- **Deviations from BUILD.md:**
  - **`known_tickers` is a caller-supplied parameter, not derived inside `normalize()`.** BUILD.md's Action says "Extract ticker mentions with a lightweight regex + known-ticker set (from all users' positions)." The DB query for the union of user positions is best done by the caller (the orchestrator in ING-10) so `normalize()` stays pure + testable + doesn't need a session. Same idea for `EmbeddingClient` and `VectorStore` on `persist()` — both injected.
  - **`persist()` also short-circuits on Chroma failure.** BUILD.md doesn't specify; treating vector-store outages as non-fatal keeps the DB source of truth authoritative. A future cleanup module can reconcile orphan DB rows (rows without a matching Chroma doc).
  - **Skipped-count uses a pre-INSERT SELECT rather than `RETURNING`.** Portable across sqlite (which has RETURNING in modern versions but SQLAlchemy support varies) and Postgres. Race-safe enough at portfolio-project scale; a stricter implementation would use `RETURNING id` and compare against the intended set.

---

## Environment state

- Backend: full fetch → normalize → persist → index pipeline available in Python. Chroma `news_items` gets populated by `persist()`. `news_clusters` still empty — that's ING-09's job.
- Frontend: unchanged.
- Database: unchanged (Alembic head `d2a235b04a85`).
- Vectors: `news_items` collection now written to by the persist pipeline.
- Tests: **135 hermetic, 4 opt-in.**
- CI: last successful run on DATA-04 (`8373f83`); pending on the ING-08 push.
- Docs: unchanged.

---

## Open questions / blockers

- **None.** ING-09 is the next natural step in the pipeline sequence.

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
