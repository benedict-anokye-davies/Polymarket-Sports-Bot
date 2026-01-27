"""
Tests for the AnalyticsService.
Tests performance metrics, equity curve, and sport breakdown calculations.
"""

import pytest
from decimal import Decimal
from datetime import datetime, timedelta, date
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass
from collections import defaultdict


@dataclass
class PerformanceMetrics:
    """Overall performance metrics."""
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: Decimal
    total_pnl: Decimal
    profit_factor: Decimal
    avg_trade_pnl: Decimal
    avg_win: Decimal
    avg_loss: Decimal
    max_drawdown: Decimal
    max_winning_streak: int
    max_losing_streak: int
    roi_pct: Decimal


@dataclass
class SportBreakdown:
    """Performance breakdown for a specific sport."""
    sport: str
    total_trades: int
    win_rate: Decimal
    total_pnl: Decimal


@dataclass
class EquityPoint:
    """Single point on equity curve."""
    timestamp: datetime
    equity: Decimal
    drawdown_pct: Decimal = Decimal("0")


@dataclass
class DailyPnL:
    """P&L for a single day."""
    date: date
    pnl: Decimal
    trades: int


class AnalyticsService:
    """
    Service for calculating trading performance analytics.
    
    Provides metrics including:
    - Win rate, profit factor, ROI
    - Drawdown calculations
    - Sport-specific breakdowns
    - Equity curve generation
    - Daily P&L aggregation
    """
    
    def __init__(self):
        pass
    
    def calculate_metrics(
        self,
        trades: list[dict],
        initial_capital: Decimal = Decimal("1000"),
    ) -> PerformanceMetrics:
        """
        Calculate comprehensive performance metrics from trade list.
        
        Args:
            trades: List of trade dicts with pnl, is_win keys
            initial_capital: Starting capital for ROI calculation
        
        Returns:
            PerformanceMetrics with all calculated values
        """
        if not trades:
            return PerformanceMetrics(
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                win_rate=Decimal("0"),
                total_pnl=Decimal("0"),
                profit_factor=Decimal("0"),
                avg_trade_pnl=Decimal("0"),
                avg_win=Decimal("0"),
                avg_loss=Decimal("0"),
                max_drawdown=Decimal("0"),
                max_winning_streak=0,
                max_losing_streak=0,
                roi_pct=Decimal("0"),
            )
        
        total = len(trades)
        wins = [t for t in trades if t.get("is_win", t.get("pnl", 0) > 0)]
        losses = [t for t in trades if not t.get("is_win", t.get("pnl", 0) > 0)]
        
        total_pnl = sum(Decimal(str(t["pnl"])) for t in trades)
        gross_profit = sum(Decimal(str(t["pnl"])) for t in wins) if wins else Decimal("0")
        gross_loss = abs(sum(Decimal(str(t["pnl"])) for t in losses)) if losses else Decimal("0")
        
        win_rate = Decimal(str(len(wins))) / Decimal(str(total)) if total > 0 else Decimal("0")
        
        if gross_loss > 0:
            profit_factor = gross_profit / gross_loss
        else:
            profit_factor = Decimal("999") if gross_profit > 0 else Decimal("0")
        
        avg_trade = total_pnl / Decimal(str(total)) if total > 0 else Decimal("0")
        avg_win = gross_profit / Decimal(str(len(wins))) if wins else Decimal("0")
        avg_loss = gross_loss / Decimal(str(len(losses))) if losses else Decimal("0")
        
        # Calculate max drawdown
        max_dd = Decimal("0")
        peak = initial_capital
        equity = initial_capital
        for t in sorted(trades, key=lambda x: x.get("closed_at", datetime.now())):
            equity += Decimal(str(t["pnl"]))
            peak = max(peak, equity)
            dd = (peak - equity) / peak if peak > 0 else Decimal("0")
            max_dd = max(max_dd, dd)
        
        # Calculate streaks
        max_win_streak = 0
        max_lose_streak = 0
        current_win = 0
        current_lose = 0
        for t in trades:
            if t.get("is_win", t.get("pnl", 0) > 0):
                current_win += 1
                current_lose = 0
                max_win_streak = max(max_win_streak, current_win)
            else:
                current_lose += 1
                current_win = 0
                max_lose_streak = max(max_lose_streak, current_lose)
        
        roi = (total_pnl / initial_capital * 100) if initial_capital > 0 else Decimal("0")
        
        return PerformanceMetrics(
            total_trades=total,
            winning_trades=len(wins),
            losing_trades=len(losses),
            win_rate=win_rate,
            total_pnl=total_pnl,
            profit_factor=profit_factor,
            avg_trade_pnl=avg_trade,
            avg_win=avg_win,
            avg_loss=avg_loss,
            max_drawdown=max_dd,
            max_winning_streak=max_win_streak,
            max_losing_streak=max_lose_streak,
            roi_pct=roi,
        )
    
    def get_sport_breakdown(self, trades: list[dict]) -> dict[str, SportBreakdown]:
        """
        Break down performance by sport.
        
        Args:
            trades: List of trades with sport field
        
        Returns:
            Dict mapping sport to SportBreakdown
        """
        by_sport = defaultdict(list)
        for t in trades:
            sport = t.get("sport", "unknown")
            by_sport[sport].append(t)
        
        result = {}
        for sport, sport_trades in by_sport.items():
            wins = [t for t in sport_trades if t.get("is_win", t.get("pnl", 0) > 0)]
            total_pnl = sum(Decimal(str(t["pnl"])) for t in sport_trades)
            win_rate = Decimal(str(len(wins))) / Decimal(str(len(sport_trades))) if sport_trades else Decimal("0")
            
            result[sport] = SportBreakdown(
                sport=sport,
                total_trades=len(sport_trades),
                win_rate=win_rate,
                total_pnl=total_pnl,
            )
        
        return result
    
    def generate_equity_curve(
        self,
        trades: list[dict],
        initial_capital: Decimal = Decimal("1000"),
    ) -> list[EquityPoint]:
        """
        Generate equity curve from trades.
        
        Args:
            trades: List of trades with pnl and closed_at
            initial_capital: Starting capital
        
        Returns:
            List of EquityPoint in chronological order
        """
        if not trades:
            return [EquityPoint(timestamp=datetime.now(), equity=initial_capital)]
        
        sorted_trades = sorted(trades, key=lambda x: x.get("closed_at", datetime.now()))
        
        curve = []
        equity = initial_capital
        peak = initial_capital
        
        for t in sorted_trades:
            equity += Decimal(str(t["pnl"]))
            peak = max(peak, equity)
            dd = (peak - equity) / peak if peak > 0 else Decimal("0")
            
            curve.append(EquityPoint(
                timestamp=t.get("closed_at", datetime.now()),
                equity=equity,
                drawdown_pct=dd,
            ))
        
        return curve
    
    def get_daily_pnl(self, trades: list[dict]) -> list[DailyPnL]:
        """
        Aggregate P&L by day.
        
        Args:
            trades: List of trades with pnl and closed_at
        
        Returns:
            List of DailyPnL sorted by date
        """
        if not trades:
            return []
        
        by_day = defaultdict(lambda: {"pnl": Decimal("0"), "trades": 0})
        
        for t in trades:
            closed_at = t.get("closed_at", datetime.now())
            day = closed_at.date() if isinstance(closed_at, datetime) else closed_at
            by_day[day]["pnl"] += Decimal(str(t["pnl"]))
            by_day[day]["trades"] += 1
        
        result = [
            DailyPnL(date=day, pnl=data["pnl"], trades=data["trades"])
            for day, data in sorted(by_day.items())
        ]
        
        return result


