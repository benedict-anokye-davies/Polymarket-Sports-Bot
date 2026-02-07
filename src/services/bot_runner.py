"""
Main bot runner service that orchestrates the trading loop.
Coordinates ESPN game state, Polymarket prices, and trade execution.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Any, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.services.kalshi_client import KalshiClient
from src.services.game_tracker_service import GameTrackerService
from src.services.trading_client_interface import TradingClient
from src.services.espn_service import ESPNService
from src.services.trading_engine import TradingEngine
from src.services.confidence_scorer import ConfidenceScorer, ConfidenceResult
from src.services.kelly_calculator import KellyCalculator
from src.services.advanced_orders import AdvancedOrderManager
from src.services.balance_guardian import BalanceGuardian
from src.db.database import async_session_factory
from src.db.crud.tracked_market import TrackedMarketCRUD
from src.db.crud.position import PositionCRUD
from src.services.market_discovery import DiscoveredMarket, market_discovery as discovery_service

from src.db.crud.global_settings import GlobalSettingsCRUD
from src.db.crud.sport_config import SportConfigCRUD
from src.db.crud.activity_log import ActivityLogCRUD
from src.core.exceptions import TradingError
from src.services.discord_notifier import discord_notifier


logger = logging.getLogger(__name__)


class BotState(Enum):
    """Bot operational states."""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    ERROR = "error"


from src.services.types import TrackedGame, SportStats


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
    - Position recovery on restart
    
    NOTE: This is REAL MONEY trading. All trades execute with actual funds.
    """
    
    # Polling intervals
    ESPN_POLL_INTERVAL = 5.0  # Seconds between ESPN polls
    DISCOVERY_INTERVAL = 10.0  # Seconds between market discovery runs
    HEALTH_CHECK_INTERVAL = 60.0  # Seconds between health checks
    CLEANUP_INTERVAL = 120.0  # Seconds between stale game cleanup runs
    MAX_TRACKED_GAMES = 100  # Maximum number of games to track simultaneously
    
    def __init__(
        self,
        trading_client: KalshiClient,
        trading_engine: TradingEngine,
        espn_service: ESPNService
    ):
        self.trading_client = trading_client
        self.trading_engine = trading_engine
        self.espn_service = espn_service
        self.game_tracker = GameTrackerService(espn_service)

        self.platform = "kalshi"

        self.state = BotState.STOPPED


        # Tracked games keyed by ESPN event ID
        self.tracked_games: dict[str, TrackedGame] = {}

        # Token ID to game mapping for WebSocket updates
        self.token_to_game: dict[str, str] = {}

        # User-selected games from bot config (game_id -> game_config dict)
        # This filters which games the bot will actually track and trade
        self.user_selected_games: dict[str, dict] = {}

        # Clients - typed as TradingClient protocol where possible, but concrete classes have more methods
        self.polymarket_client: TradingClient | None = None
        self.kalshi_client: TradingClient | None = None
        self.websocket: Any | None = None  # WebSocket connection (if used)
        self.db: AsyncSession | None = None

        # Configuration
        self.user_id: UUID | None = None
        self.enabled_sports: list[str] = []
        self.risk_per_trade: float = 0.02
        self.max_daily_loss: float = 100.0
        self.entry_threshold: float = 0.05
        self.take_profit: float = 0.15
        self.stop_loss: float = 0.10
        
        # Trading parameters from frontend config
        self.position_size: float = 100.0  # Max $ per trade
        self.min_volume: float = 50000.0   # Min market volume
        self.latest_entry_time_minutes: int = 10  # No entries after X min left
        self.latest_exit_time_minutes: int = 2    # Force exit at X min left

        # Real money trading - no simulation
        self.max_slippage: float = 0.02
        self.order_fill_timeout: int = 60
        
        # AUTO-TRADE-ALL MODE: When True, bot trades ANY market matching parameters
        # No manual game selection required
        self.auto_trade_all: bool = False

        # Emergency stop flag
        self.emergency_stop: bool = False

        # Per-sport statistics and configuration
        self.sport_stats: dict[str, SportStats] = {}
        self.sport_configs: dict[str, Any] = {}

        # Per-market configuration overrides (keyed by condition_id)
        self.market_configs: dict[str, Any] = {}

        # Concurrent entry locks (prevent double-entry race conditions)
        self._entry_locks: dict[str, asyncio.Lock] = {}

        # Pending orders tracking: order_id -> {market, side, price, size, timestamp}
        self.pending_orders: dict[str, dict] = {}

        # Kelly position sizing and confidence scoring
        self.kelly_calculator = KellyCalculator()
        self.confidence_scorer = ConfidenceScorer()
        self.use_kelly_sizing: bool = False
        self.kelly_fraction: float = 0.25
        self.min_confidence_score: float = 0.6

        # Stats
        self.start_time: datetime | None = None
        self.trades_today: int = 0
        self.daily_pnl: float = 0.0
        
        # Control (required for start/stop)
        self._stop_event = asyncio.Event()
        self._tasks: list[asyncio.Task] = []

    async def _place_order(self, game: TrackedGame, side: str, price: float, size: int) -> Any | None:
        """
        Place order on Kalshi.
        """
        # Kalshi order format
        ticker = game.market.ticker
        if not ticker:
            logger.error(f"No ticker available for Kalshi market: {game.market.question}")
            return None

        # type: ignore
        return await self.trading_client.place_order(
            ticker=ticker,
            side="buy", # Always buying in this simplified runner context
            yes_no=side.lower(),
            price=price,
            size=int(size),
        )

    def _get_order_id(self, order: dict) -> str | None:
        """Get order ID from Kalshi order response."""
        # Kalshi wraps response in {"order": {...}}
        order_data = order.get("order", order)
        return order_data.get("order_id") or order_data.get("id")

    async def _check_slippage(self, game: TrackedGame, price: float, side: str = "buy") -> bool:
        """
        Kalshi slippage check.
        Returns True if slippage is acceptable.
        """
        ticker = game.market.ticker
        if not ticker:
            return True  # Allow trade if no ticker
        slippage_ok, _ = await self.trading_client.check_slippage(ticker, price, side)
        return slippage_ok
    
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
            # Safety settings (REAL MONEY - no paper trading)
            self.emergency_stop = bool(getattr(settings, 'emergency_stop', False))
            self.max_slippage = float(getattr(settings, 'max_slippage_pct', 0.02))
            self.order_fill_timeout = int(getattr(settings, 'order_fill_timeout_seconds', 60))
            
            # AUTO-TRADE-ALL MODE: Trade any market matching parameters
            self.auto_trade_all = bool(getattr(settings, 'auto_trade_all', False))
            if self.auto_trade_all:
                logger.info("AUTO-TRADE-ALL MODE ENABLED: Bot will trade ANY market matching parameters")
            
            # Apply settings to trading client (only set attributes that exist)
            if hasattr(self.trading_client, 'max_slippage'):
                # type: ignore
                self.trading_client.max_slippage = self.max_slippage
            
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
                if sport_key not in self.enabled_sports:
                    self.enabled_sports.append(sport_key)
                # Use config thresholds (first enabled sport sets defaults)
                if config.entry_threshold_drop and self.entry_threshold == 0.05:
                    self.entry_threshold = float(config.entry_threshold_drop)
                if config.take_profit_pct and self.take_profit == 0.15:
                    self.take_profit = float(config.take_profit_pct)
                if config.stop_loss_pct and self.stop_loss == 0.10:
                    self.stop_loss = float(config.stop_loss_pct)

        # Deduplicate and sort enabled sports by priority (lower number = higher priority)
        seen = set()
        deduped = []
        for s in self.enabled_sports:
            if s not in seen:
                seen.add(s)
                deduped.append(s)
        self.enabled_sports = deduped
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
        
        # Kalshi mode: using polling for price updates (no WebSocket)
        logger.info("Kalshi mode: using polling for price updates")
        
        mode_str = "LIVE TRADING - REAL MONEY"
        games_count = len(self.user_selected_games)
        logger.info(
            f"Bot initialized for user {user_id}. "
            f"Mode: {mode_str}, "
            f"Platform: {self.platform.upper()}, "
            f"Sports: {self.enabled_sports}, "
            f"Selected games: {games_count}, "
            f"Entry threshold: {self.entry_threshold:.1%}, "
            f"TP: {self.take_profit:.1%}, SL: {self.stop_loss:.1%}"
        )
    
    async def _load_user_selected_games(self, user_id: UUID) -> None:
        """
        Load user-selected games from BOTH sources:
        1. TrackedMarket table (games selected in Markets page)
        2. Bot config from database (games configured in Bot Config page)

        This ensures games selected in either location are tracked.
        Also updates enabled_sports to include all sports from selected games.

        Args:
            user_id: User ID to load config for
        """
        from src.db.crud.tracked_market import TrackedMarketCRUD

        self.user_selected_games.clear()
        selected_sports: set[str] = set()

        # SOURCE 1: Load from TrackedMarket database (Markets page selections)
        try:
            async with async_session_factory() as db:
                db_selected = await TrackedMarketCRUD.get_selected_for_user(db, user_id)

                for market in db_selected:
                    # Use condition_id as game_id for consistency
                    game_id = market.espn_event_id or market.condition_id
                    if game_id and game_id not in self.user_selected_games:
                        # Build game dict from TrackedMarket
                        self.user_selected_games[game_id] = {
                            "game_id": game_id,
                            "condition_id": market.condition_id,
                            "token_id": market.token_id_yes,
                            "sport": market.sport or "unknown",
                            "home_team": market.home_team,
                            "away_team": market.away_team,
                            "question": market.question,
                            "selected_side": "home",  # Default
                            "source": "markets_page"
                        }
                        sport = (market.sport or "").lower()
                        if sport:
                            selected_sports.add(sport)
                        logger.info(
                            f"Loaded market-selected game: {market.away_team or '?'} @ "
                            f"{market.home_team or '?'} ({sport.upper()})"
                        )
        except Exception as e:
            logger.warning(f"Could not load TrackedMarket selections: {e}")

        # SOURCE 2: Load from bot config in database (avoids circular import with bot.py routes)
        config: dict = {}
        try:
            async with async_session_factory() as db:
                config = await GlobalSettingsCRUD.get_bot_config(db, user_id) or {}
        except Exception as e:
            logger.warning(f"Could not load bot config from DB: {e}")

        games = config.get("games", [])
        
        # Fallback to single game if "games" array not present
        if not games and config.get("game"):
            games = [config["game"]]
        
        for game in games:
            game_id = game.get("game_id")
            if game_id and game_id not in self.user_selected_games:
                self.user_selected_games[game_id] = game
                self.user_selected_games[game_id]["source"] = "bot_config"
                sport = game.get("sport", "").lower()
                if sport:
                    selected_sports.add(sport)
                logger.info(
                    f"Loaded config-selected game: {game.get('away_team', '?')} @ "
                    f"{game.get('home_team', '?')} ({sport.upper()}), "
                    f"side: {game.get('selected_side', 'home')}"
                )
        
        # LOAD TRADING PARAMETERS from frontend config
        params = config.get("parameters")
        if params:
            # Position sizing
            if params.get("position_size"):
                self.position_size = float(params["position_size"])
            else:
                self.position_size = 100.0  # Default $100
            
            # Entry threshold (probability drop)
            if params.get("probability_drop"):
                self.entry_threshold = float(params["probability_drop"]) / 100.0  # Convert % to decimal
            
            # Exit conditions
            if params.get("take_profit"):
                self.take_profit = float(params["take_profit"]) / 100.0  # Convert % to decimal
            if params.get("stop_loss"):
                self.stop_loss = float(params["stop_loss"]) / 100.0  # Convert % to decimal
            
            # Volume threshold
            if params.get("min_volume"):
                self.min_volume = float(params["min_volume"])
            else:
                self.min_volume = 50000.0  # Default $50k
            
            # Time-based rules
            if params.get("latest_entry_time") is not None:
                self.latest_entry_time_minutes = int(params["latest_entry_time"])
            else:
                self.latest_entry_time_minutes = 10  # Default 10 min
            
            if params.get("latest_exit_time") is not None:
                self.latest_exit_time_minutes = int(params["latest_exit_time"])
            else:
                self.latest_exit_time_minutes = 2  # Default 2 min
            
            logger.info(
                f"Loaded trading parameters from config: "
                f"position_size=${self.position_size:.0f}, "
                f"entry_threshold={self.entry_threshold:.1%}, "
                f"TP={self.take_profit:.1%}, SL={self.stop_loss:.1%}, "
                f"min_volume=${self.min_volume:.0f}, "
                f"entry_cutoff={self.latest_entry_time_minutes}min, "
                f"exit_before={self.latest_exit_time_minutes}min"
            )
        else:
            # Set defaults if no params in config
            self.position_size = 100.0
            self.min_volume = 50000.0
            self.latest_entry_time_minutes = 10
            self.latest_exit_time_minutes = 2
            logger.info("No trading parameters in config, using defaults")

        # Validate trading parameter ranges
        self.entry_threshold = max(0.01, min(0.99, self.entry_threshold))
        self.take_profit = max(0.01, min(0.99, self.take_profit))
        self.stop_loss = max(0.01, min(0.99, self.stop_loss))
        self.position_size = max(0.01, min(10000.0, self.position_size))
        self.min_volume = max(0.0, self.min_volume)
        if self.latest_exit_time_minutes >= self.latest_entry_time_minutes:
            logger.warning(
                f"Exit cutoff ({self.latest_exit_time_minutes}min) >= entry cutoff "
                f"({self.latest_entry_time_minutes}min), adjusting exit to entry - 1"
            )
            self.latest_exit_time_minutes = max(1, self.latest_entry_time_minutes - 1)

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
        await discord_notifier.notify_bot_started(str(self.user_id), self.enabled_sports)
        
        # Log activity
        await ActivityLogCRUD.info(
            db,
            self.user_id,
            "BOT",
            f"Bot started for sports: {', '.join(self.enabled_sports)}",
            {"sports": self.enabled_sports}
        )
        
        # Start background tasks
        self._tasks = [
            asyncio.create_task(self._discovery_loop(), name="discovery"),
            asyncio.create_task(self._espn_poll_loop(), name="espn_poll"),
            asyncio.create_task(self._price_poll_loop(), name="price_poll"),
            asyncio.create_task(self._trading_loop(), name="trading"),
            asyncio.create_task(self._health_check_loop(), name="health"),
            asyncio.create_task(self._cleanup_loop(), name="cleanup"),
        ]
        

        
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
            await ActivityLogCRUD.info(
                db,
                self.user_id,
                "BOT",
                f"Bot stopped. Trades: {self.trades_today}, PnL: ${self.daily_pnl:.2f}",
                {
                    "trades": self.trades_today,
                    "pnl": self.daily_pnl
                }
            )
        
        # Close trading client to release HTTP connections
        if hasattr(self.trading_client, 'close'):
            try:
                await self.trading_client.close()
            except Exception as e:
                logger.warning(f"Error closing trading client: {e}")

        self.state = BotState.STOPPED
        self.tracked_games.clear()
        self.token_to_game.clear()

        # Remove from singleton cache to free memory
        if self.user_id and self.user_id in _bot_instances:
            del _bot_instances[self.user_id]

        logger.info("Trading bot stopped")
    
    async def _discovery_loop(self) -> None:
        """
        Periodically discover new sports markets.
        
        Only tracks games that the user has explicitly selected in bot config.
        Runs every DISCOVERY_INTERVAL seconds.
        Uses platform-aware discovery (Polymarket Gamma API or Kalshi Sports API).
        """
        while not self._stop_event.is_set():
            try:
                async with async_session_factory() as db:
                    logger.info(f"Running market discovery for {self.platform}...")

                    # Skip discovery if no games selected by user AND auto_trade_all is disabled
                    if not self.user_selected_games and not self.auto_trade_all:
                        logger.debug("No user-selected games to track and auto_trade_all is disabled")
                        await asyncio.sleep(self.DISCOVERY_INTERVAL)
                        continue

                    # Use Kalshi market discovery
                    markets = await discovery_service.discover_kalshi_markets(
                        sports=self.enabled_sports,
                        hours_ahead=48,  # Look ahead 48 hours (today/tomorrow)
                        include_live=True
                    )

                    logger.info(f"Discovered {len(markets)} sports markets")

                    # 1. Direct Ticker Matching (Bypass ESPN Search)
                    for game_id, config in list(self.user_selected_games.items()):
                        if game_id in self.tracked_games:
                            continue

                        target_ticker = config.get("market_ticker")
                        if target_ticker:
                            matched = next((m for m in markets if m.ticker == target_ticker), None)
                            if matched:
                                logger.info(f"Direct Match Found for Ticker {target_ticker}")
                                # Create Synthetic Game Object
                                fake_game = {
                                    "id": game_id,
                                    "name": f"{matched.away_team} at {matched.home_team}",
                                    "shortName": f"{matched.away_team} @ {matched.home_team}",
                                    "competitions": [{
                                        "competitors": [
                                            {"homeAway": "home", "team": {"displayName": matched.home_team, "name": matched.home_team}},
                                            {"homeAway": "away", "team": {"displayName": matched.away_team, "name": matched.away_team}}
                                        ],
                                        "status": {"type": {"state": "pre", "name": "STATUS_SCHEDULED"}},
                                        "date": matched.game_start_time.isoformat() if matched.game_start_time else datetime.now().isoformat()
                                    }]
                                }
                                await self._start_tracking_game(
                                    db,
                                    event_id=game_id,
                                    sport=matched.sport,
                                    home_team=matched.home_team or "Home",
                                    away_team=matched.away_team or "Away",
                                    market=matched,
                                    game_data=fake_game,
                                    selected_side=config.get("selected_side", "home")
                                )

                    # 2. Match markets to ESPN games - ONLY for user-selected games
                    for sport in self.enabled_sports:
                        games = await self.espn_service.get_live_games(sport)

                        for game in games:
                            event_id = game.get("id")

                            if event_id in self.tracked_games:
                                continue  # Already tracking

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
                                # Check if this market is user-selected (by ESPN ID or Condition ID)
                                user_game_config = self.user_selected_games.get(event_id)
                                if not user_game_config:
                                    user_game_config = self.user_selected_games.get(matched_market.condition_id)

                                # AUTO-TRADE-ALL MODE: If enabled, automatically trade ALL markets that match parameters
                                if not user_game_config and self.auto_trade_all:
                                    # In auto mode, we trade ANY team that matches - pick based on which side meets criteria
                                    # Default to home side, trading engine will evaluate both sides
                                    user_game_config = {
                                        "game_id": event_id,
                                        "sport": sport,
                                        "selected_side": "auto",  # Special value: engine will pick the best side
                                        "auto_selected": True
                                    }
                                    logger.info(f"AUTO-TRADE: Auto-selecting market {matched_market.ticker} ({home_name} vs {away_name})")
                                
                                # If still not found and not in auto mode, skip
                                if not user_game_config:
                                    continue

                                selected_side = user_game_config.get("selected_side", "home")

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
                # Log to activity database using a fresh session
                if self.user_id:
                    try:
                        async with async_session_factory() as error_db:
                            await ActivityLogCRUD.error(
                                error_db,
                                self.user_id,
                                "DISCOVERY",
                                f"Market discovery failed: {str(e)[:200]}",
                                {"error_type": type(e).__name__, "loop": "discovery"}
                            )
                    except Exception as log_err:
                        logger.debug(f"Suppressed logging error: {log_err}")
            
            await asyncio.sleep(self.DISCOVERY_INTERVAL)
    
    async def _espn_poll_loop(self) -> None:
        """
        Poll ESPN for game state updates.
        
        Runs every ESPN_POLL_INTERVAL seconds.
        """
        while not self._stop_event.is_set():
            try:
                async with async_session_factory() as db:
                    # Use GameTrackerService to update all games
                    finished_games = await self.game_tracker.update_all_games()

                    # Update local tracked games map in case the service modified it (unlikely but safe)
                    self.tracked_games = self.game_tracker.tracked_games

                    for game in finished_games:
                        # Log finished game
                        logger.info(f"Game finished: {game.home_team} vs {game.away_team}")
                        await self._handle_game_finished(db, game)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in ESPN poll loop: {e}")
                # Log to activity database using a fresh session
                if self.user_id:
                    try:
                        async with async_session_factory() as error_db:
                            await ActivityLogCRUD.warning(
                                error_db,
                                self.user_id,
                                "ESPN",
                                f"ESPN polling error: {str(e)[:200]}",
                                {"error_type": type(e).__name__, "loop": "espn_poll"}
                            )
                    except Exception as log_err:
                        logger.debug(f"Suppressed logging error: {log_err}")
            
            await asyncio.sleep(self.ESPN_POLL_INTERVAL)

    async def _price_poll_loop(self) -> None:
        """
        Poll Kalshi for price updates on tracked markets in parallel.

        Runs every PRICE_POLL_INTERVAL seconds.
        Crucial for Kalshi since we don't have WebSocket price feeds.
        Uses asyncio.gather for parallel HTTP requests instead of sequential polling.
        """
        PRICE_POLL_INTERVAL = 10.0

        async def _fetch_and_update_price(event_id: str, game) -> None:
            """Fetch price for a single market and update tracked game state."""
            try:
                market_data = await self.trading_client.get_market(game.market.ticker)  # type: ignore

                if not market_data:
                    return

                # Extract market info (Kalshi wraps in "market" key usually)
                data = market_data.get("market", market_data)

                # Kalshi returns prices in cents (1-99). Normalize to 0-1.
                yes_ask = data.get("yes_ask", 0)

                # Update TrackedGame state
                game.current_price = float(yes_ask) / 100.0 if yes_ask > 0 else None

                # Update DB model-like market object attached to game
                if game.market:
                    game.market.current_price_yes = Decimal(str(game.current_price)) if game.current_price is not None else None
                    game.market.current_price_no = Decimal(str(1.0 - game.current_price)) if game.current_price is not None else None

            except Exception as e:
                logger.warning(f"Failed to fetch price for {game.market.ticker}: {e}")

        while not self._stop_event.is_set():
            try:
                # Build list of price fetch tasks for all tracked games with markets
                tasks = []
                for event_id, game in list(self.tracked_games.items()):
                    if not game.market or not game.market.ticker:
                        continue
                    tasks.append(_fetch_and_update_price(event_id, game))

                # Execute all price fetches in parallel
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in price poll loop: {e}")
                
            await asyncio.sleep(PRICE_POLL_INTERVAL)
    

    
    async def _trading_loop(self) -> None:
        """
        Main trading decision loop.
        
        Evaluates entry/exit conditions for all tracked games.
        """
        while not self._stop_event.is_set():
            try:
                async with async_session_factory() as db:
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
                    except Exception as log_err:
                        logger.debug(f"Suppressed logging error: {log_err}")
            
            await asyncio.sleep(1)  # Check every second
    
    def _build_tracked_market_from_game(self, game: TrackedGame) -> "TrackedMarket":
        """
        Build a TrackedMarket object from a TrackedGame for TradingEngine.
        
        TradingEngine expects TrackedMarket (DB model format) while bot_runner
        uses TrackedGame (runtime dataclass). This adapts between them.
        
        Note: This creates a detached model object not persisted to DB.
        """
        from src.models import TrackedMarket
        
        # Handle baseline price - use market's current price if no baseline captured
        baseline = game.baseline_price
        if baseline is None:
            baseline = game.market.current_price_yes if hasattr(game.market, 'current_price_yes') else 0.5
        
        # Get current price from tracked game or market discovery
        current = game.current_price
        if current is None:
            current = game.market.current_price_yes if hasattr(game.market, 'current_price_yes') else baseline
        
        # Create a TrackedMarket-like object with fields TradingEngine expects
        market = TrackedMarket(
            id=game.position_id or uuid.uuid4(),
            user_id=self.user_id,
            condition_id=game.market.condition_id or game.market.ticker or "",
            token_id_yes=game.market.token_id_yes or "",
            token_id_no=game.market.token_id_no or "",
            question=game.market.question or "",
            sport=game.sport,
            home_team=game.home_team,
            away_team=game.away_team,
            baseline_price_yes=Decimal(str(baseline)),
            baseline_price_no=Decimal(str(1 - baseline)),
            current_price_yes=Decimal(str(current)),
            current_price_no=Decimal(str(1 - current)),
            is_live=game.game_status == "in",
            current_period=game.period,
        )
        return market
    
    def _build_game_state_from_game(self, game: TrackedGame) -> dict:
        """
        Build a game_state dictionary from TrackedGame for TradingEngine.
        """
        segment = self._get_game_segment(game)
        time_remaining = self._get_time_remaining_seconds(game)
        
        return {
            "is_live": game.game_status == "in",
            "segment": segment,
            "period": game.period,
            "clock": game.clock,
            "time_remaining_seconds": time_remaining or 0,
            "home_score": game.home_score,
            "away_score": game.away_score,
            "home_team": game.home_team,
            "away_team": game.away_team,
            "selected_side": game.selected_side,
        }

    async def _find_matching_market(
        self,
        markets: list[Any],
        home_name: str,
        away_name: str,
        sport: str
    ) -> Any | None:
        """
        Find a market that matches the given game teams.
        """
        # Normalize names for matching
        home_norm = home_name.lower()
        away_norm = away_name.lower()
        
        for m in markets:
            # Handle both dict and object (DiscoveredMarket)
            if isinstance(m, dict):
                 m_home = m.get("home_team", "").lower() 
                 m_away = m.get("away_team", "").lower()
            else:
                 m_home = (m.home_team or "").lower()
                 m_away = (m.away_team or "").lower()
            
            # Simple substring matching
            if (m_home in home_norm or home_norm in m_home) and \
               (m_away in away_norm or away_norm in m_away):
                return m
                
        return None

    async def _evaluate_entry(self, db: AsyncSession, game: TrackedGame) -> None:
        """
        Evaluate entry conditions for a game using TradingEngine.
        
        Delegates the evaluation logic to TradingEngine.evaluate_entry() which handles:
        - Config lookups (sport, market overrides)
        - Segment/time validation
        - Price condition checks
        - Confidence scoring
        - Position sizing (Kelly or fixed)
        - Risk limit checks
        
        Bot runner handles:
        - Emergency stop check
        - Selected side filtering
        - Market enabled check
        - Entry lock acquisition
        - Order execution
        - Position recording
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
        
        # TIME-BASED ENTRY CUTOFF: Check if too little time remaining
        # Uses frontend config's latest_entry_time_minutes
        if hasattr(self, 'latest_entry_time_minutes'):
            time_remaining_sec = self._get_time_remaining_seconds(game)
            entry_cutoff_sec = self.latest_entry_time_minutes * 60
            if time_remaining_sec is not None and time_remaining_sec < entry_cutoff_sec:
                logger.debug(
                    f"Entry blocked: {time_remaining_sec}s remaining < {entry_cutoff_sec}s entry cutoff "
                    f"({self.latest_entry_time_minutes} min)"
                )
                return

        # Build objects for TradingEngine
        tracked_market = self._build_tracked_market_from_game(game)
        game_state = self._build_game_state_from_game(game)
        
        # Build overrides from frontend config
        overrides = {}
        if hasattr(self, 'position_size') and self.position_size:
            # Note: frontend sends position_size, engine expects position_size_usdc
            overrides['position_size_usdc'] = float(self.position_size)
            logger.debug(f"Passing override position_size: ${self.position_size}")
            
        if hasattr(self, 'entry_threshold') and self.entry_threshold:
            # Convert percentage 5.5 -> 0.055
            overrides['entry_threshold_drop'] = float(self.entry_threshold) / 100.0
            
        if hasattr(self, 'min_pregame_probability') and self.min_pregame_probability:
            overrides['min_pregame_probability'] = float(self.min_pregame_probability)

        # Update TradingEngine's db session with current loop session
        # This is necessary because TradingEngine was initialized with a request-scoped
        # session that may be stale by the time the trading loop runs
        self.trading_engine.db = db
        
        # Delegate entry evaluation to TradingEngine with overrides
        entry_signal = await self.trading_engine.evaluate_entry(
            tracked_market, 
            game_state,
            overrides=overrides
        )
        
        if not entry_signal:
            return
        
        # Extract signal details
        position_size = entry_signal["position_size"]
        price = entry_signal["price"]
        side = entry_signal["side"]
        token_id = entry_signal["token_id"]
        reason = entry_signal["reason"]
        confidence_score = entry_signal.get("confidence_score", 0.6)
        confidence_breakdown = entry_signal.get("confidence_breakdown", {})
        
        logger.info(
            f"Entry signal from TradingEngine: {game.home_team} vs {game.away_team} "
            f"side={side} price=${price:.4f} size=${position_size:.2f} "
            f"confidence={confidence_score:.2f} reason={reason}"
        )

        # Acquire lock to prevent double-entry
        lock = self._get_entry_lock(token_id)
        if lock.locked():
            logger.debug(f"Entry already in progress for {token_id}")
            return

        async with lock:
            # Double-check position status after acquiring lock
            if game.has_position:
                logger.debug(f"Position already exists after lock acquisition for {token_id}")
                return
            
            # Check DB for existing open positions
            existing = await PositionCRUD.get_open_for_market(
                db, self.user_id, game.market.condition_id or game.market.ticker or ""
            )
            if existing:
                logger.debug(f"Open position found in DB for {game.market.condition_id}")
                game.has_position = True
                return

            # Slippage check before execution
            slippage_ok = await self._check_slippage(game, price, "buy")
            if not slippage_ok:
                logger.warning(f"Slippage too high for {game.home_team} vs {game.away_team}")
                return

            # ========== CRITICAL: LIVE-ONLY TRADING ENFORCEMENT ==========
            # Final validation: ONLY execute if game is LIVE
            # Use both ESPN status AND Kalshi time-based detection
            # 
            # Priority:
            # 1. If ESPN says "in" -> game is live
            # 2. If ESPN status unavailable/stale, use Kalshi time-based detection
            is_live_espn = game.game_status == "in"
            is_live_kalshi = self._is_game_live_by_kalshi(game)
            
            if not is_live_espn and not is_live_kalshi:
                logger.warning(
                    f"BLOCKED pre-game entry: {game.home_team} vs {game.away_team} "
                    f"espn_status='{game.game_status}' kalshi_live={is_live_kalshi} "
                    f"(game must be LIVE for trading)"
                )
                return
            
            # Log which detection method we're using
            if is_live_espn:
                logger.info(
                    f"LIVE TRADE (ESPN): {game.home_team} vs {game.away_team} "
                    f"status='{game.game_status}' period={game.period} clock={game.clock}"
                )
            else:
                logger.info(
                    f"LIVE TRADE (Kalshi time): {game.home_team} vs {game.away_team} "
                    f"espn_status='{game.game_status}' - using Kalshi game_start_time"
                )
            # =============================================================

            # Execute entry
            await self._execute_entry_order(
                db, game, token_id, side, price, position_size,
                reason, confidence_score, confidence_breakdown
            )

    
    async def _execute_entry_order(
        self,
        db: AsyncSession,
        game: TrackedGame,
        token_id: str,
        side: str,
        price: float,
        position_size: float,
        reason: str,
        confidence_score: float,
        confidence_breakdown: dict
    ) -> None:
        """
        Execute an entry order and record the position.
        
        Separated from _evaluate_entry for clarity and testability.
        """
        sport_key = game.sport.lower()
        
        try:
            order = await self._place_order(game, side, price, int(position_size))

            if order:
                order_id = self._get_order_id(order)
                
                # Track as pending order
                self.pending_orders[order_id] = {
                    "market": game.market.condition_id or game.market.ticker,
                    "side": side,
                    "price": price,
                    "size": position_size,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "action": "BUY"
                }

                # Wait for fill with timeout
                fill_status = await self.trading_client.wait_for_fill(
                    order_id,
                    timeout=self.order_fill_timeout
                )

                if fill_status != "filled":
                    logger.warning(f"Order not filled: {fill_status}")
                    # Remove from pending
                    self.pending_orders.pop(order_id, None)
                    try:
                        await self.trading_client.cancel_order(order_id)
                    except Exception as cancel_err:
                        logger.debug(f"Order cancel failed: {cancel_err}")
                    return
                
                # Remove from pending now that it's filled
                self.pending_orders.pop(order_id, None)

                # Record position
                entry_cost = position_size * price
                token_or_ticker = game.market.ticker if self.platform == "kalshi" else token_id
                
                try:
                    position = await PositionCRUD.create(
                        db,
                        user_id=self.user_id,
                        condition_id=game.market.condition_id or game.market.ticker or "",
                        token_id=token_or_ticker or "",
                        side=side,
                        entry_price=Decimal(str(price)),
                        entry_size=Decimal(str(position_size)),
                        entry_cost_usdc=Decimal(str(entry_cost)),
                        entry_reason=reason,
                        entry_order_id=order_id,
                        entry_confidence_score=int(confidence_score * 100),
                        entry_confidence_breakdown=confidence_breakdown,
                    )
                except Exception as position_error:
                    logger.critical(
                        f"ORPHANED ORDER: Order {order_id} filled but position creation failed. "
                        f"Market: {game.market.condition_id}, Token: {token_or_ticker}, "
                        f"Size: {position_size}, Price: {price}, Error: {position_error}"
                    )
                    try:
                        await discord_notifier.send_alert(
                            f"CRITICAL: Orphaned order {order_id} - position record failed.",
                            level="critical"
                        )
                    except Exception as alert_err:
                        logger.debug(f"Alert notification failed: {alert_err}")
                    raise
                
                game.has_position = True
                game.position_id = position.id
                self.trades_today += 1

                # Update per-sport stats
                sport_stats = self.sport_stats.get(sport_key)
                if sport_stats:
                    sport_stats.trades_today += 1
                    sport_stats.open_positions += 1
                
                await discord_notifier.notify_trade_entry(
                    market_name=f"{game.market.question[:100]}",
                    side=side,
                    price=price,
                    size=position_size,
                    baseline_price=game.baseline_price,
                    trigger_reason=reason
                )
                
                logger.info(f"Entry executed: {position_size:.2f} contracts at ${price:.4f}")
        
        except Exception as e:
            logger.error(f"Failed to execute entry: {e}")
            await discord_notifier.notify_error("Entry Failed", str(e), "entry_execution")
            if self.user_id:
                try:
                    await ActivityLogCRUD.error(
                        db,
                        self.user_id,
                        "TRADE",
                        f"Entry order failed for {game.home_team} vs {game.away_team}",
                        {
                            "error": str(e)[:200],
                            "token_id": token_id[:20] if token_id else "unknown",
                            "attempted_price": price,
                            "attempted_size": position_size
                        }
                    )
                except Exception as log_err:
                    logger.debug(f"Suppressed logging error: {log_err}")

    async def _evaluate_exit(self, db: AsyncSession, game: TrackedGame) -> None:
        """
        Evaluate exit conditions for an open position using TradingEngine.
        
        Delegates evaluation logic to TradingEngine.evaluate_exit() which handles:
        - Take profit threshold check
        - Stop loss threshold check
        - Game finished check
        - Restricted segment check
        
        Bot runner additionally checks:
        - Emergency stop
        - Time-based exit (exit_time_remaining_seconds)
        - Segment-based exit (exit_before_segment)
        
        Then handles:
        - Order execution
        - Position closure recording
        - Stats updates
        - Notifications
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

        # Build objects for TradingEngine
        tracked_market = self._build_tracked_market_from_game(game)
        game_state = self._build_game_state_from_game(game)
        game_state["is_finished"] = game.game_status == "post"
        
        # Update TradingEngine's db session
        self.trading_engine.db = db

        exit_reason = None
        exit_message = None

        # Check emergency stop first (not handled by TradingEngine)
        if self.emergency_stop:
            exit_reason = "emergency_stop"
            exit_message = "Emergency stop activated"
        else:
            # Build overrides from frontend config
            # NOTE: self.take_profit and self.stop_loss are ALREADY decimals (e.g., 0.15 for 15%)
            # They were converted from percentage in _load_user_selected_games
            overrides = {}
            if hasattr(self, 'take_profit') and self.take_profit:
                overrides['take_profit_pct'] = float(self.take_profit)  # Already decimal, don't divide again!
            if hasattr(self, 'stop_loss') and self.stop_loss:
                overrides['stop_loss_pct'] = float(self.stop_loss)  # Already decimal, don't divide again!
            
            logger.debug(
                f"Exit evaluation using: take_profit={self.take_profit:.2%}, stop_loss={self.stop_loss:.2%}"
            )

            # Delegate to TradingEngine for standard exit conditions
            exit_signal = await self.trading_engine.evaluate_exit(
                position, 
                tracked_market, 
                game_state,
                overrides=overrides
            )
            
            if exit_signal:
                exit_reason = exit_signal["reason"]
                exit_message = exit_signal.get("message", exit_reason)
            else:
                # Check additional bot_runner-specific exit conditions
                
                # FRONTEND CONFIG TIME-BASED FORCED EXIT
                # Uses latest_exit_time_minutes from frontend config
                if hasattr(self, 'latest_exit_time_minutes'):
                    time_remaining = self._get_time_remaining_seconds(game)
                    exit_threshold_sec = self.latest_exit_time_minutes * 60
                    if time_remaining is not None and time_remaining <= exit_threshold_sec:
                        exit_reason = f"time_exit_{time_remaining}s_remaining"
                        exit_message = (
                            f"Forced exit: {time_remaining}s remaining <= "
                            f"{exit_threshold_sec}s threshold ({self.latest_exit_time_minutes} min)"
                        )
                        logger.info(exit_message)
                
                # Time-based exit from database config (fallback)
                if not exit_reason:
                    exit_time_remaining = self._get_effective_config(game, 'exit_time_remaining_seconds', None)
                    if exit_time_remaining is not None:
                        time_remaining = self._get_time_remaining_seconds(game)
                        if time_remaining is not None and time_remaining <= exit_time_remaining:
                            exit_reason = f"time_exit_{time_remaining}s_remaining"
                            exit_message = f"Time-based exit: {time_remaining}s remaining, threshold {exit_time_remaining}s"
                            logger.info(exit_message)

                # Segment-based exit (more granular than TradingEngine's segment check)
                exit_before_segment = self._get_effective_config(game, 'exit_before_segment', None)
                if not exit_reason and exit_before_segment:
                    current_segment = self._get_game_segment(game)
                    if self._is_past_segment(current_segment, exit_before_segment):
                        exit_reason = f"segment_exit_{current_segment}"
                        exit_message = f"Segment-based exit: in {current_segment}, must exit before {exit_before_segment}"
                        logger.info(exit_message)

        if not exit_reason:
            return

        # Calculate P&L for logging
        pnl_pct = (current_price - entry_price) / entry_price if entry_price else 0
        
        logger.info(
            f"Exit signal ({exit_reason}): {game.home_team} "
            f"P&L: {pnl_pct:.1%} - {exit_message}"
        )
        
        # Execute exit
        await self._execute_exit_order(db, game, position, current_price, exit_reason)

    async def _execute_exit_order(
        self,
        db: AsyncSession,
        game: TrackedGame,
        position: Any,
        current_price: float,
        exit_reason: str
    ) -> None:
        """
        Execute an exit order and record the position closure.
        
        Separated from _evaluate_exit for clarity and testability.
        """
        entry_price = float(position.entry_price)
        pnl_pct = (current_price - entry_price) / entry_price if entry_price else 0
        
        try:
            exit_size = float(position.entry_size)
            order = await self._place_order(game, "SELL", current_price, int(exit_size))

            if order:
                order_id = self._get_order_id(order)
                
                # Track as pending order
                self.pending_orders[order_id] = {
                    "market": game.market.condition_id or game.market.ticker,
                    "side": position.side,
                    "price": current_price,
                    "size": exit_size,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "action": "SELL"
                }
                
                pnl = (current_price - entry_price) * exit_size
                exit_proceeds = current_price * exit_size
                
                # Remove from pending after order placed

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
                
                # Remove from pending after successful fill
                self.pending_orders.pop(order_id, None)
                
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
                
                await discord_notifier.notify_trade_exit(
                    market_name=f"{game.market.question[:100]}",
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
                except Exception as log_err:
                    logger.debug(f"Suppressed logging error: {log_err}")

    async def _health_check_loop(self) -> None:
        """
        Periodic health checks and stats logging.
        """
        while not self._stop_event.is_set():
            try:
                # No DB access needed for basic health check stats logging
                # If DB access added later, use: async with async_session_factory() as db:
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
    
    async def _cleanup_loop(self) -> None:
        """
        Periodically clean up stale or finished games from tracked_games.
        
        Prevents unbounded memory growth by removing games that:
        - Have status 'post' (finished)
        - Haven't been updated in over 6 hours
        - Exceed the maximum tracked games limit
        """
        while not self._stop_event.is_set():
            try:
                async with async_session_factory() as db:
                    now = datetime.now(timezone.utc)
                    stale_threshold = timedelta(hours=6)
                    games_to_remove = []
                
                    for event_id, game in list(self.tracked_games.items()):
                        # Remove finished games without positions
                        if game.game_status == "post" and not game.has_position:
                            games_to_remove.append((event_id, "finished"))
                            continue
                    
                        # Remove stale games that haven't updated
                        if game.last_update:
                            time_since_update = now - game.last_update
                            if time_since_update > stale_threshold and not game.has_position:
                                games_to_remove.append((event_id, "stale"))
                                continue
                
                    # Clean up identified games
                    for event_id, reason in games_to_remove:
                        game = self.tracked_games.get(event_id)
                        if game:
                            logger.info(
                                f"Cleanup: removing {reason} game {game.home_team} vs "
                                f"{game.away_team} (event_id={event_id})"
                            )
                            await self._handle_game_finished(db, game)
                    
                    # ALSO Clean up stale unselected markets from DB to clear "Available Games"
                    # Default 12 hours cutoff for unselected games
                    deleted = await TrackedMarketCRUD.cleanup_stale_unselected(db, stale_threshold_hours=12)
                    if deleted > 0:
                        logger.info(f"Cleanup: removed {deleted} stale unselected markets from DB")
                
                    # Enforce maximum tracked games limit if exceeded
                    if len(self.tracked_games) > self.MAX_TRACKED_GAMES:
                        excess = len(self.tracked_games) - self.MAX_TRACKED_GAMES
                        logger.warning(
                            f"Tracked games ({len(self.tracked_games)}) exceeds limit "
                            f"({self.MAX_TRACKED_GAMES}). Removing {excess} oldest games."
                        )
                    
                        # Sort by last_update and remove oldest without positions
                        sorted_games = sorted(
                            self.tracked_games.items(),
                            key=lambda x: x[1].last_update or datetime.min.replace(tzinfo=timezone.utc)
                        )
                    
                        removed = 0
                        for event_id, game in sorted_games:
                            if removed >= excess:
                                break
                            if not game.has_position:
                                await self._handle_game_finished(db, game)
                                removed += 1
                
                    if games_to_remove:
                        logger.info(f"Cleanup complete: removed {len(games_to_remove)} games")
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup loop error: {e}")
            
            await asyncio.sleep(self.CLEANUP_INTERVAL)
    
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
            open_positions = await PositionCRUD.get_open_for_user(db, self.user_id)
            
            if not open_positions:
                logger.info("No open positions to recover")
                return
            
            logger.info(f"Recovering {len(open_positions)} open positions")
            
            for position in open_positions:
                # Get the tracked market data
                tracked_market = await TrackedMarketCRUD.get_by_condition_id(
                    db, self.user_id, position.condition_id
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
                
                # Create tracked game entry.
                # Prefer real ESPN event ID. Fall back to condition_id to avoid
                # synthetic keys that can cause duplicate tracking when the
                # discovery loop later finds the real ESPN event ID.
                event_id = (
                    tracked_market.espn_event_id
                    or tracked_market.condition_id
                    or f"recovered_{position.id}"
                )

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
                self.game_tracker.add_game(tracked)
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

    def _calculate_entry_confidence(self, game: TrackedGame) -> ConfidenceResult:
        """
        Calculate multi-factor confidence score for entry signal.
        
        Evaluates price movement quality, market liquidity indicators,
        and game timing factors to determine signal reliability.
        
        Args:
            game: Game being evaluated for entry
        
        Returns:
            ConfidenceResult with overall score and factor breakdown
        """
        current_price = Decimal(str(game.current_price or 0.5))
        baseline_price = Decimal(str(game.baseline_price or 0.5))
        
        # Estimate time remaining based on period and sport
        time_remaining = self._get_time_remaining_seconds(game) or 600
        total_period_seconds = self._get_total_period_seconds(game.sport) or 720
        
        # Get score differential if available
        score_diff = abs(game.home_score - game.away_score) if game.home_score and game.away_score else None
        
        # Determine periods based on sport
        total_periods = self._get_total_periods(game.sport)
        
        return self.confidence_scorer.calculate_confidence(
            current_price=current_price,
            baseline_price=baseline_price,
            time_remaining_seconds=time_remaining,
            total_period_seconds=total_period_seconds,
            orderbook=None,
            recent_prices=None,
            game_score_diff=score_diff,
            current_period=game.period,
            total_periods=total_periods,
        )

    async def _calculate_kelly_position_size(
        self,
        game: TrackedGame,
        bankroll: Decimal,
        confidence_score: float,
        default_size: float,
        db: AsyncSession
    ) -> float:
        """
        Calculate optimal position size using Kelly criterion.
        
        Uses confidence score to estimate win probability and calculates
        optimal sizing based on available bankroll and historical performance.
        
        Args:
            game: Game being traded
            bankroll: Available trading capital
            confidence_score: Confidence score from entry evaluation
            default_size: Default position size to fall back to
            db: Database session for historical stats
        
        Returns:
            Optimal position size in USDC
        """
        try:
            current_price = Decimal(str(game.current_price or 0.5))
            
            # Convert confidence score to win probability estimate
            # Higher confidence = higher estimated edge
            win_prob = 0.5 + (confidence_score - 0.5) * 0.3
            
            # Get historical trade statistics for calibration
            historical_win_rate = None
            sample_size = 0
            if self.user_id:
                trade_stats = await PositionCRUD.get_trade_stats(db, self.user_id)
                if trade_stats:
                    historical_win_rate = trade_stats.get("win_rate")
                    sample_size = trade_stats.get("total_trades", 0)
            
            # Get Kelly fraction from sport config
            sport_key = game.sport.lower()
            sport_config = self.sport_configs.get(sport_key)
            kelly_fraction = float(getattr(sport_config, 'kelly_fraction', self.kelly_fraction)) if sport_config else self.kelly_fraction
            
            self.kelly_calculator.kelly_fraction = kelly_fraction
            
            kelly_result = self.kelly_calculator.calculate(
                bankroll=bankroll,
                current_price=current_price,
                estimated_win_prob=win_prob,
                historical_win_rate=historical_win_rate,
                historical_sample_size=sample_size,
                max_position_size=Decimal(str(default_size * 2)),
                min_position_size=Decimal("1"),
            )
            
            if kelly_result.recommended_contracts > 0:
                kelly_size = kelly_result.adjusted_size
                # Cap at 2x default size for safety
                return min(kelly_size, default_size * 2)
            
            logger.debug(f"Kelly sizing returned 0 contracts: {kelly_result.sizing_reason}")
            
        except Exception as e:
            logger.warning(f"Kelly calculation failed, using default size: {e}")
        
        return default_size

    def _get_total_period_seconds(self, sport: str) -> int:
        """Get total seconds in a period for the given sport."""
        period_lengths = {
            "nba": 720,    # 12 minutes
            "nfl": 900,    # 15 minutes  
            "nhl": 1200,   # 20 minutes
            "mlb": 0,      # No clock
            "ncaab": 1200, # 20 minutes
            "ncaaf": 900,  # 15 minutes
        }
        return period_lengths.get(sport.lower(), 720)

    def _get_total_periods(self, sport: str) -> int:
        """Get total number of periods for the given sport."""
        total_periods = {
            "nba": 4,
            "nfl": 4,
            "nhl": 3,
            "mlb": 9,
            "ncaab": 2,
            "ncaaf": 4,
        }
        return total_periods.get(sport.lower(), 4)
    
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

    def _is_game_live_by_kalshi(self, game: TrackedGame) -> bool:
        """
        Determine if a game is LIVE using Kalshi market data.
        
        Uses market game_start_time to infer if game is in progress.
        Kalshi API doesn't have explicit 'in-play' status, but markets
        are open during live games.
        
        Logic:
        - If game_start_time is set and current_time > game_start_time, game is likely live
        - If market status is 'open' and past start time, assume game is in progress
        - Returns False if we can't determine (prefer ESPN status in that case)
        
        Args:
            game: Tracked game to check
            
        Returns:
            True if game appears to be live based on Kalshi data
        """
        try:
            # First check if we have game_start_time from market
            game_start = game.market.game_start_time
            if game_start is None:
                # Try to parse from ticker: KXNBAGAME-26FEB07GSWLAL-LAL
                game_start = self._parse_game_start_from_ticker(game.market.ticker)
            
            if game_start is None:
                return False  # Can't determine, fall back to ESPN
            
            now = datetime.now(timezone.utc)
            
            # Game is considered "live" if it has started
            # Add 15 min buffer before official start to catch tip-off preparation
            if now >= game_start - timedelta(minutes=5):
                # NBA games typically last ~2.5 hours, NFL ~3.5 hours
                # If we're past start time but not too far, game is likely in progress
                hours_since_start = (now - game_start).total_seconds() / 3600
                
                # Sport-specific game duration estimates
                max_duration_hours = {
                    'nba': 3.0,
                    'nfl': 4.0,
                    'mlb': 4.0,
                    'nhl': 3.0,
                }.get(game.sport.lower(), 3.0)
                
                # If we're past start but within expected duration, game is live
                if hours_since_start < max_duration_hours:
                    logger.debug(
                        f"Kalshi live detection: {game.home_team} vs {game.away_team} "
                        f"started {hours_since_start:.1f}h ago (max {max_duration_hours}h)"
                    )
                    return True
                else:
                    # Game likely over
                    return False
            
            return False  # Game hasn't started yet
            
        except Exception as e:
            logger.debug(f"Error in Kalshi live detection: {e}")
            return False

    def _parse_game_start_from_ticker(self, ticker: str | None) -> datetime | None:
        """
        Parse game start time from Kalshi ticker format.
        
        Ticker format: KXNBAGAME-26FEB07GSWLAL-LAL
        Date portion: 26FEB07 = Feb 7, 2026
        
        Returns approximate start time (7PM local on game day).
        """
        if not ticker:
            return None
            
        try:
            import re
            # Match patterns like 26FEB07, 25JAN15, etc.
            match = re.search(r'(\d{2})(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)(\d{2})', ticker.upper())
            if not match:
                return None
            
            year = int(match.group(1)) + 2000  # 26 -> 2026
            month_str = match.group(2)
            day = int(match.group(3))
            
            month_map = {
                'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4,
                'MAY': 5, 'JUN': 6, 'JUL': 7, 'AUG': 8,
                'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12
            }
            month = month_map.get(month_str, 1)
            
            # Default to 7PM EST / 12:00 UTC as typical NBA game start
            # This is approximate but good enough for live detection
            game_date = datetime(year, month, day, 0, 0, 0, tzinfo=timezone.utc)
            
            return game_date
            
        except Exception as e:
            logger.debug(f"Failed to parse game start from ticker {ticker}: {e}")
            return None

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
        import string
        home_lower = home_team.lower()
        away_lower = away_team.lower()
        
        # Helper to clean text
        def clean_text(text):
            return text.translate(str.maketrans(string.punctuation, ' ' * len(string.punctuation)))

        for market in markets:
            if market.sport != sport:
                continue
            if getattr(market, "is_parlay", False):
                continue
            
            question_lower = market.question.lower()
            
            # Use set matching on cleaned words
            
            # Check if both teams appear in market question (strict phrase match)
            # We check parts of the name (e.g. "Pistons" in "Detroit Pistons")
            # But "Detroit Pistons" might not be in "Detroit vs Denver"
            
            # Use set matching on cleaned words
            home_words = set(clean_text(home_lower).split())
            away_words = set(clean_text(away_lower).split())
            question_words = set(clean_text(question_lower).split())
            
            # We need at least one significant word from home team and one from away team
            # Filter out common stop words if necessary, but team names usually distinctive
            
            home_match = len(home_words & question_words) >= 1
            away_match = len(away_words & question_words) >= 1
            
            if home_match and away_match:
                return market
            
            # Fallback: Check checking against home_team/away_team fields in DiscoveredMarket
            # (which we populated in market_discovery via extraction)
            if market.home_team and market.away_team:
                m_home = market.home_team.lower()
                m_away = market.away_team.lower()
                
                # Check for cross-match
                h_match = (m_home in home_lower or home_lower in m_home)
                a_match = (m_away in away_lower or away_lower in m_away)
                
                if h_match and a_match:
                    return market
                    
                # Check swapped
                h_swap = (m_home in away_lower or away_lower in m_home)
                a_swap = (m_away in home_lower or home_lower in m_away)
                
                if h_swap and a_swap:
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

        # Prevent duplicate tracking: check if this market's token is already
        # tracked under a different key (e.g. recovered position using
        # condition_id as key, now being discovered with real ESPN event_id).
        existing_key = self.token_to_game.get(market.token_id_yes)
        if existing_key and existing_key != event_id and existing_key in self.tracked_games:
            old_game = self.tracked_games[existing_key]
            logger.info(
                f"Upgrading tracked game key from {existing_key} to {event_id} "
                f"for {home_team} vs {away_team}"
            )
            # Migrate the existing entry to the new (real) event_id,
            # preserving position state
            old_game.espn_event_id = event_id
            self.tracked_games[event_id] = old_game
            del self.tracked_games[existing_key]
            self.game_tracker.remove_game(existing_key)
            self.game_tracker.add_game(old_game)
            self.token_to_game[market.token_id_yes] = event_id
            return  # Already tracking - just upgraded the key

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

        if event_id not in self.tracked_games:
            self.tracked_games[event_id] = tracked
            self.game_tracker.add_game(tracked)
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
        Only removes from tracking if exit was successful or no position exists.
        """
        # Close any open position
        if game.has_position and game.position_id:
            try:
                await self._evaluate_exit(db, game)
            except Exception as e:
                logger.error(
                    f"Failed to exit position for finished game "
                    f"{game.home_team} vs {game.away_team}: {e}"
                )
                await discord_notifier.notify_error(
                    "Game Finished Exit Failed",
                    f"{game.home_team} vs {game.away_team}: {e}",
                    "game_finished_exit"
                )

            # Verify position was actually closed before removing from tracking
            if game.has_position and game.position_id:
                # Re-check from database in case _evaluate_exit updated it
                try:
                    position = await PositionCRUD.get_by_id(db, game.position_id)
                    if position and position.status == "open":
                        logger.warning(
                            f"Position {game.position_id} still open after game finished. "
                            f"Keeping in tracking for retry on next cycle."
                        )
                        return  # Don't remove - will retry on next cleanup cycle
                except Exception as check_err:
                    logger.error(f"Could not verify position status: {check_err}")
                    return  # Don't remove if we can't verify

        # Position is closed (or never existed) - safe to remove from tracking
        if game.espn_event_id in self.tracked_games:
            del self.tracked_games[game.espn_event_id]
            self.game_tracker.remove_game(game.espn_event_id)

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
            "paper_trading": False,
            "emergency_stop": self.emergency_stop,
            "tracked_games": len(self.tracked_games),
            "enabled_sports": self.enabled_sports,
            "websocket_status": ws_status,
            "trades_today": self.trades_today,
            "daily_pnl": self.daily_pnl,
            "max_daily_loss": self.max_daily_loss,
            "max_slippage": self.max_slippage,
            "pending_orders": len(self.pending_orders),
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
    trading_client: KalshiClient,
    trading_engine: TradingEngine,
    espn_service: ESPNService
) -> BotRunner:
    """
    Get or create bot runner instance for a user.
    
    Args:
        user_id: User ID
        trading_client: Configured trading client (Polymarket or Kalshi)
        trading_engine: Trading engine instance
        espn_service: ESPN service instance
    
    Returns:
        BotRunner instance
    """
    if user_id not in _bot_instances:
        _bot_instances[user_id] = BotRunner(
            trading_client=trading_client,
            trading_engine=trading_engine,
            espn_service=espn_service
        )
    
    return _bot_instances[user_id]


def remove_bot_runner(user_id: UUID) -> None:
    """
    Remove bot runner instance for a user, freeing memory.
    Should be called after bot is stopped.

    Args:
        user_id: User ID
    """
    if user_id in _bot_instances:
        del _bot_instances[user_id]
        logger.info(f"Removed bot instance for user {user_id}")


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

