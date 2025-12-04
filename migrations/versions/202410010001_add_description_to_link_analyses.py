"""add description to link analyses

Revision ID: 202410010001
Revises: 202409010001
Create Date: 2024-10-01 00:01:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "202410010001"
down_revision = "202409010001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_link_analyses",
        sa.Column("description", sa.Text(), nullable=True),
    )
    op.add_column(
        "order_link_analyses",
        sa.Column("description", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("order_link_analyses", "description")
    op.drop_column("user_link_analyses", "description")
