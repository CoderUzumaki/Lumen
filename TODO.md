# Lumen — Stabilization & Build-Out Plan

A modular, Claude-Code-executable to-do list. Each task is self-contained: scope, files, acceptance criteria, and dependencies are stated so you can hand any single task to a fresh session without context.

## How to use this document

- Tasks are grouped into phases. Earlier phases unblock later ones — do not skip ahead.
- Each task has a stable ID (e.g. `SEC-01`). Reference it in commits, PRs, and Claude prompts: *"Implement TODO `SEC-01` per TODO.md."*
- A task is **done** only when every line under **Acceptance** is satisfied and a smoke test passes.
- Mark progress inline: `- [ ]` → `- [x]`.
- If a task grows beyond ~1 day of work, split it before starting.

---

## Phase 0 — Repo Hygiene (no behavior change)

Low-risk cleanup. Should be done first so later diffs stay small and reviewable.

### HYG-01 — Move one-off scripts out of `backend/` ✅
- [x] Moved 8 scripts to `backend/scripts/` via `git mv` (history preserved). Added `backend/scripts/__init__.py` and `backend/scripts/README.md` documenting purpose, idempotency, and destructiveness per script. Fixed `sys.path.insert` lines so `python -m scripts.<name>` from `backend/` still resolves `app`/`models`/etc. (Note: `backend/test_*.py` files remain at root for now — they'll move under `tests/` in `TEST-01`.)

### HYG-02 — Delete the committed empty database ✅
- [x] Deleted `backend/lumen.db` (0 bytes). Added `*.db`, `*.sqlite`, `*.sqlite3` to `backend/.gitignore`. `instance/` was already ignored.

### HYG-03 — Strip debug `console.log` / emoji logging from the frontend ✅
- [x] Added `frontend/src/lib/logger.ts` — `debug`/`info` no-op in production; `warn`/`error` always emit. Converted 65 `console.log` calls across 13 files to `logger.debug` and injected the import (auto-script + manual fix for three landing files where `"use client"` directive sequencing was wrong). `grep -rn "console.log" frontend/src` excluding `lib/logger.ts` returns 0.

### HYG-04 — Replace `print()` with structured logging in the backend ✅
- [x] Added `backend/utils/logging_config.py` with `configure_logging()` (driven by `LOG_LEVEL`) and a `mask_secret()` helper. Wired it into `app.py` at startup. Converted 169 `print()` calls to `logger.<level>(...)` across 16 production modules (chose level by emoji prefix: ❌ → error, ⚠️ → warning, else info). Quieted noisy third-party loggers. Replaced unsafe `OPENROUTER_API_KEY[:15]` prints in `utils/openrouter.py` with `mask_secret(...)` (now shows only last 4 chars). All files parse cleanly. `grep -rn "^\s*print(" backend --include="*.py"` excluding `scripts/` and `test_*.py` returns 0.

### HYG-05 — Resolve duplicate analytics blueprint registration ✅ (done — naming clarified)
- [x] **Files**: [backend/routes/__init__.py:9-21](backend/routes/__init__.py), [backend/routes/analytics.py](backend/routes/analytics.py), [backend/routes/ai_analytics.py](backend/routes/ai_analytics.py)
- **Outcome**: On inspection the two blueprints serve **different URL prefixes** (`/analytics/*` vs `/api/analytics/*`) and are both used by the frontend — not a real duplicate. Renamed the `ai_analytics.py` blueprint variable from `analytics_bp` → `ai_analytics_bp` and its Flask name from `'analytics'` → `'ai_analytics'`, and documented the distinction in `routes/__init__.py`. No URL changes.

---

## Phase 1 — Configuration & Secrets

Foundation for everything else. After this, no value that varies by environment should be hardcoded.

### CFG-01 — Centralize backend configuration ✅
- [x] Rewrote `backend/config.py` to expose absolute paths (`DATABASE_PATH`, `DATABASE_URI`, `CHROMA_DB_PATH`), LLM identifiers (`LLM_VISION_MODEL`, `LLM_TEXT_MODEL`, `LLM_EMBEDDING_MODEL`), OpenRouter URLs (`OPENROUTER_BASE_URL`, `OPENROUTER_CHAT_URL`), CORS allowlist (`ALLOWED_ORIGINS`), and `DEFAULT_CURRENCY`. Removed all hardcoded constants from `models/database.py`, `routes/chat.py`, `ai/sql_agent.py`, `ai/query_classifier.py`, `ai/hybrid_query_engine.py`, `ai/rag_system.py`, `ai/anomaly_detection.py`, `ai/forecasting_agent.py`, `ai/analytics_orchestrator.py`, `utils/openrouter.py`, and `scripts/backfill_chromadb.py`. `Config.validate()` runs at startup in `app.py` and raises on missing `OPENROUTER_API_KEY`. The acceptance grep now returns only the two `config.py` defaults; smoke tests confirm validate() raises when the key is unset.
- **Deviation from spec**: The TODO asked for a single `LLM_MODEL`, but OCR (`utils/openrouter.py`) needs a vision-capable model and the chat/SQL/anomaly call sites need a text-only model. Split into `LLM_VISION_MODEL` and `LLM_TEXT_MODEL` so each path can be sized independently (cheap nemotron for vision, claude for reasoning).
- **Latent bug fixed in passing**: SQLAlchemy was writing to `sqlite:///lumen.db` (resolved to `backend/lumen.db` via cwd) while the AI agents read `instance/lumen.db` — **two different SQLite files**. Both now resolve to the same absolute `Config.DATABASE_PATH`, and `instance/` is auto-created at import time.

### CFG-02 — Strengthen `SECRET_KEY` handling ✅
- [x] Removed the `'dev-secret-key-change-in-production'` fallback. New `_resolve_secret_key()` helper: if the env var is set, uses it; otherwise generates a per-process `secrets.token_urlsafe(32)` ephemeral key **only when `FLASK_ENV=development`** (and emits both a `warnings.warn` to stderr and a `logger.warning`); in any other env returns `None`. `Config.validate()` now lists `SECRET_KEY` among required values, so production startup fails fast with `Missing required environment variable(s): SECRET_KEY`. `app.py` wires `Config.SECRET_KEY` into `app.config["SECRET_KEY"]` so Flask actually uses it (Flask was silently going without before). Verified all four cases: dev+unset (ephemeral + warning), dev+set, prod+unset (raises), prod+set.

### CFG-03 — Frontend env configuration ✅
- [x] Found a name mismatch in passing: `next.config.js` was declaring `NEXT_PUBLIC_API_URL` (with a `http://localhost:5000` fallback) while `lib/api/client.ts` actually reads `NEXT_PUBLIC_BACKEND_URL`. The `_API_URL` value was dead. Settled on `NEXT_PUBLIC_BACKEND_URL` as the single canonical name. `next.config.js` now throws synchronously at module-load if any name in `requiredPublic` is missing (verified: `node next.config.js` with the var unset prints `Missing required environment variable(s): NEXT_PUBLIC_BACKEND_URL. Copy frontend/.env.example to frontend/.env.local...`). `client.ts` no longer has a fallback either — it throws if the bundle ever loads without the value baked in. Added `frontend/.env.example` documenting `NEXT_PUBLIC_BACKEND_URL` (the only public var read today). `.gitignore` already covers `.env*.local`.

### CFG-04 — Lock CORS to the configured frontend origin ✅
- [x] `app.py` now calls `CORS(app, origins=Config.ALLOWED_ORIGINS, supports_credentials=True)`. The startup log line records the active allowlist. `Config.ALLOWED_ORIGINS` (added in CFG-01) parses a comma-separated `ALLOWED_ORIGINS` env var, falling back to `FRONTEND_URL` (which itself defaults to `http://localhost:3000`). Verified parsing for the default, multi-origin, and FRONTEND_URL-override cases. `supports_credentials=True` is set so Phase-2 auth (cookies / Authorization headers on cross-origin) works without another config change. Full HTTP-level smoke (curl preflight from a non-allowlisted origin → no `Access-Control-Allow-Origin` header) requires the backend deps installed and the server running — verify after `pip install -r requirements.txt`.

---

## Phase 2 — Authentication & Multi-Tenancy

The single biggest correctness gap. Until this is done, every API endpoint leaks data.

### AUTH-01 — Pick an auth strategy and document it ✅
- [x] **Decision: Supabase Auth**, verified server-side via JWKS (not the Python `supabase` SDK — `pyjwt[crypto]` is the right shape). Documented in [docs/AUTH.md](docs/AUTH.md): rationale vs NextAuth/Clerk, what Supabase owns vs Lumen owns, JWT claim contract, JWKS verification flow + library choice, frontend session lifecycle, required env vars (frontend: `NEXT_PUBLIC_SUPABASE_URL` + `NEXT_PUBLIC_SUPABASE_ANON_KEY`; backend: `SUPABASE_URL` + `SUPABASE_JWT_AUD`), demo-data migration plan (seeded `user_id='123'` → fixed dev UUID), and what's deliberately *not* covered (RBAC, service-to-service auth). One correction from earlier audit: Supabase was **not actually installed** — env vars existed but no library. AUTH-02 will add the deps.

### AUTH-02 — Backend JWT verification middleware ✅
- [x] Added `PyJWT[crypto]==2.8.0` to `backend/requirements.txt`. Added `SUPABASE_JWT_AUD` (default `"authenticated"`) to `Config`; documented `SUPABASE_URL` becoming required at AUTH-03. New `backend/utils/auth.py` exposes `require_auth`, `verify_token`, and the typed `TokenError` / `AuthConfigError` exceptions. JWKS lookup uses `PyJWKClient` behind a thread-safe lazy initializer (no JWKS fetch at import time; cached for an hour; auto-refresh on kid miss). Verification enforces `algorithms=["RS256","ES256"]`, expected audience + issuer, required `exp`/`sub`/`aud`/`iss` claims, and explicitly rejects `role=anon`. All errors map to distinct response codes (`missing_token`, `invalid_token`, `expired_token`, `invalid_audience`, `invalid_issuer`, `missing_claim`, `wrong_role`, `unknown_key`, `jwks_unreachable`) but the public JSON body says only `{"error":"unauthorized","code":...}`. OPTIONS preflight passes through untouched so Flask-CORS can respond. Verified end-to-end with a synthetic JWKS in a 9-case smoke harness (no header, non-Bearer, valid token, expired, wrong aud, wrong iss, anon role, tampered signature, OPTIONS preflight) — all pass. Decorator is **not** applied to any route yet; that's AUTH-03.

### AUTH-03 — Apply `@require_auth` to every data route ✅
- [x] Decorated **31 non-health routes** across `routes/ocr.py`, `routes/batch.py`, `routes/chat.py`, `routes/analytics.py`, `routes/ai_analytics.py`, `routes/database_query.py`, `routes/email_config.py`. Removed every `data.get('user_id')` / `request.args.get('user_id')` / `request.form.get('user_id')` / `request.json.get('user_id')` and replaced with `g.user_id`. Acceptance grep returns 0 matches. The legacy `GET /transactions/<user_id>` route still accepts the path segment so unfixed frontend code doesn't 404 between AUTH-03 and AUTH-05, **but the value is ignored** — `g.user_id` is the only authoritative identity (hitting `/transactions/anyone-else` while authenticated as A returns A's data). Closed two latent security bugs in passing: (a) `PUT /transactions/<transaction_id>` previously updated any transaction by id with no user check — now scoped by `user_id=g.user_id` and 404s on cross-user access; (b) `POST /api/analytics/insights/<id>/read` previously marked any insight read — now no-ops + 404 if it doesn't belong to the caller. Exempt from `@require_auth`: `routes/health.py` and `ai_analytics.py:health_check` (intentional, per spec). The 3 unimplemented Gmail OAuth stubs are also decorated so they don't become public when the body is filled in.

