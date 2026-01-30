"""
Kill Switch Manager

Implements emergency stop functionality with multiple trigger conditions.
Critical safety feature for live trading.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from dataclasses import dataclass
from enum import Enum
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.crud.position import PositionCRUD
from src.db.crud.global_settings import GlobalSettingsCRUD
from src.db.crud.activity_log import ActivityLogCRUD
from src.services.discord_notifier import discord_notifier


logger = logging.getLogger(__name__)


class KillSwitchTrigger(Enum):
    """Types of kill switch triggers."""
    DAILY_LOSS_LIMIT = "daily_loss_limit"
    CONSECUTIVE_LOSSES = "consecutive_losses"
    MAX_DRAWDOWN = "max_drawdown"
    MANUAL = "manual"
    API_ERROR_RATE = "api_error_rate"
    SLIPPAGE_SPIKE = "slippage_spike"
    BALANCE_DROP = "balance_drop"
    ORPHANED_ORDERS = "orphaned_orders"


@dataclass
class KillSwitchEvent:
    """Record of a kill switch activation."""
    trigger: KillSwitchTrigger
    triggered_at: datetime
    positions_closed: int
    total_pnl: float
    reason: str
    resolved_at: Optional[datetime] = None


class KillSwitchManager:
    """
    Manages emergency kill switches for trading.
    
    Monitors multiple risk conditions and triggers emergency stop
    when thresholds are exceeded. Can optionally close all positions.
    """
    
    # Thresholds
    DEFAULT_CONSECUTIVE_LOSSES = 4  # 4 out of 5 recent trades
    DEFAULT_MAX_DRAWDOWN_PCT = 0.20  # 20% of balance
    DEFAULT_API_ERROR_THRESHOLD = 10  # 10 errors in 5 minutes
    DEFAULT_SLIPPAGE_THRESHOLD = 0.10  # 10% slippage
    
    def __init__(
        self,
        db: AsyncSession,
        user_id: UUID,
        client: Any,  # KalshiClient or PolymarketClient
    ):
        self.db = db
        self.user_id = user_id
        self.client = client
        self._active_triggers: List[KillSwitchTrigger] = []
        self._kill_switch_active = False
        self._error_counts: Dict[str, List[datetime]] = {}
    
    async def evaluate_triggers(self) -> List[KillSwitchTrigger]:
        """
        Evaluate all kill switch conditions.
        
        Returns:
            List of triggered kill switch conditions
        """
        triggered = []
        
        try:
            # Check 1: Daily loss limit
            settings = await GlobalSettingsCRUD.get_by_user_id(self.db, self.user_id)
            if settings:
                daily_pnl = await PositionCRUD.get_daily_pnl(self.db, self.user_id)
                if daily_pnl <= -settings.max_daily_loss_usdc:
                    triggered.append(KillSwitchTrigger.DAILY_LOSS_LIMIT)
                    logger.critical(
                        f"🛑 KILL SWITCH: Daily loss limit triggered. "
                        f"P&L: ${daily_pnl:.2f}, Limit: ${settings.max_daily_loss_usdc:.2f}"
                    )
            
            # Check 2: Consecutive losses
            recent_trades = await PositionCRUD.get_recent_trades(
                self.db, self.user_id, limit=5
            )
            if len(recent_trades) >= 5:
                losses = sum(1 for t in recent_trades if t.realized_pnl_usdc < 0)
                if losses >= self.DEFAULT_CONSECUTIVE_LOSSES:
                    triggered.append(KillSwitchTrigger.CONSECUTIVE_LOSSES)
                    logger.critical(
                        f"🛑 KILL SWITCH: Consecutive losses triggered. "
                        f"{losses}/5 recent trades were losses"
                    )
            
            # Check 3: Max drawdown
            balance = await self.client.get_balance()
            available = balance.get("available_balance", 0)
            # Compare to baseline (would need to track this)
            # For now, skip this check
            
            # Check 4: API error rate
            error_count = self._count_recent_errors(minutes=5)
            if error_count >= self.DEFAULT_API_ERROR_THRESHOLD:
                triggered.append(KillSwitchTrigger.API_ERROR_RATE)
                logger.critical(
                    f"🛑 KILL SWITCH: API error rate triggered. "
                    f"{error_count} errors in last 5 minutes"
                )
            
            # Check 5: Orphaned orders
            from src.services.position_reconciler import OrphanedOrderDetector
            detector = OrphanedOrderDetector(self.db, self.user_id, self.client)
            orphaned = await detector.detect_orphaned_orders()
            if orphaned:
                triggered.append(KillSwitchTrigger.ORPHANED_ORDERS)
                logger.critical(
                    f"🛑 KILL SWITCH: Orphaned orders detected. "
                    f"{len(orphaned)} untracked positions"
                )
        
        except Exception as e:
            logger.error(f"Error evaluating kill switch triggers: {e}")
        
        return triggered
    
    async def activate(
        self,
        trigger: KillSwitchTrigger,
        close_positions: bool = True,
        reason: str = ""
    ) -> KillSwitchEvent:
        """
        Activate kill switch.
        
        Args:
            trigger: What triggered the kill switch
            close_positions: Whether to close all open positions
            reason: Additional context
        
        Returns:
            KillSwitchEvent record
        """
        self._kill_switch_active = True
        self._active_triggers.append(trigger)
        
        triggered_at = datetime.now(timezone.utc)
        positions_closed = 0
        total_pnl = 0.0
        
        logger.critical(
            f"🛑 KILL SWITCH ACTIVATED: {trigger.value}\n"
            f"Reason: {reason}\n"
            f"Closing positions: {close_positions}"
        )
        
        # Send alert
        await discord_notifier.send_alert(
            title=f"🛑 KILL SWITCH ACTIVATED: {trigger.value}",
            message=f"Reason: {reason}\n"
                   f"Time: {triggered_at.isoformat()}\n"
                   f"Auto-close positions: {close_positions}",
            level="critical"
        )
        
        # Close positions if requested
        if close_positions:
            positions_closed, total_pnl = await self._close_all_positions()
        
        # Log to database
        await ActivityLogCRUD.error(
            self.db,
            self.user_id,
            "KILL_SWITCH",
            f"Kill switch activated: {trigger.value}. "
            f"Closed {positions_closed} positions, P&L: ${total_pnl:.2f}",
            details={
                "trigger": trigger.value,
                "reason": reason,
                "positions_closed": positions_closed,
                "total_pnl": total_pnl,
            }
        )
        
        event = KillSwitchEvent(
            trigger=trigger,
            triggered_at=triggered_at,
            positions_closed=positions_closed,
            total_pnl=total_pnl,
            reason=reason
        )
        
        return event
    
    async def deactivate(self, resolution_notes: str = "") -> None:
        """
        Deactivate kill switch (manual reset required).
        
        Args:
            resolution_notes: Notes about why it was deactivated
        """
        self._kill_switch_active = False
        self._active_triggers = []
        
        logger.info(f"Kill switch deactivated. Notes: {resolution_notes}")
        
        await discord_notifier.send_alert(
            title="✅ Kill Switch Deactivated",
            message=f"Trading resumed.\nNotes: {resolution_notes}",
            level="info"
        )
        
        await ActivityLogCRUD.info(
            self.db,
            self.user_id,
            "KILL_SWITCH",
            f"Kill switch deactivated. Notes: {resolution_notes}",
            details={"resolution_notes": resolution_notes}
        )
    
    async def _close_all_positions(self) -> tuple[int, float]:
        """
        Close all open positions at market price.
        
        Returns:
            Tuple of (positions_closed, total_pnl)
        """
        positions = await PositionCRUD.get_open_for_user(self.db, self.user_id)
        closed_count = 0
        total_pnl = 0.0
        
        for position in positions:
            try:
                # Get current market price
                current_price = await self._get_current_price(position)
                
                # Place exit order
                exit_size = float(position.entry_size)
                exit_proceeds = current_price * exit_size
                
                # Calculate P&L
                entry_cost = float(position.entry_price) * exit_size
                pnl = exit_proceeds - entry_cost
                total_pnl += pnl
                
                # Close position in database
                await PositionCRUD.close_position(
                    self.db,
                    position_id=position.id,
                    exit_price=current_price,
                    exit_size=exit_size,
                    exit_proceeds_usdc=exit_proceeds,
                    exit_reason="kill_switch_emergency",
                    exit_order_id="KILL_SWITCH"
                )
                
                closed_count += 1
                logger.info(f"Closed position {position.id} via kill switch. P&L: ${pnl:.2f}")
                
            except Exception as e:
                logger.error(f"Failed to close position {position.id}: {e}")
        
        return closed_count, total_pnl
    
    async def _get_current_price(self, position: Any) -> float:
        """Get current market price for a position."""
        try:
            # Try to get from client
            if hasattr(self.client, 'get_midpoint_price'):
                return await self.client.get_midpoint_price(position.token_id)
            elif hasattr(self.client, 'get_market'):
                market = await self.client.get_market(position.token_id)
                if position.side == "YES":
                    return market.yes_price
                else:
                    return market.no_price
        except Exception as e:
            logger.warning(f"Failed to get current price: {e}")
        
        # Fallback to entry price (conservative)
        return float(position.entry_price)
    
    def record_error(self, error_type: str) -> None:
        """Record an error for rate tracking."""
        now = datetime.now(timezone.utc)
        
        if error_type not in self._error_counts:
            self._error_counts[error_type] = []
        
        self._error_counts[error_type].append(now)
        
        # Clean old errors (> 5 minutes)
        cutoff = now.replace(minute=now.minute - 5)
        self._error_counts[error_type] = [
            t for t in self._error_counts[error_type] 
            if t > cutoff
        ]
    
    def _count_recent_errors(self, minutes: int = 5) -> int:
        """Count errors in the last N minutes."""
        now = datetime.now(timezone.utc)
        cutoff = now.replace(minute=now.minute - minutes)
        
        total = 0
        for error_list in self._error_counts.values():
            total += sum(1 for t in error_list if t > cutoff)
        
        return total
    
    @property
    def is_active(self) -> bool:
        """Check if kill switch is currently active."""
        return self._kill_switch_active
    
    @property
    def active_triggers(self) -> List[KillSwitchTrigger]:
        """Get list of currently active triggers."""
        return self._active_triggers.copy()


class KillSwitchMonitor:
    """
    Background monitor that periodically checks kill switch conditions.
    """
    
    def __init__(
        self,
        db: AsyncSession,
        user_id: UUID,
        client: Any,
        check_interval_seconds: int = 30
    ):
        self.db = db
        self.user_id = user_id
        self.client = client
        self.check_interval = check_interval_seconds
        self.kill_switch = KillSwitchManager(db, user_id, client)
        self._stop_event = asyncio.Event()
        self._task = None
    
    async def start(self) -> None:
        """Start monitoring."""
        self._stop_event.clear()
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info(f"Kill switch monitor started ({self.check_interval}s interval)")
    
    async def stop(self) -> None:
        """Stop monitoring."""
        self._stop_event.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Kill switch monitor stopped")
    
    async def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while not self._stop_event.is_set():
            try:
                # Check if kill switch already active
                if self.kill_switch.is_active:
                    await asyncio.sleep(self.check_interval)
                    continue
                
                # Evaluate triggers
                triggers = await self.kill_switch.evaluate_triggers()
                
                if triggers:
                    # Activate kill switch with first trigger
                    await self.kill_switch.activate(
                        trigger=triggers[0],
                        close_positions=True,
                        reason=f"Multiple triggers: {[t.value for t in triggers]}"
                    )
                
            except Exception as e:
                logger.error(f"Kill switch monitoring error: {e}")
            
            # Wait for next check
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self.check_interval
                )
            except asyncio.TimeoutError:
                pass
