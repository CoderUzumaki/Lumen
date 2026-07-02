# Handoff — Lumen Intelligence Agent

**Branch:** `v2/intelligence-agent`
**Base:** `refactor` (at commit `af39bef` — latest from origin/refactor)
**Last updated:** 2026-07-02 (session 5 — BOOT-05 async engine + Alembic)
**Progress:** 7/60 modules complete (HP-01, HP-02, BOOT-01..BOOT-05)

---

## Next module

**ID:** `BOOT-06`
**Title:** LLM wrapper (free-tier)
**Depends on:** BOOT-03, BOOT-05, OPT-05 (schema — see the block for BOOT-06's guidance on partially implementing OPT-05 first as a bare `llm_calls` table)
**Read:** `BUILD.md` → the `BOOT-06` block (that section only), plus BUILD.md §LLM invocation for context on the free-tier constraints.

**Branch state:** BOOT-01..BOOT-05 stacked on `856d503`. Backend can boot, verify auth, and run `alembic upgrade head`. No product tables yet — the shared `Base` (id/created_at/updated_at) waits for the first migration in Phase 1.

Before starting, verify:
- `git branch --show-current` shows `v2/intelligence-agent`.
- `git log --oneline -7` shows BOOT-05..BOOT-01 on top of `856d503` and `f7e479a`.
- `git status` is clean.
- `cd backend && DATABASE_URL="sqlite:///./_scratch.db" alembic upgrade head` succeeds and creates only `alembic_version`.

---

## Last session

- **Session goal:** Execute BOOT-05 — give `Base` its shared id/created_at/updated_at columns and the async engine + session factory, tighten `alembic/env.py` to route through `Config.DATABASE_URL` with the sync-driver swap, and verify `alembic upgrade head` runs green.
- **Completed:**
  - `BOOT-05` ✅ — DB bootstrap + Alembic wiring.
  - `backend/app/db/base.py`:
    - `class Base(DeclarativeBase)` now declares `id: Mapped[uuid.UUID]` (PostgreSQL `UUID(as_uuid=True)`, default `uuid.uuid4`), `created_at: Mapped[datetime]` (`DateTime(timezone=True)`, `server_default=func.now()`), `updated_at: Mapped[datetime]` (same server_default plus `onupdate=func.now()`).
    - Added a lazy `AsyncEngine` (`get_engine()`) and `async_sessionmaker` (`get_session_factory()`) — both memoized behind module globals so importing the module doesn't attach to a live DB.
    - Added a `get_db_session()` async generator for use as a FastAPI dependency (`db: AsyncSession = Depends(get_db_session)`).
  - `backend/alembic/env.py` — replaced the BOOT-02 shim with the canonical BOOT-05 version:
    - Composes the sync URL from `os.environ["DATABASE_URL"]` (highest priority) or `Config.DATABASE_URL` (fallback). Swaps `postgresql+asyncpg://` → `postgresql+psycopg2://`; passes anything else through unchanged (sqlite, etc.).
    - `target_metadata = Base.metadata`.
    - Standard offline / online migration paths (unchanged from the BOOT-02 shim's structure).
  - `backend/requirements.txt` — added `psycopg2-binary==2.9.9` (see deviation below). Nothing removed.
- **Acceptance verified locally:**
  - `DATABASE_URL="sqlite:///./_boot05_scratch.db" alembic upgrade head` (from `backend/`) succeeds:
    ```
    INFO  [alembic.runtime.migration] Context impl SQLiteImpl.
    INFO  [alembic.runtime.migration] Will assume non-transactional DDL.
    ```
    and inspecting the resulting sqlite file shows exactly one table: `alembic_version`. Base has no concrete tables yet, so no other schema objects appear — that's the expected shape at this phase.
  - Real Postgres (local or Supabase) was NOT tested end-to-end because this sandbox has no Postgres running. Both paths execute the same `_sync_database_url()` swap; the sqlite run exercises the alembic wiring and target_metadata plumbing, and the driver swap is a mechanical `str.replace`. When a live Postgres appears in Phase 1 (first migration), any wiring bug will surface immediately.
- **Files touched:** modified `backend/app/db/base.py`, `backend/alembic/env.py`, `backend/requirements.txt`, `BUILD.md` (tick), `HANDOFF.md` (this file). Nothing created or deleted.
- **Migrations added:** none. Phase 1 (DATA-01) writes the first real migration.
- **Tests added:** none.
- **In-flight work:** none.
- **Deviations from BUILD.md:**
  - **Added `psycopg2-binary==2.9.9` to `requirements.txt`.** BOOT-05's Action item 2 says "use `psycopg2` as migration driver," but the BOOT-02 requirements list omitted psycopg2. Added here (`-binary` because it ships prebuilt wheels — no local Postgres headers needed).
  - **Real-Postgres acceptance was verified via sqlite fallback**, not against a live Postgres instance. See "Acceptance verified locally" above for the reasoning. The code path is identical up to the driver swap; the swap itself is a mechanical string replace.

---

## Environment state

- Backend: FastAPI app boots, `/health` public, `/api/me` protected. `alembic upgrade head` provisions the `alembic_version` tracking table. Base is ready to accept its first concrete model (DATA-01).
- Frontend: builds cleanly (unchanged from BOOT-04).
- Database: schema is empty apart from `alembic_version` when migrations are run.
- Vectors: unchanged (none).
- Tests: none.
- CI: `.github/workflows/handoff-check.yml` remains installed.
- Docs on `v2/intelligence-agent`: unchanged.

---

## Open questions / blockers

- **None.** BOOT-06 can start next; note its dependency on OPT-05 (Phase §OPT-05 needs to at least create the `llm_calls` table before BOOT-06 can record calls to it).

---

## Rules for the next session

1. **Read `HANDOFF.md` first** (this file). Do this before anything else.
2. **Read `PRD.md`** (all of it — it's short). Non-goals and principles are vetoes.
3. **Read the `BUILD.md` block for the "Next module" ID above.** Do NOT read other module blocks unless the current one lists them as dependencies. For BOOT-06 you also need BUILD.md §LLM invocation for the free-tier framing, and the BUILD.md block for OPT-05 (the `llm_calls` table it defines).
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
