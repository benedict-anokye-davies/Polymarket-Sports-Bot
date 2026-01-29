"""
API routes for advanced trading features.
Includes endpoints for advanced orders, multi-account management, and portfolio rebalancing.
"""

import uuid
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from src.api.deps import DbSession, OnboardedUser
from src.db.crud.activity_log import ActivityLogCRUD


router = APIRouter(prefix="/api/v1/advanced", tags=["Advanced Trading"])


# =============================================================================
# Schemas
# =============================================================================

# --- Advanced Orders ---

class TrailingStopRequest(BaseModel):
    """Request to create a trailing stop order."""
    position_id: str
    token_id: str
    condition_id: str
    size: float
    trail_pct: float = Field(ge=0.01, le=0.50, description="Trail percentage (0.01-0.50)")


class StopLossRequest(BaseModel):
    """Request to create a stop-loss order."""
    position_id: str
    token_id: str
    condition_id: str
    size: float
    stop_price: float = Field(ge=0, le=1, description="Trigger price (0-1)")
    limit_price: Optional[float] = Field(None, ge=0, le=1)


class TakeProfitRequest(BaseModel):
    """Request to create a take-profit order."""
    position_id: str
    token_id: str
    condition_id: str
    size: float
    target_price: float = Field(ge=0, le=1, description="Target price (0-1)")
    limit_price: Optional[float] = Field(None, ge=0, le=1)


class BracketOrderRequest(BaseModel):
    """Request to create a bracket order (entry + TP + SL)."""
    token_id: str
    condition_id: str
    entry_side: str = Field(pattern="^(BUY|SELL)$")
    entry_price: float = Field(ge=0, le=1)
    entry_size: float = Field(gt=0)
    take_profit_price: float = Field(ge=0, le=1)
    stop_loss_price: float = Field(ge=0, le=1)


class AdvancedOrderResponse(BaseModel):
    """Response for advanced order operations."""
    success: bool
    order_id: str
    order_type: str
    message: str


class ActiveOrdersResponse(BaseModel):
    """Response listing active advanced orders."""
    trailing_stops: list[dict]
    stop_losses: list[dict]
    take_profits: list[dict]
    brackets: list[dict]
    total_count: int


# --- Multi-Account ---

class AddAccountRequest(BaseModel):
    """Request to add a new trading account."""
    account_name: str = Field(min_length=1, max_length=100)
    platform: str = Field(pattern="^(polymarket|kalshi)$")
    private_key: Optional[str] = None
    funder_address: Optional[str] = None
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    api_passphrase: Optional[str] = None
    allocation_pct: float = Field(ge=0, le=100, default=0)
    is_primary: bool = False


class UpdateAllocationRequest(BaseModel):
    """Request to update account allocations."""
    allocations: dict[str, float] = Field(description="account_id -> allocation_pct")


class ParallelOrderRequest(BaseModel):
    """Request to place an order across multiple accounts."""
    token_id: str
    condition_id: str
    side: str = Field(pattern="^(BUY|SELL)$")
    total_size: float = Field(gt=0)
    price: float = Field(ge=0, le=1)
    strategy: str = Field(default="percentage", pattern="^(percentage|equal|balance_weighted|single|round_robin)$")
    account_ids: Optional[list[str]] = None


class AccountSummaryResponse(BaseModel):
    """Response with account summary."""
    total_accounts: int
    active_accounts: int
    total_balance: float
    allocation_valid: bool
    accounts: list[dict]


# --- Portfolio Rebalancing ---

class SetTargetRequest(BaseModel):
    """Request to set a portfolio target allocation."""
    condition_id: str
    token_id: str
    target_pct: float = Field(ge=0, le=100)
    min_pct: Optional[float] = Field(None, ge=0, le=100)
    max_pct: Optional[float] = Field(None, ge=0, le=100)
    sport: Optional[str] = None
    market_name: Optional[str] = None


class SetTargetsRequest(BaseModel):
    """Request to set multiple targets at once."""
    targets: list[SetTargetRequest]


