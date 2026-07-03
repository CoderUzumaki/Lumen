# Handoff — Lumen Intelligence Agent

**Branch:** `v2/intelligence-agent`
**Base:** `refactor` (at commit `af39bef` — latest from origin/refactor)
**Last updated:** 2026-07-03 (session 14 — ING-02 NewsAPI adapter)
**Progress:** 16/60 modules complete (HP-01, HP-02, BOOT-01..BOOT-08, DATA-01, DATA-02, DATA-03, DATA-05, ING-01, ING-02).

DATA-04 postponed (needs ING-07).

---

## Next module

**ID:** `ING-03`
**Title:** Marketaux adapter
**Depends on:** ING-01
**Read:** `BUILD.md` → the `ING-03` block. Notable: ING-03 asks for a NEW optional `hints: dict = {}` (or `hints_tickers: list[str]`) field on `NewsItemIn` for Marketaux's `entities[].symbol` payload. `NewsItemIn` in `backend/app/schemas/news.py` doesn't yet have that field — ING-03 adds it.

**Branch state:** BOOT-01..BOOT-08 + DATA-01/02/03/05 + ING-01/02 stacked on `856d503`. `NewsAPISource` is the first live adapter and the pattern for the other four; base class `BaseSource` in `app/pipelines/sources/base.py` defines the interface.

Before starting, verify:
- `git branch --show-current` shows `v2/intelligence-agent`.
- `git log --oneline -16` shows ING-02..HP-01 on top of `856d503` / `f7e479a`.
- `git status` is clean.
- `cd backend && python -m pytest tests -q` reports **80 passed, 1 deselected**.
- `ruff check .` clean.

---

## Last session

- **Session goal:** Execute ING-02 — NewsAPI adapter that returns `list[NewsItemIn]`, handles missing keys gracefully, and retries on 429 / 5xx / transport errors.
- **Completed:**
  - `ING-02` ✅ — NewsAPI adapter.
  - `backend/app/pipelines/__init__.py` + `backend/app/pipelines/sources/__init__.py` (empty package markers).
  - `backend/app/pipelines/sources/base.py` — `BaseSource` ABC with `source_name: str` class attribute and `async def fetch(self, since: datetime) -> list[NewsItemIn]`. Contract: never raise on transient failures, never raise on missing credentials, retry internally.
  - `backend/app/pipelines/sources/newsapi.py` — `NewsAPISource(BaseSource)`. Query params match BUILD.md exactly (`q="finance OR markets OR stocks OR fed OR earnings"`, `language=en`, `sortBy=publishedAt`, `pageSize=100`, `from=<since ISO>`). Missing API key → warning + `[]`. Tenacity retry (3 attempts, exponential backoff) on 429 / 5xx / transport errors; on retry-exhaustion returns `[]`. Non-retryable 4xx → warning + `[]`. Individual malformed article → skipped, not fatal. `source_id` maps from `article["source"]["id"]` (may be null); `body` falls back to `description` when `content` is absent.
  - `backend/tests/pipelines/__init__.py` + `backend/tests/pipelines/sources/__init__.py` package markers.
  - `backend/tests/pipelines/sources/test_newsapi.py` — 6 tests: mapping of 3 items with mixed shapes (missing id, missing content), missing-API-key returns empty without hitting network, 429 retried then succeeds, retry exhaustion returns empty (not raises), non-retryable 4xx returns empty, malformed article is skipped.
- **Acceptance verified locally:**
  - `python -m pytest tests -q` → **80 passed, 1 deselected**.
  - `ruff check .` clean.
- **Files touched:** created `backend/app/pipelines/{__init__.py,sources/{__init__.py,base.py,newsapi.py}}`, `backend/tests/pipelines/{__init__.py,sources/{__init__.py,test_newsapi.py}}`. Modified `BUILD.md` (tick), `HANDOFF.md` (this file).
- **Migrations added:** none.
- **Tests added:** 6.
- **In-flight work:** none.
- **Deviations from BUILD.md:** none. ING-02's spec is small and the implementation follows it literally. The exhaust-retries-returns-empty behaviour is broader than "log a warning" (BUILD.md's `on empty API key` wording) but consistent with the BaseSource contract ("never raise on transient failures"). Test file lives at `tests/pipelines/sources/test_newsapi.py`.

---

## Environment state

- Backend: two adapters exist — one abstract (`BaseSource`), one concrete (`NewsAPISource`). `NewsAPISource` is not yet called by anything; ING-10 wires the orchestrator that fans out across all enabled sources.
- Frontend: unchanged.
- Database: unchanged.
- Vectors: unchanged (none).
- Tests: **80 hermetic, 1 opt-in.**
- CI: green on ING-01 push.
- Docs: unchanged.

---

## Open questions / blockers

- **None.** ING-03 is the next adapter (Marketaux). Its addition of `hints_tickers` / `hints: dict` will need an update to `NewsItemIn` in `backend/app/schemas/news.py` — BUILD.md flags this explicitly in ING-03's Action.

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
