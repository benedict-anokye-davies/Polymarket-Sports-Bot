"""
Market discovery service for finding sports betting markets on Kalshi.
Queries Kalshi API and filters for active sports markets.
"""

import asyncio
import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Any
from dataclasses import dataclass

import httpx

from src.core.retry import retry_async
from src.core.exceptions import TradingError


logger = logging.getLogger(__name__)


@dataclass
class DiscoveredMarket:
    """Represents a discovered sports market from Kalshi."""
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
    # Platform indicator: always "kalshi"
    platform: str = "kalshi"
    
    @property
    def is_high_liquidity(self) -> bool:
        """Check if market has sufficient liquidity for trading."""
        return self.liquidity >= 500  # $500 minimum for Kalshi
    
    @property
    def is_tight_spread(self) -> bool:
        """Check if spread is acceptable for trading."""
        return self.spread <= 0.15  # 15% max spread


class MarketDiscovery:
    """
    Discovers and filters sports betting markets from Kalshi.
    """
    
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
            
            all_markets = []
            cursor = None
            
            while True:
                params = {
                    "category": "Sports",
                    "status": "open",
                    "limit": 200
                }
                if cursor:
                    params["cursor"] = cursor
                
                response = await client.get(
                    f"{kalshi_api_base}/markets",
                    params=params,
                    timeout=30.0
                )
                
                if response.status_code != 200:
                    logger.warning(f"Kalshi API returned status {response.status_code}")
                    break
                
                data = response.json()
                page_markets = data.get("markets", [])
                if not page_markets:
                    break
                    
                all_markets.extend(page_markets)
                
                cursor = data.get("cursor")
                if not cursor:
                    break
                    
                # Safety break to prevent infinite loops if too many pages
                if len(all_markets) > 5000:
                    logger.warning("Reached 5000 market limit in discovery, stopping pagination")
                    break
                    
                await asyncio.sleep(0.1)  # Rate limiting
            
            markets = all_markets
            logger.info(f"Fetched {len(markets)} markets from Kalshi Sports category")
            
            for market in markets:
                ticker = market.get("ticker", "")
                title = market.get("title", "")
                status = market.get("status", "")
                
                # Skip non-open markets
                if status not in ["open", "active"]:
                    continue
                
                # SPECIAL HANDLING: Robust Parsing for Kalshi Multi-Game/City-Based Titles
                # e.g. "yes Philadelphia, yes Los Angeles...", "yes 76ers, yes Clippers"
                # This fixes the issue where NBA games are hidden in "ESPORTS" tickers
                is_special_nba = False
                special_home = None
                special_away = None
                
                if "Philadelphia" in title and "Los Angeles" in title:
                    is_special_nba = True
                    special_home = "Philadelphia 76ers"
                    special_away = "Los Angeles Clippers"
                elif "76ers" in title and "Clippers" in title:
                    is_special_nba = True
                    special_home = "Philadelphia 76ers"
                    special_away = "Los Angeles Clippers"
                    
                if is_special_nba:
                    sport = "nba"
                else:
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
                    # Stricter filter: Sports markets must have a closing time
                    # This filters out markets with missing timestamps (often stale/invalid)
                    continue
                    
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
                if is_special_nba and special_home and special_away:
                    home_team, away_team = special_home, special_away
                else:
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
        
        Now Kalshi-only per user request. Ignores 'platform' arg unless it's explicitly forcing legacy behavior, but effectively we default to Kalshi.
        """
        # Always use Kalshi logic
        return await self.discover_kalshi_markets(
            sports=sports,
            min_volume=int(min_liquidity / 10),  # Adjust threshold for Kalshi
            hours_ahead=hours_ahead,
            include_live=include_live
        )


# Singleton instance
market_discovery = MarketDiscovery()
