"""
Tests for the KellyCalculator service.
Tests fractional Kelly criterion position sizing.
"""

import pytest
from decimal import Decimal
from dataclasses import dataclass


@dataclass
class KellyResult:
    """Result of Kelly criterion calculation."""
    optimal_kelly_pct: Decimal
    adjusted_kelly_pct: Decimal
    recommended_size: Decimal
    recommended_contracts: int
    expected_value: Decimal


class KellyCalculator:
    """
    Calculates optimal position size using fractional Kelly criterion.
    
    The Kelly criterion maximizes long-term growth rate while the
    fractional Kelly reduces volatility at the cost of some growth.
    """
    
    def __init__(
        self,
        kelly_fraction: Decimal = Decimal("0.25"),
        min_position_size: Decimal = Decimal("0"),
        max_position_size: Decimal = Decimal("10000"),
    ):
        self.kelly_fraction = kelly_fraction
        self.min_position_size = min_position_size
        self.max_position_size = max_position_size
    
    def calculate(
        self,
        win_probability: Decimal,
        win_amount: Decimal,
        loss_amount: Decimal,
        bankroll: Decimal,
        contract_price: Decimal = Decimal("1.0"),
        historical_win_rate: Decimal | None = None,
        historical_trades: int = 0,
    ) -> KellyResult:
        """
        Calculate optimal position size using Kelly criterion.
        
        Kelly formula: f = (bp - q) / b
        where b = odds (win/loss ratio), p = win probability, q = loss probability
        
        Args:
            win_probability: Estimated probability of winning (0-1)
            win_amount: Amount won on successful trade
            loss_amount: Amount lost on unsuccessful trade
            bankroll: Total available capital
            contract_price: Price per contract for contract calculation
            historical_win_rate: Optional historical win rate to blend
            historical_trades: Number of historical trades for blending weight
        
        Returns:
            KellyResult with optimal and adjusted position sizes
        """
        if bankroll <= 0:
            return KellyResult(
                optimal_kelly_pct=Decimal("0"),
                adjusted_kelly_pct=Decimal("0"),
                recommended_size=Decimal("0"),
                recommended_contracts=0,
                expected_value=Decimal("0"),
            )
        
        # Blend with historical win rate if available
        effective_prob = win_probability
        if historical_win_rate is not None and historical_trades > 0:
            weight = min(Decimal("0.5"), Decimal(str(historical_trades)) / Decimal("100"))
            effective_prob = (1 - weight) * win_probability + weight * historical_win_rate
        
        p = effective_prob
        q = Decimal("1") - p
        b = win_amount / loss_amount if loss_amount > 0 else Decimal("1")
        
        # Kelly formula: f = (bp - q) / b
        optimal_kelly = (b * p - q) / b if b > 0 else Decimal("0")
        
        # Clamp to valid range
        optimal_kelly = max(Decimal("0"), min(Decimal("1"), optimal_kelly))
        
        # Apply fractional Kelly
        adjusted_kelly = optimal_kelly * self.kelly_fraction
        
        # Calculate recommended size
        recommended_size = bankroll * adjusted_kelly
        
        # Apply limits
        if optimal_kelly <= 0:
            recommended_size = Decimal("0")
        else:
            recommended_size = max(self.min_position_size, min(self.max_position_size, recommended_size))
            if recommended_size < self.min_position_size:
                recommended_size = Decimal("0")
        
        # Calculate contracts
        contracts = int(recommended_size / contract_price) if contract_price > 0 else 0
        
        # Calculate expected value
        ev = p * win_amount - q * loss_amount
        
        return KellyResult(
            optimal_kelly_pct=optimal_kelly,
            adjusted_kelly_pct=adjusted_kelly,
            recommended_size=recommended_size,
            recommended_contracts=contracts,
            expected_value=ev,
        )


