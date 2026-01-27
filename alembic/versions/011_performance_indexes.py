"""Add performance indexes and data integrity constraints (REQ-PERF-002, REQ-PERF-005)

Revision ID: 011_performance_indexes
Revises: 010_add_refresh_tokens
Create Date: 2026-01-27 15:00:00.000000

This migration adds:
1. Performance indexes on foreign keys and frequently queried columns
2. Composite indexes for common query patterns
3. Partial indexes for filtered queries
4. CHECK constraints for data integrity
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '011_performance_indexes'
down_revision = '010_add_refresh_tokens'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ==========================================================================
    # POSITIONS TABLE INDEXES
    # ==========================================================================
    
    # Foreign key indexes (if not already created by SQLAlchemy)
    op.create_index(
        'ix_positions_user_id',
        'positions',
        ['user_id'],
        if_not_exists=True
    )
    op.create_index(
        'ix_positions_tracked_market_id',
        'positions',
        ['tracked_market_id'],
        if_not_exists=True
    )
    op.create_index(
        'ix_positions_account_id',
        'positions',
        ['account_id'],
        if_not_exists=True
    )
    
    # Status-based queries (open vs closed positions)
    op.create_index(
        'ix_positions_status',
        'positions',
        ['status'],
        if_not_exists=True
    )
    
    # Composite index for user's open positions (most common query)
    op.create_index(
        'ix_positions_user_status',
        'positions',
        ['user_id', 'status'],
        if_not_exists=True
    )
    
    # Partial index for open positions only (faster for common queries)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_positions_user_open
        ON positions (user_id)
        WHERE status = 'open'
    """)
    
    # Time-based queries for analytics
    op.create_index(
        'ix_positions_opened_at',
        'positions',
        ['opened_at'],
        if_not_exists=True
    )
    op.create_index(
        'ix_positions_closed_at',
        'positions',
        ['closed_at'],
        if_not_exists=True
    )
    
    # Sport filtering
    op.create_index(
        'ix_positions_sport',
        'positions',
        ['sport'],
        if_not_exists=True
    )
    
    # Composite for user analytics by sport
    op.create_index(
        'ix_positions_user_sport_status',
        'positions',
        ['user_id', 'sport', 'status'],
        if_not_exists=True
    )
    
    # ==========================================================================
    # TRADES TABLE INDEXES
    # ==========================================================================
    
    op.create_index(
        'ix_trades_user_id',
        'trades',
        ['user_id'],
        if_not_exists=True
    )
    op.create_index(
        'ix_trades_position_id',
        'trades',
        ['position_id'],
        if_not_exists=True
    )
    op.create_index(
        'ix_trades_status',
        'trades',
        ['status'],
        if_not_exists=True
    )
    op.create_index(
        'ix_trades_executed_at',
        'trades',
        ['executed_at'],
        if_not_exists=True
    )
    op.create_index(
        'ix_trades_created_at',
        'trades',
        ['created_at'],
        if_not_exists=True
    )
    
    # Composite for recent trades by user
    op.create_index(
        'ix_trades_user_created',
        'trades',
        ['user_id', 'created_at'],
        if_not_exists=True
    )
    
    # ==========================================================================
    # TRACKED_MARKETS TABLE INDEXES
    # ==========================================================================
    
    op.create_index(
        'ix_tracked_markets_user_id',
        'tracked_markets',
        ['user_id'],
        if_not_exists=True
    )
    op.create_index(
        'ix_tracked_markets_condition_id',
        'tracked_markets',
        ['condition_id'],
        if_not_exists=True
    )
    op.create_index(
        'ix_tracked_markets_sport',
        'tracked_markets',
        ['sport'],
        if_not_exists=True
    )
    op.create_index(
        'ix_tracked_markets_is_active',
        'tracked_markets',
        ['is_active'],
        if_not_exists=True
    )
    
    # Composite for active markets by user
    op.create_index(
        'ix_tracked_markets_user_active',
        'tracked_markets',
        ['user_id', 'is_active'],
        if_not_exists=True
    )
    
    # Partial index for active markets only
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_tracked_markets_active_only
        ON tracked_markets (user_id, sport)
        WHERE is_active = true
    """)
    
    # ESPN event lookup
    op.create_index(
        'ix_tracked_markets_espn_event',
        'tracked_markets',
        ['espn_event_id'],
        if_not_exists=True
    )
    
    # ==========================================================================
    # SPORT_CONFIGS TABLE INDEXES
    # ==========================================================================
    
    op.create_index(
        'ix_sport_configs_user_id',
        'sport_configs',
        ['user_id'],
        if_not_exists=True
    )
    op.create_index(
        'ix_sport_configs_sport',
        'sport_configs',
        ['sport'],
        if_not_exists=True
    )
    
    # Partial index for enabled configs
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_sport_configs_user_enabled
        ON sport_configs (user_id, sport)
        WHERE enabled = true
    """)
    
    # ==========================================================================
    # ACTIVITY_LOGS TABLE INDEXES
    # ==========================================================================
    
    op.create_index(
        'ix_activity_logs_user_id',
        'activity_logs',
        ['user_id'],
        if_not_exists=True
    )
    op.create_index(
        'ix_activity_logs_level',
        'activity_logs',
        ['level'],
        if_not_exists=True
    )
    op.create_index(
        'ix_activity_logs_timestamp',
        'activity_logs',
        ['timestamp'],
        if_not_exists=True
    )
    op.create_index(
        'ix_activity_logs_module',
        'activity_logs',
        ['module'],
        if_not_exists=True
    )
    
    # Composite for paginated logs by user
    op.create_index(
        'ix_activity_logs_user_timestamp',
        'activity_logs',
        ['user_id', 'timestamp'],
        if_not_exists=True
    )
    
    # ==========================================================================
    # POLYMARKET_ACCOUNTS TABLE INDEXES
    # ==========================================================================
    
    op.create_index(
        'ix_polymarket_accounts_user_id',
        'polymarket_accounts',
        ['user_id'],
        unique=True,
        if_not_exists=True
    )
    
    # ==========================================================================
    # GLOBAL_SETTINGS TABLE INDEXES
    # ==========================================================================
    
    op.create_index(
        'ix_global_settings_user_id',
        'global_settings',
        ['user_id'],
        unique=True,
        if_not_exists=True
    )
    
    # ==========================================================================
    # CHECK CONSTRAINTS FOR DATA INTEGRITY (REQ-PERF-005)
    # ==========================================================================
    
    # Helper to add constraint only if it doesn't exist (PostgreSQL)
    def add_check_constraint_if_not_exists(table: str, constraint_name: str, check_expr: str) -> None:
        op.execute(f"""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = '{constraint_name}'
                ) THEN
                    ALTER TABLE {table} ADD CONSTRAINT {constraint_name} CHECK ({check_expr});
                END IF;
            END $$;
        """)
    
    # Positions: price must be between 0 and 1 (probability)
    add_check_constraint_if_not_exists(
        'positions',
        'chk_positions_entry_price',
        'entry_price >= 0 AND entry_price <= 1'
    )
    
    add_check_constraint_if_not_exists(
        'positions',
        'chk_positions_exit_price',
        'exit_price IS NULL OR (exit_price >= 0 AND exit_price <= 1)'
    )
    
    # Positions: size must be positive
    add_check_constraint_if_not_exists(
        'positions',
        'chk_positions_entry_size',
        'entry_size > 0'
    )
    
    # Trades: price must be between 0 and 1
    add_check_constraint_if_not_exists(
        'trades',
        'chk_trades_price',
        'price >= 0 AND price <= 1'
    )
    
    # Trades: size must be positive
    add_check_constraint_if_not_exists(
        'trades',
        'chk_trades_size',
        'size > 0'
    )
    
    # Sport configs: percentages must be valid
    add_check_constraint_if_not_exists(
        'sport_configs',
        'chk_sport_configs_take_profit',
        'take_profit_pct >= 0 AND take_profit_pct <= 1'
    )
    
    add_check_constraint_if_not_exists(
        'sport_configs',
        'chk_sport_configs_stop_loss',
        'stop_loss_pct >= 0 AND stop_loss_pct <= 1'
    )
    
    # Sport configs: position size must be positive
    add_check_constraint_if_not_exists(
        'sport_configs',
        'chk_sport_configs_position_size',
        'position_size_usdc > 0'
    )
    
    # Global settings: max daily loss must be non-negative
    add_check_constraint_if_not_exists(
        'global_settings',
        'chk_global_settings_max_daily_loss',
        'max_daily_loss_usdc >= 0'
    )


