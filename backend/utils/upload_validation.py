"""Upload size and MIME validation for invoice files."""
from __future__ import annotations

from config import Config

ALLOWED_EXTENSIONS = frozenset({"pdf", "jpg", "jpeg", "png", "gif", "bmp", "webp"})
ALLOWED_MIME_PREFIXES = ("image/", "application/pdf")


def validate_upload(filename: str, content: bytes) -> str | None:
    """Return an error message if invalid, else None."""
    if not filename:
        return "No file selected"

    if len(content) > Config.MAX_UPLOAD_BYTES:
        max_mb = Config.MAX_UPLOAD_BYTES // (1024 * 1024)
        return f"File too large. Maximum size is {max_mb} MB."

    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        return (
            "Unsupported file format. Upload PDF or image "
            "(JPG, PNG, GIF, BMP, WEBP)."
        )

    return None
