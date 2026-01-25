"""Add game selection fields to tracked_markets

Revision ID: 008_game_selection
Revises: 007_sport_specific_thresholds
Create Date: 2026-01-25

Adds is_user_selected and auto_discovered columns to support
user-controlled game selection for trading.
"""

from alembic import op
import sqlalchemy as sa


revision = '008_game_selection'
down_revision = '007_sport_specific_thresholds'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add is_user_selected column - defaults to True for existing markets
    op.add_column(
        'tracked_markets',
        sa.Column(
            'is_user_selected',
            sa.Boolean(),
            nullable=False,
            server_default=sa.text('true'),
            comment='Whether user has selected this game for trading'
        )
    )
    
    # Add auto_discovered column - defaults to True for existing markets
    op.add_column(
        'tracked_markets',
        sa.Column(
            'auto_discovered',
            sa.Boolean(),
            nullable=False,
            server_default=sa.text('true'),
            comment='Whether this market was auto-discovered by the bot'
        )
    )
    
    # Create index for efficient querying of selected markets
    op.create_index(
        'ix_tracked_markets_user_selected',
        'tracked_markets',
        ['user_id', 'is_user_selected'],
        unique=False
    )


def downgrade() -> None:
    op.drop_index('ix_tracked_markets_user_selected', table_name='tracked_markets')
    op.drop_column('tracked_markets', 'auto_discovered')
    op.drop_column('tracked_markets', 'is_user_selected')
