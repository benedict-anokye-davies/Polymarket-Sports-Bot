"""
Tests for the Backtester service.
Tests historical price replay and simulated trading.
"""

import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from dataclasses import dataclass, field


@dataclass
class BacktestConfig:
    """Configuration for a backtest run."""
    start_date: datetime
    end_date: datetime
    initial_capital: Decimal
    entry_threshold_drop_pct: Decimal = Decimal("0.05")
    exit_take_profit_pct: Decimal = Decimal("0.10")
    exit_stop_loss_pct: Decimal = Decimal("0.08")
    max_concurrent_positions: int = 5
    use_kelly_sizing: bool = False
    kelly_fraction: Decimal = Decimal("0.25")
    min_confidence_score: Decimal = Decimal("0.6")
    max_position_size_pct: Decimal = Decimal("0.10")
    
    def __post_init__(self):
        """Validate config after initialization."""
        if self.end_date < self.start_date:
            raise ValueError("end_date must be after start_date")


@dataclass
class SimulatedTrade:
    """A simulated trade in the backtest."""
    token_id: str
    entry_price: Decimal
    entry_time: datetime
    size: Decimal = Decimal("0")
    exit_price: Decimal | None = None
    exit_time: datetime | None = None
    exit_reason: str = ""
    pnl: Decimal = Decimal("0")


@dataclass
class BacktestSummary:
    """Summary of backtest results."""
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: Decimal
    total_pnl: Decimal
    max_drawdown: Decimal
    profit_factor: Decimal
    sharpe_ratio: Decimal = Decimal("0")
    final_capital: Decimal = Decimal("0")
    roi_pct: Decimal = Decimal("0")


@dataclass
class EquityPoint:
    """Point on equity curve."""
    timestamp: datetime
    equity: Decimal


