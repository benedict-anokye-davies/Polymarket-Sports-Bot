"""
Accounts API endpoints - multi-account management.
"""

from decimal import Decimal
from typing import Optional, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db, get_current_user
from src.models import User, PolymarketAccount
from src.services.account_manager import AccountManager
from src.core.encryption import encrypt_credential, decrypt_credential
from src.config import settings

router = APIRouter(prefix="/accounts", tags=["accounts"])


class AccountResponse(BaseModel):
    """Account response schema."""
    id: str
    account_name: str
    platform: str = "polymarket"
    is_primary: bool
    is_active: bool
    allocation_pct: float
    funder_address: Optional[str]
    balance: Optional[float] = None
    error: Optional[str] = None


class AccountSummaryResponse(BaseModel):
    """Account summary response."""
    total_balance: float
    total_accounts: int
    accounts: list[AccountResponse]
    allocation_valid: bool
    total_allocation_pct: float


class CreateAccountRequest(BaseModel):
    """Request to create a new trading account."""
    account_name: str = Field(..., min_length=1, max_length=50)
    platform: Literal["polymarket", "kalshi"] = "polymarket"
    private_key: Optional[str] = Field(None, min_length=64)
    funder_address: Optional[str] = Field(None, min_length=42, max_length=42)
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    api_passphrase: Optional[str] = None
    allocation_pct: float = Field(100.0, ge=0, le=100)
    is_primary: bool = False


class UpdateAccountRequest(BaseModel):
    """Request to update account settings."""
    account_name: Optional[str] = Field(None, min_length=1, max_length=50)
    allocation_pct: Optional[float] = Field(None, ge=0, le=100)
    is_active: Optional[bool] = None


class SetPrimaryRequest(BaseModel):
    """Request to set primary account."""
    account_id: UUID


class AllocationUpdateRequest(BaseModel):
    """Request to update allocation percentages."""
    allocations: list[dict]


@router.get("/summary", response_model=AccountSummaryResponse)
async def get_account_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get summary of all trading accounts.
    
    Returns total balance, per-account balances, and allocation status.
    """
    manager = AccountManager(db, current_user.id)
    summary = await manager.get_account_summary()
    
    return AccountSummaryResponse(
        total_balance=summary["total_balance"],
        total_accounts=summary["total_accounts"],
        accounts=[
            AccountResponse(
                id=acc["id"],
                account_name=acc["name"],
                platform=acc.get("platform", "polymarket"),
                is_primary=acc["is_primary"],
                is_active=acc["is_active"],
                allocation_pct=acc["allocation_pct"],
                funder_address=None,
                balance=acc.get("balance"),
                error=acc.get("error"),
            )
            for acc in summary["accounts"]
        ],
        allocation_valid=summary["allocation_valid"],
        total_allocation_pct=summary["total_allocation_pct"],
    )


@router.get("/", response_model=list[AccountResponse])
async def list_accounts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all trading accounts for the current user.
    """
    stmt = (
        select(PolymarketAccount)
        .where(PolymarketAccount.user_id == current_user.id)
        .order_by(PolymarketAccount.is_primary.desc())
    )
    
    result = await db.execute(stmt)
    accounts = result.scalars().all()
    
    return [
        AccountResponse(
            id=str(acc.id),
            account_name=acc.account_name or "Primary",
            platform=acc.platform or "polymarket",
            is_primary=acc.is_primary or False,
            is_active=acc.is_active if acc.is_active is not None else True,
            allocation_pct=float(acc.allocation_pct or 100),
            funder_address=acc.funder_address,
        )
        for acc in accounts
    ]