**Known broken until AUTH-04/05 land**: the frontend still calls these endpoints without an `Authorization` header and will get 401 on every request. That's the intended sequencing per the TODO.

### AUTH-04 — Frontend auth context + protected routes
- [ ] **Files**: new `frontend/src/lib/auth/context.tsx`, new `frontend/src/app/(auth)/login/page.tsx`, [frontend/src/lib/api/client.ts](frontend/src/lib/api/client.ts), `frontend/src/app/dashboard/`, `frontend/src/app/chatbot/`, `frontend/src/app/analytics/`, `frontend/src/app/ai-analytics/`
- **Action**: Implement a `useAuth()` hook backed by the chosen provider. Add a real `/login` page. Wrap `/dashboard`, `/chatbot`, `/analytics`, `/ai-analytics` in an auth guard that redirects to `/login` when no session exists. The API client attaches the access token to every request via an `Authorization` header.
- **Acceptance**: Visiting `/dashboard` while logged out redirects to `/login`. Successful login returns to the originally requested page. The API client no longer accepts a `userId` argument anywhere.
- **Depends on**: AUTH-02, CFG-03.

### AUTH-05 — Remove every hardcoded `"123"` from the frontend
- [ ] **Files**: every `*.tsx` under `frontend/src/`, particularly [lib/api/client.ts](frontend/src/lib/api/client.ts) (14 occurrences), [section-cards.tsx:37](frontend/src/components/section-cards.tsx), [chatbotContent.tsx:294](frontend/src/app/chatbot/chatbotContent.tsx), [uploadDialog.tsx:70](frontend/src/components/uploadDialog.tsx), [analyticsCards.tsx:97](frontend/src/components/analytics/analyticsCards.tsx)
- **Action**: Delete every `"123"` default. API functions should no longer take a `userId` parameter — the backend resolves it from the token.
- **Acceptance**: `grep -rn "['\"]123['\"]" frontend/src` returns 0 matches. `grep -rn "userId\s*=\s*['\"]" frontend/src` returns 0 matches.
- **Depends on**: AUTH-03, AUTH-04.

