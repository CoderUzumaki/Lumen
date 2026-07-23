# Handoff — Lumen Intelligence Agent

**Branch:** `v2/intelligence-agent`
**Base:** `refactor` (at commit `af39bef` — latest from origin/refactor)
**Last updated:** 2026-07-21 (session 36 — BRIEF-03 in-session + BRIEF-04 & CHAT-03 in parallel via subagents)
**Progress:** 47/60 modules complete (HP-01, HP-02, BOOT-01..BOOT-08, DATA-01..DATA-05, ING-01..ING-10, REL-01..REL-06, IMP-01..IMP-05, GRD-01..GRD-03, BRIEF-01..BRIEF-04, CHAT-01..CHAT-03, EVAL-02). DATA-06 (frontend UI) + REL-07 (news feed) + IMP-06 (impact card) + BRIEF-05 (briefing page) + CHAT-05 (chat UI) all pending — every frontend module.

---

## Next module

**ID:** `CHAT-04`
**Title:** Chat endpoints + streaming
**Depends on:** CHAT-03 (now live).
**Read:** `BUILD.md` → the `CHAT-04` block at ~line 1253. Builds `backend/app/routes/chat.py`. Five endpoints:

```
POST   /api/chat/sessions                   body: { seed_cluster_id? } → ChatSessionRead
GET    /api/chat/sessions                    → list[ChatSessionRead]
GET    /api/chat/sessions/{id}               → ChatSessionRead + messages
DELETE /api/chat/sessions/{id}               → 204
POST   /api/chat/sessions/{id}/messages      body: { content: str } → SSE stream
```

SSE events for the message-post endpoint: `token`, `tool_call`, `tool_result`, `citations`, `done`. Ordered strictly.

Pattern-copy `app/routes/briefings.py` (BRIEF-04) for the SSE machinery — same trick: run the graph and emit pseudo-node events around it (proper LangGraph streaming is a future refactor). Cross-user access to a session returns 404.

**Parallelizable siblings after CHAT-04:**
- `EVAL-03` (relevance eval runner) — depends on EVAL-01 (needs a labeled dataset, human work) + REL-04. Not independent — needs EVAL-01 first, which is human labeling work.
- `EVAL-04` (impact + faithfulness runner) — same problem.
- `OPT-*` (optimization phase) — most depend on OPT chain built up; check individually.

Practically, after CHAT-04, the next parallel trio isn't obvious. Options: (a) tackle the EVAL-01 labeled-dataset problem head-on with a small pragmatic corpus (10-20 examples instead of the aspirational 200/50), (b) start wiring `run_metadata(...)` into the graphs (small cleanup — REL-04, IMP-04, BRIEF-02 each get one line), (c) begin the frontend chain with DATA-06 (single-session, big module). Escalate to user if unsure.

