"""
Unit tests for MarketMatcher.
Tests ESPN-to-Polymarket market matching algorithms.
"""

import pytest
from datetime import datetime, timezone, timedelta

from src.services.market_matcher import (
    MarketMatcher,
    MatchResult,
    match_by_abbreviation,
    match_by_team_name,
    match_by_time_window,
)


class TestAbbreviationMatching:
    """Tests for team abbreviation matching strategy."""
    
    def test_exact_abbreviation_match(self):
        """
        Test matching when both team abbreviations appear in market title.
        """
        espn_game = {
            "competitions": [{
                "competitors": [
                    {"homeAway": "home", "team": {"abbreviation": "LAL", "displayName": "Los Angeles Lakers"}},
                    {"homeAway": "away", "team": {"abbreviation": "BOS", "displayName": "Boston Celtics"}},
                ]
            }]
        }
        
        markets = [
            {
                "condition_id": "cond-123",
                "token_id": "token-456",
                "question": "LAL vs BOS - Lakers to win?",
            }
        ]
        
        result = match_by_abbreviation(espn_game, markets)
        
        assert result is not None
        assert result.condition_id == "cond-123"
        assert result.confidence >= 0.9
    
    def test_no_match_partial_abbreviation(self):
        """
        Test that partial abbreviation matches are rejected.
        """
        espn_game = {
            "competitions": [{
                "competitors": [
                    {"homeAway": "home", "team": {"abbreviation": "LAL", "displayName": "Los Angeles Lakers"}},
                    {"homeAway": "away", "team": {"abbreviation": "BOS", "displayName": "Boston Celtics"}},
                ]
            }]
        }
        
        markets = [
            {
                "condition_id": "cond-789",
                "token_id": "token-012",
                "question": "LAL to win championship?",  # Only LAL, not BOS
            }
        ]
        
        result = match_by_abbreviation(espn_game, markets)
        
        assert result is None
    
    def test_case_insensitive_matching(self):
        """
        Test that abbreviation matching is case insensitive.
        """
        espn_game = {
            "competitions": [{
                "competitors": [
                    {"homeAway": "home", "team": {"abbreviation": "NYK", "displayName": "New York Knicks"}},
                    {"homeAway": "away", "team": {"abbreviation": "MIA", "displayName": "Miami Heat"}},
                ]
            }]
        }
        
        markets = [
            {
                "condition_id": "cond-abc",
                "token_id": "token-def",
                "question": "nyk vs mia - Knicks to win?",  # lowercase
            }
        ]
        
        result = match_by_abbreviation(espn_game, markets)
        
        assert result is not None
        assert result.condition_id == "cond-abc"


class TestTeamNameMatching:
    """Tests for full team name matching strategy."""
    
    def test_full_name_match(self):
        """
        Test matching when full team names appear in market title.
        """
        espn_game = {
            "competitions": [{
                "competitors": [
                    {"homeAway": "home", "team": {"abbreviation": "LAL", "displayName": "Los Angeles Lakers"}},
                    {"homeAway": "away", "team": {"abbreviation": "BOS", "displayName": "Boston Celtics"}},
                ]
            }]
        }
        
        markets = [
            {
                "condition_id": "cond-name",
                "token_id": "token-name",
                "question": "Will the Los Angeles Lakers beat the Boston Celtics?",
            }
        ]
        
        result = match_by_team_name(espn_game, markets)
        
        assert result is not None
        assert result.condition_id == "cond-name"
        assert result.confidence >= 0.85
    
    def test_partial_name_no_match(self):
        """
        Test that partial team names do not match.
        """
        espn_game = {
            "competitions": [{
                "competitors": [
                    {"homeAway": "home", "team": {"abbreviation": "LAL", "displayName": "Los Angeles Lakers"}},
                    {"homeAway": "away", "team": {"abbreviation": "BOS", "displayName": "Boston Celtics"}},
                ]
            }]
        }
        
        markets = [
            {
                "condition_id": "cond-partial",
                "token_id": "token-partial",
                "question": "Lakers championship odds",  # Only Lakers, not Celtics
            }
        ]
        
        result = match_by_team_name(espn_game, markets)
        
        assert result is None


class TestTimeWindowMatching:
    """Tests for time window + partial match strategy."""
    
    def test_time_window_match(self):
        """
        Test matching when game time is within market window and keywords match.
        """
        game_time = datetime.now(timezone.utc) + timedelta(hours=2)
        market_end = game_time + timedelta(hours=3)
        
        espn_game = {
            "date": game_time.isoformat(),
            "competitions": [{
                "competitors": [
                    {"homeAway": "home", "team": {"abbreviation": "GSW", "displayName": "Golden State Warriors"}},
                    {"homeAway": "away", "team": {"abbreviation": "PHX", "displayName": "Phoenix Suns"}},
                ]
            }]
        }
        
        markets = [
            {
                "condition_id": "cond-time",
                "token_id": "token-time",
                "question": "Warriors vs Suns game outcome",
                "end_date_iso": market_end.isoformat(),
            }
        ]
        
        result = match_by_time_window(espn_game, markets)
        
        assert result is not None
        assert result.condition_id == "cond-time"
        assert result.confidence >= 0.7
    
    def test_time_window_too_far(self):
        """
        Test that games outside time window do not match.
        """
        game_time = datetime.now(timezone.utc) + timedelta(hours=2)
        market_end = game_time + timedelta(days=5)  # 5 days later - too far
        
        espn_game = {
            "date": game_time.isoformat(),
            "competitions": [{
                "competitors": [
                    {"homeAway": "home", "team": {"abbreviation": "GSW", "displayName": "Golden State Warriors"}},
                    {"homeAway": "away", "team": {"abbreviation": "PHX", "displayName": "Phoenix Suns"}},
                ]
            }]
        }
        
        markets = [
            {
                "condition_id": "cond-far",
                "token_id": "token-far",
                "question": "Warriors championship odds",
                "end_date_iso": market_end.isoformat(),
            }
        ]
        
        result = match_by_time_window(espn_game, markets)
        
        assert result is None


