# Lumen: Comprehensive Production Plan

> **Implementation status (July 2026):** Phases A–F from this plan are **implemented** in code. Auth, security, schema, deploy config, and frontend polish are in place. **Deferred (documented):** full Gmail OAuth (IMAP + app password works), Supabase httpOnly cookie migration, app-wide dark/light theme unification, orphaned Cliste landing components cleanup.

### Completion checklist

| Phase | Status | Notes |
|-------|--------|-------|
| A — Auth & tenancy | Done | JWT-only API; no hardcoded `user_id`; middleware + `/upload` redirect |
| B — Security | Done | SQL allowlist, per-user dedup, Fernet IMAP encryption, rate limits, upload caps |
| C — Database | Done | `DATABASE_URL`, Alembic, unified models, demo migration script |
| D — Frontend polish | Done | Toasts, error states, nav-user, CTAs, logos, error boundaries |
| E — Features | Done | Batch persist, chat history, seed `--user-id`; Gmail OAuth stub |
| F — Deploy & ops | Done | `render.yaml`, CI, pytest, worker, `QUICK_START.md` |

**Your next step:** seed Neon with `python scripts/populate_db.py --user-id <your-supabase-uuid>` then sign in and use the app.

---

This plan reflects the current codebase after the auth and model fixes from the recent session, plus a full audit of backend, frontend, security, design, and deployment.

---

## 1. Executive Summary

Lumen has strong **hackathon/demo bones**: OCR, chat, analytics, AI insights, email polling, and a polished landing page. It is **not yet project-worthy for production** because:

- Multi-tenancy is broken in several places (hardcoded `user_id: "123"`, global dedup, LLM SQL).
- Auth is half-implemented (Supabase login works, but data calls often ignore the real user).
- Storage is local-only (SQLite + Chroma on disk), which fails on Render.
- Schema and API contracts are inconsistent across modules.
- The UI is split between a marketing site and an app that feel like two products.

**Good news:** The hardest conceptual decision (Supabase JWT auth) is already made and documented in `docs/AUTH.md`. The path forward is mostly execution, not re-architecture.

---

## 2. Current State: What Works vs What Doesn't

| Area | Status | Notes |
|------|--------|-------|
| Google sign-in (Supabase) | Working | Frontend OAuth + token in `localStorage` |
| Backend JWT verification | Working | `@require_auth` on most routes |
| `/signin` page | Exists | Was missing; now present |
| Chat route | Partially working | Auth OK; model was wrong (fixed to `openrouter/free`) |
| Protected pages | Client-only guard | `AuthGuard` on app routes, no middleware |
| Real user data isolation | Broken | Frontend still sends `user_id: "123"` in many places |
| Upload flow | Broken UX | `/upload` 404; upload dialog exists on dashboard only |
| Email Gmail OAuth | Stub | Returns 501 |
| Render deployment | Not ready | SQLite/Chroma ephemeral, no gunicorn, scheduler dev-only |
| Tests | Stale | Manual scripts, wrong URLs, no auth headers |

---

## 3. Critical Mistakes and Loose Ends

### 3.1 Security (Highest Risk)

**P0 — Must fix before any public deploy**

1. **LLM-generated SQL executed without validation** (`backend/ai/sql_agent.py`)  
   The chat agent can run arbitrary SQL from the model. That is a tenancy and data-exfiltration risk. Fix: allowlist `SELECT` only, inject `user_id` server-side, never return raw SQL to clients.

2. **Global invoice deduplication ignores `user_id`** (`backend/utils/save_transaction.py`, `models/__init__.py`)  
   User B's invoice can collide with User A's. Fix: unique constraint on `(user_id, vendor_name, invoice_number)`.

3. **IMAP passwords stored in plaintext** (`models/__init__.py`, `email_config.py`)  
   Comment says "encrypted in production" but no encryption exists.

4. **Internal errors leaked to clients**  
   Many routes return `str(e)` in JSON. Attackers learn stack paths, SQL, and IMAP details.

5. **No upload size limits** (`ocr.py`, `batch.py`)  
   Full file read into memory; easy DoS on expensive OCR/LLM endpoints.

6. **No rate limiting** on `/extract`, `/chat`, `/api/analytics/analyze`.

**P1 — Important**

- `SUPABASE_URL` not validated at startup → runtime `auth_misconfigured` (hit during debugging).
- Health endpoints expose operational info (model names, key presence).
- `aiAnalyticsContent.tsx` bypasses auth client and calls `http://localhost:5000` directly with `user_id: 123`.
- Secrets in chat history / screenshots (rotate Google OAuth secret, OpenRouter key if exposed).

