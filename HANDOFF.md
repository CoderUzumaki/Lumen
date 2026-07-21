# Handoff — Lumen Intelligence Agent

**Branch:** `v2/intelligence-agent`
**Base:** `refactor` (at commit `af39bef` — latest from origin/refactor)
**Last updated:** 2026-07-21 (session 33 — IMP-04 + BRIEF-01 + CHAT-01, run in parallel)
**Progress:** 40/60 modules complete (HP-01, HP-02, BOOT-01..BOOT-08, DATA-01..DATA-05, ING-01..ING-10, REL-01..REL-06, IMP-01..IMP-04, GRD-01..GRD-03, BRIEF-01, CHAT-01). DATA-06 (frontend UI) + REL-07 (frontend news feed) + IMP-06 (frontend impact card) still pending — all frontend-blocked; backend continues.

---

## Next module

**ID:** `IMP-05`
**Title:** Impact endpoint + on-demand generation
**Depends on:** IMP-04 (now live), REL-06 (news endpoints).
**Read:** `BUILD.md` → the `IMP-05` block at ~line 1032. Wires the impact analyst behind a FastAPI endpoint (probably `POST /api/impact/generate/{cluster_id}` or similar — check the block for exact shape) and updates `ClusterDetailRead.impact` in `app/schemas/news.py` from the placeholder `Any = None` to `ImpactRead | None`.

After IMP-05: BRIEF-02 (briefing synthesizer agent), CHAT-02 (chat retrieval tools), and BRIEF-03 (scheduled briefing generation) become the next parallelizable trio. BRIEF-02 depends on IMP-05 + BRIEF-01. CHAT-02 depends on IMP-05 + ING-07. BRIEF-03 depends on BRIEF-02.

**Branch state:**
- IMP-04 is fully live and exercised by 8 hermetic tests. `analyze_impact_for_user(cluster_id, user_id, portfolio_id, *, session, analogs_store, embed, llm, fetch_prices=..., force=False)` in `app.agents.impact.graph` — same shape as REL-04's entry point. Returns `ImpactAssessment | None` (None on hard LLM parse failure with no salvageable content).
- The graph's `validate` node passes `skip_llm=True` to `check_directional` — only the lexical stage runs INSIDE the graph. Rationale: sharing one scripted `LLMClient` between `reason_mechanism` and GRD-01's YES/NO stage would make the repair loop non-deterministic under test doubles. Production still gets the strict lexical rule; if you want GRD-01's LLM stage too, wire it via a separate `LLMClient` instance in IMP-05's endpoint construction (not inside the graph).
- `Briefing`, `ChatSession`, `ChatMessage` tables + Pydantic schemas are live. Alembic head is `e5b02c8f6a39` (CHAT-01).
- `ClusterDetailRead.impact` is STILL typed `Any = None` in `app/schemas/news.py`. IMP-05 should tighten this to `ImpactRead | None` and wire the actual serialization from a persisted row.

Before starting, verify:
- `git branch --show-current` (from `.claude/worktrees/v2`) shows `v2/intelligence-agent`.
- `git log --oneline -5` shows the BRIEF-01 / CHAT-01 / IMP-04 trio on top.
- `git status` is clean.
- `cd backend && python -m pytest tests -q` reports **282 passed, 5 deselected**.
- `ruff check .` clean.
- `DATABASE_URL="sqlite:///./_scratch.db" alembic upgrade head` → `downgrade -2` → `upgrade head` clean (delete the scratch db afterward). Verified end-to-end this session.

---

## Last session

