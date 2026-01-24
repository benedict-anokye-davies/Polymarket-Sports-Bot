"""
Dashboard routes for overview and statistics.
"""

from decimal import Decimal

from fastapi import APIRouter

from src.api.deps import DbSession, OnboardedUser
from src.db.crud.position import PositionCRUD
from src.db.crud.tracked_market import TrackedMarketCRUD
from src.db.crud.global_settings import GlobalSettingsCRUD
from src.db.crud.activity_log import ActivityLogCRUD
from src.db.crud.polymarket_account import PolymarketAccountCRUD
from src.schemas.dashboard import DashboardStats, PositionSummary, RecentActivity


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
            from src.services.polymarket_client import PolymarketClient
            client = PolymarketClient(
                private_key=credentials["private_key"],
                funder_address=credentials["funder_address"]
            )
            balance_usdc = await client.get_balance()
        except Exception:
            pass
    
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
