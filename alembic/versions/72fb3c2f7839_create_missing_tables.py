"""Create missing tables

Revision ID: 72fb3c2f7839
Revises: 011_performance_indexes
Create Date: 2026-01-28 02:45:00.000000

This migration creates any missing tables that weren't created in the initial migration.
Uses IF NOT EXISTS to avoid errors on tables that already exist.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = '72fb3c2f7839'
down_revision: Union[str, None] = '011_performance_indexes'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def table_exists(table_name: str) -> bool:
    """Check if a table exists in the database."""
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    # Create global_settings if not exists
    if not table_exists('global_settings'):
        op.create_table('global_settings',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('bot_enabled', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('paper_trading_mode', sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('max_daily_loss', sa.Float(), nullable=False, server_default='100.0'),
            sa.Column('max_position_size', sa.Float(), nullable=False, server_default='50.0'),
            sa.Column('max_open_positions', sa.Integer(), nullable=False, server_default='5'),
            sa.Column('primary_sport', sa.String(50), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('user_id')
        )
        print("Created global_settings table")

    # Create polymarket_accounts if not exists
    if not table_exists('polymarket_accounts'):
        op.create_table('polymarket_accounts',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('wallet_address', sa.String(255), nullable=True),
            sa.Column('encrypted_private_key', sa.Text(), nullable=True),
            sa.Column('encrypted_api_key', sa.Text(), nullable=True),
            sa.Column('encrypted_api_secret', sa.Text(), nullable=True),
            sa.Column('encrypted_passphrase', sa.Text(), nullable=True),
            sa.Column('funder_address', sa.String(255), nullable=True),
            sa.Column('signature_type', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('is_connected', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('last_balance_check', sa.DateTime(timezone=True), nullable=True),
            sa.Column('cached_balance', sa.Float(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('user_id')
        )
        print("Created polymarket_accounts table")

    # Create sport_configs if not exists
    if not table_exists('sport_configs'):
        op.create_table('sport_configs',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('sport', sa.String(50), nullable=False),
            sa.Column('enabled', sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('entry_threshold', sa.Float(), nullable=False, server_default='0.10'),
            sa.Column('exit_threshold', sa.Float(), nullable=False, server_default='0.05'),
            sa.Column('stop_loss', sa.Float(), nullable=False, server_default='0.15'),
            sa.Column('min_time_remaining', sa.Integer(), nullable=False, server_default='300'),
            sa.Column('allowed_segments', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('user_id', 'sport', name='uq_sport_config_user_sport')
        )
        print("Created sport_configs table")

    # Create tracked_markets if not exists
    if not table_exists('tracked_markets'):
        op.create_table('tracked_markets',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('condition_id', sa.String(255), nullable=False),
            sa.Column('token_id', sa.String(255), nullable=False),
            sa.Column('market_slug', sa.String(255), nullable=True),
            sa.Column('question', sa.Text(), nullable=True),
            sa.Column('sport', sa.String(50), nullable=False),
            sa.Column('espn_event_id', sa.String(100), nullable=True),
            sa.Column('baseline_price', sa.Float(), nullable=True),
            sa.Column('baseline_captured_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('current_price', sa.Float(), nullable=True),
            sa.Column('last_price_update', sa.DateTime(timezone=True), nullable=True),
            sa.Column('game_start_time', sa.DateTime(timezone=True), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_tracked_markets_token_id', 'tracked_markets', ['token_id'])
        op.create_index('ix_tracked_markets_condition_id', 'tracked_markets', ['condition_id'])
        print("Created tracked_markets table")

    # Create positions if not exists
    if not table_exists('positions'):
        op.create_table('positions',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('tracked_market_id', postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column('token_id', sa.String(255), nullable=False),
            sa.Column('side', sa.String(10), nullable=False),
            sa.Column('entry_price', sa.Float(), nullable=False),
            sa.Column('exit_price', sa.Float(), nullable=True),
            sa.Column('size', sa.Float(), nullable=False),
            sa.Column('status', sa.String(20), nullable=False, server_default="'open'"),
            sa.Column('entry_reason', sa.Text(), nullable=True),
            sa.Column('exit_reason', sa.Text(), nullable=True),
            sa.Column('pnl', sa.Float(), nullable=True),
            sa.Column('opened_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_positions_status', 'positions', ['status'])
        print("Created positions table")

    # Create trades if not exists
    if not table_exists('trades'):
        op.create_table('trades',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('position_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('order_id', sa.String(255), nullable=True),
            sa.Column('trade_type', sa.String(10), nullable=False),
            sa.Column('price', sa.Float(), nullable=False),
            sa.Column('size', sa.Float(), nullable=False),
            sa.Column('fee', sa.Float(), nullable=True, server_default='0.0'),
            sa.Column('executed_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['position_id'], ['positions.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        print("Created trades table")

    # Create activity_logs if not exists
    if not table_exists('activity_logs'):
        op.create_table('activity_logs',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('event_type', sa.String(50), nullable=False),
            sa.Column('message', sa.Text(), nullable=False),
            sa.Column('details', sa.JSON(), nullable=True),
            sa.Column('severity', sa.String(20), nullable=False, server_default="'info'"),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_activity_logs_event_type', 'activity_logs', ['event_type'])
        op.create_index('ix_activity_logs_created_at', 'activity_logs', ['created_at'])
        print("Created activity_logs table")

    # Create refresh_tokens if not exists
    if not table_exists('refresh_tokens'):
        op.create_table('refresh_tokens',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('token_hash', sa.String(255), nullable=False),
            sa.Column('device_info', sa.String(255), nullable=True),
            sa.Column('ip_address', sa.String(45), nullable=True),
            sa.Column('is_revoked', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_refresh_tokens_token_hash', 'refresh_tokens', ['token_hash'], unique=True)
        op.create_index('ix_refresh_tokens_user_id', 'refresh_tokens', ['user_id'])
        print("Created refresh_tokens table")

    # Create market_configs if not exists
    if not table_exists('market_configs'):
        op.create_table('market_configs',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('condition_id', sa.String(255), nullable=False),
            sa.Column('token_id', sa.String(255), nullable=False),
            sa.Column('market_slug', sa.String(255), nullable=True),
            sa.Column('question', sa.Text(), nullable=True),
            sa.Column('sport', sa.String(50), nullable=False),
            sa.Column('espn_event_id', sa.String(100), nullable=True),
            sa.Column('entry_threshold', sa.Float(), nullable=True),
            sa.Column('exit_threshold', sa.Float(), nullable=True),
            sa.Column('stop_loss', sa.Float(), nullable=True),
            sa.Column('position_size', sa.Float(), nullable=True),
            sa.Column('enabled', sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('user_id', 'token_id', name='uq_market_config_user_token')
        )
        print("Created market_configs table")


def downgrade() -> None:
    # Only drop tables we created in this migration
    # In practice, this would need to check if tables were created by this migration
    pass
