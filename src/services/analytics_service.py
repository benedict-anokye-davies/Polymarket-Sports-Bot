"""
Analytics Service - calculates trade performance metrics and statistics.
Provides win rate, ROI, drawdown, Sharpe ratio and other KPIs.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Complete performance statistics."""
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


@dataclass
class SportPerformance:
    """Performance breakdown by sport."""
    sport: str
    total_trades: int
    win_rate: float
    total_pnl: float
    avg_return: float


@dataclass
class TimeSeriesPoint:
    """Single point in equity curve."""
    timestamp: datetime
    equity: float
    drawdown: float
    trade_id: Optional[str]


class AnalyticsService:
    """
    Calculates comprehensive trading analytics and performance metrics.
    
    Provides:
    - Overall performance statistics
    - Sport-specific breakdowns
    - Time-series equity curves
    - Risk metrics (Sharpe, drawdown, etc.)
    """
    
    def __init__(self, db: AsyncSession, user_id: UUID):
        self.db = db
        self.user_id = user_id
    
    async def get_performance_metrics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        sport: Optional[str] = None,
    ) -> PerformanceMetrics:
        """
        Calculate comprehensive performance metrics.
        
        Args:
            start_date: Filter trades from this date
            end_date: Filter trades until this date
            sport: Filter by specific sport
        
        Returns:
            PerformanceMetrics with all calculated statistics
        """
        from src.models import Position
        
        query = select(Position).where(
            and_(
                Position.user_id == self.user_id,
                Position.status == "closed",
            )
        )
        
        if start_date:
            query = query.where(Position.closed_at >= start_date)
        if end_date:
            query = query.where(Position.closed_at <= end_date)
        if sport:
            query = query.where(Position.sport == sport)
        
        query = query.order_by(Position.closed_at.asc())
        
        result = await self.db.execute(query)
        positions = result.scalars().all()
        
        if not positions:
            return self._empty_metrics()
        
        trades = []
        for pos in positions:
            pnl = self._calculate_position_pnl(pos)
            trades.append({
                "pnl": pnl,
                "entry_time": pos.created_at,
                "exit_time": pos.closed_at,
                "is_win": pnl > 0,
            })
        
        return self._compute_metrics(trades)
    
    def _calculate_position_pnl(self, position) -> float:
        """Calculate P&L for a closed position."""
        if position.exit_price is None:
            return 0.0
        
        entry = float(position.actual_entry_price or position.entry_price or 0)
        exit_price = float(position.exit_price)
        contracts = position.contracts or 0
        
        if position.side == "sell" or position.side == "NO":
            pnl = (entry - exit_price) * contracts
        else:
            pnl = (exit_price - entry) * contracts
        
        return pnl
    
    def _compute_metrics(self, trades: list[dict]) -> PerformanceMetrics:
        """Compute all metrics from trade list."""
        total_trades = len(trades)
        
        winning_trades = [t for t in trades if t["is_win"]]
        losing_trades = [t for t in trades if not t["is_win"]]
        
        win_count = len(winning_trades)
        lose_count = len(losing_trades)
        win_rate = win_count / total_trades if total_trades > 0 else 0
        
        gross_profit = sum(t["pnl"] for t in winning_trades)
        gross_loss = abs(sum(t["pnl"] for t in losing_trades))
        total_pnl = gross_profit - gross_loss
        
        avg_win = gross_profit / win_count if win_count > 0 else 0
        avg_loss = gross_loss / lose_count if lose_count > 0 else 0
        
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")
        
        largest_win = max((t["pnl"] for t in winning_trades), default=0)
        largest_loss = abs(min((t["pnl"] for t in losing_trades), default=0))
        
        durations = []
        for t in trades:
            if t["entry_time"] and t["exit_time"]:
                duration = (t["exit_time"] - t["entry_time"]).total_seconds() / 3600
                durations.append(duration)
        avg_duration = sum(durations) / len(durations) if durations else 0
        
        streak_data = self._calculate_streaks(trades)
        
        max_drawdown = self._calculate_max_drawdown(trades)
        
        initial_capital = 1000
        roi_pct = (total_pnl / initial_capital) * 100 if initial_capital > 0 else 0
        
        sharpe = self._calculate_sharpe_ratio(trades)
        calmar = abs(roi_pct / max_drawdown) if max_drawdown > 0 else None
        
        return PerformanceMetrics(
            total_trades=total_trades,
            winning_trades=win_count,
            losing_trades=lose_count,
            win_rate=round(win_rate, 4),
            total_pnl=round(total_pnl, 2),
            gross_profit=round(gross_profit, 2),
            gross_loss=round(gross_loss, 2),
            avg_win=round(avg_win, 2),
            avg_loss=round(avg_loss, 2),
            profit_factor=round(profit_factor, 2) if profit_factor != float("inf") else 999.99,
            largest_win=round(largest_win, 2),
            largest_loss=round(largest_loss, 2),
            avg_trade_duration_hours=round(avg_duration, 2),
            current_streak=streak_data["current"],
            max_win_streak=streak_data["max_win"],
            max_lose_streak=streak_data["max_lose"],
            max_drawdown=round(max_drawdown, 2),
            roi_pct=round(roi_pct, 2),
            sharpe_ratio=round(sharpe, 2) if sharpe else None,
            calmar_ratio=round(calmar, 2) if calmar else None,
        )
    
    def _calculate_streaks(self, trades: list[dict]) -> dict:
        """Calculate winning/losing streaks."""
        if not trades:
            return {"current": 0, "max_win": 0, "max_lose": 0}
        
        max_win_streak = 0
        max_lose_streak = 0
        current_streak = 0
        win_streak = 0
        lose_streak = 0
        
        for trade in trades:
            if trade["is_win"]:
                win_streak += 1
                lose_streak = 0
                max_win_streak = max(max_win_streak, win_streak)
            else:
                lose_streak += 1
                win_streak = 0
                max_lose_streak = max(max_lose_streak, lose_streak)
        
        if trades[-1]["is_win"]:
            current_streak = win_streak
        else:
            current_streak = -lose_streak
        
        return {
            "current": current_streak,
            "max_win": max_win_streak,
            "max_lose": max_lose_streak,
        }
    
    def _calculate_max_drawdown(self, trades: list[dict]) -> float:
        """Calculate maximum drawdown percentage."""
        if not trades:
            return 0.0
        
        peak = 0
        max_dd = 0
        equity = 0
        
        for trade in trades:
            equity += trade["pnl"]
            peak = max(peak, equity)
            drawdown = peak - equity
            if peak > 0:
                dd_pct = (drawdown / peak) * 100
                max_dd = max(max_dd, dd_pct)
        
        return max_dd
    
    def _calculate_sharpe_ratio(
        self,
        trades: list[dict],
        risk_free_rate: float = 0.05,
    ) -> Optional[float]:
        """
        Calculate Sharpe ratio (annualized).
        
        Sharpe = (avg_return - risk_free) / std_dev_returns
        """
        if len(trades) < 10:
            return None
        
        returns = [t["pnl"] for t in trades]
        avg_return = sum(returns) / len(returns)
        
        variance = sum((r - avg_return) ** 2 for r in returns) / len(returns)
        std_dev = variance ** 0.5
        
        if std_dev == 0:
            return None
        
        trades_per_year = 365
        annualized_return = avg_return * trades_per_year
        annualized_std = std_dev * (trades_per_year ** 0.5)
        
        sharpe = (annualized_return - risk_free_rate) / annualized_std
        
        return sharpe
    
    async def get_sport_breakdown(self) -> list[SportPerformance]:
        """Get performance breakdown by sport."""
        from src.models import Position
        
        query = (
            select(
                Position.sport,
                func.count(Position.id).label("total"),
                func.sum(
                    func.case(
                        (Position.exit_price > Position.entry_price, 1),
                        else_=0
                    )
                ).label("wins"),
            )
            .where(
                and_(
                    Position.user_id == self.user_id,
                    Position.status == "closed",
                    Position.sport.isnot(None),
                )
            )
            .group_by(Position.sport)
        )
        
        result = await self.db.execute(query)
        rows = result.fetchall()
        
        breakdown = []
        for row in rows:
            sport, total, wins = row
            win_rate = wins / total if total > 0 else 0
            
            pnl_query = (
                select(func.sum(Position.exit_price - Position.entry_price))
                .where(
                    and_(
                        Position.user_id == self.user_id,
                        Position.status == "closed",
                        Position.sport == sport,
                    )
                )
            )
            pnl_result = await self.db.execute(pnl_query)
            total_pnl = pnl_result.scalar() or 0
            
            breakdown.append(SportPerformance(
                sport=sport,
                total_trades=total,
                win_rate=round(win_rate, 4),
                total_pnl=round(float(total_pnl), 2),
                avg_return=round(float(total_pnl) / total, 2) if total > 0 else 0,
            ))
        
        return breakdown
    
    async def get_equity_curve(
        self,
        start_date: Optional[datetime] = None,
        initial_capital: float = 1000,
    ) -> list[TimeSeriesPoint]:
        """
        Generate equity curve time series.
        
        Returns list of equity values at each trade close.
        """
        from src.models import Position
        
        query = (
            select(Position)
            .where(
                and_(
                    Position.user_id == self.user_id,
                    Position.status == "closed",
                )
            )
            .order_by(Position.closed_at.asc())
        )
        
        if start_date:
            query = query.where(Position.closed_at >= start_date)
        
        result = await self.db.execute(query)
        positions = result.scalars().all()
        
        curve = []
        equity = initial_capital
        peak = initial_capital
        
        for pos in positions:
            pnl = self._calculate_position_pnl(pos)
            equity += pnl
            peak = max(peak, equity)
            drawdown = ((peak - equity) / peak) * 100 if peak > 0 else 0
            
            curve.append(TimeSeriesPoint(
                timestamp=pos.closed_at,
                equity=round(equity, 2),
                drawdown=round(drawdown, 2),
                trade_id=str(pos.id),
            ))
        
        return curve
    
    async def get_daily_pnl(
        self,
        days: int = 30,
    ) -> list[dict]:
        """Get daily P&L for the last N days."""
        from src.models import Position
        
        start_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        query = (
            select(Position)
            .where(
                and_(
                    Position.user_id == self.user_id,
                    Position.status == "closed",
                    Position.closed_at >= start_date,
                )
            )
            .order_by(Position.closed_at.asc())
        )
        
        result = await self.db.execute(query)
        positions = result.scalars().all()
        
        daily_pnl = {}
        for pos in positions:
            if pos.closed_at:
                date_key = pos.closed_at.date().isoformat()
                pnl = self._calculate_position_pnl(pos)
                daily_pnl[date_key] = daily_pnl.get(date_key, 0) + pnl
        
        return [
            {"date": date, "pnl": round(pnl, 2)}
            for date, pnl in sorted(daily_pnl.items())
        ]
    
    def _empty_metrics(self) -> PerformanceMetrics:
        """Return empty metrics when no trades exist."""
        return PerformanceMetrics(
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate=0,
            total_pnl=0,
            gross_profit=0,
            gross_loss=0,
            avg_win=0,
            avg_loss=0,
            profit_factor=0,
            largest_win=0,
            largest_loss=0,
            avg_trade_duration_hours=0,
            current_streak=0,
            max_win_streak=0,
            max_lose_streak=0,
            max_drawdown=0,
            roi_pct=0,
            sharpe_ratio=None,
            calmar_ratio=None,
        )
