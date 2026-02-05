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
    sport: str
    volume_24h: float
    liquidity: float
    current_price_yes: float
    current_price_no: float
    spread: float
    description: str = ""
    home_team: str | None = None
    away_team: str | None = None
    game_start_time: datetime | None = None
    end_date: datetime | None = None
    # Kalshi-specific field - ticker for trading
    ticker: str | None = None
    # Platform indicator: always "kalshi"
    platform: str = "kalshi"
    # Multi-leg (parlay) indicator for MVE markets
    is_parlay: bool = False
    parlay_legs: list[dict[str, Any]] | None = None
    
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
                "spurs", "grizzlies", "pelicans", "timberwolves", "rockets",
                # Cities
                "boston", "brooklyn", "york", "philadelphia", "toronto", "chicago",
                "cleveland", "detroit", "indiana", "milwaukee", "atlanta", "charlotte",
                "miami", "orlando", "washington", "denver", "minnesota", "oklahoma",
                "portland", "utah", "golden state", "los angeles", "phoenix", "sacramento",
                "dallas", "houston", "memphis", "orleans", "san antonio"],
        "nfl": ["nfl", "chiefs", "eagles", "bills", "cowboys", "49ers", "ravens",
                "bengals", "dolphins", "lions", "chargers", "jaguars", "jets",
                "vikings", "seahawks", "packers", "patriots", "broncos", "raiders",
                "steelers", "colts", "browns", "titans", "saints", "falcons",
                "panthers", "buccaneers", "cardinals", "rams", "bears", "giants",
                "commanders", "texans", "football", "super bowl", "touchdown",
                # Cities
                "kansas city", "buffalo", "cincinnati", "jacksonville", "baltimore",
                "pittsburgh", "tampa bay", "carolina", "arizona", "seattle", "francisco",
                "las vegas"],
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

    def _parse_datetime(self, value: Any) -> datetime | None:
        """Parse Kalshi timestamps that may be epoch seconds, ms, or ISO strings."""
        if not value:
            return None
        if isinstance(value, (int, float)):
            timestamp = float(value)
            if timestamp > 1_000_000_000_000:
                timestamp = timestamp / 1000.0
            return datetime.fromtimestamp(timestamp, tz=timezone.utc)
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return None
        return None

    def _parse_price(self, market: dict, keys: list[str], fallback: float = 0.5) -> float:
        """Parse a price from a market dict, normalizing cents to dollars."""
        for key in keys:
            value = market.get(key)
            if value is None:
                continue
            try:
                price = float(value)
            except (TypeError, ValueError):
                continue
            if price > 1.0:
                price = price / 100.0
            return max(0.0, min(1.0, price))
        return fallback

    def _parse_volume(self, market: dict) -> float:
        """Parse volume fields with fallbacks for older/newer API shapes."""
        for key in ("volume_24h", "volume"):
            value = market.get(key)
            if value is not None:
                try:
                    return float(value)
                except (TypeError, ValueError):
                    pass
        volume_yes = market.get("volume_yes", 0)
        volume_no = market.get("volume_no", 0)
        try:
            return float(volume_yes) + float(volume_no)
        except (TypeError, ValueError):
            return 0.0
    
    async def discover_kalshi_markets(
        self,
        sports: list[str] | None = None,
        min_volume: int = 0, # Default to 0 to find all markets, filtering happens later
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

            existing_tickers = {m.get("ticker") for m in markets if m.get("ticker")}
            leg_tickers: set[str] = set()

            # Collect underlying leg markets from multi-leg (MVE) markets
            for market in markets:
                title = market.get("title", "")
                subtitle = market.get("subtitle", "")
                yes_sub = market.get("yes_sub_title", "")
                no_sub = market.get("no_sub_title", "")
                text_blob = " ".join([title, subtitle, yes_sub, no_sub]).strip()

                sport = self._detect_sport(text_blob)
                if not sport:
                    ticker_upper = (market.get("ticker") or "").upper()
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
                if sports and sport not in sports:
                    continue

                legs = market.get("mve_selected_legs") or []
                for leg in legs:
                    leg_ticker = leg.get("market_ticker")
                    if leg_ticker and leg_ticker not in existing_tickers:
                        leg_tickers.add(leg_ticker)

            if leg_tickers:
                extra_markets = []
                leg_list = list(leg_tickers)
                logger.info(f"Fetching {len(leg_list)} underlying MVE leg markets")
                for i in range(0, len(leg_list), 200):
                    batch = leg_list[i:i + 200]
                    params = {
                        "tickers": ",".join(batch),
                        "limit": len(batch)
                    }
                    response = await client.get(
                        f"{kalshi_api_base}/markets",
                        params=params,
                        timeout=30.0
                    )
                    if response.status_code != 200:
                        logger.warning(
                            f"Kalshi API returned status {response.status_code} for leg batch {i // 200 + 1}"
                        )
                        continue
                    data = response.json()
                    extra_markets.extend(data.get("markets", []))
                    await asyncio.sleep(0.1)

                if extra_markets:
                    markets.extend(extra_markets)
                    logger.info(f"Added {len(extra_markets)} leg markets (total {len(markets)})")
            
            for market in markets:
                ticker = market.get("ticker", "")
                title = market.get("title", "")
                subtitle = market.get("subtitle", "")
                yes_sub = market.get("yes_sub_title", "")
                no_sub = market.get("no_sub_title", "")
                text_blob = " ".join([title, subtitle, yes_sub, no_sub]).strip()
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
                    sport = self._detect_sport(text_blob or title)
                
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
                close_ts = market.get("close_ts")
                close_time = market.get("close_time")
                event_start_ts = market.get("event_start_ts")
                event_start_time = market.get("event_start_time")

                end_date = self._parse_datetime(close_ts) or self._parse_datetime(close_time)
                if end_date:
                    
                    # Skip if already ended
                    if end_date < now:
                        continue
                    
                    # Skip if too far in future
                    if end_date > cutoff and not include_live:
                        continue
                else:
                    # Permissive fallback: If status is open/active, treat as valid.
                    # We can use current time + 24h as a placeholder end_date
                    end_date = now + timedelta(hours=24)
                    
                game_start_time = None
                if event_start_ts or event_start_time:
                    game_start_time = (
                        self._parse_datetime(event_start_ts)
                        or self._parse_datetime(event_start_time)
                    )
                
                # Get prices
                yes_price = self._parse_price(
                    market,
                    [
                        "yes_ask_dollars",
                        "yes_bid_dollars",
                        "last_price_dollars",
                        "yes_ask",
                        "yes_bid",
                        "last_price",
                        "yes_price",
                    ],
                    fallback=0.5
                )
                no_price = self._parse_price(
                    market,
                    [
                        "no_ask_dollars",
                        "no_bid_dollars",
                        "no_ask",
                        "no_bid",
                        "no_price",
                    ],
                    fallback=1.0 - yes_price
                )
                
                # Calculate spread from yes/no prices
                spread = abs(yes_price - (1 - no_price))
                
                # Volume as liquidity proxy
                volume = self._parse_volume(market)
                if volume < min_volume:
                    continue
                
                # Extract teams from title
                home_team = None
                away_team = None
                
                if is_special_nba and special_home and special_away:
                    home_team, away_team = special_home, special_away
                else:
                    home_team, away_team = self._extract_teams(text_blob or title, sport)
                    
                # Fallback: if vs extraction failed, try to match known cities/teams from keywords
                if not home_team or not away_team:
                     # Simple heuristic: find all known sport keywords in the title
                     found_teams = []
                     text_lower = title.lower()
                     if sport in self.SPORT_KEYWORDS:
                         for kw in self.SPORT_KEYWORDS[sport]:
                             # Don't match the sport name itself or generic terms
                             if kw not in [sport, "basketball", "football", "baseball", "hockey"] and kw in text_lower:
                                 found_teams.append(kw.title())
                     
                     if len(found_teams) >= 2:
                         # Assume first is away, second is home? Or just pair them.
                         # This allows matching "Detroit, Denver" to finding the game.
                         away_team = found_teams[0]
                         home_team = found_teams[1]

                parlay_legs = market.get("mve_selected_legs") or []
                is_parlay = len(parlay_legs) > 1 or "MULTIGAME" in ticker or "parlay" in title.lower() or "combo" in title.lower()

                discovered_market = DiscoveredMarket(
                    condition_id=ticker,  # Use ticker as condition_id for Kalshi
                    token_id_yes=f"{ticker}_YES",  # Synthetic token IDs
                    token_id_no=f"{ticker}_NO",
                    question=title,
                    sport=sport,
                    volume_24h=float(volume),
                    liquidity=float(volume * yes_price),  # Approximate liquidity
                    current_price_yes=yes_price,
                    current_price_no=no_price,
                    spread=spread,
                    description=subtitle or f"{yes_sub} {no_sub}".strip(),
                    home_team=home_team,
                    away_team=away_team,
                    game_start_time=game_start_time,
                    end_date=end_date,
                    ticker=ticker,
                    platform="kalshi",
                    is_parlay=is_parlay,
                    parlay_legs=parlay_legs or None
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
            min_volume=0,  # Force 0 to find all markets, regardless of liquidity (filtering happens in strategy)
            hours_ahead=hours_ahead,
            include_live=include_live
        )


# Singleton instance
market_discovery = MarketDiscovery()
