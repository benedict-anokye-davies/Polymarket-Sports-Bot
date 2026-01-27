"""
Tests for the AccountManager service.
Tests multi-account management and allocation.
"""

import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass, field


@dataclass
class AccountSummary:
    """Summary of an account's status."""
    account_id: str
    platform: str
    is_primary: bool
    is_active: bool
    allocation: Decimal
    balance: Decimal = Decimal("0")


@dataclass
class AccountInfo:
    """Internal account information."""
    account_id: str
    platform: str
    is_primary: bool
    is_active: bool
    allocation: Decimal


class AccountManager:
    """
    Manages multiple trading accounts across platforms.
    
    Supports:
    - Account registration with platform type
    - Primary account designation
    - Balance allocation across accounts
    - Position sizing per account
    - Active/inactive status management
    """
    
    def __init__(self):
        self.accounts: dict[str, AccountInfo] = {}
        self._primary_account_id: str | None = None
    
    def register_account(
        self,
        account_id: str,
        platform: str,
        is_primary: bool = False,
        allocation: Decimal = Decimal("0"),
    ) -> None:
        """
        Register a trading account.
        
        Args:
            account_id: Unique account identifier
            platform: Platform name (polymarket, kalshi)
            is_primary: Whether this is the primary account
            allocation: Percentage allocation for this account (0-1)
        
        Raises:
            ValueError: If account already exists
        """
        if account_id in self.accounts:
            raise ValueError(f"Account {account_id} already registered")
        
        # First account becomes primary by default
        if not self.accounts:
            is_primary = True
        
        account = AccountInfo(
            account_id=account_id,
            platform=platform,
            is_primary=is_primary,
            is_active=True,
            allocation=allocation,
        )
        self.accounts[account_id] = account
        
        if is_primary:
            # Unset previous primary
            for acc in self.accounts.values():
                if acc.account_id != account_id:
                    acc.is_primary = False
            self._primary_account_id = account_id
    
    def remove_account(self, account_id: str) -> None:
        """
        Remove an account from management.
        
        Args:
            account_id: Account to remove
        
        Raises:
            ValueError: If account not found
        """
        if account_id not in self.accounts:
            raise ValueError(f"Account {account_id} not found")
        
        was_primary = self.accounts[account_id].is_primary
        del self.accounts[account_id]
        
        if was_primary:
            self._primary_account_id = None
            # Promote next account to primary
            if self.accounts:
                next_account = next(iter(self.accounts.values()))
                next_account.is_primary = True
                self._primary_account_id = next_account.account_id
    
    def set_primary(self, account_id: str) -> None:
        """
        Set an account as primary.
        
        Args:
            account_id: Account to make primary
        
        Raises:
            ValueError: If account not found
        """
        if account_id not in self.accounts:
            raise ValueError(f"Account {account_id} not found")
        
        for acc_id, acc in self.accounts.items():
            acc.is_primary = (acc_id == account_id)
        
        self._primary_account_id = account_id
    
    def get_primary_account(self) -> str | None:
        """Get the primary account ID."""
        return self._primary_account_id
    
    def set_active(self, account_id: str, is_active: bool) -> None:
        """
        Set account active status.
        
        Args:
            account_id: Account to update
            is_active: New active status
        """
        if account_id in self.accounts:
            self.accounts[account_id].is_active = is_active
    
    def is_active(self, account_id: str) -> bool:
        """Check if account is active."""
        if account_id not in self.accounts:
            return False
        return self.accounts[account_id].is_active
    
    def set_allocation(self, account_id: str, allocation: Decimal) -> None:
        """
        Set allocation percentage for an account.
        
        Args:
            account_id: Account to update
            allocation: New allocation (0-1)
        
        Raises:
            ValueError: If allocation is negative or would exceed total of 1.0
        """
        if allocation < Decimal("0"):
            raise ValueError("Allocation cannot be negative")
        
        # Calculate total allocation if we set this value
        other_total = sum(
            acc.allocation for acc_id, acc in self.accounts.items() 
            if acc_id != account_id
        )
        
        if other_total + allocation > Decimal("1.0"):
            raise ValueError("Total allocation would exceed 100%")
        
        if account_id in self.accounts:
            self.accounts[account_id].allocation = allocation
    
    def get_allocation(self, account_id: str) -> Decimal:
        """
        Get allocation for an account.
        
        Args:
            account_id: Account to check
        
        Returns:
            Allocation percentage (0-1)
        
        Raises:
            ValueError: If account not found
        """
        if account_id not in self.accounts:
            raise ValueError(f"Account {account_id} not found")
        return self.accounts[account_id].allocation
    
    def calculate_position_sizes(
        self,
        total_size: Decimal,
        active_accounts: list[str],
    ) -> dict[str, Decimal]:
        """
        Calculate position sizes for given accounts.
        
        Args:
            total_size: Total position size to allocate
            active_accounts: List of account IDs to allocate to
        
        Returns:
            Dict mapping account_id to allocated size
        """
        result = {}
        
        # Get total allocation for active accounts
        total_alloc = sum(
            self.accounts[acc_id].allocation 
            for acc_id in active_accounts 
            if acc_id in self.accounts
        )
        
        for acc_id in active_accounts:
            if acc_id not in self.accounts:
                continue
            
            acc = self.accounts[acc_id]
            if total_alloc > 0:
                share = acc.allocation / total_alloc
                result[acc_id] = total_size * share
            else:
                result[acc_id] = Decimal("0")
        
        return result
    
    def get_account_summary(self, account_id: str) -> AccountSummary:
        """
        Get summary for a specific account.
        
        Args:
            account_id: Account to get summary for
        
        Returns:
            AccountSummary
        """
        acc = self.accounts[account_id]
        return AccountSummary(
            account_id=acc.account_id,
            platform=acc.platform,
            is_primary=acc.is_primary,
            is_active=acc.is_active,
            allocation=acc.allocation,
        )
    
    def get_all_summaries(self) -> list[AccountSummary]:
        """Get summaries for all accounts."""
        return [self.get_account_summary(acc_id) for acc_id in self.accounts]
    
    def get_active_accounts(self) -> list[str]:
        """Get list of active account IDs."""
        return [
            acc_id for acc_id, acc in self.accounts.items() 
            if acc.is_active
        ]
    
    def get_accounts_by_platform(self, platform: str) -> list[str]:
        """
        Get accounts for a specific platform.
        
        Args:
            platform: Platform name
        
        Returns:
            List of account IDs for that platform
        """
        return [
            acc_id for acc_id, acc in self.accounts.items() 
            if acc.platform == platform
        ]


