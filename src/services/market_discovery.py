"""
Market discovery service for finding sports betting markets on Polymarket.
Queries Gamma API and filters for active sports markets.
"""

import asyncio
import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Any
from dataclasses import dataclass

import httpx

from src.core.retry import retry_async, polymarket_circuit
from src.core.exceptions import PolymarketAPIError


logger = logging.getLogger(__name__)


@dataclass
class DiscoveredMarket:
    """Represents a discovered sports market from Polymarket or Kalshi."""
    condition_id: str
    token_id_yes: str
    token_id_no: str
    question: str
    description: str
    sport: str
    home_team: str | None
    away_team: str | None
    game_start_time: datetime | None
    end_date: datetime | None
    volume_24h: float
    liquidity: float
    current_price_yes: float
    current_price_no: float
    spread: float
    # Kalshi-specific field - ticker for trading
    ticker: str | None = None
    # Platform indicator: "polymarket" or "kalshi"
    platform: str = "polymarket"
    
    @property
    def is_high_liquidity(self) -> bool:
        """Check if market has sufficient liquidity for trading."""
        return self.liquidity >= 5000  # $5K minimum
    
    @property
    def is_tight_spread(self) -> bool:
        """Check if spread is acceptable for trading."""
        return self.spread <= 0.05  # 5% max spread


