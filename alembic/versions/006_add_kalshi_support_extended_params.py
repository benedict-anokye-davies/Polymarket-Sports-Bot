"""Add Kalshi platform support and extended trading parameters

Revision ID: 006_kalshi_extended
Revises: 005_add_paper_trading_multisport
Create Date: 2026-01-25 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '006_kalshi_extended'
down_revision: Union[str, None] = '005_add_paper_trading_multisport'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add platform column to polymarket_accounts
    op.add_column(
        'polymarket_accounts',
        sa.Column('platform', sa.String(20), nullable=False, server_default='polymarket')
    )

    # Add connection_error column to polymarket_accounts
    op.add_column(
        'polymarket_accounts',
        sa.Column('connection_error', sa.Text(), nullable=True)
    )

    # Make funder_address nullable (not needed for Kalshi)
    op.alter_column(
        'polymarket_accounts',
        'funder_address',
        existing_type=sa.String(42),
        nullable=True
    )

    # Make private_key_encrypted nullable (not needed for Kalshi)
    op.alter_column(
        'polymarket_accounts',
        'private_key_encrypted',
        existing_type=sa.Text(),
        nullable=True
    )

    # Add exit_time_remaining_seconds to sport_configs
    op.add_column(
        'sport_configs',
        sa.Column('exit_time_remaining_seconds', sa.Integer(), nullable=True, server_default='120')
    )

    # Add min_volume_threshold to sport_configs
    op.add_column(
        'sport_configs',
        sa.Column('min_volume_threshold', sa.Numeric(10, 2), nullable=True, server_default='1000.00')
    )

    # Remove server defaults after setting values
    op.alter_column(
        'polymarket_accounts',
        'platform',
        server_default=None
    )


def downgrade() -> None:
    # Remove new columns from sport_configs
    op.drop_column('sport_configs', 'min_volume_threshold')
    op.drop_column('sport_configs', 'exit_time_remaining_seconds')

    # Revert polymarket_accounts changes
    op.alter_column(
        'polymarket_accounts',
        'private_key_encrypted',
        existing_type=sa.Text(),
        nullable=False
    )

    op.alter_column(
        'polymarket_accounts',
        'funder_address',
        existing_type=sa.String(42),
        nullable=False
    )

    op.drop_column('polymarket_accounts', 'connection_error')
    op.drop_column('polymarket_accounts', 'platform')