class ConfigureRebalancerRequest(BaseModel):
    """Request to configure rebalancing behavior."""
    strategy: str = Field(default="threshold", pattern="^(threshold|periodic|manual)$")
    drift_threshold: float = Field(ge=1, le=50, default=5.0)
    min_trade_value: float = Field(ge=1, default=10.0)
    rebalance_interval_hours: int = Field(ge=1, le=168, default=24)
    respect_risk_limits: bool = True
    tax_efficient: bool = True


class RebalanceResponse(BaseModel):
    """Response from rebalancing operation."""
    id: str
    status: str
    success_count: int
    failed_count: int
    total_traded_value: float
    recommendations_count: int
    value_before: float
    value_after: float


# =============================================================================
# Advanced Orders Endpoints
# =============================================================================

@router.post("/orders/trailing-stop", response_model=AdvancedOrderResponse)
async def create_trailing_stop(
    request: TrailingStopRequest,
    db: DbSession,
    current_user: OnboardedUser
):
    """
    Create a trailing stop order for an existing position.
    
    The order will track the highest price and trigger a sell
    when price drops by the specified trail percentage.
    """
    from src.services.advanced_orders import get_advanced_order_manager
    
    manager = get_advanced_order_manager()
    if not manager:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Advanced order manager not initialized"
        )
    
    try:
        order = await manager.create_trailing_stop(
            user_id=str(current_user.id),
            position_id=request.position_id,
            token_id=request.token_id,
            condition_id=request.condition_id,
            size=Decimal(str(request.size)),
            trail_pct=Decimal(str(request.trail_pct))
        )
        
        await ActivityLogCRUD.info(
            db,
            current_user.id,
            "ADVANCED_ORDER",
            f"Created trailing stop: {request.trail_pct*100:.1f}% trail",
            {"order_id": order.id, "position_id": request.position_id}
        )
        
        return AdvancedOrderResponse(
            success=True,
            order_id=order.id,
            order_type="trailing_stop",
            message=f"Trailing stop created with {request.trail_pct*100:.1f}% trail"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/orders/stop-loss", response_model=AdvancedOrderResponse)
async def create_stop_loss(
    request: StopLossRequest,
    db: DbSession,
    current_user: OnboardedUser
):
    """
    Create a stop-loss order for an existing position.
    
    Triggers a sell when price falls to or below the stop price.
    """
    from src.services.advanced_orders import get_advanced_order_manager
    
    manager = get_advanced_order_manager()
    if not manager:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Advanced order manager not initialized"
        )
    
    try:
        order = await manager.create_stop_loss(
            user_id=str(current_user.id),
            position_id=request.position_id,
            token_id=request.token_id,
            condition_id=request.condition_id,
            size=Decimal(str(request.size)),
            stop_price=Decimal(str(request.stop_price)),
            limit_price=Decimal(str(request.limit_price)) if request.limit_price else None
        )
        
        await ActivityLogCRUD.info(
            db,
            current_user.id,
            "ADVANCED_ORDER",
            f"Created stop-loss at ${request.stop_price:.4f}",
            {"order_id": order.id, "position_id": request.position_id}
        )
        
        return AdvancedOrderResponse(
            success=True,
            order_id=order.id,
            order_type="stop_loss",
            message=f"Stop-loss created at ${request.stop_price:.4f}"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/orders/take-profit", response_model=AdvancedOrderResponse)
async def create_take_profit(
    request: TakeProfitRequest,
    db: DbSession,
    current_user: OnboardedUser
):
    """
    Create a take-profit order for an existing position.
    
    Triggers a sell when price rises to or above the target price.
    """
    from src.services.advanced_orders import get_advanced_order_manager
    
    manager = get_advanced_order_manager()
    if not manager:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Advanced order manager not initialized"
        )
    
    try:
        order = await manager.create_take_profit(
            user_id=str(current_user.id),
            position_id=request.position_id,
            token_id=request.token_id,
            condition_id=request.condition_id,
            size=Decimal(str(request.size)),
            target_price=Decimal(str(request.target_price)),
            limit_price=Decimal(str(request.limit_price)) if request.limit_price else None
        )
        
        await ActivityLogCRUD.info(
            db,
            current_user.id,
            "ADVANCED_ORDER",
            f"Created take-profit at ${request.target_price:.4f}",
            {"order_id": order.id, "position_id": request.position_id}
        )
        
        return AdvancedOrderResponse(
            success=True,
            order_id=order.id,
            order_type="take_profit",
            message=f"Take-profit created at ${request.target_price:.4f}"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/orders/bracket", response_model=AdvancedOrderResponse)
async def create_bracket_order(
    request: BracketOrderRequest,
    db: DbSession,
    current_user: OnboardedUser
):
    """
    Create a bracket order (entry + take-profit + stop-loss).
    
    Places an entry order immediately. When filled, activates both
    TP and SL orders. When either TP or SL fills, the other is cancelled.
    """
    from src.services.advanced_orders import get_advanced_order_manager
    
    manager = get_advanced_order_manager()
    if not manager:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Advanced order manager not initialized"
        )
    
    try:
        order = await manager.create_bracket_order(
            user_id=str(current_user.id),
            token_id=request.token_id,
            condition_id=request.condition_id,
            entry_side=request.entry_side,
            entry_price=Decimal(str(request.entry_price)),
            entry_size=Decimal(str(request.entry_size)),
            take_profit_price=Decimal(str(request.take_profit_price)),
            stop_loss_price=Decimal(str(request.stop_loss_price))
        )
        
        await ActivityLogCRUD.info(
            db,
            current_user.id,
            "ADVANCED_ORDER",
            f"Created bracket order: entry ${request.entry_price:.4f}, TP ${request.take_profit_price:.4f}, SL ${request.stop_loss_price:.4f}",
            {"order_id": order.id}
        )
        
        return AdvancedOrderResponse(
            success=True,
            order_id=order.id,
            order_type="bracket",
            message=f"Bracket order created"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/orders/active", response_model=ActiveOrdersResponse)
async def get_active_orders(
    db: DbSession,
    current_user: OnboardedUser
):
    """Get all active advanced orders for the current user."""
    from src.services.advanced_orders import get_advanced_order_manager
    
    manager = get_advanced_order_manager()
    if not manager:
        return ActiveOrdersResponse(
            trailing_stops=[],
            stop_losses=[],
            take_profits=[],
            brackets=[],
            total_count=0
        )
    
    orders = manager.get_active_orders(str(current_user.id))
    
    def serialize_order(order) -> dict:
        return {
            "id": order.id,
            "token_id": order.token_id,
            "condition_id": order.condition_id,
            "side": order.side,
            "size": float(order.size),
            "status": order.status.value,
            "created_at": order.created_at.isoformat()
        }
    
    return ActiveOrdersResponse(
        trailing_stops=[serialize_order(o) for o in orders["trailing_stops"]],
        stop_losses=[serialize_order(o) for o in orders["stop_losses"]],
        take_profits=[serialize_order(o) for o in orders["take_profits"]],
        brackets=[{
            "id": o.id,
            "token_id": o.token_id,
            "entry_price": float(o.entry_price),
            "take_profit_price": float(o.take_profit_price),
            "stop_loss_price": float(o.stop_loss_price),
            "status": o.status.value
        } for o in orders["brackets"]],
        total_count=sum(len(v) for v in orders.values())
    )


@router.delete("/orders/{order_id}")
async def cancel_advanced_order(
    order_id: str,
    db: DbSession,
    current_user: OnboardedUser
):
    """Cancel an advanced order by ID."""
    from src.services.advanced_orders import get_advanced_order_manager
    
    manager = get_advanced_order_manager()
    if not manager:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Advanced order manager not initialized"
        )
    
    success = await manager.cancel_order(order_id)
    
    if success:
        await ActivityLogCRUD.info(
            db,
            current_user.id,
            "ADVANCED_ORDER",
            f"Cancelled advanced order",
            {"order_id": order_id}
        )
        return {"success": True, "message": "Order cancelled"}
    
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Order not found"
    )