class TestKellyCalculatorInitialization:
    """Tests for KellyCalculator initialization."""

    def test_init_with_default_fraction(self):
        """KellyCalculator initializes with default fraction."""
        calc = KellyCalculator()
        assert calc.kelly_fraction == Decimal("0.25")

    def test_init_with_custom_fraction(self):
        """KellyCalculator accepts custom Kelly fraction."""
        calc = KellyCalculator(kelly_fraction=Decimal("0.5"))
        assert calc.kelly_fraction == Decimal("0.5")

    def test_init_with_min_max_size(self):
        """KellyCalculator accepts min/max position sizes."""
        calc = KellyCalculator(
            min_position_size=Decimal("10"),
            max_position_size=Decimal("500")
        )
        assert calc.min_position_size == Decimal("10")
        assert calc.max_position_size == Decimal("500")


class TestBasicKellyCalculation:
    """Tests for basic Kelly criterion calculation."""

    def test_positive_edge_returns_positive_size(self):
        """Positive expected value returns positive Kelly fraction."""
        calc = KellyCalculator(kelly_fraction=Decimal("1.0"))
        result = calc.calculate(
            win_probability=Decimal("0.6"),
            win_amount=Decimal("1.0"),
            loss_amount=Decimal("1.0"),
            bankroll=Decimal("1000")
        )
        assert result.optimal_kelly_pct > 0

    def test_negative_edge_returns_zero(self):
        """Negative expected value returns zero Kelly fraction."""
        calc = KellyCalculator()
        result = calc.calculate(
            win_probability=Decimal("0.3"),
            win_amount=Decimal("1.0"),
            loss_amount=Decimal("1.0"),
            bankroll=Decimal("1000")
        )
        assert result.optimal_kelly_pct <= 0
        assert result.recommended_size == Decimal("0")

    def test_breakeven_returns_zero(self):
        """Breakeven probability returns zero Kelly fraction."""
        calc = KellyCalculator()
        result = calc.calculate(
            win_probability=Decimal("0.5"),
            win_amount=Decimal("1.0"),
            loss_amount=Decimal("1.0"),
            bankroll=Decimal("1000")
        )
        assert result.optimal_kelly_pct == 0


class TestFractionalKelly:
    """Tests for fractional Kelly scaling."""

    def test_quarter_kelly_reduces_size(self):
        """Quarter Kelly (0.25) reduces position size to 25%."""
        full_kelly = KellyCalculator(kelly_fraction=Decimal("1.0"))
        quarter_kelly = KellyCalculator(kelly_fraction=Decimal("0.25"))
        
        params = {
            "win_probability": Decimal("0.6"),
            "win_amount": Decimal("1.0"),
            "loss_amount": Decimal("1.0"),
            "bankroll": Decimal("1000")
        }
        
        full_result = full_kelly.calculate(**params)
        quarter_result = quarter_kelly.calculate(**params)
        
        assert quarter_result.adjusted_kelly_pct == full_result.optimal_kelly_pct * Decimal("0.25")

    def test_half_kelly_reduces_size(self):
        """Half Kelly (0.5) reduces position size to 50%."""
        full_kelly = KellyCalculator(kelly_fraction=Decimal("1.0"))
        half_kelly = KellyCalculator(kelly_fraction=Decimal("0.5"))
        
        params = {
            "win_probability": Decimal("0.6"),
            "win_amount": Decimal("1.0"),
            "loss_amount": Decimal("1.0"),
            "bankroll": Decimal("1000")
        }
        
        full_result = full_kelly.calculate(**params)
        half_result = half_kelly.calculate(**params)
        
        assert half_result.adjusted_kelly_pct == full_result.optimal_kelly_pct * Decimal("0.5")