class TestCombinedMatcher:
    """Tests for the combined matching algorithm."""
    
    @pytest.fixture
    def matcher(self):
        """Create MarketMatcher instance."""
        return MarketMatcher()
    
    @pytest.mark.asyncio
    async def test_combined_returns_best_match(self, matcher):
        """
        Test that combined matcher returns highest confidence match.
        """
        espn_game = {
            "date": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            "competitions": [{
                "competitors": [
                    {"homeAway": "home", "team": {"abbreviation": "LAL", "displayName": "Los Angeles Lakers"}},
                    {"homeAway": "away", "team": {"abbreviation": "BOS", "displayName": "Boston Celtics"}},
                ]
            }]
        }
        
        markets = [
            {
                "condition_id": "cond-exact",
                "token_id": "token-exact",
                "question": "LAL vs BOS - Lakers to win?",
                "end_date_iso": (datetime.now(timezone.utc) + timedelta(hours=4)).isoformat(),
            }
        ]
        
        result = await matcher.match(espn_game, markets)
        
        assert result is not None
        assert result.confidence >= 0.7
    
    @pytest.mark.asyncio
    async def test_combined_returns_none_no_match(self, matcher):
        """
        Test that combined matcher returns None when no strategies match.
        """
        espn_game = {
            "date": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            "competitions": [{
                "competitors": [
                    {"homeAway": "home", "team": {"abbreviation": "LAL", "displayName": "Los Angeles Lakers"}},
                    {"homeAway": "away", "team": {"abbreviation": "BOS", "displayName": "Boston Celtics"}},
                ]
            }]
        }
        
        markets = [
            {
                "condition_id": "cond-unrelated",
                "token_id": "token-unrelated",
                "question": "Will Bitcoin reach $100k?",
                "end_date_iso": (datetime.now(timezone.utc) + timedelta(hours=4)).isoformat(),
            }
        ]
        
        result = await matcher.match(espn_game, markets)
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_confidence_threshold(self, matcher):
        """
        Test that matches below confidence threshold are rejected.
        """
        matcher.min_confidence = 0.95  # Very high threshold
        
        espn_game = {
            "date": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            "competitions": [{
                "competitors": [
                    {"homeAway": "home", "team": {"abbreviation": "LAL", "displayName": "Los Angeles Lakers"}},
                    {"homeAway": "away", "team": {"abbreviation": "BOS", "displayName": "Boston Celtics"}},
                ]
            }]
        }
        
        markets = [
            {
                "condition_id": "cond-low",
                "token_id": "token-low",
                "question": "Lakers Celtics game",  # Partial match only
                "end_date_iso": (datetime.now(timezone.utc) + timedelta(hours=4)).isoformat(),
            }
        ]
        
        result = await matcher.match(espn_game, markets)
        
        # May return None if no strategy exceeds 0.95 confidence
        if result:
            assert result.confidence >= 0.95


class TestSegmentNormalization:
    """Tests for segment normalization across sports."""
    
    def test_nba_quarters(self):
        """Test NBA quarter normalization."""
        from src.services.market_matcher import normalize_segment
        
        assert normalize_segment(1, "nba") == "q1"
        assert normalize_segment(2, "nba") == "q2"
        assert normalize_segment(3, "nba") == "q3"
        assert normalize_segment(4, "nba") == "q4"
        assert normalize_segment(5, "nba") == "ot"
    
    def test_nfl_quarters(self):
        """Test NFL quarter normalization."""
        from src.services.market_matcher import normalize_segment
        
        assert normalize_segment(1, "nfl") == "q1"
        assert normalize_segment(4, "nfl") == "q4"
        assert normalize_segment(5, "nfl") == "ot"
    
    def test_nhl_periods(self):
        """Test NHL period normalization."""
        from src.services.market_matcher import normalize_segment
        
        assert normalize_segment(1, "nhl") == "p1"
        assert normalize_segment(2, "nhl") == "p2"
        assert normalize_segment(3, "nhl") == "p3"
        assert normalize_segment(4, "nhl") == "ot"
    
    def test_mlb_innings(self):
        """Test MLB inning normalization."""
        from src.services.market_matcher import normalize_segment
        
        assert normalize_segment(1, "mlb") == "inning_1"
        assert normalize_segment(7, "mlb") == "inning_7"
        assert normalize_segment(10, "mlb") == "inning_10"
