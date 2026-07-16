# Handoff — Lumen Intelligence Agent

**Branch:** `v2/intelligence-agent`
**Base:** `refactor` (at commit `af39bef` — latest from origin/refactor)
**Last updated:** 2026-07-03 (session 26 — REL-03 classifier)
**Progress:** 28/60 modules complete (HP-01, HP-02, BOOT-01..BOOT-08, DATA-01..DATA-05, ING-01..ING-10, REL-01..REL-03). DATA-06 (frontend UI) still pending.

---

## Next module

**ID:** `REL-04`
**Title:** Relevance graph (LangGraph)
**Depends on:** REL-02, REL-03
**Read:** `BUILD.md` → the `REL-04` block. Composes `run_prefilter()` + `run_classifier()` into a LangGraph node graph with an idempotency check.

**Branch state:** REL-01 schema + REL-02 prefilter + REL-03 classifier all live. `run_prefilter()` short-circuits or hands a shortlist to `run_classifier()`, which structures the LLM output into a `RelevanceVerdict` and writes a `stage='classifier'` row.

Before starting, verify:
- `git branch --show-current` (from `.claude/worktrees/v2`) shows `v2/intelligence-agent`.
- `git log --oneline -28` shows REL-03..HP-01 on top of `856d503` / `f7e479a`.
- `git status` is clean.
- `cd backend && python -m pytest tests -q` reports **159 passed, 5 deselected**.
- `ruff check .` clean.

---

## Last session

- **Session goal:** Execute REL-03 — the LLM classifier stage. Given a cluster + prefilter shortlist, prompt the fast-tier LLM for structured `RelevanceVerdict`, guardrail hallucinated IDs, persist a `stage='classifier'` row.
- **Completed:**
  - `REL-03` ✅ — LLM classifier.
  - `backend/app/agents/relevance/classifier.py`:
    - `RelevanceVerdict(BaseModel)` — `score: float [0,1]`, `touched_positions: list[UUID]`, `touched_themes: list[UUID]`, `rationale: str` (≤500 chars).
    - `_SYSTEM_PROMPT` — mechanism-language guardrail baked in: "Use mechanism language — never recommend buy, sell, or hold."
    - `_build_user_prompt(cluster, body, positions, themes)` — formats the event title + body[:1500] + bulleted candidates with UUIDs.
    - `run_classifier(cluster_id, portfolio_id, candidate_position_ids, candidate_theme_ids, session, llm, agent_name)`:
      1. Loads the cluster, portfolio (for user_id), most-recent NewsItem body (best-effort), and the shortlisted positions/themes.
      2. Calls `llm.complete(messages, tier="fast", response_model=RelevanceVerdict, ...)`.
      3. Guardrails hallucinated IDs by intersecting `verdict.touched_positions/touched_themes` with the caller-supplied shortlist.
      4. Persists `RelevanceScore(stage='classifier', score=clamp(0..1), touched_position_ids=[str(...)], touched_theme_ids=[str(...)], rationale=verdict.rationale)`.
  - **Model tweak:** `RelevanceScore.touched_position_ids` / `touched_theme_ids` moved from `Mapped[list[UUID]]` to `Mapped[list[str]]`. Sqlite's JSON variant can't `json.dumps` a UUID object; the ARRAY variant stays functional on Postgres. Callers stringify at the boundary.
  - `backend/tests/agents/test_relevance_classifier.py`:
    - `test_persists_classifier_row_with_touched_ids` — end-to-end with a mocked LLM returning a canned verdict.
    - `test_hallucinated_ids_are_filtered_out` — LLM outputs a UUID not in the shortlist; guardrail drops it.
    - `test_score_clamped_and_rationale_persists` — score=1.0 → Decimal("1.00"); rationale round-trips.
    - `test_prompt_contains_title_body_positions_themes` — the user prompt names the event title, body content, ticker, theme description, and both UUIDs.
    - `@pytest.mark.free_tier_live test_classifier_hand_labeled_10_cases` — opt-in live probe against real OpenRouter with 10 hand-labeled event/ticker pairs (5 clear hits, 5 clear irrelevant). Passes when ≥8/10 verdicts match the expected `touched` flag. Skipped by default; enable with `pytest -m free_tier_live`.
- **Acceptance verified locally:**
  - `python -m pytest tests -q` → **159 passed, 5 deselected**.
  - `ruff check .` clean.
