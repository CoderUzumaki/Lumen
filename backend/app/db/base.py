from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base for all Lumen ORM models.

    BOOT-05 extends this with the shared id/created_at/updated_at columns and
    wires the async engine + session factory. Kept minimal here so BOOT-02's
    scaffolding boots without a live database URL.
    """
    pass
