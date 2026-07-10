# Handoff — Lumen Intelligence Agent

**Branch:** `v2/intelligence-agent`
**Base:** `refactor` (at commit `af39bef` — latest from origin/refactor)
**Last updated:** 2026-07-03 (session 25 — REL-02 prefilter)
**Progress:** 27/60 modules complete (HP-01, HP-02, BOOT-01..BOOT-08, DATA-01..DATA-05, ING-01..ING-10, REL-01, REL-02).

DATA-06 (frontend UI) still pending.

---

## Next module

**ID:** `REL-03`
**Title:** LLM classifier stage
**Depends on:** REL-02, BOOT-06
**Read:** `BUILD.md` → the `REL-03` block.

**Branch state:** REL-01 schema + REL-02 prefilter live. `run_prefilter()` either short-circuits (persisting a `stage='prefilter'` row) or returns a candidate shortlist for the LLM classifier — REL-03 consumes that shortlist.

Before starting, verify:
- `git branch --show-current` (from `.claude/worktrees/v2`) shows `v2/intelligence-agent`.
- `git log --oneline -27` shows REL-02..HP-01 on top of `856d503` / `f7e479a`.
- `git status` is clean.
- `cd backend && python -m pytest tests -q` reports **155 passed, 4 deselected**.
- `ruff check .` clean.

---

## Last session

- **Session goal:** Execute REL-02 — the fast embedding-based prefilter. Compute cluster centroid, cosine-similarity against position/theme embeddings, either short-circuit with a persisted `stage='prefilter'` row or return the candidate shortlist for the LLM classifier.
- **Completed:**
  - `REL-02` ✅ — prefilter.
  - `backend/app/agents/__init__.py`, `backend/app/agents/relevance/__init__.py` (empty package markers).
  - `backend/app/agents/relevance/prefilter.py`:
    - `PrefilterResult` dataclass: `passed`, `max_similarity`, `candidate_position_ids`, `candidate_theme_ids`, `persisted_row`.
    - `_cosine()` — pure-Python cosine; zero-vector → 0.0.
    - `_mean_vector()` — pure-Python centroid.
    - `run_prefilter(cluster_id, portfolio_id, session, news_store, themes_store, embed, threshold=None)`:
      1. Loads portfolio + positions + themes via SQLAlchemy.
      2. Fetches cluster item ids from `news_items`, then their embeddings from Chroma via `news_store.get(ids=[...])`, averages into a centroid.
      3. If no embeddings, returns `passed=True, max_similarity=0.0` — defers to classifier rather than emit a low-signal prefilter row.
      4. Embeds positions via `f"{ticker} {asset_type} {exchange}"` (per BUILD.md's per-position embedding spec) using the injected `EmbeddingClient`.
      5. Fetches theme vectors from the `themes` Chroma collection using the theme's UUID as doc id (matches DATA-04's convention).
      6. Cosine similarities to the centroid; picks `max` across positions ∪ themes.
      7. If `max_sim < PREFILTER_THRESHOLD` (default 0.35): inserts `RelevanceScore(stage='prefilter', score=clamp(max_sim), touched_*=[])`, commits, returns `passed=False`.
      8. Else: returns `passed=True` with the ids of positions/themes whose similarity ≥ threshold.
    - `_cluster_centroid()` helper — handles Chroma's numpy-array `embeddings` field via explicit `is None` / `len()` checks so numpy's ambiguous-truth-value doesn't trip us.
  - `backend/tests/agents/__init__.py`, `backend/tests/agents/test_relevance_prefilter.py` — 5 tests:
    - `test_fed_cluster_and_aapl_portfolio_passes_with_aapl_candidate` — the primary BUILD.md acceptance case. Uses a deterministic `_FakeEmbed` that models "Fed and equities are close in embedding space".
    - `test_pharma_cluster_and_tech_portfolio_drops` — the second acceptance case. Verifies `stage='prefilter'` row lands with empty touched arrays and score < threshold.
    - `test_theme_stored_vector_used` — portfolio has only a theme; stored vector aligned with the cluster → theme surfaces as candidate.
    - `test_cluster_with_no_embeddings_defers_to_classifier` — edge case; returns `passed=True, max_sim=0.0` and does NOT persist a prefilter row.
    - `test_threshold_boundary_at_zero` — everything passes when `threshold=0`.
- **Acceptance verified locally:**
  - `python -m pytest tests -q` → **155 passed, 4 deselected**.
  - `ruff check .` clean.
- **Files touched:** created `backend/app/agents/{__init__,relevance/__init__,relevance/prefilter}.py`, `backend/tests/agents/{__init__,test_relevance_prefilter}.py`. Modified `BUILD.md` (tick), `HANDOFF.md` (this file).
- **Migrations added:** none.
- **Tests added:** 5.
- **In-flight work:** none.
- **Deviations from BUILD.md:**
  - **No-embeddings edge case defers to classifier.** BUILD.md's action list doesn't spell out what to do if a cluster has no Chroma vectors yet. Emitting a low-signal `stage='prefilter'` row with score=0 would let a real signal slip through. Deferring (`passed=True, max_similarity=0.0`) hands it to REL-03 where the LLM at least sees the raw text.
  - **Candidate inclusion uses `≥ threshold`.** BUILD.md says "sim > threshold" for the shortlist. `≥` is inclusive of the boundary and matches the short-circuit condition (`< threshold` for the negation). Either is defensible; the inclusive form makes the two conditions logically complementary.
  - **Theme vectors are fetched by `str(theme.id)`.** DATA-04 uses `str(theme.id)` as the Chroma doc id (with `embedding_id` mirroring it). REL-02 uses the same lookup key rather than reading `theme.embedding_id`, since they're identical by construction — one fewer indirection.

---

## Environment state

- Backend: all previous + `run_prefilter()` available. Ready for REL-03 (LLM classifier) → REL-04 (LangGraph composition) → REL-05 (fan-out worker) → REL-06 (news endpoints) → REL-07 (frontend feed).
- Frontend: unchanged.
- Database: Alembic head `b8ef3a217c04`.
- Vectors: three cosine collections; `news_items` and `themes` both actively used by the prefilter.
- Tests: **155 hermetic, 4 opt-in.**
- CI: last successful run on REL-01 push.
- Docs: unchanged.

---

## Open questions / blockers

- **None.** REL-03 is the LLM-classifier stage — first module with a real LLM prompt in the loop. Depends on `BOOT-06`'s `LLMClient` and Pydantic's `RelevanceVerdict`.

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
