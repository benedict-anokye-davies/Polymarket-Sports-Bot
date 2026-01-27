"""
Analytics API endpoints - performance metrics and trade statistics.
"""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db, get_current_user
from src.models import User
from src.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["analytics"])


class PerformanceMetricsResponse(BaseModel):
    """Performance metrics response schema."""
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: float
    gross_profit: float
    gross_loss: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    largest_win: float
    largest_loss: float
    avg_trade_duration_hours: float
    current_streak: int
    max_win_streak: int
    max_lose_streak: int
    max_drawdown: float
    roi_pct: float
    sharpe_ratio: Optional[float]
    calmar_ratio: Optional[float]


class SportPerformanceResponse(BaseModel):
    """Sport-specific performance response."""
    sport: str
    total_trades: int
    win_rate: float
    total_pnl: float
    avg_return: float


class EquityPointResponse(BaseModel):
    """Single point in equity curve."""
    timestamp: datetime
    equity: float
    drawdown: float
    trade_id: Optional[str]


class DailyPnLResponse(BaseModel):
    """Daily P&L response."""
    date: str
    pnl: float


@router.get("/performance", response_model=PerformanceMetricsResponse)
async def get_performance_metrics(
    start_date: Optional[datetime] = Query(None, description="Filter from date"),
    end_date: Optional[datetime] = Query(None, description="Filter to date"),
    sport: Optional[str] = Query(None, description="Filter by sport"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get comprehensive trading performance metrics.
    
    Returns win rate, P&L, drawdown, Sharpe ratio and other KPIs.
    """
    analytics = AnalyticsService(db, current_user.id)
    metrics = await analytics.get_performance_metrics(
        start_date=start_date,
        end_date=end_date,
        sport=sport,
    )
    
    return PerformanceMetricsResponse(
        total_trades=metrics.total_trades,
        winning_trades=metrics.winning_trades,
        losing_trades=metrics.losing_trades,
        win_rate=metrics.win_rate,
        total_pnl=metrics.total_pnl,
        gross_profit=metrics.gross_profit,
        gross_loss=metrics.gross_loss,
        avg_win=metrics.avg_win,
        avg_loss=metrics.avg_loss,
        profit_factor=metrics.profit_factor,
        largest_win=metrics.largest_win,
        largest_loss=metrics.largest_loss,
        avg_trade_duration_hours=metrics.avg_trade_duration_hours,
        current_streak=metrics.current_streak,
        max_win_streak=metrics.max_win_streak,
        max_lose_streak=metrics.max_lose_streak,
        max_drawdown=metrics.max_drawdown,
        roi_pct=metrics.roi_pct,
        sharpe_ratio=metrics.sharpe_ratio,
        calmar_ratio=metrics.calmar_ratio,
    )


@router.get("/sports", response_model=list[SportPerformanceResponse])
async def get_sport_breakdown(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get performance breakdown by sport.
    
    Shows win rate and P&L for each sport traded.
    """
    analytics = AnalyticsService(db, current_user.id)
    breakdown = await analytics.get_sport_breakdown()
    
    return [
        SportPerformanceResponse(
            sport=s.sport,
            total_trades=s.total_trades,
            win_rate=s.win_rate,
            total_pnl=s.total_pnl,
            avg_return=s.avg_return,
        )
        for s in breakdown
    ]


@router.get("/equity-curve", response_model=list[EquityPointResponse])
async def get_equity_curve(
    start_date: Optional[datetime] = Query(None),
    initial_capital: float = Query(1000, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get equity curve time series.
    
    Returns equity value at each trade close for charting.
    """
    analytics = AnalyticsService(db, current_user.id)
    curve = await analytics.get_equity_curve(
        start_date=start_date,
        initial_capital=initial_capital,
    )
    
    return [
        EquityPointResponse(
            timestamp=point.timestamp,
            equity=point.equity,
            drawdown=point.drawdown,
            trade_id=point.trade_id,
        )
        for point in curve
    ]


@router.get("/daily-pnl", response_model=list[DailyPnLResponse])
async def get_daily_pnl(
    days: int = Query(30, ge=1, le=365, description="Number of days"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get daily P&L for the last N days.
    
    Useful for bar charts showing daily performance.
    """
    analytics = AnalyticsService(db, current_user.id)
    daily = await analytics.get_daily_pnl(days=days)
    
    return [DailyPnLResponse(date=d["date"], pnl=d["pnl"]) for d in daily]
