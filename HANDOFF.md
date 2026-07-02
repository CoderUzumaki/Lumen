# Handoff — Lumen Intelligence Agent

**Branch:** `v2/intelligence-agent`
**Base:** `refactor` (at commit `af39bef` — latest from origin/refactor)
**Last updated:** 2026-07-03 (session 9 — DATA-01 Phase 1 schema)
**Progress:** 11/60 modules complete (HP-01, HP-02, BOOT-01..BOOT-08, DATA-01).

---

## Next module

**ID:** `DATA-02`
**Title:** Pydantic schemas for portfolio / positions / themes
**Depends on:** DATA-01
**Read:** `BUILD.md` → the `DATA-02` block (that section only).

**Branch state:** BOOT-01..BOOT-08 + DATA-01 stacked on `856d503`. The DB layer now has four Phase 1 tables (`user_preferences`, `portfolios`, `positions`, `themes`) plus `llm_calls` from BOOT-06. Base was refactored from BOOT-05's monolithic id/created_at/updated_at into `Base + IdMixin + CreatedAtMixin + TimestampsMixin` mixins so DATA-01 could match the SQL schema exactly. LlmCall opts in to `(IdMixin, TimestampsMixin)` — the schema on disk is unchanged.

Before starting, verify:
- `git branch --show-current` shows `v2/intelligence-agent`.
- `git log --oneline -11` shows DATA-01..HP-01 stacked on `856d503`/`f7e479a`.
- `git status` is clean.
- `cd backend && python -m pytest tests -v` reports 8 passed, 1 deselected.
- `cd backend && DATABASE_URL="sqlite:///./_scratch.db" alembic upgrade head` applies both `boot06_llm_calls` and `data01_user_prefs_portfolios_positions_themes`.

---

## Last session

- **Session goal:** Execute DATA-01 — introduce the four Phase 1 tables (`user_preferences`, `portfolios`, `positions`, `themes`) with SQLAlchemy models that match the SQL schema exactly, and the Alembic migration that provisions them on both Postgres (with `auth.users` FKs) and sqlite (CI fallback, no `auth.users`).
- **Completed:**
  - `DATA-01` ✅ — Phase 1 schema.
  - **Refactored `backend/app/db/base.py`.** BOOT-05 had `id`/`created_at`/`updated_at` on `Base` itself, which doesn't match DATA-01's schema (`user_preferences` uses its natural key as PK; `positions` and `themes` have no `updated_at`). Split into a bare `Base(DeclarativeBase)` plus opt-in mixins `IdMixin`, `CreatedAtMixin`, `TimestampsMixin (extends CreatedAtMixin)`. Marked as a deliberate deviation from BOOT-05 — the file's docstring calls this out.
  - **Updated `backend/app/db/models/llm_call.py`** to compose `(IdMixin, TimestampsMixin, Base)`. Schema on disk is unchanged; only Python composition changed.
  - **Created four new models:**
    - `backend/app/db/models/user_preferences.py` — natural PK on `user_id`. CHECK constraints on `briefing_hour BETWEEN 0 AND 23` and `model_tier IN ('fast','thorough')`. Server defaults on all four business columns.
    - `backend/app/db/models/portfolio.py` — `IdMixin + TimestampsMixin`, `UniqueConstraint(user_id, name)`, and a partial unique index (`idx_portfolios_user_active`) enforcing "at most one active portfolio per user" using dialect-appropriate `WHERE` clauses (`is_active = 1` on sqlite, `is_active = TRUE` on Postgres). Index is declared in the model *and* the migration so `Base.metadata.create_all()` in tests emits it.
    - `backend/app/db/models/position.py` — `IdMixin + CreatedAtMixin` (no `updated_at` per spec). `ForeignKey("portfolios.id", ondelete="CASCADE")` on `portfolio_id` — same-DB FK is portable and doesn't need dialect guards. `UniqueConstraint(portfolio_id, ticker, exchange)`. CHECK constraint on `asset_type IN ('equity','etf','crypto','bond','other')`. `NUMERIC(20,8)` for `quantity` and `cost_basis`.
    - `backend/app/db/models/theme.py` — `IdMixin + CreatedAtMixin`. CHECK constraint on `weight BETWEEN 0 AND 1`. `NUMERIC(3,2)` for `weight`.
  - **Registered all four in `backend/app/db/models/__init__.py`** so `alembic autogenerate` and `Base.metadata.create_all()` pick them up.
  - **Wrote migration `371a33d86850_data01_user_prefs_portfolios_positions_themes.py`.** Creates all four tables + indexes. Guards the FKs to `auth.users(id)` behind `if op.get_bind().dialect.name == "postgresql"` so sqlite doesn't try to reference a schema it doesn't have; Postgres gets the full Supabase-native FK graph with `ondelete="CASCADE"`. Discarded the spurious `alter_column NUMERIC → UUID` on `llm_calls` that autogenerate emits because sqlite reports UUID columns as NUMERIC affinity — that alter is a no-op and would create false diffs on future autogenerates.
  - **Wrote `backend/tests/db/test_models.py::test_phase1_schema`** — 116 lines covering:
    - Happy-path insert into all four tables.
    - `briefing_hour=99` → `IntegrityError` (CHECK).
    - `model_tier="lightning"` → `IntegrityError` (CHECK).
    - `asset_type="futures"` → `IntegrityError` (CHECK).
    - `weight=1.5` → `IntegrityError` (CHECK).
    - `(user_id, name)` duplicate → `IntegrityError` (UNIQUE on portfolios).
    - `(portfolio_id, ticker, exchange)` duplicate → `IntegrityError` (UNIQUE on positions).
    - Second active portfolio per user → `IntegrityError` (partial unique index).
    - Cascade delete: deleting a portfolio drops its positions. FK enforcement enabled via `PRAGMA foreign_keys=ON` connect hook.
