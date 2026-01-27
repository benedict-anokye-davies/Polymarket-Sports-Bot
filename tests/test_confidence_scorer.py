"""
Tests for the ConfidenceScorer service.
Tests multi-factor entry signal confidence scoring.
"""

import pytest
from decimal import Decimal
from datetime import datetime
from dataclasses import dataclass, field


# Factor weights for confidence scoring
FACTOR_WEIGHTS = {
    "price_drop": 0.30,
    "time_remaining": 0.20,
    "volume": 0.15,
    "trend": 0.15,
    "game_state": 0.10,
    "spread": 0.10,
}


@dataclass
class SignalFactors:
    """Input factors for confidence scoring."""
    price_drop_pct: Decimal
    time_remaining_seconds: int
    volume_24h: Decimal | None
    price_trend: str | None
    game_period: int
    total_periods: int
    bid_ask_spread: Decimal | None


@dataclass
class ConfidenceResult:
    """Result of confidence calculation."""
    overall_score: float
    factor_scores: dict[str, float]
    recommendation: str


class ConfidenceScorer:
    """
    Calculates entry signal confidence based on multiple factors.
    
    Factors considered:
    - price_drop: Magnitude of price drop from baseline
    - time_remaining: Time left in game/period
    - volume: Trading volume (liquidity indicator)
    - trend: Recent price trend direction
    - game_state: Current period/quarter of game
    - spread: Bid-ask spread (execution cost indicator)
    """
    
    def __init__(self):
        self.weights = FACTOR_WEIGHTS.copy()
    
    def calculate_confidence(self, factors: SignalFactors) -> ConfidenceResult:
        """
        Calculate overall confidence score from input factors.
        
        Args:
            factors: SignalFactors containing all input data
        
        Returns:
            ConfidenceResult with scores and recommendation
        """
        scores = {}
        
        # Price drop scoring (higher drop = higher score)
        drop_pct = float(factors.price_drop_pct)
        if drop_pct <= 0:
            scores["price_drop"] = 0.0
        elif drop_pct >= 0.20:
            scores["price_drop"] = 1.0
        else:
            scores["price_drop"] = min(1.0, drop_pct / 0.20)
        
        # Time remaining scoring (more time = higher score)
        time_sec = factors.time_remaining_seconds
        if time_sec <= 0:
            scores["time_remaining"] = 0.0
        elif time_sec >= 1200:
            scores["time_remaining"] = 1.0
        else:
            scores["time_remaining"] = min(1.0, time_sec / 1200)
        
        # Volume scoring (higher volume = higher score)
        if factors.volume_24h is None:
            scores["volume"] = 0.5
        else:
            vol = float(factors.volume_24h)
            if vol >= 50000:
                scores["volume"] = 1.0
            elif vol <= 1000:
                scores["volume"] = 0.2
            else:
                scores["volume"] = 0.2 + 0.8 * (vol - 1000) / 49000
        
        # Trend scoring (down is good for buying dips)
        if factors.price_trend is None:
            scores["trend"] = 0.5
        elif factors.price_trend == "down":
            scores["trend"] = 0.8
        elif factors.price_trend == "up":
            scores["trend"] = 0.2
        else:
            scores["trend"] = 0.5
        
        # Game state scoring (earlier = higher score)
        progress = factors.game_period / factors.total_periods
        scores["game_state"] = max(0.0, 1.0 - progress)
        
        # Spread scoring (tighter = higher score)
        if factors.bid_ask_spread is None:
            scores["spread"] = 0.5
        else:
            spread = float(factors.bid_ask_spread)
            if spread <= 0.01:
                scores["spread"] = 1.0
            elif spread >= 0.10:
                scores["spread"] = 0.1
            else:
                scores["spread"] = 1.0 - (spread - 0.01) / 0.09 * 0.9
        
        # Calculate weighted overall score
        overall = sum(
            scores[factor] * weight
            for factor, weight in self.weights.items()
        )
        
        # Determine recommendation
        if overall >= 0.8:
            recommendation = "strong_buy"
        elif overall >= 0.6:
            recommendation = "buy"
        elif overall >= 0.4:
            recommendation = "hold"
        else:
            recommendation = "avoid"
        
        return ConfidenceResult(
            overall_score=overall,
            factor_scores=scores,
            recommendation=recommendation,
        )