### 3.2 Multi-Tenancy and Data Integrity

- Frontend: **14+ places** still use `user_id: "123"` or `"1"` (`client.ts`, dashboard, analytics, AI cards, chatbot, upload).
- Backend: `user_id` typed as `int` in some AI modules while auth provides UUID strings.
- `save_transaction` commits parent row before line items → orphan transactions on failure.
- Dual schema definitions: SQLAlchemy models vs raw `CREATE TABLE` in AI agents (`anomalies`, `insights`) → analytics can fail silently or inconsistently.

### 3.3 Incomplete Features (Explicit Loose Ends)

| Feature | State |
|---------|--------|
| Gmail OAuth for email | 501 stub |
| `/extract-batch` | OCR only, no DB persist |
| `/upload` route | Missing (404) |
| Transaction DELETE | No endpoint |
| Chat persistence | In-memory only in frontend |
| Footer / landing links | 15+ dead routes (`/privacy`, `/docs`, etc.) |
| Nav user menu | Placeholder items (Billing, Upgrade) |
| `google-cloud-vision` in requirements | Unused (OCR uses OpenRouter) |

### 3.4 Config and Environment Pitfalls (Lessons from Debugging)

- **Dynamic `process.env[name]` in Next.js client** breaks Supabase env loading — must use static `process.env.NEXT_PUBLIC_*`.
- **Import-time `Config.*` caching** — changing `.env` without restart leaves stale values (`SUPABASE_URL`, `LLM_TEXT_MODEL`).
- **Flask debug reloader** can mask which process serves requests.
- **`backend/.env` has a junk line** `DATABASE_URL=GOOGLE_APPLICATION_CREDENTIALSfin` — misleading, unused.
- **No `backend/.env.example`** — onboarding friction.

### 3.5 API and Documentation Drift

- Mixed URL prefixes: `/extract`, `/analytics/*`, `/api/analytics/*`, `/api/v1/*`.
- `DEPLOYMENT.md` mentions Postgres, `gunicorn`, `CORS_ORIGINS` — code uses SQLite, no gunicorn in requirements, `ALLOWED_ORIGINS`.
- Test scripts hit wrong paths and omit auth → useless for CI.
- README claims Google Cloud Vision; implementation uses OpenRouter vision.

---

## 4. Frontend Design Scope

### 4.1 The Core UX Problem: Two Products in One Repo

| Landing / marketing | App (dashboard, analytics, chat) |
|---------------------|----------------------------------|
| Dark Aurora, glassmorphism | Light gray/white shadcn |
| Hero CTAs do nothing | Functional sidebar + APIs |
| "Get Started" → `#contact` | Requires Google sign-in |
| Footer links to non-existent pages | Real routes only |

**Enhancement direction:** Pick one design system and one brand voice.

**Recommended approach**

1. **Unify under "Lumen"** — remove Invox/Cliste references (`app-sidebar.tsx`, `footer.tsx`).
2. **Shared tokens** — extend `globals.css` with light + dark themes; app pages should not hardcode `bg-white` everywhere.
3. **Single auth entry** — all CTAs → `/signin?next=/dashboard`.
4. **App shell** — consistent header/sidebar, loading skeletons, error boundaries.
5. **Sign-in page** — remove dev copy ("Lumen now signs users in through Supabase…"); user-facing polish only.

### 4.2 Missing UX Patterns

- No `error.tsx`, `not-found.tsx`, `loading.tsx` at app level.
- Errors often silent (analytics shows zeros; anomaly card shows "no anomalies" on API failure).
- `alert()` for export/email errors — replace with toast/dialog.
- Upload success dialog uses stale React state — may not auto-close.
- Analytics defaults to Nov 2024 for "test data" — wrong for real users.
- Missing assets: `/lumen.svg`, `/images/lumen-logo.svg`, favicon mismatch.

### 4.3 Accessibility

- Hidden dialog titles on upload modal.
- Mobile nav without `aria-label`.
- Avatar fallback hardcoded "CN".
- Chatbot `prompt()` for rename — poor a11y and mobile UX.

### 4.4 Frontend Security

