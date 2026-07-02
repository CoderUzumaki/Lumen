"""ORM model registry.

Import every model module here so `Base.metadata` picks it up during
Alembic autogenerate (and any downstream reflection).
"""
from app.db.models.llm_call import LlmCall  # noqa: F401

__all__ = ["LlmCall"]
