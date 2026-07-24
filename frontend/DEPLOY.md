# Deploy runbook — Vercel frontend (DEPLOY-01)

The Next.js 15 frontend deploys to Vercel. **The recommended flow is Vercel's
native git integration** (webhook-driven, PR previews for free). The
`.github/workflows/deploy-frontend.yml` file exists as an *opt-in* CI-driven
alternative if you want to gate deploys on some other check — never enable
both at once or every push double-deploys.

## Prerequisites

1. **Backend live at a stable URL.** DEPLOY-02 must be complete first — the
   frontend build fails without `NEXT_PUBLIC_BACKEND_URL` (see
   `frontend/next.config.ts`, which throws on any missing `NEXT_PUBLIC_*` var).
2. **Supabase project provisioned** (same one DEPLOY-02 uses). You'll need:
   - The project URL: `https://<project-ref>.supabase.co`.
   - The anon (publishable) key: Supabase dashboard → Project Settings →
     API → `anon` `public` key.
3. **A Vercel account** at [vercel.com](https://vercel.com). GitHub OAuth is
   fine; you don't need Pro for hobby-tier deploys.

## First-time setup (Vercel's git integration — recommended)

1. In the Vercel dashboard, **Add New… → Project → Import Git Repository**.
   Pick this repo.
2. **Root Directory:** `frontend`. Vercel auto-detects Next.js 15.
3. **Build & Development Settings:** leave the defaults — `vercel.json` at
   `frontend/vercel.json` already sets `framework`, `installCommand`,
   `buildCommand`, and `outputDirectory` explicitly.
4. **Environment Variables:** add these three (all three tiers — Production,
   Preview, Development):
   - `NEXT_PUBLIC_BACKEND_URL` — the Fly.io backend URL from DEPLOY-02
     (e.g. `https://lumen-backend.fly.dev`).
   - `NEXT_PUBLIC_SUPABASE_URL` — `https://<project-ref>.supabase.co`.
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY` — the anon key from Supabase.
5. **Production branch:** set to `v2/intelligence-agent` in
   Project Settings → Git. Preview deploys fire on every non-production
   branch and PR.
6. Click **Deploy**. First deploy takes ~2 minutes.
7. Once live, note the production URL — you need it for the backend's
   `ALLOWED_ORIGINS`:
   ```bash
   cd backend
   flyctl secrets set ALLOWED_ORIGINS="https://<vercel-domain>.vercel.app"
   flyctl deploy
   ```
   (Or add multiple origins comma-separated if you have a custom domain.)

## Verify

- Visit `https://<vercel-domain>.vercel.app`.
- Sign in with an existing Supabase user (or sign up).
- After sign-in you should land on `/portfolios` (or the onboarding flow
  if no portfolio exists). Every API call goes to
  `NEXT_PUBLIC_BACKEND_URL/api/…` — open the browser dev tools and watch
  Network to confirm requests hit your Fly backend, not localhost.

## Day-2 ops

### Redeploy from your machine

If Vercel's git integration is enabled, just push to `v2/intelligence-agent`.
The webhook picks it up and deploys.

For a manual deploy without pushing:

```bash
cd frontend
npm i -g vercel
vercel login
vercel --prod
```

### Roll back

Vercel dashboard → Project → Deployments → find a green deploy → **⋯** →
**Promote to Production**.

### Update an env var

Dashboard → Project → Settings → Environment Variables → edit → **Save**.
Then Deployments → **Redeploy** (env-var edits don't auto-redeploy).

### Preview URL for a specific PR

Vercel automatically comments on the PR with the preview URL. Or:
Dashboard → Project → Deployments → filter by branch.

## Opt-in: CI-driven deploys (`deploy-frontend.yml`)

Use this ONLY if you want GitHub Actions to control deploys instead of the
Vercel webhook.

1. **Disable** Vercel's native git integration for this repo:
   Project → Settings → Git → **Disconnect** OR clear the **Production
   Branch** field so no branch auto-deploys.
2. `npm i -g vercel && vercel login`.
3. `cd frontend && vercel link` — creates `frontend/.vercel/project.json`.
   **Do not commit `.vercel/`** — the `.gitignore` should already exclude it.
4. `cat frontend/.vercel/project.json` — copy the `orgId` and `projectId`.
5. Generate a token: `vercel.com/account/tokens`.
6. GitHub → Repository → Settings → Secrets and variables → Actions →
   **New repository secret**. Add three:
   - `VERCEL_TOKEN` — the token from step 5.
   - `VERCEL_ORG_ID` — from `.vercel/project.json`.
   - `VERCEL_PROJECT_ID` — from `.vercel/project.json`.
7. Optionally uncomment the `push:` block in `deploy-frontend.yml` to make
   it fire on every push. Otherwise the workflow runs on manual
   `workflow_dispatch` only.

## Known caveats

- **`NEXT_PUBLIC_*` vars are baked at build time.** Changing them after a
  deploy has no effect on already-served bundles until a redeploy.
- **Vercel free tier: 100 GB bandwidth/month, 6,000 build-minutes/month.**
  Every push triggers a preview build, so churn adds up. Not a concern
  for a portfolio project.
- **CORS: the backend must allow the frontend origin.** Update
  `ALLOWED_ORIGINS` on Fly after the first Vercel deploy. Preview URLs
  each have their own subdomain (e.g. `lumen-frontend-git-<branch>.vercel.app`);
  either enumerate them in `ALLOWED_ORIGINS` or accept that PR previews
  can't hit the production backend from a browser without a config bump.
- **`next.config.ts` throws on missing `NEXT_PUBLIC_*` vars.** The build
  fails fast with a clear message if any of the three are unset in the
  Vercel dashboard — good, prevents silent `undefined` in the bundle.
- **`v2/intelligence-agent` is the branch, not the URL.** Vercel derives
  the production URL from the project name (defaults to
  `lumen-frontend.vercel.app`). Custom domain wiring is in
  Project → Settings → Domains.
