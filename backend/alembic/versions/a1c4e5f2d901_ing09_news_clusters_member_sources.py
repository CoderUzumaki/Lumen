"""ing09_news_clusters_member_sources

Revision ID: a1c4e5f2d901
Revises: 371a33d86850
Create Date: 2026-07-03

Wait — this migration should chain after d2a235b04a85 (ING-01), not
371a33d86850 (DATA-01). Correcting below.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a1c4e5f2d901"
down_revision: Union[str, None] = "d2a235b04a85"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _string_array() -> sa.types.TypeEngine:
    return postgresql.ARRAY(sa.String()).with_variant(sa.JSON(), "sqlite")


def upgrade() -> None:
    # Add member_sources column. On Postgres this is TEXT[] with an empty-array
    # default; on sqlite it's JSON and NULL is what a plain ADD COLUMN yields —
    # so backfill NULL rows to [] afterwards.
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.add_column(
            "news_clusters",
            sa.Column(
                "member_sources",
                _string_array(),
                server_default=sa.text("'{}'::text[]"),
                nullable=False,
            ),
        )
    else:
        op.add_column(
            "news_clusters",
            sa.Column("member_sources", _string_array(), nullable=True),
        )
        op.execute(
            "UPDATE news_clusters SET member_sources = '[]' WHERE member_sources IS NULL"
        )
        with op.batch_alter_table("news_clusters") as batch:
            batch.alter_column("member_sources", nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("news_clusters") as batch:
        batch.drop_column("member_sources")
