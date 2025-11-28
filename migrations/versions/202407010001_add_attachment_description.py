"""add attachment description field

Revision ID: 202407010001
Revises: 202406010001
Create Date: 2024-07-01 00:01:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "202407010001"
down_revision = "202406010001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Добавляем описание файла, полученное от внешнего анализатора
    op.add_column("attachments", sa.Column("description", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("attachments", "description")
