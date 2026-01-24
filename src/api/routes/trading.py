"""
Trading routes for markets, positions, and manual orders.
"""

import uuid

from fastapi import APIRouter, HTTPException, status, Query

from src.api.deps import DbSession, OnboardedUser
from src.db.crud.tracked_market import TrackedMarketCRUD
from src.db.crud.position import PositionCRUD
from src.db.crud.activity_log import ActivityLogCRUD
from src.db.crud.polymarket_account import PolymarketAccountCRUD
from src.schemas.trading import (
    TrackedMarketResponse,
    PositionResponse,
    OrderRequest,
    OrderResponse,
)
from src.schemas.common import PaginatedResponse


router = APIRouter(prefix="/trading", tags=["Trading"])


@router.get("/markets", response_model=list[TrackedMarketResponse])
async def get_tracked_markets(
    db: DbSession,
    current_user: OnboardedUser,
    sport: str | None = None,
    live_only: bool = False
) -> list[TrackedMarketResponse]:
    """
    Returns tracked markets for the user.
    Optionally filtered by sport or live status.
    """
    if live_only:
        markets = await TrackedMarketCRUD.get_live_markets(db, current_user.id)
    else:
        markets = await TrackedMarketCRUD.get_active_for_user(db, current_user.id, sport)
    
    return [TrackedMarketResponse.model_validate(m) for m in markets]


@router.get("/markets/{market_id}", response_model=TrackedMarketResponse)
async def get_market_details(
    market_id: uuid.UUID,
    db: DbSession,
    current_user: OnboardedUser
) -> TrackedMarketResponse:
    """
    Returns details for a specific tracked market.
    """
    market = await TrackedMarketCRUD.get_by_id(db, market_id)
    
    if not market or market.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Market not found"
        )
    
    return TrackedMarketResponse.model_validate(market)


@router.get("/positions", response_model=list[PositionResponse])
async def get_positions(
    db: DbSession,
    current_user: OnboardedUser,
    status_filter: str | None = Query(None, alias="status"),
    limit: int = 50,
    offset: int = 0
) -> list[PositionResponse]:
    """
    Returns positions for the user with optional status filter.
    """
    positions = await PositionCRUD.get_all_for_user(
        db,
        current_user.id,
        status=status_filter,
        limit=limit,
        offset=offset
    )
    
    return [PositionResponse.model_validate(p) for p in positions]


@router.get("/positions/open", response_model=list[PositionResponse])
async def get_open_positions(
    db: DbSession,
    current_user: OnboardedUser
) -> list[PositionResponse]:
    """
    Returns all open positions for the user.
    """
    positions = await PositionCRUD.get_open_for_user(db, current_user.id)
    return [PositionResponse.model_validate(p) for p in positions]


@router.get("/positions/{position_id}", response_model=PositionResponse)
async def get_position_details(
    position_id: uuid.UUID,
    db: DbSession,
    current_user: OnboardedUser
) -> PositionResponse:
    """
    Returns details for a specific position including trades.
    """
    position = await PositionCRUD.get_with_trades(db, position_id)
    
    if not position or position.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Position not found"
        )
    
    return PositionResponse.model_validate(position)


@router.post("/order", response_model=OrderResponse)
async def place_manual_order(
    order_data: OrderRequest,
    db: DbSession,
    current_user: OnboardedUser
) -> OrderResponse:
    """
    Places a manual order on Polymarket.
    Intended for testing or manual intervention.
    """
    credentials = await PolymarketAccountCRUD.get_decrypted_credentials(db, current_user.id)
    
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Wallet not connected"
        )
    
    try:
        from src.services.polymarket_client import PolymarketClient
        
        client = PolymarketClient(
            private_key=credentials["private_key"],
            funder_address=credentials["funder_address"],
            api_key=credentials.get("api_key"),
            api_secret=credentials.get("api_secret"),
            passphrase=credentials.get("passphrase")
        )
        
        result = await client.place_order(
            token_id=order_data.token_id,
            side=order_data.side,
            price=float(order_data.price),
            size=float(order_data.size)
        )
        
        await ActivityLogCRUD.info(
            db,
            current_user.id,
            "TRADE",
            f"Manual order placed: {order_data.side} {order_data.size} @ {order_data.price}",
            details={"token_id": order_data.token_id, "order_id": result.get("id")}
        )
        
        return OrderResponse(
            success=True,
            order_id=result.get("id"),
            message="Order placed successfully",
            price=order_data.price,
            size=order_data.size
        )
        
    except Exception as e:
        await ActivityLogCRUD.error(
            db,
            current_user.id,
            "TRADE",
            f"Manual order failed: {str(e)}",
            details={"token_id": order_data.token_id}
        )
        
        return OrderResponse(
            success=False,
            message=f"Order failed: {str(e)}"
        )


@router.delete("/positions/{position_id}/close", response_model=PositionResponse)
async def close_position_manually(
    position_id: uuid.UUID,
    db: DbSession,
    current_user: OnboardedUser
) -> PositionResponse:
    """
    Manually closes a position at current market price.
    """
    position = await PositionCRUD.get_by_id(db, position_id)
    
    if not position or position.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Position not found"
        )
    
    if position.status != "open":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Position is not open"
        )
    
    credentials = await PolymarketAccountCRUD.get_decrypted_credentials(db, current_user.id)
    
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Wallet not connected"
        )
    
    try:
        from src.services.polymarket_client import PolymarketClient
        
        client = PolymarketClient(
            private_key=credentials["private_key"],
            funder_address=credentials["funder_address"],
            api_key=credentials.get("api_key"),
            api_secret=credentials.get("api_secret"),
            passphrase=credentials.get("passphrase")
        )
        
        exit_price = await client.get_midpoint_price(position.token_id)
        
        result = await client.place_order(
            token_id=position.token_id,
            side="SELL",
            price=exit_price,
            size=float(position.entry_size)
        )
        
        from decimal import Decimal
        exit_proceeds = Decimal(str(exit_price)) * position.entry_size
        
        closed_position = await PositionCRUD.close_position(
            db,
            position_id,
            exit_price=Decimal(str(exit_price)),
            exit_size=position.entry_size,
            exit_proceeds_usdc=exit_proceeds,
            exit_reason="manual_close",
            exit_order_id=result.get("id")
        )
        
        await ActivityLogCRUD.info(
            db,
            current_user.id,
            "TRADE",
            f"Position manually closed at {exit_price}",
            details={"position_id": str(position_id)}
        )
        
        return PositionResponse.model_validate(closed_position)
        
    except Exception as e:
        await ActivityLogCRUD.error(
            db,
            current_user.id,
            "TRADE",
            f"Failed to close position: {str(e)}",
            details={"position_id": str(position_id)}
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to close position: {str(e)}"
        )
