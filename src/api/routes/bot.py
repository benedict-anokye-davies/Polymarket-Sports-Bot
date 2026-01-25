"""
Bot control routes for starting, stopping, and monitoring the trading bot.
Integrates with BotRunner for actual trading operations.
"""

import logging
from fastapi import APIRouter, HTTPException, status, BackgroundTasks

from src.api.deps import DbSession, OnboardedUser
from src.db.crud.global_settings import GlobalSettingsCRUD
from src.db.crud.polymarket_account import PolymarketAccountCRUD
from src.db.crud.activity_log import ActivityLogCRUD
from src.db.crud.sport_config import SportConfigCRUD
from src.db.crud.market_config import MarketConfigCRUD
from src.schemas.common import MessageResponse
from src.services.bot_runner import get_bot_runner, get_bot_status, BotState
from src.services.polymarket_client import PolymarketClient
from src.services.trading_engine import TradingEngine
from src.services.espn_service import ESPNService
from src.config import settings as app_settings


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/bot", tags=["Bot Control"])


async def _create_bot_dependencies(db, user_id, credentials: dict):
    """
    Creates and configures bot dependencies.
    
    Args:
        db: Database session
        user_id: User ID
        credentials: Decrypted wallet credentials
    
    Returns:
        Tuple of (polymarket_client, trading_engine, espn_service)
    """
    polymarket_client = PolymarketClient(
        private_key=credentials["private_key"],
        funder_address=credentials["funder_address"],
        api_key=credentials.get("api_key"),
        api_secret=credentials.get("api_secret"),
        passphrase=credentials.get("passphrase")
    )
    
    espn_service = ESPNService()
    
    # Load global settings
    global_settings = await GlobalSettingsCRUD.get_or_create(db, user_id)
    
    # Load sport configs into a dictionary keyed by sport
    sport_configs_list = await SportConfigCRUD.get_all_for_user(db, user_id)
    sport_configs = {config.sport: config for config in sport_configs_list}
    
    # Load market-specific configs into a dictionary keyed by condition_id
    market_configs_list = await MarketConfigCRUD.get_all_for_user(db, user_id, enabled_only=True)
    market_configs = {config.condition_id: config for config in market_configs_list}
    
    # Create trading engine with all configs
    trading_engine = TradingEngine(
        db=db,
        user_id=str(user_id),
        polymarket_client=polymarket_client,
        global_settings=global_settings,
        sport_configs=sport_configs,
        market_configs=market_configs
    )
    
    return polymarket_client, trading_engine, espn_service


@router.post("/start", response_model=MessageResponse)
async def start_bot(
    db: DbSession,
    current_user: OnboardedUser,
    background_tasks: BackgroundTasks
) -> MessageResponse:
    """
    Starts the trading bot for the authenticated user.
    Validates wallet connection and initializes bot runner.
    """
    credentials = await PolymarketAccountCRUD.get_decrypted_credentials(db, current_user.id)
    
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Wallet not connected. Please complete onboarding."
        )
    
    # Check if already running
    status_info = get_bot_status(current_user.id)
    if status_info and status_info.get("state") == BotState.RUNNING.value:
        return MessageResponse(message="Bot is already running")
    
    try:
        # Create dependencies
        polymarket_client, trading_engine, espn_service = await _create_bot_dependencies(
            db, current_user.id, credentials
        )
        
        # Get or create bot runner
        bot_runner = await get_bot_runner(
            user_id=current_user.id,
            polymarket_client=polymarket_client,
            trading_engine=trading_engine,
            espn_service=espn_service
        )
        
        # Initialize with user config
        await bot_runner.initialize(db, current_user.id)
        
        # Start bot in background
        background_tasks.add_task(bot_runner.start, db)
        
        # Update database flag
        await GlobalSettingsCRUD.set_bot_enabled(db, current_user.id, True)
        
        await ActivityLogCRUD.info(
            db,
            current_user.id,
            "BOT",
            "Trading bot started with real-time monitoring"
        )
        
        return MessageResponse(message="Bot started successfully")
        
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start bot: {str(e)}"
        )