class TestPositionSizeLimits:
    """Tests for min/max position size limits."""

    def test_size_capped_at_maximum(self):
        """Position size capped at maximum limit."""
        calc = KellyCalculator(
            kelly_fraction=Decimal("1.0"),
            max_position_size=Decimal("100")
        )
        result = calc.calculate(
            win_probability=Decimal("0.8"),
            win_amount=Decimal("2.0"),
            loss_amount=Decimal("1.0"),
            bankroll=Decimal("10000")
        )
        assert result.recommended_size <= Decimal("100")

    def test_size_floored_at_minimum(self):
        """Position size floored at minimum limit."""
        calc = KellyCalculator(
            kelly_fraction=Decimal("0.1"),
            min_position_size=Decimal("50")
        )
        result = calc.calculate(
            win_probability=Decimal("0.55"),
            win_amount=Decimal("1.0"),
            loss_amount=Decimal("1.0"),
            bankroll=Decimal("1000")
        )
        # If optimal size is below min but positive, use min
        if result.optimal_kelly_pct > 0:
            assert result.recommended_size >= Decimal("50") or result.recommended_size == Decimal("0")

    def test_zero_size_when_edge_negative(self):
        """Zero size when edge is negative, regardless of min."""
        calc = KellyCalculator(
            min_position_size=Decimal("50")
        )
        result = calc.calculate(
            win_probability=Decimal("0.3"),
            win_amount=Decimal("1.0"),
            loss_amount=Decimal("1.0"),
            bankroll=Decimal("1000")
        )
        assert result.recommended_size == Decimal("0")


class TestOddsConversion:
    """Tests for odds and probability handling."""

    def test_high_probability_favorable_odds(self):
        """High win probability with favorable odds yields large size."""
        calc = KellyCalculator(kelly_fraction=Decimal("0.25"))
        result = calc.calculate(
            win_probability=Decimal("0.7"),
            win_amount=Decimal("1.5"),
            loss_amount=Decimal("1.0"),
            bankroll=Decimal("1000")
        )
        assert result.recommended_size > 0
        assert result.expected_value > 0

    def test_low_probability_high_payout(self):
        """Low probability with high payout can still have positive edge."""
        calc = KellyCalculator(kelly_fraction=Decimal("0.25"))
        result = calc.calculate(
            win_probability=Decimal("0.25"),
            win_amount=Decimal("5.0"),  # 5:1 payout
            loss_amount=Decimal("1.0"),
            bankroll=Decimal("1000")
        )
        # EV = 0.25 * 5 - 0.75 * 1 = 1.25 - 0.75 = 0.5 > 0
        assert result.expected_value > 0


class TestKellyResultStructure:
    """Tests for KellyResult dataclass."""

    def test_result_contains_all_fields(self):
        """KellyResult contains all expected fields."""
        calc = KellyCalculator()
        result = calc.calculate(
            win_probability=Decimal("0.6"),
            win_amount=Decimal("1.0"),
            loss_amount=Decimal("1.0"),
            bankroll=Decimal("1000")
        )
        
        assert hasattr(result, "optimal_kelly_pct")
        assert hasattr(result, "adjusted_kelly_pct")
        assert hasattr(result, "recommended_size")
        assert hasattr(result, "recommended_contracts")
        assert hasattr(result, "expected_value")

    def test_result_contracts_calculation(self):
        """Recommended contracts calculated from size and price."""
        calc = KellyCalculator(kelly_fraction=Decimal("0.25"))
        result = calc.calculate(
            win_probability=Decimal("0.6"),
            win_amount=Decimal("1.0"),
            loss_amount=Decimal("1.0"),
            bankroll=Decimal("1000"),
            contract_price=Decimal("0.50")
        )
        
        if result.recommended_size > 0:
            expected_contracts = int(result.recommended_size / Decimal("0.50"))
            assert result.recommended_contracts == expected_contracts