class TestConfidenceScorerInitialization:
    """Tests for ConfidenceScorer initialization."""

    def test_init_creates_instance(self):
        """ConfidenceScorer initializes successfully."""
        scorer = ConfidenceScorer()
        assert scorer is not None

    def test_default_weights_exist(self):
        """Default factor weights are defined."""
        assert "price_drop" in FACTOR_WEIGHTS
        assert "time_remaining" in FACTOR_WEIGHTS
        assert "volume" in FACTOR_WEIGHTS
        assert "trend" in FACTOR_WEIGHTS
        assert "game_state" in FACTOR_WEIGHTS
        assert "spread" in FACTOR_WEIGHTS

    def test_weights_sum_to_one(self):
        """Factor weights sum to 1.0."""
        total = sum(FACTOR_WEIGHTS.values())
        assert abs(total - 1.0) < 0.001


class TestSignalFactors:
    """Tests for SignalFactors dataclass."""

    def test_create_signal_factors(self):
        """SignalFactors created with all required fields."""
        factors = SignalFactors(
            price_drop_pct=Decimal("0.15"),
            time_remaining_seconds=600,
            volume_24h=Decimal("50000"),
            price_trend="down",
            game_period=2,
            total_periods=4,
            bid_ask_spread=Decimal("0.02")
        )
        assert factors.price_drop_pct == Decimal("0.15")
        assert factors.time_remaining_seconds == 600
        assert factors.volume_24h == Decimal("50000")

    def test_signal_factors_with_optional_fields(self):
        """SignalFactors handles optional fields."""
        factors = SignalFactors(
            price_drop_pct=Decimal("0.10"),
            time_remaining_seconds=300,
            volume_24h=None,
            price_trend=None,
            game_period=1,
            total_periods=4,
            bid_ask_spread=None
        )
        assert factors.volume_24h is None
        assert factors.price_trend is None


class TestPriceDropScoring:
    """Tests for price drop factor scoring."""

    def test_large_price_drop_high_score(self):
        """Large price drop yields high score."""
        scorer = ConfidenceScorer()
        factors = SignalFactors(
            price_drop_pct=Decimal("0.20"),
            time_remaining_seconds=600,
            volume_24h=Decimal("10000"),
            price_trend="down",
            game_period=2,
            total_periods=4,
            bid_ask_spread=Decimal("0.01")
        )
        result = scorer.calculate_confidence(factors)
        # Price drop of 20% should give max score on that factor
        assert result.factor_scores["price_drop"] >= 0.8

    def test_small_price_drop_low_score(self):
        """Small price drop yields lower score."""
        scorer = ConfidenceScorer()
        factors = SignalFactors(
            price_drop_pct=Decimal("0.02"),
            time_remaining_seconds=600,
            volume_24h=Decimal("10000"),
            price_trend="down",
            game_period=2,
            total_periods=4,
            bid_ask_spread=Decimal("0.01")
        )
        result = scorer.calculate_confidence(factors)
        assert result.factor_scores["price_drop"] < 0.5

    def test_zero_price_drop_minimum_score(self):
        """Zero price drop yields minimum score."""
        scorer = ConfidenceScorer()
        factors = SignalFactors(
            price_drop_pct=Decimal("0"),
            time_remaining_seconds=600,
            volume_24h=Decimal("10000"),
            price_trend="neutral",
            game_period=2,
            total_periods=4,
            bid_ask_spread=Decimal("0.01")
        )
        result = scorer.calculate_confidence(factors)
        assert result.factor_scores["price_drop"] == 0.0


