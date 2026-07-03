# Handoff — Lumen Intelligence Agent

**Branch:** `v2/intelligence-agent`
**Base:** `refactor` (at commit `af39bef` — latest from origin/refactor)
**Last updated:** 2026-07-03 (session 11 — DATA-03 portfolios + positions routes)
**Progress:** 13/60 modules complete (HP-01, HP-02, BOOT-01..BOOT-08, DATA-01..DATA-03).

---

## Next module

**ID:** `DATA-04`
**Title:** Themes routes
**Depends on:** DATA-01, DATA-02, ING-07
**Read:** `BUILD.md` → the `DATA-04` block.

**Important dependency wrinkle:** DATA-04 depends on ING-07 (Chroma vector store + local embeddings) — on create/update, DATA-04 stores a `themes` collection doc in Chroma and persists the doc id in `themes.embedding_id`. ING-07 hasn't been built yet (Phase 2). The next session should either (a) advance to Phase 2 modules that unblock ING-07, or (b) implement DATA-04 with a stub `EmbeddingClient` call (already exists in `app.utils.llm.EmbeddingClient` — raises NotImplementedError until ING-07). Recommend the user pick before starting.

**Branch state:** BOOT-01..BOOT-08 + DATA-01..DATA-03 stacked on `856d503`. Portfolios + positions have a live HTTP surface, ownership scoping (cross-user → 404), the activate-swap semantic, and validation-error responses at status 400 with the `validation_error` envelope code.

Before starting, verify:
- `git branch --show-current` shows `v2/intelligence-agent`.
- `git log --oneline -13` shows DATA-03..HP-01 on top of `856d503` / `f7e479a`.
- `git status` is clean.
- `cd backend && python -m pytest tests -q` reports **65 passed, 1 deselected**.
- `ruff check .` clean.

---

## Last session

