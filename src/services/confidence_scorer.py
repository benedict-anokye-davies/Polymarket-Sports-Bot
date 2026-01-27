"""
Confidence Scorer service - calculates multi-factor entry confidence scores.
Combines price, timing, volume, and trend signals into actionable score.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)


@dataclass
class ConfidenceFactors:
    """Individual confidence factor scores."""
    price_drop_score: float = 0.0
    time_remaining_score: float = 0.0
    volume_score: float = 0.0
    trend_score: float = 0.0
    game_state_score: float = 0.0
    spread_score: float = 0.0


@dataclass
class ConfidenceResult:
    """Complete confidence scoring result."""
    overall_score: float
    factors: ConfidenceFactors
    breakdown: dict
    recommendation: str
    generated_at: datetime


class ConfidenceScorer:
    """
    Calculates multi-factor confidence scores for entry signals.
    
    Scoring Factors (0.0 - 1.0 each):
    - Price Drop: How significant is the price movement from baseline
    - Time Remaining: Sufficient time for price recovery
    - Volume: Order book depth and liquidity
    - Trend: Recent price direction (looking for reversal)
    - Game State: Score differential and game phase
    - Spread: Bid-ask spread tightness
    """
    
    FACTOR_WEIGHTS = {
        "price_drop": 0.30,
        "time_remaining": 0.20,
        "volume": 0.15,
        "trend": 0.15,
        "game_state": 0.10,
        "spread": 0.10,
    }
    
    def __init__(
        self,
        min_confidence_threshold: float = 0.6,
        price_drop_threshold: float = 0.05,
        min_time_remaining_pct: float = 0.25,
    ):
        self.min_confidence_threshold = min_confidence_threshold
        self.price_drop_threshold = price_drop_threshold
        self.min_time_remaining_pct = min_time_remaining_pct
    
    def calculate_confidence(
        self,
        current_price: Decimal,
        baseline_price: Decimal,
        time_remaining_seconds: int,
        total_period_seconds: int,
        orderbook: dict | None = None,
        recent_prices: list[Decimal] | None = None,
        game_score_diff: int | None = None,
        current_period: int = 1,
        total_periods: int = 4,
    ) -> ConfidenceResult:
        """
        Calculate comprehensive confidence score for entry signal.
        
        Args:
            current_price: Current market price
            baseline_price: Pre-game baseline price
            time_remaining_seconds: Seconds left in current period
            total_period_seconds: Total seconds in a period
            orderbook: Order book data with bids/asks
            recent_prices: Recent price history for trend analysis
            game_score_diff: Point differential (positive = favored team ahead)
            current_period: Current game period/quarter
            total_periods: Total periods in game
        
        Returns:
            ConfidenceResult with overall score and breakdown
        """
        factors = ConfidenceFactors()
        
        factors.price_drop_score = self._score_price_drop(
            current_price, baseline_price
        )
        
        factors.time_remaining_score = self._score_time_remaining(
            time_remaining_seconds, total_period_seconds, current_period, total_periods
        )
        
        factors.volume_score = self._score_volume(orderbook)
        
        factors.trend_score = self._score_trend(recent_prices, current_price)
        
        factors.game_state_score = self._score_game_state(
            game_score_diff, current_period, total_periods
        )
        
        factors.spread_score = self._score_spread(orderbook, current_price)
        
        overall_score = (
            factors.price_drop_score * self.FACTOR_WEIGHTS["price_drop"] +
            factors.time_remaining_score * self.FACTOR_WEIGHTS["time_remaining"] +
            factors.volume_score * self.FACTOR_WEIGHTS["volume"] +
            factors.trend_score * self.FACTOR_WEIGHTS["trend"] +
            factors.game_state_score * self.FACTOR_WEIGHTS["game_state"] +
            factors.spread_score * self.FACTOR_WEIGHTS["spread"]
        )
        
        breakdown = {
            "price_drop": {
                "score": factors.price_drop_score,
                "weight": self.FACTOR_WEIGHTS["price_drop"],
                "weighted": factors.price_drop_score * self.FACTOR_WEIGHTS["price_drop"],
                "details": {
                    "current_price": float(current_price),
                    "baseline_price": float(baseline_price),
                    "drop_pct": float((baseline_price - current_price) / baseline_price) if baseline_price else 0,
                }
            },
            "time_remaining": {
                "score": factors.time_remaining_score,
                "weight": self.FACTOR_WEIGHTS["time_remaining"],
                "weighted": factors.time_remaining_score * self.FACTOR_WEIGHTS["time_remaining"],
                "details": {
                    "remaining_seconds": time_remaining_seconds,
                    "period": current_period,
                }
            },
            "volume": {
                "score": factors.volume_score,
                "weight": self.FACTOR_WEIGHTS["volume"],
                "weighted": factors.volume_score * self.FACTOR_WEIGHTS["volume"],
            },
            "trend": {
                "score": factors.trend_score,
                "weight": self.FACTOR_WEIGHTS["trend"],
                "weighted": factors.trend_score * self.FACTOR_WEIGHTS["trend"],
            },
            "game_state": {
                "score": factors.game_state_score,
                "weight": self.FACTOR_WEIGHTS["game_state"],
                "weighted": factors.game_state_score * self.FACTOR_WEIGHTS["game_state"],
            },
            "spread": {
                "score": factors.spread_score,
                "weight": self.FACTOR_WEIGHTS["spread"],
                "weighted": factors.spread_score * self.FACTOR_WEIGHTS["spread"],
            },
        }
        
        recommendation = self._generate_recommendation(overall_score, factors)
        
        return ConfidenceResult(
            overall_score=round(overall_score, 4),
            factors=factors,
            breakdown=breakdown,
            recommendation=recommendation,
            generated_at=datetime.now(timezone.utc),
        )
    
    def _score_price_drop(
        self,
        current_price: Decimal,
        baseline_price: Decimal,
    ) -> float:
        """
        Score based on magnitude of price drop from baseline.
        Larger drops get higher scores (indicates potential value).
        """
        if not baseline_price or baseline_price == 0:
            return 0.0
        
        drop_pct = float((baseline_price - current_price) / baseline_price)
        
        if drop_pct <= 0:
            return 0.0
        
        if drop_pct >= 0.20:
            return 1.0
        elif drop_pct >= 0.15:
            return 0.9
        elif drop_pct >= 0.10:
            return 0.8
        elif drop_pct >= 0.07:
            return 0.7
        elif drop_pct >= 0.05:
            return 0.6
        elif drop_pct >= 0.03:
            return 0.4
        else:
            return 0.2
    
    def _score_time_remaining(
        self,
        time_remaining_seconds: int,
        total_period_seconds: int,
        current_period: int,
        total_periods: int,
    ) -> float:
        """
        Score based on time remaining in game.
        More time = higher score (more recovery opportunity).
        """
        if total_period_seconds == 0:
            return 0.5
        
        periods_remaining = total_periods - current_period
        time_in_period_pct = time_remaining_seconds / total_period_seconds
        
        total_remaining_pct = (periods_remaining + time_in_period_pct) / total_periods
        
        if total_remaining_pct >= 0.75:
            return 1.0
        elif total_remaining_pct >= 0.50:
            return 0.8
        elif total_remaining_pct >= 0.25:
            return 0.6
        elif total_remaining_pct >= 0.10:
            return 0.4
        else:
            return 0.2
    
    def _score_volume(self, orderbook: dict | None) -> float:
        """
        Score based on order book depth and liquidity.
        Deeper books = easier execution, higher score.
        """
        if not orderbook:
            return 0.5
        
        bids = orderbook.get("bids", [])
        asks = orderbook.get("asks", [])
        
        bid_depth = sum(float(b.get("size", 0)) for b in bids[:5])
        ask_depth = sum(float(a.get("size", 0)) for a in asks[:5])
        
        total_depth = bid_depth + ask_depth
        
        if total_depth >= 10000:
            return 1.0
        elif total_depth >= 5000:
            return 0.8
        elif total_depth >= 1000:
            return 0.6
        elif total_depth >= 100:
            return 0.4
        else:
            return 0.2
    
    def _score_trend(
        self,
        recent_prices: list[Decimal] | None,
        current_price: Decimal,
    ) -> float:
        """
        Score based on recent price trend.
        Looking for stabilization or reversal after drop.
        """
        if not recent_prices or len(recent_prices) < 3:
            return 0.5
        
        prices = [float(p) for p in recent_prices[-10:]]
        
        if len(prices) >= 3:
            recent_avg = sum(prices[-3:]) / 3
            earlier_avg = sum(prices[:3]) / min(3, len(prices[:3]))
            
            trend_direction = recent_avg - earlier_avg
            
            if trend_direction > 0.02:
                return 0.9
            elif trend_direction > 0:
                return 0.7
            elif trend_direction > -0.02:
                return 0.5
            elif trend_direction > -0.05:
                return 0.3
            else:
                return 0.1
        
        return 0.5
    
    def _score_game_state(
        self,
        score_diff: int | None,
        current_period: int,
        total_periods: int,
    ) -> float:
        """
        Score based on game state and score differential.
        Being behind early = potential value opportunity.
        """
        if score_diff is None:
            return 0.5
        
        game_progress = current_period / total_periods
        
        if score_diff < 0:
            deficit = abs(score_diff)
            
            if game_progress < 0.5:
                if deficit <= 10:
                    return 0.9
                elif deficit <= 15:
                    return 0.7
                else:
                    return 0.5
            else:
                if deficit <= 5:
                    return 0.7
                elif deficit <= 10:
                    return 0.5
                else:
                    return 0.3
        
        elif score_diff > 0:
            return 0.6
        
        return 0.7
    
    def _score_spread(
        self,
        orderbook: dict | None,
        current_price: Decimal,
    ) -> float:
        """
        Score based on bid-ask spread tightness.
        Tighter spread = better execution, higher score.
        """
        if not orderbook:
            return 0.5
        
        bids = orderbook.get("bids", [])
        asks = orderbook.get("asks", [])
        
        if not bids or not asks:
            return 0.5
        
        best_bid = float(bids[0].get("price", 0))
        best_ask = float(asks[0].get("price", 0))
        
        if best_bid == 0:
            return 0.3
        
        spread_pct = (best_ask - best_bid) / best_bid
        
        if spread_pct <= 0.005:
            return 1.0
        elif spread_pct <= 0.01:
            return 0.8
        elif spread_pct <= 0.02:
            return 0.6
        elif spread_pct <= 0.05:
            return 0.4
        else:
            return 0.2
    
    def _generate_recommendation(
        self,
        overall_score: float,
        factors: ConfidenceFactors,
    ) -> str:
        """Generate human-readable recommendation based on scores."""
        if overall_score >= 0.8:
            return "STRONG_ENTRY"
        elif overall_score >= 0.7:
            return "GOOD_ENTRY"
        elif overall_score >= self.min_confidence_threshold:
            return "ACCEPTABLE_ENTRY"
        elif overall_score >= 0.4:
            return "WEAK_ENTRY"
        else:
            return "NO_ENTRY"
    
    def meets_threshold(self, result: ConfidenceResult) -> bool:
        """Check if confidence score meets minimum threshold for entry."""
        return result.overall_score >= self.min_confidence_threshold