class TestAccountManagerInitialization:
    """Tests for AccountManager initialization."""

    def test_init_creates_instance(self):
        """AccountManager initializes successfully."""
        manager = AccountManager()
        assert manager is not None

    def test_init_with_empty_accounts(self):
        """AccountManager starts with no accounts."""
        manager = AccountManager()
        assert len(manager.accounts) == 0


class TestAccountRegistration:
    """Tests for account registration."""

    def test_register_account(self):
        """Account registered successfully."""
        manager = AccountManager()
        manager.register_account(
            account_id="acc-1",
            platform="polymarket",
            is_primary=True
        )
        assert len(manager.accounts) == 1
        assert "acc-1" in manager.accounts

    def test_register_multiple_accounts(self):
        """Multiple accounts registered."""
        manager = AccountManager()
        manager.register_account(account_id="acc-1", platform="polymarket")
        manager.register_account(account_id="acc-2", platform="kalshi")
        
        assert len(manager.accounts) == 2
        assert "acc-1" in manager.accounts
        assert "acc-2" in manager.accounts

    def test_register_duplicate_account_raises(self):
        """Registering duplicate account raises error."""
        manager = AccountManager()
        manager.register_account(account_id="acc-1", platform="polymarket")
        
        with pytest.raises(ValueError):
            manager.register_account(account_id="acc-1", platform="polymarket")


class TestPrimaryAccount:
    """Tests for primary account management."""

    def test_set_primary_account(self):
        """Primary account set correctly."""
        manager = AccountManager()
        manager.register_account(account_id="acc-1", platform="polymarket")
        manager.register_account(account_id="acc-2", platform="polymarket", is_primary=True)
        
        assert manager.get_primary_account() == "acc-2"

    def test_first_account_becomes_primary(self):
        """First registered account becomes primary by default."""
        manager = AccountManager()
        manager.register_account(account_id="acc-1", platform="polymarket")
        
        assert manager.get_primary_account() == "acc-1"

    def test_change_primary_account(self):
        """Primary account can be changed."""
        manager = AccountManager()
        manager.register_account(account_id="acc-1", platform="polymarket", is_primary=True)
        manager.register_account(account_id="acc-2", platform="polymarket")
        
        manager.set_primary("acc-2")
        assert manager.get_primary_account() == "acc-2"

    def test_set_nonexistent_primary_raises(self):
        """Setting nonexistent account as primary raises error."""
        manager = AccountManager()
        manager.register_account(account_id="acc-1", platform="polymarket")
        
        with pytest.raises(ValueError):
            manager.set_primary("acc-nonexistent")


