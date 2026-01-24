"""
CRUD operations for ActivityLog model.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.activity_log import ActivityLog


class ActivityLogCRUD:
    """
    Database operations for ActivityLog model.
    Provides structured logging for system events and trading activity.
    """
    
    @staticmethod
    async def create(
        db: AsyncSession,
        user_id: uuid.UUID,
        level: str,
        category: str,
        message: str,
        details: dict[str, Any] | None = None
    ) -> ActivityLog:
        """
        Creates a new activity log entry.
        
        Args:
            db: Database session
            user_id: Associated user ID
            level: Log level (INFO, WARNING, ERROR)
            category: Event category (TRADE, SYSTEM, AUTH, etc.)
            message: Human-readable message
            details: Optional JSON data with additional context
        
        Returns:
            Created ActivityLog instance
        """
        log = ActivityLog(
            user_id=user_id,
            level=level,
            category=category,
            message=message,
            details=details
        )
        db.add(log)
        await db.commit()
        await db.refresh(log)
        return log
    
    @staticmethod
    async def info(
        db: AsyncSession,
        user_id: uuid.UUID,
        category: str,
        message: str,
        details: dict[str, Any] | None = None
    ) -> ActivityLog:
        """
        Creates an INFO level log entry.
        """
        return await ActivityLogCRUD.create(db, user_id, "INFO", category, message, details)
    
    @staticmethod
    async def warning(
        db: AsyncSession,
        user_id: uuid.UUID,
        category: str,
        message: str,
        details: dict[str, Any] | None = None
    ) -> ActivityLog:
        """
        Creates a WARNING level log entry.
        """
        return await ActivityLogCRUD.create(db, user_id, "WARNING", category, message, details)
    
    @staticmethod
    async def error(
        db: AsyncSession,
        user_id: uuid.UUID,
        category: str,
        message: str,
        details: dict[str, Any] | None = None
    ) -> ActivityLog:
        """
        Creates an ERROR level log entry.
        """
        return await ActivityLogCRUD.create(db, user_id, "ERROR", category, message, details)
    
    @staticmethod
    async def get_recent(
        db: AsyncSession,
        user_id: uuid.UUID,
        limit: int = 50,
        level: str | None = None,
        category: str | None = None
    ) -> list[ActivityLog]:
        """
        Retrieves recent activity logs with optional filtering.
        """
        query = select(ActivityLog).where(ActivityLog.user_id == user_id)
        
        if level:
            query = query.where(ActivityLog.level == level)
        if category:
            query = query.where(ActivityLog.category == category)
        
        query = query.order_by(ActivityLog.created_at.desc()).limit(limit)
        
        result = await db.execute(query)
        return list(result.scalars().all())
    
    @staticmethod
    async def get_by_category(
        db: AsyncSession,
        user_id: uuid.UUID,
        category: str,
        limit: int = 100
    ) -> list[ActivityLog]:
        """
        Retrieves logs filtered by category.
        """
        result = await db.execute(
            select(ActivityLog)
            .where(
                ActivityLog.user_id == user_id,
                ActivityLog.category == category
            )
            .order_by(ActivityLog.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
    
    @staticmethod
    async def get_errors_since(
        db: AsyncSession,
        user_id: uuid.UUID,
        since: datetime
    ) -> list[ActivityLog]:
        """
        Retrieves all error logs since a given timestamp.
        """
        result = await db.execute(
            select(ActivityLog)
            .where(
                ActivityLog.user_id == user_id,
                ActivityLog.level == "ERROR",
                ActivityLog.created_at >= since
            )
            .order_by(ActivityLog.created_at.desc())
        )
        return list(result.scalars().all())
    
    @staticmethod
    async def delete_old_logs(db: AsyncSession, days: int = 30) -> int:
        """
        Deletes activity logs older than specified days.
        
        Args:
            db: Database session
            days: Number of days to retain logs
        
        Returns:
            Number of deleted records
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        
        result = await db.execute(
            delete(ActivityLog).where(ActivityLog.created_at < cutoff)
        )
        await db.commit()
        return result.rowcount
