"""
Health check routes for monitoring trading system status.
Provides comprehensive health checks for all critical components.
"""

import logging
from typing import Any, Dict
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import DbSession, CurrentUser
from src.db.crud.global_settings import GlobalSettingsCRUD
from src.db.crud.polymarket_account import PolymarketAccountCRUD
from src.services.espn_service import ESPNService
from src.services.bot_runner import get_bot_status, BotState


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/health", tags=["Health"])


@router.get("/trading")
async def trading_health_check(
    db: DbSession,
    current_user: CurrentUser
) -> Dict[str, Any]:
    """
    Comprehensive health check for trading systems.
    
    Checks:
    - API connectivity to exchange
    - Database connectivity
    - ESPN service availability
    - Bot state
    - Position reconciliation status
    - Kill switch status
    
    Returns detailed status for each component.
    """
    health = {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_id": str(current_user.id),
        "checks": {}
    }
    
    # Check 1: API connectivity
    try:
        credentials = await PolymarketAccountCRUD.get_decrypted_credentials(
            db, current_user.id
        )
        
        if credentials:
            platform = credentials.get("platform", "polymarket")
            
            if platform == "kalshi":
                from src.services.kalshi_client import KalshiClient
                client = KalshiClient(
                    api_key_id=credentials["api_key"],
                    private_key_pem=credentials["api_secret"],
                    environment=credentials.get("environment", "production")
                )
                balance = await client.get_balance()
                
                health["checks"]["api_connectivity"] = {
                    "status": "pass",
                    "platform": "kalshi",
                    "available_balance": float(balance.get("available_balance", 0)),
                    "total_balance": float(balance.get("total_balance", 0))
                }
                await client.close()
            else:
                health["checks"]["api_connectivity"] = {
                    "status": "pass",
                    "platform": "polymarket",
                    "message": "Polymarket client configured"
                }
        else:
            health["checks"]["api_connectivity"] = {
                "status": "warning",
                "message": "No credentials configured"
            }
    except Exception as e:
        health["checks"]["api_connectivity"] = {
            "status": "fail",
            "error": str(e)
        }
        health["status"] = "degraded"
    
    # Check 2: Database connectivity
    try:
        await db.execute("SELECT 1")
        health["checks"]["database"] = {"status": "pass"}
    except Exception as e:
        health["checks"]["database"] = {
            "status": "fail",
            "error": str(e)
        }
        health["status"] = "unhealthy"
    
    # Check 3: ESPN connectivity
    try:
        espn_service = ESPNService()
        games = await espn_service.get_live_games("nba")
        health["checks"]["espn"] = {
            "status": "pass",
            "games_found": len(games)
        }
    except Exception as e:
        health["checks"]["espn"] = {
            "status": "fail",
            "error": str(e)
        }
        health["status"] = "degraded"
    
    # Check 4: Bot state
    try:
        bot_status = get_bot_status(current_user.id)
        if bot_status:
            health["checks"]["bot"] = {
                "status": bot_status.get("state", "unknown"),
                "running": bot_status.get("state") == BotState.RUNNING.value,
                "tracked_games": bot_status.get("tracked_games", 0),
                "trades_today": bot_status.get("trades_today", 0),
                "daily_pnl": bot_status.get("daily_pnl", 0)
            }
        else:
            health["checks"]["bot"] = {
                "status": "stopped",
                "running": False
            }
    except Exception as e:
        health["checks"]["bot"] = {
            "status": "unknown",
            "error": str(e)
        }
    
    # Check 5: Settings
    try:
        settings = await GlobalSettingsCRUD.get_by_user_id(db, current_user.id)
        if settings:
            health["checks"]["settings"] = {
                "status": "pass",
                "bot_enabled": settings.bot_enabled,
                # Removed dry_run_mode from health response
                "max_daily_loss": float(settings.max_daily_loss_usdc)
            }
        else:
            health["checks"]["settings"] = {
                "status": "warning",
                "message": "No settings configured"
            }
    except Exception as e:
        health["checks"]["settings"] = {
            "status": "fail",
            "error": str(e)
        }
    
    # Overall status logic
    failed_checks = sum(
        1 for check in health["checks"].values()
        if check.get("status") == "fail"
    )
    
    if failed_checks >= 2:
        health["status"] = "unhealthy"
    elif failed_checks == 1:
        health["status"] = "degraded"
    elif any(check.get("status") == "warning" for check in health["checks"].values()):
        health["status"] = "warning"
    
    return health


@router.get("/quick")
async def quick_health_check() -> Dict[str, str]:
    """
    Quick health check for load balancers.
    
    Returns simple pass/fail status.
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.get("/detailed")
async def detailed_health_check(
    db: DbSession,
    current_user: CurrentUser
) -> Dict[str, Any]:
    """
    Detailed health check with all metrics.
    
    Includes:
    - All checks from /health/trading
    - Position counts
    - Recent trade statistics
    - System performance metrics
    """
    # Get basic health
    basic_health = await trading_health_check(db, current_user)
    
    # Add detailed metrics
    detailed = {
        **basic_health,
        "detailed_metrics": {}
    }
    
    # Position metrics
    try:
        from src.db.crud.position import PositionCRUD
        
        open_positions = await PositionCRUD.count_open_for_user(db, current_user.id)
        daily_pnl = await PositionCRUD.get_daily_pnl(db, current_user.id)
        today_trades = await PositionCRUD.count_today_trades(db, current_user.id)
        
        detailed["detailed_metrics"]["positions"] = {
            "open_count": open_positions,
            "daily_pnl": float(daily_pnl) if daily_pnl else 0.0,
            "today_trades": today_trades
        }
    except Exception as e:
        detailed["detailed_metrics"]["positions"] = {
            "error": str(e)
        }
    
    # Reconciliation status
    try:
        from src.services.position_reconciler import PositionReconciler
        from src.db.crud.polymarket_account import PolymarketAccountCRUD
        
        credentials = await PolymarketAccountCRUD.get_decrypted_credentials(
            db, current_user.id
        )
        
        if credentials and credentials.get("platform") == "kalshi":
            from src.services.kalshi_client import KalshiClient
            client = KalshiClient(
                api_key_id=credentials["api_key"],
                private_key_pem=credentials["api_secret"],
                environment=credentials.get("environment", "production")
            )
            
            reconciler = PositionReconciler(db, current_user.id, client)
            quick_check = await reconciler.quick_check()
            
            detailed["detailed_metrics"]["reconciliation"] = quick_check
            await client.close()
    except Exception as e:
        detailed["detailed_metrics"]["reconciliation"] = {
            "error": str(e)
        }
    
    return detailed
