"""
Trading engine for evaluating entry/exit conditions and executing trades.
Core logic for automated trading decisions.
"""

import logging
from decimal import Decimal
from typing import Any, Optional, Union
from datetime import datetime
from uuid import UUID

from src.services.types import TradeSignal

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.sport_config import SportConfig
from src.models.market_config import MarketConfig
from src.models.tracked_market import TrackedMarket
from src.models.global_settings import GlobalSettings
from src.db.crud.position import PositionCRUD
from src.db.crud.tracked_market import TrackedMarketCRUD
from src.db.crud.activity_log import ActivityLogCRUD
from src.db.crud.market_config import MarketConfigCRUD

from src.services.kalshi_client import KalshiClient
from src.services.confidence_scorer import ConfidenceScorer, ConfidenceResult
from src.services.kelly_calculator import KellyCalculator, KellyResult
from src.services.balance_guardian import BalanceGuardian


logger = logging.getLogger(__name__)


class EffectiveConfig:
    """
    Holds effective trading configuration for a market.
    Combines market-specific overrides with sport defaults.
    """
    
    def __init__(
        self,
        sport_config: SportConfig,
        market_config: MarketConfig | None = None,
        overrides: dict[str, Any] | None = None
    ):
        self.sport_config = sport_config
        self.market_config = market_config
        self.overrides = overrides or {}
    
    @property
    def is_enabled(self) -> bool:
        """Check if trading is enabled for this market."""
        if self.market_config and not self.market_config.enabled:
            return False
        return self.sport_config.is_enabled
    
    @property
    def auto_trade(self) -> bool:
        """Check if auto-trading is enabled for this market."""
        if self.market_config:
            return self.market_config.auto_trade
        return True
    
    @property
    def entry_threshold_pct(self) -> Decimal:
        """Get entry threshold percentage (market override or sport default)."""
        if self.overrides.get("entry_threshold_drop") is not None:
             return Decimal(str(self.overrides["entry_threshold_drop"]))
        if self.market_config and self.market_config.entry_threshold_drop is not None:
            return self.market_config.entry_threshold_drop
        return self.sport_config.entry_threshold_pct
    
    @property
    def absolute_entry_price(self) -> Decimal:
        """Get absolute entry price threshold."""
        if self.market_config and self.market_config.entry_threshold_absolute is not None:
            return self.market_config.entry_threshold_absolute
        return self.sport_config.absolute_entry_price
    
    @property
    def min_time_remaining_seconds(self) -> int:
        """Get minimum time remaining requirement."""
        if self.market_config and self.market_config.min_time_remaining_seconds is not None:
            return self.market_config.min_time_remaining_seconds
        return self.sport_config.min_time_remaining_seconds
    
    @property
    def take_profit_pct(self) -> Decimal:
        """Get take profit percentage."""
        if self.overrides.get("take_profit_pct") is not None:
             return Decimal(str(self.overrides["take_profit_pct"]))
        if self.market_config and self.market_config.take_profit_pct is not None:
            return self.market_config.take_profit_pct
        return self.sport_config.take_profit_pct
    
    @property
    def stop_loss_pct(self) -> Decimal:
        """Get stop loss percentage."""
        if self.overrides.get("stop_loss_pct") is not None:
             return Decimal(str(self.overrides["stop_loss_pct"]))
        if self.market_config and self.market_config.stop_loss_pct is not None:
            return self.market_config.stop_loss_pct
        return self.sport_config.stop_loss_pct
    
    @property
    def default_position_size_usdc(self) -> Decimal:
        """Get position size in USDC."""
        if self.overrides.get("position_size_usdc") is not None:
            return Decimal(str(self.overrides["position_size_usdc"]))
        if self.market_config and self.market_config.position_size_usdc is not None:
            return self.market_config.position_size_usdc
        return self.sport_config.default_position_size_usdc
    
    @property
    def max_positions_per_game(self) -> int:
        """Get max positions allowed for this market."""
        if self.market_config and self.market_config.max_positions is not None:
            return self.market_config.max_positions
        return self.sport_config.max_positions_per_game
    
    @property
    def allowed_entry_segments(self) -> list[str]:
        """Get allowed entry segments from sport config."""
        return self.sport_config.allowed_entry_segments
    
    @property
    def use_kelly_sizing(self) -> bool:
        """Check if Kelly criterion sizing is enabled."""
        return getattr(self.sport_config, 'use_kelly_sizing', False)
    
    @property
    def kelly_fraction(self) -> float:
        """Get Kelly fraction for position sizing."""
        return float(getattr(self.sport_config, 'kelly_fraction', Decimal('0.25')))
    
    @property
    def min_entry_confidence_score(self) -> float:
        """Get minimum confidence score required for entry."""
        return float(getattr(self.sport_config, 'min_entry_confidence_score', Decimal('0.6')))


