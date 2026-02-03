"""
Advanced order types service for trailing stops, stop-loss, and take-profit orders.
Provides sophisticated order management beyond basic limit/market orders.
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.crud.position import PositionCRUD
from src.db.crud.activity_log import ActivityLogCRUD


logger = logging.getLogger(__name__)


class AdvancedOrderType(str, Enum):
    """Supported advanced order types."""
    TRAILING_STOP = "trailing_stop"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    OCO = "oco"  # One-cancels-other
    BRACKET = "bracket"  # Entry with TP and SL


class OrderStatus(str, Enum):
    """Order lifecycle status."""
    PENDING = "pending"
    ACTIVE = "active"
    TRIGGERED = "triggered"
    FILLED = "filled"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    FAILED = "failed"


@dataclass
class TrailingStopOrder:
    """
    Trailing stop order that follows price movement.
    Triggers when price drops by trail_pct from the highest observed price.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    position_id: str = ""
    token_id: str = ""
    condition_id: str = ""
    side: str = "SELL"  # Usually SELL to exit long positions
    size: Decimal = Decimal("0")
    trail_pct: Decimal = Decimal("0.05")  # 5% trailing distance
    trail_amount: Decimal | None = None  # Alternative: fixed dollar trail
    highest_price: Decimal = Decimal("0")
    trigger_price: Decimal = Decimal("0")
    status: OrderStatus = OrderStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    triggered_at: datetime | None = None
    filled_at: datetime | None = None
    filled_price: Decimal | None = None


@dataclass
class StopLossOrder:
    """
    Stop-loss order that triggers when price falls below threshold.
    Used to limit downside risk on open positions.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    position_id: str = ""
    token_id: str = ""
    condition_id: str = ""
    side: str = "SELL"
    size: Decimal = Decimal("0")
    stop_price: Decimal = Decimal("0")  # Trigger price
    limit_price: Decimal | None = None  # Optional limit (if None, market order)
    status: OrderStatus = OrderStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    triggered_at: datetime | None = None
    filled_at: datetime | None = None
    filled_price: Decimal | None = None


@dataclass
class TakeProfitOrder:
    """
    Take-profit order that triggers when price rises above threshold.
    Used to lock in gains at target price levels.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    position_id: str = ""
    token_id: str = ""
    condition_id: str = ""
    side: str = "SELL"
    size: Decimal = Decimal("0")
    target_price: Decimal = Decimal("0")  # Trigger price
    limit_price: Decimal | None = None  # Optional limit
    status: OrderStatus = OrderStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    triggered_at: datetime | None = None
    filled_at: datetime | None = None
    filled_price: Decimal | None = None