- Add **Next.js middleware** for `/dashboard`, `/analytics`, `/ai-analytics`, `/chatbot` (cookie/session check or redirect).
- Remove **localhost hardcode** in AI analytics.
- Stop sending `user_id` from client entirely — backend uses JWT `sub`.
- Wrap `useSearchParams` consumers in `Suspense` (Next 14 requirement).
- Consider httpOnly cookies via `@supabase/ssr` instead of only `localStorage` tokens (XSS risk).

---

## 5. Backend Architecture Enhancements

### 5.1 Data Layer

```
Current:  SQLite (local) + ChromaDB (local) + dual schemas
Target:   Postgres (Render) + managed vector store OR pgvector
          Alembic migrations + single SQLAlchemy source of truth
```

**Steps**

1. Add Alembic; remove conflicting `CREATE TABLE IF NOT EXISTS` from AI agents.
2. Migrate `user_id` to UUID/text everywhere.
3. Per-user unique constraints and query scoping on every read/write.
4. Externalize Chroma or use Supabase pgvector for durable RAG.

### 5.2 AI / LLM Layer

| Use case | Current | Target |
|----------|---------|--------|
| OCR | OpenRouter vision (free nemotron) | Keep; add file validation + size caps |
| Chat / SQL / classify | `openrouter/free` | Tiered: free for dev, pinned model for prod |
| Embeddings | OpenRouter embedding model | Confirm free-tier limits; cache embeddings |
| SQL agent | LLM writes SQL | **Replace with validated query builder or strict allowlist** |

### 5.3 Email Polling

- Scheduler only starts in `if __name__ == '__main__'` — won't run under gunicorn.
- **Fix:** Render background worker or cron + separate worker process.
- Encrypt IMAP credentials; implement or remove Gmail OAuth stubs.

### 5.4 API Standardization

Adopt one response envelope:

```json
{ "success": true, "data": {...} }
{ "success": false, "error": { "code": "...", "message": "..." } }
```

- Version under `/api/v1` consistently or document the mixed layout clearly.
- Remove legacy `/transactions/<user_id>` or return 410 with migration note.

---

## 6. Deployment and Operations (Render)

Per Render constraints and the repo state:

| Issue | Fix |
|-------|-----|
| Ephemeral disk | Postgres + external object storage for uploads |
| SQLite lost on restart | `DATABASE_URL` + SQLAlchemy URI switch |
| Chroma lost on restart | Remote vector DB or disable RAG until durable |
| No gunicorn | Add to `requirements.txt`; `gunicorn app:app` |
| Scheduler | Background worker service |
| `pdf2image` / Poppler | Document system dependency; Docker or buildpack |
| Pin dependencies | `requirements.txt` has unpinned packages |
| `0.0.0.0:$PORT` | Already correct pattern in config |
| CORS | Set `ALLOWED_ORIGINS` to production frontend URL |

Add:

- Health check: DB ping, JWKS reachability, optional OpenRouter ping.
- Structured logs + request ID (no emoji in logs on Windows — encoding errors observed).
- `backend/.env.example` and align `DEPLOYMENT.md` with real env var names.

---

## 7. Phased Roadmap to "Project Worthy"

Aligns with existing `TODO.md` but adds frontend design, security depth, and session learnings.

### Phase A — Stabilize Auth and Tenancy (1–2 weeks)

**Goal:** Every signed-in user sees only their data.

- [ ] Replace all `user_id: "123"` with JWT-derived identity (remove param from API client).
- [ ] Fix `aiAnalyticsContent.tsx` to use `apiClient` + Bearer token.
- [ ] Add Next.js `middleware.ts` for protected routes.
- [ ] Validate `SUPABASE_URL` in `Config.validate()` at boot.
- [ ] Add `backend/.env.example`.
- [ ] Rename tokens `invox_*` → `lumen_*` for consistency.
- [ ] Fix `/upload` (route or redirect to dashboard with upload dialog open).

**Done when:** Two different Google accounts see different transaction sets.

### Phase B — Security Hardening (1–2 weeks)

**Goal:** Safe to expose to the internet.

- [ ] SQL agent: allowlist + parameterized queries + no SQL in responses.
- [ ] Per-user dedup constraint; fix `save_transaction` atomicity.
- [ ] Global Flask error handlers; generic client messages.
- [ ] Upload limits (`MAX_CONTENT_LENGTH`), MIME checks.
- [ ] Rate limiting (Flask-Limiter or reverse proxy).
- [ ] Encrypt IMAP passwords (Fernet + `EMAIL_ENCRYPTION_KEY`).
- [ ] Lock down health endpoints; remove key/model leakage.
- [ ] Security review: CORS, XSS (token storage), CSRF (if cookies later).

