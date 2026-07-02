# Handoff — Lumen Intelligence Agent

**Branch:** `v2/intelligence-agent`
**Base:** `refactor` (at commit `af39bef` — latest from origin/refactor)
**Last updated:** 2026-07-02 (session 1 — BOOT-01 legacy pruning)
**Progress:** 3/60 modules complete (HP-01, HP-02, BOOT-01)

---

## Next module

**ID:** `BOOT-02`
**Title:** FastAPI scaffolding
**Depends on:** BOOT-01
**Read:** `BUILD.md` → the `BOOT-02` block (that section only)

**Branch state:** `v2/intelligence-agent` is checked out in worktree `.claude/worktrees/brave-benz-6b19f2`. BOOT-01's pruning commit is on top of `856d503`. `backend/` now contains only the four allowlisted files plus two `__init__.py` markers (see below); the FastAPI app has yet to be built.

Before starting, verify:
- `git branch --show-current` shows `v2/intelligence-agent`.
- `git log --oneline -3` shows the BOOT-01 commit on top of `856d503` and `f7e479a`.
- `git status` is clean.
- `git ls-files backend | wc -l` returns 6 (see below for the list).

---

## Last session

- **Session goal:** Execute BOOT-01 — prune the discarded invoice/OCR/dashboard trajectory from `v2/intelligence-agent` down to the allowlist in BUILD.md's Files section.
- **Completed:**
  - `BOOT-01` ✅ — legacy pruning (branch itself was already cut in session 0).
  - Root-level docs removed: `ARCHITECTURE.md`, `API_DOCS.md`, `CHATBOT_INTEGRATION.md`, `DEMO_VIDEO_GUIDE.md`, `DEPLOYMENT.md`, `DOCUMENTATION_COMPLETE.md`, `DOCUMENTATION_INDEX.md`, `PROBLEM_STATEMENT.md`, `QUICK_START.md`, `SETUP.md`.
  - Backend pruned to 6 files: `backend/.gitignore`, `backend/config.py`, `backend/utils/__init__.py`, `backend/utils/auth.py`, `backend/utils/logging_config.py`, `backend/scripts/__init__.py`. Everything else under `backend/` was deleted, including all invoice/OCR routes, the old `ai/` orchestrator directory, all utility scripts, stale test files, and the stale `chroma_db/` index.
  - Frontend pruned to 27 files under `frontend/src`: `app/layout.tsx`, `app/globals.css`, `app/signin/page.tsx`, `components/auth/*`, all shadcn primitives under `components/ui/` (minus `testimonials-column.tsx`), `hooks/use-mobile.ts`, `lib/supabase/client.ts`, `lib/utils.ts`. Everything else under `frontend/src/` was deleted — dashboard/chatbot/analytics/ai-analytics/landing pages, the marketing landing components, the invoice/email dialogs, the old Flask API client, the dashboard nav components, and the invoice-shaped app-sidebar.
- **Files touched:** 151 deletions + 3 modifications (`BUILD.md` ticked BOOT-01; `frontend/src/app/signin/page.tsx` and `frontend/src/components/auth/auth-provider.tsx` had imports pointing at now-deleted paths removed — see "Deviations" below).
- **Migrations added:** none.
- **Tests added:** none.
- **In-flight work:** none.
- **Deviations from BUILD.md:**
  - `frontend/src/app/signin/page.tsx` (a kept file) imported `Aurora` from `@/components/landing/Aurora` (a deleted directory). Dropped the import and the two decorative background renderings. Signin still works; BOOT-04's frontend scaffolding reset will restyle.
  - `frontend/src/components/auth/auth-provider.tsx` (a kept file) imported `tokenManager` from `@/lib/api/client` (deleted, since that whole Flask-era client is invoice/OCR/email trajectory). Dropped the import and the `syncSessionToLocalState` helper it powered. The auth provider still exposes `session`/`user`/`loading` via context — which is all `auth-guard.tsx` and `signin/page.tsx` consume.
  - `frontend/src/components/ui/testimonials-column.tsx` was deleted despite living under `components/ui/`. It is not a generic UI primitive — it is a landing-page marketing component and has no consumers among the kept files.
  - `frontend/public/*` was left untouched (dealership imagery, Cliste logo, etc. are still there). BUILD.md's Files scope for the frontend is `frontend/src/`; BOOT-04 or DEPLOY-06 can address `public/` when they run.
  - `docs/AUTH.md` and `docs/screenshots/README.md` were left untouched. BUILD.md's markdown delete list enumerated root-level docs only; `docs/` was not in it.
  - `CONTRIBUTING.md` was kept. It is not in the delete enumeration and is not trajectory-specific.

---

## Environment state

- Backend: pruned to the allowlisted set. FastAPI app not yet built — that's BOOT-02.
- Frontend: pruned to auth-only. No product pages, no landing. `app/signin` still renders (without the Aurora background). No `/` route — root `page.tsx` was deleted. BOOT-04 rebuilds the frontend scaffold.
- Database: local dev untouched; Supabase project unchanged.
- Vectors: `backend/chroma_db/` deleted. Fresh store will be created by ING-07.
- Tests: no v2 tests exist yet.
- CI: `.github/workflows/handoff-check.yml` remains installed. Product-code CI comes in BOOT-08.
- Docs on `v2/intelligence-agent`: `PRD.md`, `BUILD.md`, `HANDOFF.md`, `CONTRIBUTING.md`, `LICENSE`, `README.md` (to be rewritten in DEPLOY-06), `TODO.md` (frozen), `docs/AUTH.md`, `docs/screenshots/README.md`.

---

## Open questions / blockers

- **None.** All deviations above are noted and self-explanatory. BOOT-02 can start immediately.

---

## Rules for the next session

1. **Read `HANDOFF.md` first** (this file). Do this before anything else.
2. **Read `PRD.md`** (all of it — it's short). Non-goals and principles are vetoes.
3. **Read the `BUILD.md` block for the "Next module" ID above.** Do NOT read other module blocks unless the current one lists them as dependencies.
4. **Do NOT re-read the entire repo.** Files outside the module's scope are irrelevant.
5. **Implement the module and only the module.** Match Acceptance criteria literally.
6. **Do NOT expand scope.** If you notice an adjacent problem, add it as a new module ID in `BUILD.md` — don't fold it into the current work.
7. **Before ending the session:**
   - Tick the module's checkbox in `BUILD.md` (append ` ✅` to the module heading — that's the convention set by HP-01/HP-02/BOOT-01).
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