### AUTH-06 — Encrypt IMAP passwords at rest
- [ ] **Files**: [backend/models/__init__.py:128](backend/models/__init__.py), [backend/routes/email_config.py](backend/routes/email_config.py), new `backend/utils/crypto.py`
- **Action**: Add a Fernet-based encryption helper keyed by `EMAIL_ENCRYPTION_KEY` (32 url-safe bytes from env). Encrypt on write, decrypt only inside the email-polling service. Write a one-off migration script under `backend/scripts/` that encrypts any existing plaintext rows.
- **Acceptance**: Newly saved passwords stored as `gAAAA...` ciphertext. `EmailConfig.imap_password` never returned in API responses (even masked). Polling service still authenticates successfully.
- **Depends on**: HYG-01, CFG-01.

---

## Phase 3 — Database Safety

### DB-01 — Parameterize all SQL in the SQL agent
- [ ] **Files**: [backend/ai/sql_agent.py:92,104,112](backend/ai/sql_agent.py)
- **Action**: Replace every f-string SQL with parameterized queries (`?` placeholders + tuple args). For LLM-generated SQL, add an allowlist: only `SELECT` statements against `transactions` / `receipts` tables, only the authenticated user's `user_id` injected by the server.
- **Acceptance**: `grep -rn "f\".*SELECT\|f'.*SELECT" backend/ai` returns 0 matches. Attempting `; DROP TABLE` via the chat endpoint fails validation before execution.
- **Depends on**: AUTH-03.

