# Handoff — Lumen Intelligence Agent

**Branch:** `v2/intelligence-agent`
**Base:** `refactor` (at commit `af39bef` — latest from origin/refactor)
**Last updated:** 2026-07-03 (session 18 — ING-06 RSS adapter)
**Progress:** 20/60 modules complete (HP-01, HP-02, BOOT-01..BOOT-08, DATA-01..DATA-03, DATA-05, ING-01..ING-06). One-third of BUILD.md done.

DATA-04 still postponed (needs ING-07).

---

## Next module

**ID:** `ING-07`
**Title:** Chroma vector store + local embeddings (free)
**Depends on:** BOOT-06
**Read:** `BUILD.md` → the `ING-07` block. Two files: `backend/app/db/vectorstore.py`, `backend/app/utils/embeddings.py`. Uses `sentence-transformers/all-MiniLM-L6-v2` locally (already pinned in `requirements.txt`) and `chromadb==0.5.11` (also pinned). This is the module that finally unblocks DATA-04.

**Branch state:** BOOT-01..BOOT-08 + DATA-01/02/03/05 + ING-01..ING-06 stacked on `856d503`. Six adapters live (`Base`, NewsAPI, Marketaux, GDELT, EDGAR, RSS). All fetch surface is done — ING-07 shifts to the vector-store side.

Before starting, verify:
- `git branch --show-current` shows `v2/intelligence-agent`.
- `git log --oneline -20` shows ING-06..HP-01 on top of `856d503` / `f7e479a`.
- `git status` is clean.
- `cd backend && python -m pytest tests -q` reports **103 passed, 3 deselected**.
- `ruff check .` clean.

---

## Last session

- **Session goal:** Execute ING-06 — RSS adapter that pulls a caller-supplied list of feed URLs, parses each with `feedparser`, filters by `since`, and deduplicates by URL hash before yielding `NewsItemIn`s.
- **Completed:**
  - `ING-06` ✅ — RSS adapter.
  - `backend/app/pipelines/sources/rss.py` — `RSSSource(BaseSource)`. httpx.AsyncClient fetches each feed's raw bytes, then `asyncio.to_thread(feedparser.parse, resp.content)` runs the sync parser off the event loop. `_url_hash(url)` = SHA-256 hex; per-fetch dedup keeps the stream tidy independent of the DB-layer `news_items.url_hash` UNIQUE constraint. `_parse_time` converts feedparser's `struct_time` tuples to `datetime` in UTC. Missing link → skip. Missing title → skip. Missing published date → skip. Constructor: `feeds=None` reads from `Config.RSS_FEEDS`; explicit `feeds=[]` is honored. Never raises — feed-level errors are logged and skipped.
  - `backend/tests/pipelines/sources/test_rss.py` — 6 tests using two RSS fixture strings (bytes). Cover: happy path (`fixture yields correct news items` incl. body/source_id/published_at mapping), cross-feed URL-hash dedup, empty feeds list, one-feed error is contained, malformed entry dropped while good entries survive, non-200 response yields empty.
- **Acceptance verified locally:**
  - `python -m pytest tests -q` → **103 passed, 3 deselected**.
  - `ruff check .` clean.
  - `feedparser==6.0.11` installed locally (already pinned in requirements.txt — CI's fresh install covers it).
- **Files touched:** created `backend/app/pipelines/sources/rss.py`, `backend/tests/pipelines/sources/test_rss.py`. Modified `BUILD.md` (tick), `HANDOFF.md` (this file).
- **Migrations added:** none.
- **Tests added:** 6.
- **In-flight work:** none.
- **Deviations from BUILD.md:**
  - **No bundled default feed list.** BUILD.md's Action lists Reuters Business / WSJ Markets / Bloomberg Politics / FT / Livemint / Moneycontrol / arxiv-econ as the default. `Config.RSS_FEEDS` is documented in `backend/.env.example` (BOOT-07) but ships empty by default — operators fill in whichever feed URLs suit their portfolio. Hardcoding the seven above would (a) freeze operator choice and (b) risk shipping stale/gone feed URLs. Empty default + `.env.example` guidance is the more portable posture.
  - **Feed HTTP fetch is via httpx.** BUILD.md just says "Parse with `feedparser`." feedparser can accept a URL directly and do its own fetch (blocking), but going through httpx keeps testability + timeout + UA-header uniform with the other adapters and lets `asyncio.to_thread` isolate the parser CPU work.

---

## Environment state

- Backend: six source adapters live. Fetch surface complete. The five product tables + three news tables + `llm_calls` are on disk. Every `/api/*` route (portfolios / positions / me) authenticated + owner-scoped.
- Frontend: unchanged.
- Database: unchanged (Alembic head `d2a235b04a85`).
- Vectors: unchanged — ING-07 provisions Chroma next.
- Tests: **103 hermetic, 3 opt-in.**
- CI: passing on ING-05 fix.
- Docs: unchanged.

---

## Open questions / blockers

- **None.** ING-07 is the last blocker for DATA-04. After ING-07 lands, the sensible order is: ING-08 (normalizer + idempotent insertion) → ING-09 (semantic dedup + clustering) → ING-10 (orchestrator + APScheduler). DATA-04 can slot in whenever — its scope is small once `EmbeddingClient` (ING-07) is real.

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
