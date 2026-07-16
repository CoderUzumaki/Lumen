# Handoff — Lumen Intelligence Agent

**Branch:** `v2/intelligence-agent`
**Base:** `refactor` (at commit `af39bef` — latest from origin/refactor)
**Last updated:** 2026-07-17 (session 28 — REL-05 relevance fan-out)
**Progress:** 30/60 modules complete (HP-01, HP-02, BOOT-01..BOOT-08, DATA-01..DATA-05, ING-01..ING-10, REL-01..REL-05). DATA-06 (frontend UI) still pending.

---

## Next module

**ID:** `REL-06`
**Title:** News endpoints
**Depends on:** REL-01, DATA-03
**Read:** `BUILD.md` → the `REL-06` block. Builds `backend/app/routes/news.py` with two endpoints:
- `GET /api/news/relevant?limit=20&since=YYYY-MM-DDTHH:MM` → `[{cluster: NewsClusterRead, relevance: RelevanceRead}]` for the caller's active portfolio, ordered by score DESC, published_at DESC.
- `GET /api/news/clusters/{cluster_id}` → `{cluster, relevance | null, impact | null}` (impact is still `null` until IMP-* modules ship).

Acceptance: `/api/news/relevant` must return in < 300ms with 10k clusters and 200 relevance rows for the user; cross-user isolation — a user must never see another user's rows.

**Branch state:** relevance_scores are being populated end-to-end by the scheduler (ING-10 → REL-05 → REL-04 → REL-03/REL-02). Read schemas (`NewsClusterRead`, `RelevanceRead`) probably don't exist yet in `app/schemas/` — check before adding; if absent, add them alongside the routes rather than as a separate module.

Before starting, verify:
- `git branch --show-current` (from `.claude/worktrees/v2`) shows `v2/intelligence-agent`.
- `git log --oneline -5` shows REL-05 on top.
- `git status` is clean.
- `cd backend && python -m pytest tests -q` reports **170 passed, 5 deselected**.
- `ruff check .` clean.

---

## Last session