### DB-02 — Use SQLAlchemy session everywhere instead of raw sqlite3
- [ ] **Files**: [backend/ai/sql_agent.py](backend/ai/sql_agent.py), [backend/routes/chat.py](backend/routes/chat.py), any module using `sqlite3.connect`
- **Action**: Route every query through SQLAlchemy `db.session` so connection management and `user_id` scoping is consistent.
- **Acceptance**: `grep -rn "sqlite3.connect" backend --include="*.py"` returns 0 matches (except scripts).
- **Depends on**: DB-01.

### DB-03 — Drop or implement the orphan tables
- [ ] **Files**: [backend/models/__init__.py](backend/models/__init__.py) — `Receipt`, `Anomaly`, `Insight`, `EmbeddingMeta`
- **Action**: For each model, decide: (a) wire it into a real route, or (b) delete it. If it stays, add at least one route that reads from it.
- **Acceptance**: Every model in `models/__init__.py` is referenced by at least one route handler.
- **Depends on**: none.

### DB-04 — Strengthen duplicate-invoice detection
- [ ] **Files**: [backend/utils/save_transaction.py:12-15](backend/utils/save_transaction.py)
- **Action**: Match on `(user_id, vendor_name, invoice_number, total_amount, date)` instead of just `(vendor_name, invoice_number)`. Return an explicit `{"duplicate": true, "existing_id": ...}` response so the frontend can show a clear message.
- **Acceptance**: Uploading the same invoice twice is rejected with a 409 and a useful message. Different invoices with the same number from different vendors are stored separately.
- **Depends on**: none.

