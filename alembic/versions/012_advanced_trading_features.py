"""Add advanced trading features tables

Revision ID: 012_advanced_trading_features
Revises: 011_performance_indexes
Create Date: 2026-01-29

Adds tables for:
- Advanced orders (trailing stops, stop-loss, take-profit, brackets)
- Portfolio rebalancing targets and history
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '012_advanced_trading_features'
down_revision: Union[str, None] = '011_performance_indexes'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Advanced Orders table
    op.create_table(
        'advanced_orders',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('position_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('positions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('account_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('polymarket_accounts.id', ondelete='SET NULL'), nullable=True),
        
        # Order identification
        sa.Column('order_type', sa.String(30), nullable=False),  # trailing_stop, stop_loss, take_profit, bracket
        sa.Column('token_id', sa.String(100), nullable=False),
        sa.Column('condition_id', sa.String(100), nullable=False),
        sa.Column('side', sa.String(10), nullable=False),  # BUY or SELL
        sa.Column('size', sa.Numeric(18, 6), nullable=False),
        
        # Trailing stop specific
        sa.Column('trail_pct', sa.Numeric(5, 4), nullable=True),
        sa.Column('trail_amount', sa.Numeric(18, 6), nullable=True),
        sa.Column('highest_price', sa.Numeric(5, 4), nullable=True),
        
        # Stop/target prices
        sa.Column('trigger_price', sa.Numeric(5, 4), nullable=True),
        sa.Column('stop_price', sa.Numeric(5, 4), nullable=True),
        sa.Column('target_price', sa.Numeric(5, 4), nullable=True),
        sa.Column('limit_price', sa.Numeric(5, 4), nullable=True),
        
        # Bracket order fields
        sa.Column('entry_price', sa.Numeric(5, 4), nullable=True),
        sa.Column('entry_size', sa.Numeric(18, 6), nullable=True),
        sa.Column('entry_status', sa.String(20), nullable=True),
        sa.Column('take_profit_price', sa.Numeric(5, 4), nullable=True),
        sa.Column('take_profit_status', sa.String(20), nullable=True),
        sa.Column('stop_loss_price', sa.Numeric(5, 4), nullable=True),
        sa.Column('stop_loss_status', sa.String(20), nullable=True),
        
        # Status tracking
        sa.Column('status', sa.String(20), default='pending'),
        sa.Column('triggered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('filled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('filled_price', sa.Numeric(5, 4), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cancel_reason', sa.String(200), nullable=True),
        
        # Exit info (for brackets)
        sa.Column('exit_reason', sa.String(50), nullable=True),
        
        # Metadata
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    
    # Indexes for advanced_orders
    op.create_index('ix_advanced_orders_user_id', 'advanced_orders', ['user_id'])
    op.create_index('ix_advanced_orders_status', 'advanced_orders', ['status'])
    op.create_index('ix_advanced_orders_position_id', 'advanced_orders', ['position_id'])
    op.create_index('ix_advanced_orders_token_id', 'advanced_orders', ['token_id'])
    
    # Portfolio Targets table
    op.create_table(
        'portfolio_targets',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        
        # Target identification
        sa.Column('condition_id', sa.String(100), nullable=False),
        sa.Column('token_id', sa.String(100), nullable=False),
        sa.Column('market_name', sa.String(500), nullable=True),
        sa.Column('sport', sa.String(50), nullable=True),
        
        # Allocation targets
        sa.Column('target_pct', sa.Numeric(5, 2), nullable=False),  # 0.00 - 100.00
        sa.Column('min_pct', sa.Numeric(5, 2), nullable=True),
        sa.Column('max_pct', sa.Numeric(5, 2), nullable=True),
        
        # Priority for rebalancing
        sa.Column('priority', sa.Integer, default=0),
        
        # Status
        sa.Column('is_active', sa.Boolean, default=True),
        
        # Metadata
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        
        # Unique constraint
        sa.UniqueConstraint('user_id', 'condition_id', name='uq_portfolio_targets_user_condition')
    )
    
    # Indexes for portfolio_targets
    op.create_index('ix_portfolio_targets_user_id', 'portfolio_targets', ['user_id'])
    op.create_index('ix_portfolio_targets_condition_id', 'portfolio_targets', ['condition_id'])
    
    # Rebalance History table
    op.create_table(
        'rebalance_history',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        
        # Rebalancing metadata
        sa.Column('strategy', sa.String(30), nullable=False),  # threshold, periodic, manual
        sa.Column('trigger_reason', sa.String(200), nullable=True),
        
        # Portfolio state before
        sa.Column('total_value_before', sa.Numeric(18, 6), nullable=True),
        sa.Column('positions_before', sa.Integer, nullable=True),
        
        # Results
        sa.Column('recommendations_count', sa.Integer, default=0),
        sa.Column('success_count', sa.Integer, default=0),
        sa.Column('failed_count', sa.Integer, default=0),
        sa.Column('total_traded_value', sa.Numeric(18, 6), default=0),
        
        # Portfolio state after
        sa.Column('total_value_after', sa.Numeric(18, 6), nullable=True),
        sa.Column('positions_after', sa.Integer, nullable=True),
        
        # Status
        sa.Column('status', sa.String(20), default='pending'),  # pending, completed, partial, failed
        
        # Detailed actions (JSON)
        sa.Column('recommendations', postgresql.JSONB, nullable=True),
        sa.Column('executed_actions', postgresql.JSONB, nullable=True),
        
        # Metadata
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    )
    
    # Indexes for rebalance_history
    op.create_index('ix_rebalance_history_user_id', 'rebalance_history', ['user_id'])
    op.create_index('ix_rebalance_history_started_at', 'rebalance_history', ['started_at'])
    
    # Add rebalance_config column to users table (if not using separate config table)
    op.add_column(
        'users',
        sa.Column('rebalance_config', postgresql.JSONB, nullable=True)
    )


def downgrade() -> None:
    # Remove rebalance_config from users
    op.drop_column('users', 'rebalance_config')
    
    # Drop tables in reverse order
    op.drop_table('rebalance_history')
    op.drop_table('portfolio_targets')
    op.drop_table('advanced_orders')