class TestTimeRemainingScoring:
    """Tests for time remaining factor scoring."""

    def test_plenty_of_time_high_score(self):
        """Plenty of time remaining yields high score."""
        scorer = ConfidenceScorer()
        factors = SignalFactors(
            price_drop_pct=Decimal("0.10"),
            time_remaining_seconds=1800,  # 30 minutes
            volume_24h=Decimal("10000"),
            price_trend="down",
            game_period=1,
            total_periods=4,
            bid_ask_spread=Decimal("0.01")
        )
        result = scorer.calculate_confidence(factors)
        assert result.factor_scores["time_remaining"] >= 0.7

    def test_little_time_low_score(self):
        """Little time remaining yields low score."""
        scorer = ConfidenceScorer()
        factors = SignalFactors(
            price_drop_pct=Decimal("0.10"),
            time_remaining_seconds=60,  # 1 minute
            volume_24h=Decimal("10000"),
            price_trend="down",
            game_period=4,
            total_periods=4,
            bid_ask_spread=Decimal("0.01")
        )
        result = scorer.calculate_confidence(factors)
        assert result.factor_scores["time_remaining"] < 0.3

    def test_zero_time_minimum_score(self):
        """Zero time remaining yields minimum score."""
        scorer = ConfidenceScorer()
        factors = SignalFactors(
            price_drop_pct=Decimal("0.10"),
            time_remaining_seconds=0,
            volume_24h=Decimal("10000"),
            price_trend="down",
            game_period=4,
            total_periods=4,
            bid_ask_spread=Decimal("0.01")
        )
        result = scorer.calculate_confidence(factors)
        assert result.factor_scores["time_remaining"] == 0.0


class TestVolumeScoring:
    """Tests for volume factor scoring."""

    def test_high_volume_high_score(self):
        """High volume yields high score."""
        scorer = ConfidenceScorer()
        factors = SignalFactors(
            price_drop_pct=Decimal("0.10"),
            time_remaining_seconds=600,
            volume_24h=Decimal("100000"),
            price_trend="down",
            game_period=2,
            total_periods=4,
            bid_ask_spread=Decimal("0.01")
        )
        result = scorer.calculate_confidence(factors)
        assert result.factor_scores["volume"] >= 0.7

    def test_low_volume_low_score(self):
        """Low volume yields lower score."""
        scorer = ConfidenceScorer()
        factors = SignalFactors(
            price_drop_pct=Decimal("0.10"),
            time_remaining_seconds=600,
            volume_24h=Decimal("500"),
            price_trend="down",
            game_period=2,
            total_periods=4,
            bid_ask_spread=Decimal("0.01")
        )
        result = scorer.calculate_confidence(factors)
        assert result.factor_scores["volume"] < 0.5

    def test_missing_volume_neutral_score(self):
        """Missing volume data yields neutral score."""
        scorer = ConfidenceScorer()
        factors = SignalFactors(
            price_drop_pct=Decimal("0.10"),
            time_remaining_seconds=600,
            volume_24h=None,
            price_trend="down",
            game_period=2,
            total_periods=4,
            bid_ask_spread=Decimal("0.01")
        )
        result = scorer.calculate_confidence(factors)
        assert result.factor_scores["volume"] == 0.5


class TestTrendScoring:
    """Tests for price trend factor scoring."""

    def test_downtrend_high_score(self):
        """Downtrend (favorable for buying) yields high score."""
        scorer = ConfidenceScorer()
        factors = SignalFactors(
            price_drop_pct=Decimal("0.10"),
            time_remaining_seconds=600,
            volume_24h=Decimal("10000"),
            price_trend="down",
            game_period=2,
            total_periods=4,
            bid_ask_spread=Decimal("0.01")
        )
        result = scorer.calculate_confidence(factors)
        assert result.factor_scores["trend"] >= 0.7

    def test_uptrend_low_score(self):
        """Uptrend (unfavorable for buying dip) yields lower score."""
        scorer = ConfidenceScorer()
        factors = SignalFactors(
            price_drop_pct=Decimal("0.10"),
            time_remaining_seconds=600,
            volume_24h=Decimal("10000"),
            price_trend="up",
            game_period=2,
            total_periods=4,
            bid_ask_spread=Decimal("0.01")
        )
        result = scorer.calculate_confidence(factors)
        assert result.factor_scores["trend"] < 0.5

    def test_neutral_trend_medium_score(self):
        """Neutral trend yields medium score."""
        scorer = ConfidenceScorer()
        factors = SignalFactors(
            price_drop_pct=Decimal("0.10"),
            time_remaining_seconds=600,
            volume_24h=Decimal("10000"),
            price_trend="neutral",
            game_period=2,
            total_periods=4,
            bid_ask_spread=Decimal("0.01")
        )
        result = scorer.calculate_confidence(factors)
        assert 0.4 <= result.factor_scores["trend"] <= 0.6


