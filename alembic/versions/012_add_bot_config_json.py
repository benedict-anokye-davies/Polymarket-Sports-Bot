"""Add bot_config_json column to global_settings

Revision ID: 012_bot_config_json
Revises: 011_performance_indexes
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision = '012_bot_config_json'
down_revision = '011_performance_indexes'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add bot_config_json column to store persistent bot configuration
    op.add_column(
        'global_settings',
        sa.Column('bot_config_json', JSONB, nullable=True)
    )


def downgrade() -> None:
    op.drop_column('global_settings', 'bot_config_json')
