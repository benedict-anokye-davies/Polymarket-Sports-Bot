"""
Settings schemas for sport configs and global settings.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field


class SportConfigCreate(BaseModel):
    """
    Schema for creating a new sport configuration.
    """
    sport: str = Field(..., pattern="^(nba|nfl|mlb|nhl)$")
    enabled: bool = True
    entry_threshold_drop: Decimal = Field(default=Decimal("0.15"), ge=0, le=1)
    entry_threshold_absolute: Decimal = Field(default=Decimal("0.50"), ge=0, le=1)
    take_profit_pct: Decimal = Field(default=Decimal("0.20"), ge=0, le=1)
    stop_loss_pct: Decimal = Field(default=Decimal("0.10"), ge=0, le=1)
    position_size_usdc: Decimal = Field(default=Decimal("50.00"), ge=1)
    max_positions_per_game: int = Field(default=1, ge=1, le=10)
    max_total_positions: int = Field(default=5, ge=1, le=50)
    min_time_remaining_seconds: int = Field(default=300, ge=0)
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
    updated_at: datetime
    
    model_config = {"from_attributes": True}
