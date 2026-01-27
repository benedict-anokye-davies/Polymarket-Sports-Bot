"""
Unit tests for MarketMatcher.
Tests ESPN-to-Polymarket market matching algorithms.

The MarketMatcher class uses instance methods for matching strategies:
- _match_by_abbreviation
- _match_by_team_name
- _match_by_time_window

These are combined in match_game_to_market() which tries each strategy
in order of reliability until one succeeds with sufficient confidence.
"""

import pytest
from datetime import datetime, timezone, timedelta

from src.services.market_matcher import MarketMatcher, MatchResult


class TestAbbreviationMatching:
    """Tests for team abbreviation matching strategy."""
    
    @pytest.fixture
    def matcher(self):
        """Create MarketMatcher instance for testing."""
        return MarketMatcher()
    
    def test_exact_abbreviation_match(self, matcher):
        """
        Test matching when both team abbreviations appear in market title.
        Uses the internal data format expected by MarketMatcher.
        """
        espn_game = {
            "home_team": {"abbreviation": "LAL", "name": "Los Angeles Lakers"},
            "away_team": {"abbreviation": "BOS", "name": "Boston Celtics"},
        }
        
        markets = [
            {
                "condition_id": "cond-123",
                "question": "LAL vs BOS - Lakers to win?",
                "tokens": [
                    {"token_id": "token-yes", "outcome": "yes"},
                    {"token_id": "token-no", "outcome": "no"},
                ]
            }
        ]
        
        result = matcher._match_by_abbreviation(espn_game, markets)
        
        assert result is not None
        assert result.condition_id == "cond-123"
        assert result.confidence >= 0.9
        assert result.strategy == "abbreviation"
    
    def test_no_match_partial_abbreviation(self, matcher):
        """
        Test that partial abbreviation matches are rejected.
        Only one team abbreviation present should not match.
        """
        espn_game = {
            "home_team": {"abbreviation": "LAL", "name": "Los Angeles Lakers"},
            "away_team": {"abbreviation": "BOS", "name": "Boston Celtics"},
        }
        
        markets = [
            {
                "condition_id": "cond-789",
                "question": "LAL to win championship?",  # Only LAL, not BOS
                "tokens": []
            }
        ]
        
        result = matcher._match_by_abbreviation(espn_game, markets)
        
        assert result is None
    
    def test_case_insensitive_matching(self, matcher):
        """
        Test that abbreviation matching is case insensitive.
        Market question in lowercase should still match.
        """
        espn_game = {
            "home_team": {"abbreviation": "NYK", "name": "New York Knicks"},
            "away_team": {"abbreviation": "MIA", "name": "Miami Heat"},
        }
        
        markets = [
            {
                "condition_id": "cond-abc",
                "question": "nyk vs mia - Knicks to win?",  # lowercase
                "tokens": [
                    {"token_id": "token-yes", "outcome": "yes"},
                    {"token_id": "token-no", "outcome": "no"},
                ]
            }
        ]
        
        result = matcher._match_by_abbreviation(espn_game, markets)
        
        assert result is not None
        assert result.condition_id == "cond-abc"
    
    def test_missing_team_data_returns_none(self, matcher):
        """
        Test that missing team data is handled gracefully.
        """
        espn_game = {
            "home_team": None,
            "away_team": {"abbreviation": "BOS", "name": "Boston Celtics"},
        }
        
        markets = [
            {
                "condition_id": "cond-123",
                "question": "LAL vs BOS",
                "tokens": []
            }
        ]
        
        result = matcher._match_by_abbreviation(espn_game, markets)
        
        assert result is None


