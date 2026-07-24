# Handoff — Lumen Intelligence Agent

**Branch:** `v2/intelligence-agent`
**Base:** `refactor` (at commit `af39bef` — latest from origin/refactor)
**Last updated:** 2026-07-21 (session 37 — CHAT-04 + SIM-02 in parallel via subagents)
**Progress:** 49/60 modules complete (HP-01, HP-02, BOOT-01..BOOT-08, DATA-01..DATA-05, ING-01..ING-10, REL-01..REL-06, IMP-01..IMP-05, GRD-01..GRD-03, BRIEF-01..BRIEF-04, CHAT-01..CHAT-04, SIM-02, EVAL-02). DATA-06 (frontend UI) + REL-07 (news feed) + IMP-06 (impact card) + BRIEF-05 (briefing page) + CHAT-05 (chat UI) + SIM-04 (scenario page) all pending — every frontend module.

---

## Next module

**ID:** `SIM-01`
**Title:** Scenario schema + endpoint
**Depends on:** IMP-04 (live), SIM-02 (now live).
**Read:** `BUILD.md` → the `SIM-01` block at ~line 1494. Builds `backend/app/routes/scenarios.py`. One endpoint:

```
POST /api/scenarios/simulate
     body: { scenario_text: string, portfolio_id?: UUID }
     response: SSE stream of scenario analysis (similar to impact analyst)
```

