"""
Advanced features migration: Balance Guardian, Order Confirmation, Position Recovery,
Confidence Scoring, Backtesting, Kelly Sizing, Analytics, Multi-Account Support.

Revision ID: 009_advanced_features
Revises: 008_game_selection
Create Date: 2026-01-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '009_advanced_features'
down_revision: Union[str, None] = '008_game_selection'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ==========================================================================
    # Global Settings - Balance Guardian
    # ==========================================================================
    op.add_column('global_settings', sa.Column(
        'min_balance_threshold_usdc', sa.Numeric(18, 6), nullable=True, server_default='50.0'
    ))
    op.add_column('global_settings', sa.Column(
        'balance_check_interval_seconds', sa.Integer(), nullable=True, server_default='30'
    ))
    op.add_column('global_settings', sa.Column(
        'alert_email', sa.String(255), nullable=True
    ))
    op.add_column('global_settings', sa.Column(
        'alert_phone', sa.String(20), nullable=True
    ))
    op.add_column('global_settings', sa.Column(
        'kill_switch_triggered_at', sa.DateTime(timezone=True), nullable=True
    ))
    op.add_column('global_settings', sa.Column(
        'kill_switch_reason', sa.String(255), nullable=True
    ))
    op.add_column('global_settings', sa.Column(
        'current_losing_streak', sa.Integer(), nullable=True, server_default='0'
    ))
    op.add_column('global_settings', sa.Column(
        'max_losing_streak', sa.Integer(), nullable=True, server_default='0'
    ))
    op.add_column('global_settings', sa.Column(
        'streak_reduction_enabled', sa.Boolean(), nullable=True, server_default='false'
    ))
    op.add_column('global_settings', sa.Column(
        'streak_reduction_pct_per_loss', sa.Numeric(5, 2), nullable=True, server_default='10.0'
    ))

    # ==========================================================================
    # Sport Configs - Kelly Sizing & Confidence
    # ==========================================================================
    op.add_column('sport_configs', sa.Column(
        'use_kelly_sizing', sa.Boolean(), nullable=True, server_default='false'
    ))
    op.add_column('sport_configs', sa.Column(
        'kelly_fraction', sa.Numeric(3, 2), nullable=True, server_default='0.25'
    ))
    op.add_column('sport_configs', sa.Column(
        'min_kelly_sample_size', sa.Integer(), nullable=True, server_default='20'
    ))
    op.add_column('sport_configs', sa.Column(
        'min_entry_confidence_score', sa.Integer(), nullable=True, server_default='60'
    ))

    # ==========================================================================
    # Positions - Order Confirmation & Confidence
    # ==========================================================================
    op.add_column('positions', sa.Column(
        'requested_entry_price', sa.Numeric(5, 4), nullable=True
    ))
    op.add_column('positions', sa.Column(
        'actual_entry_price', sa.Numeric(5, 4), nullable=True
    ))
    op.add_column('positions', sa.Column(
        'fill_status', sa.String(20), nullable=True, server_default='filled'
    ))
    op.add_column('positions', sa.Column(
        'slippage_usdc', sa.Numeric(18, 6), nullable=True
    ))
    op.add_column('positions', sa.Column(
        'confirmation_attempts', sa.Integer(), nullable=True, server_default='0'
    ))
    op.add_column('positions', sa.Column(
        'sync_status', sa.String(20), nullable=True, server_default='synced'
    ))
    op.add_column('positions', sa.Column(
        'recovered_at', sa.DateTime(timezone=True), nullable=True
    ))
    op.add_column('positions', sa.Column(
        'recovery_source', sa.String(50), nullable=True
    ))
    op.add_column('positions', sa.Column(
        'entry_confidence_score', sa.Integer(), nullable=True
    ))
    op.add_column('positions', sa.Column(
        'entry_confidence_breakdown', postgresql.JSONB(), nullable=True
    ))
    op.add_column('positions', sa.Column(
        'account_id', sa.UUID(), nullable=True
    ))
    
    # Add foreign key for account_id
    op.create_foreign_key(
        'fk_positions_account_id',
        'positions', 'polymarket_accounts',
        ['account_id'], ['id'],
        ondelete='SET NULL'
    )

    # ==========================================================================
    # Polymarket Accounts - Multi-Account Support
    # ==========================================================================
    # First drop the unique constraint if it exists
    try:
        op.drop_constraint('polymarket_accounts_user_id_platform_key', 'polymarket_accounts', type_='unique')
    except Exception:
        pass  # Constraint may not exist
    
    op.add_column('polymarket_accounts', sa.Column(
        'account_name', sa.String(100), nullable=True, server_default='Primary'
    ))
    op.add_column('polymarket_accounts', sa.Column(
        'is_primary', sa.Boolean(), nullable=True, server_default='true'
    ))
    op.add_column('polymarket_accounts', sa.Column(
        'is_active', sa.Boolean(), nullable=True, server_default='true'
    ))
    op.add_column('polymarket_accounts', sa.Column(
        'allocation_pct', sa.Numeric(5, 2), nullable=True, server_default='100.0'
    ))

    # ==========================================================================
    # Price Snapshots - For Backtesting
    # ==========================================================================
    op.create_table(
        'price_snapshots',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('user_id', sa.UUID(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('condition_id', sa.String(100), nullable=False),
        sa.Column('token_id', sa.String(100), nullable=False),
        sa.Column('price', sa.Numeric(5, 4), nullable=False),
        sa.Column('game_state', postgresql.JSONB(), nullable=True),
        sa.Column('espn_event_id', sa.String(50), nullable=True),
        sa.Column('sport', sa.String(20), nullable=True),
        sa.Column('captured_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('idx_snapshots_condition_time', 'price_snapshots', ['condition_id', 'captured_at'])
    op.create_index('idx_snapshots_user_sport', 'price_snapshots', ['user_id', 'sport', 'captured_at'])

    # ==========================================================================
    # Backtest Results
    # ==========================================================================
    op.create_table(
        'backtest_results',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('user_id', sa.UUID(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(100), nullable=True),
        sa.Column('config', postgresql.JSONB(), nullable=False),
        sa.Column('result_summary', postgresql.JSONB(), nullable=True),
        sa.Column('trades', postgresql.JSONB(), nullable=True),
        sa.Column('equity_curve', postgresql.JSONB(), nullable=True),
        sa.Column('status', sa.String(20), nullable=True, server_default='pending'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_backtest_user_created', 'backtest_results', ['user_id', 'created_at'])


def downgrade() -> None:
    # Drop backtest tables
    op.drop_index('idx_backtest_user_created', 'backtest_results')
    op.drop_table('backtest_results')
    op.drop_index('idx_snapshots_user_sport', 'price_snapshots')
    op.drop_index('idx_snapshots_condition_time', 'price_snapshots')
    op.drop_table('price_snapshots')

    # Drop polymarket_accounts columns
    op.drop_column('polymarket_accounts', 'allocation_pct')
    op.drop_column('polymarket_accounts', 'is_active')
    op.drop_column('polymarket_accounts', 'is_primary')
    op.drop_column('polymarket_accounts', 'account_name')

    # Drop positions columns
    op.drop_constraint('fk_positions_account_id', 'positions', type_='foreignkey')
    op.drop_column('positions', 'account_id')
    op.drop_column('positions', 'entry_confidence_breakdown')
    op.drop_column('positions', 'entry_confidence_score')
    op.drop_column('positions', 'recovery_source')
    op.drop_column('positions', 'recovered_at')
    op.drop_column('positions', 'sync_status')
    op.drop_column('positions', 'confirmation_attempts')
    op.drop_column('positions', 'slippage_usdc')
    op.drop_column('positions', 'fill_status')
    op.drop_column('positions', 'actual_entry_price')
    op.drop_column('positions', 'requested_entry_price')

    # Drop sport_configs columns
    op.drop_column('sport_configs', 'min_entry_confidence_score')
    op.drop_column('sport_configs', 'min_kelly_sample_size')
    op.drop_column('sport_configs', 'kelly_fraction')
    op.drop_column('sport_configs', 'use_kelly_sizing')

    # Drop global_settings columns
    op.drop_column('global_settings', 'streak_reduction_pct_per_loss')
    op.drop_column('global_settings', 'streak_reduction_enabled')
    op.drop_column('global_settings', 'max_losing_streak')
    op.drop_column('global_settings', 'current_losing_streak')
    op.drop_column('global_settings', 'kill_switch_reason')
    op.drop_column('global_settings', 'kill_switch_triggered_at')
    op.drop_column('global_settings', 'alert_phone')
    op.drop_column('global_settings', 'alert_email')
    op.drop_column('global_settings', 'balance_check_interval_seconds')
    op.drop_column('global_settings', 'min_balance_threshold_usdc')
