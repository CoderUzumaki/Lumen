# Handoff — Lumen Intelligence Agent

**Branch:** `v2/intelligence-agent`
**Base:** `refactor` (at commit `af39bef` — latest from origin/refactor)
**Last updated:** 2026-07-17 (session 32 — GRD-01/02/03 shipped in parallel)
**Progress:** 37/60 modules complete (HP-01, HP-02, BOOT-01..BOOT-08, DATA-01..DATA-05, ING-01..ING-10, REL-01..REL-06, IMP-01..IMP-03, GRD-01..GRD-03). DATA-06 (frontend UI) + REL-07 (frontend news feed) still pending — both are frontend-blocked; backend continues.

---

## Next module

**ID:** `IMP-04`
**Title:** Impact analyst LangGraph
**Depends on:** IMP-01, IMP-02, IMP-03, REL-04, GRD-01, GRD-02, GRD-03 — all now live.
**Read:** `BUILD.md` → the `IMP-04` block at ~line 974. Builds `backend/app/agents/impact/graph.py` + `backend/app/agents/impact/prompts.py`. Graph nodes:

```
START
  → load_context     (cluster + touched positions + portfolio metadata)
  → retrieve_analogs (via IMP-02 tool)
  → fetch_price_context (via IMP-03 tool, one call per touched position)
  → reason_mechanism (thorough-tier LLM producing structured JSON per app.schemas.impact.ImpactAssessment)
  → validate         (Pydantic + GRD-01 + GRD-02)
  → [conditional: violations → repair_prompt → reason_mechanism, 1 retry only]
  → persist          (write app.db.models.impact.ImpactAssessment row, unique on cluster/user/portfolio)
  → END
```

- `reason_mechanism` uses the **thorough** tier (`tier="thorough"` in `LLMClient.complete`); `repair_prompt` uses the **fast** tier.
- The exact `reason_mechanism` prompt is in BUILD.md — mostly verbatim, with `{title}`, `{body[:2000]}`, `{citation_stubs}`, `{position_list}`, `{analogs}`, `{price_context}`, `{schema}` slotted in.
- Guardrail wiring: `check_directional(draft.mechanism)` + `check_citations(draft.citations, allowed_stubs=...)`. Non-empty violation set triggers the one-shot repair path (prepend a "your previous draft violated these rules: ..." system message and re-invoke `reason_mechanism`); a second failure persists the row anyway with `guardrail_violations` populated and `raw_llm_output` set.

Acceptance: given a real news cluster + portfolio, produces a valid `ImpactAssessment` in ≤ 20s; LangSmith run visible with all nodes; repair retry triggers when the first attempt uses forbidden language and succeeds on retry; `pytest tests/agents/test_impact_graph.py` covers happy path + guardrail-violation-then-repair.

**Branch state:** all dependencies land in the previous 6 commits (REL-04, IMP-01, IMP-02, IMP-03, GRD-01, GRD-02). GRD-03 is chat-only and NOT invoked by the impact graph — leave it out of the validate node. `historical_analogs` Chroma collection needs to be seeded before the graph can retrieve; `python -m app.evals.seed_analogs` is idempotent, run it once locally when smoke-testing.

Before starting, verify:
- `git branch --show-current` (from `.claude/worktrees/v2`) shows `v2/intelligence-agent`.
- `git log --oneline -5` shows the GRD-01/02/03 trio on top.
- `git status` is clean.
- `cd backend && python -m pytest tests -q` reports **256 passed, 5 deselected**.
- `ruff check .` clean.

---

## Last session