- **Acceptance verified locally:**
  - `alembic upgrade head` runs both migrations (`boot06_llm_calls` → `data01_user_prefs_portfolios_positions_themes`) — verified on sqlite.
  - `alembic downgrade -1 && alembic upgrade head` is a clean no-op — no residual state, no complaints.
  - `python -m pytest tests -v` reports **8 passed, 1 deselected** (7 LLM tests from BOOT-06 + 1 Phase 1 schema test from DATA-01; live-provider test still opt-in).
  - `ruff check .` clean.
- **Files touched:** created `backend/app/db/models/{user_preferences,portfolio,position,theme}.py`, `backend/alembic/versions/371a33d86850_data01_user_prefs_portfolios_positions_.py`, `backend/tests/db/__init__.py`, `backend/tests/db/test_models.py`. Modified `backend/app/db/base.py` (Base refactor), `backend/app/db/models/__init__.py` (registry), `backend/app/db/models/llm_call.py` (composes mixins), `BUILD.md` (tick), `HANDOFF.md` (this file).
- **Migrations added:** 1 — `371a33d86850_data01_user_prefs_portfolios_positions_themes`.
- **Tests added:** 1 (`test_phase1_schema`, ~9 assertions across CHECK / UNIQUE / cascade behaviours).
- **In-flight work:** none.
- **Deviations from BUILD.md:**
  - **`Base` was refactored from BOOT-05's monolithic shape into mixins.** BOOT-05's spec says Base has `id + created_at + updated_at`. DATA-01's schema requires per-table opt-in — `user_preferences` has no `id` (uses `user_id` as PK); `positions` and `themes` have no `updated_at`. Kept the same field defaults so `LlmCall` (which composes both mixins) has an identical DDL. The alternative — using multiple base classes or accepting extra columns on some tables — would violate DATA-01's "matching this schema exactly" language.
  - **Model does not declare FK to `auth.users`.** Model has raw `user_id UUID` columns; migration adds `auth.users` FKs conditionally on Postgres (`op.get_bind().dialect.name == "postgresql"`). Reason: sqlite has no schemas, and `sa.ForeignKey("auth.users.id")` on sqlite emits `REFERENCES "auth"."users"(id)` which no CI-available sqlite has. This means future autogenerate runs against Postgres will NOT diff the FKs (since the model doesn't declare them) — that's the tradeoff for CI portability, and it's fine because DATA-01 owns the FKs in its migration; nothing else does.
  - **Cascade-delete acceptance covers only same-DB FKs.** The test verifies portfolio→positions cascade (declared in the model, portable). Cascades from `auth.users` → user_preferences / portfolios / themes are Postgres-only and are not exercised in CI; they'd need a live Supabase environment to test end-to-end. When staging comes up, a smoke of "deleting an auth.user cascades to their portfolios" would validate.

---

## Environment state

- Backend: FastAPI app, auth, LLM wrapper, and four Phase 1 tables + `llm_calls` all live. Two migrations applied cleanly. Ruff clean.
- Frontend: unchanged.
- Database: `user_preferences`, `portfolios`, `positions`, `themes`, `llm_calls` on both sqlite (CI) and Postgres (Supabase). Postgres additionally has FKs to `auth.users`.
- Vectors: unchanged (none).
- Tests: 8 hermetic, 1 opt-in.
- CI: `ci.yml` runs backend ruff + pytest + frontend build + lint + test.
- Docs: unchanged.

---

## Open questions / blockers

- **None.** DATA-02 is next — Pydantic schemas for the same four entities. Purely translation from the ORM shape to Pydantic v2 models for request/response bodies.

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
