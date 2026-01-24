"""
Trading engine for evaluating entry/exit conditions and executing trades.
Core logic for automated trading decisions.
"""

import logging
from decimal import Decimal
from typing import Any
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.sport_config import SportConfig
from src.models.tracked_market import TrackedMarket
from src.models.global_settings import GlobalSettings
from src.db.crud.position import PositionCRUD
from src.db.crud.tracked_market import TrackedMarketCRUD
from src.db.crud.activity_log import ActivityLogCRUD
from src.services.polymarket_client import PolymarketClient


logger = logging.getLogger(__name__)


class TradingEngine:
    """
    Evaluates trading conditions and executes trades based on
    configured thresholds and current market state.
    """
    
    def __init__(
        self,
        db: AsyncSession,
        user_id: str,
        polymarket_client: PolymarketClient,
        global_settings: GlobalSettings,
        sport_configs: dict[str, SportConfig]
    ):
        """
        Initializes the trading engine.
        
        Args:
            db: Database session
            user_id: User identifier
            polymarket_client: Initialized Polymarket client
            global_settings: User's global settings
            sport_configs: Dictionary of sport -> config mappings
        """
        self.db = db
        self.user_id = user_id
        self.client = polymarket_client
        self.settings = global_settings
        self.sport_configs = sport_configs
    
    async def evaluate_entry(
        self,
        market: TrackedMarket,
        game_state: dict[str, Any]
    ) -> dict[str, Any] | None:
        """
        Evaluates whether entry conditions are met for a market.
        
        Args:
            market: Tracked market to evaluate
            game_state: Current game state from ESPN
        
        Returns:
            Entry signal dictionary if conditions met, None otherwise
        """
        config = self.sport_configs.get(market.sport)
        if not config or not config.is_enabled:
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
            self.db, self.user_id, market.condition_id
        )
        if open_positions >= config.max_positions_per_game:
            return None
        
        daily_pnl = await PositionCRUD.get_daily_pnl(self.db, self.user_id)
        if daily_pnl < -self.settings.max_daily_loss_usdc:
            return None
        
        current_exposure = await PositionCRUD.get_open_exposure(self.db, self.user_id)
        if current_exposure >= self.settings.max_portfolio_exposure_usdc:
            return None
        
        entry_signal = self._check_price_conditions(market, config)
        
        return entry_signal
    
    def _check_price_conditions(
        self,
        market: TrackedMarket,
        config: SportConfig
    ) -> dict[str, Any] | None:
        """
        Checks if price conditions warrant an entry.
        
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
        
        yes_drop = (baseline_yes - current_yes) / baseline_yes if baseline_yes > 0 else Decimal("0")
        no_drop = (baseline_no - current_no) / baseline_no if baseline_no > 0 else Decimal("0")
        
        threshold = config.entry_threshold_pct
        absolute = config.absolute_entry_price
        
        if yes_drop >= threshold or current_yes <= absolute:
            return {
                "side": "YES",
                "token_id": market.token_id_yes,
                "price": float(current_yes),
                "reason": f"YES price drop: {float(yes_drop)*100:.1f}% (threshold: {float(threshold)*100:.1f}%)",
                "position_size": float(config.default_position_size_usdc),
            }
        
        if no_drop >= threshold or current_no <= absolute:
            return {
                "side": "NO",
                "token_id": market.token_id_no,
                "price": float(current_no),
                "reason": f"NO price drop: {float(no_drop)*100:.1f}% (threshold: {float(threshold)*100:.1f}%)",
                "position_size": float(config.default_position_size_usdc),
            }
        
        return None
    
    async def evaluate_exit(
        self,
        position: Any,
        market: TrackedMarket,
        game_state: dict[str, Any]
    ) -> dict[str, Any] | None:
        """
        Evaluates whether exit conditions are met for a position.
        
        Args:
            position: Position to evaluate
            market: Associated tracked market
            game_state: Current game state from ESPN
        
        Returns:
            Exit signal dictionary if conditions met, None otherwise
        """
        config = self.sport_configs.get(market.sport)
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
        
        try:
            result = await self.client.place_order(
                token_id=token_id,
                side="BUY",
                price=price,
                size=size
            )
            
            position = await PositionCRUD.create(
                self.db,
                user_id=self.user_id,
                condition_id=market.condition_id,
                token_id=token_id,
                side=side,
                entry_price=Decimal(str(price)),
                entry_size=Decimal(str(size)),
                entry_cost_usdc=Decimal(str(position_size)),
                entry_reason=entry_signal["reason"],
                entry_order_id=result.get("id"),
                tracked_market_id=market.id,
                team=market.home_team if side == "YES" else market.away_team
            )
            
            await ActivityLogCRUD.info(
                self.db,
                self.user_id,
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
                self.user_id,
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
                exit_price = await self.client.get_midpoint_price(position.token_id)
            
            result = await self.client.place_order(
                token_id=position.token_id,
                side="SELL",
                price=exit_price,
                size=float(position.entry_size)
            )
            
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
            
            await ActivityLogCRUD.info(
                self.db,
                self.user_id,
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
                self.user_id,
                "TRADE",
                f"Exit failed: {str(e)}",
                details={"position_id": str(position.id)}
            )
            
            return {
                "success": False,
                "error": str(e),
            }
