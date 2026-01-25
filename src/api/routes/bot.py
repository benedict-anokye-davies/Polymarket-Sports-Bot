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
    Supports both Kalshi and Polymarket platforms.

    Args:
        db: Database session
        user_id: User ID
        credentials: Decrypted wallet credentials

    Returns:
        Tuple of (trading_client, trading_engine, espn_service)
    """
    platform = credentials.get("platform", "polymarket")

    # Create the correct client based on platform
    if platform == "kalshi":
        from src.services.kalshi_client import KalshiClient
        trading_client = KalshiClient(
            api_key=credentials["api_key"],
            private_key=credentials["api_secret"]  # Kalshi uses api_secret as private key for signing
        )
        logger.info(f"Created KalshiClient for user {user_id}")
    else:
        trading_client = PolymarketClient(
            private_key=credentials["private_key"],
            funder_address=credentials["funder_address"],
            api_key=credentials.get("api_key"),
            api_secret=credentials.get("api_secret"),
            passphrase=credentials.get("passphrase")
        )
        logger.info(f"Created PolymarketClient for user {user_id}")

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
        polymarket_client=trading_client,  # Works with either client
        global_settings=global_settings,
        sport_configs=sport_configs,
        market_configs=market_configs
    )

    return trading_client, trading_engine, espn_service


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
    credentials = await PolymarketAccountCRUD.get_decrypted_credentials(db, current_user.id)

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

# In-memory store for bot configurations (per user)
_bot_configs: dict[str, dict] = {}


@router.get("/config", response_model=BotConfigResponse)
async def get_bot_config(db: DbSession, current_user: OnboardedUser) -> BotConfigResponse:
    """
    Get current bot configuration for the user.
    """
    from src.schemas.bot_config import GameSelection
    
    user_id = str(current_user.id)
    config = _bot_configs.get(user_id, {})
    
    status_info = get_bot_status(current_user.id)
    is_running = bool(status_info and status_info.get("state") == BotState.RUNNING.value)
    
    # Get simulation mode from database
    settings = await GlobalSettingsCRUD.get_by_user_id(db, current_user.id)
    simulation_mode = settings.dry_run_mode if settings and hasattr(settings, 'dry_run_mode') else True
    
    # Convert stored dict back to Pydantic models
    game_data = config.get("game")
    game = GameSelection(**game_data) if game_data else None
    
    params_data = config.get("parameters")
    params = TradingParameters(**params_data) if params_data else TradingParameters()
    
    return BotConfigResponse(
        is_running=is_running,
        sport=config.get("sport"),
        game=game,
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
    This does not start the bot - use /bot/start for that.
    """
    from datetime import datetime
    from src.services.bot_runner import _bot_instances
    
    user_id = str(current_user.id)
    
    _bot_configs[user_id] = {
        "sport": request.sport,
        "game": request.game.model_dump(),
        "parameters": request.parameters.model_dump(),
        "simulation_mode": request.simulation_mode,
        "last_updated": datetime.now().isoformat()
    }
    
    # Persist simulation mode to database
    await GlobalSettingsCRUD.update(db, current_user.id, dry_run_mode=request.simulation_mode)
    
    # Update running bot if exists
    bot_runner = _bot_instances.get(current_user.id)
    if bot_runner:
        bot_runner.dry_run = request.simulation_mode
        if bot_runner.polymarket_client:
            bot_runner.polymarket_client.dry_run = request.simulation_mode
    
    # Log the configuration change
    mode_str = "PAPER" if request.simulation_mode else "LIVE"
    await ActivityLogCRUD.info(
        db,
        current_user.id,
        "BOT_CONFIG",
        f"[{mode_str}] Configuration updated for {request.sport}: {request.game.away_team} @ {request.game.home_team}"
    )
    
    status_info = get_bot_status(current_user.id)
    is_running = bool(status_info and status_info.get("state") == BotState.RUNNING.value)
    
    return BotConfigResponse(
        is_running=is_running,
        sport=request.sport,
        game=request.game,
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
    config = _bot_configs.get(user_id, {})
    
    # Get position counts
    open_positions = await PositionCRUD.count_open_for_user(db, current_user.id)
    today_pnl = await PositionCRUD.get_daily_pnl(db, current_user.id)
    today_trades = await PositionCRUD.count_today_trades(db, current_user.id)
    
    game = config.get("game", {})
    current_game = f"{game.get('away_team', '')} @ {game.get('home_team', '')}" if game else None
    
    return BotStatusResponse(
        is_running=is_running,
        current_game=current_game if game else None,
        current_sport=config.get("sport"),
        active_positions=open_positions,
        pending_orders=0,  # TODO: Track pending orders
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
    credentials = await PolymarketAccountCRUD.get_decrypted_credentials(db, current_user.id)
    
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Wallet not connected. Please complete onboarding."
        )
    
    try:
        if request.platform.lower() == "kalshi":
            # Use Kalshi client
            from src.services.kalshi_client import KalshiClient
            
            kalshi_key = credentials.get("kalshi_api_key")
            kalshi_private = credentials.get("kalshi_private_key")
            
            if not kalshi_key or not kalshi_private:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Kalshi credentials not configured"
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
            # Use Polymarket client
            private_key = credentials.get("private_key")
            funder_address = credentials.get("funder_address")
            
            if not private_key or not funder_address:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Polymarket wallet not configured. Please complete onboarding."
                )
            
            client = PolymarketClient(
                private_key=private_key,
                funder_address=funder_address,
                api_key=credentials.get("api_key"),
                api_secret=credentials.get("api_secret"),
                passphrase=credentials.get("passphrase")
            )
            
            result = await client.place_order(
                token_id=request.ticker,
                side=request.side.upper(),
                price=request.price,
                size=request.size
            )
            
            await ActivityLogCRUD.info(
                db,
                current_user.id,
                "POLYMARKET_ORDER",
                f"Placed {request.side} order: {request.ticker} @ {request.price}"
            )
            
            return PlaceOrderResponse(
                success=True,
                order_id=result.get("orderID", result.get("order_id")),
                status=result.get("status", "pending"),
                filled_size=result.get("filled_size", 0),
                message="Order placed on Polymarket"
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
    
    Args:
        sport: Sport identifier (nba, nfl, mlb, nhl, soccer, ncaab, etc.)
    
    Returns:
        List of games with current state
    """
    import httpx
    
    SPORT_ENDPOINTS = {
        "nba": "basketball/nba",
        "nfl": "football/nfl",
        "mlb": "baseball/mlb",
        "nhl": "hockey/nhl",
        "soccer": "soccer/usa.1",
        "ncaab": "basketball/mens-college-basketball",
        "ncaaf": "football/college-football",
        "tennis": "tennis/atp",
        "mma": "mma/ufc",
        "cricket": "cricket",
        "ufc": "mma/ufc",
    }
    
    sport_lower = sport.lower()
    endpoint = SPORT_ENDPOINTS.get(sport_lower)
    
    if not endpoint:
        logger.warning(f"Unsupported sport requested: {sport}")
        return []
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            url = f"https://site.web.api.espn.com/apis/site/v2/sports/{endpoint}/scoreboard"
            response = await client.get(url)
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
                
                # Show appropriate period info based on status
                if game_status == 'upcoming':
                    current_period = 'Pre-game'
                    clock = ''
                elif game_status == 'final':
                    current_period = 'Final'
                    clock = ''
                else:
                    current_period = f"Q{period}" if sport_lower in ['nba', 'nfl'] else f"P{period}"
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