def downgrade() -> None:
    # ==========================================================================
    # DROP CHECK CONSTRAINTS
    # ==========================================================================
    
    op.execute("ALTER TABLE global_settings DROP CONSTRAINT IF EXISTS chk_global_settings_max_daily_loss")
    op.execute("ALTER TABLE sport_configs DROP CONSTRAINT IF EXISTS chk_sport_configs_position_size")
    op.execute("ALTER TABLE sport_configs DROP CONSTRAINT IF EXISTS chk_sport_configs_stop_loss")
    op.execute("ALTER TABLE sport_configs DROP CONSTRAINT IF EXISTS chk_sport_configs_take_profit")
    op.execute("ALTER TABLE trades DROP CONSTRAINT IF EXISTS chk_trades_size")
    op.execute("ALTER TABLE trades DROP CONSTRAINT IF EXISTS chk_trades_price")
    op.execute("ALTER TABLE positions DROP CONSTRAINT IF EXISTS chk_positions_entry_size")
    op.execute("ALTER TABLE positions DROP CONSTRAINT IF EXISTS chk_positions_exit_price")
    op.execute("ALTER TABLE positions DROP CONSTRAINT IF EXISTS chk_positions_entry_price")
    
    # ==========================================================================
    # DROP INDEXES
    # ==========================================================================
    
    # Global settings
    op.drop_index('ix_global_settings_user_id', table_name='global_settings')
    
    # Polymarket accounts
    op.drop_index('ix_polymarket_accounts_user_id', table_name='polymarket_accounts')
    
    # Activity logs
    op.drop_index('ix_activity_logs_user_timestamp', table_name='activity_logs')
    op.drop_index('ix_activity_logs_module', table_name='activity_logs')
    op.drop_index('ix_activity_logs_timestamp', table_name='activity_logs')
    op.drop_index('ix_activity_logs_level', table_name='activity_logs')
    op.drop_index('ix_activity_logs_user_id', table_name='activity_logs')
    
    # Sport configs
    op.execute("DROP INDEX IF EXISTS ix_sport_configs_user_enabled")
    op.drop_index('ix_sport_configs_sport', table_name='sport_configs')
    op.drop_index('ix_sport_configs_user_id', table_name='sport_configs')
    
    # Tracked markets
    op.drop_index('ix_tracked_markets_espn_event', table_name='tracked_markets')
    op.execute("DROP INDEX IF EXISTS ix_tracked_markets_active_only")
    op.drop_index('ix_tracked_markets_user_active', table_name='tracked_markets')
    op.drop_index('ix_tracked_markets_is_active', table_name='tracked_markets')
    op.drop_index('ix_tracked_markets_sport', table_name='tracked_markets')
    op.drop_index('ix_tracked_markets_condition_id', table_name='tracked_markets')
    op.drop_index('ix_tracked_markets_user_id', table_name='tracked_markets')
    
    # Trades
    op.drop_index('ix_trades_user_created', table_name='trades')
    op.drop_index('ix_trades_created_at', table_name='trades')
    op.drop_index('ix_trades_executed_at', table_name='trades')
    op.drop_index('ix_trades_status', table_name='trades')
    op.drop_index('ix_trades_position_id', table_name='trades')
    op.drop_index('ix_trades_user_id', table_name='trades')
    
    # Positions
    op.drop_index('ix_positions_user_sport_status', table_name='positions')
    op.drop_index('ix_positions_sport', table_name='positions')
    op.drop_index('ix_positions_closed_at', table_name='positions')
    op.drop_index('ix_positions_opened_at', table_name='positions')
    op.execute("DROP INDEX IF EXISTS ix_positions_user_open")
    op.drop_index('ix_positions_user_status', table_name='positions')
    op.drop_index('ix_positions_status', table_name='positions')
    op.drop_index('ix_positions_account_id', table_name='positions')
    op.drop_index('ix_positions_tracked_market_id', table_name='positions')
    op.drop_index('ix_positions_user_id', table_name='positions')
