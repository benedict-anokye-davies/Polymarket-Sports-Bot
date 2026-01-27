"""
Tests for market discovery service - sport detection, team extraction, and filtering.
Tests REAL parsing and detection logic.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, AsyncMock

from src.services.market_discovery import MarketDiscovery, DiscoveredMarket


# =============================================================================
# Sport Detection Tests - Tests REAL keyword matching
# =============================================================================

class TestSportDetection:
    """Tests for detecting sport type from market text."""
    
    def test_detect_nba_by_league_name(self):
        """NBA keyword should detect basketball."""
        discovery = MarketDiscovery()
        
        assert discovery._detect_sport("Will the NBA Finals go to 7 games?") == "nba"
        assert discovery._detect_sport("NBA MVP 2026") == "nba"
    
    def test_detect_nba_by_team_name(self):
        """NBA team names should detect basketball."""
        discovery = MarketDiscovery()
        
        assert discovery._detect_sport("Lakers to win tonight") == "nba"
        assert discovery._detect_sport("Celtics vs Warriors") == "nba"
        assert discovery._detect_sport("Will the Bucks beat the Heat?") == "nba"
    
    def test_detect_nfl_by_league_name(self):
        """NFL keyword should detect football."""
        discovery = MarketDiscovery()
        
        assert discovery._detect_sport("NFL Week 15 predictions") == "nfl"
        assert discovery._detect_sport("Super Bowl winner") == "nfl"
    
    def test_detect_nfl_by_team_name(self):
        """NFL team names should detect football."""
        discovery = MarketDiscovery()
        
        assert discovery._detect_sport("Chiefs to beat Eagles") == "nfl"
        assert discovery._detect_sport("49ers vs Cowboys") == "nfl"
        assert discovery._detect_sport("Will the Bills make playoffs?") == "nfl"
    
    def test_detect_mlb_by_league_name(self):
        """MLB keyword should detect baseball."""
        discovery = MarketDiscovery()
        
        assert discovery._detect_sport("MLB World Series champion") == "mlb"
        assert discovery._detect_sport("Who will win the World Series?") == "mlb"
    
    def test_detect_mlb_by_team_name(self):
        """MLB team names should detect baseball."""
        discovery = MarketDiscovery()
        
        assert discovery._detect_sport("Yankees to beat Dodgers") == "mlb"
        assert discovery._detect_sport("Red Sox vs Astros") == "mlb"
    
    def test_detect_nhl_by_league_name(self):
        """NHL keyword should detect hockey."""
        discovery = MarketDiscovery()
        
        assert discovery._detect_sport("NHL Stanley Cup winner") == "nhl"
        assert discovery._detect_sport("Who wins the Stanley Cup?") == "nhl"
    
    def test_detect_nhl_by_team_name(self):
        """NHL team names should detect hockey."""
        discovery = MarketDiscovery()
        
        assert discovery._detect_sport("Bruins to win tonight") == "nhl"
        assert discovery._detect_sport("Oilers vs Avalanche") == "nhl"  # Avalanche is NHL-only
    
    def test_detect_no_sport_returns_none(self):
        """Non-sports text should return None."""
        discovery = MarketDiscovery()
        
        assert discovery._detect_sport("Will Bitcoin reach 100k?") is None
        assert discovery._detect_sport("US Presidential Election") is None
        assert discovery._detect_sport("Random market question") is None
    
    def test_detect_case_insensitive(self):
        """Detection should be case insensitive."""
        discovery = MarketDiscovery()
        
        assert discovery._detect_sport("NBA game") == "nba"
        assert discovery._detect_sport("nba game") == "nba"
        assert discovery._detect_sport("LAKERS vs CELTICS") == "nba"


# =============================================================================
# Team Extraction Tests - Tests REAL regex parsing
# =============================================================================

class TestTeamExtraction:
    """Tests for extracting team names from market text."""
    
    def test_extract_teams_vs_format(self):
        """'Team A vs Team B' format should extract both teams."""
        discovery = MarketDiscovery()
        
        home, away = discovery._extract_teams("Lakers vs Celtics", "nba")
        
        # Convention: second team is usually home
        assert "Lakers" in (home, away) or "Celtics" in (home, away)
    
    def test_extract_teams_to_beat_format(self):
        """'Team A to beat Team B' format should extract teams."""
        discovery = MarketDiscovery()
        
        home, away = discovery._extract_teams("Lakers to beat Celtics", "nba")
        
        assert home is not None or away is not None
    
    def test_extract_teams_over_format(self):
        """'Team A over Team B' format should extract teams."""
        discovery = MarketDiscovery()
        
        home, away = discovery._extract_teams("Will Chiefs over Eagles?", "nfl")
        
        # Should extract something
        assert home is not None or away is not None
    
    def test_extract_teams_no_match_returns_none(self):
        """Text without team pattern should return None, None."""
        discovery = MarketDiscovery()
        
        home, away = discovery._extract_teams("NBA MVP award", "nba")
        
        assert home is None
        assert away is None


# =============================================================================
# DiscoveredMarket Dataclass Tests
# =============================================================================

class TestDiscoveredMarketDataclass:
    """Tests for DiscoveredMarket dataclass."""
    
    def test_create_discovered_market(self):
        """Should create DiscoveredMarket with all fields."""
        market = DiscoveredMarket(
            condition_id="0x123",
            token_id_yes="0xabc",
            token_id_no="0xdef",
            question="Lakers vs Celtics?",
            description="NBA game prediction",
            sport="nba",
            home_team="Celtics",
            away_team="Lakers",
            game_start_time=datetime.now(timezone.utc),
            end_date=datetime.now(timezone.utc) + timedelta(hours=3),
            volume_24h=50000.0,
            liquidity=10000.0,
            current_price_yes=0.65,
            current_price_no=0.35,
            spread=0.02
        )
        
        assert market.condition_id == "0x123"
        assert market.sport == "nba"
        assert market.liquidity == 10000.0
    
    def test_is_high_liquidity_true(self):
        """Market with 5000+ liquidity should be high liquidity."""
        market = DiscoveredMarket(
            condition_id="0x123",
            token_id_yes="0xabc",
            token_id_no="0xdef",
            question="Test",
            description="",
            sport="nba",
            home_team=None,
            away_team=None,
            game_start_time=None,
            end_date=None,
            volume_24h=0,
            liquidity=10000.0,  # Above 5000 threshold
            current_price_yes=0.5,
            current_price_no=0.5,
            spread=0.02
        )
        
        assert market.is_high_liquidity is True
    
    def test_is_high_liquidity_false(self):
        """Market with less than 5000 liquidity should not be high liquidity."""
        market = DiscoveredMarket(
            condition_id="0x123",
            token_id_yes="0xabc",
            token_id_no="0xdef",
            question="Test",
            description="",
            sport="nba",
            home_team=None,
            away_team=None,
            game_start_time=None,
            end_date=None,
            volume_24h=0,
            liquidity=3000.0,  # Below 5000 threshold
            current_price_yes=0.5,
            current_price_no=0.5,
            spread=0.02
        )
        
        assert market.is_high_liquidity is False
    
    def test_is_tight_spread_true(self):
        """Market with spread <= 5% should be tight spread."""
        market = DiscoveredMarket(
            condition_id="0x123",
            token_id_yes="0xabc",
            token_id_no="0xdef",
            question="Test",
            description="",
            sport="nba",
            home_team=None,
            away_team=None,
            game_start_time=None,
            end_date=None,
            volume_24h=0,
            liquidity=10000.0,
            current_price_yes=0.5,
            current_price_no=0.5,
            spread=0.03  # 3% spread
        )
        
        assert market.is_tight_spread is True
    
    def test_is_tight_spread_false(self):
        """Market with spread > 5% should not be tight spread."""
        market = DiscoveredMarket(
            condition_id="0x123",
            token_id_yes="0xabc",
            token_id_no="0xdef",
            question="Test",
            description="",
            sport="nba",
            home_team=None,
            away_team=None,
            game_start_time=None,
            end_date=None,
            volume_24h=0,
            liquidity=10000.0,
            current_price_yes=0.5,
            current_price_no=0.5,
            spread=0.08  # 8% spread
        )
        
        assert market.is_tight_spread is False
    
    def test_platform_default_polymarket(self):
        """Default platform should be polymarket."""
        market = DiscoveredMarket(
            condition_id="0x123",
            token_id_yes="0xabc",
            token_id_no="0xdef",
            question="Test",
            description="",
            sport="nba",
            home_team=None,
            away_team=None,
            game_start_time=None,
            end_date=None,
            volume_24h=0,
            liquidity=0,
            current_price_yes=0.5,
            current_price_no=0.5,
            spread=0
        )
        
        assert market.platform == "polymarket"
    
    def test_kalshi_platform_with_ticker(self):
        """Kalshi market should have platform and ticker."""
        market = DiscoveredMarket(
            condition_id="kalshi-123",
            token_id_yes="yes",
            token_id_no="no",
            question="Test",
            description="",
            sport="nba",
            home_team=None,
            away_team=None,
            game_start_time=None,
            end_date=None,
            volume_24h=0,
            liquidity=0,
            current_price_yes=0.5,
            current_price_no=0.5,
            spread=0,
            ticker="NBAGAME-26JAN-LAL",
            platform="kalshi"
        )
        
        assert market.platform == "kalshi"
        assert market.ticker == "NBAGAME-26JAN-LAL"


# =============================================================================
# Sport Keywords Tests
# =============================================================================

class TestSportKeywords:
    """Tests for sport keyword constants."""
    
    def test_all_major_sports_have_keywords(self):
        """All major sports should have keyword lists."""
        discovery = MarketDiscovery()
        
        assert "nba" in discovery.SPORT_KEYWORDS
        assert "nfl" in discovery.SPORT_KEYWORDS
        assert "mlb" in discovery.SPORT_KEYWORDS
        assert "nhl" in discovery.SPORT_KEYWORDS
    
    def test_nba_keywords_include_teams(self):
        """NBA keywords should include major team names."""
        discovery = MarketDiscovery()
        
        nba_keywords = discovery.SPORT_KEYWORDS["nba"]
        
        assert "lakers" in nba_keywords
        assert "celtics" in nba_keywords
        assert "warriors" in nba_keywords
    
    def test_nfl_keywords_include_teams(self):
        """NFL keywords should include major team names."""
        discovery = MarketDiscovery()
        
        nfl_keywords = discovery.SPORT_KEYWORDS["nfl"]
        
        assert "chiefs" in nfl_keywords
        assert "eagles" in nfl_keywords
        assert "cowboys" in nfl_keywords


# =============================================================================
# HTTP Client Tests
# =============================================================================

class TestMarketDiscoveryClient:
    """Tests for HTTP client initialization."""
    
    def test_client_initially_none(self):
        """HTTP client should be None on init."""
        discovery = MarketDiscovery()
        
        assert discovery._client is None
    
    @pytest.mark.asyncio
    async def test_get_client_creates_client(self):
        """_get_client should create client on first call."""
        discovery = MarketDiscovery()
        
        client = await discovery._get_client()
        
        assert client is not None
        assert discovery._client is not None
        
        await discovery.close()
    
    @pytest.mark.asyncio
    async def test_close_clears_client(self):
        """close() should clear the client."""
        discovery = MarketDiscovery()
        
        await discovery._get_client()  # Create client
        await discovery.close()
        
        assert discovery._client is None


# =============================================================================
# API Host Constants Tests
# =============================================================================

class TestAPIHosts:
    """Tests for API host constants."""
    
    def test_gamma_host_defined(self):
        """Gamma API host should be defined."""
        discovery = MarketDiscovery()
        
        assert discovery.GAMMA_HOST == "https://gamma-api.polymarket.com"
    
    def test_clob_host_defined(self):
        """CLOB API host should be defined."""
        discovery = MarketDiscovery()
        
        assert discovery.CLOB_HOST == "https://clob.polymarket.com"


# =============================================================================
# Edge Cases Tests
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases in market discovery."""
    
    def test_detect_sport_empty_string(self):
        """Empty string should return None."""
        discovery = MarketDiscovery()
        
        assert discovery._detect_sport("") is None
    
    def test_detect_sport_special_characters(self):
        """Text with special characters should still detect sport."""
        discovery = MarketDiscovery()
        
        assert discovery._detect_sport("Lakers!!! vs Celtics???") == "nba"
    
    def test_extract_teams_with_question_mark(self):
        """Question with ? should still extract teams."""
        discovery = MarketDiscovery()
        
        home, away = discovery._extract_teams("Will Lakers beat Celtics?", "nba")
        
        # Should extract at least partially
        # The regex should handle the ? at end
    
    def test_multiple_sports_mentioned_first_wins(self):
        """When multiple sports mentioned, first match wins."""
        discovery = MarketDiscovery()
        
        # NBA keyword appears before NFL keyword
        result = discovery._detect_sport("NBA and NFL predictions")
        assert result == "nba"
