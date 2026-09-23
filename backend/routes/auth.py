"""Authentication helper endpoints."""

from flask import Blueprint, g, jsonify

from utils.auth import require_auth

auth_bp = Blueprint("auth", __name__, url_prefix="/api/v1/auth")


@auth_bp.route("/me", methods=["GET"])
@require_auth
def get_current_user():
    """Return the authenticated user's basic profile derived from the JWT."""
    claims = g.jwt_claims
    metadata = claims.get("user_metadata") or {}

    return jsonify(
        {
            "id": g.user_id,
            "email": g.user_email,
            "name": metadata.get("full_name")
            or metadata.get("name")
            or g.user_email
            or "User",
            "picture": metadata.get("avatar_url") or metadata.get("picture"),
        }
    )
