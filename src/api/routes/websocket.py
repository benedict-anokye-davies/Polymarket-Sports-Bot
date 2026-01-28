"""
WebSocket API routes for real-time updates (REQ-UX-002).

Provides authenticated WebSocket connections for pushing:
- Trade execution events
- Position updates
- Bot status changes
- Risk alerts

Security: Authentication is performed via message after connection,
not via URL query parameters to avoid token leakage in logs.
"""

import logging
import asyncio
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

# Authentication timeout in seconds
AUTH_TIMEOUT_SECONDS = 10


async def authenticate_websocket(token: str | None) -> str | None:
    """
    Authenticate WebSocket connection using JWT token.

    Args:
        token: JWT token from authenticate message

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
    token: str | None = Query(None, description="JWT access token (deprecated, use auth message)"),
):
    """
    WebSocket endpoint for real-time updates.

    Connection flow:
    1. Connect to ws://host/api/v1/ws (no token in URL)
    2. Send auth message: {"action": "authenticate", "token": "<jwt_token>"}
    3. Receive success: {"event": "connection_established", ...}
    
    Legacy: Token in URL is still supported but deprecated due to security.

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
    - {"action": "authenticate", "token": "..."}: Authenticate the connection
    - {"action": "ping"}: Request immediate heartbeat
    - {"action": "subscribe", "events": ["trade_executed", ...]}: Subscribe to specific events
    """
    await websocket.accept()
    
    user_id: str | None = None
    
    # Support legacy URL token authentication (deprecated)
    if token:
        user_id = await authenticate_websocket(token)
        if user_id:
            logger.warning(
                f"User {user_id} authenticated via URL token (deprecated). "
                "Use message-based authentication instead."
            )
    
    # If not authenticated via URL, wait for auth message
    if not user_id:
        try:
            # Wait for authentication message with timeout
            data = await asyncio.wait_for(
                websocket.receive_json(),
                timeout=AUTH_TIMEOUT_SECONDS
            )
            
            if data.get("action") == "authenticate":
                auth_token = data.get("token")
                user_id = await authenticate_websocket(auth_token)
                
                if not user_id:
                    await websocket.send_json({
                        "event": "error",
                        "data": {"message": "Authentication failed: Invalid token"}
                    })
                    await websocket.close(code=4001, reason="Authentication failed")
                    return
            else:
                await websocket.send_json({
                    "event": "error",
                    "data": {"message": "First message must be authentication"}
                })
                await websocket.close(code=4001, reason="Authentication required")
                return
                
        except asyncio.TimeoutError:
            await websocket.send_json({
                "event": "error",
                "data": {"message": "Authentication timeout"}
            })
            await websocket.close(code=4001, reason="Authentication timeout")
            return
        except Exception as e:
            logger.warning(f"WebSocket auth error: {e}")
            await websocket.close(code=4001, reason="Authentication error")
            return

    # Register the connection
    await connection_manager.connect(websocket, user_id)
    
    # Send connection established message
    await connection_manager.send_to_user(
        user_id,
        WebSocketMessage(
            event_type=WebSocketEventType.CONNECTION_ESTABLISHED,
            data={"authenticated": True, "user_id": user_id},
        ),
    )

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
            elif action == "authenticate":
                # Already authenticated, ignore re-auth attempts
                pass
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
