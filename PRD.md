# Lumen — Personal Financial Intelligence Agent

**PRD v1.0 — Trajectory: Portfolio Piece (Recruiter-Facing, Deployed, Demo-Ready)**

---

## 1. One-liner

Lumen is a personal financial intelligence agent. You give it your portfolio and the macro themes you care about. It watches the world's financial news continuously, reasons about which of it materially affects *your* holdings, and produces a personalized daily briefing plus an ask-anything chat interface — all with citations, no buy/sell recommendations, and a track record of its own past predictions.

Positioned for: an individual portfolio-holder who wants to know what today's news means for their money, without becoming a full-time market watcher and without being sold "advice."

---

## 2. Problem

An individual with a portfolio (equities, index funds, crypto) faces two failure modes every day:

1. **The signal-to-noise problem.** ~10,000 finance-tagged news items are published globally per day. Perhaps 3 of them materially affect any given portfolio. Bloomberg terminals cost $30k/year, and generic apps (Yahoo, Google Finance) surface headlines but never reason about *your* holdings.
2. **The mechanism problem.** Even when a user finds relevant news, they don't know the transmission mechanism. "The Fed hiked 25bps" — does that hurt or help *my specific portfolio*? Why? By how much? Under what assumptions? A human research analyst answers these questions; the average retail investor gets a Reddit thread.

Existing tools fail this individual because they are either (a) advisor-shaped (buy/sell recommendations, regulatory hair, subscription cost) or (b) headline-shaped (generic feeds, no personalization, no reasoning). Nothing sits in the useful middle: *personalized analysis with citations and no recommendations*.

---

## 3. Who it's for

**Primary user:** A financially literate individual who holds a self-directed portfolio and wants situational awareness without becoming a full-time analyst. Comfortable with markets, uncomfortable with the daily firehose. Wants to make informed decisions themselves — does not want to be told what to buy.

**Secondary user (portfolio-piece context):** A recruiter or engineering leader evaluating this project as a demonstration of applied AI systems engineering. Must be able to click a deployed link, understand the product in 30 seconds, and grasp the technical depth within 2 minutes.

**Explicit non-user:** Institutional investors, financial advisors acting on behalf of clients, or anyone regulated as a fiduciary. Lumen deliberately stays out of that lane.

---

## 4. What it does — concretely

A user's session with Lumen looks like this:

**Onboarding (once):** User creates an account, adds their portfolio (a list of tickers with optional quantities), and adds any macro themes they care about (e.g., "US recession risk", "AI capex cycle", "India rate cuts", "oil above $100").

**Continuously (background, every ~15 minutes):** Lumen ingests financial news from five sources (NewsAPI, Marketaux, GDELT, SEC EDGAR filings, curated RSS feeds), semantically deduplicates it into event clusters, and stores it with embeddings.

**For every user, every hour:** A relevance engine scores each new event cluster for materiality to *that* user's portfolio and themes. Below-threshold items are dropped. Above-threshold items are queued for analysis.

**For each relevant event:** An impact-analyst agent (LangGraph-orchestrated, tool-using) produces a structured impact assessment: what the event is, which of the user's positions or themes it touches, the transmission mechanism, an honest magnitude range with confidence, and citations back to the source news plus any historical analogs it found. **No directional recommendation language.**

**Once daily (user-configurable time):** A briefing synthesizer aggregates the day's analyses into a personal briefing with three sections: *Top movers for you* (the 3–5 most material items), *Watchlist for tomorrow* (developing situations to monitor), and *What would change my thinking* (falsifiability — the specific new information that would flip Lumen's current read).

**On demand — chat:** User asks anything ("what's the biggest concentration risk in my portfolio right now?", "why is NVDA down today?", "explain what a hawkish Fed means for my bond ETFs"). The chat agent retrieves relevant recent news + portfolio context and answers with citations.

**Over time — calibration:** Every impact assessment includes a predicted mechanism and magnitude. Lumen tracks whether its predictions played out (using follow-up news and price data). A visible track-record page shows what Lumen got right and wrong, and its predictions carry a self-calibrated confidence based on prior accuracy in similar setups.

---

## 5. What it doesn't do — non-goals

