# Kalshi Sports Bot - Updated Architecture
## Based on API Research Findings

---

## Critical Finding: Dual-Source Data Architecture Required

Kalshi's API provides market/trading data but does NOT expose game state information (quarter, inning, time remaining). The solution requires integrating ESPN's unofficial API for real-time game tracking.

---

## Data Source Responsibilities

| Data Point | Source | Endpoint |
|------------|--------|----------|
| Market prices | Kalshi | GET /trade-api/v2/markets |
| Order placement | Kalshi | POST /trade-api/v2/portfolio/orders |
| Account balance | Kalshi | GET /trade-api/v2/portfolio/balance |
| Current positions | Kalshi | GET /trade-api/v2/portfolio/positions |
| Game quarter/period | ESPN | /apis/site/v2/sports/{sport}/{league}/scoreboard |
| Time remaining | ESPN | Same as above |
| Score | ESPN | Same as above |
| Play-by-play | ESPN | /apis/site/v2/sports/{sport}/{league}/summary?event={id} |

---

## ESPN API Endpoints

### Scoreboard (All Live Games)

```python
ESPN_ENDPOINTS = {
    "nfl": "https://site.web.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard",
    "nba": "https://site.web.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard",
    "mlb": "https://site.web.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard",
    "nhl": "https://site.web.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard",
    "soccer_mls": "https://site.web.api.espn.com/apis/site/v2/sports/soccer/usa.1/scoreboard",
}
```

### Single Game Details

```python
# For detailed play-by-play and game state
def get_game_url(sport: str, league: str, event_id: str) -> str:
    return f"https://site.web.api.espn.com/apis/site/v2/sports/{sport}/{league}/summary?event={event_id}"
```

---

## ESPN Response Structure (Scoreboard)

```python
{
    "events": [
        {
            "id": "401547417",                    # ESPN event ID
            "name": "Miami Heat at Chicago Bulls",
            "shortName": "MIA @ CHI",
            "date": "2026-01-23T19:00Z",
            "status": {
                "type": {
                    "id": "2",                    # 1=scheduled, 2=in_progress, 3=final
                    "name": "STATUS_IN_PROGRESS",
                    "state": "in",
                    "completed": false
                },
                "period": 3,                      # Current quarter/period
                "displayClock": "4:32",           # Time remaining in period
                "clock": 272                      # Seconds remaining
            },
            "competitions": [
                {
                    "competitors": [
                        {
                            "id": "14",
                            "homeAway": "home",
                            "team": {
                                "abbreviation": "CHI",
                                "displayName": "Chicago Bulls"
                            },
                            "score": "78"
                        },
                        {
                            "id": "14",
                            "homeAway": "away",
                            "team": {
                                "abbreviation": "MIA",
                                "displayName": "Miami Heat"
                            },
                            "score": "82"
                        }
                    ]
                }
            ]
        }
    ]
}
```

---

## Game Matching: ESPN to Kalshi

The challenge: Match ESPN games to Kalshi markets.

### Approach 1: Team Name Matching

```python
def match_espn_to_kalshi(espn_game: dict, kalshi_markets: list) -> str | None:
    """
    Match ESPN game to Kalshi market ticker.
    
    ESPN gives: "Miami Heat at Chicago Bulls"
    Kalshi has: "KXNBA-MIA-CHI-25JAN26" (example format)
    """
    # Extract team abbreviations from ESPN
    home_team = espn_game["competitions"][0]["competitors"][0]["team"]["abbreviation"]
    away_team = espn_game["competitions"][0]["competitors"][1]["team"]["abbreviation"]
    
    # Search Kalshi markets for matching teams
    for market in kalshi_markets:
        ticker = market["ticker"].upper()
        # Check if both team abbreviations appear in ticker
        if home_team in ticker and away_team in ticker:
            return market["ticker"]
    
    return None
```

### Approach 2: Event Time Matching

```python
def match_by_time_and_teams(espn_game: dict, kalshi_markets: list) -> str | None:
    """Match by start time and team names."""
    espn_start = parse_datetime(espn_game["date"])
    espn_teams = {
        espn_game["competitions"][0]["competitors"][0]["team"]["displayName"].lower(),
        espn_game["competitions"][0]["competitors"][1]["team"]["displayName"].lower()
    }
    
    for market in kalshi_markets:
        # Check if market title contains both team names
        title_lower = market["title"].lower()
        if all(team in title_lower for team in espn_teams):
            return market["ticker"]
    
    return None
```