Note: `backend/app/schemas/scenario.py` **already exists** — SIM-02 preemptively landed the `PositionImpact` + `ScenarioSimulation` Pydantic shapes there (documented deviation in that module's docstring). SIM-01 just needs the route file + tests.

Endpoint semantics:
- Auth via `require_auth`.
- Body validated via a `ScenarioSimulateRequest(BaseModel)` in `app.schemas.scenario` — `scenario_text: str (min 1, max 2000)`, `portfolio_id: UUID | None`.
- If `portfolio_id` is omitted, use caller's active portfolio; 404 if no active portfolio.
- Cross-user check: if `portfolio_id` is provided but not the caller's → 404.
- Emit SSE pseudo-node envelope: `event: node_started`, then invoke `simulate_scenario(...)` on the injected runner, then emit `event: partial_content` with the serialized `ScenarioSimulation`, then `event: complete`. On error, emit `event: error`. (Same pattern used by BRIEF-04's `/api/briefings/stream`.)
- Persistence: none — matches SIM-02's shape.
- Injectable dependency `get_scenario_runner` for tests (mirror `get_impact_enqueue`, `get_briefing_enqueue`, `get_chat_turn_runner`).

**After SIM-01:** SIM-03 (preset scenarios — a curated JSON list + tiny helper) becomes trivial follow-up. Then only frontend + EVAL-01 (human labeling) + OPT chain remain in the backend spine.

**Branch state:**
- `simulate_scenario(user_id, portfolio_id, scenario_text, *, session, analogs_store, embed, llm, fetch_prices=...) -> ScenarioSimulation | None` in `app.agents.scenario.graph`. Pure function; no persistence.
- CHAT-04 exposes 5 endpoints under `/api/chat/sessions/*`. SSE emits a single synthetic `token` frame (BUILD's `tool_call`/`tool_result` events omitted pending a CHAT-03 refactor exposing `astream_events`).
- No new migrations this session (head is still `e5b02c8f6a39`, CHAT-01).

Before starting, verify:
- `git branch --show-current` (from `.claude/worktrees/v2`) shows `v2/intelligence-agent`.
- `git log --oneline -5` shows the CHAT-04 / SIM-02 pair on top.
- `git status` is clean.
- `cd backend && python -m pytest tests -q` reports **383 passed, 5 deselected**.
- `ruff check .` clean.

---

## Last session

- **Session goal:** Ship CHAT-04 + SIM-02 in parallel via two subagents (tighter risk profile after the earlier 3-agent stall).
- **Completed:**
  - `CHAT-04` ✅ — Chat endpoints + streaming.
    - `backend/app/routes/chat.py`: five endpoints — `POST /api/chat/sessions`, `GET /api/chat/sessions`, `GET /api/chat/sessions/{id}`, `DELETE /api/chat/sessions/{id}`, `POST /api/chat/sessions/{id}/messages` (SSE).
    - Session list orders by `updated_at DESC`. Detail includes messages `created_at ASC`. Every read cross-user-checked (`user_id=caller`); other-user access returns 404.
    - `POST /messages` streams `text/event-stream`. Emits `event: token` (one synthetic frame with the full content — CHAT-03 isn't token-streaming), `event: citations`, `event: done`. On `PermissionError` (cross-user race) or any other exception, emits `event: error`.
    - Injectable `TurnRunnerFn = (session_id, user_id, content) -> ChatMessage` via `get_chat_turn_runner`; tests substitute a stub that persists a canned assistant message.
    - Default runner constructs its own `AsyncSession` + `LLMClient` + `VectorStore("news_items")` + `EmbeddingClient()` per POST (request-scoped session dies before the SSE finishes; the runner needs its own).
    - `backend/tests/routes/test_chat.py`: 13 hermetic tests.
  - `SIM-02` ✅ — Scenario agent (LangGraph).
    - `backend/app/schemas/scenario.py`: `PositionImpact`, `ScenarioSimulation` (from BUILD's SIM-01 block — pre-emptively landed here since SIM-02 needs the type; SIM-01 will add `ScenarioSimulateRequest` on top).
    - `backend/app/agents/scenario/graph.py`: compiled at import as `SCENARIO_GRAPH`. Nodes: `load_portfolio_context` → `retrieve_analogs` → `fetch_price_context` → `reason_scenario` (thorough tier → `ScenarioSimulation`) → `validate` (GRD-01 lexical on `portfolio_summary` + each `PositionImpact.mechanism`) → END. **No persistence, no repair loop** — a scenario is a one-shot response. Documented in the module docstring.
    - Public entry: `async simulate_scenario(user_id, portfolio_id, scenario_text, *, session, analogs_store, embed, llm, fetch_prices=get_recent_price_action) -> ScenarioSimulation | None`. Returns None when the portfolio isn't the caller's, when the LLM parse fails, or when guardrails reject.
    - `backend/app/agents/scenario/prompts.py`: `SCENARIO_SYSTEM` + `build_reason_prompt(state)`.
    - `backend/tests/agents/test_scenario_graph.py`: 7 hermetic tests. Uses `_ScriptedLLM` mirror.
  - `backend/app/main.py`: added `chat_routes` import + `app.include_router(chat_routes.router)`.
- **Acceptance verified locally:**
  - `python -m pytest tests -q` → **383 passed, 5 deselected** (+20 new: 13 CHAT-04 + 7 SIM-02).
  - `ruff check .` clean.
- **Files touched:** 6 new files (2 routes/tests for CHAT-04; graph + prompts + schema + tests for SIM-02) + `main.py` router include. Ticked CHAT-04 and SIM-02 in `BUILD.md`. Rewrote this HANDOFF.
- **Migrations added:** none.
- **Tests added:** 20 hermetic.
- **In-flight work:** none.
- **Deviations from BUILD.md:**
  - **CHAT-04 SSE emits only `token`/`citations`/`done`.** `tool_call` / `tool_result` events are omitted pending a CHAT-03 refactor that exposes `astream_events`. The `token` event is a single synthetic frame with the assembled content, not per-token — same limitation as BRIEF-04's stream. Contract stable for the future refactor.
  - **CHAT-04's `TurnRunnerFn` signature is `(session_id, user_id, content) -> ChatMessage`** — the runner constructs its own session/LLM/store/embed. BUILD.md suggested passing them in; the endpoint's request-scoped session dies before the SSE completes, so keeping the runner self-contained is cleaner.
  - **SIM-02 has no persistence and no repair loop.** BUILD.md's IMP-04 pattern (which SIM-02 mirrors otherwise) includes both. Scenarios are ephemeral analyses — persistence, if any, belongs in SIM-01's endpoint (which can decide whether to log invocations).
  - **`ScenarioSimulation.citations` is allowed empty.** Every-claim-cites is a PRD hard rule for facts about the world; a hypothetical scenario references historical analogs instead (via `historical_analogs`). Deviation logged in the schema docstring.
  - **SIM-02 pre-emptively landed the `ScenarioSimulation` schema** in `app/schemas/scenario.py` — BUILD.md attributes that schema to SIM-01. SIM-01 now only needs to add `ScenarioSimulateRequest`.
- **Session mechanics recap:** Two subagents in parallel. Both landed clean on first try. Parent surgically split the BUILD.md ticks across the two commits (un-tick SIM-02 before committing CHAT-04, re-tick it for the SIM-02 commit) so each commit's diff shows exactly the module it lands. `main.py` was in CHAT-04's diff (router include); SIM-02 didn't touch main.py.

---

## (Prior session, for reference — kept short)

- **Session 36:** BRIEF-03 (in-session) + BRIEF-04 & CHAT-03 (parallel). 363 passed. Deviations: BRIEF-04 SSE pseudo-node envelope; CHAT-03 skip_llm=True; `run_chat_turn` raises PermissionError for cross-user.
- **Session 35:** BRIEF-02 + CHAT-02 + EVAL-02 rebuilt in-session after subagent stall. 335 passed.
- **Session 34:** IMP-05. 293 passed. `ClusterDetailRead.impact` tightened.

---

## Environment state

- Backend: chat endpoints + scenario agent live. Every backend agent module is now shipped (REL-01..06, IMP-01..05, BRIEF-01..04, CHAT-01..04, SIM-02, GRD-01..03, EVAL-02). SIM-01 endpoint is the only remaining backend module before all backend is done except EVAL-01+ (labeling) and OPT-01+ (optimizations).
- Frontend: unchanged. Six frontend modules still pending (DATA-06, REL-07, IMP-06, BRIEF-05, CHAT-05, SIM-04).
- Database: Alembic head `e5b02c8f6a39` (CHAT-01). No new migrations this session.
- Vectors: unchanged. Remember `python -m app.evals.seed_analogs` before smoke-testing IMP-05 / BRIEF-02 / SIM-02 against real Chroma.
- Tests: **383 hermetic, 5 opt-in.**
- CI: REL-03..this-batch pending push through CI.
- Docs: unchanged.

---

## Open questions / blockers

- **None for SIM-01.** SIM-02 is live and its `simulate_scenario` entry can be driven behind an injectable dependency (mirror `get_impact_enqueue` / `get_briefing_enqueue` / `get_chat_turn_runner`).
- **Follow-ups queued (do not fold into SIM-01 unless it's convenient):**
  - Wire `app.utils.langsmith.run_metadata(...)` into every LangGraph invocation site (REL-04, IMP-04, BRIEF-02, CHAT-03, SIM-02) — 5 one-line changes.
  - `analyze_impact_for_user` returns `None` on hard failure — IMP-05 currently swallows this. Consider a `impact_failures` table so the endpoint can surface "generation failed" instead of "still generating" forever.
  - Refresh `yfinance` pin in `requirements.txt` (0.2.44 → 1.5.x).
  - Expand `analogs.json` from 37 → ~150 events.
  - Tighten GRD-03 lexical patterns (`audit`, `will`) if UX testing shows over-refusal.
  - Wire GRD-01's LLM stage into IMP-04 / BRIEF-02 / CHAT-03 / SIM-02 endpoints via a separate `LLMClient` instance (not inside the graph). Ergonomic, not blocking.
  - Surface `langsmith_run_id` from `LLMResponse` onto persisted impact + briefing rows.
  - Add a `Config.IMPACT_MIN_SCORE` env var (code currently defaults to `Decimal("0.3")` via `getattr`).
  - Add `astream_events` support to CHAT-03 (and BRIEF-02) so CHAT-04 / BRIEF-04 can emit per-node + per-tool events instead of the current pseudo-node envelope.

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
