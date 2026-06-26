# Authentication Architecture

**Status:** Design — implementation in `AUTH-02` and beyond.
**Decision:** Supabase Auth (verified server-side via JWKS).
**Last updated:** Phase 2 kickoff.

## TL;DR

- Sign up / sign in happens entirely on the frontend through `@supabase/supabase-js`.
- The frontend stores the Supabase session (an `access_token` + `refresh_token`) and attaches `Authorization: Bearer <access_token>` to every backend request.
- The backend's `@require_auth` decorator verifies the JWT against Supabase's JWKS endpoint (RS256/ES256 — no shared secret needed), extracts the `sub` claim, and sets `g.user_id` for the request.
- The client never tells the backend who it is. The token does.

## Why Supabase

| Need | Supabase covers it |
|---|---|
| Email + password | ✅ |
| Magic links | ✅ |
| OAuth (Google, GitHub) | ✅ |
| Password reset | ✅ |
| Email verification | ✅ |
| JWT signing + JWKS endpoint | ✅ |
| Session refresh on the client | ✅ (handled by the JS SDK) |
| Free tier comfortable for a real product | ✅ (50k MAU) |

The alternatives we rejected:

- **NextAuth + custom JWT.** We'd write password hashing, email verification, password reset, refresh rotation, and JWKS ourselves. Maybe 3× the code for the same surface.
- **Clerk.** Best out-of-the-box UI, but the free tier (10k MAU) is tighter and paid tiers add a recurring cost we don't need for a hackathon-stage project.

`config.py` already declared `SUPABASE_URL` / `SUPABASE_KEY` as optional env vars, so the wiring was anticipated; the libraries just weren't pulled in yet.

## What we own vs what Supabase owns

| Owned by Supabase | Owned by Lumen |
|---|---|
| `auth.users` table — emails, password hashes, OAuth identities | `transactions`, `receipts`, `email_configs`, every business table |
| Issuing the JWT | Verifying the JWT |
| Refresh token rotation | Attaching the token to outbound requests |
| Email delivery (verification, reset) | Reading `sub` from the verified JWT, scoping every query by it |