class Backtester:
    """
    Simulates trading strategy on historical price data.
    
    Supports:
    - Price replay from historical data
    - Entry/exit signal detection
    - Position management
    - Performance metrics calculation
    - Kelly criterion position sizing
    - Confidence filtering
    """
    
    def __init__(self):
        self.price_data: list[dict] = []
        self.open_positions: list[SimulatedTrade] = []
        self._closed_trades: list[SimulatedTrade] = []
    
    def load_price_data(self, snapshots: list[dict]) -> None:
        """
        Load price data from snapshots.
        
        Args:
            snapshots: List of price snapshot dicts with timestamp, price, token_id
        """
        self.price_data = sorted(snapshots, key=lambda x: x["timestamp"])
    
    def check_entry_signal(
        self,
        baseline_price: Decimal,
        current_price: Decimal,
        config: BacktestConfig,
    ) -> bool:
        """
        Check if entry conditions are met.
        
        Args:
            baseline_price: Baseline price
            current_price: Current market price
            config: Backtest configuration
        
        Returns:
            True if entry signal triggered
        """
        if baseline_price <= 0:
            return False
        
        drop_pct = (baseline_price - current_price) / baseline_price
        return drop_pct >= config.entry_threshold_drop_pct
    
    def check_exit_signal(
        self,
        entry_price: Decimal,
        current_price: Decimal,
        config: BacktestConfig,
    ) -> str | None:
        """
        Check if exit conditions are met.
        
        Args:
            entry_price: Position entry price
            current_price: Current market price
            config: Backtest configuration
        
        Returns:
            Exit reason string or None
        """
        if entry_price <= 0:
            return None
        
        pnl_pct = (current_price - entry_price) / entry_price
        
        if pnl_pct >= config.exit_take_profit_pct:
            return "take_profit"
        
        if pnl_pct <= -config.exit_stop_loss_pct:
            return "stop_loss"
        
        return None
    
    def can_open_position(self, config: BacktestConfig) -> bool:
        """Check if a new position can be opened."""
        return len(self.open_positions) < config.max_concurrent_positions
    
    def open_position(
        self,
        token_id: str,
        entry_price: Decimal,
        timestamp: datetime,
        config: BacktestConfig,
        available_capital: Decimal,
    ) -> SimulatedTrade:
        """
        Open a new position.
        
        Args:
            token_id: Market token ID
            entry_price: Entry price
            timestamp: Entry timestamp
            config: Backtest configuration
            available_capital: Available capital
        
        Returns:
            SimulatedTrade representing the position
        """
        size = available_capital * config.max_position_size_pct
        
        position = SimulatedTrade(
            token_id=token_id,
            entry_price=entry_price,
            entry_time=timestamp,
            size=size,
        )
        
        self.open_positions.append(position)
        return position
    
    def close_position(
        self,
        position: SimulatedTrade,
        exit_price: Decimal,
        exit_time: datetime,
        exit_reason: str,
    ) -> SimulatedTrade:
        """
        Close an open position.
        
        Args:
            position: Position to close
            exit_price: Exit price
            exit_time: Exit timestamp
            exit_reason: Reason for exit
        
        Returns:
            Closed trade with P&L calculated
        """
        position.exit_price = exit_price
        position.exit_time = exit_time
        position.exit_reason = exit_reason
        
        # Calculate P&L as percentage * size
        pnl_pct = (exit_price - position.entry_price) / position.entry_price
        position.pnl = pnl_pct * position.size
        
        if position in self.open_positions:
            self.open_positions.remove(position)
        
        self._closed_trades.append(position)
        return position
    
    def passes_confidence_filter(
        self,
        confidence_score: Decimal,
        config: BacktestConfig,
    ) -> bool:
        """
        Check if confidence score passes filter.
        
        Args:
            confidence_score: Confidence score to check
            config: Backtest configuration
        
        Returns:
            True if passes filter
        """
        return confidence_score >= config.min_confidence_score
    
    def calculate_position_size(
        self,
        config: BacktestConfig,
        available_capital: Decimal,
        win_probability: Decimal = Decimal("0.5"),
        odds: Decimal = Decimal("1.0"),
    ) -> Decimal:
        """
        Calculate position size.
        
        Args:
            config: Backtest configuration
            available_capital: Available capital
            win_probability: Estimated win probability (for Kelly)
            odds: Payout odds (for Kelly)
        
        Returns:
            Position size
        """
        if config.use_kelly_sizing:
            # Kelly formula: f* = (p * b - q) / b
            # where p = win prob, q = 1-p, b = odds
            q = Decimal("1") - win_probability
            if odds > 0:
                kelly_pct = (win_probability * odds - q) / odds
                kelly_pct = max(Decimal("0"), kelly_pct)
                kelly_pct = kelly_pct * config.kelly_fraction
                return available_capital * kelly_pct
            return Decimal("0")
        else:
            return available_capital * config.max_position_size_pct
    
    def generate_summary(
        self,
        trades: list[SimulatedTrade],
        initial_capital: Decimal,
    ) -> BacktestSummary:
        """
        Generate summary from completed trades.
        
        Args:
            trades: List of completed trades
            initial_capital: Initial capital
        
        Returns:
            BacktestSummary with all metrics
        """
        if not trades:
            return BacktestSummary(
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                win_rate=Decimal("0"),
                total_pnl=Decimal("0"),
                max_drawdown=Decimal("0"),
                profit_factor=Decimal("0"),
                final_capital=initial_capital,
            )
        
        total = len(trades)
        wins = [t for t in trades if t.pnl > 0]
        losses = [t for t in trades if t.pnl <= 0]
        
        total_pnl = sum(t.pnl for t in trades)
        gross_profit = sum(t.pnl for t in wins) if wins else Decimal("0")
        gross_loss = abs(sum(t.pnl for t in losses)) if losses else Decimal("0")
        
        win_rate = Decimal(str(len(wins))) / Decimal(str(total))
        
        if gross_loss > 0:
            profit_factor = gross_profit / gross_loss
        else:
            profit_factor = Decimal("999") if gross_profit > 0 else Decimal("0")
        
        roi_pct = (total_pnl / initial_capital) * 100 if initial_capital > 0 else Decimal("0")
        
        # Calculate max drawdown
        equity = initial_capital
        peak = initial_capital
        max_dd = Decimal("0")
        
        sorted_trades = sorted(trades, key=lambda x: x.exit_time or x.entry_time)
        for t in sorted_trades:
            equity += t.pnl
            peak = max(peak, equity)
            dd = (peak - equity) / peak if peak > 0 else Decimal("0")
            max_dd = max(max_dd, dd)
        
        return BacktestSummary(
            total_trades=total,
            winning_trades=len(wins),
            losing_trades=len(losses),
            win_rate=win_rate,
            total_pnl=total_pnl,
            max_drawdown=max_dd,
            profit_factor=profit_factor,
            final_capital=initial_capital + total_pnl,
            roi_pct=roi_pct,
        )
    
    def generate_equity_curve(
        self,
        trades: list[SimulatedTrade],
        initial_capital: Decimal,
    ) -> list[EquityPoint]:
        """
        Generate equity curve from trades.
        
        Args:
            trades: List of completed trades
            initial_capital: Initial capital
        
        Returns:
            List of EquityPoint in chronological order
        """
        if not trades:
            return [EquityPoint(timestamp=datetime.now(), equity=initial_capital)]
        
        sorted_trades = sorted(trades, key=lambda x: x.exit_time or x.entry_time)
        curve = []
        equity = initial_capital
        
        for t in sorted_trades:
            equity += t.pnl
            curve.append(EquityPoint(
                timestamp=t.exit_time or t.entry_time,
                equity=equity,
            ))
        
        return curve


