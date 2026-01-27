"""
Kelly Criterion Calculator - optimal position sizing based on edge and win rate.
Implements fractional Kelly for conservative position sizing.
"""

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class KellyResult:
    """Kelly criterion calculation result."""
    kelly_fraction: float
    optimal_size: float
    adjusted_size: float
    edge: float
    win_probability: float
    recommended_contracts: int
    max_contracts: int
    sizing_reason: str


class KellyCalculator:
    """
    Calculates optimal position sizes using Kelly criterion.
    
    The Kelly formula: f* = (p * b - q) / b
    Where:
    - f* = fraction of bankroll to wager
    - p = probability of winning
    - q = probability of losing (1 - p)
    - b = odds received on the wager (payout ratio)
    
    For binary prediction markets:
    - If buying YES at price P, payout is (1/P - 1) if win
    - Edge = Expected_Value / Cost = (p/P) - 1
    """
    
    DEFAULT_KELLY_FRACTION = 0.25
    MIN_SAMPLE_SIZE = 20
    MAX_KELLY_FRACTION = 0.5
    MIN_EDGE = 0.02
    
    def __init__(
        self,
        kelly_fraction: float = DEFAULT_KELLY_FRACTION,
        min_sample_size: int = MIN_SAMPLE_SIZE,
        max_kelly_fraction: float = MAX_KELLY_FRACTION,
    ):
        """
        Initialize Kelly calculator.
        
        Args:
            kelly_fraction: Fraction of full Kelly to use (0.25 = quarter Kelly)
            min_sample_size: Minimum trades needed for reliable statistics
            max_kelly_fraction: Maximum allowed Kelly fraction
        """
        self.kelly_fraction = kelly_fraction
        self.min_sample_size = min_sample_size
        self.max_kelly_fraction = max_kelly_fraction
    
    def calculate(
        self,
        bankroll: Decimal,
        current_price: Decimal,
        estimated_win_prob: float,
        historical_win_rate: Optional[float] = None,
        historical_sample_size: int = 0,
        max_position_size: Optional[Decimal] = None,
        min_position_size: Decimal = Decimal("1"),
        contract_price: Decimal = Decimal("1"),
    ) -> KellyResult:
        """
        Calculate optimal position size using Kelly criterion.
        
        Args:
            bankroll: Total available capital
            current_price: Current market price (0-1)
            estimated_win_prob: Estimated probability of winning
            historical_win_rate: Actual win rate from past trades
            historical_sample_size: Number of trades in historical sample
            max_position_size: Maximum allowed position size
            min_position_size: Minimum position size
            contract_price: Price per contract in USDC
        
        Returns:
            KellyResult with optimal sizing recommendation
        """
        win_prob = self._determine_win_probability(
            estimated_win_prob,
            historical_win_rate,
            historical_sample_size,
        )
        
        edge = self._calculate_edge(current_price, win_prob)
        
        if edge <= self.MIN_EDGE:
            return KellyResult(
                kelly_fraction=0,
                optimal_size=0,
                adjusted_size=0,
                edge=edge,
                win_probability=win_prob,
                recommended_contracts=0,
                max_contracts=0,
                sizing_reason=f"Insufficient edge ({edge:.4f} < {self.MIN_EDGE})",
            )
        
        price_float = float(current_price)
        if price_float >= 1 or price_float <= 0:
            return KellyResult(
                kelly_fraction=0,
                optimal_size=0,
                adjusted_size=0,
                edge=edge,
                win_probability=win_prob,
                recommended_contracts=0,
                max_contracts=0,
                sizing_reason="Invalid price (must be between 0 and 1)",
            )
        
        odds = (1 / price_float) - 1
        
        full_kelly = self._calculate_kelly_fraction(win_prob, odds)
        
        adjusted_kelly = full_kelly * self.kelly_fraction
        adjusted_kelly = min(adjusted_kelly, self.max_kelly_fraction)
        adjusted_kelly = max(adjusted_kelly, 0)
        
        bankroll_float = float(bankroll)
        optimal_size = bankroll_float * full_kelly
        adjusted_size = bankroll_float * adjusted_kelly
        
        if max_position_size:
            adjusted_size = min(adjusted_size, float(max_position_size))
        
        adjusted_size = max(adjusted_size, float(min_position_size))
        
        contract_price_float = float(contract_price)
        recommended_contracts = int(adjusted_size / contract_price_float / price_float)
        max_contracts = int(optimal_size / contract_price_float / price_float)
        
        recommended_contracts = max(1, recommended_contracts)
        
        sizing_reason = self._generate_sizing_reason(
            full_kelly, adjusted_kelly, edge, win_prob, historical_sample_size
        )
        
        return KellyResult(
            kelly_fraction=adjusted_kelly,
            optimal_size=optimal_size,
            adjusted_size=adjusted_size,
            edge=edge,
            win_probability=win_prob,
            recommended_contracts=recommended_contracts,
            max_contracts=max_contracts,
            sizing_reason=sizing_reason,
        )
    
    def _determine_win_probability(
        self,
        estimated: float,
        historical: Optional[float],
        sample_size: int,
    ) -> float:
        """
        Blend estimated and historical win probabilities.
        
        Uses Bayesian-like weighting based on sample size.
        """
        if historical is None or sample_size < self.min_sample_size:
            return estimated
        
        confidence = min(1.0, sample_size / (self.min_sample_size * 5))
        
        blended = (estimated * (1 - confidence)) + (historical * confidence)
        
        blended = max(0.01, min(0.99, blended))
        
        return blended
    
    def _calculate_edge(self, current_price: Decimal, win_prob: float) -> float:
        """
        Calculate expected edge (expected value per dollar wagered).
        
        Edge = (win_prob / price) - 1
        If buying at 0.40 with 50% true probability: edge = (0.5/0.4) - 1 = 0.25 (25%)
        """
        price = float(current_price)
        if price <= 0 or price >= 1:
            return 0
        
        edge = (win_prob / price) - 1
        return edge
    
    def _calculate_kelly_fraction(self, win_prob: float, odds: float) -> float:
        """
        Calculate full Kelly fraction.
        
        Kelly formula: f* = (p * b - q) / b
        Where p = win probability, q = 1-p, b = odds
        """
        if odds <= 0:
            return 0
        
        q = 1 - win_prob
        kelly = (win_prob * odds - q) / odds
        
        return max(0, kelly)
    
    def _generate_sizing_reason(
        self,
        full_kelly: float,
        adjusted_kelly: float,
        edge: float,
        win_prob: float,
        sample_size: int,
    ) -> str:
        """Generate explanation for position sizing decision."""
        reasons = []
        
        if edge > 0.15:
            reasons.append("Strong edge detected")
        elif edge > 0.08:
            reasons.append("Moderate edge detected")
        else:
            reasons.append("Small edge detected")
        
        if sample_size < self.min_sample_size:
            reasons.append(f"Limited history ({sample_size} trades)")
        
        if adjusted_kelly < full_kelly * 0.5:
            reasons.append("Conservative sizing applied")
        
        return "; ".join(reasons)
    
    def calculate_from_stats(
        self,
        bankroll: Decimal,
        current_price: Decimal,
        total_trades: int,
        winning_trades: int,
        avg_win_return: float,
        avg_loss_return: float,
        max_position_size: Optional[Decimal] = None,
    ) -> KellyResult:
        """
        Calculate Kelly sizing from historical trade statistics.
        
        Args:
            bankroll: Available capital
            current_price: Current market price
            total_trades: Total number of completed trades
            winning_trades: Number of profitable trades
            avg_win_return: Average return on winning trades (e.g., 0.15 for 15%)
            avg_loss_return: Average loss on losing trades (e.g., -0.08 for 8% loss)
            max_position_size: Maximum position limit
        
        Returns:
            KellyResult with sizing recommendation
        """
        if total_trades == 0:
            return KellyResult(
                kelly_fraction=0,
                optimal_size=0,
                adjusted_size=0,
                edge=0,
                win_probability=0,
                recommended_contracts=0,
                max_contracts=0,
                sizing_reason="No trade history available",
            )
        
        historical_win_rate = winning_trades / total_trades
        
        estimated_win_prob = historical_win_rate
        
        return self.calculate(
            bankroll=bankroll,
            current_price=current_price,
            estimated_win_prob=estimated_win_prob,
            historical_win_rate=historical_win_rate,
            historical_sample_size=total_trades,
            max_position_size=max_position_size,
        )
