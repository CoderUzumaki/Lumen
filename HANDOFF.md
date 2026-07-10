# Handoff — Lumen Intelligence Agent

**Branch:** `v2/intelligence-agent`
**Base:** `refactor` (at commit `af39bef` — latest from origin/refactor)
**Last updated:** 2026-07-03 (session 24 — REL-01 relevance_scores schema)
**Progress:** 26/60 modules complete (HP-01, HP-02, BOOT-01..BOOT-08, DATA-01..DATA-05, ING-01..ING-10, REL-01). Phase 3 started.

DATA-06 (frontend UI) still pending.

---

## Next module

**ID:** `REL-02`
**Title:** Embedding-based prefilter
**Depends on:** REL-01, ING-07, DATA-01
**Read:** `BUILD.md` → the `REL-02` block.

**Branch state:** Phase 0/1/2 fully in place + REL-01 schema on top. `relevance_scores` table live; unique upsert works; cluster/portfolio cascades enforced. Phase 3's next step is the fast embedding-based prefilter that decides whether to short-circuit or hand off to the LLM classifier (REL-03).

Before starting, verify:
- `git branch --show-current` (from `.claude/worktrees/v2`) shows `v2/intelligence-agent`.
- `git log --oneline -26` shows REL-01..HP-01 on top of `856d503` / `f7e479a`.
- `git status` is clean.
- `cd backend && python -m pytest tests -q` reports **150 passed, 4 deselected**.
- `ruff check .` clean.

---

## Last session

- **Session goal:** Execute REL-01 — `relevance_scores` table with all the CHECK / UNIQUE / index / cascade behaviour BUILD.md specifies. Sets up the score-storage backbone Phase 3 writes to.
- **Completed:**
  - `REL-01` ✅ — relevance_scores schema.
  - `backend/app/db/models/relevance.py` — `RelevanceScore(IdMixin, Base)`:
    - `cluster_id` FK to `news_clusters.id ON DELETE CASCADE` (same-DB, portable).
    - `user_id` — bare UUID; FK to `auth.users` added conditionally in the migration for Postgres.
    - `portfolio_id` FK to `portfolios.id ON DELETE CASCADE` (same-DB).
    - `score NUMERIC(3,2)` with CHECK `BETWEEN 0 AND 1`.
    - `touched_position_ids` + `touched_theme_ids` = `ARRAY(UUID)` on Postgres, `JSON` on sqlite via `.with_variant()`. Application-side `default=list`.
    - `rationale TEXT` nullable.
    - `stage TEXT` with CHECK `IN ('prefilter','classifier')`.
    - `computed_at TIMESTAMPTZ DEFAULT now()`.
    - UNIQUE `(cluster_id, user_id, portfolio_id)` — the upsert key BUILD.md's acceptance rides on.
    - Composite index `idx_relevance_user_score` on `(user_id, score DESC)`.
  - `backend/app/db/models/__init__.py` — registered `RelevanceScore`.
  - `backend/alembic/versions/b8ef3a217c04_rel01_relevance_scores.py` — hand-written migration. `_uuid_array()` for the UUID-array columns portably. `_is_postgres()` gate wraps the `auth.users` FK. Composite index uses `sa.text("score DESC")` — sqlite parses this but ignores the DESC for planning; Postgres uses it.
  - `backend/tests/db/test_relevance.py` — 5 tests: insert + unique-triple violation, score CHECK (1.5 rejected), stage CHECK ("magic" rejected), cluster delete cascades, portfolio delete cascades. Fixture uses per-test sqlite tempdir with `PRAGMA foreign_keys=ON` so cascades actually run.
- **Acceptance verified locally:**
  - `alembic upgrade head` → `alembic downgrade -1` → `alembic upgrade head` round-trips cleanly on sqlite.
  - `python -m pytest tests -q` → **150 passed, 4 deselected**.
  - `ruff check .` clean.
- **Files touched:** created `backend/app/db/models/relevance.py`, `backend/alembic/versions/b8ef3a217c04_rel01_relevance_scores.py`, `backend/tests/db/test_relevance.py`. Modified `backend/app/db/models/__init__.py`, `BUILD.md` (tick), `HANDOFF.md` (this file).
- **Migrations added:** 1 — `b8ef3a217c04`.
- **Tests added:** 5.
- **In-flight work:** none.
- **Deviations from BUILD.md:** none. Postgres-only auth.users FK follows the DATA-01/ING-01 pattern already established.

---

## Environment state

- Backend: all previous work + `relevance_scores` table.
- Frontend: unchanged.
- Database: Alembic head `b8ef3a217c04`.
- Vectors: three cosine collections.
- Tests: **150 hermetic, 4 opt-in.**
- CI: last successful run on ING-10 push (verified locally).
- Docs: unchanged.

---

## Open questions / blockers

- **None.** REL-02 is the fast, embedding-based prefilter — depends on the vector store + `EmbeddingClient` (both live). It queries Chroma for the cluster centroid, per-position + per-theme embeddings, computes max cosine similarity, and either writes a `stage='prefilter'` row (short-circuit) or hands a shortlist to REL-03.

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
