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
    position_id: int | None = None


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
        
        self.state = BotState.STOPPED
        self.websocket: PolymarketWebSocket | None = None
        
        # Tracked games keyed by ESPN event ID
        self.tracked_games: dict[str, TrackedGame] = {}
        
        # Token ID to game mapping for WebSocket updates
        self.token_to_game: dict[str, str] = {}
        
        # Configuration
        self.user_id: int | None = None
        self.enabled_sports: list[str] = []
        self.risk_per_trade: float = 0.02
        self.max_daily_loss: float = 100.0
        self.entry_threshold: float = 0.05
        self.take_profit: float = 0.15
        self.stop_loss: float = 0.10
        
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
        user_id: int
    ) -> None:
        """
        Initialize bot with user configuration.
        
        Args:
            db: Database session
            user_id: User to run bot for
        """
        self.user_id = user_id
        
        # Load global settings
        settings = await GlobalSettingsCRUD.get_by_user_id(db, user_id)
        if settings:
            self.max_daily_loss = float(settings.daily_loss_limit or 100)
            self.risk_per_trade = float(settings.default_position_size or 10) / 1000
        
        # Load sport configs
        configs = await SportConfigCRUD.get_by_user_id(db, user_id)
        for config in configs:
            if config.is_enabled:
                self.enabled_sports.append(config.sport_type.lower())
                # Use config thresholds
                if config.entry_threshold_pct:
                    self.entry_threshold = config.entry_threshold_pct / 100
                if config.take_profit_pct:
                    self.take_profit = config.take_profit_pct / 100
                if config.stop_loss_pct:
                    self.stop_loss = config.stop_loss_pct / 100
        
        # Default to NBA if no sports configured
        if not self.enabled_sports:
            self.enabled_sports = ["nba"]
        
        # Initialize WebSocket
        self.websocket = PolymarketWebSocket()
        
        logger.info(
            f"Bot initialized for user {user_id}. "
            f"Sports: {self.enabled_sports}, "
            f"Entry threshold: {self.entry_threshold:.1%}, "
            f"TP: {self.take_profit:.1%}, SL: {self.stop_loss:.1%}"
        )
    
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
        
        Runs every DISCOVERY_INTERVAL seconds.
        """
        while not self._stop_event.is_set():
            try:
                logger.debug("Running market discovery...")
                
                markets = await market_discovery.discover_sports_markets(
                    sports=self.enabled_sports,
                    min_liquidity=2000,
                    max_spread=0.08,
                    hours_ahead=24,
                    include_live=True
                )
                
                logger.info(f"Discovered {len(markets)} sports markets")
                
                # Match markets to ESPN games
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
                            await self._start_tracking_game(
                                db, event_id, sport, home_name, away_name, 
                                matched_market, game
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
        self.websocket.on_price_update(self._handle_price_update)
        
        while not self._stop_event.is_set():
            try:
                await self.websocket.connect()
                
                # Subscribe to tracked markets
                token_ids = list(self.token_to_game.keys())
                if token_ids:
                    await self.websocket.subscribe_markets(token_ids)
                
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
        - Game is in first quarter/period
        - Price has dropped from baseline by threshold
        - Sufficient time remaining
        """
        # Only trade in early periods
        if game.period > 1:
            return
        
        # Check price drop from baseline
        price_drop = (game.baseline_price - game.current_price) / game.baseline_price
        
        if price_drop < self.entry_threshold:
            return  # Not enough drop
        
        logger.info(
            f"Entry signal: {game.home_team} price dropped {price_drop:.1%} "
            f"from ${game.baseline_price:.4f} to ${game.current_price:.4f}"
        )
        
        # Calculate position size
        balance = await self.polymarket_client.get_balance()
        position_size = min(float(balance) * self.risk_per_trade, 50)  # Cap at $50
        
        if position_size < 1:
            logger.warning("Insufficient balance for trade")
            return
        
        # Execute entry
        try:
            order = await self.polymarket_client.place_order(
                token_id=game.market.token_id_yes,
                side="BUY",
                price=game.current_price,
                size=position_size,
                order_type="GTC"
            )
            
            if order:
                # Record position using CRUD interface
                entry_cost = position_size * game.current_price
                position = await PositionCRUD.create(
                    db,
                    user_id=self.user_id,
                    condition_id=game.market.condition_id,
                    token_id=game.market.token_id_yes,
                    side="YES",
                    entry_price=Decimal(str(game.current_price)),
                    entry_size=Decimal(str(position_size)),
                    entry_cost_usdc=Decimal(str(entry_cost)),
                    entry_reason=f"Price drop from baseline",
                    entry_order_id=order.get("id")
                )
                
                game.has_position = True
                game.position_id = position.id
                self.trades_today += 1
                
                await discord_notifier.notify_trade_entry(
                    market_name=game.market.question[:100],
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
        - Take profit reached
        - Stop loss reached
        - Game finished
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
        pnl_pct = (current_price - entry_price) / entry_price
        
        exit_reason = None
        
        if pnl_pct >= self.take_profit:
            exit_reason = "take_profit"
        elif pnl_pct <= -self.stop_loss:
            exit_reason = "stop_loss"
        elif game.game_status == "post":
            exit_reason = "game_finished"
        
        if not exit_reason:
            return
        
        logger.info(
            f"Exit signal ({exit_reason}): {game.home_team} "
            f"P&L: {pnl_pct:.1%}"
        )
        
        # Execute exit
        try:
            exit_size = float(position.entry_size)
            order = await self.polymarket_client.place_order(
                token_id=game.market.token_id_yes,
                side="SELL",
                price=current_price,
                size=exit_size,
                order_type="GTC"
            )
            
            if order:
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
                    exit_order_id=order.get("id")
                )
                
                game.has_position = False
                game.position_id = None
                self.daily_pnl += pnl
                
                await discord_notifier.notify_trade_exit(
                    market_name=game.market.question[:100],
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
        game_data: dict
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
            current_price=baseline
        )
        
        self.tracked_games[event_id] = tracked
        self.token_to_game[market.token_id_yes] = event_id
        
        # Subscribe to WebSocket updates
        if self.websocket and self.websocket.is_connected:
            await self.websocket.subscribe_markets([market.token_id_yes])
        
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
            await self.websocket.unsubscribe_markets([game.market.token_id_yes])
        
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
        Get current bot status.
        
        Returns:
            Status dictionary with state and stats
        """
        ws_status = "connected" if self.websocket and self.websocket.is_connected else "disconnected"
        
        runtime = None
        if self.start_time:
            runtime = str(datetime.now(timezone.utc) - self.start_time)
        
        return {
            "state": self.state.value,
            "runtime": runtime,
            "tracked_games": len(self.tracked_games),
            "enabled_sports": self.enabled_sports,
            "websocket_status": ws_status,
            "trades_today": self.trades_today,
            "daily_pnl": self.daily_pnl,
            "max_daily_loss": self.max_daily_loss,
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
                    "has_position": g.has_position
                }
                for g in self.tracked_games.values()
            ]
        }


# Singleton instance - initialized per user session
_bot_instances: dict[int, BotRunner] = {}


async def get_bot_runner(
    user_id: int,
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


def get_bot_status(user_id: int) -> dict | None:
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