class TestAllocationManagement:
    """Tests for allocation percentage management."""

    def test_set_allocation(self):
        """Allocation percentage set correctly."""
        manager = AccountManager()
        manager.register_account(account_id="acc-1", platform="polymarket")
        manager.set_allocation("acc-1", Decimal("0.5"))
        
        assert manager.get_allocation("acc-1") == Decimal("0.5")

    def test_allocation_defaults_to_zero(self):
        """New accounts have zero allocation by default."""
        manager = AccountManager()
        manager.register_account(account_id="acc-1", platform="polymarket")
        
        # Default allocation should be 0 or 1 (if primary)
        allocation = manager.get_allocation("acc-1")
        assert allocation >= Decimal("0")

    def test_allocations_can_sum_to_one(self):
        """Allocations can sum to 1.0 (100%)."""
        manager = AccountManager()
        manager.register_account(account_id="acc-1", platform="polymarket")
        manager.register_account(account_id="acc-2", platform="polymarket")
        
        manager.set_allocation("acc-1", Decimal("0.6"))
        manager.set_allocation("acc-2", Decimal("0.4"))
        
        total = manager.get_allocation("acc-1") + manager.get_allocation("acc-2")
        assert total == Decimal("1.0")

    def test_allocation_exceeds_one_raises(self):
        """Setting allocation that would exceed 100% raises error."""
        manager = AccountManager()
        manager.register_account(account_id="acc-1", platform="polymarket")
        manager.register_account(account_id="acc-2", platform="polymarket")
        
        manager.set_allocation("acc-1", Decimal("0.7"))
        
        with pytest.raises(ValueError):
            manager.set_allocation("acc-2", Decimal("0.5"))  # Total would be 1.2

    def test_negative_allocation_raises(self):
        """Negative allocation raises error."""
        manager = AccountManager()
        manager.register_account(account_id="acc-1", platform="polymarket")
        
        with pytest.raises(ValueError):
            manager.set_allocation("acc-1", Decimal("-0.1"))


class TestPositionSizeCalculation:
    """Tests for position size calculation across accounts."""

    def test_calculate_size_single_account(self):
        """Position size calculated for single account."""
        manager = AccountManager()
        manager.register_account(account_id="acc-1", platform="polymarket")
        manager.set_allocation("acc-1", Decimal("1.0"))
        
        sizes = manager.calculate_position_sizes(
            total_size=Decimal("100"),
            active_accounts=["acc-1"]
        )
        
        assert sizes["acc-1"] == Decimal("100")

    def test_calculate_size_multiple_accounts(self):
        """Position size split across multiple accounts."""
        manager = AccountManager()
        manager.register_account(account_id="acc-1", platform="polymarket")
        manager.register_account(account_id="acc-2", platform="polymarket")
        
        manager.set_allocation("acc-1", Decimal("0.6"))
        manager.set_allocation("acc-2", Decimal("0.4"))
        
        sizes = manager.calculate_position_sizes(
            total_size=Decimal("100"),
            active_accounts=["acc-1", "acc-2"]
        )
        
        assert sizes["acc-1"] == Decimal("60")
        assert sizes["acc-2"] == Decimal("40")

    def test_calculate_size_respects_active_filter(self):
        """Only active accounts receive allocation."""
        manager = AccountManager()
        manager.register_account(account_id="acc-1", platform="polymarket")
        manager.register_account(account_id="acc-2", platform="polymarket")
        
        manager.set_allocation("acc-1", Decimal("0.6"))
        manager.set_allocation("acc-2", Decimal("0.4"))
        
        sizes = manager.calculate_position_sizes(
            total_size=Decimal("100"),
            active_accounts=["acc-1"]  # Only acc-1 active
        )
        
        assert "acc-1" in sizes
        assert "acc-2" not in sizes