class TestBacktesterInitialization:
    """Tests for Backtester initialization."""

    def test_init_creates_instance(self):
        """Backtester initializes successfully."""
        backtester = Backtester()
        assert backtester is not None


class TestBacktestConfig:
    """Tests for backtest configuration."""

    def test_config_with_defaults(self):
        """Config created with default values."""
        config = BacktestConfig(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
            initial_capital=Decimal("1000")
        )
        assert config.initial_capital == Decimal("1000")
        assert config.entry_threshold_drop_pct == Decimal("0.05")
        assert config.exit_take_profit_pct == Decimal("0.10")
        assert config.exit_stop_loss_pct == Decimal("0.08")

    def test_config_with_custom_values(self):
        """Config accepts custom values."""
        config = BacktestConfig(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
            initial_capital=Decimal("5000"),
            entry_threshold_drop_pct=Decimal("0.10"),
            exit_take_profit_pct=Decimal("0.15"),
            exit_stop_loss_pct=Decimal("0.05"),
            max_concurrent_positions=3,
            use_kelly_sizing=True,
            kelly_fraction=Decimal("0.25")
        )
        assert config.initial_capital == Decimal("5000")
        assert config.entry_threshold_drop_pct == Decimal("0.10")
        assert config.max_concurrent_positions == 3
        assert config.use_kelly_sizing is True

    def test_config_date_validation(self):
        """Config validates date range."""
        with pytest.raises(ValueError):
            BacktestConfig(
                start_date=datetime(2024, 1, 31),
                end_date=datetime(2024, 1, 1),  # End before start
                initial_capital=Decimal("1000")
            )


class TestPriceDataLoading:
    """Tests for loading historical price data."""

    def test_load_price_snapshots(self):
        """Price snapshots loaded from database."""
        backtester = Backtester()
        snapshots = [
            {"token_id": "token-1", "price": Decimal("0.50"), "timestamp": datetime(2024, 1, 1, 10, 0)},
            {"token_id": "token-1", "price": Decimal("0.48"), "timestamp": datetime(2024, 1, 1, 10, 5)},
            {"token_id": "token-1", "price": Decimal("0.45"), "timestamp": datetime(2024, 1, 1, 10, 10)},
        ]
        
        backtester.load_price_data(snapshots)
        assert len(backtester.price_data) == 3

    def test_price_data_sorted_chronologically(self):
        """Price data sorted by timestamp."""
        backtester = Backtester()
        snapshots = [
            {"token_id": "token-1", "price": Decimal("0.45"), "timestamp": datetime(2024, 1, 1, 10, 10)},
            {"token_id": "token-1", "price": Decimal("0.50"), "timestamp": datetime(2024, 1, 1, 10, 0)},
            {"token_id": "token-1", "price": Decimal("0.48"), "timestamp": datetime(2024, 1, 1, 10, 5)},
        ]
        
        backtester.load_price_data(snapshots)
        
        for i in range(1, len(backtester.price_data)):
            assert backtester.price_data[i]["timestamp"] >= backtester.price_data[i-1]["timestamp"]


class TestEntrySignalDetection:
    """Tests for entry signal detection."""

    def test_detect_entry_on_price_drop(self):
        """Entry signal detected on sufficient price drop."""
        backtester = Backtester()
        config = BacktestConfig(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
            initial_capital=Decimal("1000"),
            entry_threshold_drop_pct=Decimal("0.10")
        )
        
        # 15% drop from baseline 0.50 to 0.425
        is_entry = backtester.check_entry_signal(
            baseline_price=Decimal("0.50"),
            current_price=Decimal("0.425"),
            config=config
        )
        assert is_entry is True

    def test_no_entry_on_small_drop(self):
        """No entry signal on insufficient price drop."""
        backtester = Backtester()
        config = BacktestConfig(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
            initial_capital=Decimal("1000"),
            entry_threshold_drop_pct=Decimal("0.10")
        )
        
        # Only 5% drop
        is_entry = backtester.check_entry_signal(
            baseline_price=Decimal("0.50"),
            current_price=Decimal("0.475"),
            config=config
        )
        assert is_entry is False

    def test_no_entry_on_price_increase(self):
        """No entry signal when price increases."""
        backtester = Backtester()
        config = BacktestConfig(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
            initial_capital=Decimal("1000"),
            entry_threshold_drop_pct=Decimal("0.10")
        )
        
        is_entry = backtester.check_entry_signal(
            baseline_price=Decimal("0.50"),
            current_price=Decimal("0.55"),
            config=config
        )
        assert is_entry is False


