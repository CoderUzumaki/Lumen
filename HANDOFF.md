# Handoff — Lumen Intelligence Agent

**Branch:** `v2/intelligence-agent`
**Base:** `refactor` (at commit `af39bef` — latest from origin/refactor)
**Last updated:** 2026-07-03 (session 12 — DATA-05 user preferences route)
**Progress:** 14/60 modules complete (HP-01, HP-02, BOOT-01..BOOT-08, DATA-01, DATA-02, DATA-03, DATA-05).

DATA-04 is intentionally postponed — it depends on ING-07 (Phase 2). Per the user's call in session 12, DATA-05 was pulled forward to close as much of Phase 1 as possible before jumping phases.

---

## Next module

**ID:** `ING-01`
**Title:** News schemas + `news_items` and `news_clusters` migration
**Depends on:** BOOT-05
**Read:** `BUILD.md` → the `ING-01` block (that section only). It has the SQL schema for `news_items` and `news_clusters` and the Pydantic model shapes.

**Branch state:** BOOT-01..BOOT-08 + DATA-01, DATA-02, DATA-03, DATA-05 stacked on `856d503`. Phase 1 is complete except for DATA-04 (blocked on ING-07) and DATA-06 (frontend UI). Phase 2 starts with ING-01. When ING-07 lands, DATA-04 can slot in with real Chroma writes. DATA-06 (frontend) can go whenever — no dependency on Phase 2.

Before starting, verify:
- `git branch --show-current` shows `v2/intelligence-agent`.
- `git log --oneline -14` shows DATA-05..HP-01 on top of `856d503` / `f7e479a`.
- `git status` is clean.
- `cd backend && python -m pytest tests -q` reports **70 passed, 1 deselected**.
- `ruff check .` clean.

---

## Last session

- **Session goal:** Execute DATA-05 — the `/api/me` endpoint (identity + preferences, auto-creates prefs on first hit) and `/api/me/preferences` (partial update).
- **Completed:**
  - `DATA-05` ✅ — user preferences route.
  - `backend/app/routes/me.py` — router at prefix `/api/me`:
    - `_get_or_create_preferences(user_id, db)` helper: SELECT by user_id; if missing, INSERT a defaults-only row and return it. Server defaults on `user_preferences` (briefing_hour=8, timezone=UTC, currency=USD, model_tier=thorough) mean the auto-created row lands with the DATA-01 defaults.
    - `GET /api/me` → `{ "user_id": str(UUID), "email": str, "preferences": UserPreferencesRead-as-dict }`.
    - `PUT /api/me/preferences` → applies `body.model_dump(exclude_unset=True)` and returns `UserPreferencesRead`.
  - `backend/app/main.py` — removed the stub `/api/me` route added in BOOT-03, includes the new `me_routes.router` alongside portfolios/positions. Cleaned up the now-unused `Depends` import; the file's `require_auth` / `UserContext` imports moved with the route into `me.py`.
  - `backend/tests/routes/test_me.py` — 5 tests:
    - `test_first_get_me_returns_defaults` — proves the row didn't exist before, `GET /api/me` returns the DATA-01 defaults, and the row exists afterwards.
    - `test_get_me_is_idempotent` — three GETs still result in a single row.
    - `test_put_preferences_persists_and_validates` — partial update changes `briefing_hour` and `model_tier` only, other fields keep their defaults, subsequent GET reads back the update.
    - `test_put_preferences_briefing_hour_out_of_range` — 400 + `validation_error` envelope.
    - `test_put_preferences_invalid_model_tier` — 400 + `validation_error` envelope.
- **Acceptance verified locally:**
  - `python -m pytest tests -q` → **70 passed, 1 deselected** (5 new DATA-05 tests + 4 DATA-03 + 53 DATA-02 + 7 LLM + 1 Phase 1 schema).
  - `ruff check .` clean.
  - Both DATA-05 acceptance criteria (first GET returns defaults; PUT validates briefing_hour range + model_tier enum) covered by explicit tests.
- **Files touched:** created `backend/app/routes/me.py`, `backend/tests/routes/test_me.py`. Modified `backend/app/main.py` (swapped stub `/api/me` for router, cleaned import), `BUILD.md` (tick), `HANDOFF.md` (this file).
- **Migrations added:** none.
- **Tests added:** 5.
- **In-flight work:** none.
- **Deviations from BUILD.md:**
  - **DATA-04 skipped for now.** The user (in-session decision) chose to advance DATA-05 first because DATA-04 depends on ING-07 (Chroma), which is Phase 2. When ING-07 lands, DATA-04 slots in naturally. This isn't a hidden pick — HANDOFF flagged it as an open question in session 11 and the user picked "DATA-05 first" via AskUserQuestion.
  - **`GET /api/me` response is bare JSON (not wrapped in the envelope).** Consistent with other DATA-03 route responses; the envelope is applied only to error paths. If the frontend later wants unified envelope shape for success too, that's a middleware-level change.

---

## Environment state

- Backend: `/api/me` returns identity + preferences with auto-create; `/api/me/preferences` accepts partial updates. Portfolios + positions live. `/health` public.
- Frontend: unchanged.
- Database: unchanged. `user_preferences` is now first-materialized at first GET.
- Vectors: unchanged (none).
- Tests: **70 hermetic, 1 opt-in.**
- CI: passing on last push (DATA-03).
- Docs: unchanged.

---

## Open questions / blockers

- **None.** ING-01 is a pure schema module: two new tables (`news_items`, `news_clusters`) via Alembic, matching Pydantic models under `backend/app/schemas/news.py`. Depends only on BOOT-05.

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
