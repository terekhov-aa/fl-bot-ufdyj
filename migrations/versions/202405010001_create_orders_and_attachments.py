"""create orders and attachments tables"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "202405010001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "orders",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("external_id", sa.BigInteger(), unique=True, nullable=True),
        sa.Column("link", sa.Text(), unique=True, nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("pub_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rss_raw", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "enriched_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
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
        "attachments",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("order_id", sa.BigInteger(), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("stored_path", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("mime_type", sa.Text(), nullable=True),
        sa.Column("original_url", sa.Text(), nullable=True),
        sa.Column("page_url", sa.Text(), nullable=True),
        sa.Column("sha256", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("attachments")
    op.drop_table("orders")
