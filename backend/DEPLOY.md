# Deploy runbook — Fly.io backend (DEPLOY-02)

This is the one-time setup + day-2 ops guide for the Lumen backend on Fly.io.
Every subsequent deploy is a git push once the pieces below are in place.

## Prerequisites

1. **`flyctl` installed** and authenticated:
   ```bash
   # Windows (PowerShell): iwr https://fly.io/install.ps1 -useb | iex
   # macOS/Linux:           curl -L https://fly.io/install.sh | sh
   flyctl auth login
   ```
2. **Supabase project provisioned** with:
   - Auth on (email/password + Google OAuth per PRD).
   - Postgres URL — grab the connection string from the Supabase dashboard →
     Project Settings → Database → Connection string → **URI** tab. Prepend
     `postgresql+asyncpg://` (or replace `postgres://` with it) so SQLAlchemy
     uses the async driver.
3. **OpenRouter API key** at [openrouter.ai](https://openrouter.ai).
4. **NewsAPI + Marketaux keys** (optional — the pipeline runs on GDELT + EDGAR + RSS if these are missing).

## First-time setup

From the repo root:

```bash
cd backend
flyctl launch --no-deploy --copy-config --name lumen-backend --region ord
```

- `--no-deploy` skips the first deploy (we need secrets + volume first).
- `--copy-config` uses the committed `fly.toml`; pass `--now` after the volume + secrets are in.
- Swap `--name` for whatever name Fly's uniqueness check accepts.
- Swap `--region` for the one closest to your Supabase Postgres (see `flyctl platform regions`).

### 1. Create the persisted volume

Chroma + the yfinance price cache both live under `/app/data`, mounted from a Fly volume named `lumen_data` (matches the `[[mounts]] source` in `fly.toml`).

```bash
flyctl volumes create lumen_data --size 1 --region ord --yes
```

`1` GB is plenty for the MVP (news embeddings + ~200 historical analogs + price cache). Bump later with `flyctl volumes extend` if needed.

### 2. Set application secrets

Everything on this list is required. Copy the block, replace the placeholders, and paste it in one shot — `flyctl secrets set` triggers a machine restart per invocation, so batching keeps downtime to a single restart.

```bash
flyctl secrets set \
  SECRET_KEY="$(openssl rand -base64 48)" \
  OPENROUTER_API_KEY="<your openrouter key>" \
  SUPABASE_URL="https://<project-ref>.supabase.co" \
  DATABASE_URL="postgresql+asyncpg://postgres:<PASSWORD>@db.<project-ref>.supabase.co:5432/postgres" \
  ALLOWED_ORIGINS="https://<your-vercel-domain>.vercel.app,https://lumen.app"
```

Optional integrations (add each one only if you'll actually use it):

```bash
flyctl secrets set \
  NEWSAPI_KEY="<newsapi key>" \
  MARKETAUX_KEY="<marketaux key>" \
  LANGSMITH_API_KEY="<langsmith key>" \
  LANGSMITH_TRACING=true \
  LANGSMITH_PROJECT=lumen-prod
```

Verify:

```bash
flyctl secrets list
```

### 3. First deploy

```bash
flyctl deploy --remote-only
```

- `--remote-only` builds on Fly's builder (fine on a slow local network; skips a multi-hundred-MB context upload of a locally-built image).
- The `ENTRYPOINT` runs `alembic upgrade head` before uvicorn boots — the first deploy provisions the full schema.
- Sentence-transformers is baked into the image (`RUN python -c "SentenceTransformer(...)"` in the Dockerfile) so the first request doesn't cold-start on the model download.

Watch it:

```bash
flyctl logs
flyctl status
curl https://<app-name>.fly.dev/health
```

`{"status":"ok"}` means uvicorn + the migrations both succeeded.

### 4. Wire up CI-driven deploys

The GitHub Actions workflow at `.github/workflows/deploy-backend.yml` runs `flyctl deploy` on every push to `v2/intelligence-agent` that touches `backend/**`. To enable it, add a repo secret:

```bash
# Locally
flyctl auth token
```

Copy the token, then GitHub → Repository → Settings → Secrets and variables → Actions → **New repository secret**:

- Name: `FLY_API_TOKEN`
- Value: `<the token>`

## Day-2 ops

### Manual deploy from your machine

```bash
cd backend
flyctl deploy --remote-only
```

### Watch live logs

```bash
flyctl logs
```

### Roll back

```bash
flyctl releases           # list release ids
flyctl releases rollback <release-id>
```

### Update a single secret without restart

```bash
flyctl secrets set --stage KEY=value    # stage without restart
flyctl deploy                            # roll into the next release
```

### Scale memory (if OOM)

`sentence-transformers` + Chroma + FastAPI + LangGraph can push past the default 512MB on the free tier. Bump to 1GB:

```bash
flyctl scale memory 1024
```

If OOM continues under load, split the ingest scheduler into its own machine (see DEPLOY-03).

### Reset the persisted volume

```bash
flyctl ssh console
# inside the VM
rm -rf /app/data/chroma /app/data/price_cache
exit
flyctl apps restart lumen-backend
```

The `historical_analogs` collection re-seeds on next boot if `app.evals.seed_analogs` is invoked; `news_items` re-populates as ingest runs.

## Frontend CORS

Once the frontend is deployed to Vercel, add its origin to `ALLOWED_ORIGINS`:

```bash
flyctl secrets set ALLOWED_ORIGINS="https://<vercel-domain>.vercel.app,https://lumen.app"
```

Local development still works because `Config._allowed_origins()` falls back to `http://localhost:3000` if the env var is empty — but production always needs the explicit list.

## Known caveats

- **Fly free tier** hibernates machines when idle. First request after ~10 min of quiet takes 2–5s to wake. `min_machines_running = 0` in `fly.toml` accepts this trade-off; flip to `1` if the demo needs a warm process.
- **APScheduler runs in-process**, so if the machine is hibernated, no ingest / briefing jobs fire during the sleep window. The `/health/ingest` endpoint reports the freshness of the last run — the UI surfaces a banner if stale >90 minutes (per PRD risk 11.5).
- **Alembic in ENTRYPOINT** runs on every boot. This is idempotent (Alembic is a no-op when the DB is at `head`) but does add ~200-500ms to cold-start. Cheap; worth it for the "schema always fresh on deploy" property.
- **Chroma persists to the Fly volume**, but if you resize / migrate the app to a new region the volume must be forked (see `flyctl volumes fork`).
- **Sentence-transformers is CPU-only**. Fly machines have no GPU on the free tier and none of the free-tier machine types benefit from CUDA anyway — CPU inference on `all-MiniLM-L6-v2` handles the batch sizes this app produces.
