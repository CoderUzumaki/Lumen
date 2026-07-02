# Handoff — Lumen Intelligence Agent

**Branch:** `v2/intelligence-agent`
**Base:** `refactor` (at commit `af39bef` — latest from origin/refactor)
**Last updated:** 2026-07-02 (session 2 — BOOT-02 FastAPI scaffolding)
**Progress:** 4/60 modules complete (HP-01, HP-02, BOOT-01, BOOT-02)

---

## Next module

**ID:** `BOOT-03`
**Title:** Port `Config` and auth utilities
**Depends on:** BOOT-02
**Read:** `BUILD.md` → the `BOOT-03` block (that section only)

**Branch state:** BOOT-01 pruning + BOOT-02 FastAPI scaffolding are on top of `856d503`. The old `backend/config.py`, `backend/utils/auth.py`, and `backend/utils/logging_config.py` (kept from BOOT-01) are still at their old paths — BOOT-03 ports them into `backend/app/utils/`, adapts `require_auth` from a Flask decorator to a FastAPI dependency returning a `UserContext` Pydantic model, and adds the new env vars per BUILD.md §Environment variables.

Before starting, verify:
- `git branch --show-current` shows `v2/intelligence-agent`.
- `git log --oneline -4` shows the BOOT-02 and BOOT-01 commits on top of `856d503` and `f7e479a`.
- `git status` is clean.
- `python -c "from app.main import app"` (from `backend/` with deps installed) imports without error.

---

## Last session

- **Session goal:** Execute BOOT-02 — stand up the FastAPI app skeleton, error envelope, request-id middleware, alembic wiring, and pinned deps, so BOOT-03/04/05 have somewhere to add real code.
- **Completed:**
  - `BOOT-02` ✅ — FastAPI scaffolding.
  - `backend/requirements.txt` — the 25 pinned dependencies from BUILD.md verbatim.
  - `backend/pyproject.toml` — Python 3.11+, package `lumen-backend`, `[tool.setuptools.dynamic] dependencies = requirements.txt`.
  - `backend/app/__init__.py` (empty) and `backend/app/db/__init__.py` (empty) to make the packages importable.
  - `backend/app/main.py` — FastAPI app with:
    - Envelope helpers (`_ok`, `_err`) matching BUILD.md §Error envelope.
    - Lifespan startup/shutdown log (empty stub — BOOT-03 will wire `Config.validate()` + structlog init, BOOT-06 will wire LangSmith / Langfuse).
    - CORS middleware reading `ALLOWED_ORIGINS` env var (comma-separated, defaults to `http://localhost:3000`).
    - `request_id` middleware — accepts inbound `X-Request-ID` or generates a hex UUID; attaches to `request.state` and echoes on the response.
    - Exception handlers for `StarletteHTTPException` (mapped via `_HTTP_CODE_MAP` to stable envelope codes), `RequestValidationError` (422 → `validation_error` with Pydantic details), and generic `Exception` (500 → `internal_error`, logs the traceback).
    - `GET /health` → `{"data": {"status": "ok", "commit": os.environ["GIT_SHA"] or "dev"}, "error": null}`.
  - `backend/app/db/base.py` — minimal `class Base(DeclarativeBase)`. BOOT-05 extends with id/created_at/updated_at columns and wires the async engine + session factory.
  - `backend/alembic.ini` — script_location=`alembic`, `sqlalchemy.url` intentionally omitted (env.py composes it from `DATABASE_URL`).
  - `backend/alembic/env.py` — composes a sync URL from `DATABASE_URL` (swaps `postgresql+asyncpg://` → `postgresql+psycopg2://`; falls back to `sqlite:///./_alembic_scratch.db` when the env var is unset). Imports `Base.metadata` so `--autogenerate` works even though no models are declared yet.
  - `backend/alembic/script.py.mako` — standard Alembic revision template.
  - `backend/alembic/versions/.gitkeep` — placeholder for the empty versions dir.
- **Acceptance verified locally:**
  - Installed the minimum boot set (`fastapi`, `uvicorn`, `pydantic`, `sqlalchemy`, `alembic`, `httpx` at pinned versions) into the system Python 3.11.5. All 25 pinned deps were NOT installed — smoke test used only the subset above.
  - In-process ASGI call to `/health` returns `200` with the envelope `{"data": {"status": "ok", "commit": "dev"}, "error": null}` and an `X-Request-ID` response header.
  - `alembic revision --autogenerate -m "init"` (from `backend/`) produced `8955b46cc754_init.py` with empty `upgrade`/`downgrade` — deleted after the check since BOOT-05 owns the first real migration.
