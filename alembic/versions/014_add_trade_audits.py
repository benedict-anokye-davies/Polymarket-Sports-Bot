"""
Add trade_audits table for comprehensive trade tracking.

Revision ID: 014_add_trade_audits
Revises: 013_add_kalshi_environment
Create Date: 2026-01-30
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision = '014_add_trade_audits'
down_revision = '013_kalshi_env'
branch_labels = None
depends_on = None


def upgrade():
    # Create trade_audits table
    op.create_table(
        'trade_audits',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('position_id', UUID(as_uuid=True), sa.ForeignKey('positions.id'), nullable=True),
        sa.Column('action', sa.String(20), nullable=False),  # ENTRY, EXIT, CANCEL
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('order_details', JSONB, nullable=False),
        sa.Column('game_state', JSONB, nullable=True),
        sa.Column('market_data', JSONB, nullable=True),
        sa.Column('risk_metrics', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'))
    )
    
    # Create indexes for efficient querying
    op.create_index('idx_trade_audits_user_id', 'trade_audits', ['user_id'])
    op.create_index('idx_trade_audits_position_id', 'trade_audits', ['position_id'])
    op.create_index('idx_trade_audits_timestamp', 'trade_audits', ['timestamp'])
    op.create_index('idx_trade_audits_action', 'trade_audits', ['action'])
    
    # Create index for JSONB queries
    op.create_index('idx_trade_audits_order_details', 'trade_audits', ['order_details'], postgresql_using='gin')


def downgrade():
    op.drop_index('idx_trade_audits_order_details', table_name='trade_audits')
    op.drop_index('idx_trade_audits_action', table_name='trade_audits')
    op.drop_index('idx_trade_audits_timestamp', table_name='trade_audits')
    op.drop_index('idx_trade_audits_position_id', table_name='trade_audits')
    op.drop_index('idx_trade_audits_user_id', table_name='trade_audits')
    op.drop_table('trade_audits')
