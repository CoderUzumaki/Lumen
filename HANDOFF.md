# Handoff — Lumen Intelligence Agent

**Branch:** `v2/intelligence-agent`
**Base:** `refactor` (at commit `af39bef` — latest from origin/refactor)
**Last updated:** 2026-07-03 (session 16 — ING-04 GDELT adapter)
**Progress:** 18/60 modules complete (HP-01, HP-02, BOOT-01..BOOT-08, DATA-01, DATA-02, DATA-03, DATA-05, ING-01, ING-02, ING-03, ING-04).

DATA-04 postponed (needs ING-07).

---

## Next module

**ID:** `ING-05`
**Title:** EDGAR adapter
**Depends on:** ING-01
**Read:** `BUILD.md` → the `ING-05` block. Notable: needs a bundled `ticker_to_cik.json` map for the top 3000 US tickers (or fetched once at startup — call is a decision). Uses `EDGAR_USER_AGENT` env var per SEC fair-use policy.

**Branch state:** BOOT-01..BOOT-08 + DATA-01/02/03/05 + ING-01/02/03/04 stacked on `856d503`. Four adapters live: `NewsAPISource`, `MarketauxSource`, `GDELTSource`. Two markers registered — `free_tier_live` (LLM live probe) and `integration` (source live probes). Both opt-in via `pytest -m …`.

Before starting, verify:
- `git branch --show-current` shows `v2/intelligence-agent`.
- `git log --oneline -18` shows ING-04..HP-01 on top of `856d503` / `f7e479a`.
- `git status` is clean.
- `cd backend && python -m pytest tests -q` reports **92 passed, 2 deselected**.
- `ruff check .` clean.

---

## Last session

- **Session goal:** Execute ING-04 — GDELT adapter (no API key, ~1 req/sec soft rate limit, ArtList JSON format).
- **Completed:**
  - `ING-04` ✅ — GDELT adapter.
  - `backend/app/pipelines/sources/gdelt.py` — `GDELTSource(BaseSource)`. Endpoint `https://api.gdeltproject.org/api/v2/doc/doc`; query params `mode=ArtList`, `format=JSON`, `sort=DateDesc`, `maxrecords=250`, and `startdatetime` in GDELT's `YYYYMMDDHHMMSS` shape. Class-level `asyncio.Semaphore(1)` + inter-request `_MIN_INTERVAL_S` (1.0s) enforce the ~1 req/sec ceiling across all instances of the adapter — the shared state pattern GDELT's per-IP throttle needs. `seendate` is parsed from `%Y%m%dT%H%M%SZ` (no separators). `source_id` is null (GDELT has no stable id). `hints["domain"]` is set when the article has a domain. Server-side `startdatetime` filter is backed up by a client-side re-check so items older than `since` are dropped even if the server returned them. Same never-raise contract: retries 429 / 5xx via tenacity; exhausted returns []; non-retryable 4xx returns []; malformed article skipped.
  - `backend/pyproject.toml` — registered the `integration` pytest marker and extended `addopts` to `"not free_tier_live and not integration"` so both live-provider suites stay opt-in by default.
  - `backend/tests/pipelines/sources/test_gdelt.py` — 6 hermetic + 1 opt-in live probe (`@pytest.mark.integration`). Hermetic tests cover: article mapping + query params + startdatetime encoding; since-filter drops older items; 429 retried then succeeds; exhausted retries returns []; malformed seendate skipped not fatal; the class semaphore actually serializes concurrent calls (measured peak concurrency == 1 across two parallel fetches).
- **Acceptance verified locally:**
  - `python -m pytest tests -q` → **92 passed, 2 deselected**.
  - `ruff check .` clean.
- **Files touched:** created `backend/app/pipelines/sources/gdelt.py`, `backend/tests/pipelines/sources/test_gdelt.py`. Modified `backend/pyproject.toml` (marker + addopts), `BUILD.md` (tick), `HANDOFF.md` (this file).
- **Migrations added:** none.
- **Tests added:** 7 (6 hermetic + 1 live).
- **In-flight work:** none.
- **Deviations from BUILD.md:** none. GDELT's odd `YYYYMMDDTHHMMSSZ` `seendate` format required a manual `strptime`; that's an implementation detail, not a spec change. `hints["domain"]` is a small extra beyond BUILD.md's ING-04 text — using the `hints` extensibility slot from ING-03 to carry GDELT's `domain` field so downstream authority scoring (later module) has the publisher name without re-parsing raw_payload.

---

## Environment state

- Backend: four adapters (Base + NewsAPI + Marketaux + GDELT). Two pytest markers gate live-provider tests. `NewsAPISource`, `MarketauxSource`, `GDELTSource` all follow the same never-raise contract.
- Frontend: unchanged.
- Database: unchanged.
- Vectors: unchanged (none).
- Tests: **92 hermetic, 2 opt-in.**
- CI: green on ING-03 push.
- Docs: unchanged.

---

## Open questions / blockers

- **ING-05 introduces a data file — `ticker_to_cik.json` mapping the top 3000 US tickers to their SEC CIK numbers.** Two clean paths:
  1. Bundle a static JSON at implementation time (needs a one-time download from SEC's [company_tickers.json](https://www.sec.gov/files/company_tickers.json) API, hand-verified).
  2. Fetch it lazily at adapter startup and cache in memory.
  Recommend (1) for MVP determinism — the CIK set changes rarely. The file lives in `backend/app/pipelines/sources/data/ticker_to_cik.json` (or similar) and is committed. The next session's implementer should choose.

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
