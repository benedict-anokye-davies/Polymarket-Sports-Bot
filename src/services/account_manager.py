"""
Account Manager service - handles multi-account allocation and routing.
Manages multiple Polymarket/Kalshi accounts with configurable allocation.
"""

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from src.services.polymarket_client import PolymarketClient
    from src.services.kalshi_client import KalshiClient

logger = logging.getLogger(__name__)


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


class AccountManager:
    """
    Manages multiple trading accounts with allocation strategies.
    
    Responsibilities:
    - Load and validate account configurations
    - Allocate trades across accounts by percentage
    - Route orders to correct account
    - Track per-account balances and positions
    """
    
    def __init__(self, db: AsyncSession, user_id: UUID):
        self.db = db
        self.user_id = user_id
        self._accounts_cache: list = []
        self._clients_cache: dict = {}
    
    async def get_active_accounts(self) -> list:
        """
        Get all active trading accounts for user.
        
        Returns:
            List of PolymarketAccount models
        """
        from src.models import PolymarketAccount
        
        stmt = (
            select(PolymarketAccount)
            .where(PolymarketAccount.user_id == self.user_id)
            .where(PolymarketAccount.is_active == True)
            .order_by(PolymarketAccount.is_primary.desc())
        )
        
        result = await self.db.execute(stmt)
        accounts = result.scalars().all()
        self._accounts_cache = list(accounts)
        
        return self._accounts_cache
    
    async def get_primary_account(self):
        """Get the primary trading account."""
        from src.models import PolymarketAccount
        
        stmt = (
            select(PolymarketAccount)
            .where(PolymarketAccount.user_id == self.user_id)
            .where(PolymarketAccount.is_primary == True)
            .where(PolymarketAccount.is_active == True)
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
    
    async def get_client_for_account(
        self,
        account_id: UUID,
    ) -> Optional["PolymarketClient"]:
        """
        Get or create a Polymarket client for specific account.
        
        Args:
            account_id: UUID of the account
        
        Returns:
            Configured PolymarketClient or None
        """
        from src.models import PolymarketAccount
        from src.services.polymarket_client import PolymarketClient
        from src.core.encryption import decrypt_credential
        from src.config import settings
        
        if account_id in self._clients_cache:
            return self._clients_cache[account_id]
        
        stmt = select(PolymarketAccount).where(PolymarketAccount.id == account_id)
        result = await self.db.execute(stmt)
        account = result.scalar_one_or_none()
        
        if not account:
            logger.error(f"Account {account_id} not found")
            return None
        
        try:
            private_key = decrypt_credential(
                account.encrypted_private_key,
                settings.SECRET_KEY
            )
            
            api_key = None
            api_secret = None
            api_passphrase = None
            
            if account.encrypted_api_key:
                api_key = decrypt_credential(account.encrypted_api_key, settings.SECRET_KEY)
            if account.encrypted_api_secret:
                api_secret = decrypt_credential(account.encrypted_api_secret, settings.SECRET_KEY)
            if account.encrypted_api_passphrase:
                api_passphrase = decrypt_credential(account.encrypted_api_passphrase, settings.SECRET_KEY)
            
            client = PolymarketClient(
                private_key=private_key,
                funder_address=account.funder_address,
                api_key=api_key,
                api_secret=api_secret,
                api_passphrase=api_passphrase,
            )
            
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
                    balances.append({
                        "account_id": str(account.id),
                        "account_name": account.account_name or "Primary",
                        "balance": float(balance.get("balance", 0)) if isinstance(balance, dict) else float(balance or 0),
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
        from src.models import PolymarketAccount
        
        if allocation_pct < 0 or allocation_pct > 100:
            raise ValueError("Allocation must be between 0 and 100")
        
        stmt = (
            update(PolymarketAccount)
            .where(PolymarketAccount.id == account_id)
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
        
        Args:
            account_id: Account to make primary
        
        Returns:
            True if successful
        """
        from src.models import PolymarketAccount
        
        clear_stmt = (
            update(PolymarketAccount)
            .where(PolymarketAccount.user_id == self.user_id)
            .values(is_primary=False)
        )
        await self.db.execute(clear_stmt)
        
        set_stmt = (
            update(PolymarketAccount)
            .where(PolymarketAccount.id == account_id)
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
        from src.models import PolymarketAccount
        
        stmt = (
            update(PolymarketAccount)
            .where(PolymarketAccount.id == account_id)
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