---

## Updated Trading Engine Flow

```python
async def trading_cycle(self):
    """
    Main trading loop with dual-source data.
    """
    # 1. Get global settings
    settings = await self.get_settings()
    if not settings.bot_enabled:
        return
    
    # 2. Fetch data from BOTH sources
    kalshi_markets = await self.kalshi.get_sports_markets()
    espn_games = await self.espn.get_live_games()
    
    # 3. Match and merge data
    merged_games = self.match_data_sources(kalshi_markets, espn_games)
    
    # 4. Process each matched game
    for game in merged_games:
        # game now has:
        # - kalshi_ticker, kalshi_price (from Kalshi)
        # - quarter, time_remaining, score (from ESPN)
        
        if not game.is_live:
            # Capture pregame baseline from Kalshi prices
            await self.capture_baseline(game)
        else:
            # Check entry/exit using BOTH data sources
            await self.evaluate_trading_conditions(game, settings)
    
    # 5. Check existing positions for exits
    await self.check_exit_conditions()
```

---

## Merged Game Data Structure

```python
@dataclass
class MergedGameData:
    """Combined data from Kalshi and ESPN."""
    
    # Identifiers
    kalshi_ticker: str
    espn_event_id: str
    
    # Teams
    home_team: str
    away_team: str
    
    # From Kalshi
    kalshi_yes_price: int          # Current YES price (cents)
    kalshi_no_price: int           # Current NO price (cents)
    kalshi_volume: int             # Trading volume
    pregame_yes_price: int | None  # Captured baseline
    
    # From ESPN
    is_live: bool
    is_finished: bool
    period: int                    # Quarter/inning number
    period_name: str               # "Q1", "Q2", "3rd Quarter", etc.
    time_remaining_seconds: int    # Seconds left in period
    time_display: str              # "4:32" display format
    home_score: int
    away_score: int
    
    # Calculated
    price_drop_from_baseline: int  # How much price dropped
    
    def get_normalized_segment(self, sport: str) -> str:
        """Convert period to normalized segment string."""
        if sport in ["nba", "nfl"]:
            segments = ["1st_quarter", "2nd_quarter", "halftime", 
                       "3rd_quarter", "4th_quarter", "overtime"]
            if self.period <= 4:
                return segments[self.period - 1]
            return "overtime"
        elif sport == "nhl":
            segments = ["1st_period", "2nd_period", "3rd_period", "overtime"]
            if self.period <= 3:
                return segments[self.period - 1]
            return "overtime"
        elif sport == "mlb":
            # MLB uses innings
            if self.period <= 9:
                return f"inning_{self.period}"
            return f"extra_inning_{self.period}"
        return f"period_{self.period}"
```

---

## ESPN Service Implementation