- **Files touched:** created `backend/app/agents/relevance/classifier.py`, `backend/tests/agents/test_relevance_classifier.py`. Modified `backend/app/db/models/relevance.py` (`touched_*` type flip), `BUILD.md` (tick), `HANDOFF.md` (this file). No migration change needed — the DDL types (`ARRAY(UUID)` / `JSON`) still match.
- **Migrations added:** none.
- **Tests added:** 5 (4 hermetic + 1 opt-in live).
- **In-flight work:** none.
- **Deviations from BUILD.md:**
  - **`touched_position_ids` / `touched_theme_ids` wire type is `list[str]`, not `list[UUID]`.** Necessary for portability: sqlite's default JSON serializer trips on `uuid.UUID`. The DDL is unchanged — Postgres still gets `ARRAY(UUID)`, sqlite still gets `JSON`. Callers stringify at the boundary; that keeps ORM behavior symmetric across dialects.
  - **10-label live acceptance test is opt-in via `@pytest.mark.free_tier_live`.** BUILD.md's Acceptance says "≥ 8/10 correct classifications" — the hand-labeled fixture is embedded in the test but only runs under `pytest -m free_tier_live` with a real `OPENROUTER_API_KEY`. Default runs stay hermetic; production-grade quality gating happens on demand.
  - **LangSmith trace visibility is inherent to `LLMClient.complete()`** (BOOT-06 wired tracing routing there). No REL-03-specific tracing code.

---

## Environment state

- Backend: prefilter + classifier both wired. LangGraph composition (REL-04) is next.
- Frontend: unchanged.
- Database: Alembic head `b8ef3a217c04`. Type flip in the model doesn't require a migration.
- Vectors: unchanged.
- Tests: **159 hermetic, 5 opt-in.**
- CI: last successful run on REL-02.
- Docs: unchanged.

---

## Open questions / blockers

- **None.** REL-04 composes prefilter → classifier as a LangGraph, adds the idempotency check (return cached row when it exists, unless `force=True`).

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

---

## Session mechanics (new-agent bootstrap)

Read this before your first tool call. It's the accumulated tribal knowledge
from ~28 modules of building on this branch.

### Where to work

- **Worktree:** `D:\Project\New folder (2)\Lumen\.claude\worktrees\v2` — that
  is where `v2/intelligence-agent` is currently checked out.
- **Other worktrees** exist (`brave-benz-6b19f2`, `jolly-benz-09303c`,
  `silly-chebyshev-4fe09f`) but are on different branches. Ignore them.
- **The remote is at** `origin/v2/intelligence-agent` — every completed
  module has been pushed there. Rebase / diverge protection: if a later
  session cuts a new worktree, use `git worktree add … v2/intelligence-agent`
  from an existing worktree that has a fetch of origin.

### Path + shell gotchas

- **The Bash tool resets cwd to the session's original directory after every
  command.** Standalone `cd` doesn't persist. Prefix every Bash call that
  needs to touch v2 with either `cd "…/worktrees/v2/backend" && …` (single
  compound command) or use `git -C "…/worktrees/v2" …` for git.
- **Read / Edit / Write tools DO work with absolute Windows paths** across
  worktrees. Use those for file ops; use Bash only for shell things.
- **Windows path form:** `D:/Project/New folder (2)/Lumen/…` in Bash;
  `D:\Project\New folder (2)\Lumen\…` in Read/Edit/Write. Both work in
  their respective tools.

### Repeated `<system-reminder>` about brave-benz-6b19f2

Every user turn currently includes a system-reminder saying the following
files at `.claude/worktrees/brave-benz-6b19f2/` were modified by "the user
or a linter":
- `frontend/.env.example`
- `frontend/src/app/globals.css`
- `frontend/src/app/page.tsx`
- `frontend/src/app/layout.tsx`

These reverts belong to the OTHER worktree (which is on `claude/brave-benz-…`
at `refactor` @ `af39bef`). They do NOT touch the v2 worktree. Rule from
those reminders: "don't revert it unless the user asks you to. Don't tell
the user this." Translation: **ignore them; keep working in the v2
worktree**. Do not attempt to sync those files back to your good v2 copies.

### CI

- Workflow: `.github/workflows/ci.yml` (BOOT-08). Two jobs: backend
  (`ruff check .` + `pytest`) and frontend (`npm ci && npm run lint &&
  npm run build && npm test`). Every push to `v2/intelligence-agent` runs it.
- Watch a run: `gh run list --branch v2/intelligence-agent --limit 3
  --workflow "CI"` then `gh run watch <id> --exit-status`.
- Test markers deselected by default: `free_tier_live` (opt-in LLM probes),
  `integration` (opt-in external HTTP probes).