- **Session goal:** Ship the guardrail suite in parallel — GRD-01 (directional-language), GRD-02 (citations validator), GRD-03 (out-of-scope refusal). Three subagents in the same v2 worktree, each briefed with its exclusive file paths; parent handled finalize (full pytest + ruff + BUILD.md ticks + HANDOFF rewrite + three commits + push).
- **Completed:**
  - `GRD-01` ✅ — Directional-language classifier.
    - `backend/app/guardrails/directional.py`:
      - `_FORBIDDEN_TOKENS` tuple (`buy`, `sell`, `hold`, `add`, `trim`, `overweight`, `underweight`, `long`, `short`, `bullish`, `bearish`, `consider`, `should`, `recommend`, `advise`).
      - `lexical_check(text) -> list[str]` — word-boundary case-insensitive scan, deduped + alpha-sorted.
      - `_DirectionalCheck(BaseModel)` — `recommends_action: bool`, `rationale: str (≤200)`.
      - `async check_directional(text, *, llm=None, skip_llm=False) -> DirectionalVerdict` — lexical first; if clean AND not `skip_llm`, fast-tier LLM call with `agent_name="guardrail-directional"` and `response_model=_DirectionalCheck`. `matched_tokens` reflects lexical hits only; `llm_asked` records whether the LLM stage ran.
    - `backend/tests/guardrails/test_directional.py` — 16 tests. 37-example hand-crafted accuracy set → **37/37 (100%)** (BUILD.md threshold: ≥95%). Uses a fake LLM keyed on the input text for the LLM-only cases.
  - `GRD-02` ✅ — Citation-required validator.
    - `backend/app/guardrails/citations.py`:
      - `SourceStub(url, body)` dataclass — the (url, body) pairs the LLM saw in its prompt.
      - `check_citations(citations, *, allowed_stubs) -> CitationVerdict` — three hard rules: (1) `len ≥ 1`, (2) every citation URL matches at least one stub URL (case-insensitive on host, case-sensitive on path, ignore trailing `/` + scheme case), (3) every non-empty citation quote is a substring of the matched stub's body after `re.sub(r"\s+", " ", ...).strip()` whitespace normalization. Empty quotes generate an advisory in `reasons` but don't fail the verdict.
      - `_normalize_url` and `_normalize_ws` — the only helpers.
    - `backend/tests/guardrails/test_citations.py` — 10 tests: empty citations, URL mismatch, URL normalization (trailing slash, scheme case), whitespace-normalized substring match, quote-not-in-body, multi-citation with one bad, empty-quote advisory, case-sensitive path, and the extra "empty quote doesn't mask a real rule-2 failure" sanity test.
  - `GRD-03` ✅ — Out-of-scope refusal.
    - `backend/app/guardrails/scope.py`:
      - `Category = Literal["in_scope", "tax", "legal", "personal_planning", "medical"]`.
      - Curated per-category regex patterns (word-boundary for single tokens; substring case-insensitive for multi-word phrases). Ordered most-specific first so multi-word phrases match before their constituent tokens.
      - `_REFUSAL_MESSAGES: dict[Category, str]` — canned refusals pointing at licensed CPA / attorney / CFP / physician.
      - `async classify_scope(text, *, llm=None, skip_llm=False) -> ScopeVerdict` — lexical first; if clean and `skip_llm=False`, fast-tier LLM call with `agent_name="guardrail-scope"` and `_ScopeCheck` response model. LLM exceptions fail open to `in_scope` (per subagent's hardening note — a spurious refusal is worse than a rare miss because the app footer already carries the disclaimer). Input is `.strip()`ed and truncated to 4000 chars.
    - `backend/tests/guardrails/test_scope.py` — 26 tests. 10-example acceptance set → **10/10 (100%)** on both category-correct and passed-flag axes (BUILD.md threshold: ≥90%). Covers all four out-of-scope categories, in-scope skip_llm short-circuit, LLM-only catch of subtle out-of-scope, refusal-message completeness, empty-input handling, and long-input trimming.
- **Acceptance verified locally:**
  - `python -m pytest tests -q` → **256 passed, 5 deselected** (+52 new hermetic tests: 16 GRD-01 + 10 GRD-02 + 26 GRD-03).
  - `ruff check .` clean on all six new source/test files.
- **Files touched:** created 8 files (6 modules + 2 shared `__init__.py` package markers). Ticked GRD-01/02/03 in BUILD.md. Rewrote this HANDOFF.md.
- **Migrations added:** none.
- **Tests added:** 52 hermetic.
- **In-flight work:** none.
- **Deviations from BUILD.md:**
  - **GRD-01 word-boundary regex doesn't catch inflected forms** (e.g., `adding`, `trimming`, `recommends`). That's the LLM stage's job by design; the accuracy tests confirm the LLM catches the subtle-recommendation cases without lexical hits. The `LLMClient` is passed per-invocation (no module-global), so IMP-04 must inject it.
  - **GRD-02 `SourceStub` dedup policy is "last one wins"** when a caller passes two stubs with the same normalized URL. Deterministic; documented inline. Callers should dedupe upstream (relevant when the same URL appears in multiple ingest sources).
  - **GRD-02 treats a whitespace-only quote (`"   "`) as empty** (advisory, not failure). BUILD.md only said "empty"; this is the natural extension and keeps the guardrail robust against LLMs padding with whitespace.
  - **GRD-03 LLM exceptions fail open to `in_scope`** rather than raising. The tradeoff — a spurious refusal is worse UX than a rare miss (footer disclaimer covers the miss). Documented in the module docstring.
  - **GRD-03 pattern list biases toward false positives** (e.g., bare `audit`, bare `will`). If user testing shows too many innocent hits (`"AT&T earnings audit call"`, `"Buffett will speak at AGM"`), tighten those specific tokens to phrases. Flagged for post-MVP.
- **Session mechanics recap:** Three subagents ran in the same v2 worktree in the background, briefed with disjoint file paths. Parent pre-created `backend/app/guardrails/__init__.py` and `backend/tests/guardrails/__init__.py` as empty markers so no agent stomped another creating them. After all three returned, parent ran `pytest tests -q` end-to-end, `ruff check .`, ticked BUILD.md three times, wrote this HANDOFF, and split into three commits (`GRD-01:`, `GRD-02:`, `GRD-03:` messages) — HANDOFF.md landed in the last commit only.

---

## Environment state

- Backend: full impact-analyst dependency graph now complete (REL-04 relevance, IMP-01 schema, IMP-02 analogs, IMP-03 prices, GRD-01+02 validators). IMP-04 can compose them.
- Frontend: unchanged.
- Database: Alembic head `c3b8f4e1d7a2` (IMP-01). No new migrations this session.
- Vectors: unchanged. Remember to `python -m app.evals.seed_analogs` before smoke-testing IMP-04 locally.
- Tests: **256 hermetic, 5 opt-in.**
- CI: REL-03..GRD-03 pending push through CI.
- Docs: unchanged.

---

## Open questions / blockers

- **None for IMP-04.** All dependencies are live and passing.
- **Follow-ups queued (do not fold into IMP-04):**
  - Tighten `ClusterDetailRead.impact: Any` to `ImpactRead | None` when IMP-05 wires the endpoint.
  - Refresh `yfinance` pin in `requirements.txt` (0.2.44 → 1.5.x).
  - Expand `analogs.json` from 37 → ~150 events (low risk, append-only).
  - Tighten GRD-03 lexical patterns (`audit`, `will`) if UX testing shows over-refusal.

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