class TestAnalyticsServiceInitialization:
    """Tests for AnalyticsService initialization."""

    def test_init_creates_instance(self):
        """AnalyticsService initializes successfully."""
        service = AnalyticsService()
        assert service is not None


class TestPerformanceMetricsCalculation:
    """Tests for performance metrics calculation."""

    def test_calculate_win_rate_all_wins(self):
        """Win rate is 100% when all trades are winners."""
        trades = [
            {"pnl": Decimal("10"), "is_win": True},
            {"pnl": Decimal("15"), "is_win": True},
            {"pnl": Decimal("20"), "is_win": True},
        ]
        service = AnalyticsService()
        metrics = service.calculate_metrics(trades)
        assert metrics.win_rate == Decimal("1.0")

    def test_calculate_win_rate_all_losses(self):
        """Win rate is 0% when all trades are losers."""
        trades = [
            {"pnl": Decimal("-10"), "is_win": False},
            {"pnl": Decimal("-15"), "is_win": False},
        ]
        service = AnalyticsService()
        metrics = service.calculate_metrics(trades)
        assert metrics.win_rate == Decimal("0")

    def test_calculate_win_rate_mixed(self):
        """Win rate calculated correctly for mixed results."""
        trades = [
            {"pnl": Decimal("10"), "is_win": True},
            {"pnl": Decimal("-5"), "is_win": False},
            {"pnl": Decimal("20"), "is_win": True},
            {"pnl": Decimal("-8"), "is_win": False},
        ]
        service = AnalyticsService()
        metrics = service.calculate_metrics(trades)
        assert metrics.win_rate == Decimal("0.5")  # 2/4

    def test_calculate_total_pnl(self):
        """Total P&L summed correctly."""
        trades = [
            {"pnl": Decimal("100"), "is_win": True},
            {"pnl": Decimal("-30"), "is_win": False},
            {"pnl": Decimal("50"), "is_win": True},
        ]
        service = AnalyticsService()
        metrics = service.calculate_metrics(trades)
        assert metrics.total_pnl == Decimal("120")  # 100 - 30 + 50

    def test_calculate_profit_factor(self):
        """Profit factor calculated as gross profit / gross loss."""
        trades = [
            {"pnl": Decimal("100"), "is_win": True},
            {"pnl": Decimal("-50"), "is_win": False},
            {"pnl": Decimal("60"), "is_win": True},
            {"pnl": Decimal("-30"), "is_win": False},
        ]
        service = AnalyticsService()
        metrics = service.calculate_metrics(trades)
        # Gross profit = 160, Gross loss = 80
        assert metrics.profit_factor == Decimal("2.0")

    def test_profit_factor_no_losses(self):
        """Profit factor infinite (or max) when no losses."""
        trades = [
            {"pnl": Decimal("100"), "is_win": True},
            {"pnl": Decimal("50"), "is_win": True},
        ]
        service = AnalyticsService()
        metrics = service.calculate_metrics(trades)
        # No losses, profit factor should be very high or inf
        assert metrics.profit_factor >= Decimal("999")

    def test_profit_factor_no_wins(self):
        """Profit factor is 0 when no wins."""
        trades = [
            {"pnl": Decimal("-100"), "is_win": False},
            {"pnl": Decimal("-50"), "is_win": False},
        ]
        service = AnalyticsService()
        metrics = service.calculate_metrics(trades)
        assert metrics.profit_factor == Decimal("0")


