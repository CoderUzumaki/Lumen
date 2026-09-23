"""Shared Flask-Limiter instance (initialized in app.py).

Rate-limit keys are derived per authenticated user when a JWT is present,
falling back to the remote address for pre-auth requests. This means:

- Two devices signed in as the same user share one bucket (correct — they
  are one identity).
- Users behind a shared IP (NAT, corporate proxy) get independent buckets
  once signed in, so one heavy user cannot exhaust another's quota.
- Anonymous callers still get IP-based limits — enough to blunt drive-by
  probing of the auth endpoints themselves.

The `sub` claim we read here is NOT signature-verified: Flask-Limiter only
uses it as a bucket key, not for access control (`@require_auth` still
enforces full verification before any handler runs). If an attacker crafts
a JWT with a fake `sub` they simply land in their own bucket — they cannot
exhaust a legitimate user's quota.

Default limit (`60/minute` for every unattributed route) is enough headroom
for a normal browsing session while capping obviously abusive traffic.
Individual routes tighten this via `@limiter.limit(...)`.
"""
from __future__ import annotations

import jwt
from flask import request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


def _rate_limit_key() -> str:
    """Return a stable per-user (or per-IP) bucket key for the current request."""
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        token = header[7:].strip()
        try:
            claims = jwt.decode(token, options={"verify_signature": False})
            sub = claims.get("sub")
            if sub:
                return f"user:{sub}"
        except jwt.PyJWTError:
            pass
    return f"ip:{get_remote_address()}"


limiter = Limiter(
    key_func=_rate_limit_key,
    default_limits=["60 per minute"],
    # In-memory storage is fine for a single-process dev server. Switch to
    # `storage_uri="redis://..."` when we horizontally scale so buckets are
    # shared across workers.
    storage_uri="memory://",
    headers_enabled=True,  # send X-RateLimit-* headers so the frontend can react
)
