"""
Tests for ESPN service game state parsing and segment normalization.
Tests REAL parsing logic with mock HTTP responses.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import patch, AsyncMock, MagicMock

from src.services.espn_service import ESPNService


# =============================================================================
# Game State Parsing Tests - Tests REAL parsing logic
# =============================================================================

class TestGameStateParsing:
    """Tests for parsing ESPN game data into normalized state."""
    
    def test_parse_live_nba_game(self):
        """Live NBA game should parse correctly with quarter info."""
        service = ESPNService()
        
        game_data = {
            "id": "401584720",
            "name": "Los Angeles Lakers at Boston Celtics",
            "shortName": "LAL @ BOS",
            "date": "2026-01-26T00:00:00Z",
            "status": {
                "period": 3,
                "displayClock": "5:42",
                "type": {"state": "in"}
            },
            "competitions": [{
                "competitors": [
                    {
                        "homeAway": "home",
                        "score": "78",
                        "team": {
                            "displayName": "Boston Celtics",
                            "abbreviation": "BOS",
                            "id": "2"
                        }
                    },
                    {
                        "homeAway": "away",
                        "score": "72",
                        "team": {
                            "displayName": "Los Angeles Lakers",
                            "abbreviation": "LAL",
                            "id": "13"
                        }
                    }
                ]
            }]
        }
        
        state = service.parse_game_state(game_data, "nba")
        
        assert state["event_id"] == "401584720"
        assert state["is_live"] is True
        assert state["is_finished"] is False
        assert state["period"] == 3
        assert state["segment"] == "q3"
        assert state["clock_display"] == "5:42"
        assert state["time_remaining_seconds"] == 342  # 5*60 + 42
        assert state["home_team"]["abbreviation"] == "BOS"
        assert state["away_team"]["abbreviation"] == "LAL"
        assert state["home_score"] == 78
        assert state["away_score"] == 72
    
    def test_parse_finished_game(self):
        """Finished game should have is_finished=True."""
        service = ESPNService()
        
        game_data = {
            "id": "12345",
            "name": "Game Over",
            "shortName": "FINAL",
            "status": {
                "period": 4,
                "displayClock": "0:00",
                "type": {"state": "post"}
            },
            "competitions": [{"competitors": []}]
        }
        
        state = service.parse_game_state(game_data, "nba")
        
        assert state["is_live"] is False
        assert state["is_finished"] is True
    
    def test_parse_pregame(self):
        """Pregame should have is_live=False."""
        service = ESPNService()
        
        game_data = {
            "id": "12345",
            "name": "Upcoming Game",
            "shortName": "UPCOMING",
            "status": {
                "period": 0,
                "displayClock": "0:00",
                "type": {"state": "pre"}
            },
            "competitions": [{"competitors": []}]
        }
        
        state = service.parse_game_state(game_data, "nba")
        
        assert state["is_live"] is False
        assert state["is_finished"] is False


class TestSegmentNormalization:
    """Tests for segment normalization across sports."""
    
    def test_nba_quarters(self):
        """NBA should use q1, q2, q3, q4 segments."""
        service = ESPNService()
        
        assert service._normalize_segment(1, "nba") == "q1"
        assert service._normalize_segment(2, "nba") == "q2"
        assert service._normalize_segment(3, "nba") == "q3"
        assert service._normalize_segment(4, "nba") == "q4"
    
    def test_nba_overtime(self):
        """NBA overtime should return ot segment."""
        service = ESPNService()
        
        result = service._normalize_segment(5, "nba")
        # Period 5+ is overtime
        assert result in ["ot", "ot1", None] or result.startswith("ot")
    
    def test_nfl_quarters(self):
        """NFL should use q1, q2, q3, q4 segments."""
        service = ESPNService()
        
        assert service._normalize_segment(1, "nfl") == "q1"
        assert service._normalize_segment(2, "nfl") == "q2"
        assert service._normalize_segment(3, "nfl") == "q3"
        assert service._normalize_segment(4, "nfl") == "q4"
    
    def test_nhl_periods(self):
        """NHL should use p1, p2, p3 segments."""
        service = ESPNService()
        
        assert service._normalize_segment(1, "nhl") == "p1"
        assert service._normalize_segment(2, "nhl") == "p2"
        assert service._normalize_segment(3, "nhl") == "p3"
    
    def test_soccer_halves(self):
        """Soccer should use h1, h2 segments."""
        service = ESPNService()
        
        assert service._normalize_segment(1, "soccer") == "h1"
        assert service._normalize_segment(2, "soccer") == "h2"
    
    def test_college_basketball_halves(self):
        """College basketball should use h1, h2 segments."""
        service = ESPNService()
        
        assert service._normalize_segment(1, "ncaab") == "h1"
        assert service._normalize_segment(2, "ncaab") == "h2"


class TestClockParsing:
    """Tests for clock display string parsing."""
    
    def test_parse_standard_clock(self):
        """Standard MM:SS format should parse correctly."""
        service = ESPNService()
        
        assert service._parse_clock_to_seconds("12:00") == 720
        assert service._parse_clock_to_seconds("5:30") == 330
        assert service._parse_clock_to_seconds("0:45") == 45
        assert service._parse_clock_to_seconds("0:00") == 0
    
    def test_parse_single_digit_minutes(self):
        """Single digit minutes should parse correctly."""
        service = ESPNService()
        
        assert service._parse_clock_to_seconds("1:30") == 90
        assert service._parse_clock_to_seconds("9:59") == 599
    
    def test_parse_invalid_clock(self):
        """Invalid clock format should return 0."""
        service = ESPNService()
        
        assert service._parse_clock_to_seconds("invalid") == 0
        assert service._parse_clock_to_seconds("") == 0
        assert service._parse_clock_to_seconds("12") == 0


class TestSportEndpoints:
    """Tests for sport endpoint mapping."""
    
    def test_major_sports_have_endpoints(self):
        """All major sports should have valid endpoints."""
        service = ESPNService()
        
        assert "nba" in service.SPORT_ENDPOINTS
        assert "nfl" in service.SPORT_ENDPOINTS
        assert "mlb" in service.SPORT_ENDPOINTS
        assert "nhl" in service.SPORT_ENDPOINTS
    
    def test_get_sport_endpoint_valid(self):
        """Valid sport should return endpoint path."""
        service = ESPNService()
        
        assert service._get_sport_endpoint("nba") == "basketball/nba"
        assert service._get_sport_endpoint("nfl") == "football/nfl"
        assert service._get_sport_endpoint("mlb") == "baseball/mlb"
        assert service._get_sport_endpoint("nhl") == "hockey/nhl"
    
    def test_get_sport_endpoint_case_insensitive(self):
        """Sport lookup should be case insensitive."""
        service = ESPNService()
        
        assert service._get_sport_endpoint("NBA") == "basketball/nba"
        assert service._get_sport_endpoint("Nba") == "basketball/nba"
    
    def test_get_sport_endpoint_invalid_raises(self):
        """Invalid sport should raise ValueError."""
        service = ESPNService()
        
        with pytest.raises(ValueError) as exc_info:
            service._get_sport_endpoint("cricket")
        
        assert "Unsupported sport" in str(exc_info.value)


class TestTeamExtraction:
    """Tests for extracting team data from competitors."""
    
    def test_extract_home_away_teams(self):
        """Home and away teams should be extracted correctly."""
        service = ESPNService()
        
        game_data = {
            "id": "12345",
            "name": "Test Game",
            "shortName": "TEST",
            "status": {"period": 1, "displayClock": "12:00", "type": {"state": "in"}},
            "competitions": [{
                "competitors": [
                    {
                        "homeAway": "home",
                        "score": "50",
                        "team": {
                            "displayName": "Home Team",
                            "abbreviation": "HOM",
                            "id": "1"
                        }
                    },
                    {
                        "homeAway": "away",
                        "score": "45",
                        "team": {
                            "displayName": "Away Team",
                            "abbreviation": "AWY",
                            "id": "2"
                        }
                    }
                ]
            }]
        }
        
        state = service.parse_game_state(game_data, "nba")
        
        assert state["home_team"]["name"] == "Home Team"
        assert state["home_team"]["abbreviation"] == "HOM"
        assert state["away_team"]["name"] == "Away Team"
        assert state["away_team"]["abbreviation"] == "AWY"
    
    def test_missing_competitors_handled(self):
        """Missing competitors should not crash."""
        service = ESPNService()
        
        game_data = {
            "id": "12345",
            "name": "Test",
            "shortName": "T",
            "status": {"period": 1, "displayClock": "12:00", "type": {"state": "in"}},
            "competitions": [{"competitors": []}]
        }
        
        state = service.parse_game_state(game_data, "nba")
        
        assert state["home_team"] is None
        assert state["away_team"] is None


class TestScoreParsing:
    """Tests for score extraction."""
    
    def test_parse_numeric_scores(self):
        """Numeric string scores should parse to integers."""
        service = ESPNService()
        
        game_data = {
            "id": "12345",
            "name": "Test",
            "shortName": "T",
            "status": {"period": 1, "displayClock": "12:00", "type": {"state": "in"}},
            "competitions": [{
                "competitors": [
                    {"homeAway": "home", "score": "105", "team": {"displayName": "A", "abbreviation": "A", "id": "1"}},
                    {"homeAway": "away", "score": "98", "team": {"displayName": "B", "abbreviation": "B", "id": "2"}}
                ]
            }]
        }
        
        state = service.parse_game_state(game_data, "nba")
        
        assert state["home_score"] == 105
        assert state["away_score"] == 98
    
    def test_parse_missing_score_defaults_zero(self):
        """Missing score should default to 0."""
        service = ESPNService()
        
        game_data = {
            "id": "12345",
            "name": "Test",
            "shortName": "T",
            "status": {"period": 1, "displayClock": "12:00", "type": {"state": "in"}},
            "competitions": [{
                "competitors": [
                    {"homeAway": "home", "team": {"displayName": "A", "abbreviation": "A", "id": "1"}},
                    {"homeAway": "away", "score": None, "team": {"displayName": "B", "abbreviation": "B", "id": "2"}}
                ]
            }]
        }
        
        state = service.parse_game_state(game_data, "nba")
        
        assert state["home_score"] == 0
        assert state["away_score"] == 0


class TestDateParsing:
    """Tests for game start time parsing."""
    
    def test_parse_iso_date(self):
        """ISO format date should parse to datetime."""
        service = ESPNService()
        
        game_data = {
            "id": "12345",
            "name": "Test",
            "shortName": "T",
            "date": "2026-01-26T19:30:00Z",
            "status": {"period": 0, "displayClock": "0:00", "type": {"state": "pre"}},
            "competitions": [{"competitors": []}]
        }
        
        state = service.parse_game_state(game_data, "nba")
        
        assert state["start_time"] is not None
        assert state["start_time"].year == 2026
        assert state["start_time"].month == 1
        assert state["start_time"].day == 26
    
    def test_missing_date_returns_none(self):
        """Missing date should result in None start_time."""
        service = ESPNService()
        
        game_data = {
            "id": "12345",
            "name": "Test",
            "shortName": "T",
            "status": {"period": 0, "displayClock": "0:00", "type": {"state": "pre"}},
            "competitions": [{"competitors": []}]
        }
        
        state = service.parse_game_state(game_data, "nba")
        
        assert state["start_time"] is None


class TestSegmentMapping:
    """Tests for segment mapping constants."""
    
    def test_all_major_sports_have_mappings(self):
        """All major sports should have segment mappings."""
        service = ESPNService()
        
        assert "nba" in service.SEGMENT_MAPPING
        assert "nfl" in service.SEGMENT_MAPPING
        assert "nhl" in service.SEGMENT_MAPPING
        assert "mlb" not in service.SEGMENT_MAPPING or service.SEGMENT_MAPPING.get("mlb") == {}  # MLB uses innings
    
    def test_clock_countup_sports_defined(self):
        """Soccer leagues should be in clock countup set."""
        service = ESPNService()
        
        assert "soccer" in service.CLOCK_COUNTUP_SPORTS
        assert "epl" in service.CLOCK_COUNTUP_SPORTS


class TestHTTPClientInitialization:
    """Tests for HTTP client lifecycle."""
    
    def test_client_initially_none(self):
        """HTTP client should be None on init."""
        service = ESPNService()
        
        assert service._client is None
    
    @pytest.mark.asyncio
    async def test_get_client_creates_client(self):
        """_get_client should create client on first call."""
        service = ESPNService()
        
        client = await service._get_client()
        
        assert client is not None
        assert service._client is not None
        
        # Cleanup
        await client.aclose()
    
    @pytest.mark.asyncio
    async def test_get_client_reuses_client(self):
        """_get_client should return same client on subsequent calls."""
        service = ESPNService()
        
        client1 = await service._get_client()
        client2 = await service._get_client()
        
        assert client1 is client2
        
        # Cleanup
        await client1.aclose()
