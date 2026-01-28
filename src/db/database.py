"""
Database connection and session management.
Uses SQLAlchemy 2.0 async patterns with asyncpg driver for PostgreSQL
or aiosqlite for local SQLite development.
"""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
import logging

from src.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Determine if we're using SQLite (for local dev) or PostgreSQL (production)
is_sqlite = settings.async_database_url.startswith("sqlite")
is_supabase = "supabase" in settings.async_database_url

# SQLite doesn't support pool_size/max_overflow, so configure engine accordingly
if is_sqlite:
    engine = create_async_engine(
        settings.async_database_url,
        echo=settings.debug,
        connect_args={"check_same_thread": False},
    )
elif is_supabase:
    # Supabase pooler requires special settings
    engine = create_async_engine(
        settings.async_database_url,
        echo=settings.debug,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        connect_args={
            "statement_cache_size": 0,  # Required for Supabase pooler
            "prepared_statement_cache_size": 0,
        },
    )
else:
    engine = create_async_engine(
        settings.async_database_url,
        echo=settings.debug,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy ORM models.
    All models should inherit from this class.
    """
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency that provides a database session.
    Automatically closes the session after the request completes.
    
    Yields:
        AsyncSession: Database session for the current request
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """
    Initializes the database by creating all tables.
    Called during application startup.
    Uses checkfirst=True to only create tables that don't exist.
    Also runs schema sync to add any missing columns.
    """
    # Log which tables are registered before creating
    tables = list(Base.metadata.tables.keys())
    logger.info(f"Registered models for tables: {tables}")
    
    if not tables:
        logger.error("No tables registered with Base.metadata! Models not imported.")
        return
    
    try:
        async with engine.begin() as conn:
            # Check existing tables
            from sqlalchemy import inspect
            def get_existing_tables(connection):
                inspector = inspect(connection)
                return inspector.get_table_names()
            
            existing = await conn.run_sync(get_existing_tables)
            logger.info(f"Existing tables in database: {existing}")
            
            missing = [t for t in tables if t not in existing]
            logger.info(f"Missing tables to create: {missing}")
            
            # Create all missing tables
            await conn.run_sync(Base.metadata.create_all)
            
            # Verify tables were created
            existing_after = await conn.run_sync(get_existing_tables)
            logger.info(f"Tables after create_all: {existing_after}")
            
            # Sync schema - add missing columns to existing tables
            await _sync_schema_columns(conn)
            
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {type(e).__name__}: {e}")
        raise


async def _sync_schema_columns(conn) -> None:
    """
    Add missing columns to existing tables.
    Uses IF NOT EXISTS to be idempotent.
    """
    from sqlalchemy import text
    
    alterations = [
        # global_settings table - all potentially missing columns
        "ALTER TABLE global_settings ADD COLUMN IF NOT EXISTS bot_config_json JSONB DEFAULT NULL",
        "ALTER TABLE global_settings ADD COLUMN IF NOT EXISTS current_losing_streak INTEGER DEFAULT 0",
        "ALTER TABLE global_settings ADD COLUMN IF NOT EXISTS max_losing_streak INTEGER DEFAULT 0",
        "ALTER TABLE global_settings ADD COLUMN IF NOT EXISTS streak_reduction_enabled BOOLEAN DEFAULT FALSE",
        "ALTER TABLE global_settings ADD COLUMN IF NOT EXISTS streak_reduction_pct_per_loss NUMERIC(5,2) DEFAULT 10.0",
        "ALTER TABLE global_settings ADD COLUMN IF NOT EXISTS min_balance_threshold_usdc NUMERIC(18,6) DEFAULT 50.0",
        "ALTER TABLE global_settings ADD COLUMN IF NOT EXISTS balance_check_interval_seconds INTEGER DEFAULT 30",
        "ALTER TABLE global_settings ADD COLUMN IF NOT EXISTS alert_email VARCHAR(255)",
        "ALTER TABLE global_settings ADD COLUMN IF NOT EXISTS alert_phone VARCHAR(20)",
        "ALTER TABLE global_settings ADD COLUMN IF NOT EXISTS kill_switch_triggered_at TIMESTAMP WITH TIME ZONE",
        "ALTER TABLE global_settings ADD COLUMN IF NOT EXISTS kill_switch_reason VARCHAR(255)",
        
        # sport_configs table - sport-specific progress columns
        "ALTER TABLE sport_configs ADD COLUMN IF NOT EXISTS min_time_remaining_minutes INTEGER DEFAULT 5",
        "ALTER TABLE sport_configs ADD COLUMN IF NOT EXISTS max_elapsed_minutes INTEGER DEFAULT 70",
        "ALTER TABLE sport_configs ADD COLUMN IF NOT EXISTS max_entry_inning INTEGER DEFAULT 6",
        "ALTER TABLE sport_configs ADD COLUMN IF NOT EXISTS min_outs_remaining INTEGER DEFAULT 6",
        "ALTER TABLE sport_configs ADD COLUMN IF NOT EXISTS max_entry_set INTEGER DEFAULT 2",
        "ALTER TABLE sport_configs ADD COLUMN IF NOT EXISTS min_sets_remaining INTEGER DEFAULT 1",
        "ALTER TABLE sport_configs ADD COLUMN IF NOT EXISTS max_entry_round INTEGER DEFAULT 2",
        "ALTER TABLE sport_configs ADD COLUMN IF NOT EXISTS max_entry_hole INTEGER DEFAULT 14",
        "ALTER TABLE sport_configs ADD COLUMN IF NOT EXISTS min_holes_remaining INTEGER DEFAULT 4",
        "ALTER TABLE sport_configs ADD COLUMN IF NOT EXISTS exit_time_remaining_seconds INTEGER DEFAULT 120",
    ]
    
    for sql in alterations:
        try:
            await conn.execute(text(sql))
            logger.debug(f"Schema sync: {sql[:50]}...")
        except Exception as e:
            # Column might already exist or table doesn't exist yet - that's fine
            logger.debug(f"Schema sync skipped: {sql[:50]}... ({type(e).__name__})")
