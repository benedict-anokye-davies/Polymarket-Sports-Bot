"""
Account Manager service - handles multi-account allocation and routing.
Manages multiple Polymarket/Kalshi accounts with configurable allocation.

Features:
- Multiple trading accounts per user
- Configurable allocation percentages
- Parallel order execution across accounts
- Account health monitoring with automatic failover
- Balance aggregation across accounts
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, Optional, Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from src.services.kalshi_client import KalshiClient

logger = logging.getLogger(__name__)


class AllocationStrategy(str, Enum):
    """Strategies for distributing trades across accounts."""
    PERCENTAGE = "percentage"  # Based on allocation_pct
    EQUAL = "equal"  # Split equally across active accounts
    BALANCE_WEIGHTED = "balance_weighted"  # Proportional to account balance
    SINGLE = "single"  # Use single account (primary or specified)
    ROUND_ROBIN = "round_robin"  # Rotate through accounts


@dataclass
class AccountAllocation:
    """Allocation result for a single account."""
    account_id: UUID
    account_name: str
    allocation_pct: float
    allocated_contracts: int
    allocated_usd: float


@dataclass
class AllocationResult:
    """Complete allocation result across all accounts."""
    total_contracts: int
    total_usd: float
    allocations: list[AccountAllocation]
    primary_account_id: Optional[UUID]


@dataclass
class AccountHealth:
    """Health status for a trading account."""
    account_id: str
    is_healthy: bool
    consecutive_errors: int = 0
    last_error: str | None = None
    last_success_at: datetime | None = None
    last_error_at: datetime | None = None


@dataclass
class ParallelOrderResult:
    """Result of executing orders across multiple accounts."""
    order_id: str = field(default_factory=lambda: str(UUID(int=0)))
    total_size: float = 0
    filled_size: float = 0
    account_results: dict[str, dict] = field(default_factory=dict)
    status: str = "pending"  # pending, partial, filled, failed
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    @property
    def fill_rate(self) -> float:
        """Percentage of order filled."""
        if self.total_size == 0:
            return 0
        return self.filled_size / self.total_size


class AccountManager:
    """
    Manages multiple trading accounts with allocation strategies.
    
    Responsibilities:
    - Load and validate account configurations
    - Allocate trades across accounts by percentage
    - Route orders to correct account
    - Track per-account balances and positions
    - Execute orders in parallel across multiple accounts
    - Monitor account health and handle failover
    """
    
    MAX_CONSECUTIVE_ERRORS = 3  # Disable account after this many errors
    
    def __init__(self, db: AsyncSession, user_id: UUID):
        self.db = db
        self.user_id = user_id
        self._accounts_cache: list = []
        self._clients_cache: dict = {}
        self._health_status: dict[str, AccountHealth] = {}
        self._round_robin_index: int = 0
    
    async def get_client_for_account(self, account_id: UUID):
        """
        Get or create a KalshiClient for the specified account.
        
        Args:
            account_id: Account ID to get client for
            
        Returns:
            KalshiClient instance
        """
        # Check cache first
        if account_id in self._clients_cache:
            return self._clients_cache[account_id]
            
        # Get credentials from DB
        from src.db.crud.account import AccountCRUD
        credentials = await AccountCRUD.get_decrypted_credentials(self.db, account_id)
        
        if not credentials:
            return None
            
        # Create client
        from src.services.kalshi_client import KalshiClient
        
        # Check for API key (Kalshi)
        if "api_key" in credentials:
             # Kalshi
             client = KalshiClient(
                api_key=credentials["api_key"],
                private_key_pem=credentials.get("private_key") or credentials.get("api_secret")
             )
        else:
            # Fallback or Polymarket (not supported but safe to return None)
            return None
        
        # Cache it
        self._clients_cache[account_id] = client
        return client

    async def get_active_accounts(self) -> list:
        """
        Get all active trading accounts for user.
        
        Returns:
            List of PolymarketAccount models
        """
        from src.models import TradingAccount
        
        stmt = (
            select(TradingAccount)
            .where(TradingAccount.user_id == self.user_id)
            .where(TradingAccount.is_active == True)
            .order_by(TradingAccount.is_primary.desc())
        )
        
        result = await self.db.execute(stmt)
        accounts = result.scalars().all()
        self._accounts_cache = list(accounts)
        
        return self._accounts_cache
    
    async def get_primary_account(self):
        """Get the primary trading account."""
        from src.models import TradingAccount
        
        stmt = (
            select(TradingAccount)
            .where(TradingAccount.user_id == self.user_id)
            .where(TradingAccount.is_primary == True)
            .where(TradingAccount.is_active == True)
        )
        
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def allocate_trade(
        self,
        total_contracts: int,
        total_usd: Decimal,
        market_id: str,
    ) -> AllocationResult:
        """
        Allocate a trade across active accounts by configured percentage.
        
        Args:
            total_contracts: Total contracts to allocate
            total_usd: Total USD value of trade
            market_id: Market being traded (for logging)
        
        Returns:
            AllocationResult with per-account allocations
        """
        accounts = await self.get_active_accounts()
        
        if not accounts:
            logger.warning(f"No active accounts for user {self.user_id}")
            return AllocationResult(
                total_contracts=0,
                total_usd=0,
                allocations=[],
                primary_account_id=None,
            )
        
        total_allocation_pct = sum(
            float(acc.allocation_pct or 100)
            for acc in accounts
        )
        
        allocations = []
        remaining_contracts = total_contracts
        primary_id = None
        
        for i, account in enumerate(accounts):
            if account.is_primary:
                primary_id = account.id
            
            raw_pct = float(account.allocation_pct or 100)
            normalized_pct = raw_pct / total_allocation_pct if total_allocation_pct > 0 else 0
            
            if i == len(accounts) - 1:
                allocated_contracts = remaining_contracts
            else:
                allocated_contracts = int(total_contracts * normalized_pct)
                remaining_contracts -= allocated_contracts
            
            allocated_usd = float(total_usd) * normalized_pct
            
            allocations.append(AccountAllocation(
                account_id=account.id,
                account_name=account.account_name or f"Account {i+1}",
                allocation_pct=normalized_pct * 100,
                allocated_contracts=allocated_contracts,
                allocated_usd=round(allocated_usd, 2),
            ))
        
        logger.info(
            f"Allocated {total_contracts} contracts across {len(accounts)} accounts "
            f"for market {market_id}"
        )
        
        return AllocationResult(
            total_contracts=total_contracts,
            total_usd=float(total_usd),
            allocations=allocations,
            primary_account_id=primary_id,
        )
    
        """
        Get or create a trading client for specific account.
        Supports Kalshi platform.
        
        Args:
            account_id: UUID of the account
        
        Returns:
            Configured KalshiClient or None
        """
        from src.models import TradingAccount
        from src.services.kalshi_client import KalshiClient
        from src.core.encryption import decrypt_credential
        
        if account_id in self._clients_cache:
            return self._clients_cache[account_id]
        
        stmt = select(TradingAccount).where(TradingAccount.id == account_id)
        result = await self.db.execute(stmt)
        account = result.scalar_one_or_none()
        
        if not account:
            logger.error(f"Account {account_id} not found")
            return None
        
        try:
            platform = account.platform or "kalshi"
            environment = getattr(account, 'environment', 'production')
            
            if platform != "kalshi":
                 logger.error(f"Platform {platform} is not supported.")
                 return None

            # Create Kalshi client
            api_key = decrypt_credential(account.api_key_encrypted) if account.api_key_encrypted else None
            api_secret = decrypt_credential(account.api_secret_encrypted) if account.api_secret_encrypted else None
            
            if not api_key or not api_secret:
                logger.error(f"No API credentials found for Kalshi account {account_id}")
                return None
            
            client = KalshiClient(
                api_key=api_key,
                private_key_pem=api_secret,
            )
            logger.debug(f"Created KalshiClient for account {account_id} ({environment})")
            
            self._clients_cache[account_id] = client
            return client
            
        except Exception as e:
            logger.error(f"Failed to create client for account {account_id}: {e}")
            return None
    
    async def get_all_balances(self) -> list[dict]:
        """
        Get balances for all active accounts.
        
        Returns:
            List of dicts with account_id, name, balance
        """
        accounts = await self.get_active_accounts()
        balances = []
        
        for account in accounts:
            try:
                client = await self.get_client_for_account(account.id)
                if client:
                    balance = await client.get_balance()
                    # Handle different key names: Polymarket uses 'balance', Kalshi uses 'available_balance'
                    balance_value = 0
                    if isinstance(balance, dict):
                        balance_value = balance.get("balance") or balance.get("available_balance") or balance.get("total_balance") or 0
                    else:
                        balance_value = balance or 0
                    balances.append({
                        "account_id": str(account.id),
                        "account_name": account.account_name or "Primary",
                        "balance": float(balance_value),
                        "allocation_pct": float(account.allocation_pct or 100),
                        "is_primary": account.is_primary,
                    })
            except Exception as e:
                logger.error(f"Failed to get balance for account {account.id}: {e}")
                balances.append({
                    "account_id": str(account.id),
                    "account_name": account.account_name or "Primary",
                    "balance": None,
                    "error": str(e),
                })
        
        return balances
    
    async def set_account_allocation(
        self,
        account_id: UUID,
        allocation_pct: float,
    ) -> bool:
        """
        Update allocation percentage for an account.
        
        Args:
            account_id: Account to update
            allocation_pct: New allocation percentage (0-100)
        
        Returns:
            True if successful
        """
        from src.models import TradingAccount
        
        if allocation_pct < 0 or allocation_pct > 100:
            raise ValueError("Allocation must be between 0 and 100")
        
        stmt = (
            update(TradingAccount)
            .where(TradingAccount.id == account_id)
            .values(allocation_pct=Decimal(str(allocation_pct)))
        )
        
        await self.db.execute(stmt)
        await self.db.commit()
        
        if account_id in self._clients_cache:
            del self._clients_cache[account_id]
        
        return True
    
    async def set_primary_account(self, account_id: UUID) -> bool:
        """
        Set an account as the primary account.
        
        Uses a savepoint to ensure atomicity - both the clearing of
        existing primary flags and setting the new primary happen together.
        
        Args:
            account_id: Account to make primary
        
        Returns:
            True if successful
        """
        from src.models import TradingAccount
        
        # Use savepoint for atomic primary account switch
        async with self.db.begin_nested():
            # Clear all primary flags
            clear_stmt = (
                update(TradingAccount)
                .where(TradingAccount.user_id == self.user_id)
                .values(is_primary=False)
            )
            await self.db.execute(clear_stmt)
            
            # Set new primary
            set_stmt = (
                update(TradingAccount)
                .where(TradingAccount.id == account_id)
                .where(TradingAccount.user_id == self.user_id)
                .values(is_primary=True)
            )
            await self.db.execute(set_stmt)
        
        await self.db.commit()
        
        self._accounts_cache = []
        
        return True
    
    async def activate_account(self, account_id: UUID, active: bool) -> bool:
        """
        Activate or deactivate an account.
        
        Args:
            account_id: Account to update
            active: Whether account should be active
        
        Returns:
            True if successful
        """
        from src.models import TradingAccount
        
        stmt = (
            update(TradingAccount)
            .where(TradingAccount.id == account_id)
            .values(is_active=active)
        )
        
        await self.db.execute(stmt)
        await self.db.commit()
        
        self._accounts_cache = []
        if account_id in self._clients_cache:
            del self._clients_cache[account_id]
        
        return True
    
    async def get_account_summary(self) -> dict:
        """
        Get summary of all accounts with balances and allocations.
        
        Returns:
            dict with total_balance, accounts list, allocation_valid
        """
        accounts = await self.get_active_accounts()
        balances = await self.get_all_balances()
        
        balance_map = {b["account_id"]: b for b in balances}
        
        total_balance = sum(
            b.get("balance", 0) or 0
            for b in balances
            if b.get("balance") is not None
        )
        
        total_allocation = sum(
            float(acc.allocation_pct or 0)
            for acc in accounts
        )
        
        account_details = []
        for acc in accounts:
            balance_info = balance_map.get(str(acc.id), {})
            account_details.append({
                "id": str(acc.id),
                "name": acc.account_name or "Primary",
                "platform": acc.platform or "polymarket",
                "environment": getattr(acc, 'environment', 'production'),  # Kalshi demo/production
                "is_primary": acc.is_primary,
                "is_active": acc.is_active,
                "allocation_pct": float(acc.allocation_pct or 0),
                "balance": balance_info.get("balance"),
                "error": balance_info.get("error"),
            })
        
        return {
            "total_balance": round(total_balance, 2),
            "total_accounts": len(accounts),
            "accounts": account_details,
            "allocation_valid": abs(total_allocation - 100) < 0.01,
            "total_allocation_pct": round(total_allocation, 2),
        }
    
    # -------------------------------------------------------------------------
    # Parallel Order Execution
    # -------------------------------------------------------------------------
    
    async def execute_parallel_order(
        self,
        token_id: str,
        side: str,
        total_size: float,
        price: float,
        strategy: AllocationStrategy = AllocationStrategy.PERCENTAGE,
        account_ids: list[UUID] | None = None
    ) -> ParallelOrderResult:
        """
        Execute an order across multiple accounts in parallel.
        
        Args:
            token_id: Token to trade
            side: "BUY" or "SELL"
            total_size: Total size to trade
            price: Limit price
            strategy: Allocation strategy
            account_ids: Specific accounts to use (None = all active)
        
        Returns:
            ParallelOrderResult with execution details
        """
        import uuid as uuid_module
        
        accounts = await self.get_active_accounts()
        
        # Filter by specified account_ids if provided
        if account_ids:
            accounts = [a for a in accounts if a.id in account_ids]
        
        # Filter out unhealthy accounts
        healthy_accounts = []
        for acc in accounts:
            health = self._health_status.get(str(acc.id))
            if health and health.consecutive_errors >= self.MAX_CONSECUTIVE_ERRORS:
                logger.warning(f"Skipping unhealthy account {acc.id}")
                continue
            healthy_accounts.append(acc)
        
        if not healthy_accounts:
            logger.error("No healthy accounts available for order")
            return ParallelOrderResult(
                order_id=str(uuid_module.uuid4()),
                total_size=total_size,
                status="failed"
            )
        
        # Calculate allocations based on strategy
        allocations = self._calculate_allocations(
            healthy_accounts, total_size, strategy
        )
        
        result = ParallelOrderResult(
            order_id=str(uuid_module.uuid4()),
            total_size=total_size,
            status="pending"
        )
        
        # Execute orders in parallel
        tasks = []
        for account, size in allocations:
            if size <= 0:
                continue
            result.account_results[str(account.id)] = {
                "account_name": account.account_name or "Primary",
                "size": size,
                "status": "pending"
            }
            tasks.append(
                self._execute_single_order(account, token_id, side, size, price, result)
            )
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        
        # Calculate totals and status
        filled = sum(
            r.get("filled_size", 0) 
            for r in result.account_results.values()
        )
        result.filled_size = filled
        
        success_count = sum(
            1 for r in result.account_results.values() 
            if r.get("status") == "filled"
        )
        
        if success_count == len(result.account_results):
            result.status = "filled"
        elif success_count > 0:
            result.status = "partial"
        else:
            result.status = "failed"
        
        logger.info(
            f"Parallel order {result.order_id[:8]}...: "
            f"{success_count}/{len(result.account_results)} accounts filled, "
            f"total {result.filled_size}/{result.total_size}"
        )
        
        return result
    
    def _calculate_allocations(
        self,
        accounts: list,
        total_size: float,
        strategy: AllocationStrategy
    ) -> list[tuple[Any, float]]:
        """Calculate size allocation for each account based on strategy."""
        if not accounts:
            return []
        
        allocations = []
        
        if strategy == AllocationStrategy.PERCENTAGE:
            total_pct = sum(float(a.allocation_pct or 100) for a in accounts)
            for acc in accounts:
                pct = float(acc.allocation_pct or 100) / total_pct if total_pct > 0 else 1/len(accounts)
                allocations.append((acc, total_size * pct))
        
        elif strategy == AllocationStrategy.EQUAL:
            per_account = total_size / len(accounts)
            for acc in accounts:
                allocations.append((acc, per_account))
        
        elif strategy == AllocationStrategy.BALANCE_WEIGHTED:
            # Get cached balances
            total_balance = sum(
                float(a.last_balance_usdc or 0) for a in accounts
            )
            for acc in accounts:
                if total_balance > 0:
                    weight = float(acc.last_balance_usdc or 0) / total_balance
                else:
                    weight = 1 / len(accounts)
                allocations.append((acc, total_size * weight))
        
        elif strategy == AllocationStrategy.SINGLE:
            # Use primary account
            primary = next((a for a in accounts if a.is_primary), accounts[0])
            allocations.append((primary, total_size))
        
        elif strategy == AllocationStrategy.ROUND_ROBIN:
            idx = self._round_robin_index % len(accounts)
            allocations.append((accounts[idx], total_size))
            self._round_robin_index += 1
        
        return allocations
    
    async def _execute_single_order(
        self,
        account,
        token_id: str,
        side: str,
        size: float,
        price: float,
        result: ParallelOrderResult
    ) -> None:
        """Execute order on a single account and update result."""
        account_id = str(account.id)
        
        try:
            client = await self.get_client_for_account(account.id)
            if not client:
                result.account_results[account_id].update({
                    "status": "failed",
                    "error": "Failed to get client"
                })
                self._record_error(account_id, "Failed to get client")
                return
            
            order_result = await client.place_order(
                token_id=token_id,
                side=side,
                price=price,
                size=size
            )
            
            order_id = order_result.get("id") or order_result.get("orderID")
            
            result.account_results[account_id].update({
                "status": "filled",
                "order_id": order_id,
                "filled_size": size,
                "filled_price": price
            })
            
            self._record_success(account_id)
            
            logger.info(
                f"Account {account_id[:8]}... order filled: "
                f"{side} {size} @ {price}"
            )
            
        except Exception as e:
            error_msg = str(e)
            result.account_results[account_id].update({
                "status": "failed",
                "error": error_msg
            })
            self._record_error(account_id, error_msg)
            logger.error(f"Account {account_id[:8]}... order failed: {e}")
    
    def _record_success(self, account_id: str) -> None:
        """Record successful operation for an account."""
        if account_id not in self._health_status:
            self._health_status[account_id] = AccountHealth(
                account_id=account_id,
                is_healthy=True
            )
        
        health = self._health_status[account_id]
        health.consecutive_errors = 0
        health.is_healthy = True
        health.last_success_at = datetime.now(timezone.utc)
    
    def _record_error(self, account_id: str, error: str) -> None:
        """Record error for an account."""
        if account_id not in self._health_status:
            self._health_status[account_id] = AccountHealth(
                account_id=account_id,
                is_healthy=True
            )
        
        health = self._health_status[account_id]
        health.consecutive_errors += 1
        health.last_error = error
        health.last_error_at = datetime.now(timezone.utc)
        
        if health.consecutive_errors >= self.MAX_CONSECUTIVE_ERRORS:
            health.is_healthy = False
            logger.warning(
                f"Account {account_id[:8]}... marked unhealthy after "
                f"{health.consecutive_errors} consecutive errors"
            )
    
    def get_account_health(self, account_id: str | None = None) -> dict:
        """
        Get health status for one or all accounts.
        
        Args:
            account_id: Specific account (None = all accounts)
        
        Returns:
            Dict with health information
        """
        if account_id:
            health = self._health_status.get(account_id)
            if health:
                return {
                    "account_id": health.account_id,
                    "is_healthy": health.is_healthy,
                    "consecutive_errors": health.consecutive_errors,
                    "last_error": health.last_error,
                    "last_success_at": health.last_success_at.isoformat() if health.last_success_at else None,
                    "last_error_at": health.last_error_at.isoformat() if health.last_error_at else None
                }
            return {"account_id": account_id, "is_healthy": True, "consecutive_errors": 0}
        
        return {
            account_id: self.get_account_health(account_id)
            for account_id in self._health_status.keys()
        }
    
    def reset_account_health(self, account_id: str) -> None:
        """Reset health status for an account (manual recovery)."""
        if account_id in self._health_status:
            health = self._health_status[account_id]
            health.consecutive_errors = 0
            health.is_healthy = True
            health.last_error = None
            logger.info(f"Account {account_id[:8]}... health reset")