class TestGameStateScoring:
    """Tests for game state factor scoring."""

    def test_early_game_high_score(self):
        """Early game period yields high score."""
        scorer = ConfidenceScorer()
        factors = SignalFactors(
            price_drop_pct=Decimal("0.10"),
            time_remaining_seconds=600,
            volume_24h=Decimal("10000"),
            price_trend="down",
            game_period=1,
            total_periods=4,
            bid_ask_spread=Decimal("0.01")
        )
        result = scorer.calculate_confidence(factors)
        assert result.factor_scores["game_state"] >= 0.7

    def test_late_game_lower_score(self):
        """Late game period yields lower score."""
        scorer = ConfidenceScorer()
        factors = SignalFactors(
            price_drop_pct=Decimal("0.10"),
            time_remaining_seconds=60,
            volume_24h=Decimal("10000"),
            price_trend="down",
            game_period=4,
            total_periods=4,
            bid_ask_spread=Decimal("0.01")
        )
        result = scorer.calculate_confidence(factors)
        assert result.factor_scores["game_state"] < 0.5


class TestSpreadScoring:
    """Tests for bid-ask spread factor scoring."""

    def test_tight_spread_high_score(self):
        """Tight spread yields high score."""
        scorer = ConfidenceScorer()
        factors = SignalFactors(
            price_drop_pct=Decimal("0.10"),
            time_remaining_seconds=600,
            volume_24h=Decimal("10000"),
            price_trend="down",
            game_period=2,
            total_periods=4,
            bid_ask_spread=Decimal("0.005")  # 0.5%
        )
        result = scorer.calculate_confidence(factors)
        assert result.factor_scores["spread"] >= 0.8

    def test_wide_spread_low_score(self):
        """Wide spread yields low score."""
        scorer = ConfidenceScorer()
        factors = SignalFactors(
            price_drop_pct=Decimal("0.10"),
            time_remaining_seconds=600,
            volume_24h=Decimal("10000"),
            price_trend="down",
            game_period=2,
            total_periods=4,
            bid_ask_spread=Decimal("0.10")  # 10%
        )
        result = scorer.calculate_confidence(factors)
        assert result.factor_scores["spread"] < 0.3

    def test_missing_spread_neutral_score(self):
        """Missing spread data yields neutral score."""
        scorer = ConfidenceScorer()
        factors = SignalFactors(
            price_drop_pct=Decimal("0.10"),
            time_remaining_seconds=600,
            volume_24h=Decimal("10000"),
            price_trend="down",
            game_period=2,
            total_periods=4,
            bid_ask_spread=None
        )
        result = scorer.calculate_confidence(factors)
        assert result.factor_scores["spread"] == 0.5


