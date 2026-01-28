"""
Database schema synchronization script.
Adds missing columns to existing tables in Supabase.

Run this script to ensure the database schema matches the SQLAlchemy models.
"""

import asyncio
import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Load DATABASE_URL from environment
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable not set")

# Convert postgres:// to postgresql+asyncpg://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgresql://") and "+asyncpg" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)


async def sync_schema():
    """
    Add missing columns to existing tables.
    """
    engine = create_async_engine(DATABASE_URL, echo=True)
    
    # List of ALTER TABLE statements to add missing columns
    alterations = [
        # global_settings table
        """
        ALTER TABLE global_settings 
        ADD COLUMN IF NOT EXISTS bot_config_json JSONB DEFAULT NULL;
        """,
        """
        ALTER TABLE global_settings 
        ADD COLUMN IF NOT EXISTS current_losing_streak INTEGER DEFAULT 0;
        """,
        """
        ALTER TABLE global_settings 
        ADD COLUMN IF NOT EXISTS max_losing_streak INTEGER DEFAULT 0;
        """,
        """
        ALTER TABLE global_settings 
        ADD COLUMN IF NOT EXISTS streak_reduction_enabled BOOLEAN DEFAULT FALSE;
        """,
        """
        ALTER TABLE global_settings 
        ADD COLUMN IF NOT EXISTS streak_reduction_pct_per_loss NUMERIC(5,2) DEFAULT 10.0;
        """,
        """
        ALTER TABLE global_settings 
        ADD COLUMN IF NOT EXISTS min_balance_threshold_usdc NUMERIC(18,6) DEFAULT 50.0;
        """,
        """
        ALTER TABLE global_settings 
        ADD COLUMN IF NOT EXISTS balance_check_interval_seconds INTEGER DEFAULT 30;
        """,
        """
        ALTER TABLE global_settings 
        ADD COLUMN IF NOT EXISTS alert_email VARCHAR(255);
        """,
        """
        ALTER TABLE global_settings 
        ADD COLUMN IF NOT EXISTS alert_phone VARCHAR(20);
        """,
        """
        ALTER TABLE global_settings 
        ADD COLUMN IF NOT EXISTS kill_switch_triggered_at TIMESTAMP WITH TIME ZONE;
        """,
        """
        ALTER TABLE global_settings 
        ADD COLUMN IF NOT EXISTS kill_switch_reason VARCHAR(255);
        """,
        
        # sport_configs table
        """
        ALTER TABLE sport_configs 
        ADD COLUMN IF NOT EXISTS min_time_remaining_minutes INTEGER DEFAULT 5;
        """,
        """
        ALTER TABLE sport_configs 
        ADD COLUMN IF NOT EXISTS max_elapsed_minutes INTEGER DEFAULT 70;
        """,
        """
        ALTER TABLE sport_configs 
        ADD COLUMN IF NOT EXISTS max_entry_inning INTEGER DEFAULT 6;
        """,
        """
        ALTER TABLE sport_configs 
        ADD COLUMN IF NOT EXISTS min_outs_remaining INTEGER DEFAULT 6;
        """,
        """
        ALTER TABLE sport_configs 
        ADD COLUMN IF NOT EXISTS max_entry_set INTEGER DEFAULT 2;
        """,
        """
        ALTER TABLE sport_configs 
        ADD COLUMN IF NOT EXISTS min_sets_remaining INTEGER DEFAULT 1;
        """,
        """
        ALTER TABLE sport_configs 
        ADD COLUMN IF NOT EXISTS max_entry_round INTEGER DEFAULT 2;
        """,
        """
        ALTER TABLE sport_configs 
        ADD COLUMN IF NOT EXISTS max_entry_hole INTEGER DEFAULT 14;
        """,
        """
        ALTER TABLE sport_configs 
        ADD COLUMN IF NOT EXISTS min_holes_remaining INTEGER DEFAULT 4;
        """,
        """
        ALTER TABLE sport_configs 
        ADD COLUMN IF NOT EXISTS exit_time_remaining_seconds INTEGER DEFAULT 120;
        """,
    ]
    
    async with engine.begin() as conn:
        for sql in alterations:
            try:
                await conn.execute(text(sql))
                print(f"OK: {sql.strip()[:60]}...")
            except Exception as e:
                print(f"SKIP/ERROR: {sql.strip()[:60]}... - {e}")
        
        await conn.commit()
    
    print("\nSchema sync complete!")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(sync_schema())
