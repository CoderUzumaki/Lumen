# Lumen Intelligence Agent — Build Plan

**Companion to `PRD.md`.** Every module below is scoped so a fresh Claude Code session can start it from cold with only this document + the referenced files as context.

---

## How to use this document

1. **One module per Claude Code session** is ideal. Hand Claude the module ID and paste the module block into the prompt.
2. Each module has a stable ID (e.g., `ING-01`). Reference it in commits and PRs: *"Implement `ING-01` per BUILD.md."*
3. **Sequencing matters.** Every module lists `Depends on` — do not start a module before its deps are marked done.
4. **A module is done** only when every line under `Acceptance` is satisfied. Mark inline: `- [ ]` → `- [x]`, and add a one-line deviation note if reality diverged from the spec.
5. If a module grows beyond ~1 day of work, split it before starting. Add a new entry with the next free ID in that phase.

---

## Branching strategy

- **Base branch:** `refactor` (contains the latest completed work from the discarded trajectory — Phase 0 hygiene, Phase 1 config, Phase 2 backend auth, initial frontend auth). Frozen going forward.
- **New product branch:** `v2/intelligence-agent`. Cut once from `refactor` at the start of Phase 0. All work lands here.
  ```
  git checkout refactor
  git pull origin refactor
  git checkout -b v2/intelligence-agent
  git push -u origin v2/intelligence-agent
  ```
- **Feature branches:** `feat/<module-id>` off `v2/intelligence-agent` per module. Merge back with squash.
- **Do not** rebase or merge `v2/intelligence-agent` back to `refactor` or `main` until v1.0 ships. `refactor` is preserved as the "before" state for the resume story.
- The old `TODO.md` at repo root stays untouched — it belongs to the discarded trajectory and is preserved for historical reference. Do not delete it.

---

## Global conventions

These apply to every module. Do not restate them per module unless a module deviates.

### Code layout

```
/backend
  /app
    /agents               # LangGraph agent definitions
    /pipelines            # Ingestion pipelines
    /tools                # Tool functions callable by agents
    /schemas              # Pydantic models (request/response/domain)
    /db                   # SQLAlchemy models, Alembic migrations
    /routes               # FastAPI routers
    /guardrails           # Output validators
    /evals                # Eval datasets, runners
    /utils                # Shared utilities (logging, auth, config)
    main.py               # FastAPI entrypoint
  /tests
  requirements.txt
  pyproject.toml
  alembic.ini

/frontend
  /src
    /app                  # Next.js App Router pages
    /components
    /lib
      /api                # API client
      /supabase           # Supabase client
      /agents             # frontend-side agent helpers (streaming, SSE)
    /hooks
  package.json
  next.config.ts

PRD.md
BUILD.md
README.md                 # regenerated in DEPLOY-06
```

### Error envelope

Every backend response uses this envelope:

```json
{
  "data": <T> | null,
  "error": { "code": "string", "message": "string", "details"?: <any> } | null
}
```

- 2xx → `data` populated, `error` null.
- 4xx/5xx → `data` null, `error` populated.
- Error codes are stable strings: `unauthorized`, `forbidden`, `not_found`, `validation_error`, `rate_limited`, `guardrail_violation`, `upstream_failure`, `internal_error`.

### Auth

Every `/api/*` route requires `Authorization: Bearer <supabase_jwt>`. Verified via `require_auth` dependency (ported from current `backend/utils/auth.py` in Phase 0). Health endpoints and `/api/eval/latest` (public metrics page) are exempt.

### Structured logging