@router.post("/stop", response_model=MessageResponse)
async def stop_bot(db: DbSession, current_user: OnboardedUser) -> MessageResponse:
    """
    Stops the trading bot for the authenticated user.
    Gracefully stops all monitoring and closes connections.
    """
    from src.services.bot_runner import _bot_instances
    
    bot_runner = _bot_instances.get(current_user.id)
    
    if bot_runner and bot_runner.state == BotState.RUNNING:
        await bot_runner.stop(db)
    
    # Update database flag
    await GlobalSettingsCRUD.set_bot_enabled(db, current_user.id, False)
    
    await ActivityLogCRUD.info(
        db,
        current_user.id,
        "BOT",
        "Trading bot stopped"
    )
    
    return MessageResponse(message="Bot stopped successfully")


@router.get("/status", response_model=dict)
async def get_bot_status_endpoint(db: DbSession, current_user: OnboardedUser) -> dict:
    """
    Returns detailed bot status including:
    - Running state
    - Tracked games
    - WebSocket connection status
    - Today's trading stats
    """
    settings = await GlobalSettingsCRUD.get_by_user_id(db, current_user.id)
    account = await PolymarketAccountCRUD.get_by_user_id(db, current_user.id)
    
    # Get live bot status if running
    bot_status = get_bot_status(current_user.id)
    
    if bot_status:
        return {
            **bot_status,
            "wallet_connected": account is not None and account.is_connected,
            "connection_error": account.connection_error if account else None,
            "poll_interval_seconds": settings.poll_interval_seconds if settings else 10,
            "max_daily_loss_usdc": float(settings.max_daily_loss_usdc) if settings else 100.0,
            "max_portfolio_exposure_usdc": float(settings.max_portfolio_exposure_usdc) if settings else 500.0,
            "discord_alerts_enabled": settings.discord_alerts_enabled if settings else False,
        }
    
    # Bot not running - return basic status
    return {
        "state": "stopped",
        "bot_enabled": settings.bot_enabled if settings else False,
        "wallet_connected": account is not None and account.is_connected,
        "connection_error": account.connection_error if account else None,
        "poll_interval_seconds": settings.poll_interval_seconds if settings else 10,
        "max_daily_loss_usdc": float(settings.max_daily_loss_usdc) if settings else 100.0,
        "max_portfolio_exposure_usdc": float(settings.max_portfolio_exposure_usdc) if settings else 500.0,
        "discord_alerts_enabled": settings.discord_alerts_enabled if settings else False,
        "tracked_games": 0,
        "trades_today": 0,
        "daily_pnl": 0.0,
    }


@router.post("/emergency-stop", response_model=dict)
async def emergency_stop(
    db: DbSession,
    current_user: OnboardedUser,
    close_positions: bool = True
) -> dict:
    """
    Emergency stop that immediately halts all bot activity.
    
    Args:
        close_positions: If True, attempts to close all open positions at market prices.
    
    Returns:
        Summary of shutdown actions including positions closed and P&L.
    """
    from src.services.bot_runner import _bot_instances
    from src.services.discord_notifier import discord_notifier
    
    bot_runner = _bot_instances.get(current_user.id)
    
    result = {
        "success": True,
        "message": "Emergency stop executed",
        "positions_closed": 0,
        "positions_failed": 0,
        "total_pnl": 0.0,
        "errors": []
    }
    
    if bot_runner:
        # Use full emergency shutdown with position closure
        shutdown_result = await bot_runner.emergency_shutdown(db, close_positions=close_positions)
        result.update(shutdown_result)
    else:
        # Bot not running, just ensure flag is off
        await discord_notifier.notify_error(
            "Emergency Stop Triggered",
            "Bot was not running but emergency stop requested",
            "emergency_stop"
        )
    
    # Ensure database flags are set
    await GlobalSettingsCRUD.set_bot_enabled(db, current_user.id, False)
    
    # Also set emergency_stop flag in settings
    await GlobalSettingsCRUD.update(db, current_user.id, emergency_stop=True)
    
    await ActivityLogCRUD.warning(
        db,
        current_user.id,
        "BOT",
        f"Emergency stop triggered - closed {result['positions_closed']} positions, "
        f"P&L: ${result['total_pnl']:.2f}"
    )
    
    return result


