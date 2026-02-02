"""
Bot configuration schemas for trading parameter management.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from decimal import Decimal


class TradingParameters(BaseModel):
    """Trading parameters for bot configuration"""
    probability_drop: float = Field(
        default=15.0,
        ge=1.0,
        le=50.0,
        description="Minimum probability drop from pregame to trigger entry (%)"
    )
    min_volume: float = Field(
        default=50000.0,
        ge=1000.0,
        le=1000000.0,
        description="Minimum market volume to enter ($)"
    )
    position_size: float = Field(
        default=100.0,
        ge=10.0,
        le=10000.0,
        description="Maximum amount to invest per market ($)"
    )
    take_profit: float = Field(
        default=25.0,
        ge=5.0,
        le=200.0,
        description="Take profit percentage (%)"
    )
    stop_loss: float = Field(
        default=15.0,
        ge=5.0,
        le=50.0,
        description="Stop loss percentage (%)"
    )
    latest_entry_time: int = Field(
        default=10,
        ge=0,
        le=60,
        description="No new positions after this many minutes remaining"
    )
    latest_exit_time: int = Field(
        default=2,
        ge=0,
        le=30,
        description="Must close positions by this many minutes remaining"
    )


class GameSelection(BaseModel):
    """Represents a selected game for trading"""
    game_id: str
    sport: str
    home_team: str
    away_team: str
    start_time: str
    # Selected side: "home", "away", or "both"
    # When "home" - only bet if home team meets criteria
    # When "away" - only bet if away team meets criteria
    # When "both" - can bet on either team (legacy behavior)
    selected_side: str = Field(
        default="home",
        description="Which team to bet on: 'home', 'away', or 'both'"
    )
    market_ticker: Optional[str] = None
    token_id_yes: Optional[str] = None
    token_id_no: Optional[str] = None


class BotConfigRequest(BaseModel):
    """Request to update bot configuration"""
    sport: str = Field(..., description="Primary sport identifier (nba, nfl, etc.)")
    game: Optional[GameSelection] = Field(default=None, description="Primary selected game to trade")
    # Support multiple games from different sports
    additional_games: Optional[List[GameSelection]] = Field(
        default=None,
        description="Additional games to trade (can be from different sports)"
    )
    parameters: Optional[TradingParameters] = Field(default=None, description="Trading parameters")
    simulation_mode: bool = Field(default=False, description="Paper trading mode - simulate trades without real money")


class BotConfigResponse(BaseModel):
    """Response with current bot configuration"""
    is_running: bool
    sport: Optional[str] = None
    game: Optional[GameSelection] = None
    # Support multiple games from different sports
    additional_games: Optional[List[GameSelection]] = None
    parameters: Optional[TradingParameters] = None
    simulation_mode: bool = False
    last_updated: Optional[str] = None


class BotStatusResponse(BaseModel):
    """Bot status response"""
    is_running: bool
    current_game: Optional[str] = None
    current_sport: Optional[str] = None
    active_positions: int = 0
    pending_orders: int = 0
    today_pnl: float = 0.0
    today_trades: int = 0


class StartBotRequest(BaseModel):
    """Request to start the bot with specific configuration"""
    sport: str
    game_id: str
    parameters: TradingParameters


class PlaceOrderRequest(BaseModel):
    """Manual order placement request"""
    platform: str = Field(..., description="kalshi or polymarket")
    ticker: str = Field(..., description="Market ticker or token_id")
    side: str = Field(..., description="buy or sell")
    outcome: str = Field(default="yes", description="yes or no")
    price: float = Field(..., ge=0.01, le=0.99, description="Limit price")
    size: float = Field(..., gt=0, description="Order size in $ or contracts")


class PlaceOrderResponse(BaseModel):
    """Order placement response"""
    success: bool
    order_id: Optional[str] = None
    status: str
    filled_size: float = 0.0
    message: Optional[str] = None


class MarketDataResponse(BaseModel):
    """Market data for a specific game/ticker"""
    ticker: str
    platform: str
    title: str
    yes_price: float
    no_price: float
    volume: float
    status: str
    is_live: bool
    time_remaining: Optional[int] = None
