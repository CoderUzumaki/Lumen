# Handoff — Lumen Intelligence Agent

**Branch:** `v2/intelligence-agent`
**Base:** `refactor` (at commit `af39bef` — latest from origin/refactor)
**Last updated:** 2026-07-17 (session 29 — REL-06 news read endpoints)
**Progress:** 31/60 modules complete (HP-01, HP-02, BOOT-01..BOOT-08, DATA-01..DATA-05, ING-01..ING-10, REL-01..REL-06). DATA-06 (frontend UI) + REL-07 (frontend news feed) still pending — both are frontend-blocked; backend continues into Phase 4 (Impact Analysis Agent).

---

## Next module

**ID:** `IMP-01`
**Title:** Impact schema + migration
**Depends on:** DATA-01 (auth.users FK pattern), REL-01 (relevance_scores table pattern).
**Read:** `BUILD.md` → the `IMP-01` block starting at ~line 886. Introduces `backend/app/db/models/impact.py` + an Alembic migration for the impact-assessment table (structured output of the impact analyst agent — see PRD §4 "For each relevant event"). Cross-reference the REL-01 model + migration pair for the portability patterns (`ARRAY(...).with_variant(JSON, "sqlite")`, conditional `auth.users` FK, unique constraint shape).

**Why skip REL-07 and DATA-06?** Both are frontend modules. The previous agents kept `v2/intelligence-agent` moving on the backend spine so the frontend can be tackled later against a stable API surface. Continue that pattern unless the user redirects.

**Branch state:** REL-06 exposes `/api/news/relevant` (with `?limit=&since=` + active-portfolio scoping) and `/api/news/clusters/{id}` (with placeholder `impact: null` slot). IMP-01 fills that slot with a real schema.

Before starting, verify:
- `git branch --show-current` (from `.claude/worktrees/v2`) shows `v2/intelligence-agent`.
- `git log --oneline -5` shows REL-06 on top.
- `git status` is clean.
- `cd backend && python -m pytest tests -q` reports **179 passed, 5 deselected**.
- `ruff check .` clean.

---

## Last session

