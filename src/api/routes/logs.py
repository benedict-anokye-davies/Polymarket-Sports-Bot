"""
Activity log routes for viewing system events and trading activity.
"""

import math
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query
from pydantic import BaseModel

from src.api.deps import DbSession, OnboardedUser
from src.db.crud.activity_log import ActivityLogCRUD
from src.schemas.dashboard import RecentActivity


router = APIRouter(prefix="/logs", tags=["Logs"])


class LogEntry(BaseModel):
    """Log entry matching frontend expectations"""
    id: str
    timestamp: str
    level: str
    module: str
    message: str


class PaginatedLogs(BaseModel):
    """Paginated logs response"""
    items: list[LogEntry]
    total: int
    page: int
    limit: int
    total_pages: int


@router.get("/", response_model=PaginatedLogs)
async def get_activity_logs(
    db: DbSession,
    current_user: OnboardedUser,
    limit: int = Query(50, ge=1, le=500),
    page: int = Query(1, ge=1),
    level: str | None = None,
    category: str | None = None
) -> PaginatedLogs:
    """
    Returns paginated activity logs with optional filtering.
    
    Args:
        limit: Maximum number of logs per page
        page: Page number (1-indexed)
        level: Filter by log level (INFO, WARNING, ERROR)
        category: Filter by category (TRADE, BOT, WALLET, etc.)
    """
    # Get total count for pagination
    total = await ActivityLogCRUD.count_logs(
        db,
        current_user.id,
        level=level if level and level != 'all' else None,
        category=category
    )
    
    # Calculate offset
    offset = (page - 1) * limit
    
    # Get logs with pagination
    logs = await ActivityLogCRUD.get_recent_paginated(
        db,
        current_user.id,
        limit=limit,
        offset=offset,
        level=level if level and level != 'all' else None,
        category=category
    )
    
    # Convert to frontend format
    items = [
        LogEntry(
            id=str(log.id),
            timestamp=log.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            level=log.level,
            module=log.category.lower().replace("_", "."),
            message=log.message
        )
        for log in logs
    ]
    
    return PaginatedLogs(
        items=items,
        total=total,
        page=page,
        limit=limit,
        total_pages=max(1, math.ceil(total / limit))
    )


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