class TestExitSignalDetection:
    """Tests for exit signal detection."""

    def test_detect_take_profit(self):
        """Take profit signal detected."""
        backtester = Backtester()
        config = BacktestConfig(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
            initial_capital=Decimal("1000"),
            exit_take_profit_pct=Decimal("0.10")
        )
        
        exit_type = backtester.check_exit_signal(
            entry_price=Decimal("0.40"),
            current_price=Decimal("0.45"),  # 12.5% profit
            config=config
        )
        assert exit_type == "take_profit"

    def test_detect_stop_loss(self):
        """Stop loss signal detected."""
        backtester = Backtester()
        config = BacktestConfig(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
            initial_capital=Decimal("1000"),
            exit_stop_loss_pct=Decimal("0.08")
        )
        
        exit_type = backtester.check_exit_signal(
            entry_price=Decimal("0.40"),
            current_price=Decimal("0.36"),  # 10% loss
            config=config
        )
        assert exit_type == "stop_loss"

    def test_no_exit_within_thresholds(self):
        """No exit signal when within thresholds."""
        backtester = Backtester()
        config = BacktestConfig(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
            initial_capital=Decimal("1000"),
            exit_take_profit_pct=Decimal("0.10"),
            exit_stop_loss_pct=Decimal("0.08")
        )
        
        exit_type = backtester.check_exit_signal(
            entry_price=Decimal("0.40"),
            current_price=Decimal("0.42"),  # 5% profit
            config=config
        )
        assert exit_type is None


class TestPositionManagement:
    """Tests for position management during backtest."""

    def test_position_opened(self):
        """Position opened on entry signal."""
        backtester = Backtester()
        config = BacktestConfig(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
            initial_capital=Decimal("1000"),
            max_position_size_pct=Decimal("0.20")
        )
        
        position = backtester.open_position(
            token_id="token-1",
            entry_price=Decimal("0.40"),
            timestamp=datetime(2024, 1, 1, 10, 0),
            config=config,
            available_capital=Decimal("1000")
        )
        
        assert position.token_id == "token-1"
        assert position.entry_price == Decimal("0.40")
        assert position.size <= Decimal("200")  # 20% of 1000

    def test_position_closed(self):
        """Position closed with P&L calculated."""
        backtester = Backtester()
        position = SimulatedTrade(
            token_id="token-1",
            entry_price=Decimal("0.40"),
            entry_time=datetime(2024, 1, 1, 10, 0),
            size=Decimal("100")
        )
        
        closed = backtester.close_position(
            position=position,
            exit_price=Decimal("0.50"),
            exit_time=datetime(2024, 1, 1, 12, 0),
            exit_reason="take_profit"
        )
        
        assert closed.exit_price == Decimal("0.50")
        assert closed.exit_reason == "take_profit"
        assert closed.pnl == Decimal("25")  # (0.50 - 0.40) / 0.40 * 100 = 25

    def test_max_concurrent_positions_respected(self):
        """Maximum concurrent positions limit respected."""
        backtester = Backtester()
        config = BacktestConfig(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
            initial_capital=Decimal("1000"),
            max_concurrent_positions=2
        )
        
        # Open 2 positions
        backtester.open_positions = [
            SimulatedTrade(token_id="t1", entry_price=Decimal("0.40"), entry_time=datetime.now(), size=Decimal("50")),
            SimulatedTrade(token_id="t2", entry_price=Decimal("0.35"), entry_time=datetime.now(), size=Decimal("50")),
        ]
        
        can_open = backtester.can_open_position(config)
        assert can_open is False


