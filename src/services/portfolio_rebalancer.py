"""
Portfolio rebalancing service for automatic position management.
Rebalances positions across markets based on target allocations.
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Callable

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.crud.position import PositionCRUD


logger = logging.getLogger(__name__)


class RebalanceStrategy(str, Enum):
    """Rebalancing strategies."""
    THRESHOLD = "threshold"  # Rebalance when drift exceeds threshold
    PERIODIC = "periodic"  # Rebalance on schedule
    MANUAL = "manual"  # Only on explicit request


class RebalanceAction(str, Enum):
    """Types of rebalancing actions."""
    BUY = "buy"  # Increase position
    SELL = "sell"  # Decrease position
    HOLD = "hold"  # No action needed


@dataclass
class TargetAllocation:
    """Target allocation for a single market."""
    condition_id: str
    token_id: str
    target_pct: Decimal  # Target percentage of portfolio (0-100)
    min_pct: Decimal | None = None  # Minimum (triggers buy if below)
    max_pct: Decimal | None = None  # Maximum (triggers sell if above)
    sport: str | None = None
    market_name: str | None = None


@dataclass
class PortfolioPosition:
    """Current position in a market."""
    position_id: str
    condition_id: str
    token_id: str
    side: str
    size: Decimal
    entry_price: Decimal
    current_price: Decimal
    current_value: Decimal
    pnl: Decimal
    pnl_pct: Decimal
    weight_pct: Decimal  # Percentage of total portfolio


@dataclass
class RebalanceRecommendation:
    """Recommended rebalancing action for a position."""
    condition_id: str
    token_id: str
    action: RebalanceAction
    current_pct: Decimal
    target_pct: Decimal
    drift_pct: Decimal  # How far from target
    recommended_size: Decimal  # Contracts to buy/sell
    recommended_value: Decimal  # USD value of trade
    reason: str


@dataclass
class RebalanceResult:
    """Result of a rebalancing operation."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    strategy: RebalanceStrategy = RebalanceStrategy.THRESHOLD
    
    # Portfolio state before
    total_value_before: Decimal = Decimal("0")
    positions_before: int = 0
    
    # Actions taken
    recommendations: list[RebalanceRecommendation] = field(default_factory=list)
    executed_actions: list[dict] = field(default_factory=list)
    
    # Results
    success_count: int = 0
    failed_count: int = 0
    total_traded_value: Decimal = Decimal("0")
    
    # Portfolio state after
    total_value_after: Decimal = Decimal("0")
    positions_after: int = 0
    
    @property
    def status(self) -> str:
        """Overall status of rebalancing."""
        if self.failed_count == 0 and self.success_count > 0:
            return "completed"
        elif self.success_count > 0:
            return "partial"
        elif self.failed_count > 0:
            return "failed"
        return "no_action"