```python
# src/services/espn_service.py

import httpx
from typing import Optional
from datetime import datetime

class ESPNService:
    """Service for fetching game data from ESPN's unofficial API."""
    
    SPORT_ENDPOINTS = {
        "nba": "basketball/nba",
        "nfl": "football/nfl",
        "mlb": "baseball/mlb",
        "nhl": "hockey/nhl",
        "soccer": "soccer/usa.1",
    }
    
    BASE_URL = "https://site.web.api.espn.com/apis/site/v2/sports"
    
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=10.0)
    
    async def get_scoreboard(self, sport: str) -> list[dict]:
        """
        Get all games for a sport (live and upcoming).
        
        Args:
            sport: One of 'nba', 'nfl', 'mlb', 'nhl', 'soccer'
            
        Returns:
            List of game data dictionaries
        """
        if sport not in self.SPORT_ENDPOINTS:
            raise ValueError(f"Unsupported sport: {sport}")
        
        endpoint = self.SPORT_ENDPOINTS[sport]
        url = f"{self.BASE_URL}/{endpoint}/scoreboard"
        
        response = await self.client.get(url)
        response.raise_for_status()
        
        data = response.json()
        return data.get("events", [])
    
    async def get_live_games(self, sport: str) -> list[dict]:
        """Get only games currently in progress."""
        games = await self.get_scoreboard(sport)
        return [
            game for game in games
            if game.get("status", {}).get("type", {}).get("state") == "in"
        ]
    
    async def get_game_details(self, sport: str, event_id: str) -> dict:
        """
        Get detailed game data including play-by-play.
        
        Args:
            sport: Sport key
            event_id: ESPN event ID
            
        Returns:
            Detailed game data
        """
        endpoint = self.SPORT_ENDPOINTS[sport]
        url = f"{self.BASE_URL}/{endpoint}/summary?event={event_id}"
        
        response = await self.client.get(url)
        response.raise_for_status()
        
        return response.json()
    
    def parse_game_state(self, game: dict) -> dict:
        """
        Extract relevant game state from ESPN response.
        
        Returns:
            {
                "event_id": str,
                "home_team": str,
                "away_team": str,
                "home_abbrev": str,
                "away_abbrev": str,
                "home_score": int,
                "away_score": int,
                "period": int,
                "time_remaining_display": str,
                "time_remaining_seconds": int,
                "is_live": bool,
                "is_finished": bool,
                "start_time": datetime
            }
        """
        status = game.get("status", {})
        status_type = status.get("type", {})
        competition = game.get("competitions", [{}])[0]
        competitors = competition.get("competitors", [])
        
        # Find home and away teams
        home = next((c for c in competitors if c.get("homeAway") == "home"), {})
        away = next((c for c in competitors if c.get("homeAway") == "away"), {})
        
        # Parse time remaining
        clock_display = status.get("displayClock", "0:00")
        clock_seconds = status.get("clock", 0)
        
        # Handle clock as float (ESPN sometimes returns decimal seconds)
        if isinstance(clock_seconds, float):
            clock_seconds = int(clock_seconds)
        
        return {
            "event_id": game.get("id"),
            "name": game.get("name"),
            "short_name": game.get("shortName"),
            "home_team": home.get("team", {}).get("displayName", "Unknown"),
            "away_team": away.get("team", {}).get("displayName", "Unknown"),
            "home_abbrev": home.get("team", {}).get("abbreviation", "???"),
            "away_abbrev": away.get("team", {}).get("abbreviation", "???"),
            "home_score": int(home.get("score", 0)),
            "away_score": int(away.get("score", 0)),
            "period": status.get("period", 0),
            "time_remaining_display": clock_display,
            "time_remaining_seconds": clock_seconds,
            "is_live": status_type.get("state") == "in",
            "is_finished": status_type.get("completed", False),
            "start_time": game.get("date"),
        }
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
```

---

## Updated Kalshi Client (RSA Auth)

