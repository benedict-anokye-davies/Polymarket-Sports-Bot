"""
Trading routes for markets, positions, orders, and game selection.
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
    GameSelectionRequest,
    BulkGameSelectionRequest,
    SportGameSelectionRequest,
    GameSelectionResponse,
    BulkGameSelectionResponse,
    AvailableGameResponse,
    GameListResponse,
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


# =============================================================================
# Game Selection Endpoints
# =============================================================================

@router.get("/games", response_model=GameListResponse)
async def get_all_games(
    db: DbSession,
    current_user: OnboardedUser,
    sport: str | None = None
) -> GameListResponse:
    """
    Returns all games organized by selection status.
    Shows both selected (active for trading) and available (can be selected) games.
    """
    selected = await TrackedMarketCRUD.get_selected_for_user(db, current_user.id, sport)
    available = await TrackedMarketCRUD.get_unselected_for_user(db, current_user.id, sport)
    
    return GameListResponse(
        selected=[AvailableGameResponse.model_validate(m) for m in selected],
        available=[AvailableGameResponse.model_validate(m) for m in available],
        total_selected=len(selected),
        total_available=len(available)
    )


@router.get("/games/selected", response_model=list[AvailableGameResponse])
async def get_selected_games(
    db: DbSession,
    current_user: OnboardedUser,
    sport: str | None = None
) -> list[AvailableGameResponse]:
    """
    Returns games the user has selected for trading.
    These are the games the bot will actively monitor and trade on.
    """
    markets = await TrackedMarketCRUD.get_selected_for_user(db, current_user.id, sport)
    return [AvailableGameResponse.model_validate(m) for m in markets]


@router.get("/games/available", response_model=list[AvailableGameResponse])
async def get_available_games(
    db: DbSession,
    current_user: OnboardedUser,
    sport: str | None = None
) -> list[AvailableGameResponse]:
    """
    Returns games available for selection (discovered but not selected).
    User can browse these and choose which ones to trade on.
    """
    markets = await TrackedMarketCRUD.get_unselected_for_user(db, current_user.id, sport)
    return [AvailableGameResponse.model_validate(m) for m in markets]


@router.post("/games/{market_id}/select", response_model=GameSelectionResponse)
async def select_game(
    market_id: uuid.UUID,
    db: DbSession,
    current_user: OnboardedUser
) -> GameSelectionResponse:
    """
    Selects a specific game for trading.
    The bot will monitor and trade on this game based on configured thresholds.
    """
    market = await TrackedMarketCRUD.select_game(db, current_user.id, market_id)
    
    if not market:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Game not found or not owned by user"
        )
    
    await ActivityLogCRUD.info(
        db,
        current_user.id,
        "GAME_SELECTION",
        f"Selected game for trading: {market.question or market.condition_id}",
        details={"market_id": str(market_id), "sport": market.sport}
    )
    
    return GameSelectionResponse(
        success=True,
        message="Game selected for trading",
        market_id=market.id,
        condition_id=market.condition_id,
        is_user_selected=True
    )


@router.delete("/games/{market_id}/select", response_model=GameSelectionResponse)
async def unselect_game(
    market_id: uuid.UUID,
    db: DbSession,
    current_user: OnboardedUser
) -> GameSelectionResponse:
    """
    Removes a game from trading selection.
    The bot will no longer monitor or trade on this game.
    """
    market = await TrackedMarketCRUD.unselect_game(db, current_user.id, market_id)
    
    if not market:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Game not found or not owned by user"
        )
    
    await ActivityLogCRUD.info(
        db,
        current_user.id,
        "GAME_SELECTION",
        f"Unselected game from trading: {market.question or market.condition_id}",
        details={"market_id": str(market_id), "sport": market.sport}
    )
    
    return GameSelectionResponse(
        success=True,
        message="Game removed from trading selection",
        market_id=market.id,
        condition_id=market.condition_id,
        is_user_selected=False
    )


@router.post("/games/select/bulk", response_model=BulkGameSelectionResponse)
async def bulk_select_games(
    request: BulkGameSelectionRequest,
    db: DbSession,
    current_user: OnboardedUser
) -> BulkGameSelectionResponse:
    """
    Selects multiple games for trading at once.
    """
    count = await TrackedMarketCRUD.bulk_select_games(
        db, current_user.id, request.market_ids
    )
    
    await ActivityLogCRUD.info(
        db,
        current_user.id,
        "GAME_SELECTION",
        f"Bulk selected {count} games for trading",
        details={"market_ids": [str(mid) for mid in request.market_ids]}
    )
    
    return BulkGameSelectionResponse(
        success=True,
        message=f"Selected {count} games for trading",
        updated_count=count
    )


@router.delete("/games/select/bulk", response_model=BulkGameSelectionResponse)
async def bulk_unselect_games(
    request: BulkGameSelectionRequest,
    db: DbSession,
    current_user: OnboardedUser
) -> BulkGameSelectionResponse:
    """
    Removes multiple games from trading selection at once.
    """
    count = await TrackedMarketCRUD.bulk_unselect_games(
        db, current_user.id, request.market_ids
    )
    
    await ActivityLogCRUD.info(
        db,
        current_user.id,
        "GAME_SELECTION",
        f"Bulk unselected {count} games from trading",
        details={"market_ids": [str(mid) for mid in request.market_ids]}
    )
    
    return BulkGameSelectionResponse(
        success=True,
        message=f"Removed {count} games from trading selection",
        updated_count=count
    )


@router.post("/games/select/sport/{sport}", response_model=BulkGameSelectionResponse)
async def select_all_games_for_sport(
    sport: str,
    db: DbSession,
    current_user: OnboardedUser
) -> BulkGameSelectionResponse:
    """
    Selects all available games for a specific sport.
    Useful for enabling all NBA games at once, for example.
    """
    count = await TrackedMarketCRUD.select_all_by_sport(
        db, current_user.id, sport.lower()
    )
    
    await ActivityLogCRUD.info(
        db,
        current_user.id,
        "GAME_SELECTION",
        f"Selected all {sport.upper()} games for trading ({count} games)",
        details={"sport": sport}
    )
    
    return BulkGameSelectionResponse(
        success=True,
        message=f"Selected all {sport.upper()} games ({count} total)",
        updated_count=count
    )


@router.delete("/games/select/sport/{sport}", response_model=BulkGameSelectionResponse)
async def unselect_all_games_for_sport(
    sport: str,
    db: DbSession,
    current_user: OnboardedUser
) -> BulkGameSelectionResponse:
    """
    Removes all games for a specific sport from trading selection.
    """
    count = await TrackedMarketCRUD.unselect_all_by_sport(
        db, current_user.id, sport.lower()
    )
    
    await ActivityLogCRUD.info(
        db,
        current_user.id,
        "GAME_SELECTION",
        f"Unselected all {sport.upper()} games from trading ({count} games)",
        details={"sport": sport}
    )
    
    return BulkGameSelectionResponse(
        success=True,
        message=f"Removed all {sport.upper()} games from selection ({count} total)",
        updated_count=count
    )


@router.post("/markets/{condition_id}/track", response_model=GameSelectionResponse)
async def track_market_by_condition(
    condition_id: str,
    db: DbSession,
    current_user: OnboardedUser
) -> GameSelectionResponse:
    """
    Selects a market for trading using its condition_id.
    Legacy endpoint for backwards compatibility with frontend.
    """
    market = await TrackedMarketCRUD.select_by_condition_id(
        db, current_user.id, condition_id
    )
    
    if not market:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Market not found"
        )
    
    return GameSelectionResponse(
        success=True,
        message="Market tracking enabled",
        market_id=market.id,
        condition_id=market.condition_id,
        is_user_selected=True
    )


@router.delete("/markets/{condition_id}/track", response_model=GameSelectionResponse)
async def untrack_market_by_condition(
    condition_id: str,
    db: DbSession,
    current_user: OnboardedUser
) -> GameSelectionResponse:
    """
    Unselects a market from trading using its condition_id.
    Legacy endpoint for backwards compatibility with frontend.
    """
    market = await TrackedMarketCRUD.unselect_by_condition_id(
        db, current_user.id, condition_id
    )
    
    if not market:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Market not found"
        )
    

@router.get("/orders", response_model=list[dict])
async def get_open_orders(
    db: DbSession,
    current_user: OnboardedUser
) -> list[dict]:
    """
    Returns all open (resting) orders from the exchange.
    """
    credentials = await PolymarketAccountCRUD.get_decrypted_credentials(db, current_user.id)
    
    if not credentials:
        return []
    
    try:
        from src.services.polymarket_client import PolymarketClient
        
        client = PolymarketClient(
            private_key=credentials["private_key"],
            funder_address=credentials["funder_address"],
            api_key=credentials.get("api_key"),
            api_secret=credentials.get("api_secret"),
            passphrase=credentials.get("passphrase")
        )
        
        orders = await client.get_open_orders()
        return orders
        
    except Exception as e:
        # Log error but return empty list to avoid breaking UI
        await ActivityLogCRUD.error(
            db,
            current_user.id,
            "TRADING",
            f"Failed to fetch open orders: {str(e)}"
        )
        return []


@router.delete("/orders/{order_id}", response_model=dict)
async def cancel_order(
    order_id: str,
    db: DbSession,
    current_user: OnboardedUser
) -> dict:
    """
    Cancels a specific open order.
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
        
        result = await client.cancel_order(order_id)
        
        await ActivityLogCRUD.info(
            db,
            current_user.id,
            "TRADING",
            f"Cancelled order {order_id}",
            details={"order_id": order_id}
        )
        
        return {"success": True, "message": "Order cancelled", "id": order_id}
        
    except Exception as e:
        await ActivityLogCRUD.error(
            db,
            current_user.id,
            "TRADING",
            f"Failed to cancel order: {str(e)}",
            details={"order_id": order_id}
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel order: {str(e)}"
        )
