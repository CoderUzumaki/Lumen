# Handoff — Lumen Intelligence Agent

**Branch:** `v2/intelligence-agent`
**Base:** `refactor` (at commit `af39bef` — latest from origin/refactor)
**Last updated:** 2026-07-24 (session 42 — DEPLOY-02 config artifacts; deploy pending user's `fly` credentials)
**Progress:** 57/60 modules complete + DEPLOY-02 config landed (unverified — `fly deploy` still owed by the user). Modules: HP-01, HP-02, BOOT-01..BOOT-08, DATA-01..DATA-06, ING-01..ING-10, REL-01..REL-07, IMP-01..IMP-06, GRD-01..GRD-03, BRIEF-01..BRIEF-05, CHAT-01..CHAT-05, SIM-01..SIM-04, EVAL-02. Remaining: DEPLOY-01, DEPLOY-02 tick (once verified), EVAL-01, OPT-*.

---

## Next module

**DEPLOY-02 config is on disk but not tick-verified.** Complete the user-side deploy steps (below) → verify `/health` returns 200 → tick DEPLOY-02 in BUILD.md. Then move to DEPLOY-01 (Vercel frontend).

**To finish DEPLOY-02 (user's runbook — full detail in `backend/DEPLOY.md`):**

1. Install `flyctl` + `flyctl auth login`.
2. `cd backend && flyctl launch --no-deploy --copy-config --name lumen-backend --region <region>` (pick the region closest to your Supabase Postgres).
3. `flyctl volumes create lumen_data --size 1 --region <region>` (Chroma + yfinance cache persistence).
4. `flyctl secrets set SECRET_KEY=… OPENROUTER_API_KEY=… SUPABASE_URL=… DATABASE_URL=postgresql+asyncpg://… ALLOWED_ORIGINS=…` — batch these into ONE call so the machine only restarts once. Optional: `NEWSAPI_KEY`, `MARKETAUX_KEY`, `LANGSMITH_API_KEY`, `LANGSMITH_TRACING=true`, `LANGFUSE_*`.
5. `flyctl deploy --remote-only`. First deploy runs Alembic migrations via the container ENTRYPOINT.
6. `curl https://<app-name>.fly.dev/health` should return `{"status":"ok","commit":"<git sha>"}`.
7. For CI-driven deploys on every push to `v2/intelligence-agent` that touches `backend/**`: `flyctl auth token`, then add it as `FLY_API_TOKEN` in GitHub → Settings → Secrets → Actions. The `.github/workflows/deploy-backend.yml` workflow uses this to run `flyctl deploy` automatically.
8. Once `/health` is green, tick `DEPLOY-02 — Backend on Fly.io ✅` in `BUILD.md`.

**Remaining after DEPLOY-02:**

- **DEPLOY-01** (Vercel frontend) — depends on the live backend URL. Once you have `https://<app>.fly.dev`, set `NEXT_PUBLIC_BACKEND_URL` in Vercel + deploy `frontend/`. Straightforward `vercel.json` + a GitHub Actions workflow.
- **EVAL-01** (golden dataset labeling) — 200 labeled tuples of `(news, portfolio, expected relevance/impact)`. Labeling work, not implementation. EVAL-02's harness is already live and waiting for this dataset. **Human-labeling task — ask before picking up.**
- **OPT-01+** (optimizations — rerankers, prompt cache, etc.) — polish; not blocking a working demo.

**Ask the user which direction they want.**

**Branch state:**
- Frontend has **12 routes**: `/`, `/signin`, `/onboarding/portfolio`, `/portfolios`, `/portfolios/[id]`, `/news`, `/news/[id]`, `/briefing`, `/chat`, `/chat/[id]`, `/scenarios`. Every authed page uses `<Suspense><AuthGuard>…</AuthGuard></Suspense>` + `export const dynamic = "force-dynamic"`. **There is no top-nav yet** — every page is a direct URL. Adding a nav is out of scope for any current BUILD.md module; if you want one, add a new module ID.
- Shared API scaffolding: `frontend/src/lib/api/client.ts` — `apiFetch`, `apiFetchRaw`, `openBackendStream` (fetch-driven SSE with Bearer auth). All six API modules (`portfolios`, `news`, `impact`, `briefings`, `chat`, `scenarios`) route through it. `frontend/src/hooks/use-sse.ts` supports GET + POST + JSON body; consumed by BRIEF-05, CHAT-05, SIM-04.
- Backend untouched this session.

Before starting, verify:
- `git branch --show-current` (from `.claude/worktrees/v2`) shows `v2/intelligence-agent`.
- `git log --oneline -3` shows this session's commits on top: `SIM-04` → `CHAT-05`.
- `git status` is clean.
- `cd backend && python -m pytest tests -q` reports **393 passed, 5 deselected** (backend unchanged — skip unless suspicious).
- `cd frontend && NEXT_PUBLIC_BACKEND_URL=http://localhost:8000 NEXT_PUBLIC_SUPABASE_URL=https://example.supabase.co NEXT_PUBLIC_SUPABASE_ANON_KEY=x npm run build && npm run lint` clean (12 routes compile, no lint warnings).

---

## Last session

- **Session goal:** Ship DEPLOY-02 backend config (Dockerfile / fly.toml / entrypoint / CI workflow / runbook). Cannot run `fly deploy` from this session (no `flyctl` credentials); handed the deploy step to the user with a full runbook.
- **Completed:**
  - `backend/Dockerfile` — python:3.11-slim base, system deps (build-essential, libpq-dev, libgomp1 for torch, curl for /health), pip install `requirements.txt`, `SentenceTransformer('all-MiniLM-L6-v2')` baked in at build time so first-request latency skips the ~90MB model pull, non-root `app` user (uid 1001), exposes 8080, `HEALTHCHECK` on `/health`, `ENTRYPOINT ["/app/scripts/entrypoint.sh"]`.
  - `backend/.dockerignore` — excludes `__pycache__`, tests, local sqlite / scratch DBs, `chroma_data/` + `price_cache/` (Fly volume replaces them), `.env*`, `.git/`, `.github/`.
  - `backend/scripts/entrypoint.sh` (executable bit set via `git update-index --chmod=+x`) — `mkdir -p` the Chroma + yfinance subdirs under `/app/data`, `python -m alembic upgrade head`, then `exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080} --workers 2 --proxy-headers --forwarded-allow-ips=*`.
  - `backend/fly.toml` — app `lumen-backend`, region `ord` (change before first launch), `[http_service]` modern syntax with `auto_stop_machines = "stop"` + `min_machines_running = 0` for free-tier hibernation, HTTP check on `/health` every 30s with a 45s grace period, single `[[vm]]` at `shared-cpu-1x` / `512mb`. `[[mounts]]` binds `lumen_data` → `/app/data`; `[env]` points `CHROMA_PATH` and `YFINANCE_CACHE_PATH` under it so persistence survives redeploys.
  - `.github/workflows/deploy-backend.yml` — runs `flyctl deploy --remote-only` on every push to `v2/intelligence-agent` touching `backend/**`. Also `workflow_dispatch` for manual runs. Requires `FLY_API_TOKEN` repo secret; documents that in the file header + `DEPLOY.md`.
  - `backend/DEPLOY.md` — one-time setup runbook (`fly launch`, `fly volumes create`, `fly secrets set`, first deploy, CI wiring) + day-2 ops (rollback, memory scale, secret updates, cache reset). Includes an explicit warning about the free-tier hibernation cold-start and the `ALLOWED_ORIGINS` step that pairs with DEPLOY-01.
- **Deploy status:** **not deployed.** Files are on disk + committed. User needs to run steps 1–7 from `backend/DEPLOY.md` (or from the "Next module" section above) to actually stand the backend up. Once `/health` is green, tick `DEPLOY-02 — Backend on Fly.io ✅` in `BUILD.md`.
- **Acceptance verified locally:**
  - No backend code changed. `pytest` not re-run — no Python files touched.
  - Dockerfile / fly.toml not built locally (no Docker / no flyctl on the session host). Syntax has been eyeballed against Fly's current schema (modern `[http_service]` block, `auto_stop_machines` string, `[[mounts]]` without deprecated `initial_size`).
- **Files touched:** 6 new files —
  - `backend/Dockerfile`
  - `backend/.dockerignore`
  - `backend/scripts/entrypoint.sh` (git mode 100755)
  - `backend/fly.toml`
  - `backend/DEPLOY.md`
  - `.github/workflows/deploy-backend.yml`
- **Migrations added:** none. (Alembic runs at container startup via ENTRYPOINT — no schema changes this session.)
- **Tests added:** none.
- **In-flight work:** DEPLOY-02 deploy step is owed by the user. See "Next module" section above for the exact commands.
- **Deviations from BUILD.md:**
  - **DEPLOY-02 tick is deferred until the user verifies `/health` on the live URL.** BUILD.md's acceptance criterion is "backend URL reachable, /health returns 200, ingest runs successfully" — none of which can be checked without cloud credentials. Files are committed on the assumption that the user will complete the deploy step in a follow-up.
  - **Volume mount destination is `/app/data`, not `/app/chroma_data` + `/app/price_cache`** (BUILD.md doesn't specify the exact path; PRD says a single volume). The two env vars point at subdirs under `/app/data` so both Chroma and yfinance cache share one Fly volume rather than paying for two.
  - **Alembic runs inside the container ENTRYPOINT**, not as a Fly `release_command`. Release VMs don't share the mounted volume, and there's no schema work that requires an isolated release step here — running at container boot is cheaper and always keeps schema in sync with the deployed image.
  - **`[http_service]` block, not the older `[[services]]`** — matches what `fly launch` currently emits, so `fly launch --copy-config` will merge cleanly.
- **Session mechanics recap:**
  - In-session (no subagents). DEPLOY-02 is 6 files totaling ~330 lines — small enough that spawning wasn't worth the overhead.
  - Fixed one path mismatch mid-session: initial fly.toml had `CHROMA_PATH=/app/chroma_data` but the mount was `/app/data` — Chroma would have written to an unmounted path and lost persistence. Aligned to `/app/data/chroma` + `/app/data/price_cache`, entrypoint ensures the subdirs exist.
  - Modernized the fly.toml to `[http_service]` after realizing the initial `[[services]]` shape would clash with `fly launch --copy-config`.
  - Executable bit stored in git (`git update-index --chmod=+x`) so `scripts/entrypoint.sh` runs directly on Fly's builder without needing a chmod inside the Dockerfile — belt-and-braces, the Dockerfile also runs `chmod +x` before switching users.

---

## Older last-session snapshots (short)

- **Session 41:** CHAT-05 + SIM-04 pair via 2 parallel subagents. 12 frontend routes compile.

## Prior-session detail (kept for continuity — no longer authoritative)

### Session 41 — CHAT-05 + SIM-04

- **Session goal:** Ship CHAT-05 + SIM-04 in parallel via 2 subagents — the last remaining frontend pair.
- **Completed:**
  - `CHAT-05` ✅ — `/chat` (index) + `/chat/[id]` (session view). Two-column layout: sidebar (newest-first sessions, New / Delete with `confirm()`) on the left, messages area on the right. `/chat` empty state prompts pick-or-start (first-time users get a big "Start your first chat" CTA). `/chat/[id]` renders history chronologically; on send, the user message appears immediately + a placeholder assistant bubble spinner-ticks until the first `token` frame; `citations` attaches numbered chips (hover → Tooltip; click → Sheet side panel with source / quote / external link); `done` invalidates the session query so the persisted UUID + `created_at` hydrate; `error` swaps to a destructive bubble with Retry. Assistant content renders through `react-markdown` (^9.0.1, already installed); user content stays plain text. Composer: native multi-line textarea, 4000-char cap with counter, Enter to send / Shift+Enter for newline. Deep-link `/chat?seed=<cluster_id>` fires once (ref guard), POSTs a new session with `seed_cluster_id`, then `router.replace`s to `/chat/<id>`. Session-title fallback: `title` → first 60 chars of first user message → "Untitled chat".
    - Files: `lib/api/chat.ts`, `app/chat/page.tsx`, `app/chat/[id]/page.tsx`, `components/chat/{session-sidebar,message-list,message-bubble,chat-composer,citation-chips,tool-badge}.tsx`.
  - `SIM-04` ✅ — `/scenarios`. Composer at top (native textarea, 1..2000 char validation, live counter, Cmd/Ctrl+Enter shortcut). Category-grouped preset chips row below the composer (categories come from the backend response — no hardcoded categories). Streaming result area: idle hint → spinner + "Simulating…" during stream → `node_completed` timestamp → full `SimulationView` on `result` frame → destructive alert with Retry on `error`. `SimulationView` renders portfolio_summary, per-position cards (mechanism prose, magnitude bar mirrored from IMP-06 in `number` mode on a fixed -25/+25% axis, confidence bar), key_assumptions bullets, falsifiability Alert, historical-analog cards, and citations chips (or the "hypothetical — grounded in historical analogs" copy when empty, matching the PRD deviation in `schemas/scenario.py`). History side panel in a `Sheet`: sessionStorage-backed at `lumen:scenario:history`, capped at 20 entries; each entry stores the full simulation so Reload restores results without a re-run.
    - Files: `lib/api/scenarios.ts`, `app/scenarios/page.tsx`, `components/scenarios/{preset-chips,scenario-composer,simulation-view,position-impact-card,history-panel}.tsx`.
- **Acceptance verified locally:**
  - `NEXT_PUBLIC_* npm run build` → **12 routes**, all compile cleanly (`/chat` static 7.49 kB, `/chat/[id]` dynamic 41 kB, `/scenarios` static 8.64 kB added).
  - `NEXT_PUBLIC_* npm run lint` → no ESLint warnings or errors.
  - Backend suite untouched — no runs this session.
- **Files touched:** 2 commits, one per module —
  - `CHAT-05`: `lib/api/chat.ts`, `app/chat/page.tsx` + `[id]/page.tsx`, `components/chat/*` (6 files), `BUILD.md` tick.
  - `SIM-04`: `lib/api/scenarios.ts`, `app/scenarios/page.tsx`, `components/scenarios/*` (5 files), `BUILD.md` tick, `HANDOFF.md`.
- **Migrations added:** none.
- **Tests added:** none.
- **In-flight work:** none.
- **Deviations from BUILD.md:**
  - **CHAT-05: `tool_call` / `tool_result` frames parsed + `console.debug`'d + ignored.** Not a deviation from CHAT-05 (BUILD.md requests the events); it's the pre-flagged backend deviation from CHAT-04 (SSE emits only `token` / `citations` / `done` / `error`). Client is forward-compat with a future CHAT-03 refactor.
  - **CHAT-05: `useSse` invoked with a `?_=${sendCounter}` cache-buster suffix per send** so the hook's memo-key changes each turn and the closure re-forms with the new body. FastAPI ignores unknown query params on `POST /messages`. Alternative would be modifying `use-sse.ts` to accept a `key` prop — cache-buster keeps the hook untouched.
  - **CHAT-05: no `@tailwindcss/typography`,** so `MessageBubble` uses a plain wrapper class instead of `prose`. Markdown still renders — headings / lists / code get react-markdown's default HTML and inherit body typography.
  - **SIM-04: no shadcn `Textarea` component in this repo,** so the composer uses a native `<textarea>` styled to match the `Input` component's tokens.
  - **SIM-04: history is client-only in `sessionStorage`.** The scenarios endpoint doesn't persist simulations; the "history side panel" acceptance line is honored via a 20-entry sessionStorage cache, not a backend table. Cleanup or persistence would be a new module (SIM-05 territory).
  - **SIM-04: Retry after an error re-submits the current composer text.** If the user edited the composer between failure and retry, Retry restores `activeScenario` to the composer and prompts them to press Simulate — avoids a React-batching pitfall where `sse.start()` would use stale body from the current render.
- **Session mechanics recap:**
  - Two parallel subagents per HANDOFF's "safer than 3" recipe. Agent A owned CHAT-05 (9 files); Agent B owned SIM-04 (7 files). Both landed clean on first `npm run build` — no cherry-picking, no post-agent fixes required. No cross-module import coupling (SIM-04 mirrors IMP-06's magnitude bar visual instead of importing the component, since the impact one takes `Decimal | null` strings and scenarios have `number | null` floats).
  - Commits split cleanly along module boundaries. BUILD.md ticks split across the two commits. HANDOFF folded into SIM-04 (the last commit).
  - Both agents had all API contracts + type shapes + gotchas in-brief, and both leaned on the DATA-06 / REL-07 / IMP-06 / BRIEF-05 patterns already in the tree (Suspense + AuthGuard + dynamic-force, TanStack Query v5 keys, `useSse` hook, Sheet side-panel citation pattern from IMP-06). Extracting `client.ts` in session 40 paid off — no fetch-wrapper duplication this session.

---

## Older last-session snapshots (short)

- **Session 40:** REL-07 + IMP-06 + BRIEF-05 trio via 2 parallel subagents. 8 routes compile. Extracted `lib/api/client.ts`.
- **Session 39:** DATA-06 in-session — first frontend module. 5 routes compile clean.
- **Session 38:** SIM-01 + SIM-03 in-session. 393 passed. Deviations: SSE pseudo-node; presets endpoint bundled into SIM-01's router.
- **Session 37:** CHAT-04 + SIM-02 in parallel via 2 subagents. 383 passed.
- **Session 36:** BRIEF-03 (in-session) + BRIEF-04 & CHAT-03 (parallel). 363 passed.
- **Session 35:** BRIEF-02 + CHAT-02 + EVAL-02 in-session after subagent stall. 335 passed.

---

## _(Below: OLD last-session block preserved for continuity — no longer authoritative.)_

## OLD last session (SIM-01 + SIM-03)

- **Session goal:** Ship SIM-01 (scenario endpoint) + SIM-03 (preset chip list) in-session — both small enough that spawning subagents wasn't worth the coordination cost.
- **Completed:**
  - `SIM-03` ✅ — Curated preset scenarios.
    - `backend/app/agents/scenario/presets.py`: `Preset` frozen dataclass (`id`, `title`, `scenario_text`, `category`). `_PRESETS` tuple of 10 curated scenarios spanning monetary (Fed hikes/cuts, RBI), macro (US recession Q3), commodity (oil to $120), thematic (AI capex boom + slowdown), geopolitical (China stimulus, US tariff escalation), and crypto (spot ETF flows). Each preset has a stable kebab-case `id` so the UI can round-trip selections.
    - Public API: `list_presets() -> list[Preset]` (display order), `get_preset(preset_id) -> Preset | None`.
  - `SIM-01` ✅ — Scenario endpoint + presets endpoint.
    - `backend/app/routes/scenarios.py`:
      - `POST /api/scenarios/simulate` — body `ScenarioSimulateRequest(scenario_text, portfolio_id?)`. If `portfolio_id` is omitted → uses caller's active portfolio; 404 if none. If `portfolio_id` is provided → cross-user check via `_owned_portfolio`; 404 if not caller's (never leak existence). Returns `StreamingResponse(text/event-stream)` with the frames: `node_started` → `node_completed` (duration_ms) → `result` (serialized `ScenarioSimulation`) → `complete`. On runner exception → `error` frame. On runner returning None → `error` frame.
      - `GET /api/scenarios/presets` — authed. Returns the SIM-03 list serialized as dicts (`id`, `title`, `scenario_text`, `category`).
      - Injectable `ScenarioRunnerFn = (user_id, portfolio_id, scenario_text) -> Awaitable[ScenarioSimulation | None]` via `get_scenario_runner`. Default constructs its own session/analogs_store/embed/llm (request-scoped session dies before SSE finishes — same reason CHAT-04's turn runner is self-contained).
    - `backend/app/schemas/scenario.py`: added `ScenarioSimulateRequest(scenario_text: str (1..2000), portfolio_id: UUID | None)`.
    - `backend/app/main.py`: router wired.
    - `backend/tests/routes/test_scenarios.py` — 10 hermetic tests: preset list shape + auth, SSE frame ordering, explicit-portfolio-id honored, no-portfolio 404, cross-user 404, runner-raises → error frame, runner-returns-None → error frame, body length validation (empty + >2000), SIM-03 `get_preset` roundtrip.
- **Acceptance verified locally:**
  - `python -m pytest tests -q` → **393 passed, 5 deselected** (+10 new — a single test file covers both SIM-01 and SIM-03).
  - `ruff check .` clean.
- **Files touched:** created `backend/app/routes/scenarios.py`, `backend/app/agents/scenario/presets.py`, `backend/tests/routes/test_scenarios.py`. Modified `backend/app/schemas/scenario.py` (added `ScenarioSimulateRequest`), `backend/app/main.py` (router include), `BUILD.md` (both ticks), `HANDOFF.md` (this file).
- **Migrations added:** none.
- **Tests added:** 10 hermetic.
- **In-flight work:** none.
- **Deviations from BUILD.md:**
  - **SIM-01 SSE emits a single `simulator` pseudo-node envelope.** Mirrors BRIEF-04's approach — per-node streaming waits on SIM-02 gaining `astream_events` support.
  - **`GET /api/scenarios/presets` bundled into SIM-01** — BUILD.md scopes SIM-03 to `app/agents/scenario/presets.py` only, but the presets need HTTP exposure for the frontend chip UI (SIM-04). Adding the endpoint at SIM-01's router location keeps the concerns local.
  - **`ScenarioSimulateRequest` lives in `schemas/scenario.py`, not the router file** — matches how other request bodies are colocated with their read schemas.
- **Session mechanics recap:** In-session sequential (no subagents). Small pair, small blast radius. Both landed clean on first pytest run.

---

## Prior sessions (short refs)

- **Session 37:** CHAT-04 + SIM-02 parallel via 2 subagents. 383 passed.
- **Session 36:** BRIEF-03 (in-session) + BRIEF-04 & CHAT-03 (parallel). 363 passed.
- **Session 35:** BRIEF-02 + CHAT-02 + EVAL-02 in-session after subagent stall. 335 passed.
- **Session 34:** IMP-05. 293 passed.

---

## Older `## Last session` block preserved below for continuity — no longer authoritative.

## OLD Last session (CHAT-04 + SIM-02 shipment)

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