class TradingEngine:
    """
    Evaluates trading conditions and executes trades based on
    configured thresholds and current market state.
    
    Supports per-market configuration overrides that take precedence
    over sport-level defaults.
    
    Integrates:
    - Confidence scoring for entry signal quality
    - Kelly criterion for optimal position sizing
    - Balance guardian for risk management
    """
    
    def __init__(
        self,
        db: AsyncSession,
        user_id: str,
        trading_client: KalshiClient,
        global_settings: GlobalSettings,
        sport_configs: dict[str, SportConfig],
        market_configs: dict[str, MarketConfig] | None = None,
        balance_guardian: Optional[BalanceGuardian] = None,
    ):
        """
        Initializes the trading engine.
        
        Args:
            db: Database session
            user_id: User identifier (string or UUID)
            trading_client: Initialized Kalshi client
            global_settings: User's global settings
            sport_configs: Dictionary of sport -> config mappings
            market_configs: Dictionary of condition_id -> market config overrides
            balance_guardian: Optional balance guardian for risk checks
        """
        self.db = db
        self.user_id = user_id
        self.client = trading_client
        self.settings = global_settings
        self.sport_configs = sport_configs
        self.market_configs = market_configs or {}
        self.balance_guardian = balance_guardian
        
        self.confidence_scorer = ConfidenceScorer()
        self.kelly_calculator = KellyCalculator()
    
    @property
    def _user_id_uuid(self) -> UUID:
        """Convert user_id string to UUID for database operations."""
        if isinstance(self.user_id, str):
            return UUID(self.user_id)
        return self.user_id
    
    async def _place_order(self, token_id: str, side: str, price: float, size: float, yes_no: str = "yes") -> Any:
        """
        Place order on Kalshi.
        
        Note: Kalshi API uses cents (1-100) for price, while Polymarket uses 0-1 range.
        This method converts inputs to Kalshi format.
        """
        # Kalshi API: place_order(ticker, side, yes_no, price, size)
        # Kalshi price is in cents, so we convert from 0-1 range to cents
        return await self.client.place_order(
            ticker=token_id,
            side=side,
            yes_no=yes_no.lower(),
            price=price,  # Client expects 0-1, will convert to cents internally
            size=int(size)
        )
    
    async def _get_exit_price(self, token_id: str) -> float:
        """
        Get current price for exit from Kalshi.

        Tries live API first, then falls back to last known price from
        the sport_configs/tracked market data. Returns None-safe fallback
        only as a last resort.
        """
        # For Kalshi, try to get market data from API
        try:
            data = await self.client.get_market(token_id)
            market = data.get("market", data)

            # Try yes_ask first (more accurate for selling), then yes_price
            price_raw = market.get("yes_ask") or market.get("yes_price")
            if price_raw is not None:
                # Normalize to 0-1 range
                # If > 1, assume cents (e.g. 45 -> 0.45)
                # If <= 1, assume dollars (e.g. 0.45 -> 0.45)
                if float(price_raw) > 1:
                    return float(price_raw) / 100.0
                return float(price_raw)
        except Exception as e:
            logger.warning(f"Failed to get exit price for {token_id} from API: {e}")

        # Fallback: check tracked market data in database
        try:
            from src.db.crud.tracked_market import TrackedMarketCRUD
            tracked = await TrackedMarketCRUD.get_by_condition_id(
                self.db, self._user_id_uuid, token_id
            )
            if tracked and tracked.current_price_yes is not None:
                return float(tracked.current_price_yes)
        except Exception as e:
            logger.debug(f"Could not get tracked market price for {token_id}: {e}")

        # Last resort fallback - log as error since we have no real price data
        logger.error(
            f"No price data available for {token_id}, using 0.5 fallback. "
            f"This may result in inaccurate P&L calculations."
        )
        return 0.5
    
    def _get_effective_config(self, market: TrackedMarket, overrides: dict[str, Any] | None = None) -> EffectiveConfig | None:
        """
        Gets effective configuration for a market.
        Combines sport config with any market-specific overrides.
        
        Args:
            market: The tracked market to get config for
            overrides: Optional runtime overrides
        
        Returns:
            EffectiveConfig combining sport and market configs, or None if no sport config
        """
        sport_config = self.sport_configs.get(market.sport)
        if not sport_config:
            return None
        
        market_config = self.market_configs.get(market.condition_id)
        return EffectiveConfig(sport_config, market_config, overrides)
    
    async def evaluate_entry(
        self,
        market: TrackedMarket,
        game_state: dict[str, Any],
        overrides: dict[str, Any] | None = None
    ) -> dict[str, Any] | None:
        """
        Evaluates whether entry conditions are met for a market.
        Uses market-specific config if available, otherwise sport defaults.
        
        Includes confidence scoring and optional Kelly sizing.
        
        Args:
            market: Tracked market to evaluate
            game_state: Current game state from ESPN
        
        Returns:
            Entry signal dictionary if conditions met, None otherwise
        """
        config = self._get_effective_config(market, overrides)
        if not config or not config.is_enabled:
            return None
        
        # Check if auto-trading is enabled for this market
        if not config.auto_trade:
            logger.debug(f"Auto-trade disabled for market {market.condition_id}")
            return None
        
        # Check balance guardian kill switch
        if self.balance_guardian:
            status = await self.balance_guardian.get_status()
            if status.get("kill_switch", {}).get("triggered"):
                logger.warning("Kill switch active - blocking entry")
                return None
        
        if not game_state.get("is_live"):
            return None
        
        segment = game_state.get("segment", "")
        if segment not in config.allowed_entry_segments:
            return None
        
        time_remaining = game_state.get("time_remaining_seconds", 0)
        if time_remaining < config.min_time_remaining_seconds:
            return None
        
        open_positions = await PositionCRUD.count_open_for_market(
            self.db, self._user_id_uuid, market.condition_id
        )
        if open_positions >= config.max_positions_per_game:
            return None
        
        daily_pnl = await PositionCRUD.get_daily_pnl(self.db, self._user_id_uuid)
        if daily_pnl < -self.settings.max_daily_loss_usdc:
            return None
        
        current_exposure = await PositionCRUD.get_open_exposure(self.db, self._user_id_uuid)
        if current_exposure >= self.settings.max_portfolio_exposure_usdc:
            return None
        
        entry_signal = self._check_price_conditions(market, config)
        
        if entry_signal:
            # CHECK: Single position per team limit
            # This ensures "one bet per team" as requested by user.
            target_team_name = entry_signal.get("team")
            if target_team_name:
                open_team_count = await PositionCRUD.count_open_for_team(
                    self.db, self._user_id_uuid, target_team_name
                )
                if open_team_count > 0:
                    logger.debug(f"Entry blocked: Already have an open position for team {target_team_name}")
                    return None

            # Calculate confidence score
            confidence_result = self._calculate_confidence(
                market, game_state, config
            )
            
            if confidence_result.overall_score < config.min_entry_confidence_score:
                logger.info(
                    f"Confidence score {confidence_result.overall_score:.2f} below "
                    f"threshold {config.min_entry_confidence_score:.2f}"
                )
                return None
            
            entry_signal["confidence_score"] = confidence_result.overall_score
            entry_signal["confidence_breakdown"] = confidence_result.breakdown
            entry_signal["confidence_recommendation"] = confidence_result.recommendation
            
            # Calculate position size with Kelly if enabled
            position_size = await self._calculate_position_size(
                config, confidence_result, market
            )
            entry_signal["position_size"] = position_size
            
            # Apply streak reduction if applicable
            if self.balance_guardian:
                multiplier = await self.balance_guardian.calculate_streak_adjustment()
                if multiplier < 1.0:
                    entry_signal["position_size"] *= multiplier
                    entry_signal["streak_adjustment"] = multiplier
        
        return entry_signal
    
    def _check_price_conditions(
        self,
        market: TrackedMarket,
        config: EffectiveConfig
    ) -> dict[str, Any] | None:
        """
        Checks if price conditions warrant an entry.
        Uses effective config which may include market-specific overrides.
        
        Returns entry signal if either:
        1. Price dropped from baseline by threshold percentage
        2. Price is below absolute entry threshold
        """
        if not market.baseline_price_yes or not market.current_price_yes:
            return None
        
        baseline_yes = market.baseline_price_yes
        current_yes = market.current_price_yes
        baseline_no = market.baseline_price_no or (Decimal("1") - baseline_yes)
        current_no = market.current_price_no or (Decimal("1") - current_yes)

        # New: Check Pregame Probability Threshold
        # ----------------------------------------
        # Check overrides first (passed from bot runner)
        min_pregame_prob = config.overrides.get("min_pregame_probability") if hasattr(config, "overrides") and config.overrides else None
        
        # If not in overrides, check config attribute
        if min_pregame_prob is None:
             min_pregame_prob = getattr(config, "min_pregame_probability", None)
             
        if min_pregame_prob and min_pregame_prob > 0:
            # Baseline price is 0-1 (Decimal), threshold is 0-100 (float)
            # Use baseline_yes for Home team concept (usually YES side)
            baseline_pct = float(baseline_yes) * 100
            if baseline_pct < min_pregame_prob:
                # logger.debug(f"Entry set aside: Baseline {baseline_pct:.1f}% < Min Pregame {min_pregame_prob}%")
                return None
        
        yes_drop = (baseline_yes - current_yes) / baseline_yes if baseline_yes > 0 else Decimal("0")
        no_drop = (baseline_no - current_no) / baseline_no if baseline_no > 0 else Decimal("0")
        
        threshold = config.entry_threshold_pct
        absolute = config.absolute_entry_price
        
        if yes_drop >= threshold or current_yes <= absolute:
            # CHECK: Single position per team limit
            team_name = market.home_team
            if team_name:
                open_team_positions = 0
                # We need access to DB here, but _check_price_conditions is synchronous.
                # I'll move this check to evaluate_entry instead.
                pass

            return {
                "side": "YES",
                "token_id": market.token_id_yes,
                "price": float(current_yes),
                "reason": f"YES price drop: {float(yes_drop)*100:.1f}% (threshold: {float(threshold)*100:.1f}%)",
                "position_size": float(config.default_position_size_usdc),
                "team": market.home_team
            }
        
        if no_drop >= threshold or current_no <= absolute:
            return {
                "side": "NO",
                "token_id": market.token_id_no,
                "price": float(current_no),
                "reason": f"NO price drop: {float(no_drop)*100:.1f}% (threshold: {float(threshold)*100:.1f}%)",
                "position_size": float(config.default_position_size_usdc),
                "team": market.away_team
            }
        
        return None
    
    def _calculate_confidence(
        self,
        market: TrackedMarket,
        game_state: dict[str, Any],
        config: EffectiveConfig,
    ) -> ConfidenceResult:
        """
        Calculate multi-factor confidence score for entry.
        
        Args:
            market: Market being evaluated
            game_state: Current game state
            config: Effective configuration
        
        Returns:
            ConfidenceResult with overall score and factor breakdown
        """
        current_price = market.current_price_yes or Decimal("0.5")
        baseline_price = market.baseline_price_yes or Decimal("0.5")
        
        time_remaining = game_state.get("time_remaining_seconds", 0)
        total_period = game_state.get("total_period_seconds", 720)
        current_period = game_state.get("period", 1)
        total_periods = game_state.get("total_periods", 4)
        
        score_diff = game_state.get("score_diff")
        
        return self.confidence_scorer.calculate_confidence(
            current_price=current_price,
            baseline_price=baseline_price,
            time_remaining_seconds=time_remaining,
            total_period_seconds=total_period,
            orderbook=None,
            recent_prices=None,
            game_score_diff=score_diff,
            current_period=current_period,
            total_periods=total_periods,
        )
    
    async def _calculate_position_size(
        self,
        config: EffectiveConfig,
        confidence: ConfidenceResult,
        market: TrackedMarket,
    ) -> float:
        """
        Calculate optimal position size using Kelly criterion or default.
        
        Args:
            config: Effective configuration
            confidence: Confidence score result
            market: Market being traded
        
        Returns:
            Position size in USDC
        """
        default_size = float(config.default_position_size_usdc)
        
        if not config.use_kelly_sizing:
            return default_size
        
        try:
            balance = await self.client.get_balance()
            bankroll = Decimal(str(balance.get("balance", 1000) if isinstance(balance, dict) else balance or 1000))
            
            current_price = market.current_price_yes or Decimal("0.5")
            
            win_prob = 0.5 + (confidence.overall_score - 0.5) * 0.3
            
            trade_stats = await PositionCRUD.get_trade_stats(self.db, self._user_id_uuid)
            historical_win_rate = trade_stats.get("win_rate") if trade_stats else None
            sample_size = trade_stats.get("total_trades", 0) if trade_stats else 0
            
            self.kelly_calculator.kelly_fraction = config.kelly_fraction
            
            kelly_result = self.kelly_calculator.calculate(
                bankroll=bankroll,
                current_price=current_price,
                estimated_win_prob=win_prob,
                historical_win_rate=historical_win_rate,
                historical_sample_size=sample_size,
                max_position_size=Decimal(str(default_size * 2)),
            )
            
            if kelly_result.recommended_contracts > 0:
                kelly_size = kelly_result.adjusted_size
                return min(kelly_size, default_size * 2)
            
        except Exception as e:
            logger.warning(f"Kelly calculation failed, using default: {e}")
        
        return default_size
    
    async def evaluate_exit(
        self,
        position: Any,
        market: TrackedMarket,
        game_state: dict[str, Any],
        overrides: dict[str, Any] | None = None
    ) -> dict[str, Any] | None:
        """
        Evaluates whether exit conditions are met for a position.
        
        Args:
            position: The open position to evaluate
            market: Tracked market details
            game_state: Current game state
            overrides: Optional runtime overrides
        
        Returns:
            Exit signal dictionary if conditions met, None otherwise
        """
        config = self._get_effective_config(market, overrides)
        if not config:
            return None
        
        if game_state.get("is_finished"):
            return {
                "reason": "game_finished",
                "message": "Game has finished",
            }
        
        if position.side == "YES":
            current_price = market.current_price_yes
        else:
            current_price = market.current_price_no
        
        if not current_price:
            return None
        
        entry_price = position.entry_price
        pnl_pct = (current_price - entry_price) / entry_price if entry_price > 0 else Decimal("0")
        
        if pnl_pct >= config.take_profit_pct:
            return {
                "reason": "take_profit",
                "message": f"Take profit triggered: {float(pnl_pct)*100:.1f}% gain",
                "exit_price": float(current_price),
            }
        
        if pnl_pct <= -config.stop_loss_pct:
            return {
                "reason": "stop_loss",
                "message": f"Stop loss triggered: {float(abs(pnl_pct))*100:.1f}% loss",
                "exit_price": float(current_price),
            }
        
        segment = game_state.get("segment", "")
        if segment not in config.allowed_entry_segments:
            return {
                "reason": "restricted_segment",
                "message": f"Exiting before restricted segment: {segment}",
                "exit_price": float(current_price),
            }
        
        return None
    
    async def execute_entry(
        self,
        market: TrackedMarket,
        entry_signal: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Executes an entry trade based on the provided signal.
        
        Args:
            market: Market to enter
            entry_signal: Entry signal from evaluate_entry
        
        Returns:
            Execution result dictionary
        """
        token_id = entry_signal["token_id"]
        side = entry_signal["side"]
        price = entry_signal["price"]
        position_size = entry_signal["position_size"]
        
        size = position_size / price if price > 0 else 0
        
        confidence_score = entry_signal.get("confidence_score")
        confidence_breakdown = entry_signal.get("confidence_breakdown")
        
        try:
            order_result = await self._place_order(
                token_id=token_id,
                side="buy",
                price=price,
                size=size,
                yes_no=side.lower()
            )
            if isinstance(order_result, dict):
                order_data = order_result.get("order", order_result)
                result = {"id": order_data.get("order_id", str(order_result)), "status": "placed"}
            else:
                result = {"id": getattr(order_result, 'order_id', str(order_result)), "status": "placed"}

            position = await PositionCRUD.create(
                self.db,
                user_id=self._user_id_uuid,
                condition_id=market.condition_id,
                token_id=token_id,
                side=side,
                entry_price=Decimal(str(price)),
                entry_size=Decimal(str(size)),
                entry_cost_usdc=Decimal(str(position_size)),
                entry_reason=entry_signal["reason"],
                entry_order_id=result.get("id"),
                tracked_market_id=market.id,
                team=market.home_team if side == "YES" else market.away_team,
                requested_entry_price=Decimal(str(price)),
                entry_confidence_score=Decimal(str(confidence_score)) if confidence_score else None,
                entry_confidence_breakdown=confidence_breakdown,
            )

            await ActivityLogCRUD.info(
                self.db,
                self._user_id_uuid,
                "TRADE",
                f"Entered {side} position at {price:.4f}",
                details={
                    "position_id": str(position.id),
                    "token_id": token_id,
                    "size": size,
                    "reason": entry_signal["reason"],
                }
            )

            return {
                "success": True,
                "position_id": str(position.id),
                "order_id": result.get("id"),
            }
            
        except Exception as e:
            logger.error(f"Entry execution failed: {e}")
            
            await ActivityLogCRUD.error(
                self.db,
                self._user_id_uuid,
                "TRADE",
                f"Entry failed: {str(e)}",
                details={"token_id": token_id, "side": side}
            )
            
            return {
                "success": False,
                "error": str(e),
            }
    
    async def execute_exit(
        self,
        position: Any,
        exit_signal: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Executes an exit trade based on the provided signal.
        
        Args:
            position: Position to exit
            exit_signal: Exit signal from evaluate_exit
        
        Returns:
            Execution result dictionary
        """
        try:
            exit_price = exit_signal.get("exit_price")
            
            if not exit_price:
                exit_price = await self._get_exit_price(position.token_id)
            
            order_result = await self._place_order(
                token_id=position.token_id,
                side="sell",
                price=exit_price,
                size=float(position.entry_size),
                yes_no=position.side.lower()
            )
            if isinstance(order_result, dict):
                order_data = order_result.get("order", order_result)
                result = {"id": order_data.get("order_id", str(order_result)), "status": "placed"}
            else:
                result = {"id": getattr(order_result, 'order_id', str(order_result)), "status": "placed"}

            exit_proceeds = Decimal(str(exit_price)) * position.entry_size

            closed_position = await PositionCRUD.close_position(
                self.db,
                position.id,
                exit_price=Decimal(str(exit_price)),
                exit_size=position.entry_size,
                exit_proceeds_usdc=exit_proceeds,
                exit_reason=exit_signal["reason"],
                exit_order_id=result.get("id")
            )

            pnl = closed_position.realized_pnl_usdc

            # Record trade outcome for streak tracking
            if self.balance_guardian and pnl is not None:
                is_win = float(pnl) > 0
                await self.balance_guardian.record_trade_outcome(is_win)

            await ActivityLogCRUD.info(
                self.db,
                self._user_id_uuid,
                "TRADE",
                f"Closed position at {exit_price:.4f}, P&L: {pnl:.2f} USDC",
                details={
                    "position_id": str(position.id),
                    "reason": exit_signal["reason"],
                    "pnl_usdc": float(pnl) if pnl else 0,
                }
            )

            return {
                "success": True,
                "position_id": str(position.id),
                "order_id": result.get("id"),
                "pnl_usdc": float(pnl) if pnl else 0,
            }
            
        except Exception as e:
            logger.error(f"Exit execution failed: {e}")
            
            await ActivityLogCRUD.error(
                self.db,
                self._user_id_uuid,
                "TRADE",
                f"Exit failed: {str(e)}",
                details={"position_id": str(position.id)}
            )
            
            return {
                "success": False,
                "error": str(e),
            }
