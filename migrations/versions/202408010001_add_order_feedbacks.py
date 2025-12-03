"""add order_feedbacks table

Revision ID: 202408010001
Revises: 202407010001
Create Date: 2024-08-01 00:01:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "202408010001"
down_revision = "202407010001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "order_feedbacks",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("order_id", sa.BigInteger(), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.uid", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("feedback_text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            server_onupdate=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_order_feedbacks_order_id", "order_feedbacks", ["order_id"])
    op.create_index("ix_order_feedbacks_user_id", "order_feedbacks", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_order_feedbacks_user_id", table_name="order_feedbacks")
    op.drop_index("ix_order_feedbacks_order_id", table_name="order_feedbacks")
    op.drop_table("order_feedbacks")
