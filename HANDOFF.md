# Handoff — Lumen Intelligence Agent

**Branch:** `v2/intelligence-agent`
**Base:** `refactor` (at commit `af39bef` — latest from origin/refactor)
**Last updated:** 2026-07-03 (session 17 — ING-05 EDGAR adapter)
**Progress:** 19/60 modules complete (HP-01, HP-02, BOOT-01..BOOT-08, DATA-01, DATA-02, DATA-03, DATA-05, ING-01..ING-05).

DATA-04 postponed (needs ING-07).

---

## Next module

**ID:** `ING-06`
**Title:** RSS adapter
**Depends on:** ING-01
**Read:** `BUILD.md` → the `ING-06` block. Uses `feedparser` (already in requirements.txt). `RSS_FEEDS` env var is a comma-separated list; the adapter deduplicates by URL hash before yielding.

**Branch state:** BOOT-01..BOOT-08 + DATA-01/02/03/05 + ING-01..ING-05 stacked on `856d503`. Five adapters live: `BaseSource` (abstract), `NewsAPISource`, `MarketauxSource`, `GDELTSource`, `EDGARSource`.

Before starting, verify:
- `git branch --show-current` shows `v2/intelligence-agent`.
- `git log --oneline -19` shows ING-05..HP-01 on top of `856d503` / `f7e479a`.
- `git status` is clean.
- `cd backend && python -m pytest tests -q` reports **97 passed, 3 deselected**.
- `ruff check .` clean.

---

## Last session

- **Session goal:** Execute ING-05 — SEC EDGAR adapter. For each requested ticker: resolve CIK → fetch `submissions/CIK<10-digit>.json` → emit one `NewsItemIn` per 8-K / 10-K / 10-Q with parsed body from the primary document.
- **Completed:**
  - `ING-05` ✅ — EDGAR adapter.
  - `backend/app/pipelines/sources/data/__init__.py` (empty package marker).
  - `backend/app/pipelines/sources/data/ticker_to_cik.json` — 74 well-known US tickers → CIKs. Curated for MVP: FAANG + top financials + healthcare + industrials + a few high-growth SaaS/fintechs (DDOG, SNOW, PLTR, etc.). BUILD.md's stated target of "top 3000 US tickers" is a follow-up expansion; the file layout and lookup pattern are what matters at this module boundary.
  - `backend/pyproject.toml` — added `[tool.setuptools.package-data]` entry so the JSON ships with the built package.
  - `backend/app/pipelines/sources/edgar.py` — `EDGARSource(BaseSource)`. Loads `ticker_to_cik.json` at class-load time. Per-ticker flow: resolve CIK → GET `https://data.sec.gov/submissions/CIK<10-digit>.json` → filter `filings.recent` arrays by form (`8-K`/`10-K`/`10-Q`) and filingDate ≥ since → for each, GET the primary document at `Archives/edgar/data/<cik_int>/<accession_no_dashes>/<primary_doc>`, parse with `selectolax`, keep first 4000 chars of extracted text. Title = `"<ticker> filed <form> on <date>"`. source_id = accession. hints = `{"tickers": [ticker], "form": form, "cik": cik}`. Requires `User-Agent: Config.EDGAR_USER_AGENT` per SEC fair-use — attached at httpx client construction. Same never-raise contract: unknown ticker skipped (no HTTP hit), submissions 5xx retried then ticker skipped, body fetch failure leaves body=None but the item is still emitted, non-retryable 4xx returns empty for that ticker.
  - `backend/tests/pipelines/sources/test_edgar.py` — 5 hermetic + 1 opt-in live probe. Hermetic: full AAPL flow with 3 filings (10-K + 8-K + 10-Q; S-4 filtered out) and parsed bodies; unknown ticker skipped without HTTP; since-filter drops older filings (Jan-1-2026 keeps only the 10-K); body fetch 500 leaves body=None but item still emits; submissions 500 exhausts retries and skips the ticker without raising.
- **Acceptance verified locally:**
  - `python -m pytest tests -q` → **97 passed, 3 deselected** (the 3 deselected are the two live probes across GDELT + EDGAR + the LLM live probe).
  - `ruff check .` clean.
  - selectolax installed locally to support the body parser.
- **Files touched:** created `backend/app/pipelines/sources/edgar.py`, `backend/app/pipelines/sources/data/__init__.py`, `backend/app/pipelines/sources/data/ticker_to_cik.json`, `backend/tests/pipelines/sources/test_edgar.py`. Modified `backend/pyproject.toml` (package-data), `BUILD.md` (tick), `HANDOFF.md` (this file).
- **Migrations added:** none.
- **Tests added:** 6 (5 hermetic + 1 live).
- **In-flight work:** none.
- **Deviations from BUILD.md:**
  - **`ticker_to_cik.json` contains 74 tickers, not the "top 3000".** MVP-sufficient: the demo portfolio (AAPL, MSFT, NVDA, GOOGL, VOO, BND) is covered; broader coverage lands as a follow-up "seed CIK map" module or a one-off script that pulls SEC's `company_tickers.json` and re-writes the file. The lookup + adapter code is production-shaped — only the data file scope is narrower.
  - **hints populated with `{"tickers": [ticker], "form": form, "cik": cik}`.** Beyond BUILD.md's ING-05 text; using the `hints` extensibility slot established in ING-03. Downstream authority scoring + cluster tagging can use these hints without re-parsing raw_payload.

---

## Environment state

- Backend: five source adapters live. `EDGARSource` needs an input list of tickers (from ING-10's orchestrator, which will query the union of user portfolios).
- Frontend: unchanged.
- Database: unchanged.
- Vectors: unchanged (none).
- Tests: **97 hermetic, 3 opt-in.**
- CI: green on ING-03. ING-04 will trigger a rerun; ING-05 will too — verified locally.
- Docs: unchanged.

---

## Open questions / blockers

- **`selectolax==0.3.24`** is already pinned in `requirements.txt` (from BOOT-02) — CI will install it fresh.
- **`ticker_to_cik.json`** should get a follow-up expansion. Suggest a new module `ING-05a` or "seed data" module to pull `https://www.sec.gov/files/company_tickers.json` and rewrite the bundled file.

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