```python
# src/services/kalshi_client.py

import base64
import httpx
from datetime import datetime
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import padding
from typing import Optional

class KalshiClient:
    """
    Async client for Kalshi API v2 with RSA-PSS authentication.
    """
    
    DEMO_URL = "https://demo-api.kalshi.co"
    PROD_URL = "https://api.kalshi.com"
    
    def __init__(
        self,
        api_key_id: str,
        private_key_pem: str,
        environment: str = "demo"
    ):
        """
        Initialize Kalshi client.
        
        Args:
            api_key_id: API Key ID from Kalshi
            private_key_pem: Private key in PEM format (string)
            environment: 'demo' or 'prod'
        """
        self.api_key_id = api_key_id
        self.private_key = self._load_private_key(private_key_pem)
        self.base_url = self.DEMO_URL if environment == "demo" else self.PROD_URL
        self.client = httpx.AsyncClient(timeout=30.0)
    
    def _load_private_key(self, pem_string: str):
        """Load RSA private key from PEM string."""
        return serialization.load_pem_private_key(
            pem_string.encode('utf-8'),
            password=None,
            backend=default_backend()
        )
    
    def _create_signature(self, timestamp: str, method: str, path: str) -> str:
        """
        Create RSA-PSS signature for request.
        
        CRITICAL: Path must NOT include query parameters.
        Message format: {timestamp}{method}{path}
        """
        # Strip query parameters from path
        path_clean = path.split('?')[0]
        
        # Create message to sign
        message = f"{timestamp}{method}{path_clean}".encode('utf-8')
        
        # Sign with RSA-PSS
        signature = self.private_key.sign(
            message,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.DIGEST_LENGTH
            ),
            hashes.SHA256()
        )
        
        return base64.b64encode(signature).decode('utf-8')
    
    async def _request(
        self,
        method: str,
        path: str,
        params: dict = None,
        data: dict = None
    ) -> dict:
        """Make authenticated request to Kalshi API."""
        # Generate timestamp in milliseconds
        timestamp = str(int(datetime.now().timestamp() * 1000))
        
        # Create signature
        signature = self._create_signature(timestamp, method.upper(), path)
        
        # Build headers
        headers = {
            "KALSHI-ACCESS-KEY": self.api_key_id,
            "KALSHI-ACCESS-SIGNATURE": signature,
            "KALSHI-ACCESS-TIMESTAMP": timestamp,
            "Content-Type": "application/json"
        }
        
        # Build URL
        url = f"{self.base_url}{path}"
        
        # Make request
        if method.upper() == "GET":
            response = await self.client.get(url, headers=headers, params=params)
        elif method.upper() == "POST":
            response = await self.client.post(url, headers=headers, json=data)
        elif method.upper() == "DELETE":
            response = await self.client.delete(url, headers=headers)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        response.raise_for_status()
        return response.json()
    
    # ═══════════════════════════════════════════════════════════════
    # PORTFOLIO ENDPOINTS
    # ═══════════════════════════════════════════════════════════════
    
    async def get_balance(self) -> dict:
        """Get account balance."""
        return await self._request("GET", "/trade-api/v2/portfolio/balance")
    
    async def get_positions(self) -> list:
        """Get all current positions."""
        result = await self._request("GET", "/trade-api/v2/portfolio/positions")
        return result.get("market_positions", [])
    
    async def get_orders(
        self,
        ticker: str = None,
        status: str = None
    ) -> list:
        """Get orders, optionally filtered."""
        params = {}
        if ticker:
            params["ticker"] = ticker
        if status:
            params["status"] = status
        result = await self._request("GET", "/trade-api/v2/portfolio/orders", params=params)
        return result.get("orders", [])
    
    # ═══════════════════════════════════════════════════════════════
    # MARKET ENDPOINTS
    # ═══════════════════════════════════════════════════════════════
    
    async def get_markets(
        self,
        status: str = None,
        event_ticker: str = None,
        series_ticker: str = None,
        tickers: list[str] = None
    ) -> list:
        """
        Get markets with optional filters.
        
        Args:
            status: 'open', 'closed', 'settled'
            event_ticker: Filter by event
            series_ticker: Filter by series
            tickers: Specific market tickers
        """
        params = {}
        if status:
            params["status"] = status
        if event_ticker:
            params["event_ticker"] = event_ticker
        if series_ticker:
            params["series_ticker"] = series_ticker
        if tickers:
            params["tickers"] = ",".join(tickers)
        
        result = await self._request("GET", "/trade-api/v2/markets", params=params)
        return result.get("markets", [])
    
    async def get_market(self, ticker: str) -> dict:
        """Get single market details."""
        return await self._request("GET", f"/trade-api/v2/markets/{ticker}")
    
    async def get_sports_markets(self, sport: str = None) -> list:
        """
        Get sports-related markets.
        
        Note: Kalshi uses series_ticker prefixes like 'KXNBA', 'KXNFL', etc.
        This may need adjustment based on actual Kalshi ticker structure.
        """
        # Get all open markets
        all_markets = await self.get_markets(status="open")
        
        # Filter for sports (adjust prefix as needed)
        sport_prefixes = {
            "nba": ["KXNBA", "NBA"],
            "nfl": ["KXNFL", "NFL", "NFLPLOFFS"],
            "mlb": ["KXMLB", "MLB"],
            "nhl": ["KXNHL", "NHL"],
        }
        
        if sport and sport.lower() in sport_prefixes:
            prefixes = sport_prefixes[sport.lower()]
            return [
                m for m in all_markets
                if any(m.get("ticker", "").upper().startswith(p) for p in prefixes)
            ]
        
        # Return all sports markets
        all_prefixes = [p for prefixes in sport_prefixes.values() for p in prefixes]
        return [
            m for m in all_markets
            if any(m.get("ticker", "").upper().startswith(p) for p in all_prefixes)
        ]
    
    # ═══════════════════════════════════════════════════════════════
    # ORDER ENDPOINTS
    # ═══════════════════════════════════════════════════════════════
    
    async def place_order(
        self,
        ticker: str,
        side: str,          # "yes" or "no"
        action: str,        # "buy" or "sell"
        count: int,         # Number of contracts
        type: str = "limit",
        price: int = None   # Price in cents (1-99)
    ) -> dict:
        """
        Place a new order.
        
        Args:
            ticker: Market ticker
            side: 'yes' or 'no'
            action: 'buy' or 'sell'
            count: Number of contracts
            type: 'limit' or 'market'
            price: Limit price in cents (required for limit orders)
        """
        data = {
            "ticker": ticker,
            "side": side.lower(),
            "action": action.lower(),
            "count": count,
            "type": type,
        }
        
        if type == "limit" and price is not None:
            # Kalshi uses yes_price or no_price depending on side
            if side.lower() == "yes":
                data["yes_price"] = price
            else:
                data["no_price"] = price
        
        return await self._request("POST", "/trade-api/v2/portfolio/orders", data=data)
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an existing order."""
        try:
            await self._request("DELETE", f"/trade-api/v2/portfolio/orders/{order_id}")
            return True
        except Exception:
            return False
    
    # ═══════════════════════════════════════════════════════════════
    # UTILITY METHODS
    # ═══════════════════════════════════════════════════════════════
    
    async def test_connection(self) -> tuple[bool, str, float]:
        """
        Test API connection.
        
        Returns:
            (success, message, balance_in_dollars)
        """
        try:
            balance_data = await self.get_balance()
            balance_cents = balance_data.get("balance", 0)
            balance_dollars = balance_cents / 100
            return True, "Connection successful", balance_dollars
        except httpx.HTTPStatusError as e:
            return False, f"HTTP error: {e.response.status_code}", 0.0
        except Exception as e:
            return False, f"Connection failed: {str(e)}", 0.0
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
```

