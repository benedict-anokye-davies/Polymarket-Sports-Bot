"""
Bot control routes for starting, stopping, and monitoring the trading bot.
Integrates with BotRunner for actual trading operations.
"""

import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import DbSession, OnboardedUser
from src.db.crud.global_settings import GlobalSettingsCRUD
from src.db.crud.account import AccountCRUD
from src.db.crud.activity_log import ActivityLogCRUD
from src.db.crud.sport_config import SportConfigCRUD
from src.db.crud.market_config import MarketConfigCRUD
from src.schemas.common import MessageResponse
from src.services.bot_runner import get_bot_runner, get_bot_status, BotState

from src.services.trading_engine import TradingEngine
from src.services.espn_service import ESPNService
from src.config import settings as app_settings


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/bot", tags=["Bot Control"])


async def _create_bot_dependencies(db, user_id, credentials: dict):
    """
    Creates and configures bot dependencies.
    Supports both Kalshi and Polymarket platforms.

    Args:
        db: Database session
        user_id: User ID
        credentials: Decrypted wallet credentials

    Returns:
        Tuple of (trading_client, trading_engine, espn_service)
    """
    platform = credentials.get("platform", "polymarket")
    environment = credentials.get("environment", "production")

    # Create the correct client based on platform
    if platform == "kalshi":
        from src.services.kalshi_client import KalshiClient
        trading_client = KalshiClient(
            api_key=credentials["api_key"],
            # Kalshi private key might be stored as 'private_key' OR 'api_secret' depending on onboarding
            private_key_pem=credentials.get("private_key") or credentials.get("api_secret")
        )
        logger.info(f"Created KalshiClient for user {user_id} - REAL MONEY TRADING")
    else:
        # Polymarket support removed
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Polymarket is no longer supported. Please use Kalshi."
        )

    espn_service = ESPNService()

    # Load global settings
    global_settings = await GlobalSettingsCRUD.get_or_create(db, user_id)

    # Load sport configs into a dictionary keyed by sport
    sport_configs_list = await SportConfigCRUD.get_all_for_user(db, user_id)
    sport_configs = {config.sport: config for config in sport_configs_list}

    # Load market-specific configs into a dictionary keyed by condition_id
    market_configs_list = await MarketConfigCRUD.get_enabled_for_user(db, user_id)
    market_configs = {config.condition_id: config for config in market_configs_list}

    # Create trading engine with all configs
    trading_engine = TradingEngine(
        db=db,
        user_id=str(user_id),
        trading_client=trading_client,  # Works with either Polymarket or Kalshi client
        global_settings=global_settings,
        sport_configs=sport_configs,
        market_configs=market_configs
    )

    return trading_client, trading_engine, espn_service


@router.get("/leagues", response_model=list)
async def get_available_leagues() -> list:
    """
    Returns all available sports leagues for trading.
    Includes both American sports and international soccer leagues.
    """
    return ESPNService.get_available_leagues()


@router.get("/soccer-leagues", response_model=list)
async def get_soccer_leagues() -> list:
    """
    Returns all available soccer leagues for the league selector.
    Includes EPL, La Liga, Champions League, etc.
    """
    return ESPNService.get_soccer_leagues()


@router.get("/categories", response_model=list)
async def get_sport_categories() -> list:
    """
    Returns all available sport categories with their leagues.
    Used by frontend to build category tabs/dropdowns.
    
    Categories include: basketball, football, baseball, hockey,
    soccer (multiple regions), tennis, golf, combat, motorsports.
    """
    return ESPNService.get_all_categories()


