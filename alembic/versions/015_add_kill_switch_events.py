"""
Add kill_switch_events table for tracking emergency stops.

Revision ID: 015_add_kill_switch_events
Revises: 014_add_trade_audits
Create Date: 2026-01-30
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision = '015_add_kill_switch_events'
down_revision = '014_add_trade_audits'
branch_labels = None
depends_on = None


def upgrade():
    # Create kill_switch_events table
    op.create_table(
        'kill_switch_events',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('trigger_type', sa.String(50), nullable=False),  # daily_loss_limit, consecutive_losses, etc.
        sa.Column('triggered_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('positions_closed', sa.Integer, server_default='0'),
        sa.Column('total_pnl', sa.Numeric(18, 6), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolution_notes', sa.Text, nullable=True)
    )
    
    # Create indexes
    op.create_index('idx_kill_switch_user_id', 'kill_switch_events', ['user_id'])
    op.create_index('idx_kill_switch_triggered_at', 'kill_switch_events', ['triggered_at'])
    op.create_index('idx_kill_switch_trigger_type', 'kill_switch_events', ['trigger_type'])


def downgrade():
    op.drop_index('idx_kill_switch_trigger_type', table_name='kill_switch_events')
    op.drop_index('idx_kill_switch_triggered_at', table_name='kill_switch_events')
    op.drop_index('idx_kill_switch_user_id', table_name='kill_switch_events')
    op.drop_table('kill_switch_events')
