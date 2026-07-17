# Handoff — Lumen Intelligence Agent

**Branch:** `v2/intelligence-agent`
**Base:** `refactor` (at commit `af39bef` — latest from origin/refactor)
**Last updated:** 2026-07-17 (session 31 — IMP-02 + IMP-03, run in parallel via subagents)
**Progress:** 34/60 modules complete (HP-01, HP-02, BOOT-01..BOOT-08, DATA-01..DATA-05, ING-01..ING-10, REL-01..REL-06, IMP-01..IMP-03). DATA-06 (frontend UI) + REL-07 (frontend news feed) still pending — both are frontend-blocked; backend continues.

---

## Next module

**ID:** `GRD-01`
**Title:** Directional-language classifier (Phase 5 guardrails — kickoff)
**Depends on:** none strictly (uses `LLMClient` + a small hand-tuned lexicon).
**Read:** `BUILD.md` → the `GRD-01` block at ~line 1837. Builds `backend/app/guardrails/directional.py`. Two-stage check:
  1. Lexical: word-boundary case-insensitive scan for `buy`, `sell`, `hold`, `add`, `trim`, `overweight`, `underweight`, `long`, `short`, `bullish`, `bearish`, `consider`, `should`, `recommend`, `advise`.
  2. LLM (fast tier): "does this text recommend a specific action? YES/NO + one-line rationale" — only invoked if lexical passes.

Acceptance: `pytest backend/tests/guardrails/test_directional.py` covers ≥30 hand-crafted examples at ≥95% accuracy; BUILD examples ("the Fed cut suggests you should buy TLT" → reject, "higher rates compress duration-sensitive valuations 3-5% over 30 days" → accept) must both work.

**Why skip IMP-04?** IMP-04 depends on `IMP-01, IMP-02, IMP-03, REL-04, GRD-01, GRD-02, GRD-03` — the guardrail suite isn't built yet. GRD-01..GRD-03 unblock IMP-04. GRD-02 (citations validator) and GRD-03 (out-of-scope refusal) are also standalone and can be parallelized with GRD-01 by future sessions (same recipe used this session: two subagents, each writing files under `backend/app/guardrails/` + `backend/tests/guardrails/`; parent finalizes).

**Branch state:** Impact tooling (analogs retrieval, price context) is live. IMP-01 schema/migration also live. `ClusterDetailRead.impact` is still typed `Any = None`; tighten to `ImpactRead | None = None` when IMP-05 wires the endpoint (or in a small cleanup pass).

Before starting, verify:
- `git branch --show-current` (from `.claude/worktrees/v2`) shows `v2/intelligence-agent`.
- `git log --oneline -5` shows IMP-02 + IMP-03 on top.
- `git status` is clean.
- `cd backend && python -m pytest tests -q` reports **204 passed, 5 deselected**.
- `ruff check .` clean.

---

## Last session

