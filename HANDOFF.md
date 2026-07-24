# Handoff — Lumen Intelligence Agent

**Branch:** `v2/intelligence-agent`
**Base:** `refactor` (at commit `af39bef` — latest from origin/refactor)
**Last updated:** 2026-07-24 (session 40 — REL-07 + IMP-06 + BRIEF-05 frontend trio via 2 parallel subagents)
**Progress:** 55/60 modules complete (HP-01, HP-02, BOOT-01..BOOT-08, DATA-01..DATA-06, ING-01..ING-10, REL-01..REL-07, IMP-01..IMP-06, GRD-01..GRD-03, BRIEF-01..BRIEF-05, CHAT-01..CHAT-04, SIM-01..SIM-03, EVAL-02). CHAT-05 (chat UI) + SIM-04 (scenario page) are the only remaining frontend modules; DEPLOY-01 + DEPLOY-02 + EVAL-01 + OPT-* still open.

---

## Next module

The five-frontend-page arc from DATA-06 collapsed by three this session; the natural next pair is:

- **CHAT-05** (frontend chat UI) — depends on CHAT-04 (live) + DATA-06 (live). SSE-driven; can reuse `useSse` from BRIEF-05.
- **SIM-04** (frontend scenario page) — depends on SIM-03 (live) + DATA-06 (live). Chip UI over `GET /api/scenarios/presets` + SSE-driven simulate via `POST /api/scenarios/simulate` (also reusable via `useSse`).

Recommended pair: **CHAT-05 + SIM-04** in parallel via 2 subagents. Both consume SSE and both can lean on `hooks/use-sse.ts` (added this session).

**Alternative production tracks (both shippable now — app is a real product with these three pages landing):**
- **DEPLOY-02 (Fly.io backend)** — deploy the FastAPI service so the frontend can talk to a real backend. Highest-value move for a portfolio demo URL.
- **DEPLOY-01 (Vercel frontend)** — with `/onboarding/portfolio`, `/portfolios`, `/portfolios/[id]`, `/news`, `/news/[id]`, `/briefing` all live, the app is thick enough to demo. Chat + scenario pages can follow.

**EVAL-01 (golden dataset labeling)** — still available but is labeling work, not implementation; ask before picking it up.

**Ask the user which direction they want.**

**Branch state:**
- Frontend now has 8 routes: `/`, `/signin`, `/onboarding/portfolio`, `/portfolios`, `/portfolios/[id]`, `/news`, `/news/[id]`, `/briefing`. Every authed page uses the `<Suspense><AuthGuard>…</AuthGuard></Suspense>` + `export const dynamic = "force-dynamic"` shell.
- Shared API scaffolding lives in `frontend/src/lib/api/client.ts` — `apiFetch` (throws on non-2xx), `apiFetchRaw` (return raw Response — needed for IMP-06's 200/202 branch), `openBackendStream` (fetch-driven SSE with Bearer auth — EventSource can't set headers). All four API modules (`portfolios.ts`, `news.ts`, `impact.ts`, `briefings.ts`) route through it.
- New reusable hook: `frontend/src/hooks/use-sse.ts` — manual-start SSE hook wrapping `openBackendStream`; auto-aborts on unmount; handles terminal `complete`/`error` frames; CHAT-05 and SIM-04 can consume this directly.
- Backend untouched.

Before starting, verify:
- `git branch --show-current` (from `.claude/worktrees/v2`) shows `v2/intelligence-agent`.
- `git log --oneline -6` shows this session's commits on top: `BRIEF-05` → `IMP-06` → `REL-07` → `scaffold: lib/api/client.ts` → `DATA-06`.
- `git status` is clean.
- `cd backend && python -m pytest tests -q` reports **393 passed, 5 deselected** (backend unchanged — no need to re-run unless suspicious).
- `cd frontend && NEXT_PUBLIC_BACKEND_URL=http://localhost:8000 NEXT_PUBLIC_SUPABASE_URL=https://example.supabase.co NEXT_PUBLIC_SUPABASE_ANON_KEY=x npm run build && npm run lint` clean (8 routes compile, no lint warnings).

---

## Last session