Being explicit about non-goals is what makes this scope shippable in weeks instead of years.

- **No buy/sell/hold recommendations.** Ever. Not even implicitly. Language guardrails enforce this at the output layer.
- **No portfolio management or execution.** Lumen does not connect to brokerages, does not place trades, does not custody assets.
- **No bank transaction ingest.** No Plaid, no card-linking, no expense categorization. That was the previous trajectory and is deliberately discarded.
- **No OCR / receipts / invoice ingestion.** All prior codebase capabilities in this space are removed in Phase 0.
- **No tax advice or tax-loss harvesting.** Regulated territory.
- **No social/community features.** No sharing, no comments, no leaderboards.
- **No mobile app.** Web only. Responsive layout, but no native mobile shell.
- **No multi-currency portfolio valuation as a first-class feature.** Positions are stored with a native currency; the UI displays that currency. No FX conversion in briefings.
- **No real-time price streaming.** Prices are pulled on demand or on a 15-minute cadence. Sub-minute latency is not a design goal.
- **No investment style specialization.** Lumen doesn't have a "value" or "growth" or "momentum" opinion. It reports; it doesn't strategize.

---

## 6. User journeys

Three concrete journeys drive the design.

### 6.1 First-time user (onboarding, ~4 minutes)

A recruiter or curious visitor lands on the deployed site.

1. Hits `/`. Sees a hero explaining what Lumen does with a 20-second demo GIF of the briefing view.
2. Clicks "Try it" → Supabase-backed signup (email/password or Google OAuth).
3. Redirected to `/onboarding/portfolio`. Enters 3–8 tickers. Optional: quantity and cost basis. A "load sample portfolio" button seeds a plausible portfolio (AAPL, NVDA, VOO, BND, some crypto) so a recruiter can skip data entry.
4. Redirected to `/onboarding/themes`. Enters 0–5 macro themes (freeform text; e.g., "recession risk", "AI capex", "India rate cuts"). Also skippable.
5. Redirected to `/briefing`. A briefing is generated **live** (streamed via SSE) using the last 24h of relevant news for the entered portfolio. This is the "wow" moment — first briefing appears in ~30–60 seconds with citations building up in real time.

Success criterion for onboarding: a recruiter who has never seen the product goes from landing page to first briefing in under 5 minutes, without reading any documentation.

### 6.2 Returning daily user (morning ritual, ~3 minutes)

A user opens Lumen with coffee.

1. Hits `/briefing`. Yesterday's briefing has been superseded by this morning's, generated at their preferred hour.
2. Reads the top 3 items. Each has a one-line summary, a mechanism paragraph, 2–3 citation chips linking to source news, and an "impact on your holdings" line naming specific positions.
3. Clicks a citation. A side-panel opens with the original news item, Lumen's assessment, and a "what would change my thinking" line.
4. Clicks "Chat about this". A new chat session opens with the news item preloaded as context. User asks "how much of NVDA's move is priced in?" and gets a cited response.

Success criterion for daily use: the user can consume the briefing in under 3 minutes and knows what they don't need to worry about (as much as what they do).

### 6.3 Reactive user (event-driven, on-demand)

Something big happens mid-day (Fed presser, geopolitical event, earnings surprise).

1. User opens `/news/relevant`. The feed has already reordered to surface the event. It appears at the top with an "assessment in progress" badge; within 30–60 seconds a full impact assessment appears.
2. User expands the assessment. Sees mechanism, affected positions, magnitude range, cited historical analogs (e.g., "similar to March 2020 rate response").
3. User opens chat: "What would need to happen next week for this to flip from bullish to bearish for my portfolio?" Chat returns a cited response drawing on the just-created assessment plus historical context.

Success criterion for reactive use: from event → user seeing a fully-cited personalized assessment in under 2 minutes.

---

## 7. Feature set

Grouped by shipping phase. Every feature has a demo purpose or an engineering-showcase purpose (usually both).

### 7.1 MVP — v0.1 (weeks 1–5)

Everything needed for the three user journeys above to work end-to-end for a single user with a single portfolio.