**Done when:** OWASP-style pass on auth, injection, and data exposure.

### Phase C — Database and Schema Unity (2–3 weeks)

**Goal:** One schema, migrations, production DB.

- [ ] Alembic migrations from current SQLAlchemy models.
- [ ] Remove duplicate raw-SQL table creation in AI modules.
- [ ] Migrate demo `user_id='123'` to fixed dev UUID (per `docs/AUTH.md`).
- [ ] Postgres support via `DATABASE_URL`.
- [ ] Chroma strategy: pgvector or hosted vector DB.

**Done when:** Fresh deploy + migrate produces working analytics for a new user.

### Phase D — Frontend Product Polish (2–3 weeks)

**Goal:** Feels like one shipped product, not a demo + landing.

**Design system**

- [ ] Single Lumen brand (logo, colors, typography).
- [ ] Light/dark theme toggle app-wide (chatbot already has one — unify).
- [ ] Replace dead landing CTAs with `/signin` or in-page demos.
- [ ] Remove or implement footer links.
- [ ] Add missing `public/` assets.

**UX**

- [ ] `error.tsx`, `not-found.tsx`, `loading.tsx`.
- [ ] Proper error states on every data card (not silent zeros).
- [ ] Toast system instead of `alert()`.
- [ ] Sign-in page: production copy, optional email/password later.
- [ ] Onboarding empty states (no invoices → guided upload).

**Done when:** New user can land → sign in → upload → see dashboard without 404s, 500s, or `auth_misconfigured`.

### Phase E — Complete Features (2–4 weeks)

- [ ] Gmail OAuth for email OR document IMAP-only path clearly.
- [ ] Persist chat history (backend table or Supabase).
- [ ] `/extract-batch` persists transactions.
- [ ] Transaction DELETE + export polish.
- [ ] Invoice edit/upload flow end-to-end tested.
- [ ] Remove dead code (~15 unused landing components, `aiAssistantUI.tsx` duplicate).

### Phase F — Deploy, Test, Document (1–2 weeks)

- [ ] Pin `requirements.txt`; add gunicorn.
- [ ] `render.yaml` or documented Render services (web + worker + Postgres).
- [ ] Pytest suite with Supabase JWT fixtures.
- [ ] Update README, QUICK_START, DEPLOYMENT to match reality (OpenRouter not Vision).
- [ ] CI: lint + test on PR.

**Done when:** One-click deploy to Render; demo video matches deployed app.

---

## 8. Security Checklist (Pre-Launch)

| Check | Action |
|-------|--------|
| Auth on all data routes | Done — keep exempt list minimal |
| No client-supplied `user_id` | Remove from frontend + grep backend |
| SQL injection | SQL agent rewrite |
| Secrets in git | Verify `.env`, `*.json` gitignored; rotate exposed keys |
| HTTPS only in prod | Render + Supabase defaults |
| CORS | `ALLOWED_ORIGINS` = exact frontend URL |
| Token storage | Consider `@supabase/ssr` cookies |
| File uploads | Size/type limits, virus scan optional |
| Rate limits | Per-IP and per-user on LLM routes |
| Dependency audit | `pip audit`, `npm audit` |
| LLM prompt injection | Sanitize user chat input in logs; scope RAG to user |

---

## 9. Definition of "Project Worthy"

Use this as the completion bar:

1. **Correctness** — Two users cannot see each other's invoices, chat results, or analytics.
2. **Security** — No arbitrary SQL, no plaintext passwords, no raw stack traces to clients.
3. **Reliability** — Data survives deploy/restart (Postgres + durable vectors).
4. **UX** — Sign in → upload → dashboard → chat/analytics works without 404s, 500s, or `auth_misconfigured`.
5. **Design** — Coherent Lumen brand; landing converts to app; accessible core flows.
6. **Ops** — Documented env vars, pinned deps, health checks, basic tests in CI.
7. **Honesty** — README and docs match what the code actually does.

---

## 10. Recommended Immediate Next Steps (This Week)

If you want the highest impact with least effort:

1. **AUTH-05:** Remove every `"123"` from the frontend; stop sending `user_id` in API bodies.
2. **Fix `aiAnalyticsContent.tsx`** — use `apiClient`, not localhost `fetch`.
3. **Add `SUPABASE_URL` to `Config.validate()`** — fail fast at boot.
4. **SQL agent safety** — even a minimal "SELECT-only + inject user_id" guard.
5. **Unify one CTA path** — landing "Get Started" → `/signin?next=/dashboard`.
6. **Add missing logos** to `public/` so the app doesn't look broken.

