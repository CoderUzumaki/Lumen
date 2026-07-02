"""JWT verification for Supabase Auth — FastAPI dependency form.

Every `/api/*` route reads its authenticated identity like this:

    @router.get("/api/me")
    async def me(user: UserContext = Depends(require_auth)) -> dict:
        return {"user_id": str(user.user_id)}

The dependency verifies the Bearer token from the `Authorization` header
against Supabase's JWKS endpoint and returns a `UserContext`. Any
verification failure (missing header, malformed token, bad signature,
expired token, wrong issuer/audience, unknown key id) raises
`HTTPException(401)`; the main.py exception handler renders it into the
standard error envelope.

BUILD.md §Auth: `/health` and public metrics endpoints are exempt; every
other `/api/*` route depends on `require_auth`.
"""
from __future__ import annotations

import logging
import threading
from typing import Any
from uuid import UUID

import jwt
from fastapi import HTTPException, Request, status
from jwt import PyJWKClient
from pydantic import BaseModel, Field

from app.utils.config import Config

logger = logging.getLogger(__name__)


class UserContext(BaseModel):
    """Authenticated user identity extracted from a verified Supabase JWT."""

    user_id: UUID
    email: str
    role: str = Field(default="authenticated")


class AuthConfigError(RuntimeError):
    """Raised when the auth subsystem isn't configured (e.g. SUPABASE_URL unset)."""


class TokenError(Exception):
    """Verification failed for a specific token. `code` is safe to return to the client."""

    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code
        self.detail = detail


# --- JWKS client (lazy, thread-safe, PyJWKClient handles kid-miss refetch) ---

_jwks_lock = threading.Lock()
_jwks_client: PyJWKClient | None = None
_jwks_url: str | None = None


def _resolve_supabase_url() -> str:
    base = Config.SUPABASE_URL
    if not base:
        raise AuthConfigError(
            "SUPABASE_URL is not set. Cannot verify auth tokens. "
            "Set it in your .env file or shell environment."
        )
    return base


def _jwks_url_from_config() -> str:
    return f"{_resolve_supabase_url().rstrip('/')}/auth/v1/.well-known/jwks.json"


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client, _jwks_url
    with _jwks_lock:
        url = _jwks_url_from_config()
        if _jwks_client is None or _jwks_url != url:
            _jwks_client = PyJWKClient(url, cache_keys=True, lifespan=3600)
            _jwks_url = url
        return _jwks_client


def _expected_issuer() -> str:
    return f"{_resolve_supabase_url().rstrip('/')}/auth/v1"


# --- Token verification ------------------------------------------------------


def verify_token(token: str) -> dict[str, Any]:
    """Verify a Supabase access token and return its decoded claims."""
    if not token:
        raise TokenError("missing_token", "no Authorization bearer token")

    try:
        signing_key = _get_jwks_client().get_signing_key_from_jwt(token).key
    except jwt.PyJWKClientError as e:
        raise TokenError("unknown_key", f"could not resolve signing key: {e}") from e
    except jwt.DecodeError as e:
        # get_signing_key_from_jwt internally decodes the header to read `kid`,
        # so a malformed token raises here (not on the later jwt.decode call).
        raise TokenError("invalid_token", f"token could not be parsed: {e}") from e

    try:
        payload = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256", "ES256"],
            audience=Config.SUPABASE_JWT_AUD,
            issuer=_expected_issuer(),
            options={"require": ["exp", "sub", "aud", "iss"]},
        )
    except jwt.ExpiredSignatureError as e:
        raise TokenError("expired_token", "token expired") from e
    except jwt.InvalidAudienceError as e:
        raise TokenError("invalid_audience", "token aud claim mismatch") from e
    except jwt.InvalidIssuerError as e:
        raise TokenError("invalid_issuer", "token iss claim mismatch") from e
    except jwt.MissingRequiredClaimError as e:
        raise TokenError("missing_claim", f"required claim missing: {e}") from e
    except jwt.InvalidTokenError as e:
        raise TokenError("invalid_token", f"token validation failed: {e}") from e

    # Defense-in-depth: reject the anon role explicitly so a leaked anon key
    # from the frontend can't reach protected routes.
    role = payload.get("role")
    if role and role != "authenticated":
        raise TokenError("wrong_role", f"role {role!r} is not authenticated")

    return payload


# --- Header parsing ----------------------------------------------------------


def _extract_bearer_token(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    if not header:
        return None
    parts = header.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip()


# --- FastAPI dependency ------------------------------------------------------


async def require_auth(request: Request) -> UserContext:
    """FastAPI dependency: verify a Supabase JWT and return the authenticated user.

    401 is raised (via HTTPException) for any verification failure. Detailed
    reasons are logged server-side; the client sees the generic
    `unauthorized` envelope code so we don't help attackers fingerprint the
    failure mode.
    """
    token = _extract_bearer_token(request)
    if token is None:
        logger.info("auth: missing or malformed Authorization header on %s", request.url.path)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing_token")

    try:
        claims = verify_token(token)
    except TokenError as e:
        logger.info("auth: rejected token on %s (%s: %s)", request.url.path, e.code, e.detail)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=e.code) from e
    except AuthConfigError as e:
        logger.error("auth: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="auth_misconfigured") from e

    return UserContext(
        user_id=UUID(claims["sub"]),
        email=claims.get("email") or "",
        role=claims.get("role", "authenticated"),
    )