# =============================================================================
# Multi-Account Endpoints
# =============================================================================

@router.post("/accounts")
async def add_account(
    request: AddAccountRequest,
    db: DbSession,
    current_user: OnboardedUser
):
    """Add a new trading account."""
    from src.services.account_manager import AccountManager
    
    manager = AccountManager(db, current_user.id)
    
    try:
        # Use the existing add method if available, otherwise create directly
        from src.models import PolymarketAccount
        from src.core.encryption import encrypt_value
        from sqlalchemy import select, and_
        
        # If setting as primary, unset existing primary
        if request.is_primary:
            stmt = select(PolymarketAccount).where(
                and_(
                    PolymarketAccount.user_id == current_user.id,
                    PolymarketAccount.is_primary == True
                )
            )
            result = await db.execute(stmt)
            for acc in result.scalars().all():
                acc.is_primary = False
        
        account = PolymarketAccount(
            user_id=current_user.id,
            account_name=request.account_name,
            platform=request.platform,
            private_key_encrypted=encrypt_value(request.private_key) if request.private_key else None,
            funder_address=request.funder_address,
            api_key_encrypted=encrypt_value(request.api_key) if request.api_key else None,
            api_secret_encrypted=encrypt_value(request.api_secret) if request.api_secret else None,
            api_passphrase_encrypted=encrypt_value(request.api_passphrase) if request.api_passphrase else None,
            allocation_pct=Decimal(str(request.allocation_pct)),
            is_primary=request.is_primary,
            is_active=True
        )
        
        db.add(account)
        await db.commit()
        await db.refresh(account)
        
        await ActivityLogCRUD.info(
            db,
            current_user.id,
            "ACCOUNT",
            f"Added trading account: {request.account_name}",
            {"account_id": str(account.id), "platform": request.platform}
        )
        
        return {
            "success": True,
            "account_id": str(account.id),
            "message": f"Account '{request.account_name}' added successfully"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/accounts/summary", response_model=AccountSummaryResponse)
async def get_account_summary(
    db: DbSession,
    current_user: OnboardedUser
):
    """Get summary of all trading accounts."""
    from src.services.account_manager import AccountManager
    
    manager = AccountManager(db, current_user.id)
    summary = await manager.get_account_summary()
    
    return AccountSummaryResponse(
        total_accounts=summary["total_accounts"],
        active_accounts=len([a for a in summary["accounts"] if a.get("is_active")]),
        total_balance=summary["total_balance"],
        allocation_valid=summary["allocation_valid"],
        accounts=summary["accounts"]
    )


@router.put("/accounts/allocations")
async def update_allocations(
    request: UpdateAllocationRequest,
    db: DbSession,
    current_user: OnboardedUser
):
    """Update allocation percentages for accounts."""
    from src.services.account_manager import AccountManager
    
    # Validate allocations sum to 100%
    total = sum(request.allocations.values())
    if abs(total - 100) > 0.01:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Allocations must sum to 100%, got {total}%"
        )
    
    manager = AccountManager(db, current_user.id)
    
    for account_id, pct in request.allocations.items():
        await manager.set_account_allocation(
            uuid.UUID(account_id),
            pct
        )
    
    await ActivityLogCRUD.info(
        db,
        current_user.id,
        "ACCOUNT",
        "Updated account allocations",
        {"allocations": request.allocations}
    )
    
    return {"success": True, "message": "Allocations updated"}