- **Session goal:** Execute DATA-03 — implement the 10 portfolio + position endpoints, enforce owner scoping (cross-user access returns 404), enforce the "one active portfolio per user" semantic in the `/activate` endpoint, and route ticker-validation failures to a 400 + `validation_error` envelope response.
- **Completed:**
  - `DATA-03` ✅ — portfolios + positions routes.
  - `backend/app/db/models/portfolio.py` — added `positions` relationship (`selectinload` lazy loading, `cascade="all, delete-orphan", passive_deletes=True` so ORM cascades line up with the DB's ON DELETE CASCADE).
  - `backend/app/db/models/position.py` — added the reverse `portfolio` relationship.
  - `backend/app/routes/__init__.py` (empty package marker).
  - `backend/app/routes/portfolios.py` — router at prefix `/api/portfolios`:
    - `POST` → `create_portfolio` (201). When `is_active=True`, deactivates any pre-existing active portfolio for the same user before insert.
    - `GET` → `list_portfolios` ordered by `created_at`.
    - `GET /{portfolio_id}` → `get_portfolio` (404 if not owned).
    - `PUT /{portfolio_id}` → `update_portfolio` (200). Applies `body.model_dump(exclude_unset=True)`; if the change activates the portfolio, first deactivates any other active portfolio for the user.
    - `DELETE /{portfolio_id}` → `delete_portfolio` (204, `response_class=Response` to satisfy FastAPI 0.115's "204 must not have a response body" assertion).
    - `POST /{portfolio_id}/activate` → `activate_portfolio` (200). Explicitly deactivates the current active portfolio, then sets target active.
    - `POST /{portfolio_id}/positions` → `create_position` (201).
    - `GET /{portfolio_id}/positions` → `list_positions` ordered by `created_at`.
  - `backend/app/routes/positions.py` — router at prefix `/api/positions`:
    - `PUT /{position_id}` → `update_position` (200). Resolves the position by id and joins to Portfolio to enforce owner scoping.
    - `DELETE /{position_id}` → `delete_position` (204, `response_class=Response`).
  - `backend/app/main.py` — imports the two routers and `include_router`s them. Also changed the `RequestValidationError` handler to return **HTTP 400** (was 422) so DATA-03's acceptance criterion "Ticker validation errors return 400 with `validation_error` code" is literal. The `validation_error` envelope code was already correct.
  - `backend/tests/routes/__init__.py`.
  - `backend/tests/routes/test_portfolios.py` — 4 test functions covering the DATA-03 acceptance list:
    - `test_owner_crud_and_activate` — full round-trip on portfolios (create, list, get, put, add position, list positions, put position, delete position, delete portfolio) plus the activate switch across two portfolios.
    - `test_cross_user_access_returns_404` — Bob sees Alice's portfolio as 404 across every verb (GET, LIST, PUT, DELETE, activate, POST positions).
    - `test_cross_user_position_returns_404` — Bob can't touch Alice's positions.
    - `test_ticker_validation_error_returns_400_with_envelope` — a bad ticker returns 400 with `{"data": null, "error": {"code": "validation_error", ...}}`.
  - Uses a fresh sqlite scratch DB per test, `PRAGMA foreign_keys=ON`, `Base.metadata.create_all()`, and FastAPI `app.dependency_overrides` to inject a fake `UserContext` per test (Alice by default, swapped to Bob mid-test for the cross-user checks).
- **Acceptance verified locally:**
  - `python -m pytest tests -q` → **65 passed, 1 deselected** (4 new DATA-03 tests + 53 DATA-02 tests + 7 LLM tests + 1 Phase 1 schema test).
  - `ruff check .` clean.
- **Files touched:** created `backend/app/routes/{__init__,portfolios,positions}.py`, `backend/tests/routes/{__init__,test_portfolios}.py`. Modified `backend/app/db/models/portfolio.py` (added positions relationship), `backend/app/db/models/position.py` (added portfolio relationship), `backend/app/main.py` (wired routers, validation → 400), `BUILD.md` (tick), `HANDOFF.md` (this file).
- **Migrations added:** none. Relationship additions are metadata-only; the DB schema is unchanged.
- **Tests added:** 4 in `backend/tests/routes/test_portfolios.py`.
- **In-flight work:** none.
- **Deviations from BUILD.md:**
  - **Changed `RequestValidationError` status from 422 → 400.** DATA-03's Acceptance explicitly says "400". FastAPI's convention is 422; BUILD.md's own error envelope only enumerates codes, not statuses. This resolves the ambiguity in DATA-03's favour and is called out in the main.py handler comment. Any earlier client that assumed 422 for validation errors will need updating (none exist yet).
  - **Added ORM `relationship()` on Portfolio and Position.** Not in DATA-01's spec (that was a schema-only migration module); DATA-03 needs them so `PortfolioRead` can embed `positions: list[PositionRead]` via `from_attributes=True`. Same-DB `ForeignKey("portfolios.id", ondelete="CASCADE")` was already declared in DATA-01; adding the ORM relationship on top is purely a Python-level convenience.
  - **204 endpoints use `response_class=Response`.** FastAPI 0.115 fails to register a route with `status_code=204` that has any inferred response body. Setting `response_class=Response` and returning `Response(status_code=204)` is the idiomatic fix.

---

## Environment state

- Backend: 10 route endpoints live under `/api/portfolios/*` and `/api/positions/*`, all owner-scoped, all validated by DATA-02 schemas. `GET /health`, `GET /api/me` still work.
- Frontend: unchanged.
- Database: unchanged (all five product tables from DATA-01 + BOOT-06 still current).
- Vectors: unchanged (none).
- Tests: 65 hermetic, 1 opt-in. Route tests use per-test sqlite via dependency overrides — no CI dependency changes.
- CI: passing on last push.
- Docs: unchanged.

---

## Open questions / blockers

- **DATA-04's ING-07 dependency.** ING-07 (Chroma + sentence-transformers) is Phase 2. DATA-04 wants to store embedding-ids in `themes.embedding_id` and manage docs in Chroma. Two clean paths:
  1. **Skip ahead to Phase 2 (ING-01..ING-07) then come back to DATA-04.** Matches BUILD.md's stated dependency chain.
  2. **Ship DATA-04 with a stub embedding path** — the model already has `embedding_id: str | None`; on create/update, log-and-skip the Chroma write; on delete, log-and-skip the Chroma delete. Then DATA-04 is fully wired at the HTTP layer, waiting for ING-07 to fill in the Chroma calls.
  Recommend the user pick before the next session starts.

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
