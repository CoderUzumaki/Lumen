"""JWT verification middleware for Supabase Auth.

See `docs/AUTH.md` for the architecture. This module exposes one decorator:

    @require_auth
    def my_route():
        return jsonify(user=g.user_id)

It verifies the Bearer token from the `Authorization` header against
Supabase's JWKS endpoint, then populates the Flask request context with
the authenticated identity:

- g.user_id       -> the `sub` claim (UUID string)
- g.user_email    -> the `email` claim, or None
- g.jwt_claims    -> the full decoded payload (do NOT use for authorization)

Any verification failure (missing header, malformed token, bad signature,
expired token, wrong issuer/audience, unknown key id) results in 401 with
a small JSON body. Detailed reasons are logged server-side; the client
sees a generic error code so we don't help attackers fingerprint the
failure mode.
"""
from __future__ import annotations

import logging
import threading
from functools import wraps
from typing import Any, Callable

import jwt
import requests
from flask import g, jsonify, request
from jwt import PyJWKClient

from config import Config

logger = logging.getLogger(__name__)


class AuthConfigError(RuntimeError):
    """Raised when the auth subsystem isn't configured (e.g. SUPABASE_URL unset)."""


class TokenError(Exception):
    """Verification failed for a specific token. The `code` is safe to return."""

    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code
        self.detail = detail


# --- JWKS client ----------------------------------------------------------
#
# PyJWT's PyJWKClient already does in-memory caching + kid-miss refetch. We
# wrap it in a thread-safe lazy initializer so we don't fetch JWKS at import
# time (the URL may not be configured yet in dev) and so a single client is
# shared across all requests in the process.

_jwks_lock = threading.Lock()
_jwks_client: PyJWKClient | None = None
_jwks_url: str | None = None


def _jwks_url_from_config() -> str:
    base = Config.SUPABASE_URL
    if not base:
        raise AuthConfigError(
            "SUPABASE_URL is not set. Cannot verify auth tokens. "
            "Set it in your .env file or shell environment."
        )
    return f"{base.rstrip('/')}/auth/v1/.well-known/jwks.json"


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client, _jwks_url
    with _jwks_lock:
        url = _jwks_url_from_config()
        # If the configured URL changes mid-process (test fixtures swap it),
        # rebuild the client. In normal operation this only runs once.
        if _jwks_client is None or _jwks_url != url:
            _jwks_client = PyJWKClient(url, cache_keys=True, lifespan=3600)
            _jwks_url = url
        return _jwks_client


def _expected_issuer() -> str:
    return f"{Config.SUPABASE_URL.rstrip('/')}/auth/v1"


# --- Token verification ---------------------------------------------------


def verify_token(token: str) -> dict[str, Any]:
    """Verify a Supabase access token and return its claims.

    Raises:
        TokenError    - the token is invalid (wrong signature/aud/iss/exp/etc.).
        AuthConfigError - SUPABASE_URL is not configured.

    The caller is responsible for catching these and returning 401/500.
    """
    if not token:
        raise TokenError("missing_token", "no Authorization bearer token")

    try:
        signing_key = _get_jwks_client().get_signing_key_from_jwt(token).key
    except jwt.PyJWKClientError as e:
        # Covers: token is malformed, kid not in JWKS even after refresh.
        raise TokenError("unknown_key", f"could not resolve signing key: {e}")
    except requests.RequestException as e:
        # JWKS endpoint unreachable. Distinguishable so the caller can decide
        # whether to 503 instead of 401; we use 401 here for simplicity.
        raise TokenError("jwks_unreachable", f"failed to fetch JWKS: {e}")

    try:
        payload = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256", "ES256"],
            audience=Config.SUPABASE_JWT_AUD,
            issuer=_expected_issuer(),
            options={"require": ["exp", "sub", "aud", "iss"]},
        )
    except jwt.ExpiredSignatureError:
        raise TokenError("expired_token", "token expired")
    except jwt.InvalidAudienceError:
        raise TokenError("invalid_audience", "token aud claim mismatch")
    except jwt.InvalidIssuerError:
        raise TokenError("invalid_issuer", "token iss claim mismatch")
    except jwt.MissingRequiredClaimError as e:
        raise TokenError("missing_claim", f"required claim missing: {e}")
    except jwt.InvalidTokenError as e:
        raise TokenError("invalid_token", f"token validation failed: {e}")

    # Defense-in-depth: Supabase issues `role=authenticated` for real users
    # and `role=anon` for the anonymous public key. Reject anon explicitly so
    # a misuse of the anon key from the frontend doesn't grant access.
    role = payload.get("role")
    if role and role != "authenticated":
        raise TokenError("wrong_role", f"role {role!r} is not authenticated")

    return payload


# --- Header parsing -------------------------------------------------------


def _extract_bearer_token() -> str | None:
    header = request.headers.get("Authorization", "")
    if not header:
        return None
    parts = header.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip()


# --- Decorator ------------------------------------------------------------


def require_auth(fn: Callable) -> Callable:
    """Flask route decorator. See module docstring."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        # Let CORS preflight through untouched. Flask-CORS handles the actual
        # OPTIONS response; here we just need to not 401 on it.
        if request.method == "OPTIONS":
            return fn(*args, **kwargs)

        token = _extract_bearer_token()
        if token is None:
            logger.info("auth: missing or malformed Authorization header on %s", request.path)
            return jsonify({"error": "unauthorized", "code": "missing_token"}), 401

        try:
            claims = verify_token(token)
        except TokenError as e:
            logger.info("auth: rejected token on %s (%s: %s)", request.path, e.code, e.detail)
            return jsonify({"error": "unauthorized", "code": e.code}), 401
        except AuthConfigError as e:
            logger.error("auth: %s", e)
            return jsonify({"error": "auth_misconfigured"}), 500

        g.user_id = claims["sub"]
        g.user_email = claims.get("email")
        g.jwt_claims = claims
        return fn(*args, **kwargs)

    return wrapper