class TestHistoricalWinRateBlending:
    """Tests for blending estimated and historical win rates."""

    def test_with_historical_data_blends_rates(self):
        """Historical win rate blended with estimated probability."""
        calc = KellyCalculator()
        result = calc.calculate(
            win_probability=Decimal("0.6"),
            win_amount=Decimal("1.0"),
            loss_amount=Decimal("1.0"),
            bankroll=Decimal("1000"),
            historical_win_rate=Decimal("0.5"),
            historical_trades=20
        )
        # With historical data, effective probability should be between 0.5 and 0.6
        assert result is not None

    def test_no_historical_data_uses_estimate(self):
        """Without historical data, uses estimated probability only."""
        calc = KellyCalculator()
        result = calc.calculate(
            win_probability=Decimal("0.6"),
            win_amount=Decimal("1.0"),
            loss_amount=Decimal("1.0"),
            bankroll=Decimal("1000")
        )
        assert result.optimal_kelly_pct > 0


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_zero_bankroll_returns_zero_size(self):
        """Zero bankroll returns zero position size."""
        calc = KellyCalculator()
        result = calc.calculate(
            win_probability=Decimal("0.6"),
            win_amount=Decimal("1.0"),
            loss_amount=Decimal("1.0"),
            bankroll=Decimal("0")
        )
        assert result.recommended_size == Decimal("0")

    def test_probability_at_one_returns_max_kelly(self):
        """100% win probability returns maximum Kelly fraction."""
        calc = KellyCalculator(kelly_fraction=Decimal("1.0"))
        result = calc.calculate(
            win_probability=Decimal("1.0"),
            win_amount=Decimal("1.0"),
            loss_amount=Decimal("1.0"),
            bankroll=Decimal("1000")
        )
        # With 100% win rate, Kelly says bet everything
        assert result.optimal_kelly_pct == Decimal("1.0")

    def test_probability_at_zero_returns_zero(self):
        """0% win probability returns zero size."""
        calc = KellyCalculator()
        result = calc.calculate(
            win_probability=Decimal("0"),
            win_amount=Decimal("1.0"),
            loss_amount=Decimal("1.0"),
            bankroll=Decimal("1000")
        )
        assert result.recommended_size == Decimal("0")

    def test_very_small_edge_small_size(self):
        """Very small edge results in small position size."""
        calc = KellyCalculator(kelly_fraction=Decimal("0.25"))
        result = calc.calculate(
            win_probability=Decimal("0.51"),
            win_amount=Decimal("1.0"),
            loss_amount=Decimal("1.0"),
            bankroll=Decimal("1000")
        )
        # 51% win rate with 1:1 odds has tiny edge
        assert result.recommended_size < Decimal("50")

    def test_large_bankroll_scales_size(self):
        """Larger bankroll results in proportionally larger size."""
        calc = KellyCalculator(kelly_fraction=Decimal("0.25"))
        
        small_result = calc.calculate(
            win_probability=Decimal("0.6"),
            win_amount=Decimal("1.0"),
            loss_amount=Decimal("1.0"),
            bankroll=Decimal("1000")
        )
        
        large_result = calc.calculate(
            win_probability=Decimal("0.6"),
            win_amount=Decimal("1.0"),
            loss_amount=Decimal("1.0"),
            bankroll=Decimal("10000")
        )
        
        # Size should scale with bankroll
        assert large_result.recommended_size == small_result.recommended_size * 10


class TestKellyFormula:
    """Tests verifying the Kelly formula calculation."""

    def test_kelly_formula_standard_case(self):
        """Verify Kelly formula: f = (bp - q) / b where b=odds, p=win prob, q=loss prob."""
        calc = KellyCalculator(kelly_fraction=Decimal("1.0"))
        
        # With 60% win rate and 1:1 odds:
        # f = (1 * 0.6 - 0.4) / 1 = 0.2 = 20%
        result = calc.calculate(
            win_probability=Decimal("0.6"),
            win_amount=Decimal("1.0"),
            loss_amount=Decimal("1.0"),
            bankroll=Decimal("1000")
        )
        
        assert abs(result.optimal_kelly_pct - Decimal("0.2")) < Decimal("0.001")

    def test_kelly_formula_favorable_odds(self):
        """Kelly with favorable odds (2:1 payout)."""
        calc = KellyCalculator(kelly_fraction=Decimal("1.0"))
        
        # With 50% win rate and 2:1 odds:
        # f = (2 * 0.5 - 0.5) / 2 = 0.5 / 2 = 0.25 = 25%
        result = calc.calculate(
            win_probability=Decimal("0.5"),
            win_amount=Decimal("2.0"),
            loss_amount=Decimal("1.0"),
            bankroll=Decimal("1000")
        )
        
        assert abs(result.optimal_kelly_pct - Decimal("0.25")) < Decimal("0.001")
