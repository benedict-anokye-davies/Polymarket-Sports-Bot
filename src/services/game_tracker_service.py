import logging
import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.services.espn_service import ESPNService
from src.services.types import TrackedGame
from src.db.crud.tracked_market import TrackedMarketCRUD
from src.db.crud.activity_log import ActivityLogCRUD

logger = logging.getLogger(__name__)

class GameTrackerService:
    """
    Manages the lifecycle of tracked games:
    - Polling ESPN for updates
    - Syncing state (score, period, clock)
    - Handling game completion
    """
    
    def __init__(self, espn_service: ESPNService):
        self.espn_service = espn_service
        self.tracked_games: dict[str, TrackedGame] = {}
        
    def add_game(self, game: TrackedGame) -> None:
        """Start tracking a game."""
        self.tracked_games[game.espn_event_id] = game
        
    def get_game(self, event_id: str) -> TrackedGame | None:
        """Get a tracked game by ID."""
        return self.tracked_games.get(event_id)
        
    def remove_game(self, event_id: str) -> None:
        """Stop tracking a game."""
        if event_id in self.tracked_games:
            del self.tracked_games[event_id]
            
    async def update_all_games(self) -> list[TrackedGame]:
        """
        Poll ESPN and update all tracked games.
        Returns list of games that finished in this update.
        """
        finished_games = []
        
        for event_id, game in list(self.tracked_games.items()):
            try:
                game_data = await self.espn_service.get_game_summary(
                    game.sport, event_id
                )
                
                if not game_data:
                    continue
                
                # Update game state
                status = game_data.get("status", {})
                game.game_status = status.get("type", {}).get("state", "pre")
                game.period = status.get("period", 0)
                game.clock = status.get("displayClock", "")
                
                competitors = game_data.get("competitions", [{}])[0].get("competitors", [])
                for comp in competitors:
                    if comp.get("homeAway") == "home":
                        game.home_score = int(comp.get("score", 0) or 0)
                    else:
                        game.away_score = int(comp.get("score", 0) or 0)
                
                game.last_update = datetime.now(timezone.utc)
                
                if game.game_status == "post":
                    finished_games.append(game)
                    
            except Exception as e:
                logger.error(f"Failed to update game {event_id}: {e}")
                
        return finished_games