---

## 11. How This Maps to Existing `TODO.md`

`TODO.md` Phases 0–2 are largely on track. The biggest gaps vs that doc:

| TODO item | Reality |
|-----------|---------|
| AUTH-04 Frontend auth context | Partially done (`AuthProvider`, `AuthGuard`, `/signin`) — not full `docs/AUTH.md` plan |
| AUTH-05 Remove `"123"` | **Not done** — still the #1 blocker |
| DB-01 SQL agent safety | **Not done** — critical |
| Phase 4+ deploy/tests | Not started |

Treat this plan as the **product + security layer** on top of `TODO.md`, especially for frontend design and vulnerability prioritization.

---

## 12. Backend Audit Summary (Detailed Findings)

### P0 — Block Production Deploy

1. **LLM-generated SQL without validation** — `backend/ai/sql_agent.py`
2. **Multi-tenant data leak via global invoice deduplication** — `backend/utils/save_transaction.py`, `models/__init__.py`
3. **Render / ephemeral filesystem** — SQLite and ChromaDB lost on restart
4. **Conflicting database schemas** — SQLAlchemy vs raw SQL in AI agents
5. **IMAP passwords in plaintext** — `models/__init__.py`, `routes/email_config.py`

### P1 — High Priority

6. Auth gaps: `SUPABASE_URL` not in `Config.validate()`, public health leaks, JWKS → 401 not 503
7. Email scheduler won't run under Gunicorn — only starts in `if __name__ == '__main__'`
8. Internal errors exposed to clients across routes
9. `user_id` type inconsistency (dev `123` vs Supabase UUID)
10. Transaction save integrity bug (commit before line items)
11. No upload limits or content validation
12. No rate limiting

### P2 — Medium Priority

13. Incomplete features: Gmail OAuth 501, batch extract no persist, unused google-cloud-vision
14. API inconsistencies (mixed URL layout, error shapes)
15. Deployment/config mismatches (docs vs code)
16. ChromaDB tenancy and durability issues
17. Database init swallows connection failures

### P3 — Lower Priority

18. Missing/broken test suite
19. Secrets and credentials hygiene
20. Observability gaps
21. Minor code quality / dead paths

---

## 13. Frontend Audit Summary (Detailed Findings)

### P0 — Ship Blockers

1. Hardcoded `user_id: "123"` across API client and components
2. AI analytics bypasses API client with hardcoded `localhost`
3. Missing `/upload` route (404)
4. Missing static assets (`/lumen.svg`, logos, favicon)
5. Auth is client-only; no middleware

### P1 — High Priority

6. Auth UX incomplete (dev copy, Google-only, silent misconfig)
7. Landing vs app UX split (non-functional CTAs, dead footer links)
8. Design/branding inconsistency (Invox, Cliste, mixed themes)
9. Error states weak or misleading
10. Env configuration gaps
11. `useSearchParams` without `Suspense`
12. Upload dialog success-check bug (stale state)

### P2 — Medium Priority

13. Accessibility gaps
14. Dead/orphaned code (~15 unused landing components)
15. API client inconsistencies (dual data models, unused endpoints)
16. Chatbot production gaps (in-memory only)
17. Analytics test-data defaults (Nov 2024)
18. Nav user menu placeholders

### P3 — Lower Priority

- Debug logging in landing nav
- Nav uses `#` and full page reloads
- Duplicate motion libraries
- Sign-in shows internal architecture to end users

---

## 14. Recommended Fix Order (Consolidated)

1. **Stop executing raw LLM SQL** — parameterized queries, allowlisted statements, scoped by `user_id`.
2. **Fix tenancy** — per-user unique constraint; scope all dedup/filter queries.
3. **Remove hardcoded `user_id` from frontend** — use JWT identity only.
4. **Unify schema** — single source of truth (SQLAlchemy + Alembic).
5. **Render storage** — managed Postgres + external vector store; pin deps; add gunicorn.
6. **Encrypt IMAP credentials**; validate `SUPABASE_URL` at startup.
7. **Standardize API errors**; lock down health endpoints; add upload limits and rate limiting.
8. **Frontend polish** — design system, middleware, error boundaries, fix broken routes/assets.
9. **Rewrite tests** with JWT fixtures and pytest; align docs with reality.

---

*Last updated: July 2026 — reflects auth/session debugging and full codebase audit.*
