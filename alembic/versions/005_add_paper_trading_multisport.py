"""Add paper trading mode and enhanced multi-sport features

Revision ID: 005_paper_trading
Revises: a3b4c5d6e7f8
Create Date: 2026-01-25
"""

from alembic import op
import sqlalchemy as sa


revision = '005_paper_trading'
down_revision = 'a3b4c5d6e7f8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add new columns for paper trading and multi-sport enhancements."""
    
    # Global settings enhancements
    op.add_column('global_settings', sa.Column('dry_run_mode', sa.Boolean(), nullable=True, server_default='true'))
    op.add_column('global_settings', sa.Column('emergency_stop', sa.Boolean(), nullable=True, server_default='false'))
    op.add_column('global_settings', sa.Column('max_slippage_pct', sa.Numeric(5, 4), nullable=True, server_default='0.02'))
    op.add_column('global_settings', sa.Column('order_fill_timeout_seconds', sa.Integer(), nullable=True, server_default='60'))
    
    # Sport config enhancements for multi-sport
    op.add_column('sport_configs', sa.Column('max_daily_loss_usdc', sa.Numeric(10, 2), nullable=True, server_default='50.00'))
    op.add_column('sport_configs', sa.Column('max_exposure_usdc', sa.Numeric(10, 2), nullable=True, server_default='200.00'))
    op.add_column('sport_configs', sa.Column('priority', sa.Integer(), nullable=True, server_default='1'))
    op.add_column('sport_configs', sa.Column('trading_hours_start', sa.String(10), nullable=True))
    op.add_column('sport_configs', sa.Column('trading_hours_end', sa.String(10), nullable=True))


def downgrade() -> None:
    """Remove added columns."""
    
    # Global settings
    op.drop_column('global_settings', 'dry_run_mode')
    op.drop_column('global_settings', 'emergency_stop')
    op.drop_column('global_settings', 'max_slippage_pct')
    op.drop_column('global_settings', 'order_fill_timeout_seconds')
    
    # Sport configs
    op.drop_column('sport_configs', 'max_daily_loss_usdc')
    op.drop_column('sport_configs', 'max_exposure_usdc')
    op.drop_column('sport_configs', 'priority')
    op.drop_column('sport_configs', 'trading_hours_start')
    op.drop_column('sport_configs', 'trading_hours_end')
