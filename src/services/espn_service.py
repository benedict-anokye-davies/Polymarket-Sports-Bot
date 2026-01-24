"""
ESPN API service for fetching live game data.
Polls scoreboard and summary endpoints for game state.
"""

from datetime import datetime, timezone
from typing import Any

import httpx

from src.core.exceptions import ESPNAPIError


class ESPNService:
    """
    ESPN API client for retrieving live sports game data.
    Provides game state information including scores, period, and time remaining.
    """
    
    BASE_URL = "https://site.web.api.espn.com/apis/site/v2/sports"
    
    SPORT_ENDPOINTS = {
        "nba": "basketball/nba",
        "nfl": "football/nfl",
        "mlb": "baseball/mlb",
        "nhl": "hockey/nhl",
    }
    
    SEGMENT_MAPPING = {
        "nba": {1: "q1", 2: "q2", 3: "q3", 4: "q4"},
        "nfl": {1: "q1", 2: "q2", 3: "q3", 4: "q4"},
        "nhl": {1: "p1", 2: "p2", 3: "p3"},
    }
    
    def __init__(self):
        """
        Initializes the ESPN service with an HTTP client.
        """
        self._client: httpx.AsyncClient | None = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """
        Returns reusable async HTTP client.
        """
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=15.0)
        return self._client
    
    def _get_sport_endpoint(self, sport: str) -> str:
        """
        Returns the ESPN endpoint path for a sport.
        """
        endpoint = self.SPORT_ENDPOINTS.get(sport.lower())
        if not endpoint:
            raise ValueError(f"Unsupported sport: {sport}")
        return endpoint
    
    async def get_scoreboard(self, sport: str) -> list[dict[str, Any]]:
        """
        Fetches the current scoreboard for a sport.
        
        Args:
            sport: Sport identifier (nba, nfl, mlb, nhl)
        
        Returns:
            List of game data dictionaries
        """
        try:
            client = await self._get_client()
            endpoint = self._get_sport_endpoint(sport)
            
            response = await client.get(f"{self.BASE_URL}/{endpoint}/scoreboard")
            response.raise_for_status()
            
            data = response.json()
            events = data.get("events", [])
            
            return events
            
        except httpx.HTTPError as e:
            raise ESPNAPIError(f"Failed to fetch scoreboard: {str(e)}")
    
    async def get_game_summary(self, sport: str, event_id: str) -> dict[str, Any]:
        """
        Fetches detailed summary for a specific game.
        
        Args:
            sport: Sport identifier
            event_id: ESPN event ID
        
        Returns:
            Game summary data
        """
        try:
            client = await self._get_client()
            endpoint = self._get_sport_endpoint(sport)
            
            response = await client.get(
                f"{self.BASE_URL}/{endpoint}/summary",
                params={"event": event_id}
            )
            response.raise_for_status()
            
            return response.json()
            
        except httpx.HTTPError as e:
            raise ESPNAPIError(f"Failed to fetch game summary: {str(e)}")
    
    def parse_game_state(self, game: dict[str, Any], sport: str) -> dict[str, Any]:
        """
        Extracts standardized game state from ESPN event data.
        
        Args:
            game: ESPN event dictionary
            sport: Sport identifier for segment normalization
        
        Returns:
            Normalized game state dictionary
        """
        status = game.get("status", {})
        status_type = status.get("type", {})
        competitions = game.get("competitions", [{}])[0]
        competitors = competitions.get("competitors", [])
        
        home_team = None
        away_team = None
        home_score = 0
        away_score = 0
        
        for comp in competitors:
            if comp.get("homeAway") == "home":
                home_team = {
                    "name": comp.get("team", {}).get("displayName", ""),
                    "abbreviation": comp.get("team", {}).get("abbreviation", ""),
                    "id": comp.get("team", {}).get("id", ""),
                }
                home_score = int(comp.get("score", 0) or 0)
            elif comp.get("homeAway") == "away":
                away_team = {
                    "name": comp.get("team", {}).get("displayName", ""),
                    "abbreviation": comp.get("team", {}).get("abbreviation", ""),
                    "id": comp.get("team", {}).get("id", ""),
                }
                away_score = int(comp.get("score", 0) or 0)
        
        state = status_type.get("state", "")
        is_live = state == "in"
        is_finished = state == "post"
        
        period = status.get("period", 0)
        clock_display = status.get("displayClock", "0:00")
        clock_seconds = self._parse_clock_to_seconds(clock_display)
        
        segment = self._normalize_segment(period, sport)
        
        start_time = None
        if game.get("date"):
            try:
                start_time = datetime.fromisoformat(
                    game["date"].replace("Z", "+00:00")
                )
            except ValueError:
                pass
        
        return {
            "event_id": game.get("id", ""),
            "name": game.get("name", ""),
            "short_name": game.get("shortName", ""),
            "start_time": start_time,
            "is_live": is_live,
            "is_finished": is_finished,
            "period": period,
            "segment": segment,
            "clock_display": clock_display,
            "time_remaining_seconds": clock_seconds,
            "home_team": home_team,
            "away_team": away_team,
            "home_score": home_score,
            "away_score": away_score,
        }
    
    def _parse_clock_to_seconds(self, clock_display: str) -> int:
        """
        Converts clock display string to seconds.
        Handles formats like "12:00", "5:30", "0:45"
        """
        try:
            parts = clock_display.split(":")
            if len(parts) == 2:
                minutes = int(parts[0])
                seconds = int(parts[1])
                return minutes * 60 + seconds
            return 0
        except (ValueError, IndexError):
            return 0
    
    def _normalize_segment(self, period: int, sport: str) -> str:
        """
        Converts ESPN period number to standardized segment identifier.
        
        Args:
            period: Period number from ESPN
            sport: Sport identifier
        
        Returns:
            Normalized segment string (e.g., "q1", "p2", "inning_5")
        """
        sport_lower = sport.lower()
        
        if sport_lower in self.SEGMENT_MAPPING:
            mapping = self.SEGMENT_MAPPING[sport_lower]
            segment = mapping.get(period)
            if segment:
                return segment
            return "ot"
        
        if sport_lower == "mlb":
            return f"inning_{period}"
        
        return f"period_{period}"
    
    async def get_live_games(self, sport: str) -> list[dict[str, Any]]:
        """
        Fetches only currently live games for a sport.
        
        Args:
            sport: Sport identifier
        
        Returns:
            List of parsed game state dictionaries for live games only
        """
        events = await self.get_scoreboard(sport)
        
        live_games = []
        for event in events:
            state = self.parse_game_state(event, sport)
            if state["is_live"]:
                live_games.append(state)
        
        return live_games
    
    async def get_upcoming_games(self, sport: str, hours: int = 24) -> list[dict[str, Any]]:
        """
        Fetches games starting within the specified time window.
        
        Args:
            sport: Sport identifier
            hours: Number of hours to look ahead
        
        Returns:
            List of parsed game state dictionaries for upcoming games
        """
        events = await self.get_scoreboard(sport)
        
        now = datetime.now(timezone.utc)
        cutoff = now.replace(tzinfo=None)
        
        upcoming = []
        for event in events:
            state = self.parse_game_state(event, sport)
            
            if state["is_finished"] or state["is_live"]:
                continue
            
            if state["start_time"]:
                start = state["start_time"].replace(tzinfo=None)
                hours_until = (start - cutoff).total_seconds() / 3600
                
                if 0 <= hours_until <= hours:
                    upcoming.append(state)
        
        return upcoming
    
    async def get_game_details(self, sport: str, event_id: str) -> dict[str, Any] | None:
        """
        Fetches current state for a specific game by event ID.
        
        Args:
            sport: Sport identifier (nba, nfl, etc.)
            event_id: ESPN event ID
        
        Returns:
            Game data dictionary or None if not found
        """
        try:
            events = await self.get_scoreboard(sport)
            
            for event in events:
                if event.get("id") == event_id:
                    return event
            
            return None
            
        except ESPNAPIError:
            return None
    
    async def close(self) -> None:
        """
        Closes HTTP client connections.
        """
        if self._client:
            await self._client.aclose()
            self._client = None
