# Handoff — Lumen Intelligence Agent

**Branch:** `v2/intelligence-agent` *(not yet cut — BOOT-01 creates it from `refactor`)*
**Base:** `refactor` (at commit `af39bef` — latest from origin/refactor)
**Last updated:** 2026-07-02 (session 0 — planning + handoff CI installed)
**Progress:** 2/60 modules complete (HP-01, HP-02)

---

## Next module

**ID:** `BOOT-01`
**Title:** Cut the `v2/intelligence-agent` branch and prune legacy
**Depends on:** none
**Read:** `BUILD.md` → the `BOOT-01` block (that section only)

Before starting, verify:
- `git status` is clean.
- `git branch --show-current` shows `refactor` (or you are about to check it out).
- `git fetch origin && git log origin/refactor..refactor` is empty (local matches remote).

---

## Last session

- **Session goal:** Produce PRD and BUILD documents for the pivot to Personal Financial Intelligence Agent, plus install the handoff-protocol CI check early.
- **Completed:**
  - `PRD.md` — full product requirements (design principles, non-goals, journeys, success criteria, free-tier constraint, modern-UI principle).
  - `BUILD.md` — 60 modules across 11 phases with schemas, endpoints, acceptance criteria, dependencies. Includes cross-cutting Design System (DESIGN-01..03), AI Pipeline Optimizations (OPT-01..06), Benchmarking (BENCH-01..04), Guardrails (GRD-01..03), and Handoff Protocol.
  - `HANDOFF.md` — this file, the pointer for the next session.
  - `HP-01` ✅ — `HANDOFF.md` created per template.
  - `HP-02` ✅ — `.github/workflows/handoff-check.yml` installed. Enforces file existence + required sections (hard fail); emits warnings on freshness > 14 days and on pushes/PRs that change code but not `HANDOFF.md`.
- **Files touched:** `PRD.md` (new), `BUILD.md` (new), `HANDOFF.md` (new), `.github/workflows/handoff-check.yml` (new). No product code yet.
- **Migrations added:** none.
- **Tests added:** none. The CI workflow itself is verified by running it (first push triggers a live check).
- **In-flight work:** none — planning phase complete and handoff protocol enforced by CI.
- **Deviations from BUILD.md:** HP-02 (the CI check) was promoted from BOOT-08 into the handoff phase so it activates from day one instead of after CI baseline. BUILD.md updated accordingly.

---

## Environment state

- Backend: still on the discarded trajectory (Flask + invoice/OCR). BOOT-01 will prune this.
- Frontend: still has old dashboard/chatbot/analytics/landing pages. BOOT-01 will prune.
- Database: local dev untouched; Supabase project unchanged.
- Vectors: existing Chroma index at `backend/chroma_db/` is stale — BOOT-01 deletes it.
- Tests: no v2 tests exist yet.
- CI: `.github/workflows/handoff-check.yml` installed (HP-02). Product-code CI still comes in BOOT-08.
- Files uncommitted on this worktree (pending your review before the branch cut): `PRD.md`, `BUILD.md`, `HANDOFF.md`, `.github/workflows/handoff-check.yml`.

---

## Open questions / blockers

- **None.** The user has approved Option D (Personal Financial Intelligence Agent) with:
  - Free-tier tooling throughout.
  - Modern dark-first Linear/Vercel-style UI.
  - AI pipeline optimizations that produce resume bullets (OPT-01..06).
  - Benchmarking harness (BENCH-01..04) backing every claim.
  - Explicit handoff protocol so context-limit sessions can chain cleanly.

---

## Rules for the next session

1. **Read `HANDOFF.md` first** (this file). Do this before anything else.
2. **Read `PRD.md`** (all of it — it's short). Non-goals and principles are vetoes.
3. **Read the `BUILD.md` block for the "Next module" ID above.** Do NOT read other module blocks unless the current one lists them as dependencies.
4. **Do NOT re-read the entire repo.** Files outside the module's scope are irrelevant.
5. **Implement the module and only the module.** Match Acceptance criteria literally.
6. **Do NOT expand scope.** If you notice an adjacent problem, add it as a new module ID in `BUILD.md` — don't fold it into the current work.
7. **Before ending the session:**
   - Tick the module's checkbox in `BUILD.md`.
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
