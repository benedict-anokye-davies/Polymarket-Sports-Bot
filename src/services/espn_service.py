"""
ESPN API service for fetching live game data.
Polls scoreboard and summary endpoints for game state.
Includes retry logic with circuit breakers for resilience.
Implements caching to reduce API calls.
"""

import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from src.core.exceptions import ESPNAPIError
from src.core.retry import retry_async, espn_circuit
from src.core.cache import espn_cache


logger = logging.getLogger(__name__)


class ESPNService:
    """
    ESPN API client for retrieving live sports game data.
    Provides game state information including scores, period, and time remaining.
    """
    
    BASE_URL = "https://site.web.api.espn.com/apis/site/v2/sports"
    
    SPORT_ENDPOINTS = {
        # ==================== BASKETBALL ====================
        "nba": "basketball/nba",
        "wnba": "basketball/wnba",
        "ncaab": "basketball/mens-college-basketball",
        "ncaaw": "basketball/womens-college-basketball",
        "nba_gleague": "basketball/nba-g-league",
        "euroleague": "basketball/eur.euroleague",
        "eurocup": "basketball/eur.eurocup",
        "spanish_acb": "basketball/esp.acb",
        "australian_nbl": "basketball/aus.nbl",
        "fiba": "basketball/fiba.world",
        
        # ==================== FOOTBALL ====================
        "nfl": "football/nfl",
        "ncaaf": "football/college-football",
        "cfl": "football/cfl",
        "xfl": "football/xfl",
        "usfl": "football/usfl",
        
        # ==================== BASEBALL ====================
        "mlb": "baseball/mlb",
        "ncaa_baseball": "baseball/college-baseball",
        "npb": "baseball/jpn.npb",  # Japanese baseball
        "kbo": "baseball/kor.kbo",  # Korean baseball
        "mexican_baseball": "baseball/mex.lmb",
        
        # ==================== HOCKEY ====================
        "nhl": "hockey/nhl",
        "ahl": "hockey/ahl",
        "khl": "hockey/rus.khl",
        "shl": "hockey/swe.shl",  # Swedish Hockey League
        "ncaa_hockey": "hockey/college-hockey",
        "iihf": "hockey/iihf.world",
        
        # ==================== SOCCER - EUROPE ====================
        "epl": "soccer/eng.1",              # English Premier League
        "championship": "soccer/eng.2",     # English Championship
        "league_one": "soccer/eng.3",       # English League One
        "league_two": "soccer/eng.4",       # English League Two
        "fa_cup": "soccer/eng.fa",          # FA Cup
        "efl_cup": "soccer/eng.league_cup", # EFL Cup / Carabao Cup
        "laliga": "soccer/esp.1",           # La Liga (Spain)
        "laliga2": "soccer/esp.2",          # La Liga 2
        "copa_del_rey": "soccer/esp.copa_del_rey",
        "bundesliga": "soccer/ger.1",       # Bundesliga (Germany)
        "bundesliga2": "soccer/ger.2",      # 2. Bundesliga
        "dfb_pokal": "soccer/ger.dfb_pokal",
        "seriea": "soccer/ita.1",           # Serie A (Italy)
        "serieb": "soccer/ita.2",           # Serie B
        "coppa_italia": "soccer/ita.coppa_italia",
        "ligue1": "soccer/fra.1",           # Ligue 1 (France)
        "ligue2": "soccer/fra.2",           # Ligue 2
        "coupe_de_france": "soccer/fra.coupe_de_france",
        "eredivisie": "soccer/ned.1",       # Eredivisie (Netherlands)
        "liga_portugal": "soccer/por.1",    # Liga Portugal
        "scottish": "soccer/sco.1",         # Scottish Premiership
        "belgian": "soccer/bel.1",          # Belgian Pro League
        "turkish": "soccer/tur.1",          # Turkish Super Lig
        "russian": "soccer/rus.1",          # Russian Premier League
        "greek": "soccer/gre.1",            # Greek Super League
        "austrian": "soccer/aut.1",         # Austrian Bundesliga
        "swiss": "soccer/sui.1",            # Swiss Super League
        "danish": "soccer/den.1",           # Danish Superliga
        "norwegian": "soccer/nor.1",        # Norwegian Eliteserien
        "swedish": "soccer/swe.1",          # Swedish Allsvenskan
        "polish": "soccer/pol.1",           # Polish Ekstraklasa
        "czech": "soccer/cze.1",            # Czech First League
        "ukrainian": "soccer/ukr.1",        # Ukrainian Premier League
        
        # ==================== SOCCER - UEFA COMPETITIONS ====================
        "ucl": "soccer/uefa.champions",           # UEFA Champions League
        "europa": "soccer/uefa.europa",           # UEFA Europa League
        "conference": "soccer/uefa.europa.conf", # UEFA Conference League
        "nations_league": "soccer/uefa.nations",  # UEFA Nations League
        "euro_qualifiers": "soccer/uefa.euroq",   # Euro Qualifiers
        "euros": "soccer/uefa.euro",              # UEFA European Championship
        
        # ==================== SOCCER - AMERICAS ====================
        "mls": "soccer/usa.1",              # MLS
        "usl": "soccer/usa.usl.1",          # USL Championship
        "nwsl": "soccer/usa.nwsl",          # NWSL (Women's)
        "us_open_cup": "soccer/usa.open",   # US Open Cup
        "brazilian": "soccer/bra.1",        # Brasileirao Serie A
        "brazilian_b": "soccer/bra.2",      # Brasileirao Serie B
        "copa_brazil": "soccer/bra.copa_do_brazil",
        "libertadores": "soccer/conmebol.libertadores", # Copa Libertadores
        "sudamericana": "soccer/conmebol.sudamericana", # Copa Sudamericana
        "argentine": "soccer/arg.1",        # Argentine Primera Division
        "mexican": "soccer/mex.1",          # Liga MX
        "liga_mx_cup": "soccer/mex.copa_mx",
        "colombian": "soccer/col.1",        # Colombian Primera A
        "chilean": "soccer/chi.1",          # Chilean Primera Division
        "peruvian": "soccer/per.1",         # Peruvian Primera Division
        "copa_america": "soccer/conmebol.america", # Copa America
        
        # ==================== SOCCER - OTHER ====================
        "saudi": "soccer/sau.1",            # Saudi Pro League
        "japanese": "soccer/jpn.1",         # J1 League
        "korean": "soccer/kor.1",           # K League 1
        "chinese": "soccer/chn.1",          # Chinese Super League
        "australian_aleague": "soccer/aus.1", # A-League
        "indian": "soccer/ind.1",           # Indian Super League
        "afc_champions": "soccer/afc.champions", # AFC Champions League
        
        # ==================== SOCCER - INTERNATIONAL ====================
        "world_cup": "soccer/fifa.world",   # FIFA World Cup
        "world_cup_qualifiers": "soccer/fifa.worldq", # World Cup Qualifiers
        "club_world_cup": "soccer/fifa.cwc", # FIFA Club World Cup
        "womens_world_cup": "soccer/fifa.wwc", # FIFA Women's World Cup
        "concacaf_gold": "soccer/concacaf.gold", # CONCACAF Gold Cup
        "concacaf_nations": "soccer/concacaf.nations_league", # CONCACAF Nations League
        
        # ==================== TENNIS ====================
        "atp": "tennis/atp",
        "wta": "tennis/wta",
        "australian_open": "tennis/aus_open",
        "french_open": "tennis/roland_garros",
        "wimbledon": "tennis/wimbledon",
        "us_open_tennis": "tennis/us_open",
        "davis_cup": "tennis/davis_cup",
        
        # ==================== GOLF ====================
        "pga": "golf/pga",
        "lpga": "golf/lpga",
        "european_tour": "golf/euro",
        "masters": "golf/masters",
        "us_open_golf": "golf/us_open",
        "british_open": "golf/british_open",
        "pga_championship": "golf/pga_champ",
        "liv_golf": "golf/liv",
        
        # ==================== MMA / COMBAT SPORTS ====================
        "ufc": "mma/ufc",
        "bellator": "mma/bellator",
        "pfl": "mma/pfl",
        "one_championship": "mma/one",
        "boxing": "boxing/boxing",
        
        # ==================== MOTORSPORTS ====================
        "f1": "racing/f1",
        "nascar": "racing/nascar",
        "indycar": "racing/irl",
        "motogp": "racing/motogp",
        
        # ==================== OTHER SPORTS ====================
        "rugby_union": "rugby/rugby-union",
        "rugby_league": "rugby-league/nrl",
        "cricket": "cricket/cricket",
        "afl": "australian-football/afl",
        
        # Legacy mappings for backwards compatibility
        "soccer": "soccer/usa.1",
        "tennis": "tennis/atp",
        "mma": "mma/ufc",
        "golf": "golf/pga",
    }
    
    # Human-readable names for leagues (for UI display)
    LEAGUE_DISPLAY_NAMES = {
        # Basketball
        "nba": "NBA",
        "wnba": "WNBA",
        "ncaab": "College Basketball (M)",
        "ncaaw": "College Basketball (W)",
        "nba_gleague": "NBA G League",
        "euroleague": "EuroLeague",
        "eurocup": "EuroCup",
        "spanish_acb": "Spanish ACB",
        "australian_nbl": "Australian NBL",
        "fiba": "FIBA World Cup",
        
        # Football
        "nfl": "NFL",
        "ncaaf": "College Football",
        "cfl": "CFL",
        "xfl": "XFL",
        "usfl": "USFL",
        
        # Baseball
        "mlb": "MLB",
        "ncaa_baseball": "College Baseball",
        "npb": "NPB (Japan)",
        "kbo": "KBO (Korea)",
        "mexican_baseball": "Mexican Baseball",
        
        # Hockey
        "nhl": "NHL",
        "ahl": "AHL",
        "khl": "KHL (Russia)",
        "shl": "SHL (Sweden)",
        "ncaa_hockey": "College Hockey",
        "iihf": "IIHF World Championship",
        
        # Soccer - England
        "epl": "Premier League",
        "championship": "Championship",
        "league_one": "League One",
        "league_two": "League Two",
        "fa_cup": "FA Cup",
        "efl_cup": "EFL Cup",
        
        # Soccer - Spain
        "laliga": "La Liga",
        "laliga2": "La Liga 2",
        "copa_del_rey": "Copa del Rey",
        
        # Soccer - Germany
        "bundesliga": "Bundesliga",
        "bundesliga2": "2. Bundesliga",
        "dfb_pokal": "DFB-Pokal",
        
        # Soccer - Italy
        "seriea": "Serie A",
        "serieb": "Serie B",
        "coppa_italia": "Coppa Italia",
        
        # Soccer - France
        "ligue1": "Ligue 1",
        "ligue2": "Ligue 2",
        "coupe_de_france": "Coupe de France",
        
        # Soccer - Other Europe
        "eredivisie": "Eredivisie",
        "liga_portugal": "Liga Portugal",
        "scottish": "Scottish Premiership",
        "belgian": "Belgian Pro League",
        "turkish": "Turkish Super Lig",
        "russian": "Russian Premier League",
        "greek": "Greek Super League",
        "austrian": "Austrian Bundesliga",
        "swiss": "Swiss Super League",
        "danish": "Danish Superliga",
        "norwegian": "Eliteserien",
        "swedish": "Allsvenskan",
        "polish": "Ekstraklasa",
        "czech": "Czech First League",
        "ukrainian": "Ukrainian Premier League",
        
        # Soccer - UEFA
        "ucl": "Champions League",
        "europa": "Europa League",
        "conference": "Conference League",
        "nations_league": "Nations League",
        "euro_qualifiers": "Euro Qualifiers",
        "euros": "UEFA Euros",
        
        # Soccer - Americas
        "mls": "MLS",
        "usl": "USL Championship",
        "nwsl": "NWSL",
        "us_open_cup": "US Open Cup",
        "brazilian": "Brasileirao Serie A",
        "brazilian_b": "Brasileirao Serie B",
        "copa_brazil": "Copa do Brasil",
        "libertadores": "Copa Libertadores",
        "sudamericana": "Copa Sudamericana",
        "argentine": "Argentine Primera",
        "mexican": "Liga MX",
        "liga_mx_cup": "Copa MX",
        "colombian": "Colombian Primera A",
        "chilean": "Chilean Primera",
        "peruvian": "Peruvian Primera",
        "copa_america": "Copa America",
        
        # Soccer - Other
        "saudi": "Saudi Pro League",
        "japanese": "J1 League",
        "korean": "K League 1",
        "chinese": "Chinese Super League",
        "australian_aleague": "A-League",
        "indian": "Indian Super League",
        "afc_champions": "AFC Champions League",
        
        # Soccer - International
        "world_cup": "World Cup",
        "world_cup_qualifiers": "World Cup Qualifiers",
        "club_world_cup": "Club World Cup",
        "womens_world_cup": "Women's World Cup",
        "concacaf_gold": "Gold Cup",
        "concacaf_nations": "CONCACAF Nations League",
        
        # Tennis
        "atp": "ATP Tour",
        "wta": "WTA Tour",
        "australian_open": "Australian Open",
        "french_open": "French Open",
        "wimbledon": "Wimbledon",
        "us_open_tennis": "US Open (Tennis)",
        "davis_cup": "Davis Cup",
        
        # Golf
        "pga": "PGA Tour",
        "lpga": "LPGA Tour",
        "european_tour": "DP World Tour",
        "masters": "The Masters",
        "us_open_golf": "US Open (Golf)",
        "british_open": "The Open Championship",
        "pga_championship": "PGA Championship",
        "liv_golf": "LIV Golf",
        
        # MMA/Combat
        "ufc": "UFC",
        "bellator": "Bellator MMA",
        "pfl": "PFL",
        "one_championship": "ONE Championship",
        "boxing": "Boxing",
        
        # Motorsports
        "f1": "Formula 1",
        "nascar": "NASCAR",
        "indycar": "IndyCar",
        "motogp": "MotoGP",
        
        # Other
        "rugby_union": "Rugby Union",
        "rugby_league": "Rugby League",
        "cricket": "Cricket",
        "afl": "AFL",
    }
    
    # Categorize sports for the UI
    SPORT_CATEGORIES = {
        "basketball": ["nba", "wnba", "ncaab", "ncaaw", "nba_gleague", "euroleague", "eurocup", "spanish_acb", "australian_nbl", "fiba"],
        "football": ["nfl", "ncaaf", "cfl", "xfl", "usfl"],
        "baseball": ["mlb", "ncaa_baseball", "npb", "kbo", "mexican_baseball"],
        "hockey": ["nhl", "ahl", "khl", "shl", "ncaa_hockey", "iihf"],
        # Combined soccer category for convenience - includes major leagues
        "soccer": ["epl", "laliga", "bundesliga", "seriea", "ligue1", "mls", "ucl", "europa", "conference"],
        "soccer_england": ["epl", "championship", "league_one", "league_two", "fa_cup", "efl_cup"],
        "soccer_spain": ["laliga", "laliga2", "copa_del_rey"],
        "soccer_germany": ["bundesliga", "bundesliga2", "dfb_pokal"],
        "soccer_italy": ["seriea", "serieb", "coppa_italia"],
        "soccer_france": ["ligue1", "ligue2", "coupe_de_france"],
        "soccer_europe_other": ["eredivisie", "liga_portugal", "scottish", "belgian", "turkish", "russian", "greek", "austrian", "swiss", "danish", "norwegian", "swedish", "polish", "czech", "ukrainian"],
        "soccer_uefa": ["ucl", "europa", "conference", "nations_league", "euro_qualifiers", "euros"],
        "soccer_americas": ["mls", "usl", "nwsl", "us_open_cup", "brazilian", "brazilian_b", "copa_brazil", "libertadores", "sudamericana", "argentine", "mexican", "liga_mx_cup", "colombian", "chilean", "peruvian", "copa_america"],
        "soccer_asia": ["saudi", "japanese", "korean", "chinese", "australian_aleague", "indian", "afc_champions"],
        "soccer_international": ["world_cup", "world_cup_qualifiers", "club_world_cup", "womens_world_cup", "concacaf_gold", "concacaf_nations"],
        "tennis": ["atp", "wta", "australian_open", "french_open", "wimbledon", "us_open_tennis", "davis_cup"],
        "golf": ["pga", "lpga", "european_tour", "masters", "us_open_golf", "british_open", "pga_championship", "liv_golf"],
        "combat": ["ufc", "bellator", "pfl", "one_championship", "boxing"],
        "motorsports": ["f1", "nascar", "indycar", "motogp"],
        # Note: cricket removed - ESPN API no longer supports cricket scoreboard
        "other": ["rugby_union", "rugby_league", "afl"],
    }
    
    # Group IDs for fetching ALL games instead of just Top 25/filtered
    SPORT_GROUPS = {
        # College sports need specific group IDs
        "ncaab": "50",       # Division I Men's Basketball
        "ncaaw": "50",       # Division I Women's Basketball
        "ncaaf": "80",       # FBS Football
        "ncaa_baseball": "50",
        "ncaa_hockey": "50",
    }
    
    # Default segment mappings by sport type
    # Individual league overrides can be added as needed
    SEGMENT_MAPPING = {
        # Basketball - quarters
        "nba": {1: "q1", 2: "q2", 3: "q3", 4: "q4"},
        "wnba": {1: "q1", 2: "q2", 3: "q3", 4: "q4"},
        "nba_gleague": {1: "q1", 2: "q2", 3: "q3", 4: "q4"},
        "euroleague": {1: "q1", 2: "q2", 3: "q3", 4: "q4"},
        "eurocup": {1: "q1", 2: "q2", 3: "q3", 4: "q4"},
        "spanish_acb": {1: "q1", 2: "q2", 3: "q3", 4: "q4"},
        "australian_nbl": {1: "q1", 2: "q2", 3: "q3", 4: "q4"},
        "fiba": {1: "q1", 2: "q2", 3: "q3", 4: "q4"},
        "ncaab": {1: "h1", 2: "h2"},  # College basketball uses halves
        "ncaaw": {1: "h1", 2: "h2"},
        
        # Football - quarters
        "nfl": {1: "q1", 2: "q2", 3: "q3", 4: "q4"},
        "ncaaf": {1: "q1", 2: "q2", 3: "q3", 4: "q4"},
        "cfl": {1: "q1", 2: "q2", 3: "q3", 4: "q4"},
        "xfl": {1: "q1", 2: "q2", 3: "q3", 4: "q4"},
        "usfl": {1: "q1", 2: "q2", 3: "q3", 4: "q4"},
        
        # Hockey - periods
        "nhl": {1: "p1", 2: "p2", 3: "p3"},
        "ahl": {1: "p1", 2: "p2", 3: "p3"},
        "khl": {1: "p1", 2: "p2", 3: "p3"},
        "shl": {1: "p1", 2: "p2", 3: "p3"},
        "ncaa_hockey": {1: "p1", 2: "p2", 3: "p3"},
        "iihf": {1: "p1", 2: "p2", 3: "p3"},
        
        # Baseball - innings (handled dynamically)
        "mlb": {},
        "ncaa_baseball": {},
        "npb": {},
        "kbo": {},
        "mexican_baseball": {},
        
        # Tennis - sets
        "atp": {1: "set_1", 2: "set_2", 3: "set_3", 4: "set_4", 5: "set_5"},
        "wta": {1: "set_1", 2: "set_2", 3: "set_3"},
        "australian_open": {1: "set_1", 2: "set_2", 3: "set_3", 4: "set_4", 5: "set_5"},
        "french_open": {1: "set_1", 2: "set_2", 3: "set_3", 4: "set_4", 5: "set_5"},
        "wimbledon": {1: "set_1", 2: "set_2", 3: "set_3", 4: "set_4", 5: "set_5"},
        "us_open_tennis": {1: "set_1", 2: "set_2", 3: "set_3", 4: "set_4", 5: "set_5"},
        "davis_cup": {1: "set_1", 2: "set_2", 3: "set_3", 4: "set_4", 5: "set_5"},
        
        # MMA - rounds
        "ufc": {1: "r1", 2: "r2", 3: "r3", 4: "r4", 5: "r5"},
        "bellator": {1: "r1", 2: "r2", 3: "r3", 4: "r4", 5: "r5"},
        "pfl": {1: "r1", 2: "r2", 3: "r3", 4: "r4", 5: "r5"},
        "one_championship": {1: "r1", 2: "r2", 3: "r3", 4: "r4", 5: "r5"},
        "boxing": {1: "r1", 2: "r2", 3: "r3", 4: "r4", 5: "r5", 6: "r6", 7: "r7", 8: "r8", 9: "r9", 10: "r10", 11: "r11", 12: "r12"},
        
        # Golf - no periods, uses holes
        "pga": {},
        "lpga": {},
        "european_tour": {},
        "masters": {},
        "us_open_golf": {},
        "british_open": {},
        "pga_championship": {},
        "liv_golf": {},
        
        # Motorsports - laps
        "f1": {},
        "nascar": {},
        "indycar": {},
        "motogp": {},
    }
    
    # All soccer leagues use halves - generate dynamically
    SOCCER_SEGMENT = {1: "h1", 2: "h2"}
    
    # Add all soccer leagues to segment mapping
    for category in ["soccer_england", "soccer_spain", "soccer_germany", "soccer_italy", 
                     "soccer_france", "soccer_europe_other", "soccer_uefa", "soccer_americas",
                     "soccer_asia", "soccer_international"]:
        for league in SPORT_CATEGORIES.get(category, []):
            SEGMENT_MAPPING[league] = SOCCER_SEGMENT
    
    # Sports where clock counts UP instead of DOWN (all soccer leagues)
    CLOCK_COUNTUP_SPORTS = set()
    for category in ["soccer_england", "soccer_spain", "soccer_germany", "soccer_italy", 
                     "soccer_france", "soccer_europe_other", "soccer_uefa", "soccer_americas",
                     "soccer_asia", "soccer_international"]:
        for league in SPORT_CATEGORIES.get(category, []):
            CLOCK_COUNTUP_SPORTS.add(league)
    
    @classmethod
    def get_available_leagues(cls) -> list[dict]:
        """
        Returns list of all available leagues with display names.
        Used by the frontend to populate league selection dropdowns.
        """
        leagues = []
        for sport_key, display_name in cls.LEAGUE_DISPLAY_NAMES.items():
            if sport_key in cls.SPORT_ENDPOINTS:
                leagues.append({
                    "id": sport_key,
                    "name": display_name,
                    "is_soccer": sport_key in cls.CLOCK_COUNTUP_SPORTS,
                })
        return leagues
    
    @classmethod
    def get_soccer_leagues(cls) -> list[dict]:
        """
        Returns only soccer leagues for the soccer league selector.
        """
        soccer_leagues = []
        soccer_keys = (
            cls.SPORT_CATEGORIES.get("soccer_england", []) +
            cls.SPORT_CATEGORIES.get("soccer_spain", []) +
            cls.SPORT_CATEGORIES.get("soccer_germany", []) +
            cls.SPORT_CATEGORIES.get("soccer_italy", []) +
            cls.SPORT_CATEGORIES.get("soccer_france", []) +
            cls.SPORT_CATEGORIES.get("soccer_europe_other", []) +
            cls.SPORT_CATEGORIES.get("soccer_uefa", []) +
            cls.SPORT_CATEGORIES.get("soccer_americas", []) +
            cls.SPORT_CATEGORIES.get("soccer_asia", []) +
            cls.SPORT_CATEGORIES.get("soccer_international", [])
        )
        for sport_key in soccer_keys:
            if sport_key in cls.LEAGUE_DISPLAY_NAMES:
                soccer_leagues.append({
                    "id": sport_key,
                    "name": cls.LEAGUE_DISPLAY_NAMES[sport_key],
                })
        return soccer_leagues
    
    @classmethod
    def get_sport_type(cls, league_key: str) -> str:
        """Returns the sport type for a league key (basketball, soccer, football, etc.)."""
        for category, leagues in cls.SPORT_CATEGORIES.items():
            if league_key in leagues:
                if category.startswith("soccer"):
                    return "soccer"
                return category
        return "other"

    @classmethod
    def get_leagues_by_category(cls, category: str) -> list[dict]:
        """
        Returns leagues for a specific sport category.

        Args:
            category: Category key (basketball, football, hockey, baseball,
                     soccer_england, tennis, golf, combat, motorsports, etc.)

        Returns:
            List of leagues in that category with league_key and display_name
        """
        leagues = []
        category_keys = cls.SPORT_CATEGORIES.get(category, [])
        for sport_key in category_keys:
            if sport_key in cls.LEAGUE_DISPLAY_NAMES:
                leagues.append({
                    "league_key": sport_key,
                    "display_name": cls.LEAGUE_DISPLAY_NAMES[sport_key],
                    "sport_type": cls.get_sport_type(sport_key),
                    "category": category,
                })
        return leagues
    
    @classmethod
    def get_all_categories(cls) -> list[dict]:
        """
        Returns all available sport categories with their display names.
        Used by frontend to build category tabs/dropdowns.
        """
        category_display = {
            "basketball": "Basketball",
            "football": "Football",
            "baseball": "Baseball",
            "hockey": "Hockey",
            "soccer": "Soccer (Major Leagues)",
            "soccer_england": "Soccer - England",
            "soccer_spain": "Soccer - Spain",
            "soccer_germany": "Soccer - Germany",
            "soccer_italy": "Soccer - Italy",
            "soccer_france": "Soccer - France",
            "soccer_europe_other": "Soccer - Other Europe",
            "soccer_uefa": "Soccer - UEFA",
            "soccer_americas": "Soccer - Americas",
            "soccer_asia": "Soccer - Asia/Other",
            "soccer_international": "Soccer - International",
            "tennis": "Tennis",
            "golf": "Golf",
            "combat": "MMA / Combat",
            "motorsports": "Motorsports",
            "other": "Other Sports",
        }

        return [
            {
                "category": cat,
                "display_name": category_display.get(cat, cat.title()),
                "leagues": cls.get_leagues_by_category(cat)
            }
            for cat in cls.SPORT_CATEGORIES.keys()
        ]
    
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
        Results are cached for 30 seconds to reduce API calls.
        
        For college sports (ncaab, ncaaf), uses groups parameter to fetch
        ALL Division I games, not just Top 25 ranked teams.
        
        Args:
            sport: Sport identifier (nba, nfl, mlb, nhl, ncaab, etc.)
        
        Returns:
            List of game data dictionaries
        """
        # Check cache first
        cache_key = f"scoreboard:{sport.lower()}"
        cached = await espn_cache.get(cache_key)
        if cached is not None:
            logger.debug(f"Cache hit for {sport} scoreboard")
            return cached
        
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
            
            # Cache the result for 30 seconds
            await espn_cache.set(cache_key, events, ttl=30)
            
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