- **Session goal:** Execute REL-05 — the fan-out worker that scores every newly-created/updated cluster against every active portfolio after each ingest cycle.
- **Completed:**
  - `REL-05` ✅ — Fan-out worker.
  - `backend/app/pipelines/relevance_fanout.py`:
    - `FanoutSummary` dataclass — `tasks`, `cache_hits`, `prefilter_short_circuits`, `classifier_calls`, `errors`, `elapsed_seconds`, `cluster_ids`.
    - `_discover_cluster_ids(session, since)` — `SELECT NewsCluster.id WHERE last_seen_at >= since`. This is the "created or updated in the last cycle" definition.
    - `_active_portfolios(session)` — `(user_id, portfolio_id)` for every `Portfolio.is_active = True`.
    - `_score_one(...)` — one (cluster, portfolio) task. Cheap pre-probe on `(cluster, user, portfolio)` to know whether the ensuing `score_cluster_for_user()` was a cache hit or a real invocation (used for stats + cost logging). Each task opens its OWN `AsyncSession` from the injected factory (async sessions aren't concurrency-safe).
    - `run_fanout(*, session_factory, news_store, themes_store, embed, llm, cluster_ids=None, since=None, concurrency=10)` — exactly one of `cluster_ids` / `since` required. Discovers clusters + active portfolios once at the start, then groups tasks per cluster: for each cluster, `asyncio.gather()` over all portfolios under an `asyncio.Semaphore(concurrency)`. Emits a per-cluster `fanout_cluster` log line (with `est_tokens` cost estimate = `classifier_calls * 800`) and a terminal `fanout_done` line with aggregate counts + wall clock.
  - `backend/app/main.py`:
    - The scheduler job that used to be `orchestrator.run` is now a wrapper `_ingest_and_fanout()` that captures `cycle_started = now`, runs the ingest, then calls `run_fanout(since=cycle_started, ...)`. Ingest failures don't skip fanout scheduling for future cycles (each is wrapped in its own try/except). The `EmbeddingClient`, `VectorStore("news_items")`, `VectorStore("themes")`, and `LLMClient()` are all constructed once at scheduler build and passed by reference.
  - `backend/tests/pipelines/test_relevance_fanout.py`:
    - `test_fanout_50_clusters_3_users_yields_at_most_150_rows_and_reruns_zero` — the literal BUILD acceptance. Runs to completion in ~10s on sqlite, well under the 5-minute bound. Second pass: `cache_hits=150`, LLM call count unchanged, `0` new rows.
    - `test_fanout_since_window_only_scores_clusters_touched_after_since` — old cluster before boundary + fresh cluster after → only fresh is scored.
    - `test_fanout_inactive_portfolios_are_skipped` — `is_active=False` portfolios don't count.
    - `test_fanout_respects_concurrency_bound` — a tracking-LLM records the max in-flight `complete()` calls; with `concurrency=2` and 4 portfolios × 1 cluster, `max_in_flight <= 2`.
    - `test_fanout_logs_per_cluster_cost_line` — a `fanout_cluster cluster=<id> ... est_tokens=<N>` line is emitted per cluster (acceptance: "Log per-cluster fan-out cost estimates").
    - `test_fanout_requires_cluster_ids_or_since` — calling without either raises `ValueError`.
- **Acceptance verified locally:**
  - `python -m pytest tests -q` → **170 passed, 5 deselected** (+6 new hermetic tests).
  - `ruff check .` clean.
- **Files touched:** created `backend/app/pipelines/relevance_fanout.py`, `backend/tests/pipelines/test_relevance_fanout.py`. Modified `backend/app/main.py` (scheduler job wraps ingest+fanout), `BUILD.md` (tick), `HANDOFF.md` (this file).
- **Migrations added:** none.
- **Tests added:** 6 hermetic.
- **In-flight work:** none.
- **Deviations from BUILD.md:**
  - **"Created or updated in the last cycle" is defined as `NewsCluster.last_seen_at >= cycle_started`.** BUILD.md phrases it in plain English without naming a column; `last_seen_at` is the natural cluster-touched-timestamp (bumped whenever an item dedupes into the cluster).
  - **`run_fanout` accepts either an explicit `cluster_ids` iterable or a `since` timestamp.** BUILD.md only mentions the "last cycle" flow; `cluster_ids` gives back-fill / manual re-scoring callers a clean entry, and tests use it to be deterministic. Exactly one must be supplied — a `ValueError` otherwise.
  - **Cost is logged as `est_tokens` (integer, ≈ `classifier_calls × 800`), not `$`**. PRD §11.4 pins fast-tier free-tier at $0 marginal cost, so a dollar figure would always be 0. Token count is the meaningful operational signal.
  - **Scheduler wiring changed.** The APScheduler job's callable moved from `orchestrator.run` to a nested `_ingest_and_fanout` wrapper in `main.py::_build_default_orchestrator`. Ingest and fanout are each wrapped in their own `try/except` so a failure in one doesn't kill the other. No test covers `main.py` directly (matches the existing pattern — orchestrator is tested via its own module).

---

## Environment state

- Backend: full ingest → cluster → fan-out → relevance-score pipeline is wired in-process. The scheduler tick now populates `relevance_scores` autonomously.
- Frontend: unchanged.
- Database: Alembic head `b8ef3a217c04`. No schema change in REL-05.
- Vectors: unchanged (news_items + themes collections).
- Tests: **170 hermetic, 5 opt-in.**
- CI: last successful run on REL-02 (REL-03..REL-05 pending push through CI).
- Docs: unchanged.

---

## Open questions / blockers

- **None.** REL-06 wires the read side: two FastAPI endpoints over `relevance_scores` scoped to the caller's active portfolio.

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