@router.get("/categories/{category}/leagues", response_model=list)
async def get_leagues_by_category(category: str) -> list:
    """
    Returns leagues for a specific sport category.
    
    Args:
        category: Category key (e.g., 'basketball', 'hockey', 'soccer_england')
    
    Valid categories:
        - basketball: NBA, WNBA, NCAA, EuroLeague, NBL, etc.
        - football: NFL, NCAA, CFL, XFL
        - baseball: MLB, NCAA, NPB, KBO
        - hockey: NHL, AHL, KHL, SHL
        - soccer_england: EPL, Championship, FA Cup, etc.
        - soccer_spain: La Liga, La Liga 2, Copa del Rey
        - soccer_germany: Bundesliga, 2. Bundesliga, DFB-Pokal
        - soccer_italy: Serie A, Serie B, Coppa Italia
        - soccer_france: Ligue 1, Ligue 2, Coupe de France
        - soccer_europe_other: Eredivisie, Liga Portugal, etc.
        - soccer_uefa: UCL, Europa League, Conference League
        - soccer_americas: MLS, Brasileirao, Liga MX, etc.
        - soccer_asia: J League, K League, Saudi Pro League
        - soccer_international: World Cup, Copa America, etc.
        - tennis: ATP, WTA, Grand Slams
        - golf: PGA, LPGA, European Tour, LIV
        - combat: UFC, Bellator, PFL, Boxing
        - motorsports: F1, NASCAR, IndyCar, MotoGP
        - other: Rugby, Cricket, AFL
    """
    leagues = ESPNService.get_leagues_by_category(category)
    if not leagues:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Category '{category}' not found or has no leagues"
        )
    return leagues