### DB-05 — Add rate limiting on LLM-backed endpoints
- [ ] **Files**: [backend/app.py](backend/app.py), [backend/routes/ocr.py](backend/routes/ocr.py), [backend/routes/chat.py](backend/routes/chat.py), [backend/routes/ai_analytics.py](backend/routes/ai_analytics.py)
- **Action**: Add `flask-limiter`. Default: 60/min per user. Tighter limits on `/extract` (10/min) and `/chat` (30/min).
- **Acceptance**: 11th `/extract` call within a minute returns 429. Limits are per-user (not global).
- **Depends on**: AUTH-03.

---

## Phase 4 — Stabilize Existing Features

### FEAT-01 — Remove the "year=2024 / user=123" assumption from analytics
- [ ] **Files**: [frontend/src/app/analytics/analyticsContent.tsx:45](frontend/src/app/analytics/analyticsContent.tsx), [frontend/src/components/analytics/analyticsCards.tsx:97](frontend/src/components/analytics/analyticsCards.tsx), [backend/routes/analytics.py](backend/routes/analytics.py)
- **Action**: Default year = current year. When there is no data, render a clear empty state with a CTA ("Upload your first invoice"), not a broken chart.
- **Acceptance**: A brand-new user lands on `/analytics`, sees a friendly empty state, and can click through to upload. No 500s, no `NaN` axes.
- **Depends on**: AUTH-05.

### FEAT-02 — Make currency configurable per user
- [ ] **Files**: [backend/models/__init__.py](backend/models/__init__.py) (`User` model — add `currency` column), [backend/ai/rag_system.py:63](backend/ai/rag_system.py), [frontend/src/components/animatedListItemUse.tsx:203](frontend/src/components/animatedListItemUse.tsx), new currency-formatting helper in `frontend/src/lib/format.ts`
- **Action**: Add a `currency` column to the user profile (default `INR`). Every monetary display calls `formatCurrency(amount, user.currency)`. RAG and LLM prompts also receive the configured currency.
- **Acceptance**: Switching the user's currency to `USD` in settings causes every amount across the UI and chatbot responses to render as `$` instead of `₹`. No "INR" string literal remains.
- **Depends on**: AUTH-04.

