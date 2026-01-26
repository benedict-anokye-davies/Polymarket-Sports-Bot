"""
Main bot runner service that orchestrates the trading loop.
Coordinates ESPN game state, Polymarket prices, and trade execution.
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.services.polymarket_ws import PolymarketWebSocket, PriceUpdate
from src.services.polymarket_client import PolymarketClient
from src.services.espn_service import ESPNService
from src.services.trading_engine import TradingEngine
from src.services.market_discovery import market_discovery, DiscoveredMarket
from src.services.discord_notifier import discord_notifier
from src.db.crud.tracked_market import TrackedMarketCRUD
from src.db.crud.position import PositionCRUD
from src.db.crud.global_settings import GlobalSettingsCRUD
from src.db.crud.sport_config import SportConfigCRUD
from src.db.crud.activity_log import ActivityLogCRUD
from src.core.exceptions import TradingError


logger = logging.getLogger(__name__)


class BotState(Enum):
    """Bot operational states."""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass
class TrackedGame:
    """A game being actively tracked by the bot."""
    espn_event_id: str
    sport: str
    home_team: str
    away_team: str
    market: DiscoveredMarket
    baseline_price: float | None = None
    current_price: float | None = None
    game_status: str = "pre"
    period: int = 0
    clock: str = ""
    home_score: int = 0
    away_score: int = 0
    last_update: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    has_position: bool = False
    position_id: UUID | None = None
    # Which team to bet on: "home", "away", or "both"
    selected_side: str = "home"


@dataclass
class SportStats:
    """Per-sport statistics tracking."""
    sport: str
    trades_today: int = 0
    daily_pnl: float = 0.0
    open_positions: int = 0
    tracked_games: int = 0
    enabled: bool = True
    priority: int = 1
    max_daily_loss: float = 50.0
    max_exposure: float = 200.0


class BotRunner:
    """
    Main trading bot runner that coordinates all services.
    
    Responsibilities:
    - Poll ESPN for live game state
    - Subscribe to Polymarket WebSocket for price updates
    - Evaluate entry/exit conditions via TradingEngine
    - Execute trades via PolymarketClient
    - Send notifications via Discord
    - Log all activity to database
    - Support multiple sports simultaneously with per-sport risk limits
    - Paper trading mode for safe testing
    - Position recovery on restart
    """
    
    # Polling intervals
    ESPN_POLL_INTERVAL = 5.0  # Seconds between ESPN polls
    DISCOVERY_INTERVAL = 300.0  # Seconds between market discovery runs
    HEALTH_CHECK_INTERVAL = 60.0  # Seconds between health checks
    
    def __init__(
        self,
        polymarket_client: PolymarketClient,
        trading_engine: TradingEngine,
        espn_service: ESPNService
    ):
        self.polymarket_client = polymarket_client
        self.trading_engine = trading_engine
        self.espn_service = espn_service

        # Detect platform from client type
        self.platform = self._detect_platform(polymarket_client)

        self.state = BotState.STOPPED
        self.websocket: PolymarketWebSocket | None = None

        # Tracked games keyed by ESPN event ID
        self.tracked_games: dict[str, TrackedGame] = {}

        # Token ID to game mapping for WebSocket updates
        self.token_to_game: dict[str, str] = {}

        # User-selected games from bot config (game_id -> game_config dict)
        # This filters which games the bot will actually track and trade
        self.user_selected_games: dict[str, dict] = {}

        # Configuration
        self.user_id: UUID | None = None
        self.enabled_sports: list[str] = []
        self.risk_per_trade: float = 0.02
        self.max_daily_loss: float = 100.0
        self.entry_threshold: float = 0.05
        self.take_profit: float = 0.15
        self.stop_loss: float = 0.10

        # Paper trading mode
        self.dry_run: bool = True
        self.max_slippage: float = 0.02
        self.order_fill_timeout: int = 60

        # Emergency stop flag
        self.emergency_stop: bool = False

        # Per-sport statistics and configuration
        self.sport_stats: dict[str, SportStats] = {}
        self.sport_configs: dict[str, Any] = {}

        # Per-market configuration overrides (keyed by condition_id)
        self.market_configs: dict[str, Any] = {}

        # Concurrent entry locks (prevent double-entry race conditions)
        self._entry_locks: dict[str, asyncio.Lock] = {}

    def _detect_platform(self, client) -> str:
        """Detect which trading platform the client is for."""
        client_class = client.__class__.__name__
        if "Kalshi" in client_class:
            return "kalshi"
        return "polymarket"

    async def _place_order(self, game: TrackedGame, side: str, price: float, size: int) -> dict | None:
        """
        Platform-agnostic order placement.
        Handles differences between Polymarket and Kalshi order formats.
        """
        if self.platform == "kalshi":
            # Kalshi order format
            ticker = game.market.ticker
            if not ticker:
                logger.error(f"No ticker available for Kalshi market: {game.market.question}")
                return None

            return await self.polymarket_client.place_order(
                ticker=ticker,
                side=side.lower(),
                yes_no="yes",
                price=price,
                size=int(size),
                time_in_force="gtc"
            )
        else:
            # Polymarket order format
            return await self.polymarket_client.place_order(
                token_id=game.market.token_id_yes,
                side=side.upper(),
                price=price,
                size=size,
                order_type="GTC"
            )

    def _get_order_id(self, order: dict) -> str | None:
        """Get order ID from order response, handling platform differences."""
        if self.platform == "kalshi":
            return order.get("order_id")
        return order.get("id")

    async def _check_slippage(self, game: TrackedGame, price: float, side: str = "buy") -> bool:
        """
        Platform-agnostic slippage check.
        Returns True if slippage is acceptable.
        """
        if self.platform == "kalshi":
            ticker = game.market.ticker
            if not ticker:
                return True  # Allow trade if no ticker
            slippage_ok, _ = await self.polymarket_client.check_slippage(ticker, price, side)
            return slippage_ok
        else:
            # Polymarket check_slippage may return tuple or bool depending on version
            result = await self.polymarket_client.check_slippage(
                game.market.token_id_yes,
                price,
                side
            )
            if isinstance(result, tuple):
                return result[0]
            return result
        
        # Stats
        self.start_time: datetime | None = None
        self.trades_today: int = 0
        self.daily_pnl: float = 0.0
        
        # Control
        self._stop_event = asyncio.Event()
        self._tasks: list[asyncio.Task] = []
    
    async def initialize(
        self,
        db: AsyncSession,
        user_id: UUID
    ) -> None:
        """
        Initialize bot with user configuration.
        
        Loads global settings, sport configs, and recovers open positions.
        
        Args:
            db: Database session
            user_id: User to run bot for
        """
        self.user_id = user_id
        
        # Load global settings
        settings = await GlobalSettingsCRUD.get_by_user_id(db, user_id)
        if settings:
            self.max_daily_loss = float(settings.max_daily_loss_usdc or 100)
            # Load paper trading and safety settings
            self.dry_run = bool(getattr(settings, 'dry_run_mode', True))
            self.emergency_stop = bool(getattr(settings, 'emergency_stop', False))
            self.max_slippage = float(getattr(settings, 'max_slippage_pct', 0.02))
            self.order_fill_timeout = int(getattr(settings, 'order_fill_timeout_seconds', 60))
            
            # Apply to polymarket client
            self.polymarket_client.dry_run = self.dry_run
            self.polymarket_client.max_slippage = self.max_slippage
            
            # Set up Discord notifications if webhook URL is configured
            if settings.discord_webhook_url and settings.discord_alerts_enabled:
                discord_notifier.set_webhook_url(settings.discord_webhook_url)
                logger.info("Discord notifications enabled")
        
        # Load sport configs with per-sport risk limits
        configs = await SportConfigCRUD.get_by_user_id(db, user_id)
        for config in configs:
            sport_key = config.sport.lower()
            
            # Store full config for reference
            self.sport_configs[sport_key] = config
            
            # Initialize per-sport stats tracker
            self.sport_stats[sport_key] = SportStats(
                sport=sport_key,
                enabled=config.enabled,
                priority=int(getattr(config, 'priority', 1)),
                max_daily_loss=float(getattr(config, 'max_daily_loss_usdc', 50)),
                max_exposure=float(getattr(config, 'max_exposure_usdc', 200))
            )
            
            if config.enabled:
                self.enabled_sports.append(sport_key)
                # Use config thresholds (first enabled sport sets defaults)
                if config.entry_threshold_drop and self.entry_threshold == 0.05:
                    self.entry_threshold = float(config.entry_threshold_drop)
                if config.take_profit_pct and self.take_profit == 0.15:
                    self.take_profit = float(config.take_profit_pct)
                if config.stop_loss_pct and self.stop_loss == 0.10:
                    self.stop_loss = float(config.stop_loss_pct)
        
        # Sort enabled sports by priority (lower number = higher priority)
        self.enabled_sports.sort(
            key=lambda s: self.sport_stats.get(s, SportStats(sport=s)).priority
        )

        # Default to NBA if no sports configured
        if not self.enabled_sports:
            self.enabled_sports = ["nba"]
            self.sport_stats["nba"] = SportStats(sport="nba", enabled=True)

        # Load market-specific configs for overrides
        from src.db.crud.market_config import MarketConfigCRUD
        market_configs_list = await MarketConfigCRUD.get_enabled_for_user(db, user_id)
        for mc in market_configs_list:
            self.market_configs[mc.condition_id] = mc
        logger.info(f"Loaded {len(self.market_configs)} market-specific configurations")

        # Recover open positions from database
        await self._recover_positions(db)
        
        # Load user-selected games from bot config
        await self._load_user_selected_games(user_id)
        
        # Initialize WebSocket
        self.websocket = PolymarketWebSocket()
        
        mode_str = "PAPER TRADING" if self.dry_run else "LIVE TRADING"
        games_count = len(self.user_selected_games)
        logger.info(
            f"Bot initialized for user {user_id}. "
            f"Mode: {mode_str}, "
            f"Sports: {self.enabled_sports}, "
            f"Selected games: {games_count}, "
            f"Entry threshold: {self.entry_threshold:.1%}, "
            f"TP: {self.take_profit:.1%}, SL: {self.stop_loss:.1%}"
        )
    
    async def _load_user_selected_games(self, user_id: UUID) -> None:
        """
        Load user-selected games from the bot config store.
        
        This determines which specific games the bot will track and trade.
        Games not in this list will be ignored during discovery.
        Also updates enabled_sports to include all sports from selected games.
        
        Args:
            user_id: User ID to load config for
        """
        from src.api.routes.bot import _bot_configs
        
        user_id_str = str(user_id)
        config = _bot_configs.get(user_id_str, {})
        
        # Get all games (primary + additional)
        games = config.get("games", [])
        
        # Fallback to single game if "games" array not present
        if not games and config.get("game"):
            games = [config["game"]]
        
        # Build lookup by game_id and collect sports
        self.user_selected_games.clear()
        selected_sports: set[str] = set()
        
        for game in games:
            game_id = game.get("game_id")
            if game_id:
                self.user_selected_games[game_id] = game
                sport = game.get("sport", "").lower()
                if sport:
                    selected_sports.add(sport)
                logger.info(
                    f"Loaded user-selected game: {game.get('away_team', '?')} @ "
                    f"{game.get('home_team', '?')} ({sport.upper()}), "
                    f"side: {game.get('selected_side', 'home')}"
                )
        
        # Ensure all selected sports are in enabled_sports
        for sport in selected_sports:
            if sport not in self.enabled_sports:
                self.enabled_sports.append(sport)
                # Create stats tracker if not exists
                if sport not in self.sport_stats:
                    self.sport_stats[sport] = SportStats(sport=sport, enabled=True)
                logger.info(f"Auto-enabled sport {sport.upper()} based on game selection")
        
        logger.info(f"Loaded {len(self.user_selected_games)} user-selected games across sports: {list(selected_sports)}")
    
    async def start(self, db: AsyncSession) -> None:
        """
        Start the trading bot.
        
        Args:
            db: Database session
        """
        if self.state == BotState.RUNNING:
            logger.warning("Bot is already running")
            return
        
        if not self.user_id:
            raise TradingError("Bot not initialized. Call initialize() first.")
        
        logger.info("Starting trading bot...")
        self.state = BotState.STARTING
        self._stop_event.clear()
        self.start_time = datetime.now(timezone.utc)
        
        # Send start notification
        await discord_notifier.notify_bot_started(self.enabled_sports)
        
        # Log activity
        await ActivityLogCRUD.create(
            db,
            user_id=self.user_id,
            action="bot_started",
            details={"sports": self.enabled_sports}
        )
        
        # Start background tasks
        self._tasks = [
            asyncio.create_task(self._discovery_loop(db), name="discovery"),
            asyncio.create_task(self._espn_poll_loop(db), name="espn_poll"),
            asyncio.create_task(self._trading_loop(db), name="trading"),
            asyncio.create_task(self._health_check_loop(db), name="health"),
        ]
        
        if self.websocket:
            self._tasks.append(
                asyncio.create_task(self._websocket_loop(), name="websocket")
            )
        
        self.state = BotState.RUNNING
        logger.info("Trading bot started successfully")
    
    async def stop(self, db: AsyncSession) -> None:
        """
        Stop the trading bot gracefully.
        
        Args:
            db: Database session
        """
        if self.state == BotState.STOPPED:
            logger.warning("Bot is already stopped")
            return
        
        logger.info("Stopping trading bot...")
        self.state = BotState.STOPPING
        self._stop_event.set()
        
        # Cancel all tasks
        for task in self._tasks:
            task.cancel()
        
        # Wait for tasks to complete
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        
        # Close WebSocket
        if self.websocket:
            await self.websocket.disconnect()
        
        # Send stop notification
        runtime = None
        if self.start_time:
            runtime = datetime.now(timezone.utc) - self.start_time
        
        await discord_notifier.notify_bot_stopped(
            reason="User requested stop",
            runtime=runtime,
            trades_executed=self.trades_today,
            total_pnl=self.daily_pnl
        )
        
        # Log activity
        if self.user_id:
            await ActivityLogCRUD.create(
                db,
                user_id=self.user_id,
                action="bot_stopped",
                details={
                    "trades": self.trades_today,
                    "pnl": self.daily_pnl
                }
            )
        
        self.state = BotState.STOPPED
        self.tracked_games.clear()
        self.token_to_game.clear()
        logger.info("Trading bot stopped")
    
    async def _discovery_loop(self, db: AsyncSession) -> None:
        """
        Periodically discover new sports markets.
        
        Only tracks games that the user has explicitly selected in bot config.
        Runs every DISCOVERY_INTERVAL seconds.
        """
        while not self._stop_event.is_set():
            try:
                logger.debug("Running market discovery...")
                
                # Skip discovery if no games selected by user
                if not self.user_selected_games:
                    logger.debug("No user-selected games to track")
                    await asyncio.sleep(self.DISCOVERY_INTERVAL)
                    continue
                
                markets = await market_discovery.discover_sports_markets(
                    sports=self.enabled_sports,
                    min_liquidity=2000,
                    max_spread=0.08,
                    hours_ahead=24,
                    include_live=True
                )
                
                logger.info(f"Discovered {len(markets)} sports markets")
                
                # Match markets to ESPN games - ONLY for user-selected games
                for sport in self.enabled_sports:
                    games = await self.espn_service.get_live_games(sport)
                    
                    for game in games:
                        event_id = game.get("id")
                        
                        # Skip if not in user's selected games
                        if event_id not in self.user_selected_games:
                            continue
                        
                        if event_id in self.tracked_games:
                            continue  # Already tracking
                        
                        # Get user's game config for selected_side
                        user_game_config = self.user_selected_games[event_id]
                        selected_side = user_game_config.get("selected_side", "home")
                        
                        # Try to match to a market
                        competitors = game.get("competitions", [{}])[0].get("competitors", [])
                        if len(competitors) < 2:
                            continue
                        
                        home = next((c for c in competitors if c.get("homeAway") == "home"), None)
                        away = next((c for c in competitors if c.get("homeAway") == "away"), None)
                        
                        if not home or not away:
                            continue
                        
                        home_name = home.get("team", {}).get("displayName", "")
                        away_name = away.get("team", {}).get("displayName", "")
                        
                        # Find matching market
                        matched_market = await self._find_matching_market(
                            markets, home_name, away_name, sport
                        )
                        
                        if matched_market:
                            await self._start_tracking_game(
                                db, event_id, sport, home_name, away_name, 
                                matched_market, game, selected_side=selected_side
                            )
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in discovery loop: {e}")
                await discord_notifier.notify_error(
                    "Market Discovery Error",
                    str(e),
                    "discovery_loop"
                )
                # Log to activity database
                if self.user_id:
                    try:
                        await ActivityLogCRUD.error(
                            db,
                            self.user_id,
                            "DISCOVERY",
                            f"Market discovery failed: {str(e)[:200]}",
                            {"error_type": type(e).__name__, "loop": "discovery"}
                        )
                    except Exception:
                        pass  # Don't let logging failures crash the bot
            
            await asyncio.sleep(self.DISCOVERY_INTERVAL)
    
    async def _espn_poll_loop(self, db: AsyncSession) -> None:
        """
        Poll ESPN for game state updates.
        
        Runs every ESPN_POLL_INTERVAL seconds.
        """
        while not self._stop_event.is_set():
            try:
                for event_id, game in list(self.tracked_games.items()):
                    # Get updated game state
                    game_data = await self.espn_service.get_game_details(
                        game.sport, event_id
                    )
                    
                    if not game_data:
                        continue
                    
                    # Update game state
                    status = game_data.get("status", {})
                    game.game_status = status.get("type", {}).get("state", "pre")
                    game.period = status.get("period", 0)
                    game.clock = status.get("displayClock", "")
                    
                    # Update scores
                    competitors = game_data.get("competitions", [{}])[0].get("competitors", [])
                    for comp in competitors:
                        if comp.get("homeAway") == "home":
                            game.home_score = int(comp.get("score", 0) or 0)
                        else:
                            game.away_score = int(comp.get("score", 0) or 0)
                    
                    game.last_update = datetime.now(timezone.utc)
                    
                    # Check if game finished
                    if game.game_status == "post":
                        logger.info(f"Game finished: {game.home_team} vs {game.away_team}")
                        await self._handle_game_finished(db, game)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in ESPN poll loop: {e}")
                # Log to activity database
                if self.user_id:
                    try:
                        await ActivityLogCRUD.warning(
                            db,
                            self.user_id,
                            "ESPN",
                            f"ESPN polling error: {str(e)[:200]}",
                            {"error_type": type(e).__name__, "loop": "espn_poll"}
                        )
                    except Exception:
                        pass
            
            await asyncio.sleep(self.ESPN_POLL_INTERVAL)
    
    async def _websocket_loop(self) -> None:
        """
        Manage WebSocket connection and handle price updates.
        """
        if not self.websocket:
            return
        
        # Register price callback
        self.websocket.add_callback(self._handle_price_update)
        
        while not self._stop_event.is_set():
            try:
                await self.websocket.connect()
                
                # Subscribe to tracked markets
                for game in self.tracked_games.values():
                    await self.websocket.subscribe(
                        game.market.condition_id,
                        game.market.token_id_yes,
                        game.market.token_id_no
                    )
                
                # Keep connection alive
                while not self._stop_event.is_set() and self.websocket.is_connected:
                    await asyncio.sleep(1)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                await asyncio.sleep(5)  # Wait before reconnect
    
    def _handle_price_update(self, update: PriceUpdate) -> None:
        """
        Handle real-time price update from WebSocket.
        
        Args:
            update: Price update data
        """
        event_id = self.token_to_game.get(update.token_id)
        if not event_id:
            return
        
        game = self.tracked_games.get(event_id)
        if not game:
            return
        
        game.current_price = update.mid_price
        game.last_update = datetime.now(timezone.utc)
        
        logger.debug(
            f"Price update for {game.home_team} vs {game.away_team}: "
            f"${update.mid_price:.4f} (spread: ${update.spread:.4f})"
        )
    
    async def _trading_loop(self, db: AsyncSession) -> None:
        """
        Main trading decision loop.
        
        Evaluates entry/exit conditions for all tracked games.
        """
        while not self._stop_event.is_set():
            try:
                # Check daily loss limit
                if self.daily_pnl <= -self.max_daily_loss:
                    logger.warning("Daily loss limit reached. Pausing trading.")
                    await discord_notifier.notify_risk_limit_reached(
                        "Daily Loss Limit",
                        self.max_daily_loss,
                        self.daily_pnl
                    )
                    self.state = BotState.PAUSED
                    await asyncio.sleep(60)
                    continue
                
                for event_id, game in list(self.tracked_games.items()):
                    # Skip if game not live
                    if game.game_status != "in":
                        continue
                    
                    # Skip if no price data
                    if game.current_price is None or game.baseline_price is None:
                        continue
                    
                    # Evaluate conditions
                    if game.has_position:
                        await self._evaluate_exit(db, game)
                    else:
                        await self._evaluate_entry(db, game)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in trading loop: {e}")
                await discord_notifier.notify_error(
                    "Trading Loop Error",
                    str(e),
                    "trading_loop"
                )
                # Log to activity database
                if self.user_id:
                    try:
                        await ActivityLogCRUD.error(
                            db,
                            self.user_id,
                            "TRADING",
                            f"Trading loop error: {str(e)[:200]}",
                            {"error_type": type(e).__name__, "loop": "trading"}
                        )
                    except Exception:
                        pass
            
            await asyncio.sleep(1)  # Check every second
    
    async def _evaluate_entry(self, db: AsyncSession, game: TrackedGame) -> None:
        """
        Evaluate entry conditions for a game.

        Entry triggers when:
        - Selected side matches the market (home/away/both)
        - Game is in allowed entry segment (max_entry_segment)
        - Price has dropped from baseline by threshold OR below absolute threshold
        - Sufficient time remaining (min_time_remaining_seconds)
        - Market has sufficient volume (min_volume_threshold)
        - Per-sport risk limits not exceeded
        - Within trading hours for sport
        - No concurrent entry in progress (lock-protected)
        """
        # Emergency stop check
        if self.emergency_stop:
            return

        # Check selected_side - only trade if market matches user's team selection
        if not self._should_trade_market(game):
            return

        # Check if trading is enabled for this market
        if not self._is_market_enabled(game):
            logger.debug(f"Entry blocked: trading disabled for market {game.market.condition_id}")
            return

        sport_key = game.sport.lower()
        config = self.sport_configs.get(sport_key)

        # Check if in allowed entry segment (uses market override if available)
        if config:
            allowed_segments = getattr(config, 'allowed_entry_segments', ['q1', 'q2', 'q3'])
            current_segment = self._get_game_segment(game)
            if current_segment not in allowed_segments:
                logger.debug(f"Entry blocked: segment {current_segment} not in allowed {allowed_segments}")
                return

        # Check minimum time remaining (uses market override first)
        min_time_remaining = self._get_effective_config(game, 'min_time_remaining_seconds', 300)
        time_remaining = self._get_time_remaining_seconds(game)
        if time_remaining is not None and time_remaining < min_time_remaining:
            logger.debug(f"Entry blocked: only {time_remaining}s remaining, need {min_time_remaining}s")
            return

        # Check minimum volume threshold (from sport config)
        min_volume = float(self._get_effective_config(game, 'min_volume_threshold', 0) or 0)
        if min_volume > 0:
            market_volume = getattr(game.market, 'volume_24h', 0) or 0
            if market_volume < min_volume:
                logger.debug(f"Entry blocked: market volume ${market_volume:.2f} below threshold ${min_volume:.2f}")
                return

        # Fallback period check if no sport config
        if not config and game.period > 1:
            return

        # Check trading hours for sport
        if not self._check_sport_trading_hours(game.sport):
            return

        # Check per-sport risk limits
        allowed, reason = self._check_sport_risk_limits(game.sport)
        if not allowed:
            logger.debug(f"Entry blocked: {reason}")
            return

        # Get entry thresholds (market override > sport config > default)
        entry_drop_threshold = float(self._get_effective_config(game, 'entry_threshold_drop', self.entry_threshold))
        entry_absolute_price = float(self._get_effective_config(game, 'entry_threshold_absolute', 0.50))

        # Check price conditions (drop from baseline OR below absolute threshold)
        price_drop = (game.baseline_price - game.current_price) / game.baseline_price if game.baseline_price else 0
        below_absolute = game.current_price <= entry_absolute_price

        if price_drop < entry_drop_threshold and not below_absolute:
            return  # Not enough drop and not below absolute threshold

        # Acquire lock to prevent double-entry
        lock = self._get_entry_lock(game.market.token_id_yes)

        if lock.locked():
            logger.debug(f"Entry already in progress for {game.market.token_id_yes}")
            return

        async with lock:
            # Re-check position status after acquiring lock
            if game.has_position:
                return

            trigger_reason = f"Price drop of {price_drop:.1%}" if price_drop >= entry_drop_threshold else f"Below absolute threshold ${entry_absolute_price:.2f}"
            logger.info(
                f"Entry signal: {game.home_team} {trigger_reason} "
                f"from ${game.baseline_price:.4f} to ${game.current_price:.4f}"
            )

            # Get position size (market override > sport config > default)
            balance = await self.polymarket_client.get_balance()
            position_size = float(self._get_effective_config(game, 'position_size_usdc', 50))

            # Ensure we don't exceed balance
            position_size = min(position_size, float(balance) * 0.95)
            
            if position_size < 1:
                logger.warning("Insufficient balance for trade")
                return
            
            # Slippage check before execution (platform-agnostic)
            if not self.dry_run:
                slippage_ok = await self._check_slippage(game, game.current_price, "buy")
                if not slippage_ok:
                    logger.warning(
                        f"Slippage too high for {game.home_team} vs {game.away_team}"
                    )
                    return

            # Execute entry (platform-agnostic)
            try:
                order = await self._place_order(game, "BUY", game.current_price, int(position_size))

                if order:
                    order_id = self._get_order_id(order)

                    # Wait for fill with timeout (skip for paper trading)
                    fill_status = "filled"
                    if not self.dry_run:
                        fill_status = await self.polymarket_client.wait_for_fill(
                            order_id,
                            timeout=self.order_fill_timeout
                        )

                        if fill_status != "filled":
                            logger.warning(f"Order not filled: {fill_status}")
                            # Cancel unfilled order
                            try:
                                await self.polymarket_client.cancel_order(order_id)
                            except Exception:
                                pass
                            return

                    # Record position using CRUD interface
                    entry_cost = position_size * game.current_price
                    # Use ticker for Kalshi, token_id for Polymarket
                    token_or_ticker = game.market.ticker if self.platform == "kalshi" else game.market.token_id_yes
                    position = await PositionCRUD.create(
                        db,
                        user_id=self.user_id,
                        condition_id=game.market.condition_id or game.market.ticker or "",
                        token_id=token_or_ticker or "",
                        side="YES",
                        entry_price=Decimal(str(game.current_price)),
                        entry_size=Decimal(str(position_size)),
                        entry_cost_usdc=Decimal(str(entry_cost)),
                        entry_reason=f"Price drop from baseline",
                        entry_order_id=order_id
                    )
                    
                    game.has_position = True
                    game.position_id = position.id
                    self.trades_today += 1

                    # Update per-sport stats
                    sport_stats = self.sport_stats.get(sport_key)
                    if sport_stats:
                        sport_stats.trades_today += 1
                        sport_stats.open_positions += 1
                    
                    mode_str = "[PAPER] " if self.dry_run else ""
                    await discord_notifier.notify_trade_entry(
                        market_name=f"{mode_str}{game.market.question[:100]}",
                        side="YES",
                        price=game.current_price,
                        size=position_size,
                        baseline_price=game.baseline_price,
                        trigger_reason=f"Price drop of {price_drop:.1%}"
                    )
                    
                    logger.info(f"Entry executed: {position_size:.2f} contracts at ${game.current_price:.4f}")
            
            except Exception as e:
                logger.error(f"Failed to execute entry: {e}")
                await discord_notifier.notify_error("Entry Failed", str(e), "entry_execution")
                # Log to activity database
                if self.user_id:
                    try:
                        await ActivityLogCRUD.error(
                            db,
                            self.user_id,
                            "TRADE",
                            f"Entry order failed for {game.home_team} vs {game.away_team}",
                            {
                                "error": str(e)[:200],
                                "token_id": game.market.token_id_yes[:20],
                                "attempted_price": game.current_price,
                                "attempted_size": position_size
                            }
                        )
                    except Exception:
                        pass

    async def _evaluate_exit(self, db: AsyncSession, game: TrackedGame) -> None:
        """
        Evaluate exit conditions for an open position.

        Exit triggers:
        - Take profit reached (per-sport configurable)
        - Stop loss reached (per-sport configurable)
        - Time remaining below exit threshold (exit_time_remaining_seconds)
        - Game segment past exit_before_segment
        - Game finished
        - Emergency stop activated
        """
        if not game.position_id:
            return

        position = await PositionCRUD.get_by_id(db, game.position_id)
        if not position or position.status != "open":
            game.has_position = False
            game.position_id = None
            return

        entry_price = float(position.entry_price)
        current_price = game.current_price

        # Calculate P&L
        pnl_pct = (current_price - entry_price) / entry_price if entry_price else 0

        # Get exit parameters (market override > sport config > default)
        take_profit_threshold = float(self._get_effective_config(game, 'take_profit_pct', self.take_profit))
        stop_loss_threshold = float(self._get_effective_config(game, 'stop_loss_pct', self.stop_loss))
        exit_time_remaining = self._get_effective_config(game, 'exit_time_remaining_seconds', None)
        exit_before_segment = self._get_effective_config(game, 'exit_before_segment', None)

        exit_reason = None

        # Check exit conditions in priority order
        if self.emergency_stop:
            exit_reason = "emergency_stop"
        elif pnl_pct >= take_profit_threshold:
            exit_reason = "take_profit"
        elif pnl_pct <= -stop_loss_threshold:
            exit_reason = "stop_loss"
        elif game.game_status == "post":
            exit_reason = "game_finished"
        else:
            # Check time-based exit (must sell once X seconds remaining)
            if exit_time_remaining is not None:
                time_remaining = self._get_time_remaining_seconds(game)
                if time_remaining is not None and time_remaining <= exit_time_remaining:
                    exit_reason = f"time_exit_{time_remaining}s_remaining"
                    logger.info(f"Time-based exit triggered: {time_remaining}s remaining, threshold {exit_time_remaining}s")

            # Check segment-based exit
            if not exit_reason and exit_before_segment:
                current_segment = self._get_game_segment(game)
                if self._is_past_segment(current_segment, exit_before_segment):
                    exit_reason = f"segment_exit_{current_segment}"
                    logger.info(f"Segment-based exit triggered: in {current_segment}, must exit before {exit_before_segment}")

        if not exit_reason:
            return
        
        logger.info(
            f"Exit signal ({exit_reason}): {game.home_team} "
            f"P&L: {pnl_pct:.1%}"
        )
        
        # Execute exit (platform-agnostic)
        try:
            exit_size = float(position.entry_size)
            order = await self._place_order(game, "SELL", current_price, int(exit_size))

            if order:
                order_id = self._get_order_id(order)
                pnl = (current_price - entry_price) * exit_size
                exit_proceeds = current_price * exit_size

                # Update position using close_position method
                await PositionCRUD.close_position(
                    db,
                    position_id=position.id,
                    exit_price=Decimal(str(current_price)),
                    exit_size=Decimal(str(exit_size)),
                    exit_proceeds_usdc=Decimal(str(exit_proceeds)),
                    exit_reason=exit_reason,
                    exit_order_id=order_id
                )
                
                game.has_position = False
                game.position_id = None
                self.daily_pnl += pnl
                
                # Update per-sport stats
                sport_key = game.sport.lower()
                if sport_key in self.sport_stats:
                    self.sport_stats[sport_key].daily_pnl += pnl
                    self.sport_stats[sport_key].open_positions = max(
                        0, self.sport_stats[sport_key].open_positions - 1
                    )
                
                mode_str = "[PAPER] " if self.dry_run else ""
                await discord_notifier.notify_trade_exit(
                    market_name=f"{mode_str}{game.market.question[:100]}",
                    exit_price=current_price,
                    entry_price=entry_price,
                    pnl=pnl,
                    exit_reason=exit_reason,
                    hold_time=datetime.now(timezone.utc) - position.created_at
                )
                
                logger.info(f"Exit executed: P&L ${pnl:.2f} ({pnl_pct:.1%})")
            
        except Exception as e:
            logger.error(f"Failed to execute exit: {e}")
            await discord_notifier.notify_error("Exit Failed", str(e), "exit_execution")
            # Log to activity database
            if self.user_id:
                try:
                    await ActivityLogCRUD.error(
                        db,
                        self.user_id,
                        "TRADE",
                        f"Exit order failed for {game.home_team} vs {game.away_team}",
                        {
                            "error": str(e)[:200],
                            "position_id": str(game.position_id),
                            "exit_reason": exit_reason,
                            "current_price": current_price
                        }
                    )
                except Exception:
                    pass

    async def _health_check_loop(self, db: AsyncSession) -> None:
        """
        Periodic health checks and stats logging.
        """
        while not self._stop_event.is_set():
            try:
                ws_status = "connected" if self.websocket and self.websocket.is_connected else "disconnected"
                
                logger.info(
                    f"Health check: state={self.state.value}, "
                    f"tracked_games={len(self.tracked_games)}, "
                    f"ws={ws_status}, "
                    f"trades_today={self.trades_today}, "
                    f"daily_pnl=${self.daily_pnl:.2f}"
                )
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check error: {e}")
            
            await asyncio.sleep(self.HEALTH_CHECK_INTERVAL)
    
    async def _recover_positions(self, db: AsyncSession) -> None:
        """
        Recover open positions from database on bot startup.
        
        Reconstructs tracked games from positions that were open when
        the bot last stopped. Essential for preventing orphaned positions
        after restarts or crashes.
        """
        if not self.user_id:
            return
        
        try:
            # Get all open positions for user
            open_positions = await PositionCRUD.get_open_positions(db, self.user_id)
            
            if not open_positions:
                logger.info("No open positions to recover")
                return
            
            logger.info(f"Recovering {len(open_positions)} open positions")
            
            for position in open_positions:
                # Get the tracked market data
                tracked_market = await TrackedMarketCRUD.get_by_condition_id(
                    db, position.condition_id
                )
                
                if not tracked_market:
                    logger.warning(
                        f"Could not find tracked market for position {position.id}"
                    )
                    continue
                
                # Reconstruct market object
                market = DiscoveredMarket(
                    condition_id=tracked_market.condition_id,
                    question=tracked_market.question,
                    token_id_yes=tracked_market.token_id_yes,
                    token_id_no=tracked_market.token_id_no,
                    sport=tracked_market.sport,
                    current_price_yes=float(tracked_market.current_price_yes or 0.5),
                    current_price_no=1.0 - float(tracked_market.current_price_yes or 0.5),
                    volume_24h=0,
                    liquidity=0,
                    spread=0.02
                )
                
                # Create tracked game entry
                event_id = tracked_market.espn_event_id or f"recovered_{position.id}"
                
                tracked = TrackedGame(
                    espn_event_id=event_id,
                    sport=tracked_market.sport,
                    home_team=tracked_market.home_team or "Unknown",
                    away_team=tracked_market.away_team or "Unknown",
                    market=market,
                    baseline_price=float(tracked_market.baseline_price_yes or 0.5),
                    current_price=float(tracked_market.current_price_yes or 0.5),
                    has_position=True,
                    position_id=position.id
                )
                
                self.tracked_games[event_id] = tracked
                self.token_to_game[market.token_id_yes] = event_id
                
                # Update per-sport stats
                sport_key = tracked_market.sport.lower()
                if sport_key in self.sport_stats:
                    self.sport_stats[sport_key].open_positions += 1
                
                logger.info(
                    f"Recovered position: {tracked.home_team} vs {tracked.away_team} "
                    f"(entry: ${float(position.entry_price):.4f})"
                )
            
            logger.info(
                f"Position recovery complete. "
                f"Tracking {len(self.tracked_games)} games with positions"
            )
            
        except Exception as e:
            logger.error(f"Error recovering positions: {e}")
            await discord_notifier.notify_error(
                "Position Recovery Failed",
                str(e),
                "position_recovery"
            )
    
    async def emergency_shutdown(self, db: AsyncSession, close_positions: bool = True) -> dict:
        """
        Emergency shutdown with optional position closure.
        
        Immediately stops all trading activity. Optionally closes all
        open positions at market price to limit exposure.
        
        Args:
            db: Database session
            close_positions: Whether to close all open positions
        
        Returns:
            Summary of shutdown actions
        """
        logger.warning("EMERGENCY SHUTDOWN INITIATED")
        self.emergency_stop = True
        self.state = BotState.STOPPING
        
        result = {
            "shutdown_initiated": True,
            "positions_closed": 0,
            "positions_failed": 0,
            "total_pnl": 0.0,
            "errors": []
        }
        
        # Stop accepting new trades
        self._stop_event.set()
        
        # Notify immediately
        await discord_notifier.send_notification(
            title="EMERGENCY SHUTDOWN",
            message="Bot emergency stop triggered. Closing all positions.",
            level="critical"
        )
        
        if close_positions:
            for event_id, game in list(self.tracked_games.items()):
                if not game.has_position or not game.position_id:
                    continue
                
                try:
                    position = await PositionCRUD.get_by_id(db, game.position_id)
                    if not position or position.status != "open":
                        continue
                    
                    # Get current market price
                    current_price = game.current_price or float(position.entry_price)
                    exit_size = float(position.entry_size)

                    # Execute market exit (platform-agnostic)
                    exit_price = current_price * 0.98  # 2% below for market-like fill
                    order = await self._place_order(game, "SELL", exit_price, int(exit_size))

                    if order:
                        order_id = self._get_order_id(order)
                        entry_price = float(position.entry_price)
                        pnl = (current_price - entry_price) * exit_size
                        exit_proceeds = current_price * exit_size

                        await PositionCRUD.close_position(
                            db,
                            position_id=position.id,
                            exit_price=Decimal(str(current_price)),
                            exit_size=Decimal(str(exit_size)),
                            exit_proceeds_usdc=Decimal(str(exit_proceeds)),
                            exit_reason="emergency_shutdown",
                            exit_order_id=order_id
                        )
                        
                        result["positions_closed"] += 1
                        result["total_pnl"] += pnl
                        
                        logger.info(
                            f"Emergency closed: {game.home_team} vs {game.away_team} "
                            f"P&L: ${pnl:.2f}"
                        )
                    
                except Exception as e:
                    result["positions_failed"] += 1
                    result["errors"].append(str(e))
                    logger.error(f"Failed to close position for {game.espn_event_id}: {e}")
        
        # Update settings to persist emergency stop
        if self.user_id:
            settings = await GlobalSettingsCRUD.get_by_user_id(db, self.user_id)
            if settings:
                await GlobalSettingsCRUD.update(
                    db, settings.id, emergency_stop=True
                )
        
        # Complete shutdown
        await self.stop(db)
        
        # Log activity
        if self.user_id:
            await ActivityLogCRUD.create(
                db,
                user_id=self.user_id,
                action="emergency_shutdown",
                details=result
            )
        
        await discord_notifier.send_notification(
            title="Emergency Shutdown Complete",
            message=f"Closed {result['positions_closed']} positions. "
                    f"Total P&L: ${result['total_pnl']:.2f}",
            level="warning"
        )
        
        return result
    
    def _get_entry_lock(self, token_id: str) -> asyncio.Lock:
        """
        Get or create a lock for a specific market token.
        
        Prevents race conditions where multiple evaluations could
        trigger duplicate entries on the same market.
        
        Args:
            token_id: Market token ID
        
        Returns:
            asyncio.Lock for the token
        """
        if token_id not in self._entry_locks:
            self._entry_locks[token_id] = asyncio.Lock()
        return self._entry_locks[token_id]
    
    def _check_sport_trading_hours(self, sport: str) -> bool:
        """
        Check if current time is within trading hours for a sport.
        
        Args:
            sport: Sport identifier (e.g., 'nba')
        
        Returns:
            True if trading is allowed, False otherwise
        """
        config = self.sport_configs.get(sport.lower())
        if not config:
            return True  # No config means no restrictions
        
        start_hour = getattr(config, 'trading_hours_start', None)
        end_hour = getattr(config, 'trading_hours_end', None)
        
        if not start_hour or not end_hour:
            return True  # No hours configured
        
        try:
            now = datetime.now()
            start = datetime.strptime(start_hour, "%H:%M").time()
            end = datetime.strptime(end_hour, "%H:%M").time()
            current_time = now.time()
            
            # Handle overnight ranges (e.g., 22:00 to 06:00)
            if start <= end:
                return start <= current_time <= end
            else:
                return current_time >= start or current_time <= end
                
        except ValueError:
            return True  # Invalid format, allow trading
    
    def _check_sport_risk_limits(self, sport: str) -> tuple[bool, str]:
        """
        Check if per-sport risk limits allow new entries.

        Args:
            sport: Sport identifier

        Returns:
            Tuple of (allowed, reason)
        """
        stats = self.sport_stats.get(sport.lower())
        config = self.sport_configs.get(sport.lower())
        if not stats:
            return True, ""

        # Check daily loss limit for sport
        if stats.daily_pnl <= -stats.max_daily_loss:
            return False, f"{sport.upper()} daily loss limit reached"

        # Check max positions per game and total
        max_positions = 3  # Default
        if config:
            max_positions = getattr(config, 'max_total_positions', 5)

        if stats.open_positions >= max_positions:
            return False, f"{sport.upper()} max positions ({max_positions}) reached"

        return True, ""

    def _get_game_segment(self, game: TrackedGame) -> str:
        """
        Get the current game segment (q1, q2, q3, q4, p1, p2, h1, h2, etc.).

        Args:
            game: Tracked game

        Returns:
            Segment string (e.g., 'q1', 'q2', 'p1', 'h1')
        """
        sport = game.sport.lower()
        period = game.period

        if period <= 0:
            return "pre"

        # NBA, NFL, NCAA use quarters
        if sport in ['nba', 'nfl', 'ncaab', 'ncaaf']:
            if period == 1:
                return "q1"
            elif period == 2:
                return "q2"
            elif period == 3:
                return "q3"
            elif period >= 4:
                return "q4"

        # NHL uses periods
        elif sport == 'nhl':
            if period == 1:
                return "p1"
            elif period == 2:
                return "p2"
            elif period >= 3:
                return "p3"

        # Soccer, MMA use halves or rounds
        elif sport in ['soccer', 'mma']:
            if period == 1:
                return "h1"
            elif period >= 2:
                return "h2"

        # Tennis, Golf - just use period number
        elif sport in ['tennis', 'golf']:
            return f"set{period}"

        # MLB uses innings
        elif sport == 'mlb':
            return f"i{period}"

        return f"p{period}"

    def _get_time_remaining_seconds(self, game: TrackedGame) -> int | None:
        """
        Parse game clock and estimate total time remaining in game.

        Args:
            game: Tracked game

        Returns:
            Estimated seconds remaining in game, or None if cannot determine
        """
        clock = game.clock
        period = game.period
        sport = game.sport.lower()

        if not clock:
            return None

        # Parse clock format (typically "MM:SS" or "M:SS")
        try:
            parts = clock.replace(" ", "").split(":")
            if len(parts) == 2:
                minutes = int(parts[0])
                seconds = int(parts[1])
                clock_seconds = minutes * 60 + seconds
            else:
                return None
        except (ValueError, IndexError):
            return None

        # Calculate total remaining based on sport
        if sport in ['nba']:
            # 12 min quarters, 4 quarters
            period_length = 12 * 60
            total_periods = 4
        elif sport in ['nfl', 'ncaaf']:
            # 15 min quarters, 4 quarters
            period_length = 15 * 60
            total_periods = 4
        elif sport in ['ncaab']:
            # 20 min halves, 2 halves (but period counts 1, 2)
            period_length = 20 * 60
            total_periods = 2
        elif sport == 'nhl':
            # 20 min periods, 3 periods
            period_length = 20 * 60
            total_periods = 3
        elif sport == 'soccer':
            # 45 min halves, 2 halves
            period_length = 45 * 60
            total_periods = 2
        else:
            # Default: can't estimate
            return clock_seconds

        # Remaining in current period + full remaining periods
        remaining_periods = max(0, total_periods - period)
        total_remaining = clock_seconds + (remaining_periods * period_length)

        return total_remaining

    def _is_past_segment(self, current_segment: str, threshold_segment: str) -> bool:
        """
        Check if current segment is past the threshold segment.

        Args:
            current_segment: Current game segment (e.g., 'q3')
            threshold_segment: Threshold segment (e.g., 'q4_2min')

        Returns:
            True if current segment is past threshold
        """
        # Parse threshold (may include time component like 'q4_2min')
        threshold_base = threshold_segment.split('_')[0]

        # Define segment order
        segment_order = {
            'pre': 0,
            'q1': 1, 'q2': 2, 'q3': 3, 'q4': 4,
            'p1': 1, 'p2': 2, 'p3': 3,
            'h1': 1, 'h2': 2,
            'i1': 1, 'i2': 2, 'i3': 3, 'i4': 4, 'i5': 5, 'i6': 6, 'i7': 7, 'i8': 8, 'i9': 9,
            'set1': 1, 'set2': 2, 'set3': 3, 'set4': 4, 'set5': 5,
        }

        current_order = segment_order.get(current_segment, 0)
        threshold_order = segment_order.get(threshold_base, 99)

        return current_order >= threshold_order

    def _get_effective_config(self, game: TrackedGame, param: str, default: Any = None) -> Any:
        """
        Get effective config value for a parameter, checking market override first.

        Priority: market_config > sport_config > default

        Args:
            game: Tracked game
            param: Parameter name to lookup
            default: Default value if not found anywhere

        Returns:
            Effective config value
        """
        condition_id = game.market.condition_id
        sport_key = game.sport.lower()

        # Check market-specific override first
        market_cfg = self.market_configs.get(condition_id)
        if market_cfg:
            value = getattr(market_cfg, param, None)
            if value is not None:
                return value

        # Check sport config
        sport_cfg = self.sport_configs.get(sport_key)
        if sport_cfg:
            value = getattr(sport_cfg, param, None)
            if value is not None:
                return value

        return default

    def _should_trade_market(self, game: TrackedGame) -> bool:
        """
        Check if the market matches the user's selected side.
        
        Users can select:
        - "home": Only bet if the market favors home team
        - "away": Only bet if the market favors away team
        - "both": Can bet on either team (legacy behavior)
        
        For moneyline markets, we determine which team the YES token represents
        by checking the market question text.
        
        Args:
            game: Tracked game with selected_side field
            
        Returns:
            True if we should trade this market based on selected side
        """
        selected_side = getattr(game, 'selected_side', 'home')
        
        # "both" allows trading either side
        if selected_side == "both":
            return True
        
        # Determine which team the YES token represents
        # Most Polymarket moneyline markets are structured as "Will [Team] win?"
        market_question = game.market.question.lower() if hasattr(game.market, 'question') else ""
        
        home_team_lower = game.home_team.lower()
        away_team_lower = game.away_team.lower()
        
        # Check if market question references the home or away team
        home_in_question = any(word in market_question for word in home_team_lower.split())
        away_in_question = any(word in market_question for word in away_team_lower.split())
        
        # If we can't determine, allow the trade (conservative fallback)
        if not home_in_question and not away_in_question:
            logger.debug(f"Cannot determine market team for {game.market.condition_id}, allowing trade")
            return True
        
        # Determine if market is for home or away team
        market_is_home = home_in_question and not away_in_question
        market_is_away = away_in_question and not home_in_question
        
        # If both teams mentioned (e.g., "Team A vs Team B"), we need more analysis
        if home_in_question and away_in_question:
            # Check which team name appears first - usually the subject team
            home_pos = market_question.find(home_team_lower.split()[0])
            away_pos = market_question.find(away_team_lower.split()[0])
            
            if home_pos >= 0 and away_pos >= 0:
                market_is_home = home_pos < away_pos
                market_is_away = not market_is_home
            else:
                # Can't determine, allow trade
                return True
        
        # Validate against selected side
        if selected_side == "home" and not market_is_home:
            logger.debug(f"Entry blocked: user selected home team but market is for away team")
            return False
        
        if selected_side == "away" and not market_is_away:
            logger.debug(f"Entry blocked: user selected away team but market is for home team")
            return False
        
        return True

    def _is_market_enabled(self, game: TrackedGame) -> bool:
        """
        Check if trading is enabled for this market.
        
        Validates:
        - User has selected this game for trading (is_user_selected)
        - Market-specific config allows trading (enabled, auto_trade)
        - Sport is enabled in user's sport configs

        Args:
            game: Tracked game

        Returns:
            True if trading is allowed on this market
        """
        # Check if user has selected this game for trading
        if hasattr(game.market, 'is_user_selected') and not game.market.is_user_selected:
            return False
        
        condition_id = game.market.condition_id

        # Check market-specific config
        market_cfg = self.market_configs.get(condition_id)
        if market_cfg:
            # Market config exists - check enabled and auto_trade flags
            if not getattr(market_cfg, 'enabled', True):
                return False
            if not getattr(market_cfg, 'auto_trade', True):
                return False

        # Check sport enabled
        sport_key = game.sport.lower()
        sport_cfg = self.sport_configs.get(sport_key)
        if sport_cfg and not getattr(sport_cfg, 'enabled', True):
            return False

        return True
    
    def get_sport_stats(self) -> dict[str, dict]:
        """
        Get statistics for all tracked sports.
        
        Returns:
            Dictionary of sport -> stats
        """
        result = {}
        for sport, stats in self.sport_stats.items():
            result[sport] = {
                "enabled": stats.enabled,
                "priority": stats.priority,
                "trades_today": stats.trades_today,
                "daily_pnl": stats.daily_pnl,
                "open_positions": stats.open_positions,
                "tracked_games": len([
                    g for g in self.tracked_games.values() 
                    if g.sport.lower() == sport
                ]),
                "max_daily_loss": stats.max_daily_loss,
                "max_exposure": stats.max_exposure
            }
        return result
    
    async def _find_matching_market(
        self,
        markets: list[DiscoveredMarket],
        home_team: str,
        away_team: str,
        sport: str
    ) -> DiscoveredMarket | None:
        """
        Find a market matching the given teams.
        
        Args:
            markets: List of discovered markets
            home_team: Home team name
            away_team: Away team name
            sport: Sport type
        
        Returns:
            Matching market or None
        """
        home_lower = home_team.lower()
        away_lower = away_team.lower()
        
        for market in markets:
            if market.sport != sport:
                continue
            
            question_lower = market.question.lower()
            
            # Check if both teams appear in market question
            if home_lower in question_lower and away_lower in question_lower:
                return market
            
            # Check individual words
            home_words = set(home_lower.split())
            away_words = set(away_lower.split())
            question_words = set(question_lower.split())
            
            home_match = len(home_words & question_words) >= 1
            away_match = len(away_words & question_words) >= 1
            
            if home_match and away_match:
                return market
        
        return None
    
    async def _start_tracking_game(
        self,
        db: AsyncSession,
        event_id: str,
        sport: str,
        home_team: str,
        away_team: str,
        market: DiscoveredMarket,
        game_data: dict,
        selected_side: str = "home"
    ) -> None:
        """
        Start tracking a game for trading.
        
        Args:
            db: Database session
            event_id: ESPN event ID
            sport: Sport type
            home_team: Home team name
            away_team: Away team name
            market: Matched Polymarket market
            game_data: ESPN game data
            selected_side: Which team to bet on ("home", "away", or "both")
        """
        # Get baseline price
        baseline = market.current_price_yes
        
        tracked = TrackedGame(
            espn_event_id=event_id,
            sport=sport,
            home_team=home_team,
            away_team=away_team,
            market=market,
            baseline_price=baseline,
            current_price=baseline,
            selected_side=selected_side
        )
        
        self.tracked_games[event_id] = tracked
        self.token_to_game[market.token_id_yes] = event_id
        
        # Subscribe to WebSocket updates
        if self.websocket and self.websocket.is_connected:
            await self.websocket.subscribe(
                market.condition_id,
                market.token_id_yes,
                market.token_id_no
            )
        
        # Save to database
        await TrackedMarketCRUD.create(
            db,
            user_id=self.user_id,
            condition_id=market.condition_id,
            token_id_yes=market.token_id_yes,
            token_id_no=market.token_id_no,
            sport=sport,
            question=market.question,
            espn_event_id=event_id,
            home_team=home_team,
            away_team=away_team,
            baseline_price_yes=Decimal(str(baseline)),
            current_price_yes=Decimal(str(baseline)),
        )
        
        logger.info(
            f"Now tracking: {home_team} vs {away_team} ({sport.upper()}) "
            f"baseline=${baseline:.4f}"
        )
    
    async def _handle_game_finished(
        self,
        db: AsyncSession,
        game: TrackedGame
    ) -> None:
        """
        Handle a game that has finished.
        
        Closes any open positions and removes from tracking.
        """
        # Close any open position
        if game.has_position and game.position_id:
            await self._evaluate_exit(db, game)
        
        # Remove from tracking
        del self.tracked_games[game.espn_event_id]
        if game.market.token_id_yes in self.token_to_game:
            del self.token_to_game[game.market.token_id_yes]
        
        # Unsubscribe from WebSocket
        if self.websocket:
            await self.websocket.unsubscribe(game.market.condition_id)
        
        # Update database
        await TrackedMarketCRUD.deactivate(
            db,
            condition_id=game.market.condition_id
        )
        
        logger.info(
            f"Stopped tracking finished game: {game.home_team} vs {game.away_team}"
        )
    
    def get_status(self) -> dict:
        """
        Get current bot status including paper trading mode and per-sport stats.
        
        Returns:
            Status dictionary with state, stats, and multi-sport breakdown
        """
        ws_status = "connected" if self.websocket and self.websocket.is_connected else "disconnected"
        
        runtime = None
        if self.start_time:
            runtime = str(datetime.now(timezone.utc) - self.start_time)
        
        # Count games and positions per sport
        games_by_sport = {}
        for game in self.tracked_games.values():
            sport = game.sport.lower()
            if sport not in games_by_sport:
                games_by_sport[sport] = {"games": 0, "positions": 0}
            games_by_sport[sport]["games"] += 1
            if game.has_position:
                games_by_sport[sport]["positions"] += 1
        
        return {
            "state": self.state.value,
            "runtime": runtime,
            "paper_trading": self.dry_run,
            "emergency_stop": self.emergency_stop,
            "tracked_games": len(self.tracked_games),
            "enabled_sports": self.enabled_sports,
            "websocket_status": ws_status,
            "trades_today": self.trades_today,
            "daily_pnl": self.daily_pnl,
            "max_daily_loss": self.max_daily_loss,
            "max_slippage": self.max_slippage,
            "sport_breakdown": games_by_sport,
            "sport_stats": self.get_sport_stats(),
            "games": [
                {
                    "event_id": g.espn_event_id,
                    "matchup": f"{g.away_team} @ {g.home_team}",
                    "sport": g.sport,
                    "status": g.game_status,
                    "period": g.period,
                    "score": f"{g.away_score}-{g.home_score}",
                    "baseline_price": g.baseline_price,
                    "current_price": g.current_price,
                    "has_position": g.has_position,
                    "price_change_pct": (
                        ((g.current_price - g.baseline_price) / g.baseline_price * 100)
                        if g.baseline_price and g.current_price else 0
                    )
                }
                for g in self.tracked_games.values()
            ]
        }


# Singleton instance - initialized per user session
_bot_instances: dict[UUID, BotRunner] = {}


async def get_bot_runner(
    user_id: UUID,
    polymarket_client: PolymarketClient,
    trading_engine: TradingEngine,
    espn_service: ESPNService
) -> BotRunner:
    """
    Get or create bot runner instance for a user.
    
    Args:
        user_id: User ID
        polymarket_client: Configured Polymarket client
        trading_engine: Trading engine instance
        espn_service: ESPN service instance
    
    Returns:
        BotRunner instance
    """
    if user_id not in _bot_instances:
        _bot_instances[user_id] = BotRunner(
            polymarket_client=polymarket_client,
            trading_engine=trading_engine,
            espn_service=espn_service
        )
    
    return _bot_instances[user_id]


def get_bot_status(user_id: UUID) -> dict | None:
    """
    Get bot status for a user without creating instance.
    
    Args:
        user_id: User ID
    
    Returns:
        Status dict or None if not running
    """
    if user_id in _bot_instances:
        return _bot_instances[user_id].get_status()
    return None