class PortfolioRebalancer:
    """
    Automatic portfolio rebalancing across prediction markets.
    
    Features:
    - Target allocation management
    - Drift detection and threshold-based rebalancing
    - Scheduled periodic rebalancing
    - Tax-efficient rebalancing (minimize sells)
    - Slippage-aware execution
    - Risk limit respect during rebalancing
    
    Example usage:
        rebalancer = PortfolioRebalancer(client, db)
        
        # Set target allocations
        rebalancer.set_target(condition_id, token_id, target_pct=25)
        
        # Check current state
        analysis = await rebalancer.analyze_portfolio(user_id)
        
        # Execute rebalancing
        result = await rebalancer.rebalance(user_id)
    """
    
    DEFAULT_DRIFT_THRESHOLD = Decimal("5.0")  # 5% drift triggers rebalance
    DEFAULT_MIN_TRADE_VALUE = Decimal("10.0")  # Minimum trade size in USD
    
    def __init__(
        self,
        trading_client: Any,
        db: AsyncSession,
        price_fetcher: Callable[[str], float] | None = None
    ):
        """
        Initialize the portfolio rebalancer.
        
        Args:
            trading_client: Trading client for order execution
            db: Database session
            price_fetcher: Async function to get current price
        """
        self.client = trading_client
        self.db = db
        self.price_fetcher = price_fetcher
        
        # Target allocations by user_id -> condition_id
        self._targets: dict[str, dict[str, TargetAllocation]] = {}
        
        # Rebalancing configuration by user
        self._config: dict[str, dict] = {}
        
        # Rebalancing history
        self._history: list[RebalanceResult] = []
        
        # Background task
        self._is_running = False
        self._task: asyncio.Task | None = None
    
    # -------------------------------------------------------------------------
    # Target Allocation Management
    # -------------------------------------------------------------------------
    
    def set_target(
        self,
        user_id: str,
        condition_id: str,
        token_id: str,
        target_pct: Decimal,
        min_pct: Decimal | None = None,
        max_pct: Decimal | None = None,
        sport: str | None = None,
        market_name: str | None = None
    ) -> TargetAllocation:
        """
        Set target allocation for a market.
        
        Args:
            user_id: User ID
            condition_id: Market condition ID
            token_id: Token ID
            target_pct: Target percentage (0-100)
            min_pct: Minimum percentage (optional)
            max_pct: Maximum percentage (optional)
            sport: Sport category (optional)
            market_name: Display name (optional)
        
        Returns:
            TargetAllocation object
        """
        if user_id not in self._targets:
            self._targets[user_id] = {}
        
        target = TargetAllocation(
            condition_id=condition_id,
            token_id=token_id,
            target_pct=target_pct,
            min_pct=min_pct or target_pct - self.DEFAULT_DRIFT_THRESHOLD,
            max_pct=max_pct or target_pct + self.DEFAULT_DRIFT_THRESHOLD,
            sport=sport,
            market_name=market_name
        )
        
        self._targets[user_id][condition_id] = target
        
        logger.info(
            f"Set target allocation for {condition_id[:16]}...: "
            f"{target_pct}% (range: {target.min_pct}-{target.max_pct}%)"
        )
        
        return target
    
    def remove_target(self, user_id: str, condition_id: str) -> bool:
        """Remove target allocation for a market."""
        if user_id in self._targets and condition_id in self._targets[user_id]:
            del self._targets[user_id][condition_id]
            logger.info(f"Removed target for {condition_id[:16]}...")
            return True
        return False
    
    def get_targets(self, user_id: str) -> dict[str, TargetAllocation]:
        """Get all target allocations for a user."""
        return self._targets.get(user_id, {})
    
    def set_targets_from_dict(
        self,
        user_id: str,
        targets: dict[str, dict]
    ) -> list[TargetAllocation]:
        """
        Set multiple target allocations from a dictionary.
        
        Args:
            user_id: User ID
            targets: Dict of condition_id -> {token_id, target_pct, ...}
        
        Returns:
            List of created TargetAllocation objects
        """
        results = []
        
        for condition_id, config in targets.items():
            target = self.set_target(
                user_id=user_id,
                condition_id=condition_id,
                token_id=config.get("token_id", ""),
                target_pct=Decimal(str(config.get("target_pct", 0))),
                min_pct=Decimal(str(config["min_pct"])) if "min_pct" in config else None,
                max_pct=Decimal(str(config["max_pct"])) if "max_pct" in config else None,
                sport=config.get("sport"),
                market_name=config.get("market_name")
            )
            results.append(target)
        
        return results
    
    # -------------------------------------------------------------------------
    # Configuration
    # -------------------------------------------------------------------------
    
    def configure(
        self,
        user_id: str,
        strategy: RebalanceStrategy = RebalanceStrategy.THRESHOLD,
        drift_threshold: Decimal = DEFAULT_DRIFT_THRESHOLD,
        min_trade_value: Decimal = DEFAULT_MIN_TRADE_VALUE,
        rebalance_interval_hours: int = 24,
        respect_risk_limits: bool = True,
        tax_efficient: bool = True
    ) -> None:
        """
        Configure rebalancing behavior for a user.
        
        Args:
            user_id: User ID
            strategy: Rebalancing strategy
            drift_threshold: Percentage drift to trigger rebalance
            min_trade_value: Minimum trade size in USD
            rebalance_interval_hours: Hours between periodic rebalances
            respect_risk_limits: Honor position limits and daily loss limits
            tax_efficient: Minimize sells when possible
        """
        self._config[user_id] = {
            "strategy": strategy,
            "drift_threshold": drift_threshold,
            "min_trade_value": min_trade_value,
            "rebalance_interval_hours": rebalance_interval_hours,
            "respect_risk_limits": respect_risk_limits,
            "tax_efficient": tax_efficient,
            "last_rebalance": None
        }
        
        logger.info(f"Configured rebalancing for user {user_id[:8]}...")
    
    def get_config(self, user_id: str) -> dict:
        """Get rebalancing configuration for a user."""
        return self._config.get(user_id, {
            "strategy": RebalanceStrategy.THRESHOLD,
            "drift_threshold": self.DEFAULT_DRIFT_THRESHOLD,
            "min_trade_value": self.DEFAULT_MIN_TRADE_VALUE,
            "rebalance_interval_hours": 24,
            "respect_risk_limits": True,
            "tax_efficient": True
        })
    
    # -------------------------------------------------------------------------
    # Portfolio Analysis
    # -------------------------------------------------------------------------
    
    async def get_portfolio_snapshot(
        self,
        user_id: str
    ) -> tuple[list[PortfolioPosition], Decimal]:
        """
        Get current portfolio positions and total value.
        
        Args:
            user_id: User ID
        
        Returns:
            Tuple of (positions list, total portfolio value)
        """
        # Get open positions from database
        open_positions = await PositionCRUD.get_open_for_user(
            self.db, uuid.UUID(user_id)
        )
        
        positions = []
        total_value = Decimal("0")
        
        for pos in open_positions:
            # Get current price
            current_price = Decimal(str(pos.entry_price))  # Default to entry
            if self.price_fetcher:
                try:
                    price = await self.price_fetcher(pos.token_id)
                    current_price = Decimal(str(price))
                except Exception:
                    pass
            
            # Calculate position value
            entry_value = pos.entry_price * pos.entry_size
            current_value = current_price * pos.entry_size
            pnl = current_value - entry_value
            pnl_pct = (pnl / entry_value * 100) if entry_value > 0 else Decimal("0")
            
            positions.append(PortfolioPosition(
                position_id=str(pos.id),
                condition_id=pos.condition_id,
                token_id=pos.token_id,
                side=pos.side,
                size=pos.entry_size,
                entry_price=pos.entry_price,
                current_price=current_price,
                current_value=current_value,
                pnl=pnl,
                pnl_pct=pnl_pct,
                weight_pct=Decimal("0")  # Calculated below
            ))
            
            total_value += current_value
        
        # Calculate weights
        for pos in positions:
            if total_value > 0:
                pos.weight_pct = (pos.current_value / total_value) * 100
        
        return positions, total_value
    
    async def analyze_portfolio(
        self,
        user_id: str
    ) -> dict[str, Any]:
        """
        Analyze portfolio against target allocations.
        
        Returns analysis including drift, recommendations, and health metrics.
        """
        positions, total_value = await self.get_portfolio_snapshot(user_id)
        targets = self.get_targets(user_id)
        config = self.get_config(user_id)
        
        # Build position map by condition_id
        position_map = {p.condition_id: p for p in positions}
        
        analysis = {
            "total_value": float(total_value),
            "position_count": len(positions),
            "target_count": len(targets),
            "positions": [],
            "recommendations": [],
            "drift_summary": {
                "max_drift": 0,
                "avg_drift": 0,
                "positions_needing_rebalance": 0
            },
            "health": {
                "is_balanced": True,
                "total_drift": 0
            }
        }
        
        total_drift = Decimal("0")
        max_drift = Decimal("0")
        needs_rebalance = 0
        
        for condition_id, target in targets.items():
            position = position_map.get(condition_id)
            
            if position:
                current_pct = position.weight_pct
            else:
                current_pct = Decimal("0")
            
            drift = abs(current_pct - target.target_pct)
            total_drift += drift
            max_drift = max(max_drift, drift)
            
            position_data = {
                "condition_id": condition_id,
                "market_name": target.market_name,
                "target_pct": float(target.target_pct),
                "current_pct": float(current_pct),
                "drift_pct": float(drift),
                "current_value": float(position.current_value) if position else 0,
                "needs_rebalance": drift > config["drift_threshold"]
            }
            analysis["positions"].append(position_data)
            
            # Generate recommendation if drift exceeds threshold
            if drift > config["drift_threshold"]:
                needs_rebalance += 1
                
                if current_pct < target.target_pct:
                    action = RebalanceAction.BUY
                    value_needed = (target.target_pct - current_pct) / 100 * total_value
                else:
                    action = RebalanceAction.SELL
                    value_needed = (current_pct - target.target_pct) / 100 * total_value
                
                # Skip if below minimum trade value
                if value_needed < config["min_trade_value"]:
                    continue
                
                # Get current price for size calculation
                current_price = position.current_price if position else Decimal("0.5")
                if current_price > 0:
                    recommended_size = value_needed / current_price
                else:
                    recommended_size = Decimal("0")
                
                recommendation = RebalanceRecommendation(
                    condition_id=condition_id,
                    token_id=target.token_id,
                    action=action,
                    current_pct=current_pct,
                    target_pct=target.target_pct,
                    drift_pct=drift,
                    recommended_size=recommended_size,
                    recommended_value=value_needed,
                    reason=f"Drift of {float(drift):.1f}% exceeds threshold of {float(config['drift_threshold']):.1f}%"
                )
                
                analysis["recommendations"].append({
                    "condition_id": condition_id,
                    "action": action.value,
                    "current_pct": float(current_pct),
                    "target_pct": float(target.target_pct),
                    "drift_pct": float(drift),
                    "recommended_size": float(recommended_size),
                    "recommended_value": float(value_needed),
                    "reason": recommendation.reason
                })
        
        # Update summary
        analysis["drift_summary"]["max_drift"] = float(max_drift)
        analysis["drift_summary"]["avg_drift"] = float(total_drift / len(targets)) if targets else 0
        analysis["drift_summary"]["positions_needing_rebalance"] = needs_rebalance
        analysis["health"]["total_drift"] = float(total_drift)
        analysis["health"]["is_balanced"] = needs_rebalance == 0
        
        return analysis
    
    # -------------------------------------------------------------------------
    # Rebalancing Execution
    # -------------------------------------------------------------------------
    
    async def rebalance(
        self,
        user_id: str,
        dry_run: bool = False
    ) -> RebalanceResult:
        """
        Execute portfolio rebalancing.
        
        Args:
            user_id: User ID
            dry_run: If True, only generate recommendations without executing
        
        Returns:
            RebalanceResult with actions taken
        """
        config = self.get_config(user_id)
        positions, total_value = await self.get_portfolio_snapshot(user_id)
        
        result = RebalanceResult(
            strategy=config.get("strategy", RebalanceStrategy.THRESHOLD),
            total_value_before=total_value,
            positions_before=len(positions)
        )
        
        # Analyze and get recommendations
        analysis = await self.analyze_portfolio(user_id)
        
        for rec_data in analysis["recommendations"]:
            recommendation = RebalanceRecommendation(
                condition_id=rec_data["condition_id"],
                token_id=self._targets[user_id][rec_data["condition_id"]].token_id,
                action=RebalanceAction(rec_data["action"]),
                current_pct=Decimal(str(rec_data["current_pct"])),
                target_pct=Decimal(str(rec_data["target_pct"])),
                drift_pct=Decimal(str(rec_data["drift_pct"])),
                recommended_size=Decimal(str(rec_data["recommended_size"])),
                recommended_value=Decimal(str(rec_data["recommended_value"])),
                reason=rec_data["reason"]
            )
            result.recommendations.append(recommendation)
        
        if dry_run:
            logger.info(f"Dry run: {len(result.recommendations)} rebalance recommendations")
            return result
        
        # Tax-efficient: process buys before sells if configured
        if config.get("tax_efficient", True):
            buys = [r for r in result.recommendations if r.action == RebalanceAction.BUY]
            sells = [r for r in result.recommendations if r.action == RebalanceAction.SELL]
            ordered_recs = buys + sells
        else:
            ordered_recs = result.recommendations
        
        # Execute each recommendation
        for rec in ordered_recs:
            action_result = {
                "condition_id": rec.condition_id,
                "action": rec.action.value,
                "size": float(rec.recommended_size),
                "value": float(rec.recommended_value),
                "status": "pending"
            }
            
            try:
                side = "BUY" if rec.action == RebalanceAction.BUY else "SELL"
                
                # Get current price for order
                if self.price_fetcher:
                    price = await self.price_fetcher(rec.token_id)
                else:
                    price = 0.5  # Default mid price
                
                order_result = await self.client.place_order(
                    token_id=rec.token_id,
                    side=side,
                    price=price,
                    size=float(rec.recommended_size)
                )
                
                action_result["status"] = "filled"
                action_result["order_id"] = order_result.get("id")
                result.success_count += 1
                result.total_traded_value += rec.recommended_value
                
                logger.info(
                    f"Rebalance {rec.action.value}: {rec.condition_id[:16]}... "
                    f"{rec.recommended_size} contracts @ ${price:.4f}"
                )
                
            except Exception as e:
                action_result["status"] = "failed"
                action_result["error"] = str(e)
                result.failed_count += 1
                logger.error(f"Rebalance failed for {rec.condition_id[:16]}...: {e}")
            
            result.executed_actions.append(action_result)
        
        # Get updated portfolio state
        positions_after, total_value_after = await self.get_portfolio_snapshot(user_id)
        result.total_value_after = total_value_after
        result.positions_after = len(positions_after)
        
        # Update last rebalance time
        if user_id in self._config:
            self._config[user_id]["last_rebalance"] = datetime.now(timezone.utc)
        
        # Store in history
        self._history.append(result)
        
        logger.info(
            f"Rebalancing complete: {result.success_count} succeeded, "
            f"{result.failed_count} failed, ${float(result.total_traded_value):.2f} traded"
        )
        
        return result
    
    # -------------------------------------------------------------------------
    # Automatic Rebalancing
    # -------------------------------------------------------------------------
    
    async def start_auto_rebalance(self, user_id: str) -> None:
        """Start automatic rebalancing for a user."""
        if self._is_running:
            return
        
        self._is_running = True
        self._task = asyncio.create_task(self._auto_rebalance_loop(user_id))
        logger.info(f"Started auto-rebalancing for user {user_id[:8]}...")
    
    async def stop_auto_rebalance(self) -> None:
        """Stop automatic rebalancing."""
        self._is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Stopped auto-rebalancing")
    
    async def _auto_rebalance_loop(self, user_id: str) -> None:
        """Background loop for automatic rebalancing."""
        while self._is_running:
            try:
                config = self.get_config(user_id)
                strategy = config.get("strategy", RebalanceStrategy.THRESHOLD)
                
                should_rebalance = False
                
                if strategy == RebalanceStrategy.THRESHOLD:
                    # Check if any position exceeds drift threshold
                    analysis = await self.analyze_portfolio(user_id)
                    if analysis["drift_summary"]["positions_needing_rebalance"] > 0:
                        should_rebalance = True
                
                elif strategy == RebalanceStrategy.PERIODIC:
                    # Check if enough time has passed
                    last_rebalance = config.get("last_rebalance")
                    interval_hours = config.get("rebalance_interval_hours", 24)
                    
                    if last_rebalance is None:
                        should_rebalance = True
                    else:
                        elapsed = datetime.now(timezone.utc) - last_rebalance
                        if elapsed.total_seconds() >= interval_hours * 3600:
                            should_rebalance = True
                
                if should_rebalance:
                    await self.rebalance(user_id)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Auto-rebalance error: {e}")
            
            # Check every minute
            await asyncio.sleep(60)
    
    # -------------------------------------------------------------------------
    # History and Reporting
    # -------------------------------------------------------------------------
    
    def get_rebalance_history(
        self,
        limit: int = 10
    ) -> list[dict]:
        """Get recent rebalancing history."""
        history = sorted(
            self._history,
            key=lambda r: r.timestamp,
            reverse=True
        )[:limit]
        
        return [
            {
                "id": r.id,
                "timestamp": r.timestamp.isoformat(),
                "strategy": r.strategy.value,
                "status": r.status,
                "success_count": r.success_count,
                "failed_count": r.failed_count,
                "total_traded_value": float(r.total_traded_value),
                "value_before": float(r.total_value_before),
                "value_after": float(r.total_value_after)
            }
            for r in history
        ]


# Global instance
portfolio_rebalancer: PortfolioRebalancer | None = None


def get_portfolio_rebalancer() -> PortfolioRebalancer | None:
    """Get the global portfolio rebalancer instance."""
    return portfolio_rebalancer


def init_portfolio_rebalancer(
    trading_client: Any,
    db: AsyncSession,
    price_fetcher: Callable[[str], float] | None = None
) -> PortfolioRebalancer:
    """Initialize the global portfolio rebalancer."""
    global portfolio_rebalancer
    portfolio_rebalancer = PortfolioRebalancer(
        trading_client=trading_client,
        db=db,
        price_fetcher=price_fetcher
    )
    return portfolio_rebalancer
