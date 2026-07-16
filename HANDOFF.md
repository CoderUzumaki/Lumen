# Handoff — Lumen Intelligence Agent

**Branch:** `v2/intelligence-agent`
**Base:** `refactor` (at commit `af39bef` — latest from origin/refactor)
**Last updated:** 2026-07-17 (session 27 — REL-04 relevance graph)
**Progress:** 29/60 modules complete (HP-01, HP-02, BOOT-01..BOOT-08, DATA-01..DATA-05, ING-01..ING-10, REL-01..REL-04). DATA-06 (frontend UI) still pending.

---

## Next module

**ID:** `REL-05`
**Title:** Fan-out worker: score new clusters for all users
**Depends on:** REL-04, ING-10
**Read:** `BUILD.md` → the `REL-05` block. Builds `backend/app/pipelines/relevance_fanout.py`: after each ingest cycle, enumerate clusters created/updated in that cycle × each user's active portfolio and enqueue `score_cluster_for_user()` calls in a bounded `asyncio.Semaphore(10)` worker pool. Log per-cluster cost estimates. Acceptance: 50 clusters × 3 active users → ≤ 150 rows within 5 minutes; re-running yields 0 new rows.

**Branch state:** REL-01 schema, REL-02 prefilter, REL-03 classifier, and REL-04 graph (`score_cluster_for_user`) are all live. Idempotency is enforced at the graph boundary — REL-05 can spam calls without worrying about duplicate rows.

Before starting, verify:
- `git branch --show-current` (from `.claude/worktrees/v2`) shows `v2/intelligence-agent`.
- `git log --oneline -5` shows REL-04 on top.
- `git status` is clean.
- `cd backend && python -m pytest tests -q` reports **164 passed, 5 deselected**.
- `ruff check .` clean.

---

## Last session

- **Session goal:** Execute REL-04 — compose prefilter + classifier as a LangGraph with cache-hit idempotency and a `force=True` override.
- **Completed:**
  - `REL-04` ✅ — Relevance graph (LangGraph).
  - `backend/app/agents/relevance/graph.py`:
    - `_GraphState` — `TypedDict` carrying cluster/user/portfolio ids, injected deps (`session`, `news_store`, `themes_store`, `embed`, `llm`), the `PrefilterResult`, and the final `row`.
    - `_prefilter_node` — invokes `run_prefilter()`; if the prefilter short-circuits with a persisted row, that row is written into state and the graph routes to END.
    - `_classifier_node` — invokes `run_classifier()` with the prefilter's candidate shortlists.
    - `_route_after_prefilter` — conditional edge: `passed=True → classifier`, else `→ END`.
    - `_build_graph()` compiles a `StateGraph(_GraphState)` with `START → prefilter → {classifier | END}` and `classifier → END`. **Compiled at import time** as `RELEVANCE_GRAPH` so shape errors surface immediately (acceptance).
    - `score_cluster_for_user(cluster_id, user_id, portfolio_id, *, session, news_store, themes_store, embed, llm, force=False, agent_name)`:
      1. Cache probe on the unique `(cluster_id, user_id, portfolio_id)` key.
      2. Cache hit + `force=False` → return the cached row (no LLM call).
      3. Cache hit + `force=True` → delete the row (unique-constraint headroom), commit, then run the graph.
      4. `await RELEVANCE_GRAPH.ainvoke({...})` → return the `row` produced by whichever branch ran.
  - `backend/tests/agents/test_relevance_graph.py`:
    - `test_graph_compiles_at_import` — validates `RELEVANCE_GRAPH` is a compiled, invocable graph.
    - `test_prefilter_hit_returns_classifier_row` — Fed-style vector + AAPL portfolio → prefilter passes → classifier persists a `stage='classifier'` row with the mocked verdict; LLM call count = 1.
    - `test_prefilter_short_circuit_returns_prefilter_row_and_skips_llm` — Pharma vector + tech portfolio → prefilter drops the cluster, returns the persisted `stage='prefilter'` row, and the classifier LLM is never called (count = 0).
    - `test_idempotent_second_call_returns_cached_row_without_llm` — two invocations for the same key: second returns identical row, DB has exactly one row, LLM call count stays at 1.
    - `test_force_true_re_invokes_and_replaces_row` — first call → row A (LLM count = 1); swap verdict, `force=True` → new row B with the updated score/rationale (LLM count = 2), DB still has exactly one row for the key.
  - Uses a `_CountingLLM` subclass of `LLMClient` that returns a canned `RelevanceVerdict` and increments `.calls`, so the "LLM not re-invoked on cache hit" claim is directly asserted.
- **Acceptance verified locally:**
  - `python -m pytest tests -q` → **164 passed, 5 deselected** (+5 new hermetic tests).
  - `ruff check .` clean.
- **Files touched:** created `backend/app/agents/relevance/graph.py`, `backend/tests/agents/test_relevance_graph.py`. Modified `BUILD.md` (tick), `HANDOFF.md` (this file).
- **Migrations added:** none.
- **Tests added:** 5 hermetic.
- **In-flight work:** none.
- **Deviations from BUILD.md:**
  - **`force=True` deletes the cached row before re-running.** BUILD.md says "re-invoking the LLM (unless `force=True`)" without saying what happens to the existing row. The unique constraint on `(cluster, user, portfolio)` means a naive re-run would trip `UNIQUE`; deletion is the simplest correct handling and preserves the invariant that at most one row exists per key.
  - **`score_cluster_for_user` takes injected deps (`session`, `news_store`, `themes_store`, `embed`, `llm`) as keyword-only args**, not built from a global container. Matches the shape of `run_prefilter`/`run_classifier` and keeps tests hermetic. Callers (REL-05 fan-out worker will be the first) construct these once and pass them in.

---

## Environment state

- Backend: prefilter + classifier + graph composition all wired. `score_cluster_for_user()` is the entry point for REL-05's fan-out.
- Frontend: unchanged.
- Database: Alembic head `b8ef3a217c04`. No schema change in REL-04.
- Vectors: unchanged.
- Tests: **164 hermetic, 5 opt-in.**
- CI: last successful run on REL-02 (REL-03 and REL-04 pending push).
- Docs: unchanged.

---

## Open questions / blockers

- **None.** REL-05 wires the fan-out worker: after each ingest cycle, for each newly-created/updated cluster × each active portfolio, spawn `score_cluster_for_user()` under an `asyncio.Semaphore(10)`.

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
