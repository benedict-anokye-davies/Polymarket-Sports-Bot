from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID
from typing import Any

from src.services.market_discovery import DiscoveredMarket

@dataclass
class TrackedGame:
    """A game being actively tracked by the bot."""
    espn_event_id: str
    sport: str
    home_team: str
    away_team: str
    market: DiscoveredMarket
    baseline_price: float | None = None
    current_price: float | None = None
    game_status: str = "pre"
    period: int = 0
    clock: str = ""
    home_score: int = 0
    away_score: int = 0
    last_update: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    has_position: bool = False
    position_id: UUID | None = None
    # Which team to bet on: "home", "away", or "both"
    selected_side: str = "home"


@dataclass
class SportStats:
    """Per-sport statistics tracking."""
    sport: str
    trades_today: int = 0
    daily_pnl: float = 0.0
    open_positions: int = 0
    tracked_games: int = 0
    enabled: bool = True
    priority: int = 1
    max_daily_loss: float = 50.0
    max_exposure: float = 200.0


from typing import TypedDict

class TradeSignal(TypedDict):
    """Signal to execute a trade."""
    side: str
    price: float
    size: float
    confidence: float
    reason: str
    metadata: dict[str, Any]