**Branch state:**
- `run_chat_turn(session_id, user_id, user_message, *, session, llm, news_store, embed) -> ChatMessage` in `app.agents.chat.graph`. Persists both user + assistant rows in one commit. Raises `PermissionError` on cross-user session access — the CHAT-04 endpoint must map this to HTTP 404 (matches BUILD.md's cross-user rule).
- BRIEF-04 exposes `/api/briefings/{latest,by-date,regenerate,stream}` — the stream endpoint emits SSE with a single pseudo-node envelope (documented deviation).
- BRIEF-03 wired into APScheduler at 15-minute intervals; runs `run_briefing_scheduler(...)` which is idempotent via BRIEF-02's unique key.
- No new migrations this session (head is still `e5b02c8f6a39`, CHAT-01).

Before starting, verify:
- `git branch --show-current` (from `.claude/worktrees/v2`) shows `v2/intelligence-agent`.
- `git log --oneline -5` shows the BRIEF-03 / BRIEF-04 / CHAT-03 trio on top.
- `git status` is clean.
- `cd backend && python -m pytest tests -q` reports **363 passed, 5 deselected**.
- `ruff check .` clean.

---

## Last session

- **Session goal:** Ship BRIEF-02 + CHAT-02 + EVAL-02 in parallel. First attempt via three background subagents; one failed with an API stall mid-response, the other two never returned a completion record (likely stopped when the parent process cycled). Only the empty `__init__.py` markers the parent pre-created survived. Second attempt: rebuilt all three sequentially in-session in the same worktree.
- **Completed:**
  - `EVAL-02` ✅ — LangSmith setup + tracing helpers.
    - `backend/app/utils/langsmith.py`:
      - `project_name(env=None) -> str` — maps `Config.FLASK_ENV` (`development`/`staging`/`production`) → `lumen-dev`/`lumen-staging`/`lumen-prod`; unknown → `lumen-dev`; explicit `env` overrides. Idempotent, no side effects.
      - `is_tracing_enabled() -> bool` — reads `os.environ`, not `Config` (LangSmith SDK reads env directly); requires BOTH `LANGSMITH_TRACING` truthy (`true`/`1`/`yes`/`on`) AND `LANGSMITH_API_KEY` non-empty.
      - `run_metadata(*, agent_name, user_id=None, git_sha=None, extra=None) -> dict` — returns `{"tags": [...], "metadata": {...}}`. Tags: `agent_name`, `env:<short>`, 7-char short sha. Metadata: `agent_name`, `git_sha` (full), optional `user_id` (as str), and any extras (extras cannot clobber reserved keys — attempts are logged + dropped). `git_sha` defaults to `os.environ["GIT_SHA"]` or `"dev"`.
      - `mark_public(run_id) -> str | None` — best-effort. Returns `None` if tracing disabled, if the `langsmith` SDK isn't importable, or if `Client.share_run(run_id)` raises. Never raises to the caller.
    - `backend/tests/utils/test_langsmith.py` — 20 hermetic tests. Uses `monkeypatch.setenv`/`delenv` for env vars, `unittest.mock.patch("langsmith.Client", ...)` for the share_run path, `sys.modules["langsmith"] = None` to simulate missing SDK.
    - No changes to `Config` — `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`, `LANGSMITH_TRACING` were already declared in BOOT-06. This module composes on top.
  - `CHAT-02` ✅ — Three chat retrieval tools.
    - `backend/app/agents/chat/retrievers.py`:
      - `retrieve_recent_impacts(user_id, portfolio_id, *, session, lookback_days=7, k=5) -> list[ImpactRead]` — SQL query filtered by `user_id` + `portfolio_id` + `created_at >= now - lookback_days`; ordered `confidence DESC, created_at DESC`. **Skips rows with non-empty `guardrail_violations`** (they represent failed generations and aren't useful chat context). Over-fetches k*3 to keep the after-filter count near k.
      - `retrieve_news(query, user_id, portfolio_id, *, session, news_store, embed, k=5, since_days=30, min_similarity=0.35) -> list[ChatNewsSnippet]` — RAG over `news_items` Chroma collection. Loads the caller's tickers from `positions.ticker`; over-fetches from Chroma (k*4), then filters each hit by (a) freshness within `since_days`, (b) cluster intersection with the caller's ticker set (via `NewsCluster.entity_tickers`), (c) `similarity >= min_similarity`. Snippet is `body[:500]` (or title if body absent). Empty ticker set → returns `[]` immediately.
      - `get_portfolio_summary(user_id, portfolio_id, *, session) -> PortfolioSummary | None` — one-shot: portfolio (with cross-user check — returns `None` if not the caller's), positions (ticker/asset_type/quantity/currency), themes (description/weight), and the most-recent `Briefing`'s `structured_content["generated_summary"]` + `briefing_date`.
    - `backend/tests/agents/test_chat_retrievers.py` — 12 hermetic tests. Uses the sqlite + Chroma tempdir env fixture from `tests/agents/test_relevance_prefilter.py`. Deterministic `_FakeEmbed` (3D vectors: `fed`/`aapl`/`rate` → axis 0, `pharma` → axis 1, else axis 2).
  - `BRIEF-02` ✅ — Briefing synthesizer LangGraph.
    - `backend/app/agents/briefing/graph.py` — compiled at import as `BRIEFING_GRAPH`. Nodes: `gather_impacts` → `rank_top_movers` → `rank_watchlist` → `synthesize_falsifiability` → `compose_summary` → `validate` → `persist`. All-linear graph (no conditional edges — validation failure just refuses persistence).
    - Public entry: `async synthesize_briefing_for_user(user_id, portfolio_id, *, session, llm, briefing_date=None, lookback_hours=24, force=False) -> Briefing | None`. Idempotent on the `(user_id, portfolio_id, briefing_date)` unique key.
    - Structured LLM outputs (Pydantic): `_RankPick(picks: list[UUID], one_line_summaries: dict[UUID, str])` for both ranking stages; `_FalsifiabilityList(items: list[str] max_length=5)`; `_Summary(text: str max_length=800)`.
    - `_gather_impacts_node` filters `confidence >= 0.5`, skips rows with `guardrail_violations`, ranks by `confidence * novelty` (novelty = `1 / (1 + hours_since_created)`), keeps top 15.
    - `_rank_top_movers_node` + `_rank_watchlist_node`: LLM picks are intersected with the actual candidate set (hallucination guardrail). Watchlist LLM is skipped when `remaining` is empty (all candidates went to top movers) — this is a small optimization and made two tests need a second seed impact to exercise both stages.
    - `_validate_node`: GRD-01 lexical on the summary, every top/watch `one_line_summary` + `mechanism_summary`, and every falsifiability item. Any violation blocks persistence (`row=None`). Deviation-from-BUILD: `skip_llm=True` mirrors IMP-04's rationale.
    - `_persist_node`: writes `Briefing.structured_content` via `BriefingContent(...).model_dump(mode="json")`; `cited_impact_ids = [str(id) for id in top+watch]`; `generation_duration_ms = int((monotonic - start) * 1000)`.
    - `backend/app/agents/briefing/prompts.py` — four SYSTEM constants, three `build_*_prompt(...)` helpers. All prompts enforce PRD principle #2 (no directional language) inline.
    - `backend/tests/agents/test_briefing_graph.py` — 10 hermetic tests: compile-at-import, happy path (5 impacts, 3 top + 2 watch), confidence-filter (all sub-0.5 → None + 0 LLM calls), idempotency (2 impacts so watchlist runs), force replaces row, hallucinated-id filter, guardrail violation blocks persistence, `affected_positions` → ticker resolution, skip-impacts-with-guardrail-violations, lookback-hours honored.
- **Acceptance verified locally:**
  - `python -m pytest tests -q` → **335 passed, 5 deselected** (+42 new: 20 EVAL-02 + 12 CHAT-02 + 10 BRIEF-02).
  - `ruff check .` clean.
- **Files touched:** 6 new modules (`utils/langsmith.py`, `agents/chat/retrievers.py`, `agents/briefing/graph.py`, `agents/briefing/prompts.py`, plus two `__init__.py` package markers created earlier this session for `app/agents/briefing/` and `app/agents/chat/`) + 3 new test files. Ticked BRIEF-02, CHAT-02, EVAL-02 in `BUILD.md`. Rewrote this HANDOFF.
- **Migrations added:** none.
- **Tests added:** 42 hermetic.
- **In-flight work:** none.
- **Deviations from BUILD.md:**
  - **BRIEF-02 uses `check_directional(..., skip_llm=True)`** — lexical-only guardrail inside the graph. Same rationale as IMP-04: a shared scripted LLM feeding both `compose_summary` and GRD-01's YES/NO would be untestable.
  - **BRIEF-02 skips the watchlist LLM call when `remaining` is empty** (all candidates chosen for top movers). Small optimization; test coverage adjusted (`test_idempotent_*` and `test_force_replaces_row` seed 2 impacts).
  - **BRIEF-02 returns `None` on guardrail violation** rather than persisting a "failed" row. Unlike IMP-04 (per-item, individually salvageable), a briefing is a single aggregate artifact — a leaked directional phrase in ANY section should block the whole thing.
  - **CHAT-02 filters news by `NewsCluster.entity_tickers` intersection with the caller's tickers.** BUILD says "filtered to items touching the user's tickers" without spelling out the mechanism. Using cluster metadata is clean and index-friendly on Postgres.
  - **EVAL-02 doesn't yet wire `run_metadata()` into the existing graphs** (REL-04, IMP-04, BRIEF-02). Deferred as a one-line addition per graph — should land alongside CHAT-03 or in a small "wire tracing metadata everywhere" cleanup.
- **Session mechanics recap:** Initial parallel-subagent attempt failed (BRIEF-02 stalled mid-response; CHAT-02 + EVAL-02 lost their completion records — likely process cycle). Diagnosed cleanly: only the empty `__init__.py` markers survived. Restarted sequentially in-session — EVAL-02 (smallest) → CHAT-02 → BRIEF-02 (biggest). Two BRIEF-02 tests needed a second seed impact after the first `pytest -v` revealed the "watchlist skipped when remaining empty" optimization. Full suite green on the retry.

---

## Environment state

- Backend: briefing synthesizer + chat retrieval tools + LangSmith tagging helpers all live. Ready for BRIEF-03 (scheduled generation) and CHAT-03 (agent that composes the retrieval tools).
- Frontend: unchanged.
- Database: Alembic head `e5b02c8f6a39` (CHAT-01). No new migrations this session.
- Vectors: unchanged. `historical_analogs` still needs a `python -m app.evals.seed_analogs` run before end-to-end smoke tests of IMP-04 / IMP-05 / BRIEF-02.
- Tests: **335 hermetic, 5 opt-in.**
- CI: REL-03..this-batch pending push through CI.
- Docs: unchanged.

---

## Open questions / blockers

- **None for BRIEF-03.** APScheduler already in place (see `main.py::_build_default_orchestrator` for the pattern). BRIEF-03 adds a second scheduled job; the existing `_ingest_and_fanout` wrapper is the recipe.
- **Follow-ups queued (do not fold into BRIEF-03 unless it's convenient):**
  - Wire `app.utils.langsmith.run_metadata(...)` into every LangGraph invocation site (REL-04, IMP-04, BRIEF-02) — 3 one-line changes: pass `config=run_metadata(agent_name=..., user_id=..., extra={"cluster_id": ...})` to `graph.ainvoke(state, config=...)`.
  - `analyze_impact_for_user` returns `None` on hard failure — IMP-05 currently swallows this. Consider a `impact_failures` table so the endpoint can surface "generation failed" instead of "still generating" forever.
  - Refresh `yfinance` pin in `requirements.txt` (0.2.44 → 1.5.x).
  - Expand `analogs.json` from 37 → ~150 events.
  - Tighten GRD-03 lexical patterns (`audit`, `will`) if UX testing shows over-refusal.
  - Wire GRD-01's LLM stage into IMP-04 and BRIEF-02 endpoints via a separate `LLMClient` instance (not inside the graph). Ergonomic, not blocking.
  - Surface `langsmith_run_id` from `LLMResponse` onto persisted impact + briefing rows.
  - Add a `Config.IMPACT_MIN_SCORE` env var (currently the code defaults to `Decimal("0.3")` via `getattr(Config, "IMPACT_MIN_SCORE", 0.3)`).

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