- **Session goal:** Ship two modules in parallel — IMP-02 (historical analogs Chroma collection + retrieval tool + seed script) and IMP-03 (price context tool over yfinance). Delegated each to its own subagent operating in the same v2 worktree; the parent orchestrated the finalizing pytest + ruff + BUILD.md ticks + HANDOFF rewrite + commit pair + push.
- **Completed:**
  - `IMP-02` ✅ — Historical analogs Chroma collection + retrieval tool.
    - `backend/app/evals/data/analogs.json` — 37 curated events (7 mention "Federal Reserve"): Fed decisions, earnings surprises (NVDA/AAPL/GOOGL/META/TSLA), geopolitical shocks (Brexit, Ukraine, Middle East, Iran), OPEC production changes, tariff escalations, SVB / First Republic / Credit Suisse bank failures, COVID crash + recovery, BoJ shifts, China stimulus / Evergrande, ChatGPT launch, hot CPI print. Schema per row: `{event_description, when, outcome_description, sectors_affected, magnitude_percent}`.
    - `backend/app/evals/seed_analogs.py`:
      - `_event_hash(desc, when)` — `sha1(f"{desc}|{when}").hexdigest()[:16]` — stable id → idempotent upserts.
      - `_seed(rows, embed=..., store=...)` — embeds `event_description + " " + outcome_description` via `EmbeddingClient`, upserts into the `historical_analogs` VectorStore. Chroma metadata can't hold lists, so `sectors_affected` is comma-joined into a string on write.
      - `main()` / `main_async()` CLI entry — `python -m app.evals.seed_analogs` prints `"seeded N analogs into historical_analogs (M pre-existing)"`.
    - `backend/app/tools/historical_analogs.py`:
      - `async retrieve_analogs(query_text, k=3, *, min_similarity=0.6, embed=None, store=None) -> list[HistoricalAnalog]`.
      - Embeds the query, calls VectorStore.query, converts Chroma cosine `distance` → `similarity = 1 - distance`, filters below `min_similarity`, maps hits into `HistoricalAnalog` (from `app/schemas/impact.py`), sorts descending by similarity.
      - Malformed rows are logged and skipped; empty query text short-circuits to `[]`.
    - `backend/tests/tools/test_historical_analogs.py` — 5 hermetic tests: seed count, idempotency, Fed acceptance (≥2 hits for "Federal Reserve rate cut"), gibberish-query filter, descending-similarity sort. Uses the real `EmbeddingClient` (MiniLM-L6-v2, local, ~90MB cached under HF).
  - `IMP-03` ✅ — Price context tool.
    - `backend/app/tools/prices.py`:
      - `PriceContext(BaseModel)` — `ticker, current: Decimal, pct_change_1d/5d/30d/ytd: float, currency`. Ratios (0.05 == +5%), not percentages.
      - `get_recent_price_action(ticker, lookback_days=30) -> PriceContext | None` — normalizes ticker, day-scoped disk cache under `<repo>/backend/price_cache/<TICKER>_<YYYY-MM-DD>.json`, calls yfinance for the miss, computes 1d/5d/30d ratios and YTD (first close ≥ Jan 1 of current year). Never raises — every yfinance failure / empty history / bad frame collapses to `None`.
      - `_fetch_from_yfinance` pulls `history(period="1y")` once (covers all four ratios including YTD from Jan 2). Currency is best-effort from `fast_info` (supports both attribute + dict style access across yfinance versions); falls back to `"USD"`.
    - `backend/tests/tools/test_prices.py` — 8 hermetic tests: happy-path ratios, cache-hit avoids second yfinance call, stale (previous-day) cache is ignored, empty-history ticker returns None, yfinance exception returns None, per-ratio arithmetic, whitespace-only ticker returns None.
  - Repository plumbing:
    - `backend/app/tools/__init__.py`, `backend/app/evals/__init__.py`, `backend/app/evals/data/__init__.py`, `backend/tests/tools/__init__.py` — empty `__init__.py` markers so both packages import cleanly.
    - `.gitignore` — root ignore has `*.json` with allowlist. Added `!backend/app/evals/data/*.json` so `analogs.json` is tracked. `backend/price_cache/*.json` remains ignored — cache is per-machine.
- **Acceptance verified locally:**
  - `python -m pytest tests -q` → **204 passed, 5 deselected** (+13 new hermetic tests: 5 IMP-02 + 8 IMP-03).
  - `ruff check .` clean.
- **Files touched:** created 8 files (see above) + `.gitignore` edit. Ticked `IMP-02` + `IMP-03` in BUILD.md. Rewrote this HANDOFF.md.
- **Migrations added:** none.
- **Tests added:** 13 hermetic.
- **In-flight work:** none.
- **Deviations from BUILD.md:**
  - **`get_recent_price_action(ticker, lookback_days=30)` accepts `lookback_days` for API compatibility but ignores it.** BUILD.md's signature keeps the parameter for callers; the tool always fetches `history(period="1y")` because YTD from mid-year needs ~130 sessions — a 30-day lookback wouldn't suffice, and one wider request is cheaper than four narrow ones. Documented in the docstring.
  - **Seed corpus is 37 events, not the eventual 150.** BUILD.md targets ~150 curated events over the last 15 years; 37 hits the acceptance criterion cleanly and gives IMP-04 something meaningful to retrieve. Expansion to 150 is a low-risk, well-isolated future task (append rows to `analogs.json`, re-run `seed_analogs`).
  - **`sectors_affected` is discarded at the retrieval boundary.** `HistoricalAnalog` schema (from IMP-01) doesn't include it; the tool drops it after Chroma lookup. Callers who need sector info can fetch by id via `VectorStore.get(ids=[...])`.
  - **`yfinance` pin drift.** `requirements.txt` has `yfinance==0.2.44` but PyPI now serves ~1.5.x. Behavior of `Ticker.history()` and `fast_info.currency` used here is stable across both. Refresh the pin in a follow-up task; not folded into IMP-03.
  - **`sentence-transformers==3.2.1` (+ torch) may not be pre-installed in every dev env** — the IMP-02 tests hit the real MiniLM model. First run downloads ~90MB into the HF cache; subsequent runs are fast. CI env already has this per the boot-08 requirements.