- **Portfolio management** — CRUD for portfolios, positions (ticker, quantity, cost basis, currency), themes.
- **News ingestion pipeline** — Five sources (NewsAPI, Marketaux, GDELT, EDGAR, RSS), running on a 15-minute schedule, normalized into a single `NewsItem` schema, embedded, and semantically deduplicated into event clusters.
- **Source authority scoring** — A static per-source authority weight (Reuters > blog aggregator) plus a per-item novelty score.
- **Relevance engine** — A two-stage LangGraph node: (1) embedding-based prefilter (fast, catches ~80% of irrelevance), (2) LLM classification with structured output (final judgment on borderline items). Outputs relevance score + touched positions + touched themes.
- **Impact analyst agent** — Per relevant event: a LangGraph subgraph that composes retrieval (historical analogs), reasoning (mechanism), and structured output (Pydantic-validated). Refuses to produce output without at least one cited source. Enforces "no directional language" guardrail via a post-generation validator.
- **Briefing synthesizer** — Daily briefing rendered at a user-configured hour. Streamed to the frontend via SSE. Three fixed sections. All items link back to their source news and analyses.
- **Chat interface** — RAG over the user's personal news + assessment corpus, with portfolio context injected into every prompt. Streaming responses, session history, citation chips.
- **Guardrail suite** — (a) Output-language classifier that refuses drafts containing recommendation phrases, (b) citation-required validator, (c) refusal-when-out-of-scope pattern (tax, legal, medical, personal advice → polite refusal).
- **Auth & account** — Supabase, kept from current architecture. Email/password + one OAuth provider (Google).
- **Deployed** — Vercel (frontend) + Fly.io or Railway (FastAPI backend) + Supabase (auth + Postgres) + Chroma (vectors, either self-hosted on Fly or Chroma Cloud free tier) + LangSmith (traces).

### 7.2 v0.2 (weeks 6–7)

Adds the differentiating polish that separates this from a competent RAG demo.

- **Long-term agent memory + calibration** — Every impact assessment stamps a prediction record: predicted mechanism, predicted direction (advisory only, not user-facing), timeframe, and falsifiability criterion. A reflection loop runs periodically to check whether events resolved as predicted using follow-up news and (optionally) price data. A public track-record page shows Lumen's calibration.
- **Scenario simulator** — User picks or defines a scenario ("Fed cuts 50bps next FOMC", "oil to $120", "US recession Q3"). Agent walks through the specific impact on each of the user's positions with citations to historical analogs from the news corpus.
- **Eval harness with published results** — A labeled dataset of 200 (news, portfolio, expected relevance/impact) tuples. LangSmith regression runs on every commit. A visible "model quality" page in the app shows current metrics: relevance precision/recall, RAG faithfulness (RAGAS), guardrail-violation rate, calibration score.

### 7.3 v1.0 completeness (week 8+)

The version worth putting on the resume.

- **Multi-portfolio support** — A user can maintain separate portfolios (personal, retirement, experimental). Briefings and chat are scoped by active portfolio.
- **Export & share** — Briefings can be exported as PDF. A public shareable snapshot link (with anonymized portfolio) for sharing a specific analysis. **Not** a social feed — one-off link only.
- **Notifications** — Email or Slack digest at the configured briefing hour. Optional real-time alerts for high-severity events (user-configurable threshold).
- **Portfolio ingest via CSV** — Import positions from a broker CSV (Fidelity, Schwab, Zerodha, ICICI Direct format detection).
- **Demo mode** — A public demo user (`demo@lumen.app`) with a fixed sample portfolio, browsable without signup. Powers the recruiter journey.

Post-v1.0 items intentionally not planned yet: bank feeds, mobile app, brokerage integrations, tax modules, community features.

---

## 8. Product principles — the how

Six principles that constrain every design decision. When in doubt during implementation, resolve in favor of the principle.

