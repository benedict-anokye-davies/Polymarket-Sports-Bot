"""add market_configs table

Revision ID: a3b4c5d6e7f8
Revises: 72fb3c2f7838
Create Date: 2026-01-24 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = 'a3b4c5d6e7f8'
down_revision = '72fb3c2f7838'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Creates the market_configs table for per-market trading parameter overrides.
    """
    op.create_table(
        'market_configs',
        sa.Column('id', UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), nullable=False),
        sa.Column('condition_id', sa.String(100), nullable=False),
        
        # Descriptive fields
        sa.Column('market_question', sa.String(500), nullable=True),
        sa.Column('sport', sa.String(20), nullable=True),
        sa.Column('home_team', sa.String(100), nullable=True),
        sa.Column('away_team', sa.String(100), nullable=True),
        
        # Entry condition overrides
        sa.Column('entry_threshold_drop', sa.Numeric(5, 4), nullable=True),
        sa.Column('entry_threshold_absolute', sa.Numeric(5, 4), nullable=True),
        sa.Column('min_time_remaining_seconds', sa.Integer(), nullable=True),
        
        # Exit condition overrides
        sa.Column('take_profit_pct', sa.Numeric(5, 4), nullable=True),
        sa.Column('stop_loss_pct', sa.Numeric(5, 4), nullable=True),
        
        # Position sizing overrides
        sa.Column('position_size_usdc', sa.Numeric(10, 2), nullable=True),
        sa.Column('max_positions', sa.Integer(), nullable=True),
        
        # Control flags
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('auto_trade', sa.Boolean(), nullable=False, server_default='true'),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        
        # Constraints
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('user_id', 'condition_id', name='uq_user_market_config')
    )
    
    # Create indexes
    op.create_index('ix_market_configs_user_id', 'market_configs', ['user_id'])
    op.create_index('ix_market_configs_condition_id', 'market_configs', ['condition_id'])
    op.create_index('ix_market_configs_sport', 'market_configs', ['sport'])


def downgrade() -> None:
    """
    Removes the market_configs table.
    """
    op.drop_index('ix_market_configs_sport', table_name='market_configs')
    op.drop_index('ix_market_configs_condition_id', table_name='market_configs')
    op.drop_index('ix_market_configs_user_id', table_name='market_configs')
    op.drop_table('market_configs')