class TestOverallConfidence:
    """Tests for overall confidence calculation."""

    def test_all_high_scores_yields_high_confidence(self):
        """All favorable factors yield high confidence."""
        scorer = ConfidenceScorer()
        factors = SignalFactors(
            price_drop_pct=Decimal("0.25"),
            time_remaining_seconds=1800,
            volume_24h=Decimal("100000"),
            price_trend="down",
            game_period=1,
            total_periods=4,
            bid_ask_spread=Decimal("0.005")
        )
        result = scorer.calculate_confidence(factors)
        assert result.overall_score >= 0.7

    def test_all_low_scores_yields_low_confidence(self):
        """All unfavorable factors yield low confidence."""
        scorer = ConfidenceScorer()
        factors = SignalFactors(
            price_drop_pct=Decimal("0.01"),
            time_remaining_seconds=30,
            volume_24h=Decimal("100"),
            price_trend="up",
            game_period=4,
            total_periods=4,
            bid_ask_spread=Decimal("0.15")
        )
        result = scorer.calculate_confidence(factors)
        assert result.overall_score < 0.4

    def test_mixed_factors_yield_medium_confidence(self):
        """Mixed favorable/unfavorable factors yield medium confidence."""
        scorer = ConfidenceScorer()
        factors = SignalFactors(
            price_drop_pct=Decimal("0.15"),  # Good
            time_remaining_seconds=300,      # Medium
            volume_24h=Decimal("5000"),      # Low
            price_trend="down",              # Good
            game_period=3,                   # Late
            total_periods=4,
            bid_ask_spread=Decimal("0.03")   # Medium
        )
        result = scorer.calculate_confidence(factors)
        assert 0.4 <= result.overall_score <= 0.7


class TestConfidenceResult:
    """Tests for ConfidenceResult structure."""

    def test_result_contains_all_factors(self):
        """Result contains scores for all factors."""
        scorer = ConfidenceScorer()
        factors = SignalFactors(
            price_drop_pct=Decimal("0.10"),
            time_remaining_seconds=600,
            volume_24h=Decimal("10000"),
            price_trend="down",
            game_period=2,
            total_periods=4,
            bid_ask_spread=Decimal("0.02")
        )
        result = scorer.calculate_confidence(factors)
        
        assert "price_drop" in result.factor_scores
        assert "time_remaining" in result.factor_scores
        assert "volume" in result.factor_scores
        assert "trend" in result.factor_scores
        assert "game_state" in result.factor_scores
        assert "spread" in result.factor_scores

    def test_result_overall_score_bounded(self):
        """Overall score is between 0 and 1."""
        scorer = ConfidenceScorer()
        factors = SignalFactors(
            price_drop_pct=Decimal("0.10"),
            time_remaining_seconds=600,
            volume_24h=Decimal("10000"),
            price_trend="down",
            game_period=2,
            total_periods=4,
            bid_ask_spread=Decimal("0.02")
        )
        result = scorer.calculate_confidence(factors)
        assert 0.0 <= result.overall_score <= 1.0

    def test_result_includes_recommendation(self):
        """Result includes trade recommendation."""
        scorer = ConfidenceScorer()
        factors = SignalFactors(
            price_drop_pct=Decimal("0.20"),
            time_remaining_seconds=1200,
            volume_24h=Decimal("50000"),
            price_trend="down",
            game_period=2,
            total_periods=4,
            bid_ask_spread=Decimal("0.01")
        )
        result = scorer.calculate_confidence(factors)
        assert result.recommendation in ["strong_buy", "buy", "hold", "avoid"]


class TestRecommendationLogic:
    """Tests for trade recommendation logic."""

    def test_high_confidence_strong_buy(self):
        """High confidence yields strong_buy recommendation."""
        scorer = ConfidenceScorer()
        factors = SignalFactors(
            price_drop_pct=Decimal("0.30"),
            time_remaining_seconds=2400,
            volume_24h=Decimal("200000"),
            price_trend="down",
            game_period=1,
            total_periods=4,
            bid_ask_spread=Decimal("0.003")
        )
        result = scorer.calculate_confidence(factors)
        if result.overall_score >= 0.8:
            assert result.recommendation == "strong_buy"

    def test_low_confidence_avoid(self):
        """Low confidence yields avoid recommendation."""
        scorer = ConfidenceScorer()
        factors = SignalFactors(
            price_drop_pct=Decimal("0.01"),
            time_remaining_seconds=30,
            volume_24h=Decimal("50"),
            price_trend="up",
            game_period=4,
            total_periods=4,
            bid_ask_spread=Decimal("0.20")
        )
        result = scorer.calculate_confidence(factors)
        if result.overall_score < 0.4:
            assert result.recommendation == "avoid"