@router.post("/accounts/parallel-order")
async def place_parallel_order(
    request: ParallelOrderRequest,
    db: DbSession,
    current_user: OnboardedUser
):
    """Place an order distributed across multiple accounts."""
    from src.services.account_manager import AccountManager, AllocationStrategy
    
    manager = AccountManager(db, current_user.id)
    
    try:
        strategy = AllocationStrategy(request.strategy)
        account_ids = [uuid.UUID(aid) for aid in request.account_ids] if request.account_ids else None
        
        result = await manager.execute_parallel_order(
            token_id=request.token_id,
            side=request.side,
            total_size=request.total_size,
            price=request.price,
            strategy=strategy,
            account_ids=account_ids
        )
        
        await ActivityLogCRUD.info(
            db,
            current_user.id,
            "TRADE",
            f"Parallel order: {result.status}",
            {
                "order_id": result.order_id,
                "total_size": result.total_size,
                "filled_size": result.filled_size,
                "strategy": request.strategy
            }
        )
        
        return {
            "success": result.status in ["filled", "partial"],
            "order_id": result.order_id,
            "status": result.status,
            "total_size": result.total_size,
            "filled_size": result.filled_size,
            "fill_rate": result.fill_rate,
            "account_results": result.account_results
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/accounts/health")
async def get_account_health(
    db: DbSession,
    current_user: OnboardedUser
):
    """Get health status for all accounts."""
    from src.services.account_manager import AccountManager
    
    manager = AccountManager(db, current_user.id)
    return manager.get_account_health()


# =============================================================================
# Portfolio Rebalancing Endpoints
# =============================================================================

@router.post("/portfolio/targets")
async def set_portfolio_target(
    request: SetTargetRequest,
    db: DbSession,
    current_user: OnboardedUser
):
    """Set a target allocation for a market."""
    from src.services.portfolio_rebalancer import get_portfolio_rebalancer
    
    rebalancer = get_portfolio_rebalancer()
    if not rebalancer:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Portfolio rebalancer not initialized"
        )
    
    target = rebalancer.set_target(
        user_id=str(current_user.id),
        condition_id=request.condition_id,
        token_id=request.token_id,
        target_pct=Decimal(str(request.target_pct)),
        min_pct=Decimal(str(request.min_pct)) if request.min_pct else None,
        max_pct=Decimal(str(request.max_pct)) if request.max_pct else None,
        sport=request.sport,
        market_name=request.market_name
    )
    
    await ActivityLogCRUD.info(
        db,
        current_user.id,
        "PORTFOLIO",
        f"Set target allocation: {request.target_pct}%",
        {"condition_id": request.condition_id}
    )
    
    return {
        "success": True,
        "condition_id": target.condition_id,
        "target_pct": float(target.target_pct),
        "min_pct": float(target.min_pct) if target.min_pct else None,
        "max_pct": float(target.max_pct) if target.max_pct else None
    }


