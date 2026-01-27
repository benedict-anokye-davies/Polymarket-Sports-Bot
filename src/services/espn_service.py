"""
ESPN API service for fetching live game data.
Polls scoreboard and summary endpoints for game state.
Includes retry logic with circuit breakers for resilience.
"""

import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from src.core.exceptions import ESPNAPIError
from src.core.retry import retry_async, espn_circuit


logger = logging.getLogger(__name__)


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
        "soccer": "soccer/usa.1",  # MLS, can also use eng.1 for EPL
        "tennis": "tennis/atp",
        "mma": "mma/ufc",
        "golf": "golf/pga",
        # Additional leagues
        "wnba": "basketball/wnba",
        "ncaab": "basketball/mens-college-basketball",
        "ncaaf": "football/college-football",
        "epl": "soccer/eng.1",
        "laliga": "soccer/esp.1",
        "bundesliga": "soccer/ger.1",
        "seriea": "soccer/ita.1",
        "ligue1": "soccer/fra.1",
        "ucl": "soccer/uefa.champions",
    }
    
    # Group IDs for fetching ALL games instead of just Top 25/filtered
    # These allow us to get all Division I games, not just ranked teams
    SPORT_GROUPS = {
        "ncaab": "50",      # Division I Men's Basketball (all D1 games)
        "ncaaf": "80",      # FBS (Division I-A) Football (all FBS games)
        "soccer": "all",    # All soccer leagues/games
        "epl": "1",         # English Premier League
        "laliga": "15",     # La Liga
        "bundesliga": "10", # Bundesliga
        "seriea": "12",     # Serie A
        "ligue1": "9",      # Ligue 1
    }
    
    SEGMENT_MAPPING = {
        "nba": {1: "q1", 2: "q2", 3: "q3", 4: "q4"},
        "wnba": {1: "q1", 2: "q2", 3: "q3", 4: "q4"},
        "ncaab": {1: "h1", 2: "h2"},  # College basketball uses halves
        "nfl": {1: "q1", 2: "q2", 3: "q3", 4: "q4"},
        "ncaaf": {1: "q1", 2: "q2", 3: "q3", 4: "q4"},
        "nhl": {1: "p1", 2: "p2", 3: "p3"},
        "soccer": {1: "h1", 2: "h2"},
        "epl": {1: "h1", 2: "h2"},
        "laliga": {1: "h1", 2: "h2"},
        "bundesliga": {1: "h1", 2: "h2"},
        "seriea": {1: "h1", 2: "h2"},
        "ligue1": {1: "h1", 2: "h2"},
        "ucl": {1: "h1", 2: "h2"},
        "tennis": {1: "set_1", 2: "set_2", 3: "set_3", 4: "set_4", 5: "set_5"},
        "mma": {1: "r1", 2: "r2", 3: "r3", 4: "r4", 5: "r5"},
        "golf": {},  # Golf uses holes, not periods
    }
    
    # Sports where clock counts UP instead of DOWN
    CLOCK_COUNTUP_SPORTS = {"soccer", "epl", "laliga", "bundesliga", "seriea", "ligue1", "ucl"}
    
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
        Uses retry logic with circuit breaker for resilience.
        
        For college sports (ncaab, ncaaf), uses groups parameter to fetch
        ALL Division I games, not just Top 25 ranked teams.
        
        Args:
            sport: Sport identifier (nba, nfl, mlb, nhl, ncaab, etc.)
        
        Returns:
            List of game data dictionaries
        """
        try:
            client = await self._get_client()
            endpoint = self._get_sport_endpoint(sport)
            
            # Build query parameters
            params = {}
            sport_lower = sport.lower()
            
            # Add groups parameter for sports that need it to fetch all games
            # Without this, college sports only return Top 25 ranked teams
            if sport_lower in self.SPORT_GROUPS:
                group_id = self.SPORT_GROUPS[sport_lower]
                if group_id != "all":
                    params["groups"] = group_id
                # For "all", we use limit parameter instead
                else:
                    params["limit"] = "200"  # Fetch up to 200 games
            
            response = await retry_async(
                client.get,
                f"{self.BASE_URL}/{endpoint}/scoreboard",
                params=params if params else None,
                max_retries=3,
                base_delay=0.5,
                circuit_breaker=espn_circuit
            )
            response.raise_for_status()
            
            data = response.json()
            events = data.get("events", [])
            
            logger.debug(f"Fetched {len(events)} {sport.upper()} events from ESPN")
            return events
            
        except httpx.HTTPError as e:
            logger.warning(f"Failed to fetch {sport} scoreboard: {e}")
            raise ESPNAPIError(f"Failed to fetch scoreboard: {str(e)}")
    
    async def get_game_summary(self, sport: str, event_id: str) -> dict[str, Any]:
        """
        Fetches detailed summary for a specific game.
        Uses retry logic with circuit breaker for resilience.
        
        Args:
            sport: Sport identifier
            event_id: ESPN event ID
        
        Returns:
            Game summary data
        """
        try:
            client = await self._get_client()
            endpoint = self._get_sport_endpoint(sport)
            
            response = await retry_async(
                client.get,
                f"{self.BASE_URL}/{endpoint}/summary",
                params={"event": event_id},
                max_retries=3,
                base_delay=0.5,
                circuit_breaker=espn_circuit
            )
            response.raise_for_status()
            
            return response.json()
            
        except httpx.HTTPError as e:
            logger.warning(f"Failed to fetch summary for event {event_id}: {e}")
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
        
        # Sport-specific progress metrics
        sport_lower = sport.lower()
        elapsed_minutes = 0
        outs_remaining = 0
        current_inning_half = "top"
        
        # Soccer: calculate elapsed minutes (clock counts UP)
        if sport_lower in self.CLOCK_COUNTUP_SPORTS:
            # For soccer, clock_seconds IS elapsed time, not remaining
            elapsed_minutes = clock_seconds / 60
            # Calculate period contribution (45 min per half)
            if period == 2:
                elapsed_minutes += 45
        
        # MLB: parse inning details
        elif sport_lower == "mlb":
            # ESPN provides inning as period, and we need to parse top/bottom
            # Total outs in MLB: 27 per team (9 innings * 3 outs)
            # In current inning, check if top or bottom half
            situation = competitions.get("situation", {})
            outs_in_inning = situation.get("outs", 0)
            is_top_inning = situation.get("isTopInning", True)
            current_inning_half = "top" if is_top_inning else "bottom"
            
            # Calculate outs remaining for the favorite
            # If top of inning, they still have bottom + remaining innings
            # If bottom, they have remaining innings only
            remaining_innings = max(0, 9 - period)
            if is_top_inning:
                outs_remaining = (remaining_innings * 6) + (3 - outs_in_inning) + 3
            else:
                outs_remaining = (remaining_innings * 6) + (3 - outs_in_inning)
        
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
            # Sport-specific fields
            "elapsed_minutes": elapsed_minutes,  # For soccer
            "outs_remaining": outs_remaining,    # For MLB
            "inning_half": current_inning_half,  # For MLB (top/bottom)
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