---

## Market Matching Service

```python
# src/services/market_matcher.py

from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass
class MatchedGame:
    """A game with data from both Kalshi and ESPN."""
    
    # Identifiers
    kalshi_ticker: str
    espn_event_id: str
    sport: str
    
    # Teams
    home_team: str
    away_team: str
    home_abbrev: str
    away_abbrev: str
    
    # From Kalshi
    kalshi_yes_bid: int
    kalshi_yes_ask: int
    kalshi_last_price: int
    kalshi_volume: int
    
    # From ESPN
    is_live: bool
    is_finished: bool
    period: int
    time_remaining_seconds: int
    time_display: str
    home_score: int
    away_score: int
    
    # Tracked data
    pregame_baseline: Optional[int] = None
    baseline_captured_at: Optional[datetime] = None


class MarketMatcher:
    """
    Service to match Kalshi markets with ESPN games.
    """
    
    # Team abbreviation mappings (ESPN -> variations found in Kalshi)
    TEAM_ALIASES = {
        # NBA
        "MIA": ["MIA", "MIAMI", "HEAT"],
        "CHI": ["CHI", "CHICAGO", "BULLS"],
        "LAL": ["LAL", "LAKERS", "LA"],
        "BOS": ["BOS", "BOSTON", "CELTICS"],
        # Add more as needed...
        
        # NFL
        "SF": ["SF", "SFO", "49ERS", "NINERS"],
        "SEA": ["SEA", "SEATTLE", "SEAHAWKS"],
        # Add more...
    }
    
    def match_games(
        self,
        kalshi_markets: list[dict],
        espn_games: list[dict]
    ) -> list[MatchedGame]:
        """
        Match Kalshi markets to ESPN games.
        
        Returns list of MatchedGame objects with combined data.
        """
        matched = []
        
        for espn_game in espn_games:
            # Parse ESPN data
            espn_data = self._parse_espn_game(espn_game)
            
            # Find matching Kalshi market
            kalshi_market = self._find_kalshi_match(
                espn_data["home_abbrev"],
                espn_data["away_abbrev"],
                kalshi_markets
            )
            
            if kalshi_market:
                matched.append(MatchedGame(
                    kalshi_ticker=kalshi_market["ticker"],
                    espn_event_id=espn_data["event_id"],
                    sport=espn_data.get("sport", "unknown"),
                    home_team=espn_data["home_team"],
                    away_team=espn_data["away_team"],
                    home_abbrev=espn_data["home_abbrev"],
                    away_abbrev=espn_data["away_abbrev"],
                    kalshi_yes_bid=kalshi_market.get("yes_bid", 0),
                    kalshi_yes_ask=kalshi_market.get("yes_ask", 0),
                    kalshi_last_price=kalshi_market.get("last_price", 0),
                    kalshi_volume=kalshi_market.get("volume", 0),
                    is_live=espn_data["is_live"],
                    is_finished=espn_data["is_finished"],
                    period=espn_data["period"],
                    time_remaining_seconds=espn_data["time_remaining_seconds"],
                    time_display=espn_data["time_display"],
                    home_score=espn_data["home_score"],
                    away_score=espn_data["away_score"],
                ))
        
        return matched
    
    def _parse_espn_game(self, game: dict) -> dict:
        """Extract relevant data from ESPN game object."""
        status = game.get("status", {})
        status_type = status.get("type", {})
        competition = game.get("competitions", [{}])[0]
        competitors = competition.get("competitors", [])
        
        home = next((c for c in competitors if c.get("homeAway") == "home"), {})
        away = next((c for c in competitors if c.get("homeAway") == "away"), {})
        
        return {
            "event_id": game.get("id"),
            "home_team": home.get("team", {}).get("displayName", ""),
            "away_team": away.get("team", {}).get("displayName", ""),
            "home_abbrev": home.get("team", {}).get("abbreviation", ""),
            "away_abbrev": away.get("team", {}).get("abbreviation", ""),
            "home_score": int(home.get("score", 0) or 0),
            "away_score": int(away.get("score", 0) or 0),
            "period": status.get("period", 0),
            "time_remaining_seconds": int(status.get("clock", 0) or 0),
            "time_display": status.get("displayClock", "0:00"),
            "is_live": status_type.get("state") == "in",
            "is_finished": status_type.get("completed", False),
        }
    
    def _find_kalshi_match(
        self,
        home_abbrev: str,
        away_abbrev: str,
        kalshi_markets: list[dict]
    ) -> Optional[dict]:
        """Find Kalshi market matching the teams."""
        # Get all possible aliases for each team
        home_aliases = self._get_aliases(home_abbrev)
        away_aliases = self._get_aliases(away_abbrev)
        
        for market in kalshi_markets:
            ticker = market.get("ticker", "").upper()
            title = market.get("title", "").upper()
            
            # Check if both teams appear in ticker or title
            home_found = any(alias in ticker or alias in title for alias in home_aliases)
            away_found = any(alias in ticker or alias in title for alias in away_aliases)
            
            if home_found and away_found:
                return market
        
        return None
    
    def _get_aliases(self, abbrev: str) -> list[str]:
        """Get all possible aliases for a team abbreviation."""
        abbrev_upper = abbrev.upper()
        if abbrev_upper in self.TEAM_ALIASES:
            return self.TEAM_ALIASES[abbrev_upper]
        return [abbrev_upper]
```

