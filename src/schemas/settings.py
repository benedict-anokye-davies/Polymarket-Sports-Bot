"""
Settings schemas for sport configs and global settings.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, Field


# Wallet/Credential schemas
class WalletStatusResponse(BaseModel):
    """Response schema for wallet connection status."""
    is_connected: bool
    platform: Literal["kalshi", "polymarket"] | None = None
    masked_identifier: str | None = None  # "XXXX...1234" or "0x1234...abcd"
    last_tested_at: datetime | None = None
    connection_error: str | None = None


class WalletUpdateRequest(BaseModel):
    """Request schema for updating wallet credentials."""
    platform: Literal["kalshi", "polymarket"]
    # Kalshi credentials
    api_key: str | None = None
    api_secret: str | None = None  # RSA private key for Kalshi
    # Polymarket credentials
    private_key: str | None = None
    funder_address: str | None = None


# League to sport type mapping for proper defaults
LEAGUE_SPORT_TYPE_MAP = {
    # Basketball
    "nba": "nba", "wnba": "nba", "ncaab": "ncaab", "ncaaw": "ncaab",
    "nba_gleague": "nba", "euroleague": "nba", "eurocup": "nba",
    "spanish_acb": "nba", "australian_nbl": "nba", "fiba": "nba",
    
    # Football
    "nfl": "nfl", "ncaaf": "nfl", "cfl": "nfl", "xfl": "nfl", "usfl": "nfl",
    
    # Baseball
    "mlb": "mlb", "ncaa_baseball": "mlb", "npb": "mlb", "kbo": "mlb", "mexican_baseball": "mlb",
    
    # Hockey
    "nhl": "nhl", "ahl": "nhl", "khl": "nhl", "shl": "nhl", "ncaa_hockey": "nhl", "iihf": "nhl",
    
    # Soccer (all map to "soccer" sport type)
    "epl": "soccer", "championship": "soccer", "league_one": "soccer", "league_two": "soccer",
    "fa_cup": "soccer", "efl_cup": "soccer", "laliga": "soccer", "laliga2": "soccer",
    "copa_del_rey": "soccer", "bundesliga": "soccer", "bundesliga2": "soccer",
    "dfb_pokal": "soccer", "seriea": "soccer", "serieb": "soccer", "coppa_italia": "soccer",
    "ligue1": "soccer", "ligue2": "soccer", "coupe_de_france": "soccer",
    "eredivisie": "soccer", "liga_portugal": "soccer", "scottish": "soccer",
    "belgian": "soccer", "turkish": "soccer", "russian": "soccer", "greek": "soccer",
    "austrian": "soccer", "swiss": "soccer", "danish": "soccer", "norwegian": "soccer",
    "swedish": "soccer", "polish": "soccer", "czech": "soccer", "ukrainian": "soccer",
    "ucl": "soccer", "europa": "soccer", "conference": "soccer", "nations_league": "soccer",
    "euro_qualifiers": "soccer", "euros": "soccer", "mls": "soccer", "usl": "soccer",
    "nwsl": "soccer", "us_open_cup": "soccer", "brazilian": "soccer", "brazilian_b": "soccer",
    "copa_brazil": "soccer", "libertadores": "soccer", "sudamericana": "soccer",
    "argentine": "soccer", "mexican": "soccer", "liga_mx_cup": "soccer", "colombian": "soccer",
    "chilean": "soccer", "peruvian": "soccer", "copa_america": "soccer", "saudi": "soccer",
    "japanese": "soccer", "korean": "soccer", "chinese": "soccer", "australian_aleague": "soccer",
    "indian": "soccer", "afc_champions": "soccer", "world_cup": "soccer",
    "world_cup_qualifiers": "soccer", "club_world_cup": "soccer", "womens_world_cup": "soccer",
    "concacaf_gold": "soccer", "concacaf_nations": "soccer", "soccer": "soccer",
    
    # Tennis
    "atp": "tennis", "wta": "tennis", "australian_open": "tennis", "french_open": "tennis",
    "wimbledon": "tennis", "us_open_tennis": "tennis", "davis_cup": "tennis", "tennis": "tennis",
    
    # Golf
    "pga": "golf", "lpga": "golf", "european_tour": "golf", "masters": "golf",
    "us_open_golf": "golf", "british_open": "golf", "pga_championship": "golf",
    "liv_golf": "golf", "golf": "golf",
    
    # MMA/Combat
    "ufc": "mma", "bellator": "mma", "pfl": "mma", "one_championship": "mma",
    "boxing": "mma", "mma": "mma",
    
    # Motorsports (uses time-based like NFL)
    "f1": "nfl", "nascar": "nfl", "indycar": "nfl", "motogp": "nfl",
    
    # Other
    "rugby_union": "nfl", "rugby_league": "nfl", "cricket": "mlb", "afl": "nfl",
}

# All supported leagues (for validation)
ALL_SUPPORTED_LEAGUES = list(LEAGUE_SPORT_TYPE_MAP.keys())


class SportConfigCreate(BaseModel):
    """
    Schema for creating a new sport configuration.
    """
    sport: str = Field(..., description="Sport or league identifier (e.g., 'nba', 'epl', 'ucl')")
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


# ============================================================================
# Bulk League Configuration Schemas
# ============================================================================

class BulkLeagueConfigRequest(BaseModel):
    """
    Schema for configuring multiple leagues at once with the same parameters.
    Allows clients to select multiple leagues and apply uniform settings.
    """
    leagues: list[str] = Field(
        ...,
        min_length=1,
        description="List of league identifiers to configure (e.g., ['epl', 'laliga', 'ucl'])"
    )
    enabled: bool = True
    entry_threshold_drop: Decimal = Field(default=Decimal("0.15"), ge=0, le=1)
    entry_threshold_absolute: Decimal = Field(default=Decimal("0.50"), ge=0, le=1)
    take_profit_pct: Decimal = Field(default=Decimal("0.20"), ge=0, le=1)
    stop_loss_pct: Decimal = Field(default=Decimal("0.10"), ge=0, le=1)
    position_size_usdc: Decimal = Field(default=Decimal("50.00"), ge=1)
    max_positions_per_game: int = Field(default=1, ge=1, le=10)
    max_total_positions: int = Field(default=5, ge=1, le=50)
    
    # Time-based thresholds (auto-applied based on sport type)
    min_time_remaining_minutes: int | None = Field(default=5, ge=1, le=20)
    max_elapsed_minutes: int | None = Field(default=70, ge=1, le=120)
    
    # Risk management
    max_daily_loss_usdc: Decimal | None = Field(default=Decimal("50.00"), ge=0)
    max_exposure_usdc: Decimal | None = Field(default=Decimal("200.00"), ge=0)


class BulkLeagueConfigResponse(BaseModel):
    """Response schema for bulk league configuration."""
    success: bool
    configured_leagues: list[str]
    failed_leagues: list[str]
    message: str


class LeagueEnableRequest(BaseModel):
    """
    Schema for enabling/disabling multiple leagues at once.
    Use this for quick toggling without changing other parameters.
    """
    leagues: list[str] = Field(
        ...,
        min_length=1,
        description="List of league identifiers to enable/disable"
    )
    enabled: bool = Field(..., description="Whether to enable or disable the leagues")


class LeagueEnableResponse(BaseModel):
    """Response schema for league enable/disable."""
    success: bool
    updated_leagues: list[str]
    message: str


class UserLeagueConfig(BaseModel):
    """Configuration for a single league the user has set up."""
    league_key: str
    enabled: bool
    entry_threshold_drop: Decimal | None = None
    entry_threshold_absolute: Decimal | None = None
    take_profit_pct: Decimal | None = None
    stop_loss_pct: Decimal | None = None
    position_size_usdc: Decimal | None = None
    min_time_remaining_seconds: int | None = None
    max_positions: int | None = None


class LeagueInfo(BaseModel):
    """Basic information about a league."""
    league_key: str
    display_name: str
    sport_type: str


class UserLeagueStatus(BaseModel):
    """Shows all leagues and their configuration status for a user."""
    configured_leagues: list[UserLeagueConfig]
    available_leagues: list[LeagueInfo]
    enabled_count: int
    total_available: int


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
    dry_run_mode: bool | None = False
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