- **Session goal:** Ship the recommended frontend trio — REL-07 + IMP-06 + BRIEF-05 — via parallel subagents.
- **Completed:**
  - **scaffold** — extracted shared `apiFetch` + `apiFetchRaw` + `openBackendStream` (fetch-driven SSE with Bearer auth) into `frontend/src/lib/api/client.ts`. `portfolios.ts` now imports from it; the three new API modules use it too.
  - `REL-07` ✅ — `/news` feed. Suspense + AuthGuard + `dynamic = "force-dynamic"`. Rows: canonical title, deduped source chips, entity-ticker badges, `ScoreBar` (0..1 → % on a `bg-primary`/`bg-secondary` track), "Analyze impact" affordance gated at `IMPACT_MIN_SCORE = 0.3` with a tooltip explaining the disable. Header shows "Feed for: <active portfolio name>". Empty state handles both "no active portfolio" and "no relevant news yet" via the same copy path (backend returns `[]` for both). Files: `lib/api/news.ts`, `app/news/page.tsx`, `components/news/{feed-row,score-bar,source-chip}.tsx`.
  - `IMP-06` ✅ — `/news/[cluster_id]` detail. Three impact states:
    - Cached (200) → `ImpactCard` with mechanism prose, magnitude bar (fractional Decimals rendered on a fixed -25/+25% axis, "Range not established" when both endpoints null), timeframe pill, confidence bar, falsifiability Alert, citation chips (click → Sheet side panel with the full quote + "Open source" external link), historical-analog cards, `Affects N positions` count, generated-at timestamp, optional Regenerate button.
    - Generating (202) → auto-polling `useClusterImpact` (3s interval, 60s timeout, then fallback message).
    - 404 → explanation + link to `/news`.
    - Files: `lib/api/impact.ts`, `app/news/[id]/page.tsx`, `components/impact/{impact-card,magnitude-bar,citation-panel,analog-card}.tsx`.
  - `BRIEF-05` ✅ — `/briefing`. Three sections (top movers / watchlist / what would change my thinking) rendered as visually distinct groups. Header: portfolio badge + date + "Regenerate" (POST → 1s-interval refetch loop, 15s cap) + "Generate live" (SSE stream via `useSse` → `openBackendStream("/api/briefings/stream")`, updates progressively). Each `BriefingItem` card: cluster title (link — see deviation), one-line summary, `<Collapsible>` mechanism, ticker badges, confidence bar. Empty state: 404 → "no briefing yet — generate one" with a CTA that triggers the SSE. Files: `lib/api/briefings.ts`, `hooks/use-sse.ts`, `app/briefing/page.tsx`, `components/briefing/{briefing-item-card,stream-status}.tsx`.
- **Acceptance verified locally:**
  - `NEXT_PUBLIC_* npm run build` → 9 pages generated, 8 routes (`/news`, `/news/[id]`, `/briefing` added).
  - `NEXT_PUBLIC_* npm run lint` → no ESLint warnings or errors.
  - Backend suite untouched — verified once at session start: **393 passed, 5 deselected**.
- **Files touched:** 4 commits split surgically —
  - `scaffold`: `lib/api/client.ts` (new, 198L), `lib/api/portfolios.ts` (60L → 1L: dropped duplicated fetch helpers, imports from client.ts).
  - `REL-07`: `lib/api/news.ts`, `app/news/page.tsx`, `components/news/{feed-row,score-bar,source-chip}.tsx`, `BUILD.md` tick.
  - `IMP-06`: `lib/api/impact.ts`, `app/news/[id]/page.tsx`, `components/impact/{impact-card,magnitude-bar,citation-panel,analog-card}.tsx`, `BUILD.md` tick.
  - `BRIEF-05`: `lib/api/briefings.ts`, `hooks/use-sse.ts`, `app/briefing/page.tsx`, `components/briefing/{briefing-item-card,stream-status}.tsx`, `BUILD.md` tick, `HANDOFF.md`.
- **Migrations added:** none.
- **Tests added:** none (Playwright still opt-in via `LUMEN_TEST_USER_JWT` from session 39; no new e2e coverage).
- **In-flight work:** none.
- **Deviations from BUILD.md:**
  - **REL-07: no per-portfolio filter.** The `/api/news/relevant` endpoint scopes to the caller's active portfolio and takes no `portfolio_id` param. The page shows "Feed for: <active portfolio name>" instead. Adding a filter would require a backend change.
  - **IMP-06: `affected_positions` rendered as count, not tickers.** The impact table stores position UUIDs and has no ticker join; the mechanism paragraph already names positions inline. Cheap follow-up: add `positions` (joined) to `ImpactRead`.
  - **BRIEF-05: `BriefingItem` title link points to `/news` (feed), not `/news/[cluster_id]`.** The briefing schema exposes `impact_id` but not `cluster_id`, so we can't route to the detail page. Tooltip on the title explains this. Fix: add `cluster_id` to `BriefingItem` in a follow-up.
  - **`news.ts`'s `ClusterDetailRead.impact` is typed `unknown`** to avoid a cross-module import from `impact.ts`. The detail page reads impact via `useClusterImpact` (impact.ts) separately, so no consumer is affected. Documented inline.
  - **`ImpactCard`'s magnitude bar uses a fixed -25%/+25% axis.** Not spec'd — chosen so the bar has a stable visual meaning across different assessments. Values outside that range clip visually (the numeric label still shows the true value).
- **Session mechanics recap:**
  - Two parallel subagents, per HANDOFF's "safer than 3" recipe. Agent A owned REL-07 + IMP-06 (news arc); Agent B owned BRIEF-05 (SSE hook + briefing page). Both landed clean on first build.
  - Pre-flight scaffolding (`client.ts` + `portfolios.ts` refactor) done in-session before spawning agents — the shared `apiFetch` / SSE helpers are needed by every downstream module so extracting them once removes coordination cost.
  - Post-agent: `news.ts` had a `import type { ImpactRead } from "@/lib/api/impact"` — coupled REL-07 and IMP-06 at compile time, so REL-07 wouldn't build in isolation. Fixed by loosening `ClusterDetailRead.impact: ImpactRead | null` → `impact: unknown` (the detail page reads impact from `useClusterImpact`, never from `useClusterDetail`, so the type was dead weight). Now each commit is standalone-buildable — bisect-clean.
  - Commits split into 4 surgical drops (scaffold + REL-07 + IMP-06 + BRIEF-05) with BUILD.md ticks in the module commits they belong to and HANDOFF folded into the BRIEF-05 commit.

---

## Older last-session snapshots (short)

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
