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
from src.schemas.common import MessageResponse
from src.services.bot_runner import get_bot_runner, get_bot_status, BotState
from src.services.polymarket_client import PolymarketClient
from src.services.trading_engine import TradingEngine
from src.services.espn_service import ESPNService
from src.core.encryption import decrypt_value
from src.config import settings as app_settings


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/bot", tags=["Bot Control"])


async def _create_bot_dependencies(db, user_id: int, credentials: dict):
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
    
    # TradingEngine needs db and config - simplified initialization
    trading_engine = TradingEngine(
        db=db,
        user_id=str(user_id),
        polymarket_client=polymarket_client,
        global_settings=None,  # Will be loaded by bot_runner
        sport_configs={}  # Will be loaded by bot_runner
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


@router.post("/emergency-stop", response_model=MessageResponse)
async def emergency_stop(db: DbSession, current_user: OnboardedUser) -> MessageResponse:
    """
    Emergency stop that immediately halts all bot activity.
    Attempts to close open positions at market prices.
    Use with caution.
    """
    from src.services.bot_runner import _bot_instances
    from src.services.discord_notifier import discord_notifier
    
    bot_runner = _bot_instances.get(current_user.id)
    
    if bot_runner:
        # Force stop
        await bot_runner.stop(db)
        
        # Notify via Discord
        await discord_notifier.notify_error(
            "Emergency Stop Triggered",
            "Bot has been emergency stopped by user",
            "emergency_stop"
        )
    
    # Ensure database flag is off
    await GlobalSettingsCRUD.set_bot_enabled(db, current_user.id, False)
    
    await ActivityLogCRUD.warning(
        db,
        current_user.id,
        "BOT",
        "Emergency stop triggered - all bot activity halted"
    )
    
    return MessageResponse(
        message="Emergency stop executed. Bot disabled. Review positions manually.",
        success=True
    )


@router.get("/tracked-games", response_model=list)
async def get_tracked_games(current_user: OnboardedUser) -> list:
    """
    Returns list of games currently being monitored by the bot.
    """
    bot_status = get_bot_status(current_user.id)
    
    if not bot_status:
        return []
    
    return bot_status.get("games", [])