1. **Every claim cites a source.** No unsupported statement, no matter how obvious it seems. This is enforced by a validator at the LLM-output boundary, not a suggestion in a system prompt.
2. **No directional language.** Never "buy," "sell," "add," "trim," "overweight," "underweight." Instead: mechanism ("higher rates compress duration-sensitive valuations"), magnitude ("historically 3–7% over 30 days in similar setups"), and falsifiability ("this thesis breaks if the yield curve re-inverts"). Enforced by a post-generation lexical + semantic guardrail.
3. **Personalization or nothing.** Every artifact — briefing, impact assessment, chat response — must reference the specific user's portfolio or themes. Generic content is a design failure and is treated as a bug.
4. **Falsifiability over confidence.** Every non-trivial claim comes with "what would change my thinking." A user should learn how to falsify Lumen, not to trust it.
5. **Calibration honesty.** Lumen shows its track record openly, including misses. A system that hides its mistakes cannot be trusted with financial signal.
6. **Zero external UI dependencies.** No embedded terminal widgets, no third-party JS pulls. Everything renders from our own data, our own components. Reason: the deployed artifact must load fast, work offline of third parties, and be reproducible on any infrastructure.
7. **Modern, serious, dense.** The UI aesthetic is dark-first, high-contrast, Linear/Vercel-adjacent — sophisticated financial-tool feel, not playful dashboard. Numbers render in a mono font with tabular figures; colors semantic (confirmed / refuted / partial), never decorative; motion is subtle and functional. Full design token system in `BUILD.md` → Design system section is authoritative; no component ships with hardcoded colors or ad-hoc spacing.
8. **Free-tier everything.** The entire stack — models, embeddings, hosting, vectors, tracing, database — runs on free tiers or self-hosted open source. This is a hard constraint, not a preference. It shapes every technology decision and produces a real resume story (*"deployed a multi-agent AI system on $0/month infrastructure"*). See `BUILD.md` → LLM invocation + Environment variables for the authoritative stack.

---

## 9. Success criteria

Success is measured on two independent axes because this is a portfolio project with dual audiences.

### 9.1 Product success (usability)

- A brand-new user completes onboarding and sees their first briefing in under 5 minutes.
- The daily briefing is consumable in under 3 minutes and every claim links to a source.
- The chat produces a cited answer to the top 10 canonical questions ("what's my biggest risk?", "why is X down?", "what if the Fed does Y?") in under 15 seconds each.
- A user can find a specific past event and Lumen's assessment of it in under 30 seconds.
- Zero directional-language leakage in a manual audit of 100 randomly sampled outputs.

### 9.2 Portfolio-piece success (the resume story)

- Deployed at a stable URL, working from a fresh browser session, no local setup required.
- README + PRD readable in 15 minutes by a technical hiring manager. Architecture diagram + eval results visible.
- Eval harness runs on every commit (visible in CI status badge). Published metrics: relevance precision ≥ 0.75, relevance recall ≥ 0.70, RAG faithfulness (RAGAS) ≥ 0.80, guardrail violation rate ≤ 1%, calibration Brier score ≤ 0.20 (once enough resolved predictions exist).
- LangSmith public trace shareable from any briefing. Recruiter can click "view trace" on any briefing and see the full LangGraph execution.
- Codebase has real tests, real CI, and a documented eval methodology. Not a Streamlit toy.

---

## 10. Technical stack — high-level

Details in `BUILD.md`. This is the overview.

**Frontend:** Next.js 15 (App Router), React 19, TypeScript, Tailwind CSS, shadcn/ui, TanStack Query, Supabase JS client. Server-side rendering for SEO on marketing pages; client-side for the app. SSE for streaming briefings and chat.

**Backend:** Python 3.11+, FastAPI, uvicorn, Pydantic v2, SQLAlchemy 2.x (async), Alembic for migrations. Migrated from the current Flask stack in Phase 0.

**AI orchestration:** LangGraph as the primary orchestration layer for agents (relevance, impact analyst, briefing synthesizer, chat). LangChain used sparingly for its retriever and loader utilities. Both pinned. No CrewAI (opinionated in ways that fight LangGraph for this shape of work).

**LLMs (free tier):** OpenRouter as the gateway. Primary text model (`thorough` tier): `deepseek/deepseek-chat-v3.1:free` (or best-available free reasoner at build time). Fast tier: `meta-llama/llama-3.3-70b-instruct:free`. Verified live at BOOT-06 with fallback documented. Rate-limited at 20 RPM per model (free-tier norm); wrapper handles queueing.