@router.post("/portfolio/targets/bulk")
async def set_portfolio_targets_bulk(
    request: SetTargetsRequest,
    db: DbSession,
    current_user: OnboardedUser
):
    """Set multiple target allocations at once."""
    from src.services.portfolio_rebalancer import get_portfolio_rebalancer
    
    rebalancer = get_portfolio_rebalancer()
    if not rebalancer:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Portfolio rebalancer not initialized"
        )
    
    targets = rebalancer.set_targets_from_dict(
        user_id=str(current_user.id),
        targets={
            t.condition_id: {
                "token_id": t.token_id,
                "target_pct": t.target_pct,
                "min_pct": t.min_pct,
                "max_pct": t.max_pct,
                "sport": t.sport,
                "market_name": t.market_name
            }
            for t in request.targets
        }
    )
    
    await ActivityLogCRUD.info(
        db,
        current_user.id,
        "PORTFOLIO",
        f"Set {len(targets)} target allocations",
        {}
    )
    
    return {
        "success": True,
        "targets_set": len(targets)
    }


@router.get("/portfolio/targets")
async def get_portfolio_targets(
    db: DbSession,
    current_user: OnboardedUser
):
    """Get all target allocations for the current user."""
    from src.services.portfolio_rebalancer import get_portfolio_rebalancer
    
    rebalancer = get_portfolio_rebalancer()
    if not rebalancer:
        return {"targets": []}
    
    targets = rebalancer.get_targets(str(current_user.id))
    
    return {
        "targets": [
            {
                "condition_id": t.condition_id,
                "token_id": t.token_id,
                "target_pct": float(t.target_pct),
                "min_pct": float(t.min_pct) if t.min_pct else None,
                "max_pct": float(t.max_pct) if t.max_pct else None,
                "sport": t.sport,
                "market_name": t.market_name
            }
            for t in targets.values()
        ]
    }


@router.delete("/portfolio/targets/{condition_id}")
async def remove_portfolio_target(
    condition_id: str,
    db: DbSession,
    current_user: OnboardedUser
):
    """Remove a target allocation."""
    from src.services.portfolio_rebalancer import get_portfolio_rebalancer
    
    rebalancer = get_portfolio_rebalancer()
    if not rebalancer:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Portfolio rebalancer not initialized"
        )
    
    success = rebalancer.remove_target(str(current_user.id), condition_id)
    
    if success:
        await ActivityLogCRUD.info(
            db,
            current_user.id,
            "PORTFOLIO",
            "Removed target allocation",
            {"condition_id": condition_id}
        )
        return {"success": True}
    
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Target not found"
    )


