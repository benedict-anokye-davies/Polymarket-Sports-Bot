"""
Activity log routes for viewing system events and trading activity.
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query

from src.api.deps import DbSession, OnboardedUser
from src.db.crud.activity_log import ActivityLogCRUD
from src.schemas.dashboard import RecentActivity


router = APIRouter(prefix="/logs", tags=["Logs"])


@router.get("/", response_model=list[RecentActivity])
async def get_activity_logs(
    db: DbSession,
    current_user: OnboardedUser,
    limit: int = Query(50, ge=1, le=500),
    level: str | None = None,
    category: str | None = None
) -> list[RecentActivity]:
    """
    Returns activity logs with optional filtering.
    
    Args:
        limit: Maximum number of logs to return
        level: Filter by log level (INFO, WARNING, ERROR)
        category: Filter by category (TRADE, BOT, WALLET, etc.)
    """
    logs = await ActivityLogCRUD.get_recent(
        db,
        current_user.id,
        limit=limit,
        level=level,
        category=category
    )
    
    return [
        RecentActivity(
            id=log.id,
            level=log.level,
            category=log.category,
            message=log.message,
            created_at=log.created_at
        )
        for log in logs
    ]


@router.get("/errors", response_model=list[RecentActivity])
async def get_recent_errors(
    db: DbSession,
    current_user: OnboardedUser,
    hours: int = Query(24, ge=1, le=168)
) -> list[RecentActivity]:
    """
    Returns error logs from the specified time period.
    
    Args:
        hours: Number of hours to look back (default 24, max 168)
    """
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    
    logs = await ActivityLogCRUD.get_errors_since(db, current_user.id, since)
    
    return [
        RecentActivity(
            id=log.id,
            level=log.level,
            category=log.category,
            message=log.message,
            created_at=log.created_at
        )
        for log in logs
    ]


@router.get("/trades", response_model=list[RecentActivity])
async def get_trade_logs(
    db: DbSession,
    current_user: OnboardedUser,
    limit: int = Query(100, ge=1, le=500)
) -> list[RecentActivity]:
    """
    Returns trade-related activity logs.
    """
    logs = await ActivityLogCRUD.get_by_category(db, current_user.id, "TRADE", limit=limit)
    
    return [
        RecentActivity(
            id=log.id,
            level=log.level,
            category=log.category,
            message=log.message,
            created_at=log.created_at
        )
        for log in logs
    ]