- **Session goal:** Ship three modules in parallel — IMP-04 (impact analyst LangGraph, biggest agent module so far), BRIEF-01 (briefings table + migration), CHAT-01 (chat_sessions + chat_messages tables + migration). Three subagents in the shared v2 worktree; parent pre-assigned migration revision IDs so BRIEF-01 → CHAT-01 chained linearly on top of IMP-01's head (`c3b8f4e1d7a2`).
- **Completed:**
  - `IMP-04` ✅ — Impact analyst LangGraph.
    - `backend/app/agents/impact/graph.py` — compiled at import time as `IMPACT_GRAPH`. Nodes: `load_context` (cluster + touched positions from most-recent classifier row + source stubs from news items) → `retrieve_analogs` (via IMP-02) → `fetch_price_context` (via IMP-03, wrapped in `asyncio.to_thread`) → `reason_mechanism` (thorough-tier LLM → `ImpactAssessmentPayload`) → `validate` (GRD-01 lexical + GRD-02 citations) → conditional `repair_prompt` → 2nd `reason_mechanism` → `persist` → END.
    - `backend/app/agents/impact/prompts.py` — `_SYSTEM_PROMPT`, `build_reason_prompt(state)`, `build_repair_prompt(state)`. Body verbatim from BUILD.md IMP-04 with the "no directional language" enforcement list embedded.
    - Public entry: `async analyze_impact_for_user(cluster_id, user_id, portfolio_id, *, session, analogs_store, embed, llm, fetch_prices=get_recent_price_action, force=False) -> ImpactAssessment | None`. Idempotency mirrors REL-04's `score_cluster_for_user`.
    - `backend/tests/agents/test_impact_graph.py` — 8 hermetic tests: graph compiles at import; happy path persists row; idempotency (cache hit skips LLM); `force=True` re-runs; guardrail violation → repair succeeds; persistent violation → row persists with `guardrail_violations` populated; citation validator catches hallucinated URL; yfinance-None wraps gracefully. Uses `_ScriptedLLM(LLMClient)` that returns a queue of canned `ImpactAssessmentPayload` responses.
    - **Design choice logged:** the graph passes `skip_llm=True` to `check_directional` — LLM-stage of GRD-01 is deliberately out-of-graph to keep the test LLM queue deterministic (a shared scripted LLM feeding both the reasoning and the guardrail's YES/NO would be untestable).
  - `BRIEF-01` ✅ — Briefings table + Alembic migration + Pydantic schemas.
    - `backend/app/db/models/briefing.py` — `Briefing(IdMixin, Base)`. Fields per BUILD.md's DDL: `user_id`, `portfolio_id`, `briefing_date` (Date), `structured_content` (`JSONB.with_variant(JSON, sqlite)`), `cited_impact_ids` (`ARRAY(UUID).with_variant(JSON, sqlite)` — wire type `list[str]`), `generated_at` (explicit `server_default=func.now()`), `generation_duration_ms`, `langsmith_run_id`. Unique `(user_id, portfolio_id, briefing_date)`. Index `(user_id, briefing_date DESC)`.
    - `backend/alembic/versions/d4a91b7f5e28_brief01_briefings.py` — revision `d4a91b7f5e28`, down_revision `c3b8f4e1d7a2` (IMP-01 head). Postgres-only `auth.users` FK via `_is_postgres()`. `cited_impact_ids` server default `'{}'::uuid[]` on Postgres, `'[]'` on sqlite.
    - `backend/app/schemas/briefing.py` — `BriefingItem` (`impact_id`, `cluster_title`, `one_line_summary`, `affected_positions: list[str]`, `mechanism_summary`, `confidence`), `BriefingContent` (three lists capped at 5 + `generated_summary`), `BriefingRead` (from-attributes response schema).
    - `backend/tests/db/test_briefing.py` — 10 tests: ORM roundtrip, unique constraint, cascade on portfolio delete, Pydantic cap enforcement per list, confidence bounds, migration head assertion + roundtrip (with the alembic `fileConfig` logger re-enable pattern from IMP-01).
  - `CHAT-01` ✅ — chat_sessions + chat_messages tables + Pydantic schemas.
    - `backend/app/db/models/chat.py` — `ChatSession(IdMixin, TimestampsMixin, Base)` and `ChatMessage(IdMixin, CreatedAtMixin, Base)`. Session: `user_id`, `portfolio_id`, `title`, `seed_cluster_id` (nullable FK to `news_clusters`). Message: `session_id`, `role` (CHECK `role IN ('user','assistant','system')`), `content`, `citations` (JSONB variant, default `[]`), `tokens_used`, `langsmith_run_id`, `guardrail_violations` (JSONB variant, default `[]`). Indexes: `(user_id, updated_at DESC)` on sessions, `(session_id, created_at)` on messages.
    - `backend/alembic/versions/e5b02c8f6a39_chat01_chat_sessions_messages.py` — revision `e5b02c8f6a39`, down_revision `d4a91b7f5e28` (BRIEF-01 head). Two tables in one migration. Postgres-only `auth.users` FK on sessions.
    - `backend/app/schemas/chat.py` — `ChatSessionCreate`, `ChatSessionRead` (embeds messages), `ChatMessageIn`, `ChatMessageRead`. Reuses `Citation` from `app.schemas.impact`.
    - `backend/tests/db/test_chat.py` — 8 tests: two-table ORM roundtrip, role CHECK rejects bad values, session→messages cascade, portfolio→sessions cascade, `seed_cluster_id` FK enforcement, migration head assertion, Pydantic `ChatMessageIn.content` bounds.
  - `backend/app/db/models/__init__.py` — registered `Briefing`, `ChatMessage`, `ChatSession` alphabetically alongside the existing entries. Split across commits so each intermediate SHA imports cleanly.
- **Acceptance verified locally:**
  - `python -m pytest tests -q` → **282 passed, 5 deselected** (+26 new: 8 IMP-04 + 10 BRIEF-01 + 8 CHAT-01).
  - `ruff check .` clean.
  - `alembic upgrade head → downgrade -2 → upgrade head` clean on sqlite (traverses both new migrations both ways).
- **Files touched:** 12 new files (4 per module: model + migration + schema + tests for the DB modules; graph + prompts + package `__init__` + tests for IMP-04). Modified `backend/app/db/models/__init__.py` (three entries added). Ticked IMP-04, BRIEF-01, CHAT-01 in `BUILD.md`. Rewrote this `HANDOFF.md`.
- **Migrations added:** 2 (`d4a91b7f5e28_brief01_briefings`, `e5b02c8f6a39_chat01_chat_sessions_messages`).
- **Tests added:** 26 hermetic.
- **In-flight work:** none.
- **Deviations from BUILD.md:**
  - **IMP-04 `validate` node uses `check_directional(text, skip_llm=True)`** — only the lexical stage runs in-graph. Rationale documented in `graph.py`'s module docstring and above.
  - **IMP-04 returns `None` on hard failure** (LLM parse error with no salvageable draft), not a placeholder row. Callers (IMP-05 endpoint) must handle the None case.
  - **IMP-04 `langsmith_run_id` is always `None`** in persisted rows — `LLMResponse` doesn't surface it yet. Fill in when BOOT-06-adjacent LangSmith wiring exposes the id.
  - **BRIEF-01 migration head test targets revision `d4a91b7f5e28`** explicitly rather than `head` (which is downstream after CHAT-01's chain). The test stays invariant to further chained migrations.
  - **CHAT-01 `guardrail_violations` typed `list[dict]`** on `ChatMessageRead` — BUILD.md doesn't specify a shape, so we kept it loose (mirrors the JSON stored server-side).
- **Session mechanics recap:** Three subagents ran in parallel in the shared v2 worktree. Parent pre-assigned migration revisions (BRIEF-01: `d4a91b7f5e28`, CHAT-01: `e5b02c8f6a39` chaining after BRIEF-01) so alembic history stays linear. Both agents also concurrently edited `backend/app/db/models/__init__.py` — the file ended in a 3-way-stacked state (Briefing + ChatMessage/ChatSession + ImpactAssessment). Parent split commits surgically: BRIEF-01 commit's `__init__.py` has only Briefing added; CHAT-01 commit's `__init__.py` adds Chat entries on top; IMP-04 commit doesn't touch `__init__.py`. Each intermediate SHA imports cleanly (bisect-safe). Commits (in order): BRIEF-01 → CHAT-01 → IMP-04 (which carries the BUILD.md ticks for all three + this HANDOFF).

---

## Environment state

- Backend: impact analyst is live end-to-end (retrieve analogs → fetch prices → reason → validate → repair? → persist). Briefing + chat schema layers ready for their agent/endpoint modules.
- Frontend: unchanged.
- Database: Alembic head `e5b02c8f6a39` (CHAT-01). Two new tables (`briefings`, `chat_sessions`, `chat_messages`).
- Vectors: unchanged. Remember `python -m app.evals.seed_analogs` before smoke-testing IMP-04 or IMP-05 locally against real Chroma.
- Tests: **282 hermetic, 5 opt-in.**
- CI: REL-03..this-batch pending push through CI.
- Docs: unchanged.

---

## Open questions / blockers

- **None for IMP-05.** IMP-04 return-type is `ImpactAssessment | None` — the endpoint must handle the `None` case (either return a 502-shaped envelope or persist a placeholder-with-error and 200; recommend the former).
- **Follow-ups queued (do not fold into IMP-05 unless it's convenient):**
  - Tighten `ClusterDetailRead.impact: Any` to `ImpactRead | None` — actually **IMP-05 IS the natural home for this**. Do it there.
  - Refresh `yfinance` pin in `requirements.txt` (0.2.44 → 1.5.x).
  - Expand `analogs.json` from 37 → ~150 events.
  - Tighten GRD-03 lexical patterns (`audit`, `will`) if UX testing shows over-refusal.
  - Consider wiring GRD-01's LLM stage into IMP-04 via a separate `LLMClient` instance in the endpoint construction (not in the graph itself). Not blocking; ergonomic hardening for prod.
  - Surface `langsmith_run_id` from `LLMResponse` — currently always `None` on persisted impact rows.

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
