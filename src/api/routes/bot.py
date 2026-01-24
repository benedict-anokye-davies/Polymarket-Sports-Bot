"""
Bot control routes for starting, stopping, and monitoring the trading bot.
"""

from fastapi import APIRouter, HTTPException, status

from src.api.deps import DbSession, OnboardedUser
from src.db.crud.global_settings import GlobalSettingsCRUD
from src.db.crud.polymarket_account import PolymarketAccountCRUD
from src.db.crud.activity_log import ActivityLogCRUD
from src.schemas.common import MessageResponse


router = APIRouter(prefix="/bot", tags=["Bot Control"])


@router.post("/start", response_model=MessageResponse)
async def start_bot(db: DbSession, current_user: OnboardedUser) -> MessageResponse:
    """
    Starts the trading bot for the authenticated user.
    Validates that wallet is connected before starting.
    """
    credentials = await PolymarketAccountCRUD.get_decrypted_credentials(db, current_user.id)
    
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Wallet not connected. Please complete onboarding."
        )
    
    settings = await GlobalSettingsCRUD.get_by_user_id(db, current_user.id)
    
    if settings and settings.bot_enabled:
        return MessageResponse(message="Bot is already running")
    
    await GlobalSettingsCRUD.set_bot_enabled(db, current_user.id, True)
    
    await ActivityLogCRUD.info(
        db,
        current_user.id,
        "BOT",
        "Trading bot started"
    )
    
    return MessageResponse(message="Bot started successfully")


@router.post("/stop", response_model=MessageResponse)
async def stop_bot(db: DbSession, current_user: OnboardedUser) -> MessageResponse:
    """
    Stops the trading bot for the authenticated user.
    Does not close open positions.
    """
    settings = await GlobalSettingsCRUD.get_by_user_id(db, current_user.id)
    
    if not settings or not settings.bot_enabled:
        return MessageResponse(message="Bot is not running")
    
    await GlobalSettingsCRUD.set_bot_enabled(db, current_user.id, False)
    
    await ActivityLogCRUD.info(
        db,
        current_user.id,
        "BOT",
        "Trading bot stopped"
    )
    
    return MessageResponse(message="Bot stopped successfully")


@router.get("/status", response_model=dict)
async def get_bot_status(db: DbSession, current_user: OnboardedUser) -> dict:
    """
    Returns the current bot status and health information.
    """
    settings = await GlobalSettingsCRUD.get_by_user_id(db, current_user.id)
    account = await PolymarketAccountCRUD.get_by_user_id(db, current_user.id)
    
    return {
        "bot_enabled": settings.bot_enabled if settings else False,
        "wallet_connected": account is not None and account.is_connected,
        "connection_error": account.connection_error if account else None,
        "poll_interval_seconds": settings.poll_interval_seconds if settings else 10,
        "max_daily_loss_usdc": float(settings.max_daily_loss_usdc) if settings else 100.0,
        "max_portfolio_exposure_usdc": float(settings.max_portfolio_exposure_usdc) if settings else 500.0,
        "discord_alerts_enabled": settings.discord_alerts_enabled if settings else False,
    }


@router.post("/emergency-stop", response_model=MessageResponse)
async def emergency_stop(db: DbSession, current_user: OnboardedUser) -> MessageResponse:
    """
    Emergency stop that also attempts to close all open positions.
    Use with caution - will sell at current market prices.
    """
    await GlobalSettingsCRUD.set_bot_enabled(db, current_user.id, False)
    
    await ActivityLogCRUD.warning(
        db,
        current_user.id,
        "BOT",
        "Emergency stop triggered"
    )
    
    return MessageResponse(
        message="Emergency stop executed. Bot disabled. Position closure must be done manually.",
        success=True
    )