**Embeddings (local):** `sentence-transformers/all-MiniLM-L6-v2` — 384 dims, ~90MB, CPU-viable. No API cost, no rate limits. Single largest cost-cut in the stack vs. paid OpenAI embeddings.

**Reranker (local):** `BAAI/bge-reranker-base` for chat retrieval, added in OPT-04.

**Vector store:** Chroma. Two collections — `news_items` (all ingested articles) and `historical_analogs` (curated set of past events for retrieval). Self-hosted for MVP; Chroma Cloud upgrade path is trivial.

**Storage:** Postgres via Supabase for relational data (users, portfolios, positions, themes, briefings, impact assessments, predictions, chat sessions/messages, eval results).

**Auth:** Supabase Auth, JWT-verified server-side via JWKS. This is already in place; kept as-is.

**Scheduling:** APScheduler for the MVP (in-process, simple). Upgrade to Arq or Celery + Redis in v1.0 if ingest volume needs distributing.

**Observability:** LangSmith for LLM traces (free tier ample for portfolio scale). structlog for backend logs. Sentry optional.

**External data:**
- News: NewsAPI (free 100/day), Marketaux (free tier), GDELT (free), SEC EDGAR (free with User-Agent), curated RSS.
- Prices / fundamentals: Yahoo Finance via `yfinance` (free), Alpaca free tier as backup.

**Observability:** LangSmith (free 5k traces/mo) or Langfuse (free cloud tier / self-host free). Whichever is configured wins.

**Deployment (all free-tier):**
- Frontend: Vercel free hobby tier.
- Backend: Fly.io free allowance (3× shared-cpu-1x machines, 256MB each) — one for HTTP, one for scheduler.
- Database + Auth: Supabase free tier (500MB Postgres, unlimited auth).
- Vectors: Chroma persisted to a Fly volume (free-tier volume allowance).
- News APIs: NewsAPI (100/day free), Marketaux (~100/day free), GDELT + EDGAR + RSS (all unlimited free). GDELT + EDGAR + RSS form the reliable backbone; the two rate-limited APIs are best-effort.
- Prices: `yfinance` (free, no key).

---

## 11. Risks & mitigations

The risks that could actually kill this project, not the ones that make good listicles.

### 11.1 Regulatory framing drift

**Risk:** Someone reading the app perceives it as investment advice, either because the guardrails leak once and it says "buy," or because the framing on the marketing site is careless.

**Mitigation:** Guardrail suite is a *pre-shipping* gate — no LLM output can leave the backend without passing the language + citation validators. Marketing copy is audited for advisory tone. Every page has a persistent footer disclaimer. Legal-risk framing is baked into the PRD (this section) so any future contributor sees it.

### 11.2 Eval-set fabrication risk

**Risk:** The eval harness is the resume-worthy differentiator, but building a labeled dataset of 200 tuples is boring work and easy to skip or fake.

**Mitigation:** Eval-set construction is a first-class module in `BUILD.md` (Phase 8), with a specific data-collection protocol, an inter-labeler check, and a "no-fake-scores" rule (metrics only computed on the held-out labeled set). The eval page in the app is honest — if 30% of the eval set is unlabeled, it says so.

### 11.3 News API rate-limit death

**Risk:** Free-tier NewsAPI is 100 requests/day. For a 15-minute polling cadence that's 96 requests just for ingest. Any user demo consumes the budget instantly.

**Mitigation:** Multi-source design (NewsAPI, Marketaux, GDELT, EDGAR, RSS) means no single API is critical. GDELT and EDGAR are unlimited-free. RSS is unlimited. NewsAPI is treated as best-effort. A "demo mode" seeds a fixed news corpus so recruiters can browse without hitting live APIs.

### 11.4 LLM cost creep

**Risk:** Relevance scoring + impact analysis + briefing + chat could hit hundreds of LLM calls per user per day. At $0.003/1k tokens for Claude Haiku that's fine; at $0.015/1k for Sonnet it adds up.

**Mitigation:** Two-tier model routing — Haiku for relevance prefilter and classification, Sonnet only for impact analysis and briefing synthesis. Aggressive caching of assessments (an event cluster is analyzed once, not per user per session). Hard daily $ ceiling per user with a soft-fail behavior.

