# Handoff — Lumen Intelligence Agent

**Branch:** `v2/intelligence-agent`
**Base:** `refactor` (at commit `af39bef` — latest from origin/refactor)
**Last updated:** 2026-07-03 (session 15 — ING-03 Marketaux adapter)
**Progress:** 17/60 modules complete (HP-01, HP-02, BOOT-01..BOOT-08, DATA-01, DATA-02, DATA-03, DATA-05, ING-01, ING-02, ING-03).

DATA-04 postponed (needs ING-07).

---

## Next module

**ID:** `ING-04`
**Title:** GDELT adapter
**Depends on:** ING-01
**Read:** `BUILD.md` → the `ING-04` block. GDELT's DOC 2.0 API has no API key (unlimited free), soft rate-limit ~1 req/sec. Adapter needs a semaphore to serialize calls.

**Branch state:** BOOT-01..BOOT-08 + DATA-01/02/03/05 + ING-01/02/03 stacked on `856d503`. `NewsItemIn` now has an optional `hints: dict[str, Any] = {}` field. `NewsAPISource` + `MarketauxSource` share the same never-raise contract via `BaseSource`.

Before starting, verify:
- `git branch --show-current` shows `v2/intelligence-agent`.
- `git log --oneline -17` shows ING-03..HP-01 on top of `856d503` / `f7e479a`.
- `git status` is clean.
- `cd backend && python -m pytest tests -q` reports **86 passed, 1 deselected**.
- `ruff check .` clean.

---

## Last session

- **Session goal:** Execute ING-03 — Marketaux adapter matching the NewsAPI adapter's shape, plus extension of `NewsItemIn` to carry Marketaux's structured entity hints.
- **Completed:**
  - `ING-03` ✅ — Marketaux adapter.
  - `backend/app/schemas/news.py` — added `hints: dict[str, Any] = Field(default_factory=dict)` to `NewsItemIn`. BUILD.md interpretation: "add it to the schema as `hints: dict = {}`" is the field; adapters populate keys like `hints["tickers"]` for extensibility.
  - `backend/app/pipelines/sources/marketaux.py` — `MarketauxSource(BaseSource)`. Endpoint `https://api.marketaux.com/v1/news/all` with the exact query params from BUILD.md (`filter_entities=true`, `language=en`, `limit=50`, `published_after=<since ISO>`, `api_token=<key>`). Extracts `entities[].symbol` values from each row (deduping while preserving order) into `NewsItemIn.hints["tickers"]`; omits the key entirely when no entities are present so `hints == {}`. Body falls back from `description` → `snippet`. Same never-raise contract: missing key logs and returns `[]`; retries on 429 / 5xx / transport; exhausted retries return `[]`; malformed row is skipped.
  - `backend/tests/pipelines/sources/test_marketaux.py` — 6 tests: hints_tickers populated + deduped + order-preserved, missing API key → empty, 429 retried then succeeds, exhausted retries → empty, non-retryable 4xx → empty, malformed row is skipped.
- **Acceptance verified locally:**
  - `python -m pytest tests -q` → **86 passed, 1 deselected**.
  - `ruff check .` clean.
- **Files touched:** created `backend/app/pipelines/sources/marketaux.py`, `backend/tests/pipelines/sources/test_marketaux.py`. Modified `backend/app/schemas/news.py` (added `hints` field), `BUILD.md` (tick), `HANDOFF.md` (this file).
- **Migrations added:** none.
- **Tests added:** 6.
- **In-flight work:** none.
- **Deviations from BUILD.md:** none. The one interpretive call was "`hints_tickers: list[str]` field on the NewsItemIn (a new optional field — add it to the schema as `hints: dict = {}` for extensibility)" — read as: schema stores `hints: dict`, Marketaux populates `hints["tickers"]`. That preserves extensibility (future adapters can add `hints["topics"]`, `hints["sentiment"]`, …) without a schema change per source.

---

## Environment state

- Backend: three adapters now — `BaseSource` (abstract), `NewsAPISource`, `MarketauxSource`. None wired into an orchestrator yet — ING-10 owns that.
- Frontend: unchanged.
- Database: unchanged.
- Vectors: unchanged (none).
- Tests: **86 hermetic, 1 opt-in.**
- CI: green on ING-02 push.
- Docs: unchanged.

---

## Open questions / blockers

- **None.** ING-04 (GDELT) is next — no API key needed, soft rate limit ~1 req/sec via semaphore, ArtList JSON format.

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
