"""add link and attachment analyses

Revision ID: 202409010001
Revises: 202408010001_add_order_feedbacks
Create Date: 2024-09-01 00:01:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "202409010001"
down_revision = "202408010001_add_order_feedbacks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "attachment_analyses",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("attachment_id", sa.BigInteger(), sa.ForeignKey("attachments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("raw_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_attachment_analyses_attachment_id", "attachment_analyses", ["attachment_id"])

    op.create_table(
        "user_link_analyses",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_uid", sa.String(length=36), sa.ForeignKey("users.uid", ondelete="CASCADE"), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("analysis_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_user_link_analyses_user_uid", "user_link_analyses", ["user_uid"])

    op.create_table(
        "order_link_analyses",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("order_id", sa.BigInteger(), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("analysis_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_order_link_analyses_order_id", "order_link_analyses", ["order_id"])


def downgrade() -> None:
    op.drop_index("ix_order_link_analyses_order_id", table_name="order_link_analyses")
    op.drop_table("order_link_analyses")
    op.drop_index("ix_user_link_analyses_user_uid", table_name="user_link_analyses")
    op.drop_table("user_link_analyses")
    op.drop_index("ix_attachment_analyses_attachment_id", table_name="attachment_analyses")
    op.drop_table("attachment_analyses")