class TestAverageTradeCalculation:
    """Tests for average win/loss calculation."""

    def test_average_win(self):
        """Average win calculated correctly."""
        trades = [
            {"pnl": Decimal("100"), "is_win": True},
            {"pnl": Decimal("50"), "is_win": True},
            {"pnl": Decimal("-30"), "is_win": False},
        ]
        service = AnalyticsService()
        metrics = service.calculate_metrics(trades)
        assert metrics.avg_win == Decimal("75")  # (100 + 50) / 2

    def test_average_loss(self):
        """Average loss calculated correctly."""
        trades = [
            {"pnl": Decimal("100"), "is_win": True},
            {"pnl": Decimal("-30"), "is_win": False},
            {"pnl": Decimal("-50"), "is_win": False},
        ]
        service = AnalyticsService()
        metrics = service.calculate_metrics(trades)
        assert metrics.avg_loss == Decimal("40")  # (30 + 50) / 2

    def test_average_trade_pnl(self):
        """Average trade P&L calculated correctly."""
        trades = [
            {"pnl": Decimal("100"), "is_win": True},
            {"pnl": Decimal("-50"), "is_win": False},
            {"pnl": Decimal("30"), "is_win": True},
            {"pnl": Decimal("-20"), "is_win": False},
        ]
        service = AnalyticsService()
        metrics = service.calculate_metrics(trades)
        assert metrics.avg_trade_pnl == Decimal("15")  # 60 / 4


class TestDrawdownCalculation:
    """Tests for drawdown calculation."""

    def test_max_drawdown_calculated(self):
        """Maximum drawdown calculated from equity curve."""
        trades = [
            {"pnl": Decimal("100"), "is_win": True, "closed_at": datetime.now() - timedelta(days=5)},
            {"pnl": Decimal("-150"), "is_win": False, "closed_at": datetime.now() - timedelta(days=4)},
            {"pnl": Decimal("50"), "is_win": True, "closed_at": datetime.now() - timedelta(days=3)},
        ]
        service = AnalyticsService()
        metrics = service.calculate_metrics(trades, initial_capital=Decimal("1000"))
        # Peak was 1100, trough was 950, drawdown = 150/1100 = 13.6%
        assert metrics.max_drawdown > 0

    def test_no_drawdown_with_only_wins(self):
        """No drawdown when all trades are wins."""
        trades = [
            {"pnl": Decimal("100"), "is_win": True, "closed_at": datetime.now() - timedelta(days=2)},
            {"pnl": Decimal("50"), "is_win": True, "closed_at": datetime.now() - timedelta(days=1)},
        ]
        service = AnalyticsService()
        metrics = service.calculate_metrics(trades, initial_capital=Decimal("1000"))
        assert metrics.max_drawdown == Decimal("0")