@dataclass
class BracketOrder:
    """
    Bracket order combining entry with take-profit and stop-loss.
    When entry fills, both TP and SL orders become active.
    When either TP or SL fills, the other is cancelled (OCO behavior).
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    token_id: str = ""
    condition_id: str = ""
    
    # Entry order
    entry_side: str = "BUY"
    entry_price: Decimal = Decimal("0")
    entry_size: Decimal = Decimal("0")
    entry_status: OrderStatus = OrderStatus.PENDING
    entry_order_id: str | None = None  # Added field to track the entry order
    entry_filled_at: datetime | None = None
    
    # Take profit (active after entry fills)
    take_profit_price: Decimal = Decimal("0")
    take_profit_status: OrderStatus = OrderStatus.PENDING
    
    # Stop loss (active after entry fills)
    stop_loss_price: Decimal = Decimal("0")
    stop_loss_status: OrderStatus = OrderStatus.PENDING
    
    # Overall bracket status
    status: OrderStatus = OrderStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    exit_reason: str | None = None  # "take_profit" or "stop_loss"


class AdvancedOrderManager:
    """
    Manages advanced order types with real-time price monitoring.
    
    Features:
    - Trailing stop orders that follow favorable price movement
    - Stop-loss orders for risk management
    - Take-profit orders for locking in gains
    - Bracket orders (entry + TP + SL in one)
    - OCO (one-cancels-other) behavior
    
    The manager runs a background loop that checks prices against
    trigger conditions and executes orders when triggered.
    """
    
    MONITOR_INTERVAL = 1.0  # Check prices every second
    
    def __init__(
        self,
        trading_client: Any,
        price_fetcher: Callable[[str], float] | None = None,
        db: AsyncSession | None = None
    ):
        """
        Initialize the advanced order manager.
        
        Args:
            trading_client: Polymarket or Kalshi client for order execution
            price_fetcher: Async function to get current price for a token
            db: Database session for position updates
        """
        self.client = trading_client
        self.price_fetcher = price_fetcher
        self.db = db
        
        # Order storage (in production, persist to database)
        self.trailing_stops: dict[str, TrailingStopOrder] = {}
        self.stop_losses: dict[str, StopLossOrder] = {}
        self.take_profits: dict[str, TakeProfitOrder] = {}
        self.brackets: dict[str, BracketOrder] = {}
        
        # Monitoring state
        self._is_running = False
        self._monitor_task: asyncio.Task | None = None
        self._callbacks: list[Callable[[str, str, dict], Any]] = []
    
    def add_callback(self, callback: Callable[[str, str, dict], Any]) -> None:
        """
        Register a callback for order events.
        
        Args:
            callback: Function(order_id, event_type, details)
        """
        self._callbacks.append(callback)
    
    async def _notify_callbacks(self, order_id: str, event: str, details: dict) -> None:
        """Notify all registered callbacks of an event."""
        for callback in self._callbacks:
            try:
                result = callback(order_id, event, details)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"Callback error: {e}")
    
    async def start(self) -> None:
        """Start the order monitoring loop."""
        if self._is_running:
            return
        
        self._is_running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Advanced order manager started")
    
    async def stop(self) -> None:
        """Stop the order monitoring loop."""
        self._is_running = False
        
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Advanced order manager stopped")
    
    # -------------------------------------------------------------------------
    # Trailing Stop Orders
    # -------------------------------------------------------------------------
    
    async def create_trailing_stop(
        self,
        user_id: str,
        position_id: str,
        token_id: str,
        condition_id: str,
        size: Decimal,
        trail_pct: Decimal,
        current_price: Decimal | None = None
    ) -> TrailingStopOrder:
        """
        Create a trailing stop order.
        
        Args:
            user_id: User ID
            position_id: Position ID to protect
            token_id: Token to monitor
            condition_id: Market condition ID
            size: Size to sell when triggered
            trail_pct: Trailing percentage (e.g., 0.05 for 5%)
            current_price: Starting price (if None, fetches current)
        
        Returns:
            Created TrailingStopOrder
        """
        if current_price is None and self.price_fetcher:
            current_price = Decimal(str(await self.price_fetcher(token_id)))
        
        order = TrailingStopOrder(
            user_id=user_id,
            position_id=position_id,
            token_id=token_id,
            condition_id=condition_id,
            size=size,
            trail_pct=trail_pct,
            highest_price=current_price or Decimal("0"),
            trigger_price=self._calculate_trail_trigger(
                current_price or Decimal("0"), trail_pct
            ),
            status=OrderStatus.ACTIVE
        )
        
        self.trailing_stops[order.id] = order
        
        logger.info(
            f"Created trailing stop: {order.id[:8]}... "
            f"trail={float(trail_pct)*100:.1f}% trigger=${float(order.trigger_price):.4f}"
        )
        
        await self._notify_callbacks(order.id, "created", {
            "type": "trailing_stop",
            "trail_pct": float(trail_pct),
            "trigger_price": float(order.trigger_price)
        })
        
        return order
    
    def _calculate_trail_trigger(
        self, highest_price: Decimal, trail_pct: Decimal
    ) -> Decimal:
        """Calculate trigger price for trailing stop."""
        return highest_price * (Decimal("1") - trail_pct)
    
    async def _update_trailing_stop(
        self, order: TrailingStopOrder, current_price: Decimal
    ) -> bool:
        """
        Update trailing stop with new price.
        
        Returns:
            True if order was triggered
        """
        # Update highest price if current is higher
        if current_price > order.highest_price:
            order.highest_price = current_price
            order.trigger_price = self._calculate_trail_trigger(
                current_price, order.trail_pct
            )
            logger.debug(
                f"Trailing stop {order.id[:8]}... updated: "
                f"high=${float(order.highest_price):.4f} trigger=${float(order.trigger_price):.4f}"
            )
        
        # Check if triggered
        if current_price <= order.trigger_price:
            order.status = OrderStatus.TRIGGERED
            order.triggered_at = datetime.now(timezone.utc)
            return True
        
        return False
    
    # -------------------------------------------------------------------------
    # Stop-Loss Orders
    # -------------------------------------------------------------------------
    
    async def create_stop_loss(
        self,
        user_id: str,
        position_id: str,
        token_id: str,
        condition_id: str,
        size: Decimal,
        stop_price: Decimal,
        limit_price: Decimal | None = None
    ) -> StopLossOrder:
        """
        Create a stop-loss order.
        
        Args:
            user_id: User ID
            position_id: Position ID to protect
            token_id: Token to monitor
            condition_id: Market condition ID
            size: Size to sell when triggered
            stop_price: Price at which to trigger
            limit_price: Optional limit price (None = market order)
        
        Returns:
            Created StopLossOrder
        """
        order = StopLossOrder(
            user_id=user_id,
            position_id=position_id,
            token_id=token_id,
            condition_id=condition_id,
            size=size,
            stop_price=stop_price,
            limit_price=limit_price,
            status=OrderStatus.ACTIVE
        )
        
        self.stop_losses[order.id] = order
        
        logger.info(
            f"Created stop-loss: {order.id[:8]}... "
            f"stop=${float(stop_price):.4f}"
        )
        
        await self._notify_callbacks(order.id, "created", {
            "type": "stop_loss",
            "stop_price": float(stop_price)
        })
        
        return order
    
    # -------------------------------------------------------------------------
    # Take-Profit Orders
    # -------------------------------------------------------------------------
    
    async def create_take_profit(
        self,
        user_id: str,
        position_id: str,
        token_id: str,
        condition_id: str,
        size: Decimal,
        target_price: Decimal,
        limit_price: Decimal | None = None
    ) -> TakeProfitOrder:
        """
        Create a take-profit order.
        
        Args:
            user_id: User ID
            position_id: Position ID
            token_id: Token to monitor
            condition_id: Market condition ID
            size: Size to sell when triggered
            target_price: Price at which to trigger
            limit_price: Optional limit price
        
        Returns:
            Created TakeProfitOrder
        """
        order = TakeProfitOrder(
            user_id=user_id,
            position_id=position_id,
            token_id=token_id,
            condition_id=condition_id,
            size=size,
            target_price=target_price,
            limit_price=limit_price,
            status=OrderStatus.ACTIVE
        )
        
        self.take_profits[order.id] = order
        
        logger.info(
            f"Created take-profit: {order.id[:8]}... "
            f"target=${float(target_price):.4f}"
        )
        
        await self._notify_callbacks(order.id, "created", {
            "type": "take_profit",
            "target_price": float(target_price)
        })
        
        return order
    
    # -------------------------------------------------------------------------
    # Bracket Orders (Entry + TP + SL)
    # -------------------------------------------------------------------------
    
    async def create_bracket_order(
        self,
        user_id: str,
        token_id: str,
        condition_id: str,
        entry_side: str,
        entry_price: Decimal,
        entry_size: Decimal,
        take_profit_price: Decimal,
        stop_loss_price: Decimal
    ) -> BracketOrder:
        """
        Create a bracket order with entry, take-profit, and stop-loss.
        
        The entry order is placed immediately. When filled, TP and SL
        orders become active. When either TP or SL fills, the other
        is cancelled (OCO behavior).
        
        Args:
            user_id: User ID
            token_id: Token to trade
            condition_id: Market condition ID
            entry_side: "BUY" or "SELL" for entry
            entry_price: Entry limit price
            entry_size: Position size
            take_profit_price: TP trigger price
            stop_loss_price: SL trigger price
        
        Returns:
            Created BracketOrder
        """
        order = BracketOrder(
            user_id=user_id,
            token_id=token_id,
            condition_id=condition_id,
            entry_side=entry_side,
            entry_price=entry_price,
            entry_size=entry_size,
            take_profit_price=take_profit_price,
            stop_loss_price=stop_loss_price,
            status=OrderStatus.PENDING
        )
        
        # Place the entry order
        try:
            entry_result = await self.client.place_order(
                token_id=token_id,
                side=entry_side,
                price=float(entry_price),
                size=float(entry_size)
            )
            
            # Extract order ID to track status
            if entry_result:
                # Handle different client response formats
                if isinstance(entry_result, dict):
                    order.entry_order_id = entry_result.get("id") or entry_result.get("order_id")
                elif hasattr(entry_result, "id"):
                    order.entry_order_id = entry_result.id

            order.status = OrderStatus.ACTIVE
            order.entry_status = OrderStatus.ACTIVE
            
            logger.info(
                f"Bracket entry placed: {order.id[:8]}... "
                f"{entry_side} ${float(entry_size)} @ ${float(entry_price):.4f}"
            )
            
        except Exception as e:
            order.status = OrderStatus.FAILED
            order.entry_status = OrderStatus.FAILED
            logger.error(f"Bracket entry failed: {e}")
            raise
        
        self.brackets[order.id] = order
        
        await self._notify_callbacks(order.id, "created", {
            "type": "bracket",
            "entry_price": float(entry_price),
            "take_profit_price": float(take_profit_price),
            "stop_loss_price": float(stop_loss_price)
        })
        
        return order
    
    # -------------------------------------------------------------------------
    # Order Cancellation
    # -------------------------------------------------------------------------
    
    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an advanced order by ID.
        
        Args:
            order_id: Order ID to cancel
        
        Returns:
            True if cancelled successfully
        """
        # Check all order types
        if order_id in self.trailing_stops:
            order = self.trailing_stops.pop(order_id)
            order.status = OrderStatus.CANCELLED
            logger.info(f"Cancelled trailing stop: {order_id[:8]}...")
            return True
        
        if order_id in self.stop_losses:
            order = self.stop_losses.pop(order_id)
            order.status = OrderStatus.CANCELLED
            logger.info(f"Cancelled stop-loss: {order_id[:8]}...")
            return True
        
        if order_id in self.take_profits:
            order = self.take_profits.pop(order_id)
            order.status = OrderStatus.CANCELLED
            logger.info(f"Cancelled take-profit: {order_id[:8]}...")
            return True
        
        if order_id in self.brackets:
            order = self.brackets.pop(order_id)
            order.status = OrderStatus.CANCELLED
            logger.info(f"Cancelled bracket: {order_id[:8]}...")
            return True
        
        return False
    
    async def cancel_orders_for_position(self, position_id: str) -> int:
        """
        Cancel all advanced orders for a position.
        
        Args:
            position_id: Position ID
        
        Returns:
            Number of orders cancelled
        """
        cancelled = 0
        
        # Cancel trailing stops
        for order_id, order in list(self.trailing_stops.items()):
            if order.position_id == position_id:
                await self.cancel_order(order_id)
                cancelled += 1
        
        # Cancel stop losses
        for order_id, order in list(self.stop_losses.items()):
            if order.position_id == position_id:
                await self.cancel_order(order_id)
                cancelled += 1
        
        # Cancel take profits
        for order_id, order in list(self.take_profits.items()):
            if order.position_id == position_id:
                await self.cancel_order(order_id)
                cancelled += 1
        
        return cancelled
    
    # -------------------------------------------------------------------------
    # Monitoring Loop
    # -------------------------------------------------------------------------
    
    async def _monitor_loop(self) -> None:
        """Main monitoring loop for all advanced orders."""
        while self._is_running:
            try:
                await self._check_all_orders()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
            
            await asyncio.sleep(self.MONITOR_INTERVAL)
    
    async def _check_all_orders(self) -> None:
        """Check all active orders against current prices."""
        # Collect all unique token IDs
        token_ids: set[str] = set()
        
        for order in self.trailing_stops.values():
            if order.status == OrderStatus.ACTIVE:
                token_ids.add(order.token_id)
        
        for order in self.stop_losses.values():
            if order.status == OrderStatus.ACTIVE:
                token_ids.add(order.token_id)
        
        for order in self.take_profits.values():
            if order.status == OrderStatus.ACTIVE:
                token_ids.add(order.token_id)
        
        for order in self.brackets.values():
            if order.status == OrderStatus.ACTIVE:
                token_ids.add(order.token_id)
        
        if not token_ids:
            return
        
        # Fetch prices for all tokens
        prices: dict[str, Decimal] = {}
        for token_id in token_ids:
            try:
                if self.price_fetcher:
                    price = await self.price_fetcher(token_id)
                    prices[token_id] = Decimal(str(price))
            except Exception as e:
                logger.warning(f"Failed to fetch price for {token_id[:16]}...: {e}")
        
        # Check trailing stops
        for order in list(self.trailing_stops.values()):
            if order.status != OrderStatus.ACTIVE:
                continue
            
            price = prices.get(order.token_id)
            if price is None:
                continue
            
            triggered = await self._update_trailing_stop(order, price)
            if triggered:
                await self._execute_triggered_order(order, price, "trailing_stop")
        
        # Check stop losses
        for order in list(self.stop_losses.values()):
            if order.status != OrderStatus.ACTIVE:
                continue
            
            price = prices.get(order.token_id)
            if price is None:
                continue
            
            if price <= order.stop_price:
                order.status = OrderStatus.TRIGGERED
                order.triggered_at = datetime.now(timezone.utc)
                await self._execute_triggered_order(order, price, "stop_loss")
        
        # Check take profits
        for order in list(self.take_profits.values()):
            if order.status != OrderStatus.ACTIVE:
                continue
            
            price = prices.get(order.token_id)
            if price is None:
                continue
            
            if price >= order.target_price:
                order.status = OrderStatus.TRIGGERED
                order.triggered_at = datetime.now(timezone.utc)
                await self._execute_triggered_order(order, price, "take_profit")
        
        # Check brackets (TP and SL after entry filled)
        for order in list(self.brackets.values()):
            if order.status != OrderStatus.ACTIVE:
                continue
            
            price = prices.get(order.token_id)
            if price is None:
                continue
            
            await self._check_bracket_order(order, price)
    
    async def _execute_triggered_order(
        self,
        order: TrailingStopOrder | StopLossOrder | TakeProfitOrder,
        current_price: Decimal,
        order_type: str
    ) -> None:
        """Execute a triggered order."""
        try:
            # Determine execution price
            if isinstance(order, StopLossOrder) and order.limit_price:
                exec_price = float(order.limit_price)
            elif isinstance(order, TakeProfitOrder) and order.limit_price:
                exec_price = float(order.limit_price)
            else:
                exec_price = float(current_price)
            
            # Place the exit order
            result = await self.client.place_order(
                token_id=order.token_id,
                side=order.side,
                price=exec_price,
                size=float(order.size)
            )
            
            order.status = OrderStatus.FILLED
            order.filled_at = datetime.now(timezone.utc)
            order.filled_price = Decimal(str(exec_price))
            
            logger.info(
                f"{order_type.upper()} triggered and filled: {order.id[:8]}... "
                f"@ ${exec_price:.4f}"
            )
            
            await self._notify_callbacks(order.id, "filled", {
                "type": order_type,
                "filled_price": exec_price,
                "size": float(order.size)
            })
            
            # Update position in database if available
            if self.db and order.position_id:
                try:
                    await PositionCRUD.close_position(
                        self.db,
                        uuid.UUID(order.position_id),
                        exit_price=Decimal(str(exec_price)),
                        exit_reason=order_type
                    )
                except Exception as e:
                    logger.error(f"Failed to update position: {e}")
            
        except Exception as e:
            order.status = OrderStatus.FAILED
            logger.error(f"Failed to execute {order_type}: {e}")
            
            await self._notify_callbacks(order.id, "failed", {
                "type": order_type,
                "error": str(e)
            })
    
    async def _check_bracket_order(
        self, order: BracketOrder, current_price: Decimal
    ) -> None:
        """Check bracket order TP and SL conditions."""
        # Only check if entry has filled and TP/SL are active
        if order.entry_status != OrderStatus.FILLED:
            # Check if entry order filled via API
            if order.entry_order_id:
                try:
                    # Fetch fresh order status
                    if hasattr(self.client, 'get_order'):
                        # Support both async and sync clients (though we likely use async here)
                        result = self.client.get_order(order.entry_order_id)
                        if asyncio.iscoroutine(result):
                            result = await result
                            
                        # Parse result (Kalshi vs Polymarket format)
                        status = None
                        if isinstance(result, dict):
                            # Kalshi: {"order": {"status": "executed"}}
                            # Polymarket: {"status": "cancellable"} or similar
                            order_data = result.get("order", result)
                            status = order_data.get("status")
                            
                        if status in ["executed", "filled", "matched"]:
                            order.entry_status = OrderStatus.FILLED
                            order.status = OrderStatus.ACTIVE  # TP/SL now active
                            logger.info(f"Bracket entry confirmed filled: {order.id[:8]}...")
                        elif status in ["canceled", "expired", "killed"]:
                            order.entry_status = OrderStatus.CANCELLED
                            order.status = OrderStatus.CANCELLED
                            logger.info(f"Bracket entry travelled/expired: {order.id[:8]}...")
                            
                except Exception as e:
                    logger.debug(f"Failed to check entry status for {order.entry_order_id}: {e}")
            return
        
        # Check take profit
        if (
            order.take_profit_status == OrderStatus.ACTIVE
            and current_price >= order.take_profit_price
        ):
            order.take_profit_status = OrderStatus.TRIGGERED
            order.stop_loss_status = OrderStatus.CANCELLED  # OCO
            
            try:
                exit_side = "SELL" if order.entry_side == "BUY" else "BUY"
                await self.client.place_order(
                    token_id=order.token_id,
                    side=exit_side,
                    price=float(order.take_profit_price),
                    size=float(order.entry_size)
                )
                
                order.take_profit_status = OrderStatus.FILLED
                order.status = OrderStatus.FILLED
                order.exit_reason = "take_profit"
                order.completed_at = datetime.now(timezone.utc)
                
                logger.info(f"Bracket TP filled: {order.id[:8]}...")
                
            except Exception as e:
                order.take_profit_status = OrderStatus.FAILED
                logger.error(f"Bracket TP failed: {e}")
            
            return
        
        # Check stop loss
        if (
            order.stop_loss_status == OrderStatus.ACTIVE
            and current_price <= order.stop_loss_price
        ):
            order.stop_loss_status = OrderStatus.TRIGGERED
            order.take_profit_status = OrderStatus.CANCELLED  # OCO
            
            try:
                exit_side = "SELL" if order.entry_side == "BUY" else "BUY"
                await self.client.place_order(
                    token_id=order.token_id,
                    side=exit_side,
                    price=float(order.stop_loss_price),
                    size=float(order.entry_size)
                )
                
                order.stop_loss_status = OrderStatus.FILLED
                order.status = OrderStatus.FILLED
                order.exit_reason = "stop_loss"
                order.completed_at = datetime.now(timezone.utc)
                
                logger.info(f"Bracket SL filled: {order.id[:8]}...")
                
            except Exception as e:
                order.stop_loss_status = OrderStatus.FAILED
                logger.error(f"Bracket SL failed: {e}")
    
    # -------------------------------------------------------------------------
    # Status Queries
    # -------------------------------------------------------------------------
    
    def get_active_orders(self, user_id: str | None = None) -> dict[str, list]:
        """
        Get all active orders, optionally filtered by user.
        
        Returns:
            Dict with order type keys and lists of active orders
        """
        result = {
            "trailing_stops": [],
            "stop_losses": [],
            "take_profits": [],
            "brackets": []
        }
        
        for order in self.trailing_stops.values():
            if order.status == OrderStatus.ACTIVE:
                if user_id is None or order.user_id == user_id:
                    result["trailing_stops"].append(order)
        
        for order in self.stop_losses.values():
            if order.status == OrderStatus.ACTIVE:
                if user_id is None or order.user_id == user_id:
                    result["stop_losses"].append(order)
        
        for order in self.take_profits.values():
            if order.status == OrderStatus.ACTIVE:
                if user_id is None or order.user_id == user_id:
                    result["take_profits"].append(order)
        
        for order in self.brackets.values():
            if order.status == OrderStatus.ACTIVE:
                if user_id is None or order.user_id == user_id:
                    result["brackets"].append(order)
        
        return result
    
    def get_orders_for_position(self, position_id: str) -> dict[str, list]:
        """Get all orders associated with a position."""
        result = {
            "trailing_stops": [],
            "stop_losses": [],
            "take_profits": []
        }
        
        for order in self.trailing_stops.values():
            if order.position_id == position_id:
                result["trailing_stops"].append(order)
        
        for order in self.stop_losses.values():
            if order.position_id == position_id:
                result["stop_losses"].append(order)
        
        for order in self.take_profits.values():
            if order.position_id == position_id:
                result["take_profits"].append(order)
        
        return result


# Global instance
advanced_order_manager: AdvancedOrderManager | None = None


def get_advanced_order_manager() -> AdvancedOrderManager | None:
    """Get the global advanced order manager instance."""
    return advanced_order_manager


def init_advanced_order_manager(
    trading_client: Any,
    price_fetcher: Callable[[str], float] | None = None,
    db: AsyncSession | None = None
) -> AdvancedOrderManager:
    """Initialize the global advanced order manager."""
    global advanced_order_manager
    advanced_order_manager = AdvancedOrderManager(
        trading_client=trading_client,
        price_fetcher=price_fetcher,
        db=db
    )
    return advanced_order_manager
