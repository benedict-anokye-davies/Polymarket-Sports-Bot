"""Add audit_events table for compliance logging

Revision ID: 009_audit_events
Revises: 008_game_selection
Create Date: 2026-01-27 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '009_audit_events'
down_revision = '008_game_selection'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create audit_events table
    op.create_table(
        'audit_events',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('event_id', sa.String(length=255), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('severity', sa.String(length=20), nullable=False),
        sa.Column('user_id', sa.String(length=255), nullable=True),
        sa.Column('action', sa.String(length=255), nullable=False),
        sa.Column('resource_type', sa.String(length=100), nullable=False),
        sa.Column('resource_id', sa.String(length=255), nullable=True),
        sa.Column('details', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('correlation_id', sa.String(length=255), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for efficient querying
    op.create_index('ix_audit_events_event_id', 'audit_events', ['event_id'], unique=True)
    op.create_index('ix_audit_events_event_type', 'audit_events', ['event_type'])
    op.create_index('ix_audit_events_severity', 'audit_events', ['severity'])
    op.create_index('ix_audit_events_user_id', 'audit_events', ['user_id'])
    op.create_index('ix_audit_events_timestamp', 'audit_events', ['timestamp'])
    op.create_index('ix_audit_events_correlation', 'audit_events', ['correlation_id'])
    op.create_index('ix_audit_events_user_timestamp', 'audit_events', ['user_id', 'timestamp'])
    op.create_index('ix_audit_events_type_timestamp', 'audit_events', ['event_type', 'timestamp'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_audit_events_type_timestamp', table_name='audit_events')
    op.drop_index('ix_audit_events_user_timestamp', table_name='audit_events')
    op.drop_index('ix_audit_events_correlation', table_name='audit_events')
    op.drop_index('ix_audit_events_timestamp', table_name='audit_events')
    op.drop_index('ix_audit_events_user_id', table_name='audit_events')
    op.drop_index('ix_audit_events_severity', table_name='audit_events')
    op.drop_index('ix_audit_events_event_type', table_name='audit_events')
    op.drop_index('ix_audit_events_event_id', table_name='audit_events')
    
    # Drop table
    op.drop_table('audit_events')
