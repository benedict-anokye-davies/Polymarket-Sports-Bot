"""
Dashboard routes for overview and statistics.
Includes SSE streaming for real-time updates.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from src.api.deps import DbSession, OnboardedUser, SSEUser
from src.db.crud.position import PositionCRUD
from src.db.crud.tracked_market import TrackedMarketCRUD
from src.db.crud.global_settings import GlobalSettingsCRUD
from src.db.crud.activity_log import ActivityLogCRUD
from src.db.crud.polymarket_account import PolymarketAccountCRUD
from src.schemas.dashboard import DashboardStats, PositionSummary, RecentActivity
from src.services.bot_runner import get_bot_status


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(db: DbSession, current_user: OnboardedUser) -> DashboardStats:
    """
    Returns aggregated statistics for the dashboard overview.
    Includes balance, positions, P&L, and recent activity.
    """
    settings = await GlobalSettingsCRUD.get_by_user_id(db, current_user.id)
    open_positions = await PositionCRUD.get_open_for_user(db, current_user.id)
    active_markets = await TrackedMarketCRUD.get_active_for_user(db, current_user.id)
    recent_logs = await ActivityLogCRUD.get_recent(db, current_user.id, limit=10)
    
    balance_usdc = Decimal("0")
    credentials = await PolymarketAccountCRUD.get_decrypted_credentials(db, current_user.id)
    
    if credentials:
        try:
            platform = credentials.get("platform", "polymarket")
            
            if platform == "kalshi":
                from src.services.kalshi_client import KalshiClient
                api_key = credentials.get("api_key")
                api_secret = credentials.get("api_secret")
                
                if api_key and api_secret:
                    client = KalshiClient(
                        api_key=api_key,
                        private_key_pem=api_secret,
                    )
                    balance_data = await client.get_balance()
                    await client.close()
                    # Kalshi returns balance in cents, convert to dollars
                    balance_cents = balance_data.get("balance", 0) or balance_data.get("available_balance", 0)
                    balance_usdc = Decimal(str(balance_cents)) / Decimal("100")
            else:
                from src.services.polymarket_client import PolymarketClient
                private_key = credentials.get("private_key")
                funder_address = credentials.get("funder_address")
                
                if private_key and funder_address:
                    client = PolymarketClient(
                        private_key=private_key,
                        funder_address=funder_address
                    )
                    balance_usdc = await client.get_balance()
        except Exception as e:
            logger.warning(f"Failed to fetch balance for user {current_user.id}: {e}")
    
    open_exposure = await PositionCRUD.get_open_exposure(db, current_user.id)
    daily_pnl = await PositionCRUD.get_daily_pnl(db, current_user.id)
    total_pnl = await PositionCRUD.get_total_pnl(db, current_user.id)
    win_rate = await PositionCRUD.get_win_rate(db, current_user.id)
    
    position_summaries = []
    for pos in open_positions:
        market = await TrackedMarketCRUD.get_by_condition_id(db, current_user.id, pos.condition_id)
        current_price = None
        unrealized_pnl = None
        
        if market:
            if pos.side == "YES":
                current_price = market.current_price_yes
            else:
                current_price = market.current_price_no
            
            if current_price:
                current_value = current_price * pos.entry_size
                unrealized_pnl = current_value - pos.entry_cost_usdc
        
        position_summaries.append(PositionSummary(
            id=pos.id,
            token_id=pos.token_id,
            side=pos.side,
            team=pos.team,
            entry_price=pos.entry_price,
            current_price=current_price,
            unrealized_pnl=unrealized_pnl,
            size=pos.entry_size,
            opened_at=pos.opened_at
        ))
    
    activity_items = [
        RecentActivity(
            id=log.id,
            level=log.level,
            category=log.category,
            message=log.message,
            created_at=log.created_at
        )
        for log in recent_logs
    ]
    
    return DashboardStats(
        balance_usdc=balance_usdc,
        open_positions_count=len(open_positions),
        open_positions_value=open_exposure,
        total_pnl_today=daily_pnl,
        total_pnl_all_time=total_pnl,
        win_rate=win_rate,
        active_markets_count=len(active_markets),
        bot_status="running" if settings and settings.bot_enabled else "stopped",
        open_positions=position_summaries,
        recent_activity=activity_items
    )


@router.get("/stream")
async def stream_dashboard(request: Request, db: DbSession, current_user: SSEUser):
    """
    Server-Sent Events endpoint for real-time dashboard updates.
    Streams bot status, tracked games, and price updates every 2 seconds.
    
    Supports token auth via query param for EventSource compatibility:
    GET /dashboard/stream?token=<jwt>
    
    Event types:
    - status: Bot running state and stats
    - games: Currently tracked games with prices
    - positions: Open positions with unrealized P&L
    - heartbeat: Keep-alive ping
    """
    # Import here to avoid circular imports
    from src.db.database import async_session_factory
    
    # Store user_id before generator (current_user may not be available inside)
    user_id = current_user.id
    
    # Maximum SSE stream duration (30 minutes) to prevent resource exhaustion
    MAX_STREAM_DURATION = 1800  # seconds
    
    async def event_generator() -> AsyncGenerator[str, None]:
        """Generates SSE events for dashboard updates."""
        stream_start = datetime.now(timezone.utc)
        
        try:
            while True:
                # Check max duration
                elapsed = (datetime.now(timezone.utc) - stream_start).total_seconds()
                if elapsed > MAX_STREAM_DURATION:
                    logger.info(f"SSE stream max duration reached for user {user_id}")
                    yield f"event: close\ndata: {{\"reason\": \"max_duration\"}}\n\n"
                    break
                
                # Check if client disconnected
                if await request.is_disconnected():
                    logger.debug(f"SSE client disconnected: user {user_id}")
                    break
                
                try:
                    # Get bot status (no DB needed)
                    bot_status = get_bot_status(user_id)
                    
                    if bot_status:
                        # Send status event
                        status_data = {
                            "type": "status",
                            "data": {
                                "state": bot_status.get("state", "stopped"),
                                "tracked_games": bot_status.get("tracked_games", 0),
                                "trades_today": bot_status.get("trades_today", 0),
                                "daily_pnl": bot_status.get("daily_pnl", 0),
                                "websocket_status": bot_status.get("websocket_status", "disconnected"),
                                "runtime": bot_status.get("runtime"),
                            }
                        }
                        yield f"event: status\ndata: {json.dumps(status_data)}\n\n"
                        
                        # Send games event
                        games = bot_status.get("games", [])
                        if games:
                            games_data = {
                                "type": "games",
                                "data": games
                            }
                            yield f"event: games\ndata: {json.dumps(games_data)}\n\n"
                    else:
                        # Bot not running - send stopped status
                        yield f"event: status\ndata: {json.dumps({'type': 'status', 'data': {'state': 'stopped'}})}\n\n"
                    
                    # Get open positions with fresh DB session to avoid closed session
                    async with async_session_factory() as session:
                        positions = await PositionCRUD.get_open_for_user(session, user_id)
                        if positions:
                            positions_data = {
                                "type": "positions",
                                "data": [
                                    {
                                        "id": str(p.id),
                                        "condition_id": p.condition_id,
                                        "side": p.side,
                                        "entry_price": float(p.entry_price),
                                        "entry_size": float(p.entry_size),
                                        "team": p.team,
                                    }
                                    for p in positions
                                ]
                            }
                            yield f"event: positions\ndata: {json.dumps(positions_data)}\n\n"
                    
                    # Heartbeat
                    yield f"event: heartbeat\ndata: {json.dumps({'timestamp': datetime.now(timezone.utc).isoformat()})}\n\n"
                    
                except Exception as e:
                    logger.warning(f"SSE event generation error: {e}")
                    yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
                
                # Wait before next update
                await asyncio.sleep(2)
                
        except asyncio.CancelledError:
            logger.debug(f"SSE stream cancelled: user {user_id}")
        except Exception as e:
            logger.error(f"SSE stream error: {e}")
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.get("/performance")
async def get_performance_history(
    db: DbSession,
    current_user: OnboardedUser,
    days: int = 30
) -> dict:
    """
    Returns daily P&L history for performance charts.
    
    Args:
        days: Number of days of history to return (default 30)
    
    Returns:
        Dict with daily P&L data points and summary statistics
    """
    # Get all closed positions within the date range
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    
    positions = await PositionCRUD.get_all_for_user(
        db, current_user.id, status="closed", limit=1000
    )
    
    # Group by date and calculate daily P&L
    daily_pnl: dict[str, float] = {}
    total_trades = 0
    winning_trades = 0
    total_pnl = Decimal("0")
    
    for pos in positions:
        if pos.closed_at and pos.closed_at >= cutoff:
            date_key = pos.closed_at.strftime("%Y-%m-%d")
            pnl = float(pos.realized_pnl_usdc or 0)
            
            if date_key not in daily_pnl:
                daily_pnl[date_key] = 0
            daily_pnl[date_key] += pnl
            
            total_trades += 1
            total_pnl += pos.realized_pnl_usdc or Decimal("0")
            if pos.realized_pnl_usdc and pos.realized_pnl_usdc > 0:
                winning_trades += 1
    
    # Fill in missing dates with 0
    chart_data = []
    current = datetime.now(timezone.utc).date()
    for i in range(days):
        date = current - timedelta(days=i)
        date_str = date.strftime("%Y-%m-%d")
        chart_data.append({
            "date": date_str,
            "pnl": daily_pnl.get(date_str, 0),
            "cumulative": 0  # Will be calculated below
        })
    
    # Reverse to chronological order and calculate cumulative
    chart_data.reverse()
    cumulative = 0
    for point in chart_data:
        cumulative += point["pnl"]
        point["cumulative"] = round(cumulative, 2)
    
    return {
        "chart_data": chart_data,
        "summary": {
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "win_rate": round(winning_trades / total_trades * 100, 1) if total_trades > 0 else 0,
            "total_pnl": float(total_pnl),
            "avg_trade_pnl": float(total_pnl / total_trades) if total_trades > 0 else 0,
            "best_day": max(daily_pnl.values()) if daily_pnl else 0,
            "worst_day": min(daily_pnl.values()) if daily_pnl else 0,
        }
    }
