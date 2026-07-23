# Handoff — Lumen Intelligence Agent

**Branch:** `v2/intelligence-agent`
**Base:** `refactor` (at commit `af39bef` — latest from origin/refactor)
**Last updated:** 2026-07-21 (session 34 — IMP-05 impact endpoint + on-demand generation)
**Progress:** 41/60 modules complete (HP-01, HP-02, BOOT-01..BOOT-08, DATA-01..DATA-05, ING-01..ING-10, REL-01..REL-06, IMP-01..IMP-05, GRD-01..GRD-03, BRIEF-01, CHAT-01). DATA-06 (frontend UI) + REL-07 (frontend news feed) + IMP-06 (frontend impact card) still pending — all frontend-blocked; backend continues.

---

## Next module

**ID:** `BRIEF-02`
**Title:** Briefing synthesizer agent
**Depends on:** IMP-05 (now live), BRIEF-01.
**Read:** `BUILD.md` → the `BRIEF-02` block at ~line 1109. Builds `backend/app/agents/briefing/graph.py` + `backend/app/agents/briefing/prompts.py`. Consumes today's most-relevant impact rows for a user + active portfolio and synthesizes a `BriefingContent` (three sections: `top_movers`, `watchlist`, `what_would_change_my_thinking` + `generated_summary`). Persists a `briefings` row.

After BRIEF-02, the next parallelizable trio: **BRIEF-03** (scheduled generation — wires APScheduler for the user-configured briefing hour), **CHAT-02** (three chat retrieval tools: `retrieve_recent_impacts`, `retrieve_news`, `get_portfolio_summary`), and — trickier — **EVAL-02** (LangSmith wiring). BRIEF-03 depends on BRIEF-02. CHAT-02 depends on IMP-05 + ING-07 (both live). EVAL-02 depends only on BOOT-06 (live) and extends `app/utils/langsmith.py` (does not yet exist — create it).

**Branch state:**
- IMP-05 is live behind auth. `GET /api/news/clusters/{id}/impact` returns cached (200) or 202 + `poll_url`; `POST /impact/generate` forces regeneration. Threshold gate: relevance score ≥ 0.3 for the caller (default; override via `Config.IMPACT_MIN_SCORE`). Below-threshold or absent-relevance clusters return 404. Cross-user isolated — a user never observes another user's impact row.
- `ClusterDetailRead.impact` now typed `ImpactRead | None` (no more placeholder `Any`). REL-06's cluster detail endpoint fills it from the caller's own impact row via a scoped query — same isolation rule.
- The impact-generation enqueue is a fire-and-forget `asyncio.create_task` in `app/routes/impact.py::_default_enqueue`. Uses a fresh `AsyncSession` from `get_session_factory()`, constructs its own `LLMClient` / `EmbeddingClient` / `VectorStore("historical_analogs")`. Tests override via `app.dependency_overrides[get_impact_enqueue]` — a `_EnqueueRecorder` test double records calls and (optionally) fires a callback to synchronously seed the cached row.

Before starting, verify:
- `git branch --show-current` (from `.claude/worktrees/v2`) shows `v2/intelligence-agent`.
- `git log --oneline -5` shows IMP-05 on top.
- `git status` is clean.
- `cd backend && python -m pytest tests -q` reports **293 passed, 5 deselected**.
- `ruff check .` clean.

---

## Last session