class TestTeamNameMatching:
    """Tests for full team name matching strategy."""
    
    @pytest.fixture
    def matcher(self):
        """Create MarketMatcher instance for testing."""
        return MarketMatcher()
    
    def test_full_name_match(self, matcher):
        """
        Test matching when full team names appear in market title.
        """
        espn_game = {
            "home_team": {"abbreviation": "LAL", "name": "los angeles lakers"},
            "away_team": {"abbreviation": "BOS", "name": "boston celtics"},
        }
        
        markets = [
            {
                "condition_id": "cond-name",
                "question": "Will the Los Angeles Lakers beat the Boston Celtics?",
                "tokens": [
                    {"token_id": "token-yes", "outcome": "yes"},
                    {"token_id": "token-no", "outcome": "no"},
                ]
            }
        ]
        
        result = matcher._match_by_team_name(espn_game, markets)
        
        assert result is not None
        assert result.condition_id == "cond-name"
        assert result.confidence >= 0.8
    
    def test_partial_name_no_match(self, matcher):
        """
        Test that single team name mention does not match.
        """
        espn_game = {
            "home_team": {"abbreviation": "LAL", "name": "los angeles lakers"},
            "away_team": {"abbreviation": "BOS", "name": "boston celtics"},
        }
        
        markets = [
            {
                "condition_id": "cond-partial",
                "question": "Lakers championship odds",  # Only Lakers, not Celtics
                "tokens": []
            }
        ]
        
        result = matcher._match_by_team_name(espn_game, markets)
        
        # Should not match with only one team mentioned
        assert result is None


class TestTimeWindowMatching:
    """Tests for time window + partial match strategy."""
    
    @pytest.fixture
    def matcher(self):
        """Create MarketMatcher instance for testing."""
        return MarketMatcher()
    
    def test_time_window_match(self, matcher):
        """
        Test matching when game time is within market window and keywords match.
        """
        game_time = datetime.now(timezone.utc) + timedelta(hours=2)
        market_end = game_time + timedelta(hours=3)
        
        espn_game = {
            "start_time": game_time,
            "home_team": {"abbreviation": "GSW", "name": "golden state warriors"},
            "away_team": {"abbreviation": "PHX", "name": "phoenix suns"},
        }
        
        markets = [
            {
                "condition_id": "cond-time",
                "question": "Warriors vs Suns game outcome",
                "end_date_iso": market_end.isoformat(),
                "tokens": [
                    {"token_id": "token-yes", "outcome": "yes"},
                    {"token_id": "token-no", "outcome": "no"},
                ]
            }
        ]
        
        result = matcher._match_by_time_window(espn_game, markets)
        
        assert result is not None
        assert result.condition_id == "cond-time"
        assert result.confidence >= 0.7
        assert result.strategy == "time_window"
    
    def test_missing_start_time_returns_none(self, matcher):
        """
        Test that missing start_time returns None gracefully.
        """
        espn_game = {
            "home_team": {"abbreviation": "GSW", "name": "golden state warriors"},
            "away_team": {"abbreviation": "PHX", "name": "phoenix suns"},
            # No start_time field
        }
        
        markets = [
            {
                "condition_id": "cond-time",
                "question": "Warriors vs Suns",
                "end_date_iso": datetime.now(timezone.utc).isoformat(),
                "tokens": []
            }
        ]
        
        result = matcher._match_by_time_window(espn_game, markets)
        
        assert result is None


class TestCombinedMatcher:
    """Tests for the combined match_game_to_market method."""
    
    @pytest.fixture
    def matcher(self):
        """Create MarketMatcher instance for testing."""
        return MarketMatcher()
    
    def test_combined_returns_best_match(self, matcher):
        """
        Test that combined matcher returns match from first successful strategy.
        """
        espn_game = {
            "start_time": datetime.now(timezone.utc) + timedelta(hours=1),
            "home_team": {"abbreviation": "LAL", "name": "los angeles lakers"},
            "away_team": {"abbreviation": "BOS", "name": "boston celtics"},
        }
        
        markets = [
            {
                "condition_id": "cond-exact",
                "question": "LAL vs BOS - Lakers to win?",
                "end_date_iso": (datetime.now(timezone.utc) + timedelta(hours=4)).isoformat(),
                "tokens": [
                    {"token_id": "token-yes", "outcome": "yes"},
                    {"token_id": "token-no", "outcome": "no"},
                ]
            }
        ]
        
        result = matcher.match_game_to_market(espn_game, markets)
        
        assert result is not None
        assert result.confidence >= matcher.MIN_CONFIDENCE
    
    def test_combined_returns_none_no_match(self, matcher):
        """
        Test that combined matcher returns None when no strategies match.
        """
        espn_game = {
            "start_time": datetime.now(timezone.utc) + timedelta(hours=1),
            "home_team": {"abbreviation": "LAL", "name": "los angeles lakers"},
            "away_team": {"abbreviation": "BOS", "name": "boston celtics"},
        }
        
        markets = [
            {
                "condition_id": "cond-unrelated",
                "question": "Will Bitcoin reach $100k?",
                "end_date_iso": (datetime.now(timezone.utc) + timedelta(hours=4)).isoformat(),
                "tokens": []
            }
        ]
        
        result = matcher.match_game_to_market(espn_game, markets)
        
        assert result is None