@router.post("/", response_model=AccountResponse)
async def create_account(
    request: CreateAccountRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new trading account.
    
    Encrypts private key and API credentials before storage.
    Supports both Polymarket (requires private_key/funder_address)
    and Kalshi (requires api_key/api_secret) platforms.
    """
    # Validate platform-specific required fields
    if request.platform == "polymarket":
        if not request.private_key or not request.funder_address:
            raise HTTPException(
                status_code=400,
                detail="Polymarket accounts require private_key and funder_address"
            )
    elif request.platform == "kalshi":
        if not request.api_key or not request.api_secret:
            raise HTTPException(
                status_code=400,
                detail="Kalshi accounts require api_key and api_secret"
            )
    
    encrypted_key = None
    if request.private_key:
        encrypted_key = encrypt_credential(request.private_key)
    
    encrypted_api_key = None
    encrypted_api_secret = None
    encrypted_api_passphrase = None
    
    if request.api_key:
        encrypted_api_key = encrypt_credential(request.api_key)
    if request.api_secret:
        encrypted_api_secret = encrypt_credential(request.api_secret)
    if request.api_passphrase:
        encrypted_api_passphrase = encrypt_credential(request.api_passphrase)
    
    # Use savepoint to ensure atomic primary flag update + account creation
    async with db.begin_nested():
        if request.is_primary:
            # Clear primary flag on existing accounts
            from sqlalchemy import update
            clear_stmt = (
                update(PolymarketAccount)
                .where(PolymarketAccount.user_id == current_user.id)
                .values(is_primary=False)
            )
            await db.execute(clear_stmt)
        
        account = PolymarketAccount(
            user_id=current_user.id,
            account_name=request.account_name,
            platform=request.platform,
            private_key_encrypted=encrypted_key,
            funder_address=request.funder_address,
            api_key_encrypted=encrypted_api_key,
            api_secret_encrypted=encrypted_api_secret,
            api_passphrase_encrypted=encrypted_api_passphrase,
            allocation_pct=Decimal(str(request.allocation_pct)),
            is_primary=request.is_primary,
            is_active=True,
        )
        
        db.add(account)
    
    await db.commit()
    await db.refresh(account)
    
    return AccountResponse(
        id=str(account.id),
        account_name=account.account_name,
        platform=account.platform or "polymarket",
        is_primary=account.is_primary or False,
        is_active=account.is_active if account.is_active is not None else True,
        allocation_pct=float(account.allocation_pct or 100),
        funder_address=account.funder_address,
    )


@router.patch("/{account_id}", response_model=AccountResponse)
async def update_account(
    account_id: UUID,
    request: UpdateAccountRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update account settings (name, allocation, active status).
    """
    stmt = (
        select(PolymarketAccount)
        .where(PolymarketAccount.id == account_id)
        .where(PolymarketAccount.user_id == current_user.id)
    )
    
    result = await db.execute(stmt)
    account = result.scalar_one_or_none()
    
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    if request.account_name is not None:
        account.account_name = request.account_name
    if request.allocation_pct is not None:
        account.allocation_pct = Decimal(str(request.allocation_pct))
    if request.is_active is not None:
        account.is_active = request.is_active
    
    await db.commit()
    await db.refresh(account)
    
    return AccountResponse(
        id=str(account.id),
        account_name=account.account_name or "Primary",
        platform=account.platform or "polymarket",
        is_primary=account.is_primary or False,
        is_active=account.is_active if account.is_active is not None else True,
        allocation_pct=float(account.allocation_pct or 100),
        funder_address=account.funder_address,
    )


@router.post("/{account_id}/set-primary")
async def set_primary_account(
    account_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Set an account as the primary trading account.
    """
    manager = AccountManager(db, current_user.id)
    success = await manager.set_primary_account(account_id)
    
    if not success:
        raise HTTPException(status_code=400, detail="Failed to set primary account")
    
    return {"message": "Primary account updated"}


@router.post("/allocations")
async def update_allocations(
    request: AllocationUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update allocation percentages for multiple accounts atomically.
    
    All allocations are updated in a single transaction to prevent
    partial updates if any allocation fails.
    
    Expects list of {account_id, allocation_pct} objects.
    """
    total_pct = sum(a.get("allocation_pct", 0) for a in request.allocations)
    if abs(total_pct - 100) > 0.01:
        raise HTTPException(
            status_code=400,
            detail=f"Allocations must sum to 100% (got {total_pct}%)"
        )
    
    from sqlalchemy import update
    
    # Update all allocations atomically within a savepoint
    async with db.begin_nested():
        for allocation in request.allocations:
            account_id = UUID(allocation["account_id"])
            pct = allocation["allocation_pct"]
            
            if pct < 0 or pct > 100:
                raise HTTPException(
                    status_code=400,
                    detail=f"Allocation must be between 0 and 100 (got {pct})"
                )
            
            stmt = (
                update(PolymarketAccount)
                .where(PolymarketAccount.id == account_id)
                .where(PolymarketAccount.user_id == current_user.id)
                .values(allocation_pct=Decimal(str(pct)))
            )
            await db.execute(stmt)
    
    await db.commit()
    
    return {"message": "Allocations updated successfully"}


@router.delete("/{account_id}")
async def delete_account(
    account_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a trading account.
    
    Cannot delete the primary account if it's the only one.
    """
    stmt = (
        select(PolymarketAccount)
        .where(PolymarketAccount.id == account_id)
        .where(PolymarketAccount.user_id == current_user.id)
    )
    
    result = await db.execute(stmt)
    account = result.scalar_one_or_none()
    
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    count_stmt = (
        select(PolymarketAccount)
        .where(PolymarketAccount.user_id == current_user.id)
    )
    count_result = await db.execute(count_stmt)
    total_accounts = len(count_result.scalars().all())
    
    if account.is_primary and total_accounts == 1:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete the only account"
        )
    
    await db.delete(account)
    await db.commit()
    
    return {"message": "Account deleted successfully"}


@router.get("/{account_id}/balance")
async def get_account_balance(
    account_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get current balance for a specific account.
    """
    manager = AccountManager(db, current_user.id)
    client = await manager.get_client_for_account(account_id)
    
    if not client:
        raise HTTPException(status_code=404, detail="Account not found or client error")
    
    try:
        balance = await client.get_balance()
        return {
            "account_id": str(account_id),
            "balance": float(balance.get("balance", 0)) if isinstance(balance, dict) else float(balance or 0),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
