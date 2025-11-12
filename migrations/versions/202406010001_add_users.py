"""add users"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "202406010001"
down_revision = "202405010001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("uid", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("competencies_text", sa.Text(), nullable=True),
        sa.Column("categories", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            server_onupdate=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "user_attachments",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_uid",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.uid", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("stored_path", sa.String(length=1024), nullable=False),
        sa.Column("size", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("content_type", sa.String(length=255), nullable=True),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_index("ix_user_attachments_user_uid", "user_attachments", ["user_uid"])


def downgrade() -> None:
    op.drop_index("ix_user_attachments_user_uid", table_name="user_attachments")
    op.drop_table("user_attachments")
    op.drop_table("users")
