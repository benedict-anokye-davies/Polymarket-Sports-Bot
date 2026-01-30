"""
Add orphaned_orders table for tracking untracked positions.

Revision ID: 016_add_orphaned_orders
Revises: 015_add_kill_switch_events
Create Date: 2026-01-30
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision = '016_add_orphaned_orders'
down_revision = '015_add_kill_switch_events'
branch_labels = None
depends_on = None


def upgrade():
    # Create orphaned_orders table
    op.create_table(
        'orphaned_orders',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('ticker', sa.String(100), nullable=False),
        sa.Column('order_id', sa.String(100), nullable=False),
        sa.Column('side', sa.String(10), nullable=False),
        sa.Column('size', sa.Numeric(18, 6), nullable=True),
        sa.Column('price', sa.Numeric(18, 6), nullable=True),
        sa.Column('detected_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('resolved', sa.Boolean, server_default='false'),
        sa.Column('resolution_action', sa.String(50), nullable=True)  # MANUAL_CLOSE, AUTO_CLOSE, FALSE_POSITIVE
    )
    
    # Create indexes
    op.create_index('idx_orphaned_orders_user_id', 'orphaned_orders', ['user_id'])
    op.create_index('idx_orphaned_orders_ticker', 'orphaned_orders', ['ticker'])
    op.create_index('idx_orphaned_orders_detected_at', 'orphaned_orders', ['detected_at'])
    op.create_index('idx_orphaned_orders_resolved', 'orphaned_orders', ['resolved'])


def downgrade():
    op.drop_index('idx_orphaned_orders_resolved', table_name='orphaned_orders')
    op.drop_index('idx_orphaned_orders_detected_at', table_name='orphaned_orders')
    op.drop_index('idx_orphaned_orders_ticker', table_name='orphaned_orders')
    op.drop_index('idx_orphaned_orders_user_id', table_name='orphaned_orders')
    op.drop_table('orphaned_orders')