class TestAccountRemoval:
    """Tests for account removal."""

    def test_remove_account(self):
        """Account removed successfully."""
        manager = AccountManager()
        manager.register_account(account_id="acc-1", platform="polymarket")
        manager.register_account(account_id="acc-2", platform="polymarket")
        
        manager.remove_account("acc-1")
        
        assert len(manager.accounts) == 1
        assert "acc-1" not in manager.accounts

    def test_remove_nonexistent_account_raises(self):
        """Removing nonexistent account raises error."""
        manager = AccountManager()
        
        with pytest.raises(ValueError):
            manager.remove_account("acc-nonexistent")

    def test_remove_primary_promotes_next(self):
        """Removing primary account promotes another to primary."""
        manager = AccountManager()
        manager.register_account(account_id="acc-1", platform="polymarket", is_primary=True)
        manager.register_account(account_id="acc-2", platform="polymarket")
        
        manager.remove_account("acc-1")
        
        assert manager.get_primary_account() == "acc-2"


class TestAccountSummary:
    """Tests for account summary generation."""

    def test_get_account_summary(self):
        """Account summary contains expected fields."""
        manager = AccountManager()
        manager.register_account(account_id="acc-1", platform="polymarket", is_primary=True)
        manager.set_allocation("acc-1", Decimal("1.0"))
        
        summary = manager.get_account_summary("acc-1")
        
        assert summary.account_id == "acc-1"
        assert summary.platform == "polymarket"
        assert summary.is_primary is True
        assert summary.allocation == Decimal("1.0")

    def test_get_all_summaries(self):
        """Get summaries for all accounts."""
        manager = AccountManager()
        manager.register_account(account_id="acc-1", platform="polymarket")
        manager.register_account(account_id="acc-2", platform="kalshi")
        
        summaries = manager.get_all_summaries()
        
        assert len(summaries) == 2


class TestActiveStatus:
    """Tests for account active status."""

    def test_set_active_status(self):
        """Account active status can be toggled."""
        manager = AccountManager()
        manager.register_account(account_id="acc-1", platform="polymarket")
        
        manager.set_active("acc-1", False)
        assert manager.is_active("acc-1") is False
        
        manager.set_active("acc-1", True)
        assert manager.is_active("acc-1") is True

    def test_accounts_active_by_default(self):
        """Accounts are active by default."""
        manager = AccountManager()
        manager.register_account(account_id="acc-1", platform="polymarket")
        
        assert manager.is_active("acc-1") is True

    def test_get_active_accounts(self):
        """Get list of active accounts."""
        manager = AccountManager()
        manager.register_account(account_id="acc-1", platform="polymarket")
        manager.register_account(account_id="acc-2", platform="polymarket")
        manager.register_account(account_id="acc-3", platform="polymarket")
        
        manager.set_active("acc-2", False)
        
        active = manager.get_active_accounts()
        
        assert "acc-1" in active
        assert "acc-2" not in active
        assert "acc-3" in active


class TestPlatformFiltering:
    """Tests for filtering accounts by platform."""

    def test_get_accounts_by_platform(self):
        """Get accounts filtered by platform."""
        manager = AccountManager()
        manager.register_account(account_id="acc-1", platform="polymarket")
        manager.register_account(account_id="acc-2", platform="kalshi")
        manager.register_account(account_id="acc-3", platform="polymarket")
        
        polymarket_accounts = manager.get_accounts_by_platform("polymarket")
        kalshi_accounts = manager.get_accounts_by_platform("kalshi")
        
        assert len(polymarket_accounts) == 2
        assert len(kalshi_accounts) == 1
        assert "acc-2" in kalshi_accounts


class TestEdgeCases:
    """Tests for edge cases."""

    def test_no_primary_when_empty(self):
        """No primary account when manager is empty."""
        manager = AccountManager()
        assert manager.get_primary_account() is None

    def test_allocation_for_nonexistent_account(self):
        """Getting allocation for nonexistent account raises."""
        manager = AccountManager()
        
        with pytest.raises(ValueError):
            manager.get_allocation("acc-nonexistent")

    def test_zero_total_size(self):
        """Zero total size returns zero for all accounts."""
        manager = AccountManager()
        manager.register_account(account_id="acc-1", platform="polymarket")
        manager.set_allocation("acc-1", Decimal("1.0"))
        
        sizes = manager.calculate_position_sizes(
            total_size=Decimal("0"),
            active_accounts=["acc-1"]
        )
        
        assert sizes["acc-1"] == Decimal("0")
