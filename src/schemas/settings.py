"""
Settings schemas for sport configs and global settings.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field


# Expanded list of supported sports
SUPPORTED_SPORTS = [
    "nba", "nfl", "mlb", "nhl",  # Major US leagues
    "wnba", "ncaab", "ncaaf",     # Additional US sports
    "soccer", "epl", "laliga", "bundesliga", "seriea", "ligue1", "ucl",  # Soccer
    "tennis", "mma", "golf"       # Individual sports
]
SPORT_PATTERN = f"^({'|'.join(SUPPORTED_SPORTS)})$"


class SportConfigCreate(BaseModel):
    """
    Schema for creating a new sport configuration.
    """
    sport: str = Field(..., pattern=SPORT_PATTERN)
    enabled: bool = True
    entry_threshold_drop: Decimal = Field(default=Decimal("0.15"), ge=0, le=1)
    entry_threshold_absolute: Decimal = Field(default=Decimal("0.50"), ge=0, le=1)
    take_profit_pct: Decimal = Field(default=Decimal("0.20"), ge=0, le=1)
    stop_loss_pct: Decimal = Field(default=Decimal("0.10"), ge=0, le=1)
    position_size_usdc: Decimal = Field(default=Decimal("50.00"), ge=1)
    max_positions_per_game: int = Field(default=1, ge=1, le=10)
    max_total_positions: int = Field(default=5, ge=1, le=50)
    min_time_remaining_seconds: int = Field(default=300, ge=0)
    
    # Sport-specific progress thresholds
    min_time_remaining_minutes: int | None = Field(default=5, ge=1, le=20)  # NBA, NFL, NHL
    max_elapsed_minutes: int | None = Field(default=70, ge=1, le=120)       # Soccer
    max_entry_inning: int | None = Field(default=6, ge=1, le=9)             # MLB
    min_outs_remaining: int | None = Field(default=6, ge=1, le=54)          # MLB
    max_entry_set: int | None = Field(default=2, ge=1, le=5)                # Tennis
    min_sets_remaining: int | None = Field(default=1, ge=1, le=3)           # Tennis
    max_entry_round: int | None = Field(default=2, ge=1, le=5)              # MMA
    max_entry_hole: int | None = Field(default=14, ge=1, le=18)             # Golf
    min_holes_remaining: int | None = Field(default=4, ge=1, le=18)         # Golf
    
    # Per-sport risk management
    max_daily_loss_usdc: Decimal | None = Field(default=Decimal("50.00"), ge=0)
    max_exposure_usdc: Decimal | None = Field(default=Decimal("200.00"), ge=0)
    priority: int | None = Field(default=1, ge=1, le=10)
    trading_hours_start: str | None = Field(default=None, pattern="^[0-2][0-9]:[0-5][0-9]$")
    trading_hours_end: str | None = Field(default=None, pattern="^[0-2][0-9]:[0-5][0-9]$")


class SportConfigUpdate(BaseModel):
    """
    Schema for updating an existing sport configuration.
    All fields optional to allow partial updates.
    """
    enabled: bool | None = None
    entry_threshold_drop: Decimal | None = Field(default=None, ge=0, le=1)
    entry_threshold_absolute: Decimal | None = Field(default=None, ge=0, le=1)
    take_profit_pct: Decimal | None = Field(default=None, ge=0, le=1)
    stop_loss_pct: Decimal | None = Field(default=None, ge=0, le=1)
    position_size_usdc: Decimal | None = Field(default=None, ge=1)
    max_positions_per_game: int | None = Field(default=None, ge=1, le=10)
    max_total_positions: int | None = Field(default=None, ge=1, le=50)
    min_time_remaining_seconds: int | None = Field(default=None, ge=0)
    
    # Sport-specific progress thresholds
    min_time_remaining_minutes: int | None = Field(default=None, ge=1, le=20)
    max_elapsed_minutes: int | None = Field(default=None, ge=1, le=120)
    max_entry_inning: int | None = Field(default=None, ge=1, le=9)
    min_outs_remaining: int | None = Field(default=None, ge=1, le=54)
    max_entry_set: int | None = Field(default=None, ge=1, le=5)
    min_sets_remaining: int | None = Field(default=None, ge=1, le=3)
    max_entry_round: int | None = Field(default=None, ge=1, le=5)
    max_entry_hole: int | None = Field(default=None, ge=1, le=18)
    min_holes_remaining: int | None = Field(default=None, ge=1, le=18)
    
    # Per-sport risk management
    max_daily_loss_usdc: Decimal | None = Field(default=None, ge=0)
    max_exposure_usdc: Decimal | None = Field(default=None, ge=0)
    priority: int | None = Field(default=None, ge=1, le=10)
    trading_hours_start: str | None = Field(default=None, pattern="^[0-2][0-9]:[0-5][0-9]$")
    trading_hours_end: str | None = Field(default=None, pattern="^[0-2][0-9]:[0-5][0-9]$")


class SportConfigResponse(BaseModel):
    """
    Schema for sport configuration in API responses.
    """
    id: uuid.UUID
    sport: str
    enabled: bool
    entry_threshold_drop: Decimal
    entry_threshold_absolute: Decimal
    take_profit_pct: Decimal
    stop_loss_pct: Decimal
    position_size_usdc: Decimal
    max_positions_per_game: int
    max_total_positions: int
    min_time_remaining_seconds: int
    
    # Sport-specific progress thresholds
    min_time_remaining_minutes: int | None = None
    max_elapsed_minutes: int | None = None
    max_entry_inning: int | None = None
    min_outs_remaining: int | None = None
    max_entry_set: int | None = None
    min_sets_remaining: int | None = None
    max_entry_round: int | None = None
    max_entry_hole: int | None = None
    min_holes_remaining: int | None = None
    
    # Per-sport risk management
    max_daily_loss_usdc: Decimal | None = None
    max_exposure_usdc: Decimal | None = None
    priority: int | None = None
    trading_hours_start: str | None = None
    trading_hours_end: str | None = None
    updated_at: datetime

    model_config = {"from_attributes": True}


class GlobalSettingsUpdate(BaseModel):
    """
    Schema for updating global bot settings.
    All fields optional to allow partial updates.
    """
    bot_enabled: bool | None = None
    max_daily_loss_usdc: Decimal | None = Field(default=None, ge=0)
    max_portfolio_exposure_usdc: Decimal | None = Field(default=None, ge=0)
    discord_webhook_url: str | None = None
    discord_alerts_enabled: bool | None = None
    poll_interval_seconds: int | None = Field(default=None, ge=5, le=60)
    # Paper trading and safety
    dry_run_mode: bool | None = None
    emergency_stop: bool | None = None
    max_slippage_pct: Decimal | None = Field(default=None, ge=0, le=0.5)
    order_fill_timeout_seconds: int | None = Field(default=None, ge=10, le=300)
    # Balance Guardian fields
    min_balance_threshold: Decimal | None = Field(default=None, ge=0)
    kill_switch_active: bool | None = None
    current_losing_streak: int | None = Field(default=None, ge=0)
    max_losing_streak: int | None = Field(default=None, ge=1, le=50)
    streak_reduction_pct: Decimal | None = Field(default=None, ge=0, le=1)


class GlobalSettingsResponse(BaseModel):
    """
    Schema for global settings in API responses.
    """
    id: uuid.UUID
    bot_enabled: bool
    max_daily_loss_usdc: Decimal
    max_portfolio_exposure_usdc: Decimal
    discord_webhook_url: str | None
    discord_alerts_enabled: bool
    poll_interval_seconds: int
    # Paper trading and safety
    dry_run_mode: bool | None = True
    emergency_stop: bool | None = False
    max_slippage_pct: Decimal | None = None
    order_fill_timeout_seconds: int | None = None
    # Balance Guardian fields
    min_balance_threshold: Decimal | None = None
    kill_switch_active: bool = False
    kill_switch_activated_at: datetime | None = None
    kill_switch_reason: str | None = None
    current_losing_streak: int = 0
    max_losing_streak: int = 5
    streak_reduction_pct: Decimal = Decimal("0.5")
    updated_at: datetime
    
    model_config = {"from_attributes": True}
