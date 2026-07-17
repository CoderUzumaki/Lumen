# Handoff — Lumen Intelligence Agent

**Branch:** `v2/intelligence-agent`
**Base:** `refactor` (at commit `af39bef` — latest from origin/refactor)
**Last updated:** 2026-07-17 (session 30 — IMP-01 impact schema + migration)
**Progress:** 32/60 modules complete (HP-01, HP-02, BOOT-01..BOOT-08, DATA-01..DATA-05, ING-01..ING-10, REL-01..REL-06, IMP-01). DATA-06 (frontend UI) + REL-07 (frontend news feed) still pending — both are frontend-blocked; backend continues into Phase 4 (Impact Analysis Agent).

---

## Next module

**ID:** `IMP-02`
**Title:** Historical analogs collection + retrieval tool
**Depends on:** ING-07 (Chroma collection init).
**Read:** `BUILD.md` → the `IMP-02` block starting at ~line 944. Adds a new Chroma collection `historical_analogs`, a seed script `backend/app/evals/seed_analogs.py` populating ~150 curated events (Fed decisions, earnings surprises, geopolitical shocks, sector rotations from the last 15 years), and a `retrieve_analogs(query_text: str, k: int = 3) -> list[HistoricalAnalog]` tool that semantic-searches at minimum similarity 0.6. Seed script must be idempotent (replace on `event_hash`).

Acceptance: seed script populates; `retrieve_analogs("Federal Reserve rate cut")` returns ≥ 2 relevant events.

**Where to look for patterns:**
- `HistoricalAnalog` Pydantic type is defined in `backend/app/schemas/impact.py` (added in IMP-01).
- Chroma collection init pattern: `backend/app/db/vectorstore.py` (see `init_collections`).
- The prefilter/classifier tests exercise VectorStore usage in `tests/agents/test_relevance_prefilter.py` — mirror the fixture shape.
- Curated seed content is real work — draft a JSON/YAML fixture in `app/evals/data/analogs.json` (or similar) that the seed script iterates.

**Branch state:** `impact_assessments` table + Alembic migration `c3b8f4e1d7a2` are live. `Citation` / `HistoricalAnalog` / `ImpactAssessment` Pydantic schemas in `app/schemas/impact.py`. `ImpactRead` schema also defined but not yet wired into any endpoint — `ClusterDetailRead.impact` is still `Any = None` in `app/schemas/news.py`. Tighten that field to `ImpactRead | None = None` once IMP-04 lands and there's a real row to serialize (or in a small cleanup pass, whichever's more convenient).

Before starting, verify:
- `git branch --show-current` (from `.claude/worktrees/v2`) shows `v2/intelligence-agent`.
- `git log --oneline -5` shows IMP-01 on top.
- `git status` is clean.
- `cd backend && python -m pytest tests -q` reports **191 passed, 5 deselected**.
- `ruff check .` clean.
- `DATABASE_URL="sqlite:///./_scratch.db" alembic upgrade head` → downgrade -1 → upgrade head all clean (delete the scratch db afterward).

---

## Last session

