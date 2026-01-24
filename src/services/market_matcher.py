"""
Market matching service for linking ESPN games to Polymarket markets.
Implements multi-strategy matching with confidence scoring.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class MatchResult:
    """
    Result of a market matching operation.
    Contains the matched token IDs and confidence score.
    """
    condition_id: str
    token_id_yes: str
    token_id_no: str
    question: str
    confidence: float
    strategy: str


class MarketMatcher:
    """
    Matches ESPN game data to Polymarket market identifiers.
    Uses multiple strategies in order of reliability.
    """
    
    MIN_CONFIDENCE = 0.7
    
    def __init__(self):
        """
        Initializes the market matcher.
        """
        pass
    
    def match_game_to_market(
        self,
        espn_game: dict[str, Any],
        polymarket_markets: list[dict[str, Any]]
    ) -> MatchResult | None:
        """
        Attempts to match an ESPN game to a Polymarket market.
        Executes matching strategies in order of reliability.
        
        Args:
            espn_game: Parsed ESPN game state dictionary
            polymarket_markets: List of active Polymarket market dictionaries
        
        Returns:
            MatchResult if match found with sufficient confidence, None otherwise
        """
        strategies = [
            self._match_by_abbreviation,
            self._match_by_team_name,
            self._match_by_time_window,
        ]
        
        for strategy in strategies:
            result = strategy(espn_game, polymarket_markets)
            if result and result.confidence >= self.MIN_CONFIDENCE:
                return result
        
        return None
    
    def _match_by_abbreviation(
        self,
        espn_game: dict[str, Any],
        polymarket_markets: list[dict[str, Any]]
    ) -> MatchResult | None:
        """
        Primary strategy: matches by team abbreviations.
        Most reliable when abbreviations are consistent across sources.
        """
        home_team = espn_game.get("home_team", {})
        away_team = espn_game.get("away_team", {})
        
        if not home_team or not away_team:
            return None
        
        home_abbrev = home_team.get("abbreviation", "").upper()
        away_abbrev = away_team.get("abbreviation", "").upper()
        
        if not home_abbrev or not away_abbrev:
            return None
        
        for market in polymarket_markets:
            question = market.get("question", "")
            question_upper = question.upper()
            
            if home_abbrev in question_upper and away_abbrev in question_upper:
                return MatchResult(
                    condition_id=market.get("condition_id", ""),
                    token_id_yes=self._extract_token_id(market, "yes"),
                    token_id_no=self._extract_token_id(market, "no"),
                    question=question,
                    confidence=0.9,
                    strategy="abbreviation"
                )
        
        return None
    
    def _match_by_team_name(
        self,
        espn_game: dict[str, Any],
        polymarket_markets: list[dict[str, Any]]
    ) -> MatchResult | None:
        """
        Secondary strategy: matches by full team display names.
        Handles cases where abbreviations differ between sources.
        """
        home_team = espn_game.get("home_team", {})
        away_team = espn_game.get("away_team", {})
        
        if not home_team or not away_team:
            return None
        
        home_name = home_team.get("name", "").lower()
        away_name = away_team.get("name", "").lower()
        
        if not home_name or not away_name:
            return None
        
        home_parts = set(home_name.split())
        away_parts = set(away_name.split())
        
        for market in polymarket_markets:
            question = market.get("question", "")
            question_lower = question.lower()
            
            if home_name in question_lower and away_name in question_lower:
                return MatchResult(
                    condition_id=market.get("condition_id", ""),
                    token_id_yes=self._extract_token_id(market, "yes"),
                    token_id_no=self._extract_token_id(market, "no"),
                    question=question,
                    confidence=0.85,
                    strategy="team_name_full"
                )
            
            question_words = set(question_lower.split())
            home_matches = len(home_parts.intersection(question_words))
            away_matches = len(away_parts.intersection(question_words))
            
            if home_matches >= 2 and away_matches >= 2:
                return MatchResult(
                    condition_id=market.get("condition_id", ""),
                    token_id_yes=self._extract_token_id(market, "yes"),
                    token_id_no=self._extract_token_id(market, "no"),
                    question=question,
                    confidence=0.8,
                    strategy="team_name_partial"
                )
        
        return None
    
    def _match_by_time_window(
        self,
        espn_game: dict[str, Any],
        polymarket_markets: list[dict[str, Any]]
    ) -> MatchResult | None:
        """
        Tertiary strategy: matches by game start time within tolerance.
        Used when team names have variations across sources.
        """
        start_time = espn_game.get("start_time")
        if not start_time:
            return None
        
        home_team = espn_game.get("home_team", {})
        away_team = espn_game.get("away_team", {})
        
        team_keywords = set()
        
        if home_team:
            name_parts = home_team.get("name", "").lower().split()
            team_keywords.update(name_parts)
        
        if away_team:
            name_parts = away_team.get("name", "").lower().split()
            team_keywords.update(name_parts)
        
        common_words = {"the", "at", "vs", "versus", "game", "match"}
        team_keywords = team_keywords - common_words
        
        for market in polymarket_markets:
            market_end = market.get("end_date_iso")
            if not market_end:
                continue
            
            try:
                if isinstance(market_end, str):
                    end_dt = datetime.fromisoformat(
                        market_end.replace("Z", "+00:00")
                    )
                else:
                    end_dt = market_end
                
                if start_time.tzinfo is None:
                    start_compare = start_time
                    end_compare = end_dt.replace(tzinfo=None)
                else:
                    start_compare = start_time
                    end_compare = end_dt
                
                time_delta = abs((end_compare - start_compare).total_seconds())
                
                if time_delta < 14400:
                    question_lower = market.get("question", "").lower()
                    matches = sum(1 for kw in team_keywords if kw in question_lower)
                    
                    if matches >= 2:
                        return MatchResult(
                            condition_id=market.get("condition_id", ""),
                            token_id_yes=self._extract_token_id(market, "yes"),
                            token_id_no=self._extract_token_id(market, "no"),
                            question=market.get("question", ""),
                            confidence=0.7,
                            strategy="time_window"
                        )
                        
            except (ValueError, TypeError):
                continue
        
        return None
    
    def _extract_token_id(self, market: dict[str, Any], outcome: str) -> str:
        """
        Extracts the token ID for a specific outcome from market data.
        
        Args:
            market: Market dictionary from Polymarket
            outcome: "yes" or "no"
        
        Returns:
            Token ID string
        """
        tokens = market.get("tokens", [])
        
        for token in tokens:
            token_outcome = token.get("outcome", "").lower()
            if token_outcome == outcome.lower():
                return token.get("token_id", "")
        
        if outcome.lower() == "yes":
            return market.get("token_id_yes", market.get("clobTokenIds", ["", ""])[0])
        else:
            return market.get("token_id_no", market.get("clobTokenIds", ["", ""])[-1])
    
    def match_multiple_games(
        self,
        espn_games: list[dict[str, Any]],
        polymarket_markets: list[dict[str, Any]]
    ) -> list[tuple[dict[str, Any], MatchResult]]:
        """
        Matches multiple ESPN games to Polymarket markets.
        
        Args:
            espn_games: List of parsed ESPN game states
            polymarket_markets: List of active Polymarket markets
        
        Returns:
            List of (game, match_result) tuples for successful matches
        """
        matches = []
        matched_conditions = set()
        
        for game in espn_games:
            result = self.match_game_to_market(game, polymarket_markets)
            
            if result and result.condition_id not in matched_conditions:
                matches.append((game, result))
                matched_conditions.add(result.condition_id)
        
        return matches
