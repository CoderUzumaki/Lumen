# Handoff — Lumen Intelligence Agent

**Branch:** `v2/intelligence-agent`
**Base:** `refactor` (at commit `af39bef` — latest from origin/refactor)
**Last updated:** 2026-07-02 (session 3 — BOOT-03 Config + FastAPI auth port)
**Progress:** 5/60 modules complete (HP-01, HP-02, BOOT-01, BOOT-02, BOOT-03)

---

## Next module

**ID:** `BOOT-04`
**Title:** Frontend scaffolding reset
**Depends on:** BOOT-01
**Read:** `BUILD.md` → the `BOOT-04` block (that section only)

**Branch state:** BOOT-01..BOOT-03 are on top of `856d503`. Backend now has `backend/app/main.py` wired to `Config.validate()` + `configure_logging()` on lifespan; `backend/app/utils/{config,auth,logging_config}.py` are the authoritative ports; the old paths (`backend/config.py`, `backend/utils/*`, `backend/scripts/`) are deleted. Frontend still has the auth-only skeleton from BOOT-01 — that's BOOT-04's problem: rebuild the `/` landing, wire `QueryClientProvider` + `ThemeProvider` into `layout.tsx`, prune `package.json`, add the new deps.

Before starting, verify:
- `git branch --show-current` shows `v2/intelligence-agent`.
- `git log --oneline -5` shows BOOT-03, BOOT-02, BOOT-01 stacked on top of `856d503` / `f7e479a`.
- `git status` is clean.
- `python -c "from app.utils.auth import require_auth; from app.utils.config import Config"` succeeds from `backend/` with deps installed.

---

## Last session

- **Session goal:** Execute BOOT-03 — port the surviving `backend/config.py`, `backend/utils/auth.py`, `backend/utils/logging_config.py` into `backend/app/utils/`, adapt `require_auth` from a Flask decorator to a FastAPI dependency returning a `UserContext` Pydantic model, add the new env vars from BUILD.md §Environment variables, and wire everything into `main.py`.
- **Completed:**
  - `BOOT-03` ✅ — config + auth port.
  - `backend/app/utils/__init__.py` (empty, package marker).
  - `backend/app/utils/config.py` — the full BUILD.md §Environment variables surface as `Config.*` attributes: `ALLOWED_ORIGINS`, `DATABASE_URL`, `LOG_LEVEL`, `SUPABASE_URL`, `SUPABASE_JWT_AUD`, `OPENROUTER_API_KEY`, `OPENROUTER_BASE_URL`, `LLM_TEXT_MODEL_FAST`, `LLM_TEXT_MODEL_THOROUGH`, `LLM_RATE_LIMIT_RPM` (JSON), `LLM_DAILY_BUDGET_USD`, `EMBEDDING_MODEL`, `EMBEDDING_DEVICE`, `NEWSAPI_KEY`, `MARKETAUX_KEY`, `GDELT_ENABLED`, `EDGAR_USER_AGENT`, `RSS_FEEDS`, `YFINANCE_CACHE_PATH`, `CHROMA_PATH`, `LANGSMITH_*`, `LANGFUSE_*`, `INGEST_INTERVAL_MINUTES`, `CLUSTER_SIMILARITY_THRESHOLD`, `PREFILTER_THRESHOLD`, `SECRET_KEY`, `FLASK_ENV`. Kept the ephemeral-dev-SECRET_KEY behaviour from the original. `Config.validate()` requires `SECRET_KEY`, `OPENROUTER_API_KEY`, `SUPABASE_URL` — everything else is optional-at-boot and validates at point-of-use. Discarded from the original: `LLM_VISION_MODEL`, `OPENROUTER_CHAT_URL`, `LLM_TEXT_MODEL`, `LLM_EMBEDDING_MODEL`, `OPENROUTER_MODEL`, `DEFAULT_CURRENCY`, `DATABASE_PATH`/`DATABASE_URI` (superseded by `DATABASE_URL`), `SUPABASE_KEY`, old `CHROMA_DB_PATH`.
  - `backend/app/utils/auth.py` — `UserContext` Pydantic model (`user_id: UUID`, `email: str`, `role: str`); `async def require_auth(request: Request) -> UserContext` FastAPI dependency raising `HTTPException(401)` on failure; `verify_token()` preserves the JWKS caching + audience/issuer/anon-role checks from the Flask port. Fixed a carry-over bug: `PyJWKClient.get_signing_key_from_jwt` raises `jwt.DecodeError` (not `PyJWKClientError`) on malformed tokens — now caught and mapped to `TokenError("invalid_token", ...)`.
  - `backend/app/utils/logging_config.py` — ported verbatim per Action item 4; only tweak was replacing the Flask-era noisy-logger list (`werkzeug`) with `httpx`. BUILD.md §Structured logging targets structlog, but BOOT-03's spec is "port unchanged" — a later observability module can migrate.
  - `backend/app/main.py` — lifespan now calls `configure_logging()` and `Config.validate()` (removes the BOOT-02 deferred deviation). CORS now reads `Config.ALLOWED_ORIGINS`. Added `GET /api/me` protected by `Depends(require_auth)`, returning `_ok({"user_id", "email", "role"})`.
  - Deleted the old paths: `backend/config.py`, `backend/utils/__init__.py`, `backend/utils/auth.py`, `backend/utils/logging_config.py`, `backend/scripts/__init__.py` (with the now-empty `backend/scripts/`).
