"""ORM model registry.

Import every model module here so `Base.metadata` picks it up during
Alembic autogenerate (and any downstream reflection).
"""
from app.db.models.llm_call import LlmCall  # noqa: F401
from app.db.models.portfolio import Portfolio  # noqa: F401
from app.db.models.position import Position  # noqa: F401
from app.db.models.theme import Theme  # noqa: F401
from app.db.models.user_preferences import UserPreferences  # noqa: F401

__all__ = [
    "LlmCall",
    "Portfolio",
    "Position",
    "Theme",
    "UserPreferences",
]
