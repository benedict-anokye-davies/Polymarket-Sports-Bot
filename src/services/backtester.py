"""
Backtester service - replays historical price data to simulate trading strategies.
Uses stored price snapshots to evaluate strategy performance.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Callable, Any
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@dataclass
class BacktestConfig:
    """Configuration for a backtest run."""
    start_date: datetime
    end_date: datetime
    initial_capital: float = 1000.0
    entry_threshold_drop_pct: float = 0.05
    exit_take_profit_pct: float = 0.10
    exit_stop_loss_pct: float = 0.08
    max_position_size_pct: float = 0.20
    max_concurrent_positions: int = 5
    min_confidence_score: float = 0.6
    use_kelly_sizing: bool = False
    kelly_fraction: float = 0.25
    sport_filter: Optional[str] = None


@dataclass
class BacktestTrade:
    """Single simulated trade in backtest."""
    token_id: str
    entry_time: datetime
    entry_price: float
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    contracts: int = 0
    pnl: float = 0.0
    exit_reason: str = ""


@dataclass
class BacktestSummary:
    """Summary statistics from backtest."""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    total_pnl: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: Optional[float] = None
    profit_factor: float = 0.0
    avg_trade_pnl: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    max_concurrent_positions_reached: int = 0
    final_capital: float = 0.0
    roi_pct: float = 0.0


@dataclass
class BacktestState:
    """Internal state during backtest execution."""
    capital: float = 1000.0
    positions: dict = field(default_factory=dict)
    completed_trades: list = field(default_factory=list)
    equity_curve: list = field(default_factory=list)
    peak_capital: float = 1000.0
    max_drawdown: float = 0.0


class Backtester:
    """
    Simulates trading strategies using historical price data.
    
    Process:
    1. Load price snapshots for date range
    2. Iterate through snapshots chronologically
    3. Apply entry/exit logic at each timestamp
    4. Track positions, P&L, and equity curve
    5. Generate summary statistics
    """
    
    def __init__(self, db: AsyncSession, user_id: UUID):
        self.db = db
        self.user_id = user_id
        self._running = False
        self._progress_callback: Optional[Callable] = None
    
    async def run_backtest(
        self,
        config: BacktestConfig,
        progress_callback: Optional[Callable[[float, str], Any]] = None,
    ) -> tuple[BacktestSummary, list[BacktestTrade], list[dict]]:
        """
        Execute a backtest with the given configuration.
        
        Args:
            config: Backtest configuration parameters
            progress_callback: Optional callback(progress_pct, status_msg)
        
        Returns:
            Tuple of (summary, trades, equity_curve)
        """
        self._running = True
        self._progress_callback = progress_callback
        
        try:
            await self._report_progress(0, "Loading price data...")
            
            snapshots = await self._load_snapshots(config)
            
            if not snapshots:
                logger.warning("No price snapshots found for backtest period")
                return BacktestSummary(), [], []
            
            await self._report_progress(10, f"Loaded {len(snapshots)} snapshots")
            
            state = BacktestState(capital=config.initial_capital)
            state.peak_capital = config.initial_capital
            
            baselines = await self._load_baselines(config)
            
            total_snapshots = len(snapshots)
            
            for i, snapshot in enumerate(snapshots):
                if not self._running:
                    break
                
                await self._process_snapshot(snapshot, state, config, baselines)
                
                if i % 100 == 0:
                    progress = 10 + (80 * (i / total_snapshots))
                    await self._report_progress(progress, f"Processing {i}/{total_snapshots}")
            
            await self._report_progress(90, "Closing remaining positions...")
            
            final_price = snapshots[-1].price if snapshots else Decimal("0.5")
            for token_id in list(state.positions.keys()):
                await self._close_position(
                    state, token_id, float(final_price),
                    snapshots[-1].captured_at, "backtest_end"
                )
            
            await self._report_progress(95, "Calculating statistics...")
            
            summary = self._calculate_summary(state, config)
            
            await self._report_progress(100, "Backtest complete")
            
            return summary, state.completed_trades, state.equity_curve
            
        finally:
            self._running = False
    
    async def _load_snapshots(self, config: BacktestConfig) -> list:
        """Load price snapshots for the backtest period."""
        from src.models import PriceSnapshot
        
        query = (
            select(PriceSnapshot)
            .where(
                and_(
                    PriceSnapshot.user_id == self.user_id,
                    PriceSnapshot.captured_at >= config.start_date,
                    PriceSnapshot.captured_at <= config.end_date,
                )
            )
            .order_by(PriceSnapshot.captured_at.asc())
        )
        
        if config.sport_filter:
            query = query.where(PriceSnapshot.sport == config.sport_filter)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def _load_baselines(self, config: BacktestConfig) -> dict:
        """
        Load baseline prices for markets in the period.
        Returns dict mapping condition_id to baseline price.
        """
        from src.models import TrackedMarket
        
        query = (
            select(TrackedMarket)
            .where(TrackedMarket.user_id == self.user_id)
        )
        
        result = await self.db.execute(query)
        markets = result.scalars().all()
        
        return {
            m.condition_id: float(m.baseline_price_yes)
            for m in markets
            if m.baseline_price_yes
        }
    
    async def _process_snapshot(
        self,
        snapshot,
        state: BacktestState,
        config: BacktestConfig,
        baselines: dict,
    ) -> None:
        """Process a single price snapshot - check exits then entries."""
        current_price = float(snapshot.price)
        token_id = snapshot.token_id
        timestamp = snapshot.captured_at
        
        if token_id in state.positions:
            position = state.positions[token_id]
            
            profit_pct = (current_price - position.entry_price) / position.entry_price
            
            if profit_pct >= config.exit_take_profit_pct:
                await self._close_position(
                    state, token_id, current_price, timestamp, "take_profit"
                )
            elif profit_pct <= -config.exit_stop_loss_pct:
                await self._close_position(
                    state, token_id, current_price, timestamp, "stop_loss"
                )
        
        if token_id not in state.positions:
            if len(state.positions) >= config.max_concurrent_positions:
                return
            
            baseline = baselines.get(snapshot.condition_id)
            if not baseline:
                return
            
            drop_pct = (baseline - current_price) / baseline
            
            if drop_pct >= config.entry_threshold_drop_pct:
                await self._open_position(
                    state, snapshot, current_price, timestamp, config
                )
        
        self._update_equity(state, timestamp)
    
    async def _open_position(
        self,
        state: BacktestState,
        snapshot,
        price: float,
        timestamp: datetime,
        config: BacktestConfig,
    ) -> None:
        """Open a new simulated position."""
        position_size = state.capital * config.max_position_size_pct
        contracts = int(position_size / price)
        
        if contracts <= 0:
            return
        
        cost = contracts * price
        if cost > state.capital:
            contracts = int(state.capital / price)
            cost = contracts * price
        
        state.capital -= cost
        
        trade = BacktestTrade(
            token_id=snapshot.token_id,
            entry_time=timestamp,
            entry_price=price,
            contracts=contracts,
        )
        
        state.positions[snapshot.token_id] = trade
        
        logger.debug(f"Backtest: Opened {contracts} @ {price:.4f}")
    
    async def _close_position(
        self,
        state: BacktestState,
        token_id: str,
        price: float,
        timestamp: datetime,
        reason: str,
    ) -> None:
        """Close a simulated position."""
        if token_id not in state.positions:
            return
        
        trade = state.positions[token_id]
        trade.exit_time = timestamp
        trade.exit_price = price
        trade.exit_reason = reason
        
        pnl = (price - trade.entry_price) * trade.contracts
        trade.pnl = pnl
        
        proceeds = trade.contracts * price
        state.capital += proceeds
        
        state.completed_trades.append(trade)
        del state.positions[token_id]
        
        logger.debug(f"Backtest: Closed @ {price:.4f}, PnL: {pnl:.2f} ({reason})")
    
    def _update_equity(self, state: BacktestState, timestamp: datetime) -> None:
        """Update equity curve and drawdown tracking."""
        position_value = sum(
            p.contracts * p.entry_price
            for p in state.positions.values()
        )
        
        total_equity = state.capital + position_value
        
        state.peak_capital = max(state.peak_capital, total_equity)
        drawdown = (state.peak_capital - total_equity) / state.peak_capital if state.peak_capital > 0 else 0
        state.max_drawdown = max(state.max_drawdown, drawdown)
        
        state.equity_curve.append({
            "timestamp": timestamp.isoformat(),
            "equity": round(total_equity, 2),
            "drawdown_pct": round(drawdown * 100, 2),
        })
    
    def _calculate_summary(
        self,
        state: BacktestState,
        config: BacktestConfig,
    ) -> BacktestSummary:
        """Calculate final backtest statistics."""
        trades = state.completed_trades
        
        if not trades:
            return BacktestSummary(final_capital=state.capital)
        
        winning = [t for t in trades if t.pnl > 0]
        losing = [t for t in trades if t.pnl <= 0]
        
        total_pnl = sum(t.pnl for t in trades)
        gross_profit = sum(t.pnl for t in winning)
        gross_loss = abs(sum(t.pnl for t in losing))
        
        win_rate = len(winning) / len(trades) if trades else 0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")
        
        avg_win = gross_profit / len(winning) if winning else 0
        avg_loss = gross_loss / len(losing) if losing else 0
        
        returns = [t.pnl for t in trades]
        avg_return = sum(returns) / len(returns)
        variance = sum((r - avg_return) ** 2 for r in returns) / len(returns)
        std_dev = variance ** 0.5 if variance > 0 else 0
        sharpe = (avg_return / std_dev) * (252 ** 0.5) if std_dev > 0 else None
        
        roi = ((state.capital - config.initial_capital) / config.initial_capital) * 100
        
        return BacktestSummary(
            total_trades=len(trades),
            winning_trades=len(winning),
            losing_trades=len(losing),
            win_rate=round(win_rate, 4),
            total_pnl=round(total_pnl, 2),
            max_drawdown=round(state.max_drawdown * 100, 2),
            sharpe_ratio=round(sharpe, 2) if sharpe else None,
            profit_factor=round(profit_factor, 2) if profit_factor != float("inf") else 999.99,
            avg_trade_pnl=round(total_pnl / len(trades), 2),
            avg_win=round(avg_win, 2),
            avg_loss=round(avg_loss, 2),
            max_concurrent_positions_reached=config.max_concurrent_positions,
            final_capital=round(state.capital, 2),
            roi_pct=round(roi, 2),
        )
    
    async def _report_progress(self, progress: float, message: str) -> None:
        """Report progress via callback if configured."""
        if self._progress_callback:
            try:
                await self._progress_callback(progress, message)
            except Exception as e:
                logger.warning(f"Progress callback error: {e}")
    
    def stop(self) -> None:
        """Stop a running backtest."""
        self._running = False
    
    async def save_result(
        self,
        config: BacktestConfig,
        summary: BacktestSummary,
        trades: list[BacktestTrade],
        equity_curve: list[dict],
        name: Optional[str] = None,
    ) -> UUID:
        """
        Save backtest results to database.
        
        Returns:
            UUID of saved BacktestResult
        """
        from src.models import BacktestResult
        import dataclasses
        
        config_dict = dataclasses.asdict(config)
        config_dict["start_date"] = config.start_date.isoformat()
        config_dict["end_date"] = config.end_date.isoformat()
        
        summary_dict = dataclasses.asdict(summary)
        
        trades_list = [
            {
                "token_id": t.token_id,
                "entry_time": t.entry_time.isoformat() if t.entry_time else None,
                "entry_price": t.entry_price,
                "exit_time": t.exit_time.isoformat() if t.exit_time else None,
                "exit_price": t.exit_price,
                "contracts": t.contracts,
                "pnl": t.pnl,
                "exit_reason": t.exit_reason,
            }
            for t in trades
        ]
        
        result = BacktestResult(
            user_id=self.user_id,
            name=name or f"Backtest {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}",
            config=config_dict,
            result_summary=summary_dict,
            trades=trades_list,
            equity_curve=equity_curve,
            status="completed",
            started_at=config.start_date,
            completed_at=datetime.now(timezone.utc),
        )
        
        self.db.add(result)
        await self.db.commit()
        await self.db.refresh(result)
        
        return result.id