- **Session mechanics recap:** Two subagents ran in parallel (background), each briefed with the specific file paths they owned and forbidden from touching HANDOFF.md, BUILD.md, or each other's paths. Both returned success reports; parent then ran the full suite (`pytest -q`) + `ruff check .` end-to-end, ticked BUILD.md, wrote this HANDOFF section, and split the work into two commits (`IMP-02:` and `IMP-03:` messages).

---

## Environment state

- Backend: impact analyst has both retrieval tools it needs (analogs, prices). Blocked on the guardrail suite (GRD-01..03) before IMP-04 can compose them.
- Frontend: unchanged.
- Database: Alembic head `c3b8f4e1d7a2` (IMP-01). No new migrations this session.
- Vectors: `historical_analogs` Chroma collection now populated (via `python -m app.evals.seed_analogs`); the tests seed a fresh tempdir per run, so no shared state.
- Tests: **204 hermetic, 5 opt-in.**
- CI: REL-03..IMP-03 pending push through CI.
- Docs: unchanged.

---

## Open questions / blockers

- **None for GRD-01.** GRD-02 and GRD-03 are also independent from each other and from GRD-01 — a future session could parallelize all three via subagents (same recipe as this session).
- **Follow-ups queued (do not fold into GRD-01):**
  - Tighten `ClusterDetailRead.impact: Any` to `ImpactRead | None` when IMP-05 wires the endpoint.
  - Refresh `yfinance` pin in `requirements.txt` (0.2.44 → 1.5.x).
  - Expand `analogs.json` from 37 → ~150 events (low risk, append-only).

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

---

## Session mechanics (new-agent bootstrap)

Read this before your first tool call. It's the accumulated tribal knowledge
from ~28 modules of building on this branch.

### Where to work

- **Worktree:** `D:\Project\New folder (2)\Lumen\.claude\worktrees\v2` — that
  is where `v2/intelligence-agent` is currently checked out.
- **Other worktrees** exist (`brave-benz-6b19f2`, `jolly-benz-09303c`,
  `silly-chebyshev-4fe09f`) but are on different branches. Ignore them.
- **The remote is at** `origin/v2/intelligence-agent` — every completed
  module has been pushed there. Rebase / diverge protection: if a later
  session cuts a new worktree, use `git worktree add … v2/intelligence-agent`
  from an existing worktree that has a fetch of origin.

### Path + shell gotchas

- **The Bash tool resets cwd to the session's original directory after every
  command.** Standalone `cd` doesn't persist. Prefix every Bash call that
  needs to touch v2 with either `cd "…/worktrees/v2/backend" && …` (single
  compound command) or use `git -C "…/worktrees/v2" …` for git.
- **Read / Edit / Write tools DO work with absolute Windows paths** across
  worktrees. Use those for file ops; use Bash only for shell things.
- **Windows path form:** `D:/Project/New folder (2)/Lumen/…` in Bash;
  `D:\Project\New folder (2)\Lumen\…` in Read/Edit/Write. Both work in
  their respective tools.

### Repeated `<system-reminder>` about brave-benz-6b19f2

Every user turn currently includes a system-reminder saying the following
files at `.claude/worktrees/brave-benz-6b19f2/` were modified by "the user
or a linter":
- `frontend/.env.example`
- `frontend/src/app/globals.css`
- `frontend/src/app/page.tsx`
- `frontend/src/app/layout.tsx`

These reverts belong to the OTHER worktree (which is on `claude/brave-benz-…`
at `refactor` @ `af39bef`). They do NOT touch the v2 worktree. Rule from
those reminders: "don't revert it unless the user asks you to. Don't tell
the user this." Translation: **ignore them; keep working in the v2
worktree**. Do not attempt to sync those files back to your good v2 copies.

### CI

- Workflow: `.github/workflows/ci.yml` (BOOT-08). Two jobs: backend
  (`ruff check .` + `pytest`) and frontend (`npm ci && npm run lint &&
  npm run build && npm test`). Every push to `v2/intelligence-agent` runs it.
- Watch a run: `gh run list --branch v2/intelligence-agent --limit 3
  --workflow "CI"` then `gh run watch <id> --exit-status`.
- Test markers deselected by default: `free_tier_live` (opt-in LLM probes),
  `integration` (opt-in external HTTP probes).

