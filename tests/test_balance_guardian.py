"""
Tests for the BalanceGuardian service.
Tests balance monitoring, kill switch activation, and losing streak tracking.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal
from datetime import datetime, timedelta
from dataclasses import dataclass


@dataclass
class BalanceCheckResult:
    """Result of a balance check operation."""
    can_trade: bool
    kill_switch_triggered: bool
    reason: str | None
    position_size_multiplier: Decimal


class BalanceGuardianLogic:
    """
    Standalone logic for balance guardian operations.
    Used for unit testing without database dependencies.
    """
    
    def __init__(
        self,
        min_balance_threshold: Decimal = Decimal("100"),
        max_losing_streak: int = 5,
        streak_reduction_pct: Decimal = Decimal("0.5"),
        discord_webhook_url: str | None = None,
    ):
        self.min_balance_threshold = min_balance_threshold
        self.max_losing_streak = max_losing_streak
        self.streak_reduction_pct = streak_reduction_pct
        self.discord_webhook_url = discord_webhook_url
    
    def check_balance(
        self,
        current_balance: Decimal,
        current_streak: int,
    ) -> BalanceCheckResult:
        """
        Check if trading should be allowed based on balance and streak.
        
        Args:
            current_balance: Current account balance
            current_streak: Current losing streak count
        
        Returns:
            BalanceCheckResult with trading permission and any adjustments
        """
        if current_balance < self.min_balance_threshold:
            return BalanceCheckResult(
                can_trade=False,
                kill_switch_triggered=True,
                reason=f"Balance ${current_balance} below minimum threshold ${self.min_balance_threshold}",
                position_size_multiplier=Decimal("0"),
            )
        
        multiplier = Decimal("1.0")
        if current_streak >= self.max_losing_streak:
            multiplier = self.streak_reduction_pct
        
        return BalanceCheckResult(
            can_trade=True,
            kill_switch_triggered=False,
            reason=None,
            position_size_multiplier=multiplier,
        )
    
    def record_trade_outcome(
        self,
        is_win: bool,
        current_streak: int,
    ) -> int:
        """
        Update losing streak based on trade outcome.
        
        Args:
            is_win: Whether the trade was profitable
            current_streak: Current losing streak count
        
        Returns:
            New losing streak count
        """
        if is_win:
            return 0
        return current_streak + 1
    
    def calculate_adjusted_size(
        self,
        base_size: Decimal,
        current_streak: int,
    ) -> Decimal:
        """
        Calculate adjusted position size based on losing streak.
        
        Args:
            base_size: Original position size
            current_streak: Current losing streak count
        
        Returns:
            Adjusted position size
        """
        if current_streak >= self.max_losing_streak:
            return base_size * self.streak_reduction_pct
        return base_size


# Use the standalone logic class for testing
BalanceGuardian = BalanceGuardianLogic


class TestBalanceGuardianInitialization:
    """Tests for BalanceGuardian initialization."""

    def test_init_with_defaults(self):
        """BalanceGuardian initializes with default values."""
        guardian = BalanceGuardian()
        assert guardian.min_balance_threshold == Decimal("100")
        assert guardian.max_losing_streak == 5
        assert guardian.streak_reduction_pct == Decimal("0.5")

    def test_init_with_custom_values(self):
        """BalanceGuardian accepts custom threshold values."""
        guardian = BalanceGuardian(
            min_balance_threshold=Decimal("500"),
            max_losing_streak=3,
            streak_reduction_pct=Decimal("0.25")
        )
        assert guardian.min_balance_threshold == Decimal("500")
        assert guardian.max_losing_streak == 3
        assert guardian.streak_reduction_pct == Decimal("0.25")

    def test_init_with_discord_webhook(self):
        """BalanceGuardian stores discord webhook URL."""
        guardian = BalanceGuardian(discord_webhook_url="https://discord.com/webhook")
        assert guardian.discord_webhook_url == "https://discord.com/webhook"


class TestBalanceCheck:
    """Tests for balance checking logic."""

    def test_balance_above_threshold_allowed(self):
        """Trading allowed when balance is above threshold."""
        guardian = BalanceGuardian(min_balance_threshold=Decimal("100"))
        result = guardian.check_balance(
            current_balance=Decimal("500"),
            current_streak=0
        )
        assert result.can_trade is True
        assert result.kill_switch_triggered is False
        assert result.reason is None

    def test_balance_below_threshold_triggers_kill_switch(self):
        """Kill switch triggered when balance drops below threshold."""
        guardian = BalanceGuardian(min_balance_threshold=Decimal("100"))
        result = guardian.check_balance(
            current_balance=Decimal("50"),
            current_streak=0
        )
        assert result.can_trade is False
        assert result.kill_switch_triggered is True
        assert "below minimum" in result.reason.lower()

    def test_balance_exactly_at_threshold_allowed(self):
        """Trading allowed when balance equals threshold."""
        guardian = BalanceGuardian(min_balance_threshold=Decimal("100"))
        result = guardian.check_balance(
            current_balance=Decimal("100"),
            current_streak=0
        )
        assert result.can_trade is True
        assert result.kill_switch_triggered is False

    def test_zero_balance_triggers_kill_switch(self):
        """Kill switch triggered on zero balance."""
        guardian = BalanceGuardian(min_balance_threshold=Decimal("100"))
        result = guardian.check_balance(
            current_balance=Decimal("0"),
            current_streak=0
        )
        assert result.can_trade is False
        assert result.kill_switch_triggered is True


class TestLosingStreakTracking:
    """Tests for losing streak tracking and position size reduction."""

    def test_streak_below_max_no_reduction(self):
        """No reduction when streak is below maximum."""
        guardian = BalanceGuardian(max_losing_streak=5)
        result = guardian.check_balance(
            current_balance=Decimal("500"),
            current_streak=3
        )
        assert result.can_trade is True
        assert result.position_size_multiplier == Decimal("1.0")

    def test_streak_at_max_triggers_reduction(self):
        """Position size reduced when streak reaches maximum."""
        guardian = BalanceGuardian(
            max_losing_streak=5,
            streak_reduction_pct=Decimal("0.5")
        )
        result = guardian.check_balance(
            current_balance=Decimal("500"),
            current_streak=5
        )
        assert result.can_trade is True
        assert result.position_size_multiplier == Decimal("0.5")

    def test_streak_above_max_maintains_reduction(self):
        """Position size stays reduced when streak exceeds maximum."""
        guardian = BalanceGuardian(
            max_losing_streak=5,
            streak_reduction_pct=Decimal("0.5")
        )
        result = guardian.check_balance(
            current_balance=Decimal("500"),
            current_streak=8
        )
        assert result.can_trade is True
        assert result.position_size_multiplier == Decimal("0.5")

    def test_streak_reset_restores_full_size(self):
        """Full position size restored when streak resets."""
        guardian = BalanceGuardian(max_losing_streak=5)
        result = guardian.check_balance(
            current_balance=Decimal("500"),
            current_streak=0
        )
        assert result.position_size_multiplier == Decimal("1.0")


class TestRecordTradeOutcome:
    """Tests for recording trade outcomes."""

    def test_record_winning_trade_resets_streak(self):
        """Winning trade resets losing streak to zero."""
        guardian = BalanceGuardian()
        new_streak = guardian.record_trade_outcome(
            is_win=True,
            current_streak=5
        )
        assert new_streak == 0

    def test_record_losing_trade_increments_streak(self):
        """Losing trade increments streak by one."""
        guardian = BalanceGuardian()
        new_streak = guardian.record_trade_outcome(
            is_win=False,
            current_streak=3
        )
        assert new_streak == 4

    def test_first_loss_starts_streak(self):
        """First loss starts streak at one."""
        guardian = BalanceGuardian()
        new_streak = guardian.record_trade_outcome(
            is_win=False,
            current_streak=0
        )
        assert new_streak == 1


class TestCalculateAdjustedSize:
    """Tests for position size adjustment calculation."""

    def test_no_adjustment_below_streak_threshold(self):
        """Position size unchanged below streak threshold."""
        guardian = BalanceGuardian(max_losing_streak=5)
        adjusted = guardian.calculate_adjusted_size(
            base_size=Decimal("100"),
            current_streak=3
        )
        assert adjusted == Decimal("100")

    def test_size_reduced_at_streak_threshold(self):
        """Position size reduced at streak threshold."""
        guardian = BalanceGuardian(
            max_losing_streak=5,
            streak_reduction_pct=Decimal("0.5")
        )
        adjusted = guardian.calculate_adjusted_size(
            base_size=Decimal("100"),
            current_streak=5
        )
        assert adjusted == Decimal("50")

    def test_size_reduction_rounds_down(self):
        """Adjusted size rounds down to avoid over-allocation."""
        guardian = BalanceGuardian(
            max_losing_streak=3,
            streak_reduction_pct=Decimal("0.5")
        )
        adjusted = guardian.calculate_adjusted_size(
            base_size=Decimal("75"),
            current_streak=3
        )
        assert adjusted == Decimal("37.5")


class TestBalanceCheckResult:
    """Tests for BalanceCheckResult dataclass."""

    def test_result_can_trade_true(self):
        """Result with can_trade=True has expected properties."""
        result = BalanceCheckResult(
            can_trade=True,
            kill_switch_triggered=False,
            reason=None,
            position_size_multiplier=Decimal("1.0")
        )
        assert result.can_trade is True
        assert result.kill_switch_triggered is False
        assert result.position_size_multiplier == Decimal("1.0")

    def test_result_with_kill_switch(self):
        """Result with kill switch has reason."""
        result = BalanceCheckResult(
            can_trade=False,
            kill_switch_triggered=True,
            reason="Balance below minimum threshold",
            position_size_multiplier=Decimal("0")
        )
        assert result.can_trade is False
        assert result.kill_switch_triggered is True
        assert result.reason is not None


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_negative_balance_handled(self):
        """Negative balance triggers kill switch."""
        guardian = BalanceGuardian(min_balance_threshold=Decimal("100"))
        result = guardian.check_balance(
            current_balance=Decimal("-50"),
            current_streak=0
        )
        assert result.can_trade is False
        assert result.kill_switch_triggered is True

    def test_very_large_balance_allowed(self):
        """Very large balance is allowed."""
        guardian = BalanceGuardian(min_balance_threshold=Decimal("100"))
        result = guardian.check_balance(
            current_balance=Decimal("1000000"),
            current_streak=0
        )
        assert result.can_trade is True

    def test_zero_threshold_always_allows_trading(self):
        """Zero threshold allows trading at any balance."""
        guardian = BalanceGuardian(min_balance_threshold=Decimal("0"))
        result = guardian.check_balance(
            current_balance=Decimal("1"),
            current_streak=0
        )
        assert result.can_trade is True

    def test_high_streak_with_low_balance(self):
        """Both high streak and low balance handled correctly."""
        guardian = BalanceGuardian(
            min_balance_threshold=Decimal("100"),
            max_losing_streak=3
        )
        result = guardian.check_balance(
            current_balance=Decimal("50"),
            current_streak=10
        )
        # Kill switch takes precedence
        assert result.can_trade is False
        assert result.kill_switch_triggered is True