We do **not** mirror users into our own `users` table. The `transactions.user_id` column stores the Supabase user UUID directly (the JWT's `sub` claim) and is the only join key we need. If we later want application-specific user state (preferred currency, locale, etc.), we'll add a `user_profiles` table keyed on `auth.users.id` — but that's deferred until a feature requires it.

## Token format

Supabase issues an `access_token` as a JWT:

```
header.payload.signature
```

Key claims we rely on:

| Claim | Meaning | Lumen use |
|---|---|---|
| `sub` | The user's UUID in `auth.users` | This is `g.user_id` — the only identity Lumen trusts |
| `email` | Verified email | Optional, attached to `g.user_email` for logging only |
| `exp` | Expiry (Unix ts) | Verifier rejects expired tokens |
| `iss` | Issuer URL | Must equal `${SUPABASE_URL}/auth/v1` |
| `aud` | Audience | Must equal `authenticated` |
| `role` | `authenticated` or `anon` | Reject anything other than `authenticated` |

**Token lifetime:** 1 hour (Supabase default). The frontend's Supabase client refreshes silently via the refresh token; the backend never sees the refresh token.

**Signing algorithm:** RS256/ES256, depending on what the Supabase project has configured. Either way, verification uses the JWKS endpoint, not a shared secret:

```
${SUPABASE_URL}/auth/v1/.well-known/jwks.json
```

The JWKS response should be cached in-process (the keys rotate rarely; refetching on every request is wasteful and brittle). Refresh the cache when a token's `kid` isn't in the cached key set.

## Backend verification flow

```
┌─ HTTP request ──────────────────────────────────────────────┐
│ Authorization: Bearer eyJhbGciOiJSUzI1NiI...                │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
         @require_auth decorator on the route
                          │
   ┌──────────────────────┴──────────────────────┐
   │ 1. Read Bearer token from Authorization header
   │ 2. Decode header (unverified) to get `kid`
   │ 3. Fetch matching public key from JWKS cache
   │      (refresh cache if kid not found)
   │ 4. jwt.decode(token, key, algorithms=["RS256","ES256"],
   │                audience="authenticated",
   │                issuer=f"{SUPABASE_URL}/auth/v1")
   │ 5. g.user_id    = payload["sub"]
   │    g.user_email = payload.get("email")
   │    g.jwt_claims = payload
   │ 6. Call the wrapped view
   └─────────────────────────────────────────────┘

   On any failure step (missing header / bad signature /
   expired / wrong issuer / wrong audience / kid not in JWKS
   after refresh), respond 401 with {"error": "unauthorized"}.
```

Routes never read `user_id` from the request body or query string after this. `g.user_id` is the only authoritative identity.

### Library choice

`pyjwt[crypto]` for signature verification. Reasons:
- Lightweight, single purpose, mature.
- The `supabase` Python SDK is built for *running queries against* Supabase as a logged-in client. It's not the right tool for verifying tokens issued to *other* clients — using it just to call `auth.get_user(token)` would make a network round-trip for every request.
- JWKS fetch + cache is ~30 lines of code; no need for a heavyweight dependency.

## Frontend session lifecycle

The Supabase JS client handles almost all of this; our code just wires it up.

```
┌─ Anonymous visitor ─────────────────────────────────────┐
│ /login renders. Calls supabase.auth.signInWithPassword  │
│ (or signInWithOAuth, or signInWithOtp for magic links). │
│ On success, supabase-js persists session in localStorage│
│ and broadcasts onAuthStateChange.                       │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─ Authenticated session ─────────────────────────────────┐
│ AuthProvider context exposes { user, accessToken }.     │
│ Axios interceptor reads the token from the Supabase     │
│ client (single source of truth) and attaches it as      │
│ Authorization: Bearer <token> on every request.         │
│                                                         │
│ Supabase-js auto-refreshes the access token ~5 minutes  │
│ before expiry. Our interceptor always reads the latest, │
│ so no manual refresh handling is needed.                │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─ Sign out ──────────────────────────────────────────────┐
│ supabase.auth.signOut() clears local storage and        │
│ revokes the refresh token server-side. Route guard      │
│ redirects to /login.                                    │
└─────────────────────────────────────────────────────────┘
```

### Route guarding

A client-side `<AuthGuard>` wraps `/dashboard`, `/chatbot`, `/analytics`, `/ai-analytics`. If `useAuth().user` is `null`, redirect to `/login?next=<current-path>`. The current next-auth-stub block in `frontend/src/app/chatbot/page.tsx` gets deleted in `FEAT-04`.

## Required environment variables

### Frontend (`.env.local`)

| Var | Source | Purpose |
|---|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase dashboard → Project Settings → API → Project URL | Initialize the JS client |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase dashboard → API → Project API Keys → `anon` `public` | The publishable client key (safe to ship in the bundle) |

Both must be added to `frontend/.env.example` and the `requiredPublic` array in `next.config.js`.

### Backend (`.env`)

| Var | Source | Purpose |
|---|---|---|
| `SUPABASE_URL` | same as frontend `NEXT_PUBLIC_SUPABASE_URL` | Builds the JWKS URL and the expected `iss` claim |
| `SUPABASE_JWT_AUD` | usually `authenticated` | Expected `aud` claim; surface as a config var rather than hardcoding |

The `service_role` key is **not** needed for token verification. It would only be required if Lumen itself ever needed to act against Supabase's admin API (e.g., to delete a user). Keep it out of the backend until we genuinely need it; storing service_role anywhere it isn't required widens the blast radius.

## Demo data migration

`transactions.user_id` is currently `TEXT` and seeded with the literal string `'123'` by `scripts/populate_db.py` and `scripts/reset_and_populate_inr.py`. Real Supabase user IDs are UUIDs (`550e8400-e29b-41d4-a716-446655440000` shape). After AUTH-02 lands, two follow-ups:

1. The seed scripts take a `--user-id` CLI argument (defaulting to a fixed dev UUID like `00000000-0000-0000-0000-000000000123` so existing flows keep working).
2. A one-off migration moves any rows with `user_id='123'` to that dev UUID, so a developer signing in as that user still sees the demo data. Document in `backend/scripts/README.md`.

## Multi-tenancy guarantees

Once `@require_auth` is applied to every data route (AUTH-03):

- `g.user_id` is always set inside protected routes.
- Routes **never** call `data.get('user_id')` or `request.args.get('user_id')` again — pre-commit grep enforces this.
- Every SQL/ORM read filters on `user_id = :g.user_id`. The SQL agent (AUTH-aware after DB-01) injects this clause server-side, not via the LLM prompt, so a misbehaving prompt cannot bypass tenancy.

The single-tenant escape hatch is the future `Workspace` model (`NEW-06`), which switches the scoping key from `user_id` to `workspace_id` and routes membership through a join table. That's deferred until at least one user requests team accounts.

## What this doc does not cover

- Role-based access control (admin vs viewer within a single tenant) — not needed until `NEW-06`.
- Service-to-service auth (e.g., the email-polling worker calling the API) — handle when we extract a worker; until then, the polling code shares the Flask app's process and can act as a system user.
- API keys for third-party integrations — out of scope until a user requests it.