### FEAT-03 — Real error UI for the AI Analytics auto-load
- [ ] **Files**: [frontend/src/app/ai-analytics/aiAnalyticsContent.tsx:18-54](frontend/src/app/ai-analytics/aiAnalyticsContent.tsx)
- **Action**: Replace `console.error` on failure with an inline error card ("Analysis failed: <reason>. Retry"). Move auto-trigger behind a feature flag — `analyze` should be an explicit user action by default.
- **Acceptance**: When the backend returns 500, the page renders a visible error with a retry button. When it succeeds, results stream in normally.
- **Depends on**: none.

### FEAT-04 — Restore or remove the commented chatbot auth check
- [ ] **Files**: [frontend/src/app/chatbot/page.tsx:5-45](frontend/src/app/chatbot/page.tsx)
- **Action**: After AUTH-04 lands, delete the commented next-auth block entirely. The route guard from AUTH-04 replaces it.
- **Acceptance**: No commented-out code remains in `page.tsx`. Visiting `/chatbot` while logged out redirects to `/login`.
- **Depends on**: AUTH-04.

### FEAT-05 — Restore or delete the commented `FileUploadForm`
- [ ] **Files**: [frontend/src/app/dashboard/dashboardContent.tsx:55-57](frontend/src/app/dashboard/dashboardContent.tsx)
- **Action**: Decide whether the dashboard should expose direct uploads (vs. only the modal `UploadDialog`). If yes, wire it. If no, delete the commented block.
- **Acceptance**: No commented JSX in `dashboardContent.tsx`.
- **Depends on**: none.

### FEAT-06 — Implement or remove the stubbed composer actions
- [ ] **Files**: [frontend/src/components/chatbot/ComposerActionsPopover.tsx:40-101](frontend/src/components/chatbot/ComposerActionsPopover.tsx)
- **Action**: Each of the 10 buttons currently logs to console. Either (a) wire them to real behavior, or (b) hide the ones we won't build now. Recommended: keep `Add photo` (works with existing OCR), `Deep research` (web search), and `Templates`; hide the rest behind a feature flag.
- **Acceptance**: Every visible button performs a real action. No remaining `console.log` stubs in the file.
- **Depends on**: none.

---

## Phase 5 — Real AI/ML (replace LLM-only with the advertised pipeline)

Docs promise ARIMA/Prophet forecasting, Isolation Forest anomalies, and Google Cloud Vision OCR. Today, everything is an LLM call. Pick whichever pieces actually matter and build them properly.

### AI-01 — Anomaly detection: real model, not an LLM prompt
- [ ] **Files**: new `backend/ai/anomaly.py`, [backend/routes/ai_analytics.py](backend/routes/ai_analytics.py) (`/anomalies` endpoint)
- **Action**: Train a per-user Isolation Forest on `(amount, vendor, day_of_month, day_of_week, category)`. Persist the model under `backend/models_data/{user_id}/anomaly.joblib`. Retrain nightly via a scheduled job. The endpoint returns the model's flagged outliers with a contribution explanation.
- **Acceptance**: With a seeded dataset containing an obvious outlier (10x normal vendor amount), the endpoint flags it. No LLM call is made on the `/anomalies` path.
- **Depends on**: DB-01, AUTH-03.

### AI-02 — Recurring-payment detection
- [ ] **Files**: new `backend/ai/recurring.py`, [backend/routes/ai_analytics.py](backend/routes/ai_analytics.py) (`/patterns` endpoint)
- **Action**: For each `(user, vendor)` group, detect periodicity by computing the median inter-event interval and its variance. Flag as recurring if variance/median < 0.2 and at least 3 occurrences. Return next-expected-date.
- **Acceptance**: A user with monthly rent payments sees rent flagged as recurring with a correct next-month prediction.
- **Depends on**: DB-01.