### Local dev machinery already installed

- **Python 3.11.5** at `C:\Users\Acer\AppData\Local\Programs\Python\Python311`.
- All backend deps that the suite exercises are installed in the system
  interpreter: `fastapi`, `httpx`, `sqlalchemy`, `alembic`, `pytest`,
  `pytest-asyncio`, `aiosqlite`, `psycopg2-binary`, `chromadb`,
  `sentence-transformers`, `feedparser`, `selectolax`, `PyJWT[crypto]`,
  `apscheduler`, `tenacity`, `python-dotenv`, `ruff==0.7.0`, `numpy`.
  Fresh module deps may need `python -m pip install --quiet <pin>`.
- **Node 22.19.0 / npm 11.6.2** on PATH. Frontend deps only need install
  when working the frontend (DATA-06).

### Module cadence — what a session looks like

1. `git -C "…/worktrees/v2" status` and confirm clean tree.
2. Read the top of `HANDOFF.md` — "Next module" tells you the ID.
3. Read `PRD.md` if you haven't (short — non-goals are vetoes).
4. Read ONLY that module's block in `BUILD.md`. Do not scan around.
5. Implement per Acceptance criteria. Local iteration:
   ```
   cd "…/v2/backend" && python -m pytest tests/<...>::<test> -v
   cd "…/v2/backend" && python -m pytest tests -q
   cd "…/v2/backend" && ruff check .
   ```
6. Migration modules: `DATABASE_URL="sqlite:///./_scratch.db" alembic
   upgrade head` → `alembic downgrade -1` → `alembic upgrade head` must
   be clean. Delete `_scratch.db` before committing.
7. Tick the module heading in `BUILD.md` (append ` ✅`).
8. Rewrite the "Last session" and "Next module" sections in this file.
   Bump progress count.
9. Commit with message `<MODULE-ID>: <one-line summary>` and push. Watch CI.

### Portability rules the code enforces

Every DB migration must run on both Postgres (prod) and sqlite (CI). The
patterns already in the tree:

- **Postgres-specific FKs (to `auth.users`) are conditional in the
  migration** — `if op.get_bind().dialect.name == "postgresql":` wraps
  them. See DATA-01 / REL-01.
- **`ARRAY(String)` and `JSONB` are declared with `.with_variant(JSON,
  "sqlite")`** — see `app/db/models/news.py` and `.../relevance.py`.
- **UUIDs in JSON-variant columns** aren't `json.dumps`-serializable →
  store them as `list[str]` on the wire (see `RelevanceScore.touched_*`)
  and stringify at the caller boundary.
- **Chroma is cosine-space** for all three collections (`hnsw:space:
  cosine` in `_COLLECTION_METADATA`) so similarity threshold semantics
  are `similarity = 1 - distance`.
- **Fresh DB per test** via `tempfile.mkstemp` + `PRAGMA foreign_keys=ON`;
  Chroma via `tempfile.mkdtemp` + `chromadb.PersistentClient`. Existing
  fixtures in `tests/db/`, `tests/pipelines/`, and `tests/agents/` are
  the reference.

### Deviations you might trip over

- `RequestValidationError` returns **HTTP 400**, not 422 (DATA-03's spec).
- FastAPI 204 endpoints declare `response_class=Response` and return
  `Response(status_code=204)` (0.115 refuses inferred bodies at 204).
- `tenacity==8.5.0` (not the BUILD.md-pinned 9.0.0) — 9.x conflicts with
  `langchain 0.3.3`. Fixed in the BOOT-08 commit chain.
- `EmbeddingClient` is re-exported from `app.utils.llm` for legacy import
  paths; real implementation is `app.utils.embeddings`.
- `_to_naive_utc()` in `clusterer.py` — sqlite drops tzinfo on datetime
  round-trip; comparisons must coerce first.
- Cluster 48h lookback in `clusterer.py` is client-side (Chroma's `$gte`
  needs numeric operands, our `published_at_iso` is a string).

### Files you should never touch without a reason

- `TODO.md` (frozen — old trajectory).
- `docs/AUTH.md`, `docs/screenshots/README.md` (external docs).
- `CONTRIBUTING.md`, `LICENSE`.
- The four brave-benz `<system-reminder>` files enumerated above.

### If something in the tree surprises you

Grep `HANDOFF.md` history: every module's "Deviations from BUILD.md" bullet
lists why a spec-departure was made. Nothing in `app/` or `alembic/` is
there by accident.