- **Acceptance verified locally:**
  - `from app.utils.auth import require_auth` and `from app.utils.config import Config` import cleanly (system Python 3.11.5 with `fastapi`, `PyJWT[crypto]`, `pydantic`, `python-dotenv` installed).
  - `Config.validate()` with `FLASK_ENV=production` and every required var unset raises `ValueError: Missing required environment variable(s): SECRET_KEY, OPENROUTER_API_KEY, SUPABASE_URL. ...`.
  - In-process ASGI:
    - `GET /health` → 200 with envelope `{"data": {"status": "ok", "commit": "dev"}, "error": null}`.
    - `GET /api/me` no `Authorization` header → 401 with envelope `{"data": null, "error": {"code": "unauthorized", "message": "missing_token"}}`.
    - `GET /api/me` with `Authorization: Bearer not-a-real-jwt` → 401 with envelope `{... "message": "invalid_token"}`.
    - `GET /api/me` with malformed `Authorization: NotBearer xyz` → 401 with envelope `{... "message": "missing_token"}` (parser rejects non-Bearer scheme before token verification).
  - `GET /api/me` with a real Supabase JWT was NOT tested end-to-end — that requires a live Supabase project and a signed token. The JWKS verification path is a straight port of the working refactor-branch code plus the DecodeError fix; the frontend AUTH tests will exercise it live once BOOT-04 is up.
- **Files touched:** created `backend/app/utils/__init__.py`, `backend/app/utils/config.py`, `backend/app/utils/auth.py`, `backend/app/utils/logging_config.py`. Modified `backend/app/main.py` (imports, lifespan, CORS source, `/api/me`), `BUILD.md` (tick), `HANDOFF.md` (this file). Deleted `backend/config.py`, `backend/utils/__init__.py`, `backend/utils/auth.py`, `backend/utils/logging_config.py`, `backend/scripts/__init__.py`.
- **Migrations added:** none.
- **Tests added:** none. The first backend test file appears in BOOT-06 (`test_llm.py`). Ad-hoc ASGI smoke lives in the transcript only.
- **In-flight work:** none.
- **Deviations from BUILD.md:**
  - **Deleted the old paths after porting.** BUILD.md's Files scope for BOOT-03 lists the *new* paths under `backend/app/utils/`; it doesn't explicitly say to delete the originals. But keeping both would create two competing sources of truth (and confusing imports). Deletes were staged alongside the port.
  - **Fixed a carry-over bug in the JWKS lookup.** The original `backend/utils/auth.py` had a `requests.RequestException` catch that never triggered (PyJWKClient uses `urllib.request`, not `requests`) and did NOT catch `jwt.DecodeError`, which propagates from `get_signing_key_from_jwt` on malformed tokens. Dropped the dead `requests` catch and added the `DecodeError` catch → `TokenError("invalid_token")`. Behaviour improvement is user-visible in the smoke output above.
  - **BOOT-02's deferred `Config.validate()` + `configure_logging()` lifespan wiring is now done.** No net new deviation; this is the BOOT-02 deviation resolving inside BOOT-03 as the spec intends.
  - **`logging_config.py` remained stdlib.** BUILD.md's global §Structured logging targets `structlog` JSON output with `request_id`/`user_id`/`route`/`module` fields — but BOOT-03's Action item 4 explicitly says "Port `logging_config.py` unchanged." Ported unchanged; the structlog migration is on a later observability module's plate.

---

## Environment state

- Backend: FastAPI app boots, validates config, serves `GET /health` (public) and `GET /api/me` (auth-required). Everything else — LLM wrapper, models, ingestion, agents — is empty and waits for BOOT-04..BOOT-08 and beyond. `backend/app/` is the authoritative source tree; the pre-BOOT-01 paths at `backend/config.py` / `backend/utils/*` / `backend/scripts/` are gone.
- Frontend: unchanged from BOOT-01 — auth-only skeleton, no `/` route. BOOT-04 rebuilds.
- Database: unchanged. Alembic can still autogenerate against `DATABASE_URL` (defaults to a sqlite scratch when unset).
- Vectors: no vector store yet.
- Tests: still no v2 tests.
- CI: `.github/workflows/handoff-check.yml` remains installed.
- Docs on `v2/intelligence-agent`: `PRD.md`, `BUILD.md`, `HANDOFF.md`, `CONTRIBUTING.md`, `LICENSE`, `README.md`, `TODO.md`, `docs/AUTH.md`, `docs/screenshots/README.md`.

---

## Open questions / blockers

- **None.** BOOT-04 can start immediately.

---

## Rules for the next session

1. **Read `HANDOFF.md` first** (this file). Do this before anything else.
2. **Read `PRD.md`** (all of it — it's short). Non-goals and principles are vetoes.
3. **Read the `BUILD.md` block for the "Next module" ID above.** Do NOT read other module blocks unless the current one lists them as dependencies. For BOOT-04 you also want the "Design system" section under §Global conventions since the frontend now needs its tokens.
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
