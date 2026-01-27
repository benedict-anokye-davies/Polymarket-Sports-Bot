"""
WebSocket Connection Manager (REQ-UX-002)

Provides real-time push notifications to connected frontend clients.
Supports multiple event types and per-user connection management.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import Any
from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

logger = logging.getLogger(__name__)


class WebSocketEventType(str, Enum):
    """Types of WebSocket events that can be pushed to clients."""

    # Trading events
    TRADE_EXECUTED = "trade_executed"
    POSITION_OPENED = "position_opened"
    POSITION_CLOSED = "position_closed"
    POSITION_UPDATED = "position_updated"
    ORDER_PLACED = "order_placed"
    ORDER_FILLED = "order_filled"
    ORDER_CANCELLED = "order_cancelled"

    # Bot status events
    BOT_STARTED = "bot_started"
    BOT_STOPPED = "bot_stopped"
    BOT_ERROR = "bot_error"
    BOT_STATUS_CHANGED = "bot_status_changed"

    # Market events
    MARKET_ALERT = "market_alert"
    PRICE_UPDATE = "price_update"

    # System events
    CONNECTION_ESTABLISHED = "connection_established"
    HEARTBEAT = "heartbeat"
    ERROR = "error"

    # Risk events
    DAILY_LOSS_WARNING = "daily_loss_warning"
    KILL_SWITCH_ACTIVATED = "kill_switch_activated"


@dataclass
class WebSocketMessage:
    """Structure for WebSocket messages."""

    event_type: WebSocketEventType
    data: dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    correlation_id: str | None = None

    def to_json(self) -> str:
        """Serialize message to JSON string."""
        return json.dumps({
            "event": self.event_type.value,
            "data": self.data,
            "timestamp": self.timestamp,
            "correlation_id": self.correlation_id,
        })

    @classmethod
    def from_dict(cls, data: dict) -> "WebSocketMessage":
        """Create message from dictionary."""
        return cls(
            event_type=WebSocketEventType(data["event"]),
            data=data.get("data", {}),
            timestamp=data.get("timestamp", datetime.now(timezone.utc).isoformat()),
            correlation_id=data.get("correlation_id"),
        )


class ConnectionManager:
    """
    Manages WebSocket connections for real-time updates.

    Features:
    - Per-user connection tracking
    - Broadcast to all users or specific user
    - Automatic connection cleanup
    - Heartbeat support
    """

    def __init__(self):
        # Map of user_id -> list of active WebSocket connections
        self._connections: dict[str, list[WebSocket]] = {}
        # Lock for thread-safe connection management
        self._lock = asyncio.Lock()
        # Heartbeat interval in seconds
        self.heartbeat_interval = 30

    async def connect(self, websocket: WebSocket, user_id: str) -> None:
        """
        Accept and register a new WebSocket connection.

        Args:
            websocket: The WebSocket connection to register
            user_id: The authenticated user's ID
        """
        await websocket.accept()

        async with self._lock:
            if user_id not in self._connections:
                self._connections[user_id] = []
            self._connections[user_id].append(websocket)

        logger.info(f"WebSocket connected for user {user_id}")

        # Send connection confirmation
        await self.send_to_user(
            user_id,
            WebSocketMessage(
                event_type=WebSocketEventType.CONNECTION_ESTABLISHED,
                data={"message": "Connected to trading bot"},
            ),
        )

    async def disconnect(self, websocket: WebSocket, user_id: str) -> None:
        """
        Remove a WebSocket connection.

        Args:
            websocket: The WebSocket connection to remove
            user_id: The user's ID
        """
        async with self._lock:
            if user_id in self._connections:
                if websocket in self._connections[user_id]:
                    self._connections[user_id].remove(websocket)
                if not self._connections[user_id]:
                    del self._connections[user_id]

        logger.info(f"WebSocket disconnected for user {user_id}")

    async def send_to_user(
        self,
        user_id: str,
        message: WebSocketMessage,
    ) -> int:
        """
        Send a message to all connections for a specific user.

        Args:
            user_id: The target user's ID
            message: The message to send

        Returns:
            Number of connections message was sent to
        """
        sent_count = 0
        disconnected = []

        async with self._lock:
            connections = self._connections.get(user_id, []).copy()

        for websocket in connections:
            try:
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_text(message.to_json())
                    sent_count += 1
                else:
                    disconnected.append(websocket)
            except Exception as e:
                logger.warning(f"Failed to send WebSocket message: {e}")
                disconnected.append(websocket)

        # Clean up disconnected sockets
        if disconnected:
            async with self._lock:
                for ws in disconnected:
                    if user_id in self._connections and ws in self._connections[user_id]:
                        self._connections[user_id].remove(ws)

        return sent_count

    async def broadcast(self, message: WebSocketMessage) -> int:
        """
        Broadcast a message to all connected users.

        Args:
            message: The message to broadcast

        Returns:
            Total number of connections message was sent to
        """
        total_sent = 0

        async with self._lock:
            user_ids = list(self._connections.keys())

        for user_id in user_ids:
            sent = await self.send_to_user(user_id, message)
            total_sent += sent

        return total_sent

    async def send_heartbeat(self) -> None:
        """Send heartbeat to all connections."""
        await self.broadcast(
            WebSocketMessage(
                event_type=WebSocketEventType.HEARTBEAT,
                data={"server_time": datetime.now(timezone.utc).isoformat()},
            )
        )

    def get_connection_count(self, user_id: str | None = None) -> int:
        """
        Get the number of active connections.

        Args:
            user_id: If provided, count only this user's connections

        Returns:
            Number of active connections
        """
        if user_id:
            return len(self._connections.get(user_id, []))
        return sum(len(conns) for conns in self._connections.values())

    def get_connected_users(self) -> list[str]:
        """Get list of user IDs with active connections."""
        return list(self._connections.keys())


# Global connection manager instance
connection_manager = ConnectionManager()


# Convenience functions for pushing events
async def push_trade_event(
    user_id: str,
    event_type: WebSocketEventType,
    trade_data: dict[str, Any],
) -> None:
    """Push a trade-related event to a user."""
    await connection_manager.send_to_user(
        user_id,
        WebSocketMessage(event_type=event_type, data=trade_data),
    )


async def push_bot_status(
    user_id: str,
    status: str,
    details: dict[str, Any] | None = None,
) -> None:
    """Push a bot status update to a user."""
    await connection_manager.send_to_user(
        user_id,
        WebSocketMessage(
            event_type=WebSocketEventType.BOT_STATUS_CHANGED,
            data={"status": status, **(details or {})},
        ),
    )


async def push_position_update(
    user_id: str,
    position_data: dict[str, Any],
) -> None:
    """Push a position update to a user."""
    await connection_manager.send_to_user(
        user_id,
        WebSocketMessage(
            event_type=WebSocketEventType.POSITION_UPDATED,
            data=position_data,
        ),
    )


async def push_error(
    user_id: str,
    error_message: str,
    error_code: str | None = None,
) -> None:
    """Push an error notification to a user."""
    await connection_manager.send_to_user(
        user_id,
        WebSocketMessage(
            event_type=WebSocketEventType.ERROR,
            data={
                "message": error_message,
                "code": error_code,
            },
        ),
    )


async def push_risk_alert(
    user_id: str,
    alert_type: WebSocketEventType,
    alert_data: dict[str, Any],
) -> None:
    """Push a risk management alert to a user."""
    await connection_manager.send_to_user(
        user_id,
        WebSocketMessage(event_type=alert_type, data=alert_data),
    )
