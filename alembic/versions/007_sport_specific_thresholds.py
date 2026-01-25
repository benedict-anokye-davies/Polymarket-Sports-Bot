"""Add sport-specific progress threshold columns

Revision ID: 007_sport_specific_thresholds
Revises: 006_kalshi_extended
Create Date: 2026-01-25

Adds columns for sport-specific progress tracking:
- NBA/NFL/NHL: min_time_remaining_minutes (time-based)
- Soccer: max_elapsed_minutes (clock counts up)
- MLB: max_entry_inning, min_outs_remaining (innings-based)
- Tennis: max_entry_set, min_sets_remaining (sets-based)
- MMA: max_entry_round (rounds-based)
- Golf: max_entry_hole, min_holes_remaining (holes-based)
"""

from alembic import op
import sqlalchemy as sa


revision = "007_sport_specific_thresholds"
down_revision = "006_kalshi_extended"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Time-based sports (NBA, NFL, NHL) - minutes remaining
    op.add_column(
        "sport_configs",
        sa.Column("min_time_remaining_minutes", sa.Integer(), nullable=True, default=5)
    )
    
    # Soccer - clock counts up, so we track max elapsed
    op.add_column(
        "sport_configs",
        sa.Column("max_elapsed_minutes", sa.Integer(), nullable=True, default=70)
    )
    
    # MLB - innings-based
    op.add_column(
        "sport_configs",
        sa.Column("max_entry_inning", sa.Integer(), nullable=True, default=6)
    )
    op.add_column(
        "sport_configs",
        sa.Column("min_outs_remaining", sa.Integer(), nullable=True, default=6)
    )
    
    # Tennis - sets-based
    op.add_column(
        "sport_configs",
        sa.Column("max_entry_set", sa.Integer(), nullable=True, default=2)
    )
    op.add_column(
        "sport_configs",
        sa.Column("min_sets_remaining", sa.Integer(), nullable=True, default=1)
    )
    
    # MMA - rounds-based
    op.add_column(
        "sport_configs",
        sa.Column("max_entry_round", sa.Integer(), nullable=True, default=2)
    )
    
    # Golf - holes-based
    op.add_column(
        "sport_configs",
        sa.Column("max_entry_hole", sa.Integer(), nullable=True, default=14)
    )
    op.add_column(
        "sport_configs",
        sa.Column("min_holes_remaining", sa.Integer(), nullable=True, default=4)
    )
    
    # Backfill existing records with smart defaults based on sport
    op.execute("""
        UPDATE sport_configs 
        SET min_time_remaining_minutes = CASE 
            WHEN sport IN ('nba', 'nfl', 'nhl', 'wnba', 'ncaab', 'ncaaf') THEN 5
            ELSE NULL 
        END,
        max_elapsed_minutes = CASE
            WHEN sport IN ('soccer', 'epl', 'laliga', 'bundesliga', 'seriea', 'ligue1', 'ucl') THEN 70
            ELSE NULL
        END,
        max_entry_inning = CASE WHEN sport = 'mlb' THEN 6 ELSE NULL END,
        min_outs_remaining = CASE WHEN sport = 'mlb' THEN 6 ELSE NULL END,
        max_entry_set = CASE WHEN sport = 'tennis' THEN 2 ELSE NULL END,
        min_sets_remaining = CASE WHEN sport = 'tennis' THEN 1 ELSE NULL END,
        max_entry_round = CASE WHEN sport = 'mma' THEN 2 ELSE NULL END,
        max_entry_hole = CASE WHEN sport = 'golf' THEN 14 ELSE NULL END,
        min_holes_remaining = CASE WHEN sport = 'golf' THEN 4 ELSE NULL END
    """)


def downgrade() -> None:
    op.drop_column("sport_configs", "min_time_remaining_minutes")
    op.drop_column("sport_configs", "max_elapsed_minutes")
    op.drop_column("sport_configs", "max_entry_inning")
    op.drop_column("sport_configs", "min_outs_remaining")
    op.drop_column("sport_configs", "max_entry_set")
    op.drop_column("sport_configs", "min_sets_remaining")
    op.drop_column("sport_configs", "max_entry_round")
    op.drop_column("sport_configs", "max_entry_hole")
    op.drop_column("sport_configs", "min_holes_remaining")