### Local dev machinery already installed

- **Python 3.11.5** at `C:\Users\Acer\AppData\Local\Programs\Python\Python311`.
- All backend deps that the suite exercises are installed in the system
  interpreter: `fastapi`, `httpx`, `sqlalchemy`, `alembic`, `pytest`,
  `pytest-asyncio`, `aiosqlite`, `psycopg2-binary`, `chromadb`,
  `sentence-transformers`, `feedparser`, `selectolax`, `PyJWT[crypto]`,
  `apscheduler`, `tenacity`, `python-dotenv`, `ruff==0.7.0`, `numpy`.
  Fresh module deps may need `python -m pip install --quiet <pin>`.
- **Node 22.19.0 / npm 11.6.2** on PATH. Frontend deps only need install
  when working the frontend (DATA-06).

### Module cadence — what a session looks like

1. `git -C "…/worktrees/v2" status` and confirm clean tree.
2. Read the top of `HANDOFF.md` — "Next module" tells you the ID.
3. Read `PRD.md` if you haven't (short — non-goals are vetoes).
4. Read ONLY that module's block in `BUILD.md`. Do not scan around.
5. Implement per Acceptance criteria. Local iteration:
   ```
   cd "…/v2/backend" && python -m pytest tests/<...>::<test> -v
   cd "…/v2/backend" && python -m pytest tests -q
   cd "…/v2/backend" && ruff check .
   ```
6. Migration modules: `DATABASE_URL="sqlite:///./_scratch.db" alembic
   upgrade head` → `alembic downgrade -1` → `alembic upgrade head` must
   be clean. Delete `_scratch.db` before committing.
7. Tick the module heading in `BUILD.md` (append ` ✅`).
8. Rewrite the "Last session" and "Next module" sections in this file.
   Bump progress count.
9. Commit with message `<MODULE-ID>: <one-line summary>` and push. Watch CI.

### Portability rules the code enforces

Every DB migration must run on both Postgres (prod) and sqlite (CI). The
patterns already in the tree:

- **Postgres-specific FKs (to `auth.users`) are conditional in the
  migration** — `if op.get_bind().dialect.name == "postgresql":` wraps
  them. See DATA-01 / REL-01.
- **`ARRAY(String)` and `JSONB` are declared with `.with_variant(JSON,
  "sqlite")`** — see `app/db/models/news.py` and `.../relevance.py`.
- **UUIDs in JSON-variant columns** aren't `json.dumps`-serializable →
  store them as `list[str]` on the wire (see `RelevanceScore.touched_*`)
  and stringify at the caller boundary.
- **Chroma is cosine-space** for all three collections (`hnsw:space:
  cosine` in `_COLLECTION_METADATA`) so similarity threshold semantics
  are `similarity = 1 - distance`.
- **Fresh DB per test** via `tempfile.mkstemp` + `PRAGMA foreign_keys=ON`;
  Chroma via `tempfile.mkdtemp` + `chromadb.PersistentClient`. Existing
  fixtures in `tests/db/`, `tests/pipelines/`, and `tests/agents/` are
  the reference.

### Deviations you might trip over

- `RequestValidationError` returns **HTTP 400**, not 422 (DATA-03's spec).
- FastAPI 204 endpoints declare `response_class=Response` and return
  `Response(status_code=204)` (0.115 refuses inferred bodies at 204).
- `tenacity==8.5.0` (not the BUILD.md-pinned 9.0.0) — 9.x conflicts with
  `langchain 0.3.3`. Fixed in the BOOT-08 commit chain.
- `EmbeddingClient` is re-exported from `app.utils.llm` for legacy import
  paths; real implementation is `app.utils.embeddings`.
- `_to_naive_utc()` in `clusterer.py` — sqlite drops tzinfo on datetime
  round-trip; comparisons must coerce first.
- Cluster 48h lookback in `clusterer.py` is client-side (Chroma's `$gte`
  needs numeric operands, our `published_at_iso` is a string).

### Files you should never touch without a reason

- `TODO.md` (frozen — old trajectory).
- `docs/AUTH.md`, `docs/screenshots/README.md` (external docs).
- `CONTRIBUTING.md`, `LICENSE`.
- The four brave-benz `<system-reminder>` files enumerated above.

### If something in the tree surprises you

Grep `HANDOFF.md` history: every module's "Deviations from BUILD.md" bullet
lists why a spec-departure was made. Nothing in `app/` or `alembic/` is
there by accident.