@router.put("/portfolio/config")
async def configure_rebalancer(
    request: ConfigureRebalancerRequest,
    db: DbSession,
    current_user: OnboardedUser
):
    """Configure rebalancing behavior."""
    from src.services.portfolio_rebalancer import get_portfolio_rebalancer, RebalanceStrategy
    
    rebalancer = get_portfolio_rebalancer()
    if not rebalancer:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Portfolio rebalancer not initialized"
        )
    
    rebalancer.configure(
        user_id=str(current_user.id),
        strategy=RebalanceStrategy(request.strategy),
        drift_threshold=Decimal(str(request.drift_threshold)),
        min_trade_value=Decimal(str(request.min_trade_value)),
        rebalance_interval_hours=request.rebalance_interval_hours,
        respect_risk_limits=request.respect_risk_limits,
        tax_efficient=request.tax_efficient
    )
    
    await ActivityLogCRUD.info(
        db,
        current_user.id,
        "PORTFOLIO",
        f"Configured rebalancer: {request.strategy}",
        {"drift_threshold": request.drift_threshold}
    )
    
    return {"success": True, "message": "Rebalancer configured"}


@router.get("/portfolio/config")
async def get_rebalancer_config(
    db: DbSession,
    current_user: OnboardedUser
):
    """Get current rebalancing configuration."""
    from src.services.portfolio_rebalancer import get_portfolio_rebalancer
    
    rebalancer = get_portfolio_rebalancer()
    if not rebalancer:
        return {"config": None}
    
    config = rebalancer.get_config(str(current_user.id))
    
    return {
        "config": {
            "strategy": config.get("strategy", "threshold"),
            "drift_threshold": float(config.get("drift_threshold", 5)),
            "min_trade_value": float(config.get("min_trade_value", 10)),
            "rebalance_interval_hours": config.get("rebalance_interval_hours", 24),
            "respect_risk_limits": config.get("respect_risk_limits", True),
            "tax_efficient": config.get("tax_efficient", True)
        }
    }


@router.get("/portfolio/analysis")
async def analyze_portfolio(
    db: DbSession,
    current_user: OnboardedUser
):
    """Analyze portfolio against target allocations."""
    from src.services.portfolio_rebalancer import get_portfolio_rebalancer
    
    rebalancer = get_portfolio_rebalancer()
    if not rebalancer:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Portfolio rebalancer not initialized"
        )
    
    analysis = await rebalancer.analyze_portfolio(str(current_user.id))
    return analysis


@router.post("/portfolio/rebalance", response_model=RebalanceResponse)
async def rebalance_portfolio(
    dry_run: bool = False,
    db: DbSession = None,
    current_user: OnboardedUser = None
):
    """
    Execute portfolio rebalancing.
    
    Set dry_run=true to preview actions without executing.
    """
    from src.services.portfolio_rebalancer import get_portfolio_rebalancer
    
    rebalancer = get_portfolio_rebalancer()
    if not rebalancer:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Portfolio rebalancer not initialized"
        )
    
    result = await rebalancer.rebalance(
        user_id=str(current_user.id),
        dry_run=dry_run
    )
    
    if not dry_run:
        await ActivityLogCRUD.info(
            db,
            current_user.id,
            "PORTFOLIO",
            f"Rebalanced portfolio: {result.success_count} trades",
            {"result_id": result.id, "status": result.status}
        )
    
    return RebalanceResponse(
        id=result.id,
        status=result.status,
        success_count=result.success_count,
        failed_count=result.failed_count,
        total_traded_value=float(result.total_traded_value),
        recommendations_count=len(result.recommendations),
        value_before=float(result.total_value_before),
        value_after=float(result.total_value_after)
    )


@router.get("/portfolio/history")
async def get_rebalance_history(
    limit: int = 10,
    db: DbSession = None,
    current_user: OnboardedUser = None
):
    """Get rebalancing history."""
    from src.services.portfolio_rebalancer import get_portfolio_rebalancer
    
    rebalancer = get_portfolio_rebalancer()
    if not rebalancer:
        return {"history": []}
    
    history = rebalancer.get_rebalance_history(limit=limit)
    return {"history": history}