@router.post("/start", response_model=MessageResponse)
async def start_bot(
    db: DbSession,
    current_user: OnboardedUser,
    background_tasks: BackgroundTasks
) -> MessageResponse:
    """
    Starts the trading bot for the authenticated user.
    Validates credentials and initializes bot runner.
    Supports both Kalshi and Polymarket platforms.
    """
    credentials = await AccountCRUD.get_decrypted_credentials(db, current_user.id)

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No credentials found. Please complete onboarding."
        )

    platform = credentials.get("platform", "polymarket")

    # Validate platform-specific credentials
    if platform == "kalshi":
        if not credentials.get("api_key") or not credentials.get("api_secret"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Kalshi API credentials not configured. Please update in Settings."
            )
    else:
        if not credentials.get("private_key") or not credentials.get("funder_address"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Polymarket wallet not connected. Please complete onboarding."
            )
    
    # Check if already running
    status_info = get_bot_status(current_user.id)
    if status_info and status_info.get("state") == BotState.RUNNING.value:
        return MessageResponse(message="Bot is already running")
    
    trading_client = None
    trading_engine = None
    espn_service = None
    
    try:
        # Create dependencies
        trading_client, trading_engine, espn_service = await _create_bot_dependencies(
            db, current_user.id, credentials
        )
        
        # Get or create bot runner
        bot_runner = await get_bot_runner(
            user_id=current_user.id,
            trading_client=trading_client,
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
        
        # Cleanup resources on error
        if trading_client and hasattr(trading_client, 'close'):
            try:
                await trading_client.close()
            except Exception as close_err:
                logger.warning(f"Error closing trading client: {close_err}")
        
        if espn_service and hasattr(espn_service, 'close'):
            try:
                await espn_service.close()
            except Exception as close_err:
                logger.warning(f"Error closing ESPN service: {close_err}")
        
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
    account = await AccountCRUD.get_by_user_id(db, current_user.id)
    
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
        "paper_trading": False
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
    Paper trading is not supported. All trading uses real money.
    This endpoint is kept for API compatibility but always returns live mode.
    """
    await ActivityLogCRUD.info(
        db,
        current_user.id,
        "BOT",
        "Trading mode is LIVE TRADING (paper trading not supported)"
    )

    return MessageResponse(message="Trading mode is LIVE TRADING. Paper trading is not supported.")


@router.get("/paper-trading", response_model=dict)
async def get_paper_trading_status(db: DbSession, current_user: OnboardedUser) -> dict:
    """
    Returns trading mode status. Always live - paper trading not supported.
    """
    return {
        "paper_trading_enabled": False,
        "mode": "LIVE",
        "simulated_trades": []
    }


# =============================================================================
# Bot Configuration Endpoints (New)
# =============================================================================

from src.schemas.bot_config import (
    BotConfigRequest,
    BotConfigResponse,
    TradingParameters,
    PlaceOrderRequest,
    PlaceOrderResponse,
    MarketDataResponse,
    BotStatusResponse
)

# In-memory cache for bot configurations (per user) - backed by database
_bot_configs: dict[str, dict] = {}


async def _load_config_from_db(db: AsyncSession, user_id: str) -> dict | None:
    """
    Loads bot config from database into memory cache.
    Called on first access or after server restart.
    """
    from uuid import UUID
    config = await GlobalSettingsCRUD.get_bot_config(db, UUID(user_id))
    if config:
        _bot_configs[user_id] = config
    return config


@router.get("/config", response_model=BotConfigResponse)
async def get_bot_config(db: DbSession, current_user: OnboardedUser) -> BotConfigResponse:
    """
    Get current bot configuration for the user.
    Loads from database if not in memory cache.
    """
    from src.schemas.bot_config import GameSelection
    
    user_id = str(current_user.id)
    
    # Load from database if not in cache
    if user_id not in _bot_configs:
        await _load_config_from_db(db, user_id)
    
    config = _bot_configs.get(user_id, {})
    
    status_info = get_bot_status(current_user.id)
    is_running = bool(status_info and status_info.get("state") == BotState.RUNNING.value)
    
    # All trading is live
    simulation_mode = False

    # Convert stored dict back to Pydantic models
    game_data = config.get("game")
    game = GameSelection(**game_data) if game_data else None
    
    # Get additional games
    all_games = config.get("games", [])
    additional_games = None
    if all_games and len(all_games) > 1:
        additional_games = [GameSelection(**g) for g in all_games[1:]]
    
    params_data = config.get("parameters")
    params = TradingParameters(**params_data) if params_data else None
    
    return BotConfigResponse(
        is_running=is_running,
        sport=config.get("sport"),
        game=game,
        additional_games=additional_games,
        parameters=params,
        simulation_mode=simulation_mode,
        last_updated=config.get("last_updated")
    )


@router.post("/config", response_model=BotConfigResponse)
async def save_bot_config(
    db: DbSession,
    current_user: OnboardedUser,
    request: BotConfigRequest
) -> BotConfigResponse:
    """
    Save bot configuration with trading parameters.
    Supports multiple games from different sports via additional_games array.
    This does not start the bot - use /bot/start for that.
    """
    from datetime import datetime
    from src.services.bot_runner import _bot_instances
    
    user_id = str(current_user.id)
    
    # Build list of all games to track
    all_games = []
    if request.game:
        all_games.append(request.game.model_dump())
    
    # Add additional games from other sports
    if request.additional_games:
        for game in request.additional_games:
            all_games.append(game.model_dump())
    
    _bot_configs[user_id] = {
        "sport": request.sport,
        "game": request.game.model_dump() if request.game else None,
        "games": all_games,  # Store ALL games for multi-sport tracking
        "parameters": request.parameters.model_dump() if request.parameters else None,
        "simulation_mode": request.simulation_mode,
        "last_updated": datetime.now().isoformat()
    }
    
    # Persist to database for recovery after server restart
    await GlobalSettingsCRUD.save_bot_config(db, current_user.id, _bot_configs[user_id])
    
    # Log the configuration change
    games_count = len(all_games)
    if games_count > 1:
        log_msg = f"[LIVE] Configuration updated: {games_count} games selected across multiple sports"
    elif games_count == 1 and request.game:
        log_msg = f"[LIVE] Configuration updated for {request.sport}: {request.game.away_team} @ {request.game.home_team}"
    else:
        log_msg = f"[LIVE] Game selection cleared"
    
    await ActivityLogCRUD.info(
        db,
        current_user.id,
        "BOT_CONFIG",
        log_msg
    )
    
    status_info = get_bot_status(current_user.id)
    is_running = bool(status_info and status_info.get("state") == BotState.RUNNING.value)
    
    # Build additional_games list for response
    additional_games_response = None
    if request.additional_games:
        additional_games_response = request.additional_games
    
    return BotConfigResponse(
        is_running=is_running,
        sport=request.sport,
        game=request.game,
        additional_games=additional_games_response,
        parameters=request.parameters,
        simulation_mode=request.simulation_mode,
        last_updated=_bot_configs[user_id]["last_updated"]
    )


@router.get("/status/detailed", response_model=BotStatusResponse)
async def get_detailed_bot_status(
    db: DbSession,
    current_user: OnboardedUser
) -> BotStatusResponse:
    """
    Get detailed bot status including positions and P&L.
    """
    from src.db.crud.position import PositionCRUD
    
    status_info = get_bot_status(current_user.id)
    is_running = bool(status_info and status_info.get("state") == BotState.RUNNING.value)
    
    user_id = str(current_user.id)
    
    # Load from database if not in cache
    if user_id not in _bot_configs:
        await _load_config_from_db(db, user_id)
    
    config = _bot_configs.get(user_id, {})
    
    # Get position counts
    open_positions = await PositionCRUD.count_open_for_user(db, current_user.id)
    today_pnl = await PositionCRUD.get_daily_pnl(db, current_user.id)
    today_trades = await PositionCRUD.count_today_trades(db, current_user.id)
    
    # Get pending orders count from bot runner status
    pending_orders = status_info.get("pending_orders", 0) if status_info else 0
    
    game = config.get("game", {})
    current_game = f"{game.get('away_team', '')} @ {game.get('home_team', '')}" if game else None
    
    return BotStatusResponse(
        is_running=is_running,
        current_game=current_game if game else None,
        current_sport=config.get("sport"),
        active_positions=open_positions,
        pending_orders=pending_orders,
        today_pnl=float(today_pnl) if today_pnl else 0.0,
        today_trades=today_trades
    )


@router.post("/order", response_model=PlaceOrderResponse)
async def place_manual_order(
    db: DbSession,
    current_user: OnboardedUser,
    request: PlaceOrderRequest
) -> PlaceOrderResponse:
    """
    Place a manual order on Kalshi or Polymarket.
    Requires wallet to be connected.
    """
    credentials = await AccountCRUD.get_decrypted_credentials(db, current_user.id)
    
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Wallet not connected. Please complete onboarding."
        )
    
    try:
        if request.platform.lower() == "kalshi":
            # Use Kalshi client
            from src.services.kalshi_client import KalshiClient
            
            kalshi_key = credentials.get("api_key")
            kalshi_private = credentials.get("api_secret")
            
            if not kalshi_key or not kalshi_private:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Kalshi credentials not configured. Please complete onboarding with Kalshi API key and secret."
                )
            
            client = KalshiClient(kalshi_key, kalshi_private)
            
            order = await client.place_order(
                ticker=request.ticker,
                side=request.side,
                yes_no=request.outcome,
                price=request.price,
                size=int(request.size)
            )
            
            await client.close()
            
            await ActivityLogCRUD.info(
                db,
                current_user.id,
                "KALSHI_ORDER",
                f"Placed {request.side} order: {request.ticker} @ {request.price}"
            )
            
            return PlaceOrderResponse(
                success=True,
                order_id=order.order_id,
                status=order.status,
                filled_size=order.filled_size,
                message=f"Order placed on Kalshi"
            )
        
        elif request.platform.lower() == "polymarket":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Polymarket is no longer supported."
            )
        
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown platform: {request.platform}. Use 'kalshi' or 'polymarket'"
            )
    
    except Exception as e:
        logger.error(f"Order placement failed: {e}")
        return PlaceOrderResponse(
            success=False,
            status="failed",
            message=str(e)
        )


# =============================================================================
# Live Games from ESPN (Real-Time Data) - PUBLIC ENDPOINT
# =============================================================================

@router.get("/live-games/{sport}", response_model=list)
async def get_live_espn_games(
    sport: str
) -> list:
    """
    Fetch live and upcoming games directly from ESPN API.
    Returns real-time game data including scores, periods, and times.

    This endpoint is PUBLIC - no authentication required since ESPN data is public.

    Supports ALL 100+ leagues/sports from ESPNService including:
    - Basketball: nba, wnba, ncaab, ncaaw, euroleague, etc.
    - Football: nfl, ncaaf, cfl, xfl
    - Baseball: mlb, ncaa_baseball, npb, kbo
    - Hockey: nhl, ahl, khl, ncaa_hockey
    - Soccer: epl, laliga, bundesliga, seriea, ligue1, mls, ucl, etc.
    - And many more...

    Args:
        sport: Sport/league identifier (nba, nfl, epl, ncaab, etc.)

    Returns:
        List of games with current state
    """
    import httpx

    sport_lower = sport.lower()

    # Use the full ESPNService configuration
    endpoint = ESPNService.SPORT_ENDPOINTS.get(sport_lower)

    if not endpoint:
        logger.warning(f"Unsupported sport/league requested: {sport}")
        return []

    # CRITICAL: Add groups parameter for college sports to fetch ALL games
    # Without this, ESPN only returns Top 25 ranked teams for college sports
    SPORT_GROUPS = {
        "ncaab": "50",       # Division I Men's Basketball - ALL teams
        "ncaaw": "50",       # Division I Women's Basketball - ALL teams
        "ncaaf": "80",       # FBS Football - ALL teams
        "ncaa_baseball": "50",
        "ncaa_hockey": "50",
    }

    params = {}
    if sport_lower in SPORT_GROUPS:
        params["groups"] = SPORT_GROUPS[sport_lower]
        params["limit"] = "200"  # Fetch more games

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            url = f"https://site.web.api.espn.com/apis/site/v2/sports/{endpoint}/scoreboard"
            response = await client.get(url, params=params if params else None)
            response.raise_for_status()

            data = response.json()
            events = data.get("events", [])
            
            games = []
            for event in events:
                # Parse game state
                status = event.get("status", {})
                status_type = status.get("type", {})
                competitions = event.get("competitions", [{}])[0]
                competitors = competitions.get("competitors", [])
                
                home_team = None
                away_team = None
                home_score = 0
                away_score = 0
                
                for comp in competitors:
                    if comp.get("homeAway") == "home":
                        home_team = {
                            "name": comp.get("team", {}).get("displayName", "TBD"),
                            "abbreviation": comp.get("team", {}).get("abbreviation", ""),
                        }
                        home_score = int(comp.get("score", 0) or 0)
                    elif comp.get("homeAway") == "away":
                        away_team = {
                            "name": comp.get("team", {}).get("displayName", "TBD"),
                            "abbreviation": comp.get("team", {}).get("abbreviation", ""),
                        }
                        away_score = int(comp.get("score", 0) or 0)
                
                state = status_type.get("state", "")
                is_live = state == "in"
                is_finished = state == "post"
                
                game_status = 'live' if is_live else ('final' if is_finished else 'upcoming')
                
                period = status.get("period", 0)
                clock_display = status.get("displayClock", "0:00")
                
                # Show appropriate period info based on status and sport type
                if game_status == 'upcoming':
                    current_period = 'Pre-game'
                    clock = ''
                elif game_status == 'final':
                    current_period = 'Final'
                    clock = ''
                else:
                    # Determine period label based on sport type
                    if sport_lower in ['nba', 'wnba', 'nba_gleague', 'nfl', 'ncaaf', 'cfl', 'xfl', 'usfl']:
                        current_period = f"Q{period}"
                    elif sport_lower in ['ncaab', 'ncaaw'] or sport_lower in ESPNService.CLOCK_COUNTUP_SPORTS:
                        # College basketball uses halves, soccer uses halves
                        current_period = f"H{period}" if period <= 2 else f"OT{period-2}"
                    elif sport_lower in ['nhl', 'ahl', 'khl', 'shl', 'ncaa_hockey', 'iihf']:
                        current_period = f"P{period}"
                    elif sport_lower in ['mlb', 'ncaa_baseball', 'npb', 'kbo']:
                        current_period = f"Inning {period}"
                    else:
                        current_period = f"P{period}"
                    clock = clock_display
                
                start_time = event.get("date")
                
                games.append({
                    'id': event.get("id", ""),
                    'homeTeam': home_team['name'] if home_team else 'TBD',
                    'awayTeam': away_team['name'] if away_team else 'TBD',
                    'homeAbbr': home_team['abbreviation'] if home_team else '',
                    'awayAbbr': away_team['abbreviation'] if away_team else '',
                    'homeScore': home_score,
                    'awayScore': away_score,
                    'startTime': start_time,
                    'status': game_status,
                    'currentPeriod': current_period,
                    'clock': clock,
                    'name': event.get("name", ""),
                    'shortName': event.get("shortName", ""),
                    'homeOdds': 0.50,
                    'awayOdds': 0.50,
                    'volume': 0,
                })
            
            logger.info(f"Fetched {len(games)} {sport.upper()} games from ESPN")
            return games
            
    except Exception as e:
        logger.error(f"Failed to fetch ESPN games for {sport}: {e}")
        return []


@router.get("/markets/{platform}/{sport}", response_model=list)
async def get_available_markets(
    platform: str,
    sport: str,
    current_user: OnboardedUser
) -> list:
    """
    Fetch available sports markets from Kalshi or Polymarket.
    
    Args:
        platform: 'kalshi' or 'polymarket'
        sport: Sport identifier (nba, nfl, mlb, etc.)
    """
    try:
        if platform.lower() == "kalshi":
            from src.services.kalshi_client import KalshiClient
            
            # For market discovery, we don't need auth
            import httpx
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    "https://api.elections.kalshi.com/trade-api/v2/markets",
                    params={
                        "category": "Sports",
                        "series_ticker": sport.upper(),
                        "status": "open",
                        "limit": 50
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return data.get("markets", [])
                else:
                    return []
        
        elif platform.lower() == "polymarket":
            import httpx
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Query Gamma API for sports markets
                response = await client.get(
                    "https://gamma-api.polymarket.com/markets",
                    params={
                        "tag": sport.lower(),
                        "active": "true",
                        "limit": 50
                    }
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    return []
        
        else:
            return []
    
    except Exception as e:
        logger.error(f"Failed to fetch markets: {e}")
        return []


@router.post("/reconcile", response_model=dict)
async def manual_reconciliation(
    db: DbSession,
    current_user: OnboardedUser
) -> dict:
    """
    Manually trigger position reconciliation.
    
    Checks for:
    - Orphaned orders (on exchange but not in database)
    - Ghost positions (in database but not on exchange)
    - Position size mismatches
    
    Returns:
        Reconciliation results with any discrepancies found.
    """
    from src.services.position_reconciler import PositionReconciler
    from src.services.kalshi_client import KalshiClient
    from src.db.crud.polymarket_account import PolymarketAccountCRUD
    
    try:
        # Get user credentials
        credentials = await PolymarketAccountCRUD.get_decrypted_credentials(
            db, current_user.id
        )
        
        if not credentials:
            return {
                "success": False,
                "error": "No trading credentials configured"
            }
        
        # Create client
        if credentials.get("platform") == "kalshi":
            client = KalshiClient(
                api_key=credentials["api_key"],
                private_key_pem=credentials["api_secret"],
            )
        else:
            return {
                "success": False,
                "error": "Reconciliation currently only supported for Kalshi"
            }
        
        # Run reconciliation
        reconciler = PositionReconciler(db, current_user.id, kalshi_client=client)
        result = await reconciler.reconcile()
        
        await client.close()
        
        # Extract kalshi results
        kalshi_result = result.get("kalshi", {})
        
        # Log the reconciliation
        from src.db.crud.activity_log import ActivityLogCRUD
        await ActivityLogCRUD.info(
            db,
            current_user.id,
            "RECONCILIATION",
            f"Manual reconciliation completed: {result.get('total_synced', 0)} synced, "
            f"{result.get('total_recovered', 0)} recovered, "
            f"{result.get('total_closed', 0)} closed",
            details={
                "synced": result.get('total_synced', 0),
                "recovered": result.get('total_recovered', 0),
                "closed": result.get('total_closed', 0)
            }
        )
        
        return {
            "success": True,
            "timestamp": result.get('reconciled_at'),
            "polymarket": result.get('polymarket'),
            "kalshi": kalshi_result,
            "total_synced": result.get('total_synced', 0),
            "total_recovered": result.get('total_recovered', 0),
            "total_closed": result.get('total_closed', 0),
            "errors": result.get('errors', [])
        }
        
    except Exception as e:
        logger.error(f"Reconciliation failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@router.get("/reconcile/status", response_model=dict)
async def get_reconciliation_status(
    db: DbSession,
    current_user: OnboardedUser
) -> dict:
    """
    Get quick reconciliation status without running full reconciliation.
    
    Returns basic counts of exchange vs database positions.
    """
    from src.services.position_reconciler import PositionReconciler
    from src.services.kalshi_client import KalshiClient
    from src.db.crud.polymarket_account import PolymarketAccountCRUD
    
    try:
        credentials = await PolymarketAccountCRUD.get_decrypted_credentials(
            db, current_user.id
        )
        
        if not credentials or credentials.get("platform") != "kalshi":
            return {
                "status": "not_available",
                "message": "Reconciliation only available for Kalshi"
            }
        
        client = KalshiClient(
            api_key=credentials["api_key"],
            private_key_pem=credentials["api_secret"],
        )

        # Get quick status by comparing counts
        try:
            exchange_positions = await client.get_positions()
            from src.db.crud.position import PositionCRUD
            db_positions = await PositionCRUD.get_open_for_user(db, current_user.id)
            
            await client.close()
            
            return {
                "status": "ok",
                "exchange_positions": len(exchange_positions) if exchange_positions else 0,
                "database_positions": len(db_positions),
                "discrepancy": len(exchange_positions or []) != len(db_positions),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            await client.close()
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

