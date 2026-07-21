"""chat01_chat_sessions_messages

Revision ID: e5b02c8f6a39
Revises: d4a91b7f5e28
Create Date: 2026-07-20

Creates `chat_sessions` + `chat_messages` per BUILD.md CHAT-01. FKs to
`portfolios` and `news_clusters` are same-DB (portable). FK to `auth.users(id)`
on `chat_sessions.user_id` is Postgres-only and added conditionally so sqlite
CI can still `alembic upgrade head`.

The role CHECK constraint (`role IN ('user','assistant','system')`) is
declared inline in CREATE TABLE — portable to both dialects.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "e5b02c8f6a39"
down_revision: Union[str, None] = "d4a91b7f5e28"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def _jsonb() -> sa.types.TypeEngine:
    return postgresql.JSONB().with_variant(sa.JSON(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "chat_sessions",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("portfolio_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("seed_cluster_id", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["portfolio_id"], ["portfolios.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["seed_cluster_id"], ["news_clusters.id"]
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_chat_sessions_user_updated",
        "chat_sessions",
        ["user_id", sa.text("updated_at DESC")],
    )

    op.create_table(
        "chat_messages",
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "citations",
            _jsonb(),
            nullable=True,
            server_default=sa.text("'[]'"),
        ),
        sa.Column("tokens_used", sa.Integer(), nullable=True),
        sa.Column("langsmith_run_id", sa.Text(), nullable=True),
        sa.Column(
            "guardrail_violations",
            _jsonb(),
            nullable=True,
            server_default=sa.text("'[]'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.CheckConstraint(
            "role IN ('user','assistant','system')",
            name="ck_chat_messages_role",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"], ["chat_sessions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_chat_messages_session",
        "chat_messages",
        ["session_id", "created_at"],
    )

    if _is_postgres():
        op.create_foreign_key(
            "fk_chat_sessions_user_id",
            "chat_sessions",
            "users",
            ["user_id"],
            ["id"],
            source_schema="public",
            referent_schema="auth",
            ondelete="CASCADE",
        )


def downgrade() -> None:
    if _is_postgres():
        op.drop_constraint(
            "fk_chat_sessions_user_id",
            "chat_sessions",
            schema="public",
            type_="foreignkey",
        )
    op.drop_index("idx_chat_messages_session", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_index("idx_chat_sessions_user_updated", table_name="chat_sessions")
    op.drop_table("chat_sessions")