class MarketDiscovery:
    """
    Discovers and filters sports betting markets from Polymarket.
    
    Uses Gamma API to find markets, then filters by:
    - Sport type (NBA, NFL, MLB, NHL)
    - Liquidity thresholds
    - Game timing (upcoming/live)
    - Spread requirements
    """
    
    GAMMA_HOST = "https://gamma-api.polymarket.com"
    CLOB_HOST = "https://clob.polymarket.com"
    
    # Keywords for sport detection
    SPORT_KEYWORDS = {
        "nba": ["nba", "lakers", "celtics", "warriors", "nets", "bulls", "heat", 
                "knicks", "sixers", "suns", "bucks", "mavs", "nuggets", "clippers",
                "basketball", "cavaliers", "raptors", "pacers", "hawks", "hornets",
                "pistons", "magic", "wizards", "thunder", "blazers", "jazz", "kings",
                "spurs", "grizzlies", "pelicans", "timberwolves", "rockets"],
        "nfl": ["nfl", "chiefs", "eagles", "bills", "cowboys", "49ers", "ravens",
                "bengals", "dolphins", "lions", "chargers", "jaguars", "jets",
                "vikings", "seahawks", "packers", "patriots", "broncos", "raiders",
                "steelers", "colts", "browns", "titans", "saints", "falcons",
                "panthers", "buccaneers", "cardinals", "rams", "bears", "giants",
                "commanders", "texans", "football", "super bowl", "touchdown"],
        "mlb": ["mlb", "yankees", "dodgers", "astros", "braves", "mets", "phillies",
                "padres", "rangers", "orioles", "rays", "twins", "mariners", "cubs",
                "cardinals", "red sox", "guardians", "brewers", "diamondbacks",
                "blue jays", "giants", "reds", "tigers", "royals", "pirates",
                "white sox", "angels", "rockies", "nationals", "marlins", "athletics",
                "baseball", "world series", "home run"],
        "nhl": ["nhl", "bruins", "panthers", "oilers", "rangers", "avalanche",
                "stars", "hurricanes", "devils", "kings", "maple leafs", "jets",
                "lightning", "wild", "canucks", "flames", "golden knights", "kraken",
                "islanders", "capitals", "penguins", "senators", "blues", "red wings",
                "predators", "flyers", "sabres", "blackhawks", "coyotes", "ducks",
                "sharks", "blue jackets", "hockey", "stanley cup"],
    }
    
    # Team abbreviation mapping
    TEAM_ABBREVIATIONS = {
        # NBA
        "lakers": "LAL", "celtics": "BOS", "warriors": "GSW", "nets": "BKN",
        "bulls": "CHI", "heat": "MIA", "knicks": "NYK", "sixers": "PHI",
        "suns": "PHX", "bucks": "MIL", "mavericks": "DAL", "mavs": "DAL",
        "nuggets": "DEN", "clippers": "LAC", "cavaliers": "CLE", "raptors": "TOR",
        # NFL
        "chiefs": "KC", "eagles": "PHI", "bills": "BUF", "cowboys": "DAL",
        "49ers": "SF", "ravens": "BAL", "bengals": "CIN", "dolphins": "MIA",
        # Add more as needed...
    }
    
    def __init__(self):
        self._client: httpx.AsyncClient | None = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client
    
    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    def _detect_sport(self, text: str) -> str | None:
        """
        Detect sport type from market text.
        
        Args:
            text: Market question or description
        
        Returns:
            Sport identifier (nba, nfl, mlb, nhl) or None
        """
        text_lower = text.lower()
        
        for sport, keywords in self.SPORT_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text_lower:
                    return sport
        
        return None
    
    def _extract_teams(self, text: str, sport: str) -> tuple[str | None, str | None]:
        """
        Extract team names from market text.
        
        Args:
            text: Market question
            sport: Detected sport type
        
        Returns:
            Tuple of (home_team, away_team) - may be None
        """
        # Common patterns: "Team A vs Team B", "Team A to beat Team B"
        vs_pattern = r"(.+?)\s+(?:vs\.?|versus|to beat|over)\s+(.+?)(?:\?|$|in)"
        match = re.search(vs_pattern, text, re.IGNORECASE)
        
        if match:
            team1 = match.group(1).strip()
            team2 = match.group(2).strip()
            # Convention: Second team is usually home team
            return team2, team1
        
        return None, None
    
    async def fetch_gamma_markets(
        self,
        limit: int = 100,
        offset: int = 0,
        active_only: bool = True
    ) -> list[dict[str, Any]]:
        """
        Fetch markets from Gamma API.
        
        Args:
            limit: Maximum markets to fetch
            offset: Pagination offset
            active_only: Only return active markets
        
        Returns:
            List of market dictionaries
        """
        try:
            client = await self._get_client()
            
            params = {
                "limit": limit,
                "offset": offset,
                "order": "volume24hr",
                "ascending": "false",
            }
            
            if active_only:
                params["active"] = "true"
                params["closed"] = "false"
            
            response = await retry_async(
                client.get,
                f"{self.GAMMA_HOST}/markets",
                params=params,
                max_retries=3,
                circuit_breaker=polymarket_circuit
            )
            
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPError as e:
            raise PolymarketAPIError(f"Failed to fetch Gamma markets: {e}")
    
    async def fetch_market_details(self, condition_id: str) -> dict[str, Any]:
        """
        Fetch detailed market info including token IDs.
        
        Args:
            condition_id: Market condition ID
        
        Returns:
            Market details with tokens
        """
        try:
            client = await self._get_client()
            
            response = await retry_async(
                client.get,
                f"{self.CLOB_HOST}/markets/{condition_id}",
                max_retries=3,
                circuit_breaker=polymarket_circuit
            )
            
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPError as e:
            raise PolymarketAPIError(f"Failed to fetch market details: {e}")
    
    async def get_market_price(self, token_id: str) -> dict[str, float]:
        """
        Get current price for a token.
        
        Args:
            token_id: Token ID to query
        
        Returns:
            Dict with bid, ask, mid prices
        """
        try:
            client = await self._get_client()
            
            response = await retry_async(
                client.get,
                f"{self.CLOB_HOST}/price",
                params={"token_id": token_id},
                max_retries=2,
                circuit_breaker=polymarket_circuit
            )
            
            response.raise_for_status()
            data = response.json()
            
            return {
                "bid": float(data.get("bid", 0) or 0),
                "ask": float(data.get("ask", 0) or 0),
                "mid": float(data.get("mid", 0) or 0),
            }
            
        except httpx.HTTPError as e:
            logger.warning(f"Failed to fetch price for {token_id}: {e}")
            return {"bid": 0, "ask": 0, "mid": 0}
    
    async def discover_sports_markets(
        self,
        sports: list[str] | None = None,
        min_liquidity: float = 1000,
        max_spread: float = 0.10,
        hours_ahead: int = 48,
        include_live: bool = True
    ) -> list[DiscoveredMarket]:
        """
        Discover sports betting markets matching criteria.
        
        Args:
            sports: List of sports to include (None = all)
            min_liquidity: Minimum liquidity in USD
            max_spread: Maximum acceptable spread
            hours_ahead: How far ahead to look for games
            include_live: Include currently live games
        
        Returns:
            List of DiscoveredMarket objects
        """
        discovered = []
        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(hours=hours_ahead)
        
        # Fetch multiple pages of markets
        all_markets = []
        for offset in range(0, 500, 100):
            markets = await self.fetch_gamma_markets(limit=100, offset=offset)
            if not markets:
                break
            all_markets.extend(markets)
            await asyncio.sleep(0.1)  # Rate limiting
        
        logger.info(f"Fetched {len(all_markets)} total markets from Gamma")
        
        for market in all_markets:
            # Skip non-binary markets
            if len(market.get("outcomes", [])) != 2:
                continue
            
            question = market.get("question", "")
            description = market.get("description", "")
            full_text = f"{question} {description}"
            
            # Detect sport
            sport = self._detect_sport(full_text)
            if not sport:
                continue
            
            # Filter by requested sports
            if sports and sport not in sports:
                continue
            
            # Check timing
            end_date_str = market.get("endDate") or market.get("end_date_iso")
            end_date = None
            if end_date_str:
                try:
                    end_date = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
                    
                    # Skip if already ended
                    if end_date < now:
                        continue
                    
                    # Skip if too far in future
                    if end_date > cutoff and not include_live:
                        continue
                except ValueError:
                    pass
            
            # Get token IDs
            condition_id = market.get("conditionId") or market.get("condition_id")
            if not condition_id:
                continue
            
            tokens = market.get("tokens", [])
            if len(tokens) < 2:
                # Fetch detailed info
                try:
                    details = await self.fetch_market_details(condition_id)
                    tokens = details.get("tokens", [])
                except Exception:
                    continue
            
            if len(tokens) < 2:
                continue
            
            # Extract token IDs (YES is typically first)
            token_yes = tokens[0] if isinstance(tokens[0], str) else tokens[0].get("token_id", "")
            token_no = tokens[1] if isinstance(tokens[1], str) else tokens[1].get("token_id", "")
            
            # Get current prices
            price_yes = await self.get_market_price(token_yes)
            price_no = await self.get_market_price(token_no)
            
            # Calculate spread
            mid_yes = price_yes["mid"]
            spread = abs(price_yes["ask"] - price_yes["bid"]) if price_yes["ask"] > 0 else 1.0
            
            # Check liquidity
            liquidity = float(market.get("liquidityNum", 0) or market.get("liquidity", 0) or 0)
            if liquidity < min_liquidity:
                continue
            
            # Check spread
            if spread > max_spread:
                continue
            
            # Extract teams
            home_team, away_team = self._extract_teams(question, sport)
            
            discovered_market = DiscoveredMarket(
                condition_id=condition_id,
                token_id_yes=token_yes,
                token_id_no=token_no,
                question=question,
                description=description[:500] if description else "",
                sport=sport,
                home_team=home_team,
                away_team=away_team,
                game_start_time=end_date,  # Approximate
                end_date=end_date,
                volume_24h=float(market.get("volume24hr", 0) or 0),
                liquidity=liquidity,
                current_price_yes=mid_yes,
                current_price_no=price_no["mid"],
                spread=spread
            )
            
            discovered.append(discovered_market)
            logger.debug(f"Discovered {sport.upper()} market: {question[:50]}...")
        
        # Sort by liquidity (highest first)
        discovered.sort(key=lambda m: m.liquidity, reverse=True)
        
        logger.info(f"Discovered {len(discovered)} sports markets")
        return discovered
    
    async def discover_markets_for_espn_game(
        self,
        home_team: str,
        away_team: str,
        sport: str,
        game_time: datetime
    ) -> DiscoveredMarket | None:
        """
        Find Polymarket market matching an ESPN game.
        
        Args:
            home_team: Home team name or abbreviation
            away_team: Away team name or abbreviation
            sport: Sport type
            game_time: Game start time
        
        Returns:
            Matching market or None
        """
        markets = await self.discover_sports_markets(
            sports=[sport],
            min_liquidity=500,  # Lower threshold for matching
            hours_ahead=24
        )
        
        home_lower = home_team.lower()
        away_lower = away_team.lower()
        
        for market in markets:
            question_lower = market.question.lower()
            
            # Check if both teams mentioned
            home_match = home_lower in question_lower or (
                market.home_team and home_lower in market.home_team.lower()
            )
            away_match = away_lower in question_lower or (
                market.away_team and away_lower in market.away_team.lower()
            )
            
            if home_match and away_match:
                # Verify timing is close
                if market.end_date:
                    time_diff = abs((market.end_date - game_time).total_seconds())
                    if time_diff < 14400:  # Within 4 hours
                        return market
        
        return None

    async def discover_kalshi_markets(
        self,
        sports: list[str] | None = None,
        min_volume: int = 100,
        hours_ahead: int = 48,
        include_live: bool = True
    ) -> list[DiscoveredMarket]:
        """
        Discover sports betting markets from Kalshi.
        
        Uses KalshiClient to fetch sports markets and converts them to
        DiscoveredMarket format for compatibility with the trading engine.
        
        Args:
            sports: List of sports to include (None = all)
            min_volume: Minimum volume threshold
            hours_ahead: How far ahead to look for games
            include_live: Include currently live games
        
        Returns:
            List of DiscoveredMarket objects with platform="kalshi"
        """
        from src.services.kalshi_client import KalshiClient
        
        discovered = []
        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(hours=hours_ahead)
        
        # Create a temporary unauthenticated client for market discovery
        # Market data endpoints don't require authentication
        try:
            client = await self._get_client()
            
            # Kalshi sports endpoint
            kalshi_api_base = "https://api.elections.kalshi.com/trade-api/v2"
            
            params = {
                "category": "Sports",
                "status": "open",
                "limit": 200
            }
            
            response = await client.get(
                f"{kalshi_api_base}/markets",
                params=params,
                timeout=30.0
            )
            
            if response.status_code != 200:
                logger.warning(f"Kalshi API returned status {response.status_code}")
                return []
            
            data = response.json()
            markets = data.get("markets", [])
            
            logger.info(f"Fetched {len(markets)} markets from Kalshi Sports category")
            
            for market in markets:
                ticker = market.get("ticker", "")
                title = market.get("title", "")
                status = market.get("status", "")
                
                # Skip non-open markets
                if status not in ["open", "active"]:
                    continue
                
                # Detect sport from title or ticker
                sport = self._detect_sport(title)
                if not sport:
                    # Try to detect from ticker (e.g., NBA24_LAL_BOS_W_241230)
                    ticker_upper = ticker.upper()
                    if "NBA" in ticker_upper:
                        sport = "nba"
                    elif "NFL" in ticker_upper:
                        sport = "nfl"
                    elif "MLB" in ticker_upper:
                        sport = "mlb"
                    elif "NHL" in ticker_upper:
                        sport = "nhl"
                
                if not sport:
                    continue
                
                # Filter by requested sports
                if sports and sport not in sports:
                    continue
                
                # Check timing
                close_ts = market.get("close_ts", 0)
                event_start_ts = market.get("event_start_ts", 0)
                
                if close_ts:
                    end_date = datetime.fromtimestamp(close_ts, tz=timezone.utc)
                    
                    # Skip if already ended
                    if end_date < now:
                        continue
                    
                    # Skip if too far in future
                    if end_date > cutoff and not include_live:
                        continue
                else:
                    end_date = None
                
                game_start_time = None
                if event_start_ts:
                    game_start_time = datetime.fromtimestamp(event_start_ts, tz=timezone.utc)
                
                # Get prices
                yes_price = float(market.get("yes_price", 0.5))
                no_price = float(market.get("no_price", 0.5))
                
                # Calculate spread from yes/no prices
                spread = abs(yes_price - (1 - no_price))
                
                # Volume as liquidity proxy
                volume = market.get("volume_yes", 0) + market.get("volume_no", 0)
                if volume < min_volume:
                    continue
                
                # Extract teams from title
                home_team, away_team = self._extract_teams(title, sport)
                
                discovered_market = DiscoveredMarket(
                    condition_id=ticker,  # Use ticker as condition_id for Kalshi
                    token_id_yes=f"{ticker}_YES",  # Synthetic token IDs
                    token_id_no=f"{ticker}_NO",
                    question=title,
                    description=market.get("subtitle", ""),
                    sport=sport,
                    home_team=home_team,
                    away_team=away_team,
                    game_start_time=game_start_time,
                    end_date=end_date,
                    volume_24h=float(volume),
                    liquidity=float(volume * yes_price),  # Approximate liquidity
                    current_price_yes=yes_price,
                    current_price_no=no_price,
                    spread=spread,
                    ticker=ticker,
                    platform="kalshi"
                )
                
                discovered.append(discovered_market)
                logger.debug(f"Discovered Kalshi {sport.upper()} market: {title[:50]}...")
            
            # Sort by volume (highest first)
            discovered.sort(key=lambda m: m.volume_24h, reverse=True)
            
            logger.info(f"Discovered {len(discovered)} Kalshi sports markets")
            return discovered
            
        except Exception as e:
            logger.error(f"Failed to discover Kalshi markets: {e}")
            return []

    async def discover_markets_for_platform(
        self,
        platform: str,
        sports: list[str] | None = None,
        min_liquidity: float = 1000,
        max_spread: float = 0.10,
        hours_ahead: int = 48,
        include_live: bool = True
    ) -> list[DiscoveredMarket]:
        """
        Platform-aware market discovery dispatcher.
        
        Routes to appropriate discovery method based on platform.
        
        Args:
            platform: "polymarket" or "kalshi"
            sports: List of sports to include
            min_liquidity: Minimum liquidity threshold
            max_spread: Maximum acceptable spread
            hours_ahead: How far ahead to look
            include_live: Include live games
        
        Returns:
            List of DiscoveredMarket objects
        """
        if platform.lower() == "kalshi":
            return await self.discover_kalshi_markets(
                sports=sports,
                min_volume=int(min_liquidity / 10),  # Adjust threshold for Kalshi
                hours_ahead=hours_ahead,
                include_live=include_live
            )
        else:
            return await self.discover_sports_markets(
                sports=sports,
                min_liquidity=min_liquidity,
                max_spread=max_spread,
                hours_ahead=hours_ahead,
                include_live=include_live
            )


# Singleton instance
market_discovery = MarketDiscovery()
