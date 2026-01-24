"""
Polymarket WebSocket manager for real-time price streaming.
Implements resilient connection with automatic reconnection and exponential backoff.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Callable, Any
from dataclasses import dataclass, field

import websockets
from websockets.exceptions import WebSocketException

from src.core.retry import calculate_backoff


logger = logging.getLogger(__name__)


@dataclass
class PriceUpdate:
    """Represents a price change event from WebSocket."""
    token_id: str
    price: float
    size: float
    side: str  # "BUY" or "SELL"
    best_bid: float
    best_ask: float
    timestamp: datetime
    condition_id: str
    order_hash: str | None = None
    
    @property
    def spread(self) -> float:
        """Calculate bid-ask spread."""
        return self.best_ask - self.best_bid
    
    @property
    def spread_pct(self) -> float:
        """Calculate spread as percentage of mid price."""
        mid = (self.best_bid + self.best_ask) / 2
        if mid == 0:
            return 0
        return self.spread / mid


@dataclass
class MarketState:
    """Tracks current state of a market."""
    condition_id: str
    token_id_yes: str
    token_id_no: str
    best_bid_yes: float = 0.0
    best_ask_yes: float = 0.0
    best_bid_no: float = 0.0
    best_ask_no: float = 0.0
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    @property
    def mid_price_yes(self) -> float:
        """Mid price for YES outcome."""
        if self.best_bid_yes == 0 or self.best_ask_yes == 0:
            return 0
        return (self.best_bid_yes + self.best_ask_yes) / 2
    
    @property
    def mid_price_no(self) -> float:
        """Mid price for NO outcome."""
        if self.best_bid_no == 0 or self.best_ask_no == 0:
            return 0
        return (self.best_bid_no + self.best_ask_no) / 2


class PolymarketWebSocket:
    """
    Manages WebSocket connection to Polymarket CLOB for real-time price updates.
    
    Features:
    - Automatic reconnection with exponential backoff
    - Subscription management for multiple markets
    - Price update callbacks for trading engine integration
    - Connection health monitoring
    """
    
    WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/"
    PING_INTERVAL = 10  # seconds
    RECV_TIMEOUT = 60   # seconds before considering connection dead
    MAX_RECONNECT_ATTEMPTS = 10
    
    def __init__(self):
        self._websocket: websockets.WebSocketClientProtocol | None = None
        self._subscribed_markets: set[str] = set()  # condition_ids
        self._market_states: dict[str, MarketState] = {}
        self._callbacks: list[Callable[[PriceUpdate], Any]] = []
        self._is_running = False
        self._reconnect_attempt = 0
        self._last_message_time: datetime | None = None
        self._connection_task: asyncio.Task | None = None
        self._ping_task: asyncio.Task | None = None
    
    @property
    def is_connected(self) -> bool:
        """Check if WebSocket is connected."""
        return self._websocket is not None and self._websocket.open
    
    def add_callback(self, callback: Callable[[PriceUpdate], Any]) -> None:
        """
        Register a callback for price updates.
        
        Args:
            callback: Function that receives PriceUpdate objects
        """
        self._callbacks.append(callback)
    
    def remove_callback(self, callback: Callable[[PriceUpdate], Any]) -> None:
        """Remove a previously registered callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
    
    def get_market_state(self, condition_id: str) -> MarketState | None:
        """Get current state for a market."""
        return self._market_states.get(condition_id)
    
    async def subscribe(self, condition_id: str, token_id_yes: str, token_id_no: str) -> None:
        """
        Subscribe to price updates for a market.
        
        Args:
            condition_id: Market condition ID
            token_id_yes: YES outcome token ID
            token_id_no: NO outcome token ID
        """
        self._subscribed_markets.add(condition_id)
        self._market_states[condition_id] = MarketState(
            condition_id=condition_id,
            token_id_yes=token_id_yes,
            token_id_no=token_id_no
        )
        
        if self.is_connected:
            await self._send_subscription(condition_id, "subscribe")
            logger.info(f"Subscribed to market: {condition_id}")
    
    async def unsubscribe(self, condition_id: str) -> None:
        """Unsubscribe from a market."""
        self._subscribed_markets.discard(condition_id)
        self._market_states.pop(condition_id, None)
        
        if self.is_connected:
            await self._send_subscription(condition_id, "unsubscribe")
            logger.info(f"Unsubscribed from market: {condition_id}")
    
    async def _send_subscription(self, condition_id: str, operation: str) -> None:
        """Send subscription message to WebSocket."""
        if not self._websocket:
            return
        
        state = self._market_states.get(condition_id)
        if not state:
            return
        
        # Subscribe to both token IDs
        message = {
            "assets_ids": [state.token_id_yes, state.token_id_no],
            "type": "market"
        }
        
        await self._websocket.send(json.dumps(message))
    
    async def start(self) -> None:
        """Start the WebSocket connection and message processing."""
        if self._is_running:
            logger.warning("WebSocket manager already running")
            return
        
        self._is_running = True
        self._connection_task = asyncio.create_task(self._connection_loop())
        logger.info("WebSocket manager started")
    
    async def stop(self) -> None:
        """Stop the WebSocket connection gracefully."""
        self._is_running = False
        
        if self._ping_task:
            self._ping_task.cancel()
            try:
                await self._ping_task
            except asyncio.CancelledError:
                pass
        
        if self._websocket:
            await self._websocket.close()
            self._websocket = None
        
        if self._connection_task:
            self._connection_task.cancel()
            try:
                await self._connection_task
            except asyncio.CancelledError:
                pass
        
        logger.info("WebSocket manager stopped")
    
    async def _connection_loop(self) -> None:
        """Main connection loop with automatic reconnection."""
        while self._is_running:
            try:
                await self._connect_and_listen()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"WebSocket connection error: {e}")
                
                if not self._is_running:
                    break
                
                # Exponential backoff for reconnection
                delay = calculate_backoff(
                    self._reconnect_attempt,
                    base_delay=1.0,
                    max_delay=30.0
                )
                self._reconnect_attempt += 1
                
                if self._reconnect_attempt > self.MAX_RECONNECT_ATTEMPTS:
                    logger.critical(
                        f"Max reconnection attempts ({self.MAX_RECONNECT_ATTEMPTS}) exceeded"
                    )
                    break
                
                logger.info(f"Reconnecting in {delay:.2f}s (attempt {self._reconnect_attempt})")
                await asyncio.sleep(delay)
    
    async def _connect_and_listen(self) -> None:
        """Establish connection and process messages."""
        logger.info(f"Connecting to {self.WS_URL}")
        
        async with websockets.connect(
            self.WS_URL,
            ping_interval=None,  # We handle pings manually
            ping_timeout=None
        ) as websocket:
            self._websocket = websocket
            self._reconnect_attempt = 0
            self._last_message_time = datetime.now(timezone.utc)
            
            logger.info("WebSocket connected successfully")
            
            # Resubscribe to all markets
            for condition_id in self._subscribed_markets:
                await self._send_subscription(condition_id, "subscribe")
            
            # Start ping task
            self._ping_task = asyncio.create_task(self._ping_loop())
            
            try:
                await self._message_loop()
            finally:
                if self._ping_task:
                    self._ping_task.cancel()
    
    async def _ping_loop(self) -> None:
        """Send periodic pings to keep connection alive."""
        while self._is_running and self._websocket:
            try:
                await asyncio.sleep(self.PING_INTERVAL)
                if self._websocket and self._websocket.open:
                    await self._websocket.send("PING")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Ping failed: {e}")
    
    async def _message_loop(self) -> None:
        """Process incoming WebSocket messages."""
        while self._is_running and self._websocket:
            try:
                message = await asyncio.wait_for(
                    self._websocket.recv(),
                    timeout=self.RECV_TIMEOUT
                )
                
                self._last_message_time = datetime.now(timezone.utc)
                
                # Skip pong responses
                if message == "PONG":
                    continue
                
                await self._process_message(message)
                
            except asyncio.TimeoutError:
                logger.warning(f"No message received for {self.RECV_TIMEOUT}s, reconnecting")
                raise
            except WebSocketException as e:
                logger.error(f"WebSocket error: {e}")
                raise
    
    async def _process_message(self, raw_message: str) -> None:
        """Parse and process a WebSocket message."""
        try:
            data = json.loads(raw_message)
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON: {raw_message[:100]}")
            return
        
        event_type = data.get("event_type")
        
        if event_type == "price_change":
            await self._handle_price_change(data)
        elif event_type == "book":
            await self._handle_book_update(data)
        elif event_type == "last_trade_price":
            await self._handle_last_trade(data)
        elif event_type == "tick_size_change":
            logger.info(f"Tick size change: {data}")
    
    async def _handle_price_change(self, data: dict) -> None:
        """Handle price_change event."""
        condition_id = data.get("market", "")
        timestamp_ms = data.get("timestamp", 0)
        timestamp = datetime.fromtimestamp(int(timestamp_ms) / 1000, tz=timezone.utc)
        
        for change in data.get("price_changes", []):
            token_id = change.get("asset_id", "")
            
            price_update = PriceUpdate(
                token_id=token_id,
                price=float(change.get("price", 0)),
                size=float(change.get("size", 0)),
                side=change.get("side", ""),
                best_bid=float(change.get("best_bid", 0)),
                best_ask=float(change.get("best_ask", 0)),
                timestamp=timestamp,
                condition_id=condition_id,
                order_hash=change.get("hash")
            )
            
            # Update market state
            state = self._market_states.get(condition_id)
            if state:
                if token_id == state.token_id_yes:
                    state.best_bid_yes = price_update.best_bid
                    state.best_ask_yes = price_update.best_ask
                elif token_id == state.token_id_no:
                    state.best_bid_no = price_update.best_bid
                    state.best_ask_no = price_update.best_ask
                state.last_updated = timestamp
            
            # Notify callbacks
            for callback in self._callbacks:
                try:
                    result = callback(price_update)
                    if asyncio.iscoroutine(result):
                        await result
                except Exception as e:
                    logger.error(f"Callback error: {e}")
    
    async def _handle_book_update(self, data: dict) -> None:
        """Handle orderbook update event."""
        # Book updates contain full orderbook snapshots
        # Extract best bid/ask from the book
        token_id = data.get("asset_id", "")
        bids = data.get("bids", [])
        asks = data.get("asks", [])
        
        best_bid = float(bids[0]["price"]) if bids else 0
        best_ask = float(asks[0]["price"]) if asks else 0
        
        # Find condition_id for this token
        for condition_id, state in self._market_states.items():
            if token_id == state.token_id_yes:
                state.best_bid_yes = best_bid
                state.best_ask_yes = best_ask
                state.last_updated = datetime.now(timezone.utc)
            elif token_id == state.token_id_no:
                state.best_bid_no = best_bid
                state.best_ask_no = best_ask
                state.last_updated = datetime.now(timezone.utc)
    
    async def _handle_last_trade(self, data: dict) -> None:
        """Handle last trade price event."""
        # Log for debugging, don't update state
        logger.debug(f"Last trade: {data.get('asset_id')} @ {data.get('price')}")


# Global singleton instance
websocket_manager = PolymarketWebSocket()