@router.post("/clear-emergency", response_model=MessageResponse)
async def clear_emergency_stop(db: DbSession, current_user: OnboardedUser) -> MessageResponse:
    """
    Clears the emergency stop flag, allowing the bot to be restarted.
    """
    await GlobalSettingsCRUD.update(db, current_user.id, emergency_stop=False)
    
    await ActivityLogCRUD.info(
        db,
        current_user.id,
        "BOT",
        "Emergency stop cleared - bot can be restarted"
    )
    
    return MessageResponse(message="Emergency stop cleared. Bot can now be restarted.")


@router.get("/sport-stats", response_model=dict)
async def get_sport_stats(current_user: OnboardedUser) -> dict:
    """
    Returns per-sport statistics including:
    - Trades today per sport
    - P&L per sport
    - Open positions per sport
    - Tracked games per sport
    """
    from src.services.bot_runner import _bot_instances
    
    bot_runner = _bot_instances.get(current_user.id)
    
    if not bot_runner:
        return {"sports": {}, "message": "Bot not running"}
    
    return {
        "sports": bot_runner.get_sport_stats(),
        "enabled_sports": bot_runner.enabled_sports,
        "paper_trading": bot_runner.dry_run
    }


@router.get("/tracked-games", response_model=list)
async def get_tracked_games(current_user: OnboardedUser) -> list:
    """
    Returns list of games currently being monitored by the bot.
    """
    bot_status = get_bot_status(current_user.id)
    
    if not bot_status:
        return []
    
    return bot_status.get("games", [])


@router.post("/paper-trading", response_model=MessageResponse)
async def toggle_paper_trading(
    db: DbSession,
    current_user: OnboardedUser,
    enabled: bool = True
) -> MessageResponse:
    """
    Toggles paper trading mode.
    
    Paper trading executes simulated trades without real money.
    Recommended for testing strategies before going live.
    
    Args:
        enabled: True for paper trading, False for live trading
    """
    from src.services.bot_runner import _bot_instances
    
    # Update database setting
    await GlobalSettingsCRUD.update(db, current_user.id, dry_run_mode=enabled)
    
    # Update running bot if exists
    bot_runner = _bot_instances.get(current_user.id)
    if bot_runner:
        bot_runner.dry_run = enabled
        bot_runner.polymarket_client.dry_run = enabled
    
    mode_str = "PAPER TRADING" if enabled else "LIVE TRADING"
    await ActivityLogCRUD.info(
        db,
        current_user.id,
        "BOT",
        f"Trading mode changed to {mode_str}"
    )
    
    return MessageResponse(message=f"Trading mode set to {mode_str}")


@router.get("/paper-trading", response_model=dict)
async def get_paper_trading_status(db: DbSession, current_user: OnboardedUser) -> dict:
    """
    Returns current paper trading status and simulated trades if in paper mode.
    """
    from src.services.bot_runner import _bot_instances
    
    settings = await GlobalSettingsCRUD.get_by_user_id(db, current_user.id)
    is_paper = settings.dry_run_mode if settings and hasattr(settings, 'dry_run_mode') else True
    
    result = {
        "paper_trading_enabled": is_paper,
        "mode": "PAPER" if is_paper else "LIVE",
        "simulated_trades": []
    }
    
    # Get simulated trades from running bot
    bot_runner = _bot_instances.get(current_user.id)
    if bot_runner and bot_runner.polymarket_client:
        simulated = getattr(bot_runner.polymarket_client, '_simulated_orders', {})
        result["simulated_trades"] = list(simulated.values())
    
    return result