- **Session goal:** Execute REL-06 — two FastAPI read endpoints over `relevance_scores`, active-portfolio-scoped, cross-user-safe.
- **Completed:**
  - `REL-06` ✅ — News endpoints.
  - `backend/app/schemas/news.py`:
    - Added `RelevanceRead` (mirrors the `RelevanceScore` model — `id`, `cluster_id`, `user_id`, `portfolio_id`, `score`, `touched_position_ids`, `touched_theme_ids`, `stage` (Literal['prefilter','classifier']), `rationale`, `computed_at`).
    - `RelevantClusterRead` — `{cluster: NewsClusterRead, relevance: RelevanceRead}` for the feed.
    - `ClusterDetailRead` — `{cluster, relevance | None, impact: Any = None}` for the detail endpoint. `impact` is `Any` for now; IMP-01 will tighten it to a real `ImpactRead` schema.
  - `backend/app/routes/news.py`:
    - `_active_portfolio(user_id, db)` — helper that returns the caller's active portfolio (or None).
    - `GET /api/news/relevant?limit=&since=` — `limit ∈ [1, 100]` (default 20). SQL: `SELECT relevance_scores, news_clusters JOIN ON cluster_id WHERE user_id=? AND portfolio_id=? [AND last_seen_at >= since] ORDER BY score DESC, last_seen_at DESC LIMIT ?`. Uses the `idx_relevance_user_score` index. Empty list (200) when the caller has no active portfolio — legitimate onboarding state, not an error.
    - `GET /api/news/clusters/{cluster_id}` — 404 for unknown cluster. Loads cluster + items (published_at DESC) + the caller's own relevance row (if any). Cross-user check: relevance query filters on `user_id = caller` AND `portfolio_id = caller's active pf`, so another user's row on the same cluster is invisible.
  - `backend/app/main.py`:
    - Included `news_routes.router` alongside the existing routers.
  - `backend/tests/routes/test_news.py`:
    - `test_relevant_feed_orders_by_score_desc_then_last_seen_desc` — 3 clusters, verified tiebreak on `last_seen_at`.
    - `test_relevant_feed_respects_limit_and_since` — `limit=3` returns 3 of 6; `since` filter with URL-encoded ISO datetime (via httpx `params=`) drops older clusters.
    - `test_relevant_feed_excludes_other_users_rows` — shared cluster, Bob has a 0.99 row, Alice sees `[]`; after Alice adds her own row she sees only hers.
    - `test_relevant_feed_uses_active_portfolio_only` — inactive portfolio's high-score row does not surface.
    - `test_relevant_feed_with_no_active_portfolio_returns_empty` — no pf → `[]`.
    - `test_cluster_detail_includes_items_and_caller_relevance` — items are newest-first; relevance body present; `impact` is null.
    - `test_cluster_detail_relevance_is_null_when_caller_has_no_row` — no row for caller → `relevance: null`.
    - `test_cluster_detail_never_exposes_another_users_relevance` — Bob has scored, Alice fetches → `relevance: null` (only Bob's row exists, and it's invisible).
    - `test_cluster_detail_404_for_unknown_cluster` — random UUID → 404.
  - Auth is stubbed via `app.dependency_overrides[require_auth]` — same pattern used by `tests/routes/test_portfolios.py`.
- **Acceptance verified locally:**
  - `python -m pytest tests -q` → **179 passed, 5 deselected** (+9 new hermetic tests).
  - `ruff check .` clean.
- **Files touched:** created `backend/app/routes/news.py`, `backend/tests/routes/test_news.py`. Modified `backend/app/schemas/news.py` (added 3 schemas), `backend/app/main.py` (router include), `BUILD.md` (tick), `HANDOFF.md` (this file).
- **Migrations added:** none.
- **Tests added:** 9 hermetic.
- **In-flight work:** none.
- **Deviations from BUILD.md:**
  - **Ordering is `score DESC, cluster.last_seen_at DESC` — not `published_at DESC`.** BUILD.md says `score DESC, published_at DESC` without naming the entity. `NewsCluster` has no `published_at`; the cluster-level freshness signal is `last_seen_at` (bumped when the newest item dedupes in). Joining to `news_items` just to sort would burn an index scan for no user-visible gain, so the sort is on `last_seen_at` at the cluster level. Same rule as REL-05's `since` window.
  - **No active portfolio → `200 []`, not `404`.** BUILD.md doesn't spell out this edge case; empty list keeps the feed page renderable for a newly-signed-up user who hasn't set up a portfolio yet.
  - **`ClusterDetailRead.impact` is typed `Any = None`** as a shape-stable placeholder. Once IMP-01 lands `ImpactRead`, tighten to `ImpactRead | None = None`.
  - **The 300ms perf acceptance is not tested with a 10k-cluster corpus** — the hermetic sqlite suite would need seed fixtures that dwarf the test runtime. The `(user_id, score)` index from REL-01 and the LIMIT keep the query cheap; on Postgres with the index this is trivially sub-100ms. If we grow ops confidence bars later, add a `@pytest.mark.integration` corpus test that seeds 10k clusters + 200 rows and measures wall-clock.

---

## Environment state

- Backend: full read stack over `relevance_scores` is live behind auth. Frontend can now render a personalized feed.
- Frontend: unchanged.
- Database: Alembic head `b8ef3a217c04`. No schema change in REL-06.
- Vectors: unchanged.
- Tests: **179 hermetic, 5 opt-in.**
- CI: REL-03..REL-06 pending push through CI.
- Docs: unchanged.

---

## Open questions / blockers

- **None.** IMP-01 introduces the `impact_assessments` table + Alembic migration — pattern-copy REL-01. If REL-07 (frontend news feed) turns out to block a demo before DATA-06 finishes, escalate to the user for scope reordering.

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