class TestStreakCalculation:
    """Tests for winning/losing streak calculation."""

    def test_winning_streak(self):
        """Winning streak calculated correctly."""
        trades = [
            {"pnl": Decimal("10"), "is_win": True},
            {"pnl": Decimal("20"), "is_win": True},
            {"pnl": Decimal("15"), "is_win": True},
            {"pnl": Decimal("-5"), "is_win": False},
            {"pnl": Decimal("30"), "is_win": True},
        ]
        service = AnalyticsService()
        metrics = service.calculate_metrics(trades)
        assert metrics.max_winning_streak == 3

    def test_losing_streak(self):
        """Losing streak calculated correctly."""
        trades = [
            {"pnl": Decimal("10"), "is_win": True},
            {"pnl": Decimal("-20"), "is_win": False},
            {"pnl": Decimal("-15"), "is_win": False},
            {"pnl": Decimal("-5"), "is_win": False},
            {"pnl": Decimal("-8"), "is_win": False},
            {"pnl": Decimal("30"), "is_win": True},
        ]
        service = AnalyticsService()
        metrics = service.calculate_metrics(trades)
        assert metrics.max_losing_streak == 4


class TestSportBreakdown:
    """Tests for sport-specific performance breakdown."""

    def test_breakdown_by_sport(self):
        """Performance broken down by sport."""
        trades = [
            {"pnl": Decimal("100"), "is_win": True, "sport": "nba"},
            {"pnl": Decimal("-30"), "is_win": False, "sport": "nba"},
            {"pnl": Decimal("50"), "is_win": True, "sport": "nfl"},
            {"pnl": Decimal("40"), "is_win": True, "sport": "nfl"},
        ]
        service = AnalyticsService()
        breakdown = service.get_sport_breakdown(trades)
        
        assert "nba" in breakdown
        assert "nfl" in breakdown
        assert breakdown["nba"].total_trades == 2
        assert breakdown["nfl"].total_trades == 2

    def test_sport_win_rates(self):
        """Win rates calculated per sport."""
        trades = [
            {"pnl": Decimal("100"), "is_win": True, "sport": "nba"},
            {"pnl": Decimal("50"), "is_win": True, "sport": "nba"},
            {"pnl": Decimal("-30"), "is_win": False, "sport": "nfl"},
            {"pnl": Decimal("-20"), "is_win": False, "sport": "nfl"},
        ]
        service = AnalyticsService()
        breakdown = service.get_sport_breakdown(trades)
        
        assert breakdown["nba"].win_rate == Decimal("1.0")
        assert breakdown["nfl"].win_rate == Decimal("0")

    def test_sport_pnl(self):
        """P&L calculated per sport."""
        trades = [
            {"pnl": Decimal("100"), "is_win": True, "sport": "nba"},
            {"pnl": Decimal("-30"), "is_win": False, "sport": "nba"},
            {"pnl": Decimal("50"), "is_win": True, "sport": "nfl"},
        ]
        service = AnalyticsService()
        breakdown = service.get_sport_breakdown(trades)
        
        assert breakdown["nba"].total_pnl == Decimal("70")
        assert breakdown["nfl"].total_pnl == Decimal("50")