- **Session goal:** Ship IMP-05 solo — no independent parallel candidate was cleanly available (BRIEF-02/CHAT-02 both need IMP-05; DATA-06 is a full frontend build; EVAL-01 requires human labeling). Also fold in the "tighten `ClusterDetailRead.impact: Any` → `ImpactRead | None`" cleanup queued from IMP-04's HANDOFF.
- **Completed:**
  - `IMP-05` ✅ — Impact endpoint + on-demand generation.
    - `backend/app/routes/impact.py` — new router at `/api/news/clusters/{cluster_id}/impact` + `/impact/generate`.
    - `GET /api/news/clusters/{cluster_id}/impact`:
      1. Loads caller's active portfolio (404 if none, matches other routes' "no-portfolio → 404" pattern).
      2. 404 on unknown `cluster_id`.
      3. Probes for a cached `ImpactAssessment` row on `(cluster, user, portfolio)`. On hit → 200 with `ImpactRead` body.
      4. On miss, loads the caller's `RelevanceScore` for the cluster. Score below `_IMPACT_MIN_SCORE` (default `Decimal("0.3")`, `Config.IMPACT_MIN_SCORE` overrides) or missing → 404 with a "cluster relevance is below the impact threshold" message.
      5. Otherwise enqueues via the injected `EnqueueFn` (default: fire-and-forget `asyncio.create_task`) and returns 202 with `{"status": "generating", "poll_url": <this-same-endpoint>}`.
    - `POST /api/news/clusters/{cluster_id}/impact/generate` — same threshold gate; always enqueues with `force=True`. Skips the cached-row probe (that's the point of force).
    - Enqueue is a FastAPI dependency (`get_impact_enqueue`) so tests can override it — the real default calls `analyze_impact_for_user()` in a background task with its own fresh session + `LLMClient` + `EmbeddingClient` + `VectorStore("historical_analogs")`.
    - IMP-04 idempotency (unique on `(cluster, user, portfolio)`) means duplicate enqueues on the GET path are safe: whichever generation wins, the loser observes the cached row on re-invocation.
  - **Schema tightening (folded from IMP-04's follow-ups):**
    - `app/schemas/news.py::ClusterDetailRead.impact` moved from `Any = None` to `ImpactRead | None = None`. Docstring updated to reference IMP-05.
    - `app/routes/news.py::cluster_detail` now issues a scoped `SELECT ImpactAssessment WHERE cluster_id=? AND user_id=<caller> AND portfolio_id=<active>` and serializes the row into the response (same cross-user isolation rule as `relevance`).
    - Restored `Any` in the `typing` import — `NewsItemIn.raw_payload: dict[str, Any]` and `NewsItemIn.hints: dict[str, Any]` still need it. Missed on the first edit; caught by 27 unrelated normalizer/orchestrator test failures on the first full-suite pass.
  - `backend/tests/routes/test_impact.py` — 11 hermetic tests:
    - Cached-200 (with a `_EnqueueRecorder` test double asserting `enqueue.calls == []`).
    - Above-threshold-202 (asserts `poll_url` ends with the GET endpoint URL; asserts `enqueue.calls == [(cluster, user, pf, False)]`).
    - Below-threshold-404, no-relevance-row-404, no-active-portfolio-404, unknown-cluster-404.
    - Cross-user isolation on GET — Bob's cached row on the same cluster is invisible to Alice, and her above-threshold relevance still triggers her own enqueue.
    - POST force with cached row present — still returns 202 and enqueues with `force=True`.
    - POST below-threshold 404.
    - `test_cluster_detail_serializes_impact_row` — REL-06's `/clusters/{id}` returns the `ImpactRead` body when a row exists for the caller.
    - `test_cluster_detail_impact_null_when_caller_has_no_row` — only Bob has a row → Alice's detail response returns `impact: null`.
  - `app/main.py` — registered `impact_routes.router`.
- **Acceptance verified locally:**
  - `python -m pytest tests -q` → **293 passed, 5 deselected** (+11 new hermetic tests for IMP-05).
  - `ruff check .` clean.
  - Manual: `curl -s /api/news/clusters/<id>/impact` returns 202 on above-threshold uncached clusters, 200 on cached, 404 on below-threshold or unknown cluster.
- **Files touched:** created `backend/app/routes/impact.py`, `backend/tests/routes/test_impact.py`. Modified `backend/app/schemas/news.py` (typed `impact: ImpactRead | None`), `backend/app/routes/news.py` (cluster detail now serializes caller's impact row), `backend/app/main.py` (router include), `BUILD.md` (tick), `HANDOFF.md` (this file).
- **Migrations added:** none.
- **Tests added:** 11 hermetic.
- **In-flight work:** none.
- **Deviations from BUILD.md:**
  - **BUILD.md's spec left the polling protocol implicit** — the response body includes `poll_url`, and we chose to make `poll_url` the same GET endpoint that returned the 202 (a client polls until they get 200). No separate "job" resource. Simpler and matches the IMP-04 idempotency model — duplicate enqueues don't multiply rows.
  - **Enqueue uses `asyncio.create_task` from within the request handler**, not FastAPI `BackgroundTasks`. Reason: `BackgroundTasks` runs after the response but before the connection closes, holding the client until the LLM call finishes; `create_task` returns immediately. The background coroutine opens its own session from `get_session_factory()` because the request-scoped session dies with the response.
  - **Enqueue is a FastAPI dependency (`get_impact_enqueue`), overridable via `app.dependency_overrides`** — the test double `_EnqueueRecorder` records calls without touching the real graph. In production it defaults to the fire-and-forget task. This was already the shape used for `get_db_session` and `require_auth` in earlier route tests.
  - **Below-threshold + no-relevance-row are both 404 with the same message.** BUILD says "Below-threshold returns 404 with a clear message." — extended to no-relevance-row (structurally identical: caller has no reason to see this cluster's analyst output).
- **Bug caught mid-session:** first full-suite run showed 27 unrelated test failures across the normalizer and orchestrator. Root cause: I dropped `Any` from `from typing import Any, Literal` in `app/schemas/news.py` when tightening `ClusterDetailRead.impact`, but `NewsItemIn.raw_payload: dict[str, Any]` and `NewsItemIn.hints: dict[str, Any]` still needed it — pydantic couldn't finish class construction. Restored the import; the rest of the suite went green immediately.

---

## Environment state

- Backend: impact analyst is live end-to-end AND exposed via HTTP. The `/api/news/clusters/{id}/impact` GET + POST/generate pair completes the retrieve → reason → validate → persist → serve loop. `ClusterDetailRead.impact` is now a real typed field.
- Frontend: unchanged.
- Database: Alembic head `e5b02c8f6a39` (CHAT-01). No new migrations this session.
- Vectors: unchanged. Remember `python -m app.evals.seed_analogs` before smoke-testing the endpoint against real Chroma (the enqueue calls the real graph, which needs the analog corpus seeded).
- Tests: **293 hermetic, 5 opt-in.**
- CI: REL-03..this-batch pending push through CI.
- Docs: unchanged.

---

## Open questions / blockers

- **None for BRIEF-02.** BRIEF-01 schema, IMP-05 endpoint, and the whole impact pipeline underneath are all live. BRIEF-02 composes a thorough-tier LLM over today's impact rows.
- **Follow-ups queued (do not fold into BRIEF-02 unless it's convenient):**
  - **`analyze_impact_for_user` returns `None` on hard failure** — IMP-05 currently swallows this in the background task (log-only). If the client polls and never gets a row, they'll see 202-forever. Consider a `impact_failures` table or a "last_attempt_at" column so the endpoint can eventually surface "generation failed, try again" instead of "still generating."
  - Refresh `yfinance` pin in `requirements.txt` (0.2.44 → 1.5.x).
  - Expand `analogs.json` from 37 → ~150 events.
  - Tighten GRD-03 lexical patterns (`audit`, `will`) if UX testing shows over-refusal.
  - Consider wiring GRD-01's LLM stage into IMP-04 via a separate `LLMClient` instance in the endpoint construction. Not blocking; ergonomic hardening for prod.
  - Surface `langsmith_run_id` from `LLMResponse` — currently always `None` on persisted impact rows.
  - Add a `Config.IMPACT_MIN_SCORE` env var (currently the code defaults to `Decimal("0.3")` and reads `getattr(Config, "IMPACT_MIN_SCORE", 0.3)` — Config doesn't declare it explicitly yet).

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