### 11.5 Ingestion pipeline fragility

**Risk:** A 15-minute cron running for weeks unattended is one bug from either duplicating everything or missing everything for days.

**Mitigation:** Idempotent inserts keyed by source-provided IDs (or URL hash if none). Ingestion writes a heartbeat row every run. `/health/ingest` endpoint surfaces last-run status. If the last successful ingest is more than 90 minutes stale, the app UI shows a banner.

### 11.6 Scope creep from "one stop"

**Risk:** Every conversation about the product will surface an obvious-seeming feature ("add budgets", "add tax", "add bank feeds"). The MVP dies in feature negotiation.

**Mitigation:** The non-goals list (§5) is the veto document. New features get added to a "post-v1.0 backlog" section in `BUILD.md`; nothing in that list can move into a phase without an explicit PRD amendment.

### 11.7 Calibration is meaningless with too few resolved predictions

**Risk:** The track-record feature (§7.2) is impressive only if there are, say, 50+ resolved predictions to score. In the first 4 weeks of live use there will be maybe 5.

**Mitigation:** Backfill. Phase 7 seeds the calibration dataset by running the impact analyst on 30 historical events (Fed decisions, earnings surprises, geopolitical shocks over the past 12 months) and resolving them against known price outcomes. This bootstraps the track record to something meaningful on day one of v0.2.

---

## 12. What we're deliberately keeping simple

Complexity we're refusing:

- **No multi-tenancy in the org sense.** Users own their portfolios; portfolios do not belong to workspaces. Multi-user teams are a v2 problem.
- **No role-based access control.** A user has full access to their data; no viewer/editor split.
- **No feature flags.** Ship-or-don't. Feature flags are a scaling tool and this is single-scale.
- **No microservices.** One FastAPI process, one scheduled worker (same process), one Postgres, one vector store. Split only if it stops fitting.
- **No streaming ingest.** 15-minute batch. Real-time can wait.
- **No user preferences beyond the basics** — briefing hour, model tier (fast vs. thorough), currency for display. That's it.

---

## 13. Open questions

Explicitly unresolved. Each will be answered before its dependent module is built.

- **Q1: Portfolio pricing frequency.** Do we compute a live portfolio value in the UI? MVP proposal: no; positions are stored with cost basis and the UI shows raw positions only. Live valuation is a v0.2 additive.
- **Q2: Chat memory across sessions.** Does the chat remember the last session's context when a new session starts? MVP proposal: no; each chat session is independent. Long-term agent memory (Phase 7) is a separate system focused on predictions, not chat.
- **Q3: How much of past news to keep.** All-time, or rolling 90 days? Storage cost of embeddings for all-time news at ~500 items/day = 45k/quarter = manageable. Proposal: keep 12 months of raw news, all-time for impact assessments (which are much smaller).
- **Q4: Do we support fractional positions and options?** MVP: no options. Fractional shares yes (quantity is a decimal). Options are a v1.0 consideration.
- **Q5: Localization / currency.** MVP: single display currency per portfolio, no FX conversion. If the user's portfolio has mixed currencies, positions are stored raw and displayed raw. Aggregate portfolio values are not shown.
- **Q6: What's the recruiter demo-mode experience?** Proposal: a public `demo@lumen.app` login with a pre-seeded portfolio and pre-generated briefings from real news events over the last 30 days. Skip signup entirely on a "try demo" click.

---

## 14. Success looks like this

Six months after v1.0 ships, we can point at:

- A live, working, deployed product at `lumen.app` (or similar). A recruiter clicks the demo button, sees a fully populated briefing, opens a chat, and asks "what's my portfolio's biggest risk?" — gets a cited, personalized answer in under 20 seconds.
- A public GitHub repo with a clean architecture, real tests, a documented eval harness, and CI status badges.
- A published eval report showing precision/recall/faithfulness on a real held-out dataset, with visible iteration history.
- A LangSmith public trace shareable from any briefing card in the app.
- Zero regulatory issues, zero directional-language leakage in production.

That's the artifact that gets someone hired.

---

*Next: see `BUILD.md` for the phase-by-phase execution plan.*
