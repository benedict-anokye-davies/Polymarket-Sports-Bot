"""Add environment field for Kalshi demo/production support

Revision ID: 013_kalshi_env
Revises: 012_advanced_trading_features
Create Date: 2026-01-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '013_kalshi_env'
down_revision: Union[str, None] = '012_advanced_trading_features'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add environment column to polymarket_accounts table."""
    # Add environment column for Kalshi demo/production selection
    # Default to 'production' for existing accounts
    op.add_column(
        'polymarket_accounts',
        sa.Column(
            'environment',
            sa.String(20),
            nullable=False,
            server_default='production'
        )
    )


def downgrade() -> None:
    """Remove environment column."""
    op.drop_column('polymarket_accounts', 'environment')
