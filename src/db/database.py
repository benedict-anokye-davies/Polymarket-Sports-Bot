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

# SQLite doesn't support pool_size/max_overflow, so configure engine accordingly
if is_sqlite:
    engine = create_async_engine(
        settings.async_database_url,
        echo=settings.debug,
        connect_args={"check_same_thread": False},
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
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database initialized successfully")