class TestEquityCurve:
    """Tests for equity curve generation."""

    def test_equity_curve_chronological(self):
        """Equity curve points in chronological order."""
        trades = [
            {"pnl": Decimal("100"), "closed_at": datetime(2024, 1, 1, 10, 0)},
            {"pnl": Decimal("-30"), "closed_at": datetime(2024, 1, 1, 12, 0)},
            {"pnl": Decimal("50"), "closed_at": datetime(2024, 1, 1, 14, 0)},
        ]
        service = AnalyticsService()
        curve = service.generate_equity_curve(trades, initial_capital=Decimal("1000"))
        
        assert len(curve) >= 3
        for i in range(1, len(curve)):
            assert curve[i].timestamp >= curve[i-1].timestamp

    def test_equity_curve_values(self):
        """Equity curve reflects cumulative P&L."""
        trades = [
            {"pnl": Decimal("100"), "closed_at": datetime(2024, 1, 1, 10, 0)},
            {"pnl": Decimal("-30"), "closed_at": datetime(2024, 1, 1, 12, 0)},
        ]
        service = AnalyticsService()
        curve = service.generate_equity_curve(trades, initial_capital=Decimal("1000"))
        
        # After first trade: 1100
        # After second trade: 1070
        assert curve[-1].equity == Decimal("1070")

    def test_equity_curve_with_no_trades(self):
        """Equity curve with no trades returns initial capital."""
        service = AnalyticsService()
        curve = service.generate_equity_curve([], initial_capital=Decimal("1000"))
        
        assert len(curve) == 1
        assert curve[0].equity == Decimal("1000")


class TestDailyPnL:
    """Tests for daily P&L aggregation."""

    def test_daily_pnl_aggregation(self):
        """P&L aggregated by day."""
        trades = [
            {"pnl": Decimal("100"), "closed_at": datetime(2024, 1, 1, 10, 0)},
            {"pnl": Decimal("50"), "closed_at": datetime(2024, 1, 1, 14, 0)},
            {"pnl": Decimal("-30"), "closed_at": datetime(2024, 1, 2, 10, 0)},
        ]
        service = AnalyticsService()
        daily = service.get_daily_pnl(trades)
        
        assert len(daily) == 2
        day1 = next(d for d in daily if d.date.day == 1)
        day2 = next(d for d in daily if d.date.day == 2)
        assert day1.pnl == Decimal("150")
        assert day2.pnl == Decimal("-30")

    def test_daily_trade_count(self):
        """Trade count per day calculated."""
        trades = [
            {"pnl": Decimal("100"), "closed_at": datetime(2024, 1, 1, 10, 0)},
            {"pnl": Decimal("50"), "closed_at": datetime(2024, 1, 1, 14, 0)},
            {"pnl": Decimal("25"), "closed_at": datetime(2024, 1, 1, 16, 0)},
            {"pnl": Decimal("-30"), "closed_at": datetime(2024, 1, 2, 10, 0)},
        ]
        service = AnalyticsService()
        daily = service.get_daily_pnl(trades)
        
        day1 = next(d for d in daily if d.date.day == 1)
        day2 = next(d for d in daily if d.date.day == 2)
        assert day1.trades == 3
        assert day2.trades == 1


class TestROICalculation:
    """Tests for ROI calculation."""

    def test_roi_positive(self):
        """Positive ROI calculated correctly."""
        trades = [{"pnl": Decimal("200"), "is_win": True}]
        service = AnalyticsService()
        metrics = service.calculate_metrics(trades, initial_capital=Decimal("1000"))
        assert metrics.roi_pct == Decimal("20")  # 200/1000 * 100

    def test_roi_negative(self):
        """Negative ROI calculated correctly."""
        trades = [{"pnl": Decimal("-100"), "is_win": False}]
        service = AnalyticsService()
        metrics = service.calculate_metrics(trades, initial_capital=Decimal("1000"))
        assert metrics.roi_pct == Decimal("-10")  # -100/1000 * 100

    def test_roi_with_zero_capital(self):
        """ROI handles zero initial capital gracefully."""
        trades = [{"pnl": Decimal("100"), "is_win": True}]
        service = AnalyticsService()
        metrics = service.calculate_metrics(trades, initial_capital=Decimal("0"))
        # Should handle gracefully, not crash
        assert metrics is not None


class TestEmptyData:
    """Tests for handling empty data."""

    def test_metrics_with_no_trades(self):
        """Metrics calculation with empty trades list."""
        service = AnalyticsService()
        metrics = service.calculate_metrics([])
        
        assert metrics.total_trades == 0
        assert metrics.win_rate == Decimal("0")
        assert metrics.total_pnl == Decimal("0")

    def test_sport_breakdown_no_trades(self):
        """Sport breakdown with empty trades list."""
        service = AnalyticsService()
        breakdown = service.get_sport_breakdown([])
        
        assert len(breakdown) == 0

    def test_daily_pnl_no_trades(self):
        """Daily P&L with empty trades list."""
        service = AnalyticsService()
        daily = service.get_daily_pnl([])
        
        assert len(daily) == 0