class TestMatchResultDataclass:
    """Tests for MatchResult dataclass structure."""
    
    def test_match_result_fields(self):
        """
        Test that MatchResult has all required fields.
        """
        result = MatchResult(
            condition_id="cond-test",
            token_id_yes="token-yes",
            token_id_no="token-no",
            question="Test question?",
            confidence=0.9,
            strategy="abbreviation"
        )
        
        assert result.condition_id == "cond-test"
        assert result.token_id_yes == "token-yes"
        assert result.token_id_no == "token-no"
        assert result.question == "Test question?"
        assert result.confidence == 0.9
        assert result.strategy == "abbreviation"


class TestEdgeCases:
    """Tests for edge cases and error handling."""
    
    @pytest.fixture
    def matcher(self):
        """Create MarketMatcher instance for testing."""
        return MarketMatcher()
    
    def test_empty_markets_list(self, matcher):
        """
        Test handling of empty markets list.
        """
        espn_game = {
            "home_team": {"abbreviation": "LAL", "name": "Los Angeles Lakers"},
            "away_team": {"abbreviation": "BOS", "name": "Boston Celtics"},
        }
        
        result = matcher.match_game_to_market(espn_game, [])
        
        assert result is None
    
    def test_empty_game_data(self, matcher):
        """
        Test handling of empty game data.
        """
        espn_game = {}
        
        markets = [
            {
                "condition_id": "cond-123",
                "question": "LAL vs BOS",
                "tokens": []
            }
        ]
        
        result = matcher.match_game_to_market(espn_game, markets)
        
        assert result is None
    
    def test_market_missing_question(self, matcher):
        """
        Test handling of market missing question field.
        """
        espn_game = {
            "home_team": {"abbreviation": "LAL", "name": "Los Angeles Lakers"},
            "away_team": {"abbreviation": "BOS", "name": "Boston Celtics"},
        }
        
        markets = [
            {
                "condition_id": "cond-123",
                # Missing "question" field
                "tokens": []
            }
        ]
        
        result = matcher._match_by_abbreviation(espn_game, markets)
        
        # Should not crash, just return None
        assert result is None


class TestConfidenceThreshold:
    """Tests for confidence threshold behavior."""
    
    def test_default_min_confidence(self):
        """
        Test that MarketMatcher has expected default MIN_CONFIDENCE.
        """
        matcher = MarketMatcher()
        
        assert matcher.MIN_CONFIDENCE == 0.7
    
    def test_custom_confidence_threshold(self):
        """
        Test that confidence threshold can be modified.
        """
        matcher = MarketMatcher()
        matcher.MIN_CONFIDENCE = 0.95
        
        espn_game = {
            "start_time": datetime.now(timezone.utc),
            "home_team": {"abbreviation": "LAL", "name": "Los Angeles Lakers"},
            "away_team": {"abbreviation": "BOS", "name": "Boston Celtics"},
        }
        
        # Time window match has 0.7 confidence, should be rejected at 0.95 threshold
        markets = [
            {
                "condition_id": "cond-low",
                "question": "Some lakers celtics basketball game",
                "end_date_iso": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
                "tokens": []
            }
        ]
        
        # match_game_to_market checks confidence >= MIN_CONFIDENCE
        # If we only match by time_window (0.7), it should be below 0.95
        result = matcher.match_game_to_market(espn_game, markets)
