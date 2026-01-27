"""
WebSocket API routes for real-time updates (REQ-UX-002).

Provides authenticated WebSocket connections for pushing:
- Trade execution events
- Position updates
- Bot status changes
- Risk alerts
"""

import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException, status
from jose import jwt, JWTError

from src.config import get_settings
from src.core.websocket import (
    connection_manager,
    WebSocketMessage,
    WebSocketEventType,
)

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(tags=["WebSocket"])


async def authenticate_websocket(token: str | None) -> str | None:
    """
    Authenticate WebSocket connection using JWT token.

    Args:
        token: JWT token from query parameter

    Returns:
        User ID if authenticated, None otherwise
    """
    if not token:
        return None

    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        user_id = payload.get("sub")
        if user_id is None:
            return None
        return str(user_id)
    except JWTError as e:
        logger.warning(f"WebSocket authentication failed: {e}")
        return None


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str | None = Query(None, description="JWT access token"),
):
    """
    WebSocket endpoint for real-time updates.

    Connect with: ws://host/ws?token=<jwt_token>

    Events pushed to client:
    - trade_executed: When a trade is executed
    - position_opened: When a new position is opened
    - position_closed: When a position is closed
    - position_updated: When position P&L changes
    - bot_started: When the bot starts
    - bot_stopped: When the bot stops
    - bot_error: When the bot encounters an error
    - heartbeat: Periodic heartbeat to keep connection alive
    - error: Error notifications

    Client can send:
    - {"action": "ping"}: Request immediate heartbeat
    - {"action": "subscribe", "events": ["trade_executed", ...]}: Subscribe to specific events
    """
    # Authenticate the connection
    user_id = await authenticate_websocket(token)

    if not user_id:
        await websocket.close(code=4001, reason="Authentication required")
        return

    # Register the connection
    await connection_manager.connect(websocket, user_id)

    try:
        while True:
            # Wait for messages from client
            data = await websocket.receive_json()

            action = data.get("action")

            if action == "ping":
                # Respond with heartbeat
                await connection_manager.send_to_user(
                    user_id,
                    WebSocketMessage(
                        event_type=WebSocketEventType.HEARTBEAT,
                        data={"pong": True},
                    ),
                )
            elif action == "subscribe":
                # Client wants to subscribe to specific events
                # (For now, all events are pushed; this is a placeholder for filtering)
                events = data.get("events", [])
                logger.info(f"User {user_id} subscribed to events: {events}")
                await connection_manager.send_to_user(
                    user_id,
                    WebSocketMessage(
                        event_type=WebSocketEventType.CONNECTION_ESTABLISHED,
                        data={"subscribed": events},
                    ),
                )
            else:
                # Unknown action
                await connection_manager.send_to_user(
                    user_id,
                    WebSocketMessage(
                        event_type=WebSocketEventType.ERROR,
                        data={"message": f"Unknown action: {action}"},
                    ),
                )

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for user {user_id}")
    except Exception as e:
        logger.error(f"WebSocket error for user {user_id}: {e}")
    finally:
        await connection_manager.disconnect(websocket, user_id)


@router.get("/ws/status")
async def websocket_status():
    """
    Get WebSocket connection statistics.

    Returns connection counts and connected users (for debugging).
    """
    return {
        "total_connections": connection_manager.get_connection_count(),
        "connected_users": len(connection_manager.get_connected_users()),
    }