- **Files touched:** created `backend/requirements.txt`, `backend/pyproject.toml`, `backend/app/__init__.py`, `backend/app/main.py`, `backend/app/db/__init__.py`, `backend/app/db/base.py`, `backend/alembic.ini`, `backend/alembic/env.py`, `backend/alembic/script.py.mako`, `backend/alembic/versions/.gitkeep`. Modified `BUILD.md` (tick), `HANDOFF.md` (this file). Nothing deleted.
- **Migrations added:** none committed. The autogenerate acceptance was verified and its throwaway output deleted.
- **Tests added:** none. `backend/tests/` still doesn't exist; the phase's first test appears at BOOT-06 (`test_llm.py`).
- **In-flight work:** none.
- **Deviations from BUILD.md:**
  - **`Config.validate()` in lifespan is deferred to BOOT-03.** BUILD.md's Action list says "Startup event: `Config.validate()` + structured logging init + LangSmith init if configured." But `backend/app/utils/config.py` is BOOT-03's Files scope, not BOOT-02's — so the lifespan is a bare log stub with a comment marking where BOOT-03 (Config) and BOOT-06 (tracing) will wire in.
  - **`backend/alembic/env.py` + `alembic/script.py.mako` + `alembic/versions/.gitkeep` are outside BOOT-02's Files scope.** BUILD.md lists only `alembic.ini` in BOOT-02's Files and puts `alembic/env.py` in BOOT-05's Files. But BOOT-02's acceptance requires `alembic revision --autogenerate` to succeed, which is impossible without `env.py` and a version template. Wrote minimal versions here; BOOT-05 replaces / extends `env.py` when it wires the real Base with id/created_at/updated_at.
  - **Nothing outside `backend/` was touched.** Frontend still has the auth-only skeleton from BOOT-01; the whole app + landing page rebuild is BOOT-04's problem.
  - **Runtime verification only covered the acceptance triggers, not a full uvicorn boot.** The 25 pinned deps include heavy packages (`chromadb`, `sentence-transformers`, `torch` transitive, `langgraph`, etc.) that were NOT installed for BOOT-02. `uvicorn app.main:app --reload` should start cleanly once someone `pip install -r requirements.txt` — `main.py` only imports `fastapi`, `starlette`, `stdlib`.

---

## Environment state

- Backend: FastAPI app skeleton on disk. `GET /health` works via ASGI. Everything else (auth, config, LLM wrapper, models, routes) is empty stubs waiting for BOOT-03..BOOT-08. The old `backend/config.py`, `backend/utils/auth.py`, `backend/utils/logging_config.py` still sit at their pre-refactor paths — BOOT-03 will port them into `backend/app/utils/`.
- Frontend: unchanged from BOOT-01 — auth-only skeleton, no `/` route yet.
- Database: local dev untouched; Supabase project unchanged. Alembic can autogenerate against `sqlite:///./_alembic_scratch.db` in a pinch when `DATABASE_URL` is unset.
- Vectors: no vector store yet. ING-07 will provision.
- Tests: no v2 tests exist yet.
- CI: `.github/workflows/handoff-check.yml` remains installed. Product-code CI is BOOT-08.
- Docs on `v2/intelligence-agent`: `PRD.md`, `BUILD.md`, `HANDOFF.md`, `CONTRIBUTING.md`, `LICENSE`, `README.md` (to be rewritten in DEPLOY-06), `TODO.md` (frozen), `docs/AUTH.md`, `docs/screenshots/README.md`.

---

## Open questions / blockers

- **None.** BOOT-03 can start immediately. It ports the existing `backend/config.py`, `backend/utils/auth.py`, `backend/utils/logging_config.py` into `backend/app/utils/`, strips the OCR/vision fields, adapts `require_auth` to a FastAPI dependency, and adds the new env vars listed at the bottom of BUILD.md.

---

## Rules for the next session

1. **Read `HANDOFF.md` first** (this file). Do this before anything else.
2. **Read `PRD.md`** (all of it — it's short). Non-goals and principles are vetoes.
3. **Read the `BUILD.md` block for the "Next module" ID above.** Do NOT read other module blocks unless the current one lists them as dependencies. For BOOT-03 you also want the "Environment variables" section at the very bottom of BUILD.md, since BOOT-03 introduces the new vars into `Config`.
4. **Do NOT re-read the entire repo.** Files outside the module's scope are irrelevant.
5. **Implement the module and only the module.** Match Acceptance criteria literally.
6. **Do NOT expand scope.** If you notice an adjacent problem, add it as a new module ID in `BUILD.md` — don't fold it into the current work.
7. **Before ending the session:**
   - Tick the module's checkbox in `BUILD.md` (append ` ✅` to the module heading — that's the convention set by HP-01/HP-02/BOOT-01/BOOT-02).
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