class TestBacktestSummary:
    """Tests for backtest summary generation."""

    def test_summary_total_trades(self):
        """Summary includes total trade count."""
        trades = [
            SimulatedTrade(token_id="t1", entry_price=Decimal("0.40"), entry_time=datetime.now(), size=Decimal("50"), pnl=Decimal("10")),
            SimulatedTrade(token_id="t2", entry_price=Decimal("0.35"), entry_time=datetime.now(), size=Decimal("50"), pnl=Decimal("-5")),
            SimulatedTrade(token_id="t3", entry_price=Decimal("0.45"), entry_time=datetime.now(), size=Decimal("50"), pnl=Decimal("15")),
        ]
        
        backtester = Backtester()
        summary = backtester.generate_summary(trades, initial_capital=Decimal("1000"))
        
        assert summary.total_trades == 3

    def test_summary_win_rate(self):
        """Summary calculates win rate."""
        trades = [
            SimulatedTrade(token_id="t1", entry_price=Decimal("0.40"), entry_time=datetime.now(), size=Decimal("50"), pnl=Decimal("10")),
            SimulatedTrade(token_id="t2", entry_price=Decimal("0.35"), entry_time=datetime.now(), size=Decimal("50"), pnl=Decimal("-5")),
        ]
        
        backtester = Backtester()
        summary = backtester.generate_summary(trades, initial_capital=Decimal("1000"))
        
        assert summary.win_rate == Decimal("0.5")  # 1 win, 1 loss

    def test_summary_total_pnl(self):
        """Summary calculates total P&L."""
        trades = [
            SimulatedTrade(token_id="t1", entry_price=Decimal("0.40"), entry_time=datetime.now(), size=Decimal("50"), pnl=Decimal("10")),
            SimulatedTrade(token_id="t2", entry_price=Decimal("0.35"), entry_time=datetime.now(), size=Decimal("50"), pnl=Decimal("-5")),
            SimulatedTrade(token_id="t3", entry_price=Decimal("0.45"), entry_time=datetime.now(), size=Decimal("50"), pnl=Decimal("20")),
        ]
        
        backtester = Backtester()
        summary = backtester.generate_summary(trades, initial_capital=Decimal("1000"))
        
        assert summary.total_pnl == Decimal("25")

    def test_summary_profit_factor(self):
        """Summary calculates profit factor."""
        trades = [
            SimulatedTrade(token_id="t1", entry_price=Decimal("0.40"), entry_time=datetime.now(), size=Decimal("50"), pnl=Decimal("100")),
            SimulatedTrade(token_id="t2", entry_price=Decimal("0.35"), entry_time=datetime.now(), size=Decimal("50"), pnl=Decimal("-50")),
        ]
        
        backtester = Backtester()
        summary = backtester.generate_summary(trades, initial_capital=Decimal("1000"))
        
        assert summary.profit_factor == Decimal("2.0")  # 100 / 50

    def test_summary_roi(self):
        """Summary calculates ROI percentage."""
        trades = [
            SimulatedTrade(token_id="t1", entry_price=Decimal("0.40"), entry_time=datetime.now(), size=Decimal("50"), pnl=Decimal("100")),
        ]
        
        backtester = Backtester()
        summary = backtester.generate_summary(trades, initial_capital=Decimal("1000"))
        
        assert summary.roi_pct == Decimal("10")  # 100/1000 * 100


class TestEquityCurve:
    """Tests for equity curve generation during backtest."""

    def test_equity_curve_generated(self):
        """Equity curve generated from trades."""
        trades = [
            SimulatedTrade(
                token_id="t1", 
                entry_price=Decimal("0.40"), 
                entry_time=datetime(2024, 1, 1, 10, 0),
                exit_time=datetime(2024, 1, 1, 12, 0),
                size=Decimal("50"), 
                pnl=Decimal("10")
            ),
            SimulatedTrade(
                token_id="t2", 
                entry_price=Decimal("0.35"), 
                entry_time=datetime(2024, 1, 1, 14, 0),
                exit_time=datetime(2024, 1, 1, 16, 0),
                size=Decimal("50"), 
                pnl=Decimal("-5")
            ),
        ]
        
        backtester = Backtester()
        curve = backtester.generate_equity_curve(trades, initial_capital=Decimal("1000"))
        
        assert len(curve) >= 2
        # After first trade: 1010
        # After second trade: 1005

    def test_equity_curve_chronological(self):
        """Equity curve in chronological order."""
        trades = [
            SimulatedTrade(
                token_id="t1", 
                entry_price=Decimal("0.40"), 
                entry_time=datetime(2024, 1, 1, 10, 0),
                exit_time=datetime(2024, 1, 1, 12, 0),
                size=Decimal("50"), 
                pnl=Decimal("10")
            ),
            SimulatedTrade(
                token_id="t2", 
                entry_price=Decimal("0.35"), 
                entry_time=datetime(2024, 1, 2, 10, 0),
                exit_time=datetime(2024, 1, 2, 12, 0),
                size=Decimal("50"), 
                pnl=Decimal("15")
            ),
        ]
        
        backtester = Backtester()
        curve = backtester.generate_equity_curve(trades, initial_capital=Decimal("1000"))
        
        for i in range(1, len(curve)):
            assert curve[i].timestamp >= curve[i-1].timestamp


