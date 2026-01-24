"""
Trading schemas for markets, positions, and orders.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field


class TrackedMarketResponse(BaseModel):
    """
    Schema for tracked market data in API responses.
    """
    id: uuid.UUID
    condition_id: str
    token_id_yes: str
    token_id_no: str
    question: str | None
    sport: str
    home_team: str | None
    away_team: str | None
    home_abbrev: str | None
    away_abbrev: str | None
    game_start_time: datetime | None
    baseline_price_yes: Decimal | None
    baseline_price_no: Decimal | None
    current_price_yes: Decimal | None
    current_price_no: Decimal | None
    is_live: bool
    is_finished: bool
    current_period: int | None
    time_remaining_seconds: int | None
    home_score: int | None
    away_score: int | None
    match_confidence: Decimal | None
    last_updated_at: datetime
    
    model_config = {"from_attributes": True}


class TradeResponse(BaseModel):
    """
    Schema for individual trade records in API responses.
    """
    id: uuid.UUID
    polymarket_order_id: str | None
    action: str
    side: str
    price: Decimal
    size: Decimal
    total_usdc: Decimal
    fee_usdc: Decimal
    status: str
    executed_at: datetime | None
    created_at: datetime
    
    model_config = {"from_attributes": True}


class PositionResponse(BaseModel):
    """
    Schema for position data in API responses.
    """
    id: uuid.UUID
    condition_id: str
    token_id: str
    side: str
    team: str | None
    entry_price: Decimal
    entry_size: Decimal
    entry_cost_usdc: Decimal
    entry_reason: str | None
    exit_price: Decimal | None
    exit_size: Decimal | None
    exit_proceeds_usdc: Decimal | None
    exit_reason: str | None
    realized_pnl_usdc: Decimal | None
    status: str
    opened_at: datetime
    closed_at: datetime | None
    trades: list[TradeResponse] = []
    
    model_config = {"from_attributes": True}


class OrderRequest(BaseModel):
    """
    Schema for manually placing an order.
    """
    token_id: str
    side: str = Field(..., pattern="^(BUY|SELL)$")
    price: Decimal = Field(..., ge=0, le=1)
    size: Decimal = Field(..., gt=0)


class OrderResponse(BaseModel):
    """
    Schema for order placement response.
    """
    success: bool
    order_id: str | None = None
    message: str
    price: Decimal | None = None
    size: Decimal | None = None


class MarketCreate(BaseModel):
    """
    Schema for creating a tracked market entry.
    Used by bot_runner when discovering new markets.
    """
    user_id: int
    condition_id: str
    token_id: str
    question: str
    sport: str
    espn_event_id: str
    home_team: str
    away_team: str
    baseline_price: float
    is_active: bool = True


class PositionCreate(BaseModel):
    """
    Schema for creating a new position.
    Used by bot_runner when entering trades.
    """
    user_id: int
    market_id: str  # condition_id
    token_id: str
    side: str
    entry_price: float
    size: float
    status: str = "open"
