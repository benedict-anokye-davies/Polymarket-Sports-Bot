"""
Dashboard schemas for overview and statistics.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel


class PositionSummary(BaseModel):
    """
    Summary of a single open position for dashboard display.
    """
    id: uuid.UUID
    token_id: str
    side: str
    team: str | None
    entry_price: Decimal
    current_price: Decimal | None
    unrealized_pnl: Decimal | None
    size: Decimal
    opened_at: datetime
    
    model_config = {"from_attributes": True}


class RecentActivity(BaseModel):
    """
    Single activity log entry for dashboard display.
    """
    id: uuid.UUID
    level: str
    category: str
    message: str
    created_at: datetime
    
    model_config = {"from_attributes": True}


class DashboardStats(BaseModel):
    """
    Aggregated statistics for the dashboard overview.
    """
    balance_usdc: Decimal
    open_positions_count: int
    open_positions_value: Decimal
    total_pnl_today: Decimal
    total_pnl_all_time: Decimal
    win_rate: float
    active_markets_count: int
    bot_status: str
    open_positions: list[PositionSummary]
    recent_activity: list[RecentActivity]
