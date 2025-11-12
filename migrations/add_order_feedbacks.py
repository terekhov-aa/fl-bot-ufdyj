"""add order feedbacks table

Revision ID: add_order_feedbacks
Revises: 
Create Date: 2024-11-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'add_order_feedbacks'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Создаем таблицу order_feedbacks
    op.create_table('order_feedbacks',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('order_id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('feedback_text', sa.Text(), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.uid'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Создаем индексы
    op.create_index('ix_order_feedbacks_order_id', 'order_feedbacks', ['order_id'])
    op.create_index('ix_order_feedbacks_user_id', 'order_feedbacks', ['user_id'])
    op.create_index('ix_order_feedbacks_status', 'order_feedbacks', ['status'])
    
    # Создаем уникальный индекс для предотвращения дублирующих откликов
    op.create_index(
        'ix_order_feedbacks_unique_user_order', 
        'order_feedbacks', 
        ['order_id', 'user_id'], 
        unique=True
    )


def downgrade() -> None:
    # Удаляем индексы
    op.drop_index('ix_order_feedbacks_unique_user_order', 'order_feedbacks')
    op.drop_index('ix_order_feedbacks_status', 'order_feedbacks')
    op.drop_index('ix_order_feedbacks_user_id', 'order_feedbacks')
    op.drop_index('ix_order_feedbacks_order_id', 'order_feedbacks')
    
    # Удаляем таблицу
    op.drop_table('order_feedbacks')