- Backend: `structlog` with JSON output. Every log line includes `request_id`, `user_id` (if auth'd), `route`, `module`.
- Frontend: keep existing `lib/logger.ts` (debug/info no-op in prod).

### LLM invocation — free-tier constrained

**Cost constraint: everything runs on free tiers or self-hosted.** This shapes every model choice, provider choice, and rate-limit strategy.

All LLM calls go through a single wrapper `backend/app/utils/llm.py` that:
- Reads model tier from user preferences (`fast` = free small model, `thorough` = free large model).
- Uses OpenRouter's free-tier models (see `LLM_TEXT_MODEL_FAST` / `LLM_TEXT_MODEL_THOROUGH` env vars). Defaults chosen at BOOT-06 based on current OpenRouter free-tier availability — verify at implementation time and pin the current best.
- Emits traces to LangSmith **or** self-hosted Langfuse (whichever is configured; Langfuse is the free fallback if LangSmith's 5k-trace/mo free tier is exhausted).
- Enforces **request-per-minute rate limits** (not a $ ceiling — everything is free). Free-tier OpenRouter models are typically capped at 20 RPM per model. Wrapper maintains a per-model token bucket and queues requests when saturated.
- Handles retry with exponential backoff on 5xx / rate-limit errors (`tenacity`).
- Records prompt tokens, completion tokens, model, latency, and cache-hit status to `llm_calls` table (see OPT-05) for benchmarking.

No route or agent calls LiteLLM / Anthropic / OpenAI SDK directly. Everything goes through `llm.py`.

**Model selection at time of writing** (verify current availability at BOOT-06):
- Fast tier candidates (~7B–70B params, low latency): `meta-llama/llama-3.3-70b-instruct:free`, `google/gemini-2.0-flash-exp:free`, `nvidia/nemotron-nano-9b-v2:free`, `mistralai/mistral-small-3.1-24b-instruct:free`.
- Thorough tier candidates (strong reasoning): `deepseek/deepseek-chat-v3.1:free`, `nvidia/llama-3.3-nemotron-super-49b-v1:free`, `qwen/qwen-3-235b-a22b:free`, `deepseek/deepseek-r1:free` (has reasoning trace).
- If free-tier availability degrades, fall back to paid Haiku 4.5 as a documented last resort (add a per-user daily $ soft cap of $0.20 at that point).

### Testing

- Every phase has at least one test file under `backend/tests/`.
- `pytest` runs against an in-memory SQLite for unit; against a docker-composed Postgres for integration (CI only).
- Frontend tests: `vitest` for units, Playwright for the onboarding smoke test.

### Design system — modern, dense, financial-tool serious

Every UI decision defers to this system. If a component doesn't compose cleanly with these tokens, that's a bug.

**Overall aesthetic:** dark-first, high-contrast, dense but not cramped. References: Linear, Vercel dashboard, Perplexity's finance pages, Cursor. Avoid: gradients, glassmorphism, playful color, rounded-3xl cards. This tool is for money — it should feel serious.

**Typography:**
- Body + UI: **Geist Sans** (Vercel's font, MIT-licensed, self-host via `next/font/local`).
- Numeric + code + citations: **Geist Mono**. All prices, percentages, magnitude ranges render in Geist Mono with `tabular-nums`.
- Type scale (rem): `text-xs 0.75`, `text-sm 0.875`, `text-base 1`, `text-lg 1.125`, `text-xl 1.25`, `text-2xl 1.5`, `text-3xl 1.875`, `text-4xl 2.25`. No H1 above `text-4xl` — this isn't a marketing site inside the app.
- Body line-height: 1.6. Headings: 1.2. Numeric: 1 (tight).

**Color palette (CSS custom properties, defined in `app/globals.css`):**
```css
:root[data-theme="dark"] {
  --bg-base:      #0a0a0a;   /* page background */
  --bg-surface:   #111111;   /* cards, panels */
  --bg-elevated:  #171717;   /* modals, popovers */
  --border-subtle:#1f1f1f;
  --border-strong:#2a2a2a;
  --text-primary: #fafafa;
  --text-secondary:#a3a3a3;
  --text-muted:   #737373;

  /* Semantic — outcome mapping, not stock direction */
  --confirmed:    #10b981;   /* emerald 500 — prediction confirmed */
  --refuted:      #f43f5e;   /* rose 500 — prediction refuted */
  --partial:      #f59e0b;   /* amber 500 — partial confirmation */
  --neutral:      #6366f1;   /* indigo 500 — inconclusive */

  /* Accents — used sparingly */
  --accent:       #ffffff;   /* primary CTA, white on black */
  --accent-fg:    #0a0a0a;
  --focus-ring:   #3b82f6;   /* blue 500 */
}
:root[data-theme="light"] {
  /* Inverse mapping; ship in v0.2 or later. Dark is the default for MVP. */
}
```
- **Never** use raw hex in components. Always via CSS var → Tailwind arbitrary value: `bg-[var(--bg-surface)]`.
- Tailwind config maps these to semantic names: `bg-surface`, `text-primary`, `border-subtle`, `text-confirmed`, etc.

**Layout & spacing:**
- 12-column grid, max content width `1440px`, gutters `24px` desktop / `16px` mobile.
- App shell: fixed left sidebar (240px), main content (fluid), optional right rail (360px).
- Section rhythm: `space-y-16` between major sections, `space-y-8` between subsections, `space-y-4` between items.
- Never nest cards more than 2 deep. Card padding: `p-6` default, `p-8` for hero cards.

**Component conventions:**
- Border radius: `rounded-lg` (8px) default, `rounded-xl` (12px) for cards, `rounded-full` for chips/pills. Nothing above `rounded-xl`.
- Border: `1px solid var(--border-subtle)`. Focus: `1px solid var(--focus-ring)` + `ring-2 ring-focus-ring/20`.
- Shadow: **none by default.** Elevation via background color, not drop shadow. This is the biggest departure from typical dashboards; keep discipline.
- Numbers: `font-mono tabular-nums`. Percentages get sign (`+2.3%` / `-1.7%`) colored by outcome semantics, not by up/down (we're not making predictions).
- Icons: `lucide-react`, size `16px` inline / `20px` standalone. Never emoji in production UI.
- Motion: **subtle and functional.** Enter transitions `150ms ease-out`, hover states `100ms`. Framer Motion only for the SSE streaming reveal on the briefing page. Zero decorative animation.

**Component library:** `shadcn/ui` (already in repo). When adding a new primitive, take it from shadcn/Radix — do not hand-roll dropdowns, dialogs, tooltips.

**Empty states are a first-class UI concern.** Every list/table/feed has a designed empty state with an icon (from lucide), a one-line explanation, and a primary CTA. Never a blank page.

**Loading states:** skeleton components matching the shape of the incoming content. No spinners inside content areas — spinners only at the app-shell level (auth resolution).

**Streaming states:** for SSE endpoints (briefing generation, chat), render content progressively. A subtle 2px pulsing left border on the streaming block distinguishes it from static content.

**Accessibility (mandatory, not aspirational):**
- All interactive elements keyboard-navigable; focus rings visible.
- Color contrast: WCAG AA minimum (4.5:1 for body text).
- Semantic HTML: `<button>` not `<div onclick>`.
- Screen-reader labels on icon-only buttons.

**Design system module:** DESIGN-01 (below) formalizes the token file, Tailwind config, and a Storybook page proving the primitives.

---

## Post-v1.0 backlog (out of current scope)

Anything the user or a future session proposes that isn't in this document goes here. Do not merge features into a phase without a PRD amendment.

- Bank feed / Plaid ingest
- Mobile app
- Brokerage integration / trading
- Tax modules
- Community / sharing features
- Multi-user workspaces / RBAC
- Options and derivatives
- Live intraday price streaming

---

# Phase 0 — Repository & Branch Bootstrap

Goal: get from the current Flask + invoice-OCR trajectory to a clean FastAPI + agent-ready foundation. No product functionality yet.

### BOOT-01 — Cut the `v2/intelligence-agent` branch and prune legacy ✅

- **Files:** everything under `backend/` except `backend/config.py`, `backend/utils/auth.py`, `backend/utils/logging_config.py`, `backend/.gitignore`. Everything under `frontend/src/` except `lib/supabase/*`, `components/auth/*`, `app/signin/*`, `app/layout.tsx`, `middleware.ts` (if any), and truly generic UI primitives under `components/ui/`.
- **Action:**
  1. From `main`, cut `v2/intelligence-agent`. All subsequent work is on this branch.
  2. Delete all invoice-related backend routes (`ocr.py`, `batch.py`, `chat.py`, `analytics.py`, `ai_analytics.py`, `database_query.py`, `email_config.py`).
  3. Delete `backend/ai/*` (old orchestrator, forecasting, classifier, sql_agent, rag_system, anomaly, risk, pattern).
  4. Delete `backend/scripts/*` except `__init__.py`.
  5. Delete `backend/chroma_db/*` (stale index).
  6. Delete all frontend pages: `app/dashboard/*`, `app/chatbot/*`, `app/analytics/*`, `app/ai-analytics/*`, `app/landing/*`.
  7. Delete related components: everything under `components/ai-analytics/`, `components/analytics/`, `components/chatbot/`, `components/landing/`, `components/uploadDialog.tsx`, `components/section-cards.tsx`, `components/animatedListItemUse.tsx`.
  8. Keep `PRD.md`, `BUILD.md`, `.gitignore`, `LICENSE`, `README.md` (will be rewritten in DEPLOY-06). Delete the other markdown docs (`ARCHITECTURE.md`, `API_DOCS.md`, `CHATBOT_INTEGRATION.md`, `DEMO_VIDEO_GUIDE.md`, `DEPLOYMENT.md`, `DOCUMENTATION_COMPLETE.md`, `DOCUMENTATION_INDEX.md`, `PROBLEM_STATEMENT.md`, `QUICK_START.md`, `SETUP.md`) — they describe the discarded trajectory. Keep `TODO.md` untouched per branching-strategy note.
- **Acceptance:**
  - `git ls-tree -r HEAD --name-only backend | wc -l` shows under 15 files (config, auth util, logging util, .gitignore, `app/` scaffold, `requirements.txt`, `alembic.ini`, `pyproject.toml`).
  - `git ls-tree -r HEAD --name-only frontend/src` shows under 30 files (auth + supabase + layout + signin + ui primitives).
  - `git log --oneline v2/intelligence-agent..main` is empty (no missed commits).
- **Depends on:** none.

### BOOT-02 — FastAPI scaffolding ✅

- **Files:** `backend/app/main.py`, `backend/app/__init__.py`, `backend/pyproject.toml`, `backend/requirements.txt`, `backend/alembic.ini`, `backend/app/db/base.py`.
- **Action:**
  1. New `pyproject.toml` declaring Python 3.11+, package name `lumen-backend`.
  2. `requirements.txt` (versions pinned):
     ```
     fastapi==0.115.0
     uvicorn[standard]==0.32.0
     pydantic==2.9.2
     pydantic-settings==2.5.2
     sqlalchemy[asyncio]==2.0.35
     asyncpg==0.29.0
     alembic==1.13.3
     structlog==24.4.0
     httpx==0.27.2
     python-jose[cryptography]==3.3.0
     PyJWT[crypto]==2.9.0
     supabase==2.9.1
     langgraph==0.2.34
     langchain==0.3.3
     langchain-openai==0.2.2
     langsmith==0.1.135
     langfuse==2.53.0
     chromadb==0.5.11
     sentence-transformers==3.2.1
     apscheduler==3.10.4
     tenacity==9.0.0
     python-dotenv==1.0.1
     yfinance==0.2.44
     feedparser==6.0.11
     selectolax==0.3.24
     ```
     (Pin these exact versions. Later phases may add.)
     - `sentence-transformers` for local embeddings (see ING-07 — replaces paid OpenAI embeddings).
     - `langfuse` as the free self-hostable trace backend, alongside `langsmith` (whichever is configured wins).
     - `langchain-anthropic` intentionally removed — we route Anthropic-family models through OpenRouter via `langchain-openai` (OpenAI-compatible protocol).
  3. `main.py` creates a FastAPI app with:
     - CORS middleware reading `ALLOWED_ORIGINS` from config.
     - A `request_id` middleware (attach a UUID per request, log it, return as `X-Request-ID`).
     - Exception handlers producing the error envelope for `HTTPException`, `ValidationError`, and generic `Exception`.
     - Startup event: `Config.validate()` + structured logging init + LangSmith init if configured.
     - Register `GET /health` returning `{"status": "ok", "commit": "<sha>"}`.
  4. `alembic.ini` + `backend/app/db/base.py` with async SQLAlchemy engine.
- **Acceptance:**
  - `uvicorn app.main:app --reload` starts cleanly.
  - `curl localhost:8000/health` returns 200 with the envelope.
  - `alembic revision --autogenerate -m "init"` produces an empty migration (no models yet).
- **Depends on:** BOOT-01.

### BOOT-03 — Port `Config` and auth utilities ✅

- **Files:** `backend/app/utils/config.py`, `backend/app/utils/auth.py`, `backend/app/utils/logging_config.py`.
- **Action:**
  1. Port the current `backend/config.py` verbatim into `backend/app/utils/config.py`, then strip everything invoice/OCR-related (`LLM_VISION_MODEL`, OCR endpoints, ChromaDB paths that reference the old collection).
  2. Add the new required env vars (see §Environment variables below).
  3. Port `backend/utils/auth.py` → `backend/app/utils/auth.py`. Change signature from Flask decorator to FastAPI dependency:
     ```python
     async def require_auth(request: Request) -> UserContext: ...
     ```
     `UserContext` is a Pydantic model with `user_id: UUID`, `email: str`, `role: str`.
  4. Port `logging_config.py` unchanged.
- **Acceptance:**
  - `from app.utils.auth import require_auth` importable.
  - A protected route `GET /api/me` returning `{"user_id": ...}` works with a real Supabase JWT and returns 401 without.
  - `Config.validate()` fails startup if any required env var missing.
- **Depends on:** BOOT-02.

### BOOT-04 — Frontend scaffolding reset ✅

- **Files:** `frontend/src/app/layout.tsx`, `frontend/src/app/page.tsx`, `frontend/src/app/globals.css`, `frontend/next.config.ts`, `frontend/package.json`.
- **Action:**
  1. `app/page.tsx` becomes a marketing landing (placeholder text OK — will be finished in DEPLOY-05).
  2. `app/layout.tsx` keeps `AuthProvider`, adds `QueryClientProvider` (TanStack Query), `ThemeProvider` (existing).
  3. Strip unused package.json dependencies (chart libs used by old analytics, etc). Keep: next, react, react-dom, @supabase/supabase-js, @tanstack/react-query, tailwindcss, lucide-react, class-variance-authority, clsx, radix-ui/* (whatever is actually referenced by kept components), zod.
  4. Add: `@tanstack/react-query`, `react-markdown` (for chat rendering), `eventsource-parser` (for SSE), `date-fns`.
- **Acceptance:**
  - `npm run build` in `frontend/` succeeds with zero warnings related to missing modules.
  - `/` renders a plain landing page.
  - `/signin` still works (existing auth flow untouched).
- **Depends on:** BOOT-01.

### BOOT-05 — Supabase database bootstrap + Alembic wiring ✅

- **Files:** `backend/app/db/base.py`, `backend/alembic/env.py`.
- **Action:**
  1. Configure `DATABASE_URL` env var to accept a Supabase Postgres connection string. Local dev fallback: `postgresql+asyncpg://postgres:postgres@localhost:5432/lumen`.
  2. Alembic uses the async engine but with a sync driver for migrations (Alembic's constraint) — use `psycopg2` as migration driver, `asyncpg` at runtime.
  3. Base `SQLAlchemy` declarative class with:
     - `id: Mapped[UUID]` primary key (default `uuid.uuid4`).
     - `created_at: Mapped[datetime]` server_default `now()`.
     - `updated_at: Mapped[datetime]` server_default `now()` with `onupdate=now()`.
  4. `alembic upgrade head` creates only the tracking table (no models yet).
- **Acceptance:**
  - Local Postgres: `alembic upgrade head` succeeds and creates `alembic_version`.
  - Supabase Postgres: same.
- **Depends on:** BOOT-02.

### BOOT-06 — LLM wrapper (free-tier) ✅

- **Files:** `backend/app/utils/llm.py`, `backend/app/utils/tracing.py`, `backend/app/utils/rate_limit.py`.
- **Action:**
  1. `LLMClient` class exposing:
     ```python
     async def complete(
         messages: list[Message],
         *,
         tier: Literal["fast", "thorough"] = "thorough",
         response_model: type[BaseModel] | None = None,
         max_tokens: int = 1024,
         temperature: float = 0.2,
         user_id: UUID | None = None,
         cache_key: str | None = None,
     ) -> LLMResponse:
     ```
     - Routes to the model configured in `LLM_TEXT_MODEL_FAST` / `LLM_TEXT_MODEL_THOROUGH` env vars via OpenRouter (OpenAI-compatible endpoint at `https://openrouter.ai/api/v1/chat/completions`).
     - Before implementation, verify each configured model currently exists on OpenRouter's free tier at `/api/v1/models`; if any fails a live probe, log a warning and continue with the fallback model.
     - If `response_model` given, forces structured JSON output (either via `response_format={"type": "json_object"}` if supported by the target model, or via prompt-embedded JSON schema instructions with a Pydantic validator + retry loop) and validates.
     - If `cache_key` given, checks the semantic cache table first (see OPT-05); returns cached result on hit.
     - Retries 3x on 5xx, 429, or JSON parse failure with exponential backoff (`tenacity`).
     - Rate-limits: consults per-model token buckets from `rate_limit.py`. Free-tier defaults: 20 RPM per model. On saturation, queues the call (bounded queue of 100; over that, raises `RateLimitedExceeded`).
     - Emits trace via `tracing.py`: LangSmith if `LANGSMITH_API_KEY` set, Langfuse if `LANGFUSE_PUBLIC_KEY` set, otherwise no-op.
     - Records the call to the `llm_calls` table (OPT-05) for benchmarking: `{model, tier, prompt_tokens, completion_tokens, latency_ms, cache_hit, user_id, agent_name}`.
  2. `EmbeddingClient` — thin wrapper. **Uses local `sentence-transformers` via ING-07**, NOT a paid API. Kept here only for import ergonomics.
  3. `tracing.py` — initializes whichever trace backend is configured. Trace context propagates via `contextvars` so every downstream LLM call inherits the parent run.
  4. `rate_limit.py` — in-process token buckets keyed by `model_id`. Configurable via `LLM_RATE_LIMIT_RPM` env var (JSON: `{"deepseek/deepseek-chat-v3.1:free": 20, ...}`).
- **Acceptance:**
  - `pytest backend/tests/utils/test_llm.py` covers: happy path (mocked httpx), retry-on-5xx, JSON-parse failure retry, rate-limit backoff triggers, semantic cache hit skips network call.
  - A hitting run against real OpenRouter (behind an integration test marker `@pytest.mark.free_tier_live`) returns a valid response for both `fast` and `thorough` tiers.
  - `llm_calls` table receives a row for every non-cached invocation.
- **Depends on:** BOOT-03, BOOT-05, OPT-05 (schema — implement OPT-05 first as a bare table, wire the cache logic later).

### BOOT-07 — Environment variables consolidated ✅

- **Files:** `backend/.env.example`, `frontend/.env.example`.
- **Action:** Write both `.env.example` files with every variable Lumen ever reads. Group logically. Include a one-line description per var. See §Environment variables at the bottom of this document for the authoritative list.
- **Acceptance:**
  - `cp .env.example .env && python -c "from app.utils.config import Config; Config.validate()"` succeeds if `.env` is filled in.
  - Every required var in `Config` appears in `.env.example`.
- **Depends on:** BOOT-03.

### BOOT-08 — CI baseline ✅

- **Files:** `.github/workflows/ci.yml`.
- **Action:**
  - On every PR + push to `v2/intelligence-agent`:
    - Backend job: `pip install -r requirements.txt && ruff check && pytest`.
    - Frontend job: `npm ci && npm run lint && npm run build && npm test`.
  - Post-build: LangSmith eval regression job (skipped until EVAL-04 lands).
- **Acceptance:** PR checks show green on a trivial change.
- **Depends on:** BOOT-02, BOOT-04.

---

# Phase 1 — Portfolio & User Data Model

Everything a user configures about themselves. Nothing agentic yet.

### DATA-01 — Migration: user_preferences, portfolios, positions, themes ✅

- **Files:** `backend/app/db/models/*.py`, new Alembic migration `alembic/versions/xxxx_phase1_data.py`.
- **Action:** Create SQLAlchemy models matching this schema exactly:

  ```sql
  CREATE TABLE user_preferences (
    user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    briefing_hour INTEGER NOT NULL DEFAULT 8 CHECK (briefing_hour BETWEEN 0 AND 23),
    briefing_timezone TEXT NOT NULL DEFAULT 'UTC',
    display_currency TEXT NOT NULL DEFAULT 'USD',
    model_tier TEXT NOT NULL DEFAULT 'thorough' CHECK (model_tier IN ('fast','thorough')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
  );

  CREATE TABLE portfolios (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, name)
  );
  CREATE INDEX idx_portfolios_user_id ON portfolios (user_id);
  CREATE UNIQUE INDEX idx_portfolios_user_active
    ON portfolios (user_id) WHERE is_active = TRUE;

  CREATE TABLE positions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_id UUID NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    ticker TEXT NOT NULL,
    asset_type TEXT NOT NULL DEFAULT 'equity'
      CHECK (asset_type IN ('equity','etf','crypto','bond','other')),
    quantity NUMERIC(20, 8),
    cost_basis NUMERIC(20, 8),
    currency TEXT NOT NULL DEFAULT 'USD',
    exchange TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (portfolio_id, ticker, exchange)
  );
  CREATE INDEX idx_positions_portfolio_id ON positions (portfolio_id);
  CREATE INDEX idx_positions_ticker ON positions (ticker);

  CREATE TABLE themes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    description TEXT NOT NULL,
    weight NUMERIC(3, 2) NOT NULL DEFAULT 1.0 CHECK (weight BETWEEN 0 AND 1),
    embedding_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
  );
  CREATE INDEX idx_themes_user_id ON themes (user_id);
  ```

- **Acceptance:**
  - `alembic upgrade head` succeeds.
  - `alembic downgrade -1 && alembic upgrade head` is a no-op.
  - `pytest backend/tests/db/test_models.py::test_phase1_schema` inserts rows, hits every CHECK constraint, verifies cascade delete.
- **Depends on:** BOOT-05.

### DATA-02 — Pydantic schemas for portfolio/positions/themes ✅

- **Files:** `backend/app/schemas/portfolio.py`, `backend/app/schemas/theme.py`, `backend/app/schemas/preferences.py`.
- **Action:** Define request and response Pydantic v2 models. Naming: `PortfolioCreate`, `PortfolioUpdate`, `PortfolioRead`, and so on. `PortfolioRead` embeds `positions: list[PositionRead]`. Validation:
  - Ticker: `^[A-Z0-9.\-:]{1,20}$` (upper-cased, dots and hyphens allowed for BRK.B, futures).
  - Currency: ISO 4217 uppercase.
  - Theme description: 3–200 chars.
  - Weight: 0.0–1.0.
- **Acceptance:**
  - `pytest backend/tests/schemas/test_portfolio.py` covers valid + invalid cases per field.
- **Depends on:** DATA-01.

### DATA-03 — Portfolio & positions routes ✅

- **Files:** `backend/app/routes/portfolios.py`, `backend/app/routes/positions.py`.
- **Action:** Implement CRUD endpoints:

  ```
  POST   /api/portfolios                          body: PortfolioCreate    → PortfolioRead
  GET    /api/portfolios                          → list[PortfolioRead]
  GET    /api/portfolios/{id}                     → PortfolioRead
  PUT    /api/portfolios/{id}                     body: PortfolioUpdate    → PortfolioRead
  DELETE /api/portfolios/{id}                     → 204
  POST   /api/portfolios/{id}/activate            → PortfolioRead (unique-active constraint enforced)

  POST   /api/portfolios/{id}/positions           body: PositionCreate     → PositionRead
  GET    /api/portfolios/{id}/positions           → list[PositionRead]
  PUT    /api/positions/{position_id}             body: PositionUpdate     → PositionRead
  DELETE /api/positions/{position_id}             → 204
  ```

  Every route resolves `user_id` from `require_auth`, scopes queries to owner, returns 404 (not 403) on cross-user access to avoid leaking existence.

- **Acceptance:**
  - `pytest backend/tests/routes/test_portfolios.py`:
    - Owner CRUD works.
    - Cross-user access returns 404.
    - `POST /portfolios/{id}/activate` deactivates any previous active.
    - Ticker validation errors return 400 with `validation_error` code.
- **Depends on:** DATA-01, DATA-02, BOOT-03.

### DATA-04 — Themes routes ✅

- **Files:** `backend/app/routes/themes.py`.
- **Action:** Implement CRUD:

  ```
  POST   /api/themes                              body: ThemeCreate        → ThemeRead
  GET    /api/themes                              → list[ThemeRead]
  PUT    /api/themes/{id}                         body: ThemeUpdate        → ThemeRead
  DELETE /api/themes/{id}                         → 204
  ```

  On create/update, generate an embedding for `description` via `EmbeddingClient` and store the vector in the `themes` collection in Chroma (see ING-07). Persist the Chroma doc id in `themes.embedding_id`.

- **Acceptance:**
  - Owner CRUD works; cross-user access returns 404.
  - Creating a theme results in a Chroma doc with matching id.
  - Deleting a theme deletes the Chroma doc.
- **Depends on:** DATA-01, DATA-02, ING-07.

### DATA-05 — User preferences route ✅

- **Files:** `backend/app/routes/me.py`.
- **Action:**

  ```
  GET  /api/me                          → { user_id, email, preferences: UserPreferencesRead }
  PUT  /api/me/preferences              body: UserPreferencesUpdate       → UserPreferencesRead
  ```

  `GET /api/me` auto-creates the `user_preferences` row on first hit if missing.

- **Acceptance:**
  - First `GET /api/me` after signup returns defaults.
  - `PUT` updates persist and validate (briefing_hour in range, tier in enum).
- **Depends on:** DATA-01, DATA-02.

### DATA-06 — Frontend portfolio setup UI

- **Files:** `frontend/src/app/onboarding/portfolio/page.tsx`, `frontend/src/app/portfolios/page.tsx`, `frontend/src/app/portfolios/[id]/page.tsx`, `frontend/src/lib/api/portfolios.ts`.
- **Action:**
  1. `api/portfolios.ts`: typed client for the endpoints above using TanStack Query.
  2. `/onboarding/portfolio`: single-page form. Shows a "Load sample portfolio" button that seeds AAPL, MSFT, NVDA, GOOGL, VOO, BND (a plausible tech-heavy portfolio for demo). Manual entry: add rows with ticker + optional quantity + currency + exchange.
  3. `/portfolios`: list view. Each portfolio card shows name, position count, active badge, edit/delete buttons.
  4. `/portfolios/[id]`: detail view. Positions table with inline edit.
  5. Redirects: if user has zero portfolios, `/portfolios` redirects to `/onboarding/portfolio`.
- **Acceptance:**
  - Fresh user completes onboarding form and lands on `/briefing` (placeholder for now).
  - CRUD works end-to-end against local backend.
  - Playwright test `frontend/e2e/onboarding.spec.ts` covers the sample-portfolio path.
- **Depends on:** DATA-03, DATA-05, BOOT-04.

---

# Phase 2 — News Ingestion Pipeline

Continuous background pipeline. Five sources, one normalized schema, deduped into clusters, embedded, stored.

### ING-01 — News schemas + `news_items` and `news_clusters` migration ✅

- **Files:** `backend/app/db/models/news.py`, `backend/app/schemas/news.py`, new Alembic migration.
- **Action:**

  ```sql
  CREATE TABLE news_clusters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_title TEXT NOT NULL,
    canonical_summary TEXT,
    first_seen_at TIMESTAMPTZ NOT NULL,
    last_seen_at TIMESTAMPTZ NOT NULL,
    entity_tickers TEXT[] NOT NULL DEFAULT '{}',
    entity_topics TEXT[] NOT NULL DEFAULT '{}',
    authority_score NUMERIC(3, 2) NOT NULL DEFAULT 0.5,
    novelty_score NUMERIC(3, 2) NOT NULL DEFAULT 1.0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
  );
  CREATE INDEX idx_news_clusters_first_seen ON news_clusters (first_seen_at DESC);
  CREATE INDEX idx_news_clusters_entity_tickers ON news_clusters USING GIN (entity_tickers);

  CREATE TABLE news_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cluster_id UUID REFERENCES news_clusters(id) ON DELETE SET NULL,
    source TEXT NOT NULL
      CHECK (source IN ('newsapi','marketaux','gdelt','edgar','rss')),
    source_id TEXT,
    url TEXT NOT NULL,
    url_hash TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    body TEXT,
    published_at TIMESTAMPTZ NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    raw_payload JSONB
  );
  CREATE INDEX idx_news_items_cluster ON news_items (cluster_id);
  CREATE INDEX idx_news_items_published ON news_items (published_at DESC);

  CREATE TABLE ingest_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ,
    items_fetched INTEGER,
    items_new INTEGER,
    items_deduped INTEGER,
    error TEXT
  );
  CREATE INDEX idx_ingest_runs_source_started ON ingest_runs (source, started_at DESC);
  ```

  Pydantic:
  ```python
  class NewsItemIn(BaseModel):
      source: Literal["newsapi","marketaux","gdelt","edgar","rss"]
      source_id: str | None
      url: HttpUrl
      title: str
      body: str | None
      published_at: datetime
      raw_payload: dict

  class NewsClusterRead(BaseModel):
      id: UUID
      canonical_title: str
      canonical_summary: str | None
      first_seen_at: datetime
      last_seen_at: datetime
      entity_tickers: list[str]
      entity_topics: list[str]
      authority_score: float
      novelty_score: float
      items: list[NewsItemRead]
  ```

- **Acceptance:** migration up/down clean, unique constraint on `url_hash` prevents duplicate inserts.
- **Depends on:** BOOT-05.

### ING-02 — NewsAPI adapter ✅

- **Files:** `backend/app/pipelines/sources/newsapi.py`.
- **Action:**
  1. Adapter class `NewsAPISource(BaseSource)` implementing `async fetch(since: datetime) -> list[NewsItemIn]`.
  2. Query params: `q="finance OR markets OR stocks OR fed OR earnings"`, `language=en`, `sortBy=publishedAt`, `pageSize=100`, `from=<since ISO8601>`.
  3. Handle 429 by respecting `X-RateLimit-Reset`, back off with `tenacity`.
  4. On empty API key: log a warning and return `[]` (never raise — free tier optional).
  5. `source_id` = NewsAPI's `id` field if present, else null.
- **Acceptance:**
  - Unit test with mocked httpx returns 3 items, all mapped correctly.
  - Missing API key → empty list, no exception.
  - 429 response is retried with backoff.
- **Depends on:** ING-01, BOOT-06.

### ING-03 — Marketaux adapter ✅

- **Files:** `backend/app/pipelines/sources/marketaux.py`.
- **Action:** `MarketauxSource` — same shape as NewsAPI. Endpoint: `https://api.marketaux.com/v1/news/all?filter_entities=true&language=en&limit=50&published_after=<since>`. Extract `entities[].symbol` into a `hints_tickers: list[str]` field on the `NewsItemIn` (a new optional field — add it to the schema in ING-01 as `hints: dict = {}` for extensibility).
- **Acceptance:** unit tests pass; hints_tickers populated from Marketaux response.
- **Depends on:** ING-01.

### ING-04 — GDELT adapter ✅

- **Files:** `backend/app/pipelines/sources/gdelt.py`.
- **Action:** GDELT's DOC 2.0 API. Query URL pattern:
  ```
  https://api.gdeltproject.org/api/v2/doc/doc
    ?query=(finance OR markets OR stocks OR "Federal Reserve")
     sourcelang:english
    &mode=ArtList
    &format=JSON
    &sort=DateDesc
    &maxrecords=250
  ```
  No API key needed. Rate limit: soft, ~1 req/sec. Adapter serializes calls with a semaphore.
- **Acceptance:** Live call test (marked `@pytest.mark.integration`) returns ≥ 10 items.
- **Depends on:** ING-01.

### ING-05 — EDGAR adapter ✅

- **Files:** `backend/app/pipelines/sources/edgar.py`.
- **Action:** SEC EDGAR filings via `https://data.sec.gov/submissions/CIK<10-digit>.json` — for each ticker in the union of all users' portfolios, look up recent 8-K, 10-K, 10-Q filings. Requires `User-Agent: Lumen <contact-email>` header (env var `EDGAR_USER_AGENT`). Because EDGAR is US-only and needs CIK lookup, add a `ticker_to_cik.json` map bundled with the app for the top 3000 US tickers.
  - `NewsItemIn.title` = `"<ticker> filed <form> on <date>"`.
  - `NewsItemIn.body` = first 4000 chars of filing narrative section (best effort — parse HTML with `selectolax`).
  - `NewsItemIn.source_id` = accession number.
- **Acceptance:** For a known-CIK ticker (AAPL, CIK 0000320193), adapter returns their last 3 filings with parsed bodies.
- **Depends on:** ING-01.

### ING-06 — RSS adapter ✅

- **Files:** `backend/app/pipelines/sources/rss.py`.
- **Action:** `RSSSource` accepting a list of feed URLs (config: `RSS_FEEDS` env var, comma-separated). Default list: Reuters Business, WSJ Markets (headlines), Bloomberg Politics (RSS), Financial Times World, Livemint India, Moneycontrol, arxiv-econ. Parse with `feedparser`. Deduplicate by URL hash before yielding.
- **Acceptance:** Given a fixture RSS XML, adapter yields correct `NewsItemIn` objects.
- **Depends on:** ING-01.

### ING-07 — Chroma vector store + local embeddings (free) ✅

- **Files:** `backend/app/db/vectorstore.py`, `backend/app/utils/embeddings.py`.
- **Action:**
  1. `VectorStore` wrapper around `chromadb.PersistentClient` (path from `CHROMA_PATH` env, default `/app/chroma_data`).
  2. Three collections created idempotently on app startup:
     - `news_items` — one doc per news item, embedding of `title + body[:1500]`, metadata `{cluster_id, source, published_at_iso, tickers}`.
     - `themes` — one doc per user theme, metadata `{user_id}`.
     - `historical_analogs` — see IMP-02.
  3. `EmbeddingClient` in `utils/embeddings.py` uses **local `sentence-transformers`** (free, no API cost, no rate limits):
     - Default model: `sentence-transformers/all-MiniLM-L6-v2` (384 dims, ~90MB, runs fine on CPU).
     - Alternative for higher quality (~4x slower, still CPU-viable): `BAAI/bge-small-en-v1.5` (384 dims). Toggled via `EMBEDDING_MODEL` env var.
     - Loaded once at process start into a module-level singleton; batch-encodes lists (batch size 64) for throughput.
     - No retries needed (local call), but wrapped in a `run_in_executor` to avoid blocking the async event loop.
     - Rationale (record in a code comment): OpenAI's `text-embedding-3-small` is the industry default but costs $0.02/M tokens with no free tier. `all-MiniLM-L6-v2` benchmarks within 5% of it on retrieval quality for English news and is free forever. This is the single largest cost-cut in the stack.
- **Acceptance:**
  - App startup creates all three collections if missing.
  - Unit test: embed 5 titles, insert into `news_items`, query top-k, verify order matches semantic expectation (Fed news retrieves other Fed news).
  - Embedding a batch of 100 items completes in < 3s on the target Fly VM.
- **Depends on:** BOOT-06.

### ING-08 — Normalizer + idempotent insertion ✅

- **Files:** `backend/app/pipelines/normalizer.py`, `backend/app/pipelines/persist.py`.
- **Action:**
  1. `normalize(item: NewsItemIn) -> NormalizedItem`:
     - Compute `url_hash = sha256(canonical_url).hexdigest()`. Canonical URL strips query params except `id`.
     - Strip HTML from body with `selectolax`.
     - Extract ticker mentions with a lightweight regex + known-ticker set (from all users' positions).
     - Truncate body to 8000 chars.
  2. `persist(items: list[NormalizedItem])`:
     - `INSERT ... ON CONFLICT (url_hash) DO NOTHING` — idempotent.
     - Insert embedding into Chroma `news_items` with the item's id as doc id.
     - Return `(inserted_count, skipped_count)`.
- **Acceptance:**
  - Running the same list twice inserts N items the first time, 0 the second.
  - Embeddings appear in Chroma with matching ids.
- **Depends on:** ING-01, ING-07.

### ING-09 — Semantic dedup + clustering into `news_clusters` ✅

- **Files:** `backend/app/pipelines/clusterer.py`.
- **Action:**
  1. For each newly-inserted item (from ING-08), query Chroma `news_items` for the top-5 nearest neighbors published within the last 48h.
  2. If max similarity > `CLUSTER_SIMILARITY_THRESHOLD` (default 0.87), assign the new item's `cluster_id` = existing cluster id. Update `news_clusters.last_seen_at`, append new source to a source-tracking JSON column (add in migration).
  3. Otherwise, create a new `news_clusters` row with `canonical_title = item.title`, `canonical_summary = item.body[:500]`, initial `entity_tickers` = extracted tickers.
  4. Authority score = per-source static weight (config: `SOURCE_AUTHORITY` dict). Cluster authority = max of members. Novelty score = 1.0 - (member_count / 10), clamped [0.1, 1.0].
- **Acceptance:**
  - Given 3 near-duplicate articles about the same event, all end up in the same cluster.
  - Given 2 unrelated articles, they end up in different clusters.
  - `pytest backend/tests/pipelines/test_clusterer.py` includes synthetic + real-world fixtures.
- **Depends on:** ING-08.

### ING-10 — Ingestion orchestrator + APScheduler ✅

- **Files:** `backend/app/pipelines/orchestrator.py`, wire into `main.py` startup.
- **Action:**
  1. `IngestOrchestrator.run()` — for each source: create an `ingest_runs` row, fetch, normalize, persist, cluster, close the row with counts.
  2. Errors caught per-source (one source failing does not kill others). Errors stored on the `ingest_runs` row.
  3. APScheduler starts on app startup: `orchestrator.run` every `INGEST_INTERVAL_MINUTES` (default 15). First run happens 30s after boot to keep startup fast.
  4. Add `GET /health/ingest` returning per-source `{last_run_at, last_status, items_new_last_run}`.
- **Acceptance:**
  - App startup logs "Scheduler started; first ingest in 30s".
  - `/health/ingest` after one cycle shows non-null `last_run_at` for each source with a valid API key.
  - Killing one source's adapter (e.g., raising in NewsAPI) does not prevent others from running.
- **Depends on:** ING-02..ING-06, ING-08, ING-09.

---

# Phase 3 — Relevance Engine

Given a news cluster + a user's portfolio + themes, decide relevance. First LangGraph work.

### REL-01 — Relevance schema + migration ✅

- **Files:** `backend/app/db/models/relevance.py`, migration.
- **Action:**

  ```sql
  CREATE TABLE relevance_scores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cluster_id UUID NOT NULL REFERENCES news_clusters(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    portfolio_id UUID NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    score NUMERIC(3, 2) NOT NULL CHECK (score BETWEEN 0 AND 1),
    touched_position_ids UUID[] NOT NULL DEFAULT '{}',
    touched_theme_ids UUID[] NOT NULL DEFAULT '{}',
    rationale TEXT,
    stage TEXT NOT NULL CHECK (stage IN ('prefilter','classifier')),
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (cluster_id, user_id, portfolio_id)
  );
  CREATE INDEX idx_relevance_user_score ON relevance_scores (user_id, score DESC);
  ```

- **Acceptance:** migration clean; unique constraint on `(cluster_id, user_id, portfolio_id)` upserts correctly.
- **Depends on:** DATA-01, ING-01.

### REL-02 — Embedding-based prefilter ✅

- **Files:** `backend/app/agents/relevance/prefilter.py`.
- **Action:**
  1. Input: a `news_cluster_id` and a `portfolio_id`.
  2. Load user's positions and themes.
  3. Fetch the cluster's item embeddings from Chroma (average them).
  4. For each position, generate a per-position embedding vector: `f"{ticker} {asset_type} {exchange}"` → embedding.
  5. For each theme, use the theme's already-stored embedding.
  6. Compute max cosine similarity between the cluster centroid and any position/theme vector.
  7. If max_sim < `PREFILTER_THRESHOLD` (default 0.35), write a `relevance_scores` row with `stage='prefilter'`, `score = max_sim`, empty touched arrays, and short-circuit.
  8. Otherwise return the shortlist of positions/themes with sim > threshold for the classifier stage.
- **Acceptance:**
  - Given a Fed news cluster + a portfolio holding AAPL only, prefilter surfaces AAPL as a candidate (Fed → all equities).
  - Given a niche pharma news cluster + a tech-only portfolio, prefilter drops it.
- **Depends on:** REL-01, ING-07, DATA-01.

### REL-03 — LLM classifier stage ✅

- **Files:** `backend/app/agents/relevance/classifier.py`.
- **Action:**
  1. Input: news cluster + shortlist from prefilter.
  2. Prompt template ships the cluster title + body[:1500] + a compact bullet list of candidate positions/themes.
  3. Force structured output (Pydantic `RelevanceVerdict`):
     ```python
     class RelevanceVerdict(BaseModel):
         score: float = Field(..., ge=0, le=1)
         touched_positions: list[UUID]
         touched_themes: list[UUID]
         rationale: str = Field(..., max_length=500)
     ```
  4. LLM tier: `fast` (Haiku 4.5).
  5. Persist `relevance_scores` row with `stage='classifier'`.
- **Acceptance:**
  - `pytest backend/tests/agents/test_relevance_classifier.py` with 10 hand-labeled cases hits ≥ 8/10 correct classifications.
  - LangSmith trace visible for each call.
- **Depends on:** REL-02, BOOT-06.

### REL-04 — Relevance graph (LangGraph) ✅

- **Files:** `backend/app/agents/relevance/graph.py`.
- **Action:** Compose prefilter + classifier as a LangGraph:
  ```
  START → prefilter → [conditional: score < threshold] → END
                    → classifier → persist → END
  ```
  Expose `async score_cluster_for_user(cluster_id: UUID, user_id: UUID, portfolio_id: UUID) -> RelevanceScore`.
- **Acceptance:**
  - Graph is compilable at import time.
  - Called on a new cluster, returns a valid `RelevanceScore` and persists a row.
  - Idempotent: calling twice for the same `(cluster, user, portfolio)` returns the cached row without re-invoking the LLM (unless `force=True`).
- **Depends on:** REL-02, REL-03.

### REL-05 — Fan-out worker: score new clusters for all users ✅

- **Files:** `backend/app/pipelines/relevance_fanout.py`.
- **Action:**
  1. After each ingest cycle (see ING-10), invoke the fan-out worker.
  2. For each cluster created/updated in the last cycle: for each user's active portfolio, enqueue `score_cluster_for_user` in a bounded worker pool (`asyncio.Semaphore(10)`).
  3. Log per-cluster fan-out cost estimates.
- **Acceptance:**
  - After a cycle that creates 50 clusters with 3 active users, `relevance_scores` gains ≤ 150 rows within 5 minutes.
  - Idempotency: re-running the fan-out yields 0 new rows.
- **Depends on:** REL-04, ING-10.

### REL-06 — News endpoints ✅

- **Files:** `backend/app/routes/news.py`.
- **Action:**

  ```
  GET  /api/news/relevant?limit=20&since=YYYY-MM-DDTHH:MM
       Returns [{ cluster: NewsClusterRead, relevance: RelevanceRead }] for the active portfolio,
       ordered by score DESC, published_at DESC.

  GET  /api/news/clusters/{cluster_id}
       Returns { cluster: NewsClusterRead, relevance: RelevanceRead | null,
                 impact: ImpactRead | null }.
  ```

- **Acceptance:**
  - Query performance: `/api/news/relevant` returns in < 300ms with 10k clusters and 200 relevance rows for the user.
  - Cross-user: user can never see relevance rows scoped to another user.
- **Depends on:** REL-01, DATA-03.

### REL-07 — Frontend news feed page

- **Files:** `frontend/src/app/news/page.tsx`, `frontend/src/components/news/*`.
- **Action:** Feed view. Each row: cluster title, source chips, "affects: NVDA, VOO" badges, relevance score bar, "Analyze impact" button (enabled only when impact assessment exists or on-demand generation is triggered).
- **Acceptance:**
  - Feed renders and filters by portfolio.
  - Clicking a row expands into a detail view.
- **Depends on:** REL-06, DATA-06.

---

# Phase 4 — Impact Analysis Agent

The core AI-engineering showcase: multi-step reasoning agent that turns a relevant news cluster into a cited, structured impact assessment.

### IMP-01 — Impact schema + migration ✅

- **Files:** `backend/app/db/models/impact.py`, migration.
- **Action:**

  ```sql
  CREATE TABLE impact_assessments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cluster_id UUID NOT NULL REFERENCES news_clusters(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    portfolio_id UUID NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    mechanism TEXT NOT NULL,
    magnitude_low NUMERIC(6, 4),
    magnitude_high NUMERIC(6, 4),
    timeframe_days INTEGER,
    confidence NUMERIC(3, 2) CHECK (confidence BETWEEN 0 AND 1),
    falsifiability TEXT NOT NULL,
    citations JSONB NOT NULL,
    historical_analogs JSONB NOT NULL DEFAULT '[]',
    affected_positions UUID[] NOT NULL DEFAULT '{}',
    raw_llm_output TEXT,
    guardrail_violations JSONB DEFAULT '[]',
    langsmith_run_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (cluster_id, user_id, portfolio_id)
  );
  CREATE INDEX idx_impact_user_created ON impact_assessments (user_id, created_at DESC);
  ```

  Pydantic:
  ```python
  class Citation(BaseModel):
      source: str
      url: HttpUrl
      title: str
      quote: str = Field(..., max_length=300)

  class HistoricalAnalog(BaseModel):
      event_description: str
      when: date
      outcome_description: str
      similarity_score: float = Field(..., ge=0, le=1)

  class ImpactAssessment(BaseModel):
      mechanism: str = Field(..., min_length=50, max_length=1500)
      magnitude_low: float | None
      magnitude_high: float | None
      timeframe_days: int | None = Field(None, ge=1, le=365)
      confidence: float = Field(..., ge=0, le=1)
      falsifiability: str = Field(..., min_length=20, max_length=500)
      citations: list[Citation] = Field(..., min_length=1)
      historical_analogs: list[HistoricalAnalog] = Field(default_factory=list)
      affected_positions: list[UUID] = Field(..., min_length=1)
  ```

- **Acceptance:** migration clean; `citations` must be non-empty (JSON schema check via CHECK constraint on jsonb length).
- **Depends on:** REL-01.

### IMP-02 — Historical analogs collection + retrieval tool

- **Files:** `backend/app/tools/historical_analogs.py`, seed script `backend/app/evals/seed_analogs.py`.
- **Action:**
  1. New Chroma collection `historical_analogs` seeded (from the seed script) with ~150 curated historical events: Fed decisions, earnings surprises, geopolitical shocks, sector rotations from the last 15 years. Each doc: `{event_description, when, outcome_description, sectors_affected, magnitude_percent}`.
  2. Tool `retrieve_analogs(query_text: str, k: int = 3) -> list[HistoricalAnalog]` — semantic search, filters by minimum similarity 0.6.
  3. Seed script is idempotent (re-runs replace on `event_hash`).
- **Acceptance:**
  - Seed script populates the collection.
  - `retrieve_analogs("Federal Reserve rate cut")` returns ≥ 2 relevant historical events.
- **Depends on:** ING-07.

### IMP-03 — Price context tool

- **Files:** `backend/app/tools/prices.py`.
- **Action:** Tool `get_recent_price_action(ticker: str, lookback_days: int = 30) -> PriceContext`. Uses `yfinance` (offline-friendly with a small file cache under `/app/price_cache/`). Returns:
  ```python
  class PriceContext(BaseModel):
      ticker: str
      current: Decimal
      pct_change_1d: float
      pct_change_5d: float
      pct_change_30d: float
      pct_change_ytd: float
      currency: str
  ```
  Failure mode: returns `None` if yfinance can't resolve — never raises.
- **Acceptance:** Called for AAPL returns non-null with plausible values. Called for garbage ticker returns None.
- **Depends on:** BOOT-06.

### IMP-04 — Impact analyst LangGraph

- **Files:** `backend/app/agents/impact/graph.py`, `backend/app/agents/impact/prompts.py`.
- **Action:**

  Graph nodes:
  ```
  START
    → load_context (cluster + touched positions + portfolio metadata)
    → retrieve_analogs (via IMP-02 tool)
    → fetch_price_context (via IMP-03 tool for each touched position)
    → reason_mechanism (LLM call producing structured JSON)
    → validate (Pydantic + guardrail suite, GRD-01..GRD-03)
    → [conditional: violations → repair_prompt → reason_mechanism (1 retry)]
    → persist
    → END
  ```

  LLM tier: `thorough` (Sonnet 5) for `reason_mechanism`, `fast` (Haiku 4.5) for `repair_prompt`.

  Prompt for `reason_mechanism`:
  ```
  You are Lumen's impact analyst. You analyze how a news event mechanically transmits
  to specific portfolio positions. You never recommend action. You always cite sources.

  Event cluster:
  Title: {title}
  Body: {body[:2000]}
  Sources: {citation_stubs}

  User's touched positions (from relevance engine):
  {position_list}

  Historical analogs (from retrieval):
  {analogs}

  Recent price context:
  {price_context}

  Output a JSON object matching this schema:
  {schema}

  Rules:
  - The `mechanism` field must describe the transmission channel in cause-effect terms.
  - The `magnitude_low` and `magnitude_high` fields are honest ranges (nullable if unknowable).
  - `falsifiability` must name a specific observable that would flip your read.
  - `citations` must reference the news sources you drew from.
  - Do NOT include phrases like "buy", "sell", "add", "trim", "overweight",
    "underweight", "consider", "should". Describe mechanics only.
  ```

- **Acceptance:**
  - Given a real news cluster + portfolio, produces a valid `ImpactAssessment` in ≤ 20s.
  - LangSmith run visible with all 5 nodes.
  - Repair retry triggers when the first attempt uses forbidden language, and succeeds on retry.
  - `pytest backend/tests/agents/test_impact_graph.py` covers happy path + guardrail-violation-then-repair.
- **Depends on:** IMP-01, IMP-02, IMP-03, REL-04, GRD-01, GRD-02, GRD-03.

### IMP-05 — Impact endpoint + on-demand generation

- **Files:** `backend/app/routes/impact.py`.
- **Action:**

  ```
  GET  /api/news/clusters/{cluster_id}/impact
       Returns cached impact if exists.
       If not, and cluster has relevance score >= 0.3 for user, enqueue generation
       and return 202 with `{"status": "generating", "poll_url": "..."}`.
  ```

  Add `POST /api/news/clusters/{cluster_id}/impact/generate` to force regeneration.

- **Acceptance:**
  - Cached impact returns 200 with full assessment.
  - Uncached, above-threshold triggers async generation; polling reveals the result within 30s.
  - Below-threshold returns 404 with a clear message.
- **Depends on:** IMP-04, REL-05.

### IMP-06 — Frontend impact card

- **Files:** `frontend/src/app/news/[id]/page.tsx`, `frontend/src/components/impact/*`.
- **Action:** Full impact view: mechanism paragraph, magnitude bar (low → high), timeframe pill, confidence bar, falsifiability callout, citation chips (click → source news in side panel), historical analog cards, "affects" position list with per-position price context.
- **Acceptance:**
  - Card renders all fields.
  - Citations open originals in a side panel.
  - Loading state (skeleton) shown during async generation.
- **Depends on:** IMP-05, REL-07.

---

# Phase 5 — Briefing Synthesizer

Aggregate the day's impact assessments into a personalized briefing.

### BRIEF-01 — Briefing schema + migration

- **Files:** `backend/app/db/models/briefing.py`, migration.
- **Action:**

  ```sql
  CREATE TABLE briefings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    portfolio_id UUID NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    briefing_date DATE NOT NULL,
    structured_content JSONB NOT NULL,
    cited_impact_ids UUID[] NOT NULL DEFAULT '{}',
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    generation_duration_ms INTEGER,
    langsmith_run_id TEXT,
    UNIQUE (user_id, portfolio_id, briefing_date)
  );
  CREATE INDEX idx_briefings_user_date ON briefings (user_id, briefing_date DESC);
  ```

  Pydantic:
  ```python
  class BriefingItem(BaseModel):
      impact_id: UUID
      cluster_title: str
      one_line_summary: str = Field(..., max_length=200)
      affected_positions: list[str]  # tickers
      mechanism_summary: str = Field(..., max_length=400)
      confidence: float

  class BriefingContent(BaseModel):
      top_movers: list[BriefingItem] = Field(..., max_length=5)
      watchlist: list[BriefingItem] = Field(..., max_length=5)
      what_would_change_my_thinking: list[str] = Field(..., max_length=5)
      generated_summary: str = Field(..., max_length=800)
  ```

- **Acceptance:** migration clean.
- **Depends on:** IMP-01.

### BRIEF-02 — Briefing synthesizer agent

- **Files:** `backend/app/agents/briefing/graph.py`, `backend/app/agents/briefing/prompts.py`.
- **Action:**

  Graph:
  ```
  START
    → gather_impacts (last 24h with score ≥ 0.5, ordered by score * novelty DESC)
    → rank_top_movers (LLM: pick top 3-5, given portfolio context)
    → rank_watchlist (LLM: pick 3-5 developing situations)
    → synthesize_what_would_change (LLM: extract 3-5 falsifiability items)
    → compose_generated_summary (LLM: 100-word overview)
    → validate (guardrail suite)
    → persist
    → END
  ```

  Two model tiers: `thorough` for compose_generated_summary; `fast` for ranking.

- **Acceptance:**
  - Running against a fixture set of 15 impact assessments yields a valid `BriefingContent` in ≤ 30s.
  - Every `impact_id` in `cited_impact_ids` corresponds to a real assessment for the user.
  - Guardrail violations block persistence.
- **Depends on:** BRIEF-01, IMP-05, GRD-01, GRD-02.

### BRIEF-03 — Scheduled briefing generation

- **Files:** `backend/app/pipelines/briefing_scheduler.py`.
- **Action:** APScheduler job that runs every 15 minutes: query `user_preferences` for users whose local `briefing_hour` == current local hour and who don't have a briefing for today. Enqueue the briefing agent for each. Cap concurrency at 5.
- **Acceptance:**
  - A user with `briefing_hour=8, briefing_timezone="Asia/Kolkata"` gets a briefing generated around 08:00 IST.
  - No duplicate briefings for the same `(user, portfolio, date)`.
- **Depends on:** BRIEF-02, DATA-05.

### BRIEF-04 — Briefing endpoints + streaming

- **Files:** `backend/app/routes/briefings.py`.
- **Action:**

  ```
  GET  /api/briefings/latest                       → BriefingRead (most recent)
  GET  /api/briefings?date=YYYY-MM-DD              → BriefingRead
  POST /api/briefings/regenerate                   → 202 { poll_url }
  GET  /api/briefings/stream                       → SSE (Server-Sent Events)
       Streams events:
         event: node_started      data: {"node": "gather_impacts"}
         event: node_completed    data: {"node": "gather_impacts", "duration_ms": 200}
         event: partial_content   data: <partial BriefingContent JSON>
         event: complete          data: {"briefing_id": "..."}
  ```

  SSE endpoint runs the briefing graph with a callback that emits per-node events. Used by the "generate live" button on the briefing page (recruiter demo).

- **Acceptance:**
  - `curl -N /api/briefings/stream` produces valid SSE events.
  - Frontend can consume the stream and progressively render sections.
- **Depends on:** BRIEF-02.

### BRIEF-05 — Frontend briefing page

- **Files:** `frontend/src/app/briefing/page.tsx`, `frontend/src/components/briefing/*`, `frontend/src/hooks/use-sse.ts`.
- **Action:** Full briefing page. Three sections. Each item card shows title, one-line summary, mechanism (expandable), affected positions, confidence bar, "view full analysis" link → the impact detail page. A "Generate live" button that streams a fresh briefing via SSE for demo purposes.
- **Acceptance:**
  - Loads yesterday's briefing on first visit; falls back to "no briefing yet — generate one" if none exists.
  - Live-generate streams nodes in order and updates the UI progressively.
- **Depends on:** BRIEF-04.

---

# Phase 6 — Chat Interface

RAG over the user's news + assessments + portfolio, with streaming responses.

### CHAT-01 — Chat schema + migration

- **Files:** `backend/app/db/models/chat.py`, migration.
- **Action:**

  ```sql
  CREATE TABLE chat_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    portfolio_id UUID NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    title TEXT,
    seed_cluster_id UUID REFERENCES news_clusters(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
  );
  CREATE INDEX idx_chat_sessions_user_updated ON chat_sessions (user_id, updated_at DESC);

  CREATE TABLE chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user','assistant','system')),
    content TEXT NOT NULL,
    citations JSONB DEFAULT '[]',
    tokens_used INTEGER,
    langsmith_run_id TEXT,
    guardrail_violations JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
  );
  CREATE INDEX idx_chat_messages_session ON chat_messages (session_id, created_at);
  ```

- **Acceptance:** migration clean.
- **Depends on:** BOOT-05.

### CHAT-02 — Chat retrieval tools

- **Files:** `backend/app/agents/chat/retrievers.py`.
- **Action:** Three retrievers callable as tools:
  1. `retrieve_recent_impacts(lookback_days: int = 7, k: int = 5)` — top-k relevant impact assessments in the last week for this user's active portfolio.
  2. `retrieve_news(query: str, k: int = 5, since_days: int = 30)` — RAG over `news_items` Chroma collection, filtered to items touching the user's tickers.
  3. `get_portfolio_summary()` — one-shot lookup of the active portfolio: positions, themes, most recent briefing summary.
- **Acceptance:** Each tool returns typed results in < 500ms.
- **Depends on:** IMP-05, ING-07.

### CHAT-03 — Chat agent (LangGraph)

- **Files:** `backend/app/agents/chat/graph.py`.
- **Action:**

  Graph:
  ```
  START
    → classify_intent (LLM: portfolio-context | news-question | mechanism-question | out-of-scope)
    → [if out-of-scope] → polite_refusal → END
    → route_tools (LLM chooses which retrievers to call)
    → execute_tools (parallel)
    → compose_response (LLM: streaming, structured with citations)
    → validate (guardrail suite; streaming validator too — stops mid-stream on violation)
    → persist_message
    → END
  ```

  Streaming: the `compose_response` node streams tokens; the frontend receives incremental content plus a citations array appended at the end.

- **Acceptance:**
  - Question "what's my biggest concentration risk?" retrieves portfolio summary and returns a cited answer.
  - Question "should I buy NVDA?" is refused politely with a canned response.
  - Question "explain what happened to interest rates this week" retrieves recent news and impacts.
- **Depends on:** CHAT-01, CHAT-02, GRD-01, GRD-02, GRD-03.

### CHAT-04 — Chat endpoints + streaming

- **Files:** `backend/app/routes/chat.py`.
- **Action:**

  ```
  POST   /api/chat/sessions                   body: { seed_cluster_id? } → ChatSessionRead
  GET    /api/chat/sessions                    → list[ChatSessionRead]
  GET    /api/chat/sessions/{id}               → ChatSessionRead + messages
  DELETE /api/chat/sessions/{id}               → 204
  POST   /api/chat/sessions/{id}/messages      body: { content: string } → SSE stream
         events:
           token         data: {"delta": "..."}
           tool_call     data: {"tool": "retrieve_news", "args": {...}}
           tool_result   data: {"tool": "retrieve_news", "result_summary": "..."}
           citations     data: [Citation, ...]
           done          data: {"message_id": "..."}
  ```

- **Acceptance:**
  - SSE stream events arrive in correct order.
  - History endpoint returns messages in chronological order.
  - Cross-user session access returns 404.
- **Depends on:** CHAT-03.

### CHAT-05 — Frontend chat UI

- **Files:** `frontend/src/app/chat/page.tsx`, `frontend/src/app/chat/[id]/page.tsx`, `frontend/src/components/chat/*`.
- **Action:**
  - Session list sidebar (left), messages area (right).
  - Messages render markdown via `react-markdown`.
  - Streaming tokens appear character by character.
  - Tool-call events show a small "searching news..." indicator that resolves when the tool result arrives.
  - Citations appear as numbered chips below assistant messages; hover shows source, click opens side panel.
  - "New chat" button; deep-link `/chat?seed=<cluster_id>` starts a session with the cluster loaded.
- **Acceptance:**
  - Full chat session works end-to-end.
  - Deep link from a briefing item opens chat with context.
- **Depends on:** CHAT-04.

---

# Phase 7 — Long-Term Memory & Calibration

The differentiator. Tracks whether Lumen's predictions played out and surfaces a calibration score.

### MEM-01 — Predictions schema + migration

- **Files:** `backend/app/db/models/prediction.py`, migration.
- **Action:**

  ```sql
  CREATE TABLE predictions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    impact_id UUID NOT NULL REFERENCES impact_assessments(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    predicted_direction TEXT NOT NULL
      CHECK (predicted_direction IN ('positive','negative','neutral','mixed')),
    predicted_magnitude_low NUMERIC(6, 4),
    predicted_magnitude_high NUMERIC(6, 4),
    timeframe_days INTEGER NOT NULL,
    falsifiability_criterion TEXT NOT NULL,
    resolve_by TIMESTAMPTZ NOT NULL,
    resolved_at TIMESTAMPTZ,
    actual_outcome TEXT CHECK (actual_outcome IN ('confirmed','partial','refuted','inconclusive')),
    actual_magnitude NUMERIC(6, 4),
    resolution_notes TEXT,
    resolution_source TEXT,          -- 'manual' | 'auto_price' | 'auto_news'
    calibration_delta NUMERIC(6, 4),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
  );
  CREATE INDEX idx_predictions_user_resolve ON predictions (user_id, resolve_by);
  CREATE INDEX idx_predictions_impact ON predictions (impact_id);
  ```

- **Acceptance:** migration clean.
- **Depends on:** IMP-01.

### MEM-02 — Auto-stamp predictions on impact creation

- **Files:** modify `backend/app/agents/impact/graph.py` (persist node) — after saving the impact assessment, insert one `predictions` row.
- **Action:** For every new impact assessment:
  - `predicted_direction` = derived from `mechanism` via a small LLM classifier call.
  - `predicted_magnitude_low/high` = copied from impact.
  - `timeframe_days` = copied from impact (default 14 if null).
  - `falsifiability_criterion` = copied from impact.
  - `resolve_by` = now + `timeframe_days`.
- **Acceptance:**
  - Every new impact assessment produces exactly one prediction row.
  - `predicted_direction` is a valid enum value.
- **Depends on:** MEM-01, IMP-04.

### MEM-03 — Resolution engine (auto-resolve via prices + news)

- **Files:** `backend/app/pipelines/resolver.py`.
- **Action:** Scheduled job every 6 hours:
  1. Query `predictions WHERE resolved_at IS NULL AND resolve_by <= NOW()`.
  2. For each: use `get_recent_price_action` on affected positions to compute actual movement over the `timeframe_days` window.
  3. Compare `actual_magnitude` vs `predicted_magnitude_low..high`. Classify:
     - `confirmed` if actual within range AND direction matches.
     - `partial` if direction matches but magnitude off by ≤ 2×.
     - `refuted` if direction wrong OR magnitude off by > 2×.
     - `inconclusive` if data missing.
  4. Compute `calibration_delta = |predicted_midpoint - actual_magnitude|`.
  5. Update the row.
- **Acceptance:**
  - On a fixture set of resolved predictions, classification matches manual labels ≥ 80% of the time.
  - `resolution_source` correctly populated.
- **Depends on:** MEM-02, IMP-03.

### MEM-04 — Calibration endpoint + track record page

- **Files:** `backend/app/routes/calibration.py`, `frontend/src/app/track-record/page.tsx`.
- **Action:**

  ```
  GET  /api/calibration                  → { total_predictions, resolved,
                                            confirmed_rate, partial_rate, refuted_rate,
                                            brier_score, calibration_by_confidence: [...] }
  GET  /api/predictions                  → list[PredictionRead]
  GET  /api/predictions/{id}             → PredictionRead
  POST /api/predictions/{id}/resolve     body: { outcome, actual_magnitude, notes }
                                          (manual override — user-facing)
  ```

  Frontend `/track-record`: a "Lumen's track record" page showing the rollup stats, a calibration reliability curve, and a table of individual predictions with their outcomes. Public URL (no auth) shows aggregated stats only; per-prediction detail requires auth.

- **Acceptance:**
  - Page renders correctly with real data.
  - Brier score computed correctly against test fixture.
- **Depends on:** MEM-03.

### MEM-05 — Historical backfill (bootstrap calibration)

- **Files:** `backend/app/evals/backfill_calibration.py`.
- **Action:** Standalone script (invoked once via `python -m app.evals.backfill_calibration`) that:
  1. Loads 30 real historical events from the past 12 months (Fed decisions, notable earnings, geopolitical shocks — curated list in `backend/app/evals/historical_events.json`).
  2. Constructs synthetic news clusters + a "demo" portfolio owned by a hidden system user.
  3. Runs the full pipeline: relevance → impact → prediction → resolution against actual price data.
  4. Populates the calibration dataset so v0.2 ships with a meaningful track record on day one.
- **Acceptance:**
  - Script runs to completion in ≤ 30 min.
  - Public `/track-record` shows ≥ 25 resolved predictions after backfill.
- **Depends on:** MEM-03, MEM-04.

---

# Phase 8 — Eval Harness

The resume-worthy differentiator. Real labeled dataset, LangSmith runs, published metrics.

### EVAL-01 — Golden dataset construction

- **Files:** `backend/app/evals/datasets/relevance_v1.jsonl`, `backend/app/evals/datasets/impact_v1.jsonl`, `backend/app/evals/README.md`.
- **Action:**
  1. `relevance_v1.jsonl` — 200 examples. Each: `{cluster_id, portfolio_desc, expected_score, expected_touched_tickers, rationale}`. Sourced from real news over 3 months × 5 synthetic portfolios (US tech-heavy, dividend income, global diversified, crypto-heavy, India equity).
  2. `impact_v1.jsonl` — 50 examples. Each: `{cluster_id, portfolio_desc, expected_mechanism_keywords, expected_direction, expected_magnitude_range, expected_analog_events}`.
  3. Labeling protocol documented in `evals/README.md`. All examples double-labeled by two humans (or the same human 2 weeks apart); inter-labeler agreement ≥ 80% is a merge gate.
- **Acceptance:**
  - Datasets exist and validate against their JSON schema.
  - `evals/README.md` documents provenance, labeling protocol, and known limitations.
- **Depends on:** IMP-04.

### EVAL-02 — LangSmith setup + tracing

- **Files:** `backend/app/utils/langsmith.py` (extend), CI env vars.
- **Action:**
  1. LangSmith project name: `lumen-{env}` where env ∈ {dev, staging, prod}.
  2. All LangGraph runs auto-tagged with `user_id`, `agent_name`, `git_sha`.
  3. Public trace-sharing enabled on selected runs (briefing generations get shared traces so they can be linked from the app).
- **Acceptance:**
  - LangSmith dashboard shows runs from all three environments.
  - Each briefing card in the UI has a "view trace" link that opens a public LangSmith trace.
- **Depends on:** BOOT-06.

### EVAL-03 — Eval runner (relevance)

- **Files:** `backend/app/evals/runners/relevance.py`.
- **Action:** CLI: `python -m app.evals.runners.relevance --dataset relevance_v1 --limit 200`. Runs the relevance graph on every example, compares against gold, computes:
  - Precision = TP / (TP + FP) on ticker-touched predictions.
  - Recall = TP / (TP + FN).
  - F1.
  - Confusion matrix per threshold ({0.3, 0.5, 0.7}).
  Persist result to `eval_runs` table with `metrics` JSON.
- **Acceptance:**
  - Runner executes and reports numbers.
  - Result reproducible with the same git sha and dataset.
- **Depends on:** EVAL-01, REL-04.

### EVAL-04 — Eval runner (impact + faithfulness)

- **Files:** `backend/app/evals/runners/impact.py`, `backend/app/evals/runners/faithfulness.py`.
- **Action:**
  1. `impact.py` scores impact assessments on:
     - Direction match: predicted direction vs expected direction.
     - Magnitude overlap: intersection of predicted range with expected range.
     - Analog retrieval: does the retrieved historical analog match any expected one?
  2. `faithfulness.py` runs RAGAS on the impact assessments: `faithfulness`, `answer_relevancy`, `context_precision`, `context_recall`.
- **Acceptance:**
  - Both runners execute.
  - RAGAS scores > 0.7 on the impact dataset.
- **Depends on:** EVAL-01, IMP-04.

### EVAL-05 — CI integration + regression gate

- **Files:** `.github/workflows/ci.yml` (extend).
- **Action:** On PRs touching `backend/app/agents/**`:
  1. Run relevance eval on a fixed 50-example subsample.
  2. Compare metrics vs. last successful main-branch run.
  3. Fail the PR if F1 drops by > 0.05 vs main.
  4. Post metrics as a PR comment.
- **Acceptance:**
  - A trivial PR gets its metrics posted.
  - A PR that breaks the classifier is blocked.
- **Depends on:** EVAL-03, EVAL-04, BOOT-08.

### EVAL-06 — Public metrics page

- **Files:** `frontend/src/app/quality/page.tsx`, `backend/app/routes/eval.py`.
- **Action:**

  ```
  GET  /api/eval/latest              → { relevance: {...}, impact: {...},
                                        faithfulness: {...}, guardrails: {...},
                                        run_at, git_sha }
  GET  /api/eval/history             → last 30 runs (metrics only)
  ```

  Frontend `/quality`: prominent metrics dashboard. Bar charts for each metric. History sparklines. Links to the LangSmith dataset. Public page (no auth) — this is the resume artifact.

- **Acceptance:**
  - Page loads and renders live metrics.
  - Metrics update within 10 minutes of a new eval run.
- **Depends on:** EVAL-03, EVAL-04.

---

# Phase 9 — Scenario Simulator (v0.2)

User picks or defines a scenario; agent walks through impact on portfolio.

### SIM-01 — Scenario schema + endpoint

- **Files:** `backend/app/routes/scenarios.py`, `backend/app/schemas/scenario.py`.
- **Action:**

  ```
  POST /api/scenarios/simulate
       body: { scenario_text: string, portfolio_id?: UUID }
       response: SSE stream of scenario analysis (similar to impact analyst)
  ```

  ```python
  class ScenarioSimulation(BaseModel):
      scenario_text: str
      per_position_impact: list[PositionImpact]
      portfolio_summary: str
      citations: list[Citation]
      historical_analogs: list[HistoricalAnalog]
      key_assumptions: list[str]
      falsifiability: str
  ```

- **Acceptance:** endpoint accepts and streams a simulation.
- **Depends on:** IMP-04.

### SIM-02 — Scenario agent (LangGraph)

- **Files:** `backend/app/agents/scenario/graph.py`.
- **Action:** Reuses the impact analyst's tools (analog retrieval, price context) but with a scenario prompt instead of a news cluster. Explicitly stateful — user can iterate ("what if we also assume oil stays flat?").
- **Acceptance:** produces valid `ScenarioSimulation`.
- **Depends on:** IMP-04.

### SIM-03 — Preset scenarios

- **Files:** `backend/app/agents/scenario/presets.py`.
- **Action:** A set of 10 curated preset scenarios: "Fed cuts 50bps at next FOMC", "US recession Q3", "Oil to $120", "AI capex boom continues 12 months", "India rate cuts by 100bps", etc. UI shows these as one-click chips.
- **Acceptance:** presets load, click generates a full simulation.
- **Depends on:** SIM-02.

### SIM-04 — Frontend scenario page

- **Files:** `frontend/src/app/scenarios/page.tsx`.
- **Action:** Text input for freeform scenario, preset chips, streaming result display. Simulation history in a side panel.
- **Acceptance:** page renders and streams simulations.
- **Depends on:** SIM-03.

---

# Phase 10 — Deployment & Polish

Get the app live at a stable URL. Seed the demo. Write the resume-facing README.

### DEPLOY-01 — Frontend on Vercel

- **Files:** `vercel.json`, GitHub Actions job.
- **Action:**
  1. Connect Vercel to the repo, deploy `frontend/`.
  2. Env vars set in Vercel dashboard.
  3. Preview deployments on every PR.
  4. Production deploys on merge to `v2/intelligence-agent`.
- **Acceptance:** live URL reachable, sign-in works, app fetches from backend URL.
- **Depends on:** DATA-06, DEPLOY-02.

### DEPLOY-02 — Backend on Fly.io

- **Files:** `backend/Dockerfile`, `backend/fly.toml`, GitHub Actions job.
- **Action:**
  1. `Dockerfile` — python:3.11-slim base, `uvicorn` entrypoint with 2 workers.
  2. `fly.toml` — single VM, 1×shared-cpu-1x with 512MB (upgrade if OOM), volume mount for `/app/chroma_data`.
  3. Env vars set via `flyctl secrets`.
  4. `fly deploy` on merge.
- **Acceptance:** backend URL reachable, `/health` returns 200, ingest runs successfully.
- **Depends on:** ING-10, all migrations applied to prod Postgres.

### DEPLOY-03 — Scheduled worker isolation

- **Files:** `backend/fly.toml` extension.
- **Action:** Optionally split ingestion + briefing scheduler into a separate Fly machine (same image, different entrypoint) to isolate from HTTP traffic. Skip for MVP unless ingest starves HTTP; document the split as a v1.0 upgrade.
- **Acceptance:** if split: worker machine runs the schedulers, HTTP machine only serves requests.
- **Depends on:** DEPLOY-02.

### DEPLOY-04 — Public demo user + seeded data

- **Files:** `backend/app/evals/seed_demo.py`.
- **Action:**
  1. Create a demo user in Supabase (`demo@lumen.app`, fixed password stored as a secret).
  2. Seed a plausible portfolio (AAPL, MSFT, NVDA, GOOGL, VOO, BND, ETH-USD).
  3. Seed 5 themes.
  4. Run the pipeline over the last 30 days of news for this user, generating relevance scores + impact assessments + one briefing per day.
  5. A "Try demo" button on the landing page one-clicks a Supabase magic-link login for this user.
- **Acceptance:**
  - Fresh visitor clicks "Try demo" and lands on a fully populated `/briefing`.
  - The seeded data survives redeploys (seeding is idempotent).
- **Depends on:** DEPLOY-02, MEM-05.

### DEPLOY-05 — Landing page polish

- **Files:** `frontend/src/app/page.tsx`, marketing assets under `frontend/public/`.
- **Action:**
  - Hero: one-line pitch, "Try demo" primary CTA, "Sign up free" secondary CTA.
  - 20-second demo GIF (recorded live from the deployed app).
  - Three-column "what it does": news ingest → personalized analysis → cited briefing.
  - "Model quality" section linking to `/quality`.
  - Persistent footer with the "not investment advice" disclaimer.
- **Acceptance:**
  - Lighthouse score ≥ 90 on performance, accessibility, best practices, SEO.
  - GIF loads without CLS.
- **Depends on:** DEPLOY-01, EVAL-06.

### DEPLOY-06 — README + resume-facing docs

- **Files:** `README.md` (rewrite), `docs/ARCHITECTURE.md` (new), `docs/EVALS.md` (new).
- **Action:**
  1. `README.md` — pitch (one paragraph), live URL + demo credentials, screenshots, high-level architecture diagram, tech-stack table, how to run locally, links to `PRD.md`, `BUILD.md`, `ARCHITECTURE.md`, `EVALS.md`.
  2. `docs/ARCHITECTURE.md` — deep-dive: LangGraph node diagrams for each agent, data flow, sequence diagram for a briefing generation, why each framework was chosen.
  3. `docs/EVALS.md` — how the eval harness works, published metrics, methodology, known limitations.
- **Acceptance:**
  - README readable in 5 minutes; a hiring manager who has never seen the repo understands what it is and why it's technically interesting.
  - Architecture diagram is legible and matches reality.
- **Depends on:** DEPLOY-01, DEPLOY-02, EVAL-06.

---

# Cross-cutting: Design System (DESIGN-01..DESIGN-03)

These modules formalize the design system described in Global Conventions. Land them early — every frontend module downstream depends on the tokens and primitives.

### DESIGN-01 — Design tokens + Tailwind config

- **Files:** `frontend/src/app/globals.css`, `frontend/tailwind.config.ts`, `frontend/src/lib/fonts.ts`.
- **Action:**
  1. `globals.css` declares every CSS custom property from the palette + typography scale sections above.
  2. `tailwind.config.ts` maps them to semantic Tailwind tokens (`colors.surface`, `colors.confirmed`, `fontFamily.sans`, `fontFamily.mono`, `spacing.rhythm-16 = 4rem`, etc.).
  3. `fonts.ts` loads Geist Sans + Geist Mono via `next/font/local` (self-hosted, no CDN dependency).
  4. Root layout sets `data-theme="dark"` on `<html>`.
- **Acceptance:**
  - No component in the repo hardcodes a hex color; grep for `#[0-9a-fA-F]{3,8}` in `frontend/src/**/*.tsx` returns 0 matches outside `globals.css`.
  - Lighthouse contrast audit: 0 failures.
- **Depends on:** BOOT-04.

### DESIGN-02 — Primitive component set

- **Files:** `frontend/src/components/ui/*` (extend existing shadcn primitives), `frontend/src/components/primitives/*` (new Lumen-specific).
- **Action:** Build/audit the following primitives to spec:
  - `Button` (variants: primary, secondary, ghost, destructive; sizes sm/md/lg; loading state built-in).
  - `Card` (variants: default, elevated; internal spacing `p-6`/`p-8`).
  - `Badge` (variants: neutral, confirmed, refuted, partial; sizes sm/md).
  - `Chip` (rounded-full, small, for tickers and citations).
  - `Stat` (numeric display with label above, mono digits, optional delta chip).
  - `Skeleton` (matches Card/Stat/Chip shapes).
  - `Section` (heading + subheading + slot; enforces vertical rhythm).
  - `EmptyState` (icon + heading + prose + CTA).
  - `StreamingBlock` (pulsing left-border wrapper for SSE content).
- **Acceptance:** every primitive has a Storybook (or in-app `/design` route) entry showing all variants; visual sanity is manually verified before merge.
- **Depends on:** DESIGN-01.

### DESIGN-03 — App shell + navigation

- **Files:** `frontend/src/components/app-shell/*`, `frontend/src/app/(app)/layout.tsx`.
- **Action:** Build the persistent app shell used by every authenticated page:
  - Fixed left sidebar 240px: logo, primary nav (Briefing, News, Chat, Track record, Quality, Portfolio, Settings), active portfolio switcher pinned at bottom.
  - Top bar 56px: page title, right-aligned actions (search, user menu).
  - Main content area with max-width `1440px`, centered.
  - Mobile: sidebar collapses to a Sheet.
- **Acceptance:** all authenticated pages render inside the shell; keyboard nav works; mobile responsive at 375px min-width.
- **Depends on:** DESIGN-02, DATA-06.

---

# Cross-cutting: AI Pipeline Optimizations (OPT-01..OPT-06)

**This is where the resume bullets come from.** Each module is a measurable optimization with a before/after number that goes on the resume verbatim. Every optimization must be paired with a benchmark (Phase 8) that proves the win.

Ship order: OPT-01, OPT-05, then the rest as time allows. OPT-05 is a soft dependency of many other modules — implement its table schema in Phase 0 as a bare skeleton so downstream work can write to it.

### OPT-01 — Two-stage relevance filter (already partially in REL-02/REL-03; formalize the win)

- **Files:** `backend/app/agents/relevance/*`, benchmark in `backend/app/evals/bench_relevance.py`.
- **Action:**
  - The prefilter → classifier split (REL-02 → REL-03) is a classic embedding-then-LLM cascade. Instrument it to capture the win explicitly.
  - Log every classification: whether the LLM stage was invoked or the prefilter short-circuited.
  - Compute the **cost reduction ratio** = `1 - (LLM calls made / candidate news items)`. Target ≥ 0.7 (i.e. 70% of news never hits the LLM).
- **Acceptance:**
  - Benchmark shows precision/recall of the full cascade is within 5% of a classifier-only baseline (measured on the EVAL-01 golden set).
  - Cost reduction ratio ≥ 0.7 in production.
- **Resume bullet target:** *"Designed a two-stage relevance filter (semantic pre-filter + LLM classifier) that cut LLM-call volume by 72% while preserving F1 within 3% of a classifier-only baseline, on a 200-example labeled benchmark."*
- **Depends on:** REL-04, EVAL-03.

### OPT-02 — Prompt caching / structured prompt templates

- **Files:** `backend/app/agents/*/prompts.py`, `backend/app/utils/prompt_cache.py`.
- **Action:**
  - Every agent's prompt is split into a large **static prefix** (role + instructions + schema + few-shot examples) and a small **dynamic suffix** (per-call inputs). Static prefixes ≥ 90% of prompt tokens.
  - For providers that support prompt caching (Anthropic, some OpenRouter-routed models), enable it via provider-specific headers.
  - For providers without native caching, use the semantic cache from OPT-05 keyed on `(agent_name, template_version, dynamic_suffix_hash)`.
- **Acceptance:**
  - Benchmark shows repeat-call latency reduced by ≥ 40% and repeat-call token cost reduced by ≥ 60%.
- **Resume bullet target:** *"Implemented a two-tier prompt cache (native provider caching + semantic dedup on OpenAI-compatible endpoints), cutting repeat-call latency by 47% and token cost by 68% across relevance and briefing agents."*
- **Depends on:** OPT-05.

### OPT-03 — HyDE (Hypothetical Document Embeddings) for chat retrieval

- **Files:** `backend/app/agents/chat/retrievers.py`.
- **Action:**
  - Before retrieving news for a chat query, use the fast-tier LLM to generate a **hypothetical answer** to the query. Embed the hypothetical answer, not the raw query. Retrieve against that.
  - Rationale: retrieval quality on short user queries ("why is NVDA down?") is poor because the query embeds to a different point in space than a news article. A hypothetical answer sits in article-space.
  - Guarded by feature flag `USE_HYDE_RETRIEVAL` — enabled by default, toggleable for A/B benchmarking.
- **Acceptance:**
  - Benchmark on a 50-query held-out chat retrieval set shows `nDCG@5` improvement of ≥ 0.08 vs. raw-query embedding.
- **Resume bullet target:** *"Improved retrieval quality on personal financial chat queries by 18% (nDCG@5, 0.71 → 0.84) by implementing HyDE — generating hypothetical answers with a 7B model before embedding-space retrieval."*
- **Depends on:** CHAT-02, EVAL-04.

### OPT-04 — Cross-encoder reranker for chat retrieval

- **Files:** `backend/app/agents/chat/reranker.py`.
- **Action:**
  - After the vector retriever returns top-N (N=20), rerank with a local cross-encoder: `BAAI/bge-reranker-base` (~110MB, CPU-viable). Keep top-5.
  - Loaded as a module-level singleton via `sentence-transformers.CrossEncoder`.
- **Acceptance:**
  - Benchmark: precision@5 improvement of ≥ 0.10 vs. no-reranker baseline on the eval set.
- **Resume bullet target:** *"Boosted top-5 retrieval precision from 0.62 to 0.78 by adding a locally-hosted cross-encoder reranker (bge-reranker-base) after vector search."*
- **Depends on:** OPT-03.

### OPT-05 — Semantic response cache

- **Files:** `backend/app/utils/semantic_cache.py`, `backend/app/db/models/llm_cache.py`, migration.
- **Action:**

  ```sql
  CREATE TABLE llm_calls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_name TEXT NOT NULL,
    tier TEXT NOT NULL,
    model TEXT NOT NULL,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    latency_ms INTEGER,
    cache_hit BOOLEAN NOT NULL DEFAULT FALSE,
    cache_source TEXT,                       -- 'exact' | 'semantic' | 'provider'
    user_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
  );

  CREATE TABLE llm_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cache_key TEXT NOT NULL,                 -- for exact-match
    prompt_embedding VECTOR(384),            -- via pgvector, or JSON if pgvector not enabled
    prompt_preview TEXT,
    response_json JSONB NOT NULL,
    hit_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL
  );
  CREATE INDEX idx_llm_cache_key ON llm_cache (cache_key);
  ```
  - Two lookup paths: (1) exact SHA256 of normalized prompt; (2) if `cache_key` explicitly opts in, semantic lookup via cosine similarity ≥ 0.97 against `prompt_embedding`.
  - Semantic cache is used only for agents where response variance across similar prompts is acceptable (relevance classifier, intent classifier, guardrail). NOT used for impact analysis or briefing synthesis where fidelity matters.
- **Acceptance:**
  - `hit_count` visible in `/api/eval/latest` alongside eval metrics.
  - Cache hit rate on relevance classifier ≥ 0.35 after 48h of operation.
- **Resume bullet target:** *"Built a two-tier LLM response cache (exact + semantic) achieving 38% hit rate on classification workloads, eliminating ~1,200 free-tier API calls per day."*
- **Depends on:** BOOT-05.

### OPT-06 — Parallel tool calls in chat agent

- **Files:** `backend/app/agents/chat/graph.py`.
- **Action:**
  - In CHAT-03's `route_tools` → `execute_tools` step, execute independent tool calls in parallel via `asyncio.gather`.
  - Instrument end-to-end response latency and compare to a serial baseline.
- **Acceptance:**
  - Benchmark: median chat first-token latency reduced by ≥ 30% on queries that trigger ≥ 2 tool calls.
- **Resume bullet target:** *"Parallelized independent tool calls in a LangGraph agent's execution phase, reducing median chat response time-to-first-token by 34% on multi-tool queries."*
- **Depends on:** CHAT-03.

---

# Cross-cutting: Benchmarking & Metrics (BENCH-01..BENCH-04)

Extends Phase 8. These modules produce the specific, publishable numbers that back the resume bullets. Every module here writes to a stable table so the numbers can be quoted from a URL, not screenshots.

### BENCH-01 — Latency percentile harness

- **Files:** `backend/app/evals/bench_latency.py`, `backend/app/db/models/bench_runs.py`, migration.
- **Action:**

  ```sql
  CREATE TABLE bench_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    kind TEXT NOT NULL,                      -- 'latency' | 'quality' | 'cost' | 'cache'
    subject TEXT NOT NULL,                   -- 'relevance' | 'impact' | 'chat' | 'briefing' | 'e2e'
    git_sha TEXT NOT NULL,
    n_samples INTEGER NOT NULL,
    metrics JSONB NOT NULL,                  -- {p50_ms, p95_ms, p99_ms, mean_ms, ...}
    notes TEXT,
    ran_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
  );
  CREATE INDEX idx_bench_runs_subject_ran ON bench_runs (subject, ran_at DESC);
  ```

  - Runner replays 100 fixture inputs per subject, records per-node LangGraph latency, aggregates percentiles.
- **Acceptance:** CLI `python -m app.evals.bench_latency --subject relevance --n 100` completes and inserts a row.
- **Depends on:** REL-04, IMP-04, BRIEF-02, CHAT-03.

### BENCH-02 — Cost-per-artifact tracking

- **Files:** `backend/app/evals/bench_cost.py`.
- **Action:** Aggregate `llm_calls` rows to compute:
  - Free-tier API calls per briefing / per assessment / per chat turn.
  - Effective throughput ratio: what % of workload fits inside free-tier RPM limits without queuing.
- **Acceptance:** dashboard shows per-artifact call count and RPM headroom.
- **Depends on:** OPT-05.

### BENCH-03 — Regression gate on all optimization modules

- **Files:** `.github/workflows/ci.yml` (extend EVAL-05 gate).
- **Action:** Every PR touching an agent runs the relevant benchmark. If any of these regress by more than the tolerance, PR is blocked:
  - Relevance F1 (tolerance 0.05).
  - RAG faithfulness (tolerance 0.05).
  - Impact-direction accuracy (tolerance 0.05).
  - Chat p95 latency (tolerance 25%).
  - Cache hit rate (tolerance 10 percentage points).
- **Acceptance:** a PR that degrades any metric beyond tolerance is blocked with a clear comment.
- **Depends on:** BENCH-01, EVAL-05.

### BENCH-04 — Publishable metrics card

- **Files:** `frontend/src/app/quality/page.tsx` (extend EVAL-06).
- **Action:** The public `/quality` page renders a single-screen "state of the model" card with the exact numbers that back each resume bullet, labeled by the OPT-nn / BENCH-nn module that produced them. Includes:
  - Two-stage cascade cost reduction (OPT-01)
  - Prompt cache hit rate + latency delta (OPT-02, OPT-05)
  - HyDE retrieval nDCG@5 delta (OPT-03)
  - Reranker precision@5 delta (OPT-04)
  - Parallel tool call latency delta (OPT-06)
  - Overall: relevance F1, RAG faithfulness, calibration Brier score
- **Acceptance:** page loads and every number is sourced from a `bench_runs` or `eval_runs` row (not hardcoded).
- **Depends on:** all OPT-nn, EVAL-03, EVAL-04, EVAL-06.

---

# Cross-cutting: Guardrails

Applied by IMP-04, BRIEF-02, CHAT-03. All live under `backend/app/guardrails/`.

### GRD-01 — Directional-language classifier

- **Files:** `backend/app/guardrails/directional.py`.
- **Action:** A hybrid lexical + LLM guardrail.
  1. Lexical check: reject drafts containing any of these tokens (case-insensitive, word-boundary): `buy`, `sell`, `hold`, `add`, `trim`, `overweight`, `underweight`, `long`, `short`, `bullish`, `bearish` used as a stance, `consider`, `should`, `recommend`, `advise`.
  2. LLM check (only if lexical passes): a small Haiku call asking "does this text recommend a specific action to the reader? YES/NO with 1-line rationale."
  3. Both checks must pass for the draft to be accepted.
- **Acceptance:**
  - Draft "the Fed cut suggests you should buy TLT" → rejected.
  - Draft "higher rates historically compress duration-sensitive valuations by 3-5% over 30 days" → accepted.
  - `pytest backend/tests/guardrails/test_directional.py` covers 30 hand-crafted examples with ≥ 95% accuracy.

### GRD-02 — Citation-required validator

- **Files:** `backend/app/guardrails/citations.py`.
- **Action:** For any structured output with a `citations` field, verify:
  - `len(citations) >= 1`.
  - Every citation's `url` is one of the citation stubs passed into the prompt (prevents hallucinated citations).
  - Every citation `quote` is a substring of the corresponding source news body (allowing whitespace normalization).

### GRD-03 — Out-of-scope refusal

- **Files:** `backend/app/guardrails/scope.py`.
- **Action:** For chat inputs, an intent classifier that detects out-of-scope requests: tax advice, legal advice, personal financial planning ("should I buy a house?"), medical questions. Returns a canned refusal with a link to a licensed-professional suggestion.
- **Acceptance:** covers 10 canonical out-of-scope questions with ≥ 90% detection.

---

# Environment variables — authoritative list

The `.env.example` files (BOOT-07) mirror this list.

### Backend (`backend/.env`)

```
# --- Core ---
FLASK_ENV=development                     # legacy name, kept for compatibility until fully removed
SECRET_KEY=<generate-in-prod>             # required in prod; ephemeral in dev
ALLOWED_ORIGINS=http://localhost:3000     # comma-separated
DATABASE_URL=postgresql+asyncpg://...     # Supabase Postgres

# --- Supabase auth ---
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_JWT_AUD=authenticated

# --- LLM (OpenRouter, free tier) ---
OPENROUTER_API_KEY=<key>                   # free to obtain
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
LLM_TEXT_MODEL_FAST=meta-llama/llama-3.3-70b-instruct:free
LLM_TEXT_MODEL_THOROUGH=deepseek/deepseek-chat-v3.1:free
# JSON string of {model_id: rpm_cap}; free tier is typically 20 RPM
LLM_RATE_LIMIT_RPM={"default":20}
# Fallback paid cap ONLY if free tier degrades — leave at 0 to disable paid
LLM_DAILY_BUDGET_USD=0.0

# --- Embeddings (local, free) ---
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DEVICE=cpu                       # 'cpu' or 'cuda' if available

# --- News sources ---
NEWSAPI_KEY=<key>                          # optional; empty → skipped
MARKETAUX_KEY=<key>                        # optional
GDELT_ENABLED=true
EDGAR_USER_AGENT=Lumen contact@example.com
RSS_FEEDS=https://feeds.reuters.com/reuters/businessNews,https://...

# --- Market data ---
YFINANCE_CACHE_PATH=/app/price_cache

# --- Vector store ---
CHROMA_PATH=/app/chroma_data

# --- Observability (pick ONE — both are free at portfolio scale) ---
# Option A: LangSmith (free tier: 5,000 traces/month)
LANGSMITH_API_KEY=<key>
LANGSMITH_PROJECT=lumen-dev
LANGSMITH_TRACING=true
# Option B: Langfuse (self-hostable free, or free cloud tier)
LANGFUSE_PUBLIC_KEY=<key>
LANGFUSE_SECRET_KEY=<key>
LANGFUSE_HOST=https://cloud.langfuse.com
LOG_LEVEL=INFO

# --- Scheduler ---
INGEST_INTERVAL_MINUTES=15
CLUSTER_SIMILARITY_THRESHOLD=0.87
PREFILTER_THRESHOLD=0.35
```

### Frontend (`frontend/.env.local`)

```
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
NEXT_PUBLIC_SUPABASE_URL=https://<project>.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon-key>
```

---

# Cross-cutting acceptance gates

Before declaring v0.1 (MVP) shipped:

1. Every phase 0–6 module marked `- [x]`.
2. Deployed at a public URL, reachable from a fresh browser.
3. Demo user (`demo@lumen.app`) works end-to-end without signup.
4. Zero `guardrail_violations` on the last 50 impact assessments (auditable via `impact_assessments.guardrail_violations`).
5. `pytest backend/tests -q` all green.
6. `npm run build && npm test` all green.
7. CI pipeline passing on `v2/intelligence-agent`.

Before declaring v0.2:

8. Phases 7 + 8 modules marked `- [x]`.
9. Public `/track-record` shows ≥ 25 resolved predictions with reasonable calibration.
10. Public `/quality` shows relevance F1 ≥ 0.70, RAGAS faithfulness ≥ 0.75.
11. LangSmith public trace shareable from any briefing card.

Before declaring v1.0:

12. Phases 9 + 10 modules marked `- [x]`.
13. Landing Lighthouse ≥ 90.
14. README + ARCHITECTURE + EVALS docs complete.
15. All acceptance criteria for `PRD.md` §9 (both product success and portfolio-piece success) satisfied.

---

# Working with Claude Code on this list

- One module per session is ideal. Hand Claude the module ID and let it open only the files listed under that module.
- Reference the `Depends on` field — if a dep isn't done, fix that first.
- Update this file at the end of each session: tick the checkbox and add a one-line deviation note under the module if reality diverged.
- When a task reveals a sibling problem out of scope, add it as a new entry (next free ID in that phase) rather than expanding the current task.
- If a module is blocked by a decision that requires human judgment (e.g., "which of these two vector-store libraries?"), stop and ask before proceeding. Do not silently pick.
- **PRD is the veto document.** If a proposed change violates the PRD's non-goals or product principles, escalate rather than accommodate.

---

# Handoff Protocol (mandatory)

Context windows fill. Sessions end mid-work. To make handoffs cheap, every session follows this protocol.

### The three canonical files

Every session — starting *and* ending — deals with exactly three files:

1. **`PRD.md`** — read at session start. Refreshes the product intent, non-goals, and design principles. Do not modify unless a formal PRD amendment is being made.
2. **`BUILD.md`** — read the specific module block referenced by `HANDOFF.md`. Do not read modules you're not working on.
3. **`HANDOFF.md`** — the source of truth for "where are we." Read it first on session start; update it before session end.

### The rule

> **No session ends without an updated `HANDOFF.md`.**
> If the session ran out of context before it finished a module, `HANDOFF.md` states exactly which lines of code / which files are in-flight so the next session can resume without archaeology.

### `HANDOFF.md` template

Every field is required. Empty fields must say `none` or `n/a` — don't omit.

```markdown
# Handoff — Lumen Intelligence Agent

**Branch:** v2/intelligence-agent
**Base:** refactor
**Last updated:** YYYY-MM-DD (session <n>)
**Progress:** <done>/<total> modules complete

## Next module
**ID:** BOOT-03
**Title:** Port Config and auth utilities
**Depends on:** BOOT-02 ✅
**Read:** BUILD.md → "BOOT-03" section (the only module block to read)

## Last session
- **Session goal:** Implement BOOT-02
- **Completed:** BOOT-02 (FastAPI scaffolding, /health returns 200, alembic init clean)
- **Files touched:** backend/app/main.py, backend/pyproject.toml, backend/requirements.txt, backend/alembic.ini
- **Migrations added:** none
- **Tests added:** backend/tests/test_health.py (2 tests, passing)
- **In-flight (unfinished) work:** none
- **Deviations from BUILD.md:** none

## Environment state
- Backend: `uvicorn app.main:app` starts cleanly on :8000
- Frontend: not touched this session
- Database: local Postgres reachable at localhost:5432; `alembic upgrade head` clean
- Vectors: not initialized yet
- Tests: `pytest` — 2 passing, 0 failing
- CI: green

## Open questions / blockers
- none
- (or: "need user decision on X before starting Y")

## Rules for next session
- Read HANDOFF.md first (this file).
- Read PRD.md.
- Read only the BUILD.md block for the "Next module" ID above.
- Do NOT re-read prior modules' files unless the module spec explicitly needs them.
- Do NOT expand scope. Match Acceptance criteria literally.
- Before ending: update this HANDOFF.md, tick the completed module's checkbox in BUILD.md, commit.
```

### HP-01 — Create `HANDOFF.md` (very first module of the new branch) ✅

- [x] File created at repo root with the template above, filled in for BOOT-01 as the next module. Progress at 0/60. In-flight: none. Committed in session 0 alongside PRD.md and BUILD.md.

### HP-02 — CI check: HANDOFF.md protocol enforcement ✅

- [x] **Files:** `.github/workflows/handoff-check.yml`.
- **Action:** GitHub Actions workflow that runs on push to `v2/intelligence-agent` + `feat/**` and on PRs targeting `v2/intelligence-agent`. Enforces the handoff protocol with two hard checks and two soft checks:
  1. **Hard: file exists.** `HANDOFF.md` present at repo root, else fail.
  2. **Hard: required sections present.** `**Last updated:**`, `## Next module`, `## Last session`, `## Environment state` — missing any is a failure.
  3. **Soft: freshness.** `Last updated:` date parsed; if > 14 days old, `::warning` emitted (does not block).
  4. **Soft: code-without-handoff.** If the push/PR changed `backend/` or `frontend/` files but not `HANDOFF.md`, `::warning` emitted (does not block). Handles new-branch pushes by falling back to a merge-base against `origin/refactor`.
- **Acceptance:** ✅ Workflow file exists. Once pushed to a triggering branch, the Actions tab shows a "Handoff freshness" job with a green check on well-formed HANDOFF, warnings on stale/missed-update, hard fail on missing/malformed HANDOFF.
- **Depends on:** HP-01.

### Automation guardrails on the handoff — installed

- **HP-02 (CI check):** installed. Warnings and hard-fail contract described above.
- **Pre-commit hook** (still deferred to BOOT-08 unless promoted): would warn locally when a commit touches `backend/` or `frontend/` without touching `HANDOFF.md`. HP-02's CI check catches this at push time already; the local hook is a convenience, not a correctness requirement.

### What NOT to put in `HANDOFF.md`

- Full code diffs (git has them).
- Long design rationales (belong in `BUILD.md` deviation notes or a new ADR under `docs/adr/`).
- Anything user-facing (that's `PRD.md`).
- Anything longer than one screen. If it doesn't fit, it's not a handoff — it's a status report, and you're doing it wrong.

The handoff is a **pointer**, not a summary. The next session reconstructs context from `PRD.md` + the pointed-to `BUILD.md` module + the pointed-to code, not from prose in `HANDOFF.md`.