---

## Updated File Structure

```
kalshi-sports-bot/
|-- src/
|   |-- __init__.py
|   |-- main.py
|   |-- config.py
|   |
|   |-- api/
|   |   |-- deps.py
|   |   |-- routes/
|   |       |-- auth.py
|   |       |-- onboarding.py
|   |       |-- dashboard.py
|   |       |-- settings.py
|   |       |-- bot.py
|   |       |-- trading.py
|   |   |-- websocket.py
|   |
|   |-- core/
|   |   |-- security.py
|   |   |-- encryption.py
|   |   |-- exceptions.py
|   |
|   |-- services/
|   |   |-- kalshi_client.py      # Kalshi API (prices, orders)
|   |   |-- espn_service.py       # ESPN API (game state)    <-- NEW
|   |   |-- market_matcher.py     # Match ESPN to Kalshi     <-- NEW
|   |   |-- trading_engine.py     # Main trading logic
|   |   |-- position_manager.py
|   |   |-- alert_service.py
|   |
|   |-- models/
|   |-- schemas/
|   |-- db/
|   |-- templates/
|   |-- static/
|
|-- tests/
|-- docs/
|-- Dockerfile
|-- requirements.txt
```

---

## Summary of Changes

| Original Assumption | Updated Approach |
|---------------------|------------------|
| Single data source (Kalshi) | Dual sources: Kalshi + ESPN |
| Game state from Kalshi | Game state from ESPN API |
| Simple ticker matching | Team abbreviation matching logic |
| Direct period parsing | ESPN provides period/clock directly |

---

## ESPN API Considerations

1. **Unofficial API**: ESPN does not officially support this API. It works but could change.

2. **No Auth Required**: ESPN scoreboard endpoints are public, no API key needed.

3. **Rate Limiting**: Poll conservatively (every 5-10 seconds) to avoid being blocked.

4. **Latency Advantage**: ESPN data arrives 5-10 seconds before TV broadcasts, giving trading advantage.

5. **Fallback Plan**: If ESPN blocks requests, can scrape or use alternative sports data APIs (paid options exist).

---

This architecture is more complex but reflects how real sports trading bots work. The dual-source approach is standard in the industry.
