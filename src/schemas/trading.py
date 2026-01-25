"""
Trading schemas for markets, positions, orders, and game selection.
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
    is_user_selected: bool = True
    auto_discovered: bool = True
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


# ============================================================================
# Game Selection Schemas
# ============================================================================

class GameSelectionRequest(BaseModel):
    """
    Schema for selecting/unselecting a single game.
    """
    market_id: uuid.UUID | None = Field(None, description="TrackedMarket UUID")
    condition_id: str | None = Field(None, description="Polymarket condition_id")
    
    def __init__(self, **data):
        super().__init__(**data)
        if not self.market_id and not self.condition_id:
            raise ValueError("Either market_id or condition_id must be provided")


class BulkGameSelectionRequest(BaseModel):
    """
    Schema for selecting/unselecting multiple games at once.
    """
    market_ids: list[uuid.UUID] = Field(
        ...,
        min_length=1,
        description="List of TrackedMarket UUIDs to select/unselect"
    )


class SportGameSelectionRequest(BaseModel):
    """
    Schema for selecting/unselecting all games for a sport.
    """
    sport: str = Field(..., description="Sport identifier (nba, nfl, mlb, etc.)")


class GameSelectionResponse(BaseModel):
    """
    Schema for game selection operation response.
    """
    success: bool
    message: str
    market_id: uuid.UUID | None = None
    condition_id: str | None = None
    is_user_selected: bool | None = None


class BulkGameSelectionResponse(BaseModel):
    """
    Schema for bulk game selection operation response.
    """
    success: bool
    message: str
    updated_count: int


class AvailableGameResponse(BaseModel):
    """
    Schema for an available game discovered from Polymarket.
    Shows games that can be selected for trading.
    """
    id: uuid.UUID
    condition_id: str
    question: str | None
    sport: str
    home_team: str | None
    away_team: str | None
    home_abbrev: str | None
    away_abbrev: str | None
    game_start_time: datetime | None
    current_price_yes: Decimal | None
    current_price_no: Decimal | None
    is_live: bool
    is_finished: bool
    is_user_selected: bool
    match_confidence: Decimal | None
    
    model_config = {"from_attributes": True}


class GameListResponse(BaseModel):
    """
    Schema for list of games with selection status.
    """
    selected: list[AvailableGameResponse]
    available: list[AvailableGameResponse]
    total_selected: int
    total_available: int


# ============================================================================
# Market Configuration Schemas (Per-Market Overrides)
# ============================================================================

class MarketConfigBase(BaseModel):
    """
    Base schema with common market configuration fields.
    All fields are optional as they represent overrides.
    """
    # Entry conditions
    entry_threshold_drop: Decimal | None = Field(
        None,
        ge=0,
        le=1,
        description="Required price drop percentage to enter (0.15 = 15%)"
    )
    entry_threshold_absolute: Decimal | None = Field(
        None,
        ge=0,
        le=1,
        description="Enter if price drops below this value"
    )
    min_time_remaining_seconds: int | None = Field(
        None,
        ge=0,
        description="Minimum seconds remaining in period to enter"
    )
    
    # Exit conditions
    take_profit_pct: Decimal | None = Field(
        None,
        ge=0,
        le=1,
        description="Take profit at this percentage gain (0.20 = 20%)"
    )
    stop_loss_pct: Decimal | None = Field(
        None,
        ge=0,
        le=1,
        description="Stop loss at this percentage loss (0.10 = 10%)"
    )
    
    # Position sizing
    position_size_usdc: Decimal | None = Field(
        None,
        ge=0,
        description="Override position size for this market"
    )
    max_positions: int | None = Field(
        None,
        ge=0,
        description="Max concurrent positions in this market"
    )
    
    # Control flags
    enabled: bool = Field(True, description="Enable/disable trading on this market")
    auto_trade: bool = Field(True, description="Allow bot to auto-trade")


class MarketConfigCreate(MarketConfigBase):
    """
    Schema for creating a new market configuration.
    """
    condition_id: str = Field(..., description="Polymarket condition_id")
    market_question: str | None = Field(None, description="Human-readable market question")
    sport: str | None = Field(None, description="Sport category")
    home_team: str | None = None
    away_team: str | None = None


class MarketConfigUpdate(MarketConfigBase):
    """
    Schema for updating an existing market configuration.
    All fields optional - only provided fields are updated.
    """
    market_question: str | None = None
    enabled: bool | None = None
    auto_trade: bool | None = None


class MarketConfigResponse(BaseModel):
    """
    Schema for market configuration in API responses.
    """
    id: uuid.UUID
    condition_id: str
    market_question: str | None
    sport: str | None
    home_team: str | None
    away_team: str | None
    
    # Entry conditions
    entry_threshold_drop: Decimal | None
    entry_threshold_absolute: Decimal | None
    min_time_remaining_seconds: int | None
    
    # Exit conditions
    take_profit_pct: Decimal | None
    stop_loss_pct: Decimal | None
    
    # Position sizing
    position_size_usdc: Decimal | None
    max_positions: int | None
    
    # Control flags
    enabled: bool
    auto_trade: bool
    
    # Timestamps
    created_at: datetime
    updated_at: datetime
    
    model_config = {"from_attributes": True}


class MarketConfigWithDefaults(MarketConfigResponse):
    """
    Extended response that includes effective values.
    Shows both the override value and the default from sport config.
    """
    # Effective values (override or default)
    effective_entry_threshold_drop: Decimal
    effective_entry_threshold_absolute: Decimal
    effective_take_profit_pct: Decimal
    effective_stop_loss_pct: Decimal
    effective_position_size_usdc: Decimal
    effective_min_time_remaining_seconds: int
    effective_max_positions: int


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