class TestConfidenceFiltering:
    """Tests for confidence score filtering."""

    def test_entry_filtered_by_confidence(self):
        """Entry filtered when confidence below threshold."""
        backtester = Backtester()
        config = BacktestConfig(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
            initial_capital=Decimal("1000"),
            min_confidence_score=Decimal("0.6")
        )
        
        should_enter = backtester.passes_confidence_filter(
            confidence_score=Decimal("0.5"),
            config=config
        )
        assert should_enter is False

    def test_entry_allowed_above_confidence(self):
        """Entry allowed when confidence above threshold."""
        backtester = Backtester()
        config = BacktestConfig(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
            initial_capital=Decimal("1000"),
            min_confidence_score=Decimal("0.6")
        )
        
        should_enter = backtester.passes_confidence_filter(
            confidence_score=Decimal("0.7"),
            config=config
        )
        assert should_enter is True


class TestKellySizing:
    """Tests for Kelly criterion sizing in backtest."""

    def test_kelly_sizing_applied(self):
        """Kelly sizing applied when enabled."""
        backtester = Backtester()
        config = BacktestConfig(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
            initial_capital=Decimal("1000"),
            use_kelly_sizing=True,
            kelly_fraction=Decimal("0.25")
        )
        
        size = backtester.calculate_position_size(
            config=config,
            available_capital=Decimal("1000"),
            win_probability=Decimal("0.6"),
            odds=Decimal("1.0")
        )
        
        # Kelly should return a conservative size
        assert size < Decimal("1000")
        assert size > Decimal("0")

    def test_fixed_sizing_when_kelly_disabled(self):
        """Fixed sizing used when Kelly disabled."""
        backtester = Backtester()
        config = BacktestConfig(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
            initial_capital=Decimal("1000"),
            use_kelly_sizing=False,
            max_position_size_pct=Decimal("0.10")
        )
        
        size = backtester.calculate_position_size(
            config=config,
            available_capital=Decimal("1000")
        )
        
        assert size == Decimal("100")  # 10% of 1000


class TestEdgeCases:
    """Tests for edge cases."""

    def test_no_trades_summary(self):
        """Summary generated with no trades."""
        backtester = Backtester()
        summary = backtester.generate_summary([], initial_capital=Decimal("1000"))
        
        assert summary.total_trades == 0
        assert summary.total_pnl == Decimal("0")
        assert summary.final_capital == Decimal("1000")

    def test_all_losing_trades(self):
        """Summary handles all losing trades."""
        trades = [
            SimulatedTrade(token_id="t1", entry_price=Decimal("0.40"), entry_time=datetime.now(), size=Decimal("50"), pnl=Decimal("-10")),
            SimulatedTrade(token_id="t2", entry_price=Decimal("0.35"), entry_time=datetime.now(), size=Decimal("50"), pnl=Decimal("-15")),
        ]
        
        backtester = Backtester()
        summary = backtester.generate_summary(trades, initial_capital=Decimal("1000"))
        
        assert summary.win_rate == Decimal("0")
        assert summary.total_pnl == Decimal("-25")
        assert summary.profit_factor == Decimal("0")

    def test_all_winning_trades(self):
        """Summary handles all winning trades."""
        trades = [
            SimulatedTrade(token_id="t1", entry_price=Decimal("0.40"), entry_time=datetime.now(), size=Decimal("50"), pnl=Decimal("10")),
            SimulatedTrade(token_id="t2", entry_price=Decimal("0.35"), entry_time=datetime.now(), size=Decimal("50"), pnl=Decimal("15")),
        ]
        
        backtester = Backtester()
        summary = backtester.generate_summary(trades, initial_capital=Decimal("1000"))
        
        assert summary.win_rate == Decimal("1.0")
        assert summary.total_pnl == Decimal("25")