### AI-03 — Forecasting endpoint (ARIMA or Prophet)
- [ ] **Files**: new `backend/ai/forecast.py`, [backend/routes/ai_analytics.py](backend/routes/ai_analytics.py) (`/forecast` endpoint)
- **Action**: Aggregate per-user spend by week. Fit Prophet (or `statsmodels` ARIMA if Prophet's deps are too heavy) and return next-4-weeks forecast with confidence intervals.
- **Acceptance**: Endpoint returns 4 forecasted values with upper/lower bounds. Frontend `forecast` card renders a fan chart.
- **Depends on**: AI-02 (shares some helpers).

### AI-04 — Honest OCR story
- [ ] **Files**: [backend/routes/ocr.py](backend/routes/ocr.py), [README.md](README.md), [API_DOCS.md](API_DOCS.md), [ARCHITECTURE.md](ARCHITECTURE.md)
- **Action**: Either (a) integrate Google Cloud Vision as the primary OCR path with the OpenRouter vision model as fallback, or (b) update all docs to truthfully describe the OpenRouter-only pipeline. Pick one and commit.
- **Acceptance**: Docs and code agree about which OCR provider runs in production.
- **Depends on**: CFG-01.

### AI-05 — RAG: deduplicate and version the vector store
- [ ] **Files**: [backend/ai/rag_system.py](backend/ai/rag_system.py), [backend/utils/save_transaction.py:53-55](backend/utils/save_transaction.py)
- **Action**: Use a deterministic doc id (`f"tx:{user_id}:{transaction_id}"`) so re-saves overwrite instead of duplicating. Surface RAG embedding failures to the user (don't silently swallow). Add a `chroma_db_version` config so we can migrate when embeddings change.
- **Acceptance**: Saving the same transaction twice results in one ChromaDB doc, not two. A failed embedding returns a 502 (not a silent 200).
- **Depends on**: CFG-01.

---

## Phase 6 — New Features (only after Phases 0–3 are green)

These are the ideas worth building once the foundation is real. Each is independently shippable.

### NEW-01 — Budgets & alerts
- **Why**: Closes the loop from "tracking" to "deciding". A user sets a monthly cap per category; the app warns at 80% and blocks/notifies at 100%.
- **Files**: new `backend/routes/budgets.py`, new `Budget` model, new `frontend/src/app/budgets/page.tsx`
- **Action**: CRUD for budgets keyed by `(user_id, category, month)`. A nightly job evaluates spend vs. budget; over-threshold events create `Notification` rows and (optionally) send email.
- **Acceptance**: User can create/edit/delete budgets. Dashboard surfaces a "Budget health" card. Crossing 80% triggers an in-app notification within 24h.

### NEW-02 — Vendor & category management UI
- **Why**: Categorization is currently invisible to users; cleaning it up is the single biggest lever for analytics quality.
- **Files**: new `frontend/src/app/vendors/page.tsx`, new endpoints under `backend/routes/vendors.py`
- **Action**: List all vendors with transaction counts and total spend. Allow merging duplicates (`Amazon`, `AMAZON.IN`, `Amzn`) and overriding category. Re-run analytics after merge.
- **Acceptance**: Merging two vendors moves all transactions to the surviving vendor and recomputes per-vendor metrics.

### NEW-03 — Receipt search via RAG
- **Why**: The vector store exists but no end-user UI uses it. A natural-language search ("dinner with Sarah in March") is the single most demoable AI feature.
- **Files**: new `frontend/src/app/search/page.tsx`, [backend/ai/rag_system.py](backend/ai/rag_system.py)
- **Action**: A search input that queries ChromaDB and renders the top-K matching transactions with score and excerpt.
- **Acceptance**: Searching "coffee last week" returns coffee-related transactions from the last 7 days, ranked by relevance.

### NEW-04 — Email-driven ingest pipeline (end-to-end)
- **Why**: Email config UI exists but the polling → parse → save loop is unfinished. Closing this is the highest-value automation.
- **Files**: [backend/utils/email_poller.py](backend/utils/email_poller.py), new `backend/utils/email_parser.py`, [backend/routes/email_config.py](backend/routes/email_config.py)
- **Action**: For each configured account, fetch unread receipts (heuristic: subject/body keywords + attached PDF), run them through OCR, save, mark read. Show ingest status per account in the UI.
- **Acceptance**: Sending a test invoice email to the configured account causes a new transaction to appear within 5 minutes. Failed ingests surface a per-row error in the UI.

### NEW-05 — Export presets & scheduled reports
- **Why**: One-off CSV export already exists; scheduled email of last-month summary is a small extension with high stickiness.
- **Files**: extend [backend/routes/invoices.py (export)](backend/routes/invoices.py), new `backend/scripts/scheduled_reports.py`, frontend settings page
- **Action**: User chooses a frequency (weekly/monthly) and recipient email. A scheduled job emails the rendered summary PDF + CSV.
- **Acceptance**: Setting "monthly to me@example.com" causes a report email at the start of each month with the prior month's data.

### NEW-06 — Multi-user workspaces (org accounts)
- **Why**: Once auth is real, multi-tenant teams are the obvious next step for SMB users.
- **Files**: new `Workspace`, `WorkspaceMember` models; `user_id` scoping replaced by `workspace_id`; invite flow
- **Action**: Every transaction is owned by a workspace. Users belong to N workspaces with roles (owner/editor/viewer). All existing queries become workspace-scoped.
- **Acceptance**: A user invited as `viewer` can read but not upload or edit. Switching the active workspace changes every page's data.
- **Depends on**: AUTH phase complete.

---

## Phase 7 — Testing & CI

### TEST-01 — Backend test harness
- [ ] **Files**: new `backend/tests/` (replacing the loose `test_*.py` in `backend/` root), `backend/conftest.py`
- **Action**: Move the existing `test_analytics_api.py`, `test_chart_api.py`, `test_patterns.py`, `test_recurring_data.py` into `backend/tests/`. Add `pytest` + `pytest-flask`. Each test runs against an in-memory SQLite with seeded fixtures.
- **Acceptance**: `cd backend && pytest` runs all tests green. CI fails on any test failure.
- **Depends on**: HYG-01.

### TEST-02 — Frontend test harness
- [ ] **Files**: new `frontend/__tests__/`, `frontend/jest.config.js` or `vitest.config.ts`
- **Action**: Add component tests for the chatbot composer, upload dialog, and at least one analytics chart. Add a single Playwright smoke test that logs in, uploads a sample PDF, and verifies the transaction appears.
- **Acceptance**: `npm test` passes. Playwright smoke test passes against a running stack.
- **Depends on**: AUTH-04.

### TEST-03 — GitHub Actions CI
- [ ] **Files**: new `.github/workflows/ci.yml`
- **Action**: On every PR: install backend deps, run `pytest`; install frontend deps, run `npm run lint && npm run build && npm test`.
- **Acceptance**: A PR with a failing test is blocked from merge.
- **Depends on**: TEST-01, TEST-02.

---

## Cross-cutting acceptance gates

Before declaring "stable" and starting Phase 6:

1. `grep -rn "['\"]123['\"]" frontend/src backend` returns 0 matches outside fixtures.
2. Every backend route under `routes/` is decorated with `@require_auth` (or explicitly whitelisted in `app.py`).
3. No raw f-string SQL anywhere in `backend/`.
4. CORS, `SECRET_KEY`, `EMAIL_ENCRYPTION_KEY`, `OPENROUTER_API_KEY`, `NEXT_PUBLIC_BACKEND_URL` are all required env vars and documented in `.env.example` files.
5. `pytest` + `npm test` both green; CI workflow runs on PRs.
6. A new user signing up sees: a working onboarding, an empty-state dashboard, and an upload CTA — not a broken page that assumes user 123.

---

## Working with Claude Code on this list

- One task per session is ideal. Hand Claude the task ID and let it open just the files listed under that task.
- Reference the **Depends on** field — if a dep isn't done, fix that first.
- Update this file at the end of each session: tick the checkbox and add a one-line note under the task if anything changed.
- When a task reveals a sibling problem out of scope, add it as a new entry (next free ID in that phase) rather than expanding the current task.