- **Session goal:** Execute IMP-01 — introduce the `impact_assessments` table (ORM + migration) and the Pydantic wire types (`Citation`, `HistoricalAnalog`, `ImpactAssessment`, `ImpactRead`) that IMP-04 will produce and later endpoints will serve.
- **Completed:**
  - `IMP-01` ✅ — Impact schema + migration.
  - `backend/app/db/models/impact.py` — `ImpactAssessment` ORM model. Fields mirror BUILD.md's spec DDL. Portability recipe copied from REL-01:
    - `JSONB` columns (`citations`, `historical_analogs`, `guardrail_violations`) declared as `postgresql.JSONB().with_variant(JSON, "sqlite")`.
    - `affected_positions` typed `list[str]` on the wire (sqlite JSON encoder can't handle `UUID`); DDL is `ARRAY(UUID).with_variant(JSON, "sqlite")`.
    - CHECKs in `__table_args__`: `confidence BETWEEN 0 AND 1`, `timeframe_days IS NULL OR BETWEEN 1 AND 365`. Uses `IdMixin + CreatedAtMixin` for `id` / `created_at`.
    - Unique constraint `(cluster_id, user_id, portfolio_id)`; index `(user_id, created_at)`.
  - `backend/app/db/models/__init__.py` — registered `ImpactAssessment`.
  - `backend/alembic/versions/c3b8f4e1d7a2_imp01_impact_assessments.py` — Alembic migration on top of REL-01 head (`b8ef3a217c04`). Dialect-conditional bits:
    - `_uuid_array()` + `_jsonb()` helpers for the with-variant types.
    - **`ck_impact_assessments_citations_nonempty` is inline in `create_table`** (sqlite doesn't support `ALTER TABLE ADD CONSTRAINT`), with dialect-specific SQL: `jsonb_array_length(citations) >= 1` on Postgres, `json_array_length(citations) >= 1` on sqlite.
    - `affected_positions` server default is `'{}'::uuid[]` on Postgres, `'[]'` on sqlite.
    - `fk_impact_assessments_user_id` FK to `auth.users(id)` is Postgres-only (same recipe as REL-01).
  - `backend/app/schemas/impact.py` — Pydantic wire types:
    - `Citation` — `source`, `url` (`HttpUrl`), `title`, `quote` (`max_length=300`).
    - `HistoricalAnalog` — `event_description`, `when` (`date`), `outcome_description`, `similarity_score` (`ge=0, le=1`).
    - `ImpactAssessment` — LLM output shape. `mechanism` (`min_length=50, max_length=1500`), `magnitude_low`/`magnitude_high` (`float | None`), `timeframe_days` (`ge=1, le=365`), `confidence` (`ge=0, le=1`), `falsifiability` (`min_length=20, max_length=500`), `citations` (`min_length=1`), `historical_analogs` (default `[]`), `affected_positions` (`min_length=1`).
    - `ImpactRead` — DB row read shape used by future endpoints.
  - `backend/tests/db/test_impact.py` — 12 hermetic tests:
    - ORM insert + read roundtrip through every column.
    - Unique constraint on `(cluster, user, portfolio)`.
    - Confidence CHECK rejects out-of-range values.
    - Timeframe CHECK: NULL and 1..365 accepted; 400 rejected. Second-row fixture uses `is_active=False` because `idx_portfolios_user_active` (partial unique) permits at most one active pf per user.
    - Cluster / portfolio delete cascades.
    - Pydantic: empty citations rejected, empty affected_positions rejected, confidence / timeframe bounds enforced, `HistoricalAnalog.similarity_score` bounded, `Citation.quote` max 300 chars.
    - `test_migration_rejects_empty_citations` — runs `command.upgrade(cfg, "head")` against a fresh sqlite (via `monkeypatch.setenv("DATABASE_URL", ...)`), then raw-INSERTs a row with `citations='[]'` and asserts CHECK failure. Verifies the dialect-conditional migration-level check without an inline model constraint.
- **Acceptance verified locally:**
  - `python -m pytest tests -q` → **191 passed, 5 deselected** (+12 new hermetic tests).
  - `ruff check .` clean.
  - `alembic upgrade head` → `downgrade -1` → `upgrade head` clean on sqlite (also runs inside the migration test).
- **Files touched:** created `backend/app/db/models/impact.py`, `backend/app/schemas/impact.py`, `backend/alembic/versions/c3b8f4e1d7a2_imp01_impact_assessments.py`, `backend/tests/db/test_impact.py`. Modified `backend/app/db/models/__init__.py` (registered ImpactAssessment), `BUILD.md` (tick), `HANDOFF.md` (this file).
- **Migrations added:** 1 (`c3b8f4e1d7a2_imp01_impact_assessments`).
- **Tests added:** 12 hermetic.
- **In-flight work:** none.
- **Deviations from BUILD.md:**
  - **The `citations` non-empty CHECK is dialect-conditional and lives ONLY in the migration**, not in the ORM's `__table_args__`. sqlite can't ALTER ADD CONSTRAINT so the CHECK is inline in `create_table`; the SQL body differs per dialect (`jsonb_array_length` on Postgres vs. `json_array_length` on sqlite). Pydantic `min_length=1` on `ImpactAssessment.citations` gives the app-layer gate.
  - **Added a `timeframe_days` CHECK** (`NULL OR BETWEEN 1 AND 365`) that BUILD.md doesn't spell out — Pydantic already bounds this on the wire, but the DB gate mirrors the intent cheaply and matches the `confidence` CHECK's style.
  - **`ImpactAssessment` class name collides across `db/models/impact.py` and `schemas/impact.py`.** Callers disambiguate at import time. Tests use `from app.schemas.impact import ImpactAssessment as ImpactAssessmentPayload` to distinguish.
  - **`test_migration_rejects_empty_citations` re-enables all named loggers after `command.upgrade`** — alembic env.py calls `fileConfig(alembic.ini)`, which by default disables every existing named logger. Without the re-enable, the fanout caplog test that runs later sees no records. Documented in the test's docstring.

---

## Environment state

- Backend: impact schema + wire types are live. IMP-02..IMP-05 can now start plumbing the analyst pipeline.
- Frontend: unchanged.
- Database: Alembic head `c3b8f4e1d7a2`. `impact_assessments` table exists.
- Vectors: unchanged. IMP-02 will add a third Chroma collection (`historical_analogs`).
- Tests: **191 hermetic, 5 opt-in.**
- CI: REL-03..IMP-01 pending push through CI.
- Docs: unchanged.

---

## Open questions / blockers

- **None.** IMP-02 introduces the historical-analogs Chroma collection + retrieval tool. Curated seed content (~150 events) is the boring-but-important part — draft as a JSON fixture in `app/evals/data/` before wiring the seed script.

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
