"""Add auto_trade_all to global_settings

Revision ID: add_auto_trade_all
Revises: 
Create Date: 2026-02-07

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_auto_trade_all'
down_revision = None  # Will be set by alembic
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add auto_trade_all column to global_settings table
    op.add_column('global_settings', sa.Column('auto_trade_all', sa.Boolean(), nullable=True, server_default='false'))


def downgrade() -> None:
    op.drop_column('global_settings', 'auto_trade_all')
