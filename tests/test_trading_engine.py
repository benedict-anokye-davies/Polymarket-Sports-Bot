"""
Unit tests for TradingEngine.
Tests entry/exit evaluation logic and order lifecycle management.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal
from datetime import datetime, timezone

from src.services.trading_engine import TradingEngine


class TestEntryEvaluation:
    """Tests for entry condition evaluation logic."""
    
    @pytest.fixture
    def engine(self):
        """Create TradingEngine instance with mocked dependencies."""
        engine = TradingEngine()
        engine.logger = MagicMock()
        return engine
    
    def test_price_below_absolute_threshold(self, engine):
        """
        Test that entry is triggered when current price
        falls below configured absolute threshold.
        """
        config = {
            "absolute_entry_threshold": Decimal("0.30"),
            "percentage_drop_threshold": Decimal("0.15"),
            "min_time_remaining_seconds": 60,
            "allowed_entry_segments": ["q1", "q2", "q3", "q4"],
        }
        
        market = {
            "current_price_yes": Decimal("0.25"),
            "baseline_price_yes": Decimal("0.50"),
        }
        
        game_state = {
            "segment": "q2",
            "time_remaining_seconds": 300,
            "is_live": True,
        }
        
        result = engine.evaluate_entry(config, market, game_state)
        
        assert result["should_enter"] is True
        assert result["reason"] == "price_below_absolute"
    
    def test_percentage_drop_threshold(self, engine):
        """
        Test that entry is triggered when price drops
        by configured percentage from baseline.
        """
        config = {
            "absolute_entry_threshold": Decimal("0.10"),
            "percentage_drop_threshold": Decimal("0.15"),
            "min_time_remaining_seconds": 60,
            "allowed_entry_segments": ["q1", "q2", "q3", "q4"],
        }
        
        market = {
            "current_price_yes": Decimal("0.40"),
            "baseline_price_yes": Decimal("0.50"),
        }
        
        game_state = {
            "segment": "q2",
            "time_remaining_seconds": 300,
            "is_live": True,
        }
        
        result = engine.evaluate_entry(config, market, game_state)
        
        assert result["should_enter"] is True
        assert result["reason"] == "percentage_drop"
    
    def test_no_entry_game_not_live(self, engine):
        """
        Test that no entry occurs when game is not live.
        """
        config = {
            "absolute_entry_threshold": Decimal("0.30"),
            "percentage_drop_threshold": Decimal("0.15"),
            "min_time_remaining_seconds": 60,
            "allowed_entry_segments": ["q1", "q2", "q3", "q4"],
        }
        
        market = {
            "current_price_yes": Decimal("0.25"),
            "baseline_price_yes": Decimal("0.50"),
        }
        
        game_state = {
            "segment": "q2",
            "time_remaining_seconds": 300,
            "is_live": False,
        }
        
        result = engine.evaluate_entry(config, market, game_state)
        
        assert result["should_enter"] is False
        assert "not_live" in result["reason"]
    
    def test_no_entry_insufficient_time(self, engine):
        """
        Test that no entry occurs when insufficient time
        remains in the period.
        """
        config = {
            "absolute_entry_threshold": Decimal("0.30"),
            "percentage_drop_threshold": Decimal("0.15"),
            "min_time_remaining_seconds": 120,
            "allowed_entry_segments": ["q1", "q2", "q3", "q4"],
        }
        
        market = {
            "current_price_yes": Decimal("0.25"),
            "baseline_price_yes": Decimal("0.50"),
        }
        
        game_state = {
            "segment": "q2",
            "time_remaining_seconds": 60,
            "is_live": True,
        }
        
        result = engine.evaluate_entry(config, market, game_state)
        
        assert result["should_enter"] is False
        assert "time" in result["reason"].lower()
    
    def test_no_entry_restricted_segment(self, engine):
        """
        Test that no entry occurs during restricted game segments.
        """
        config = {
            "absolute_entry_threshold": Decimal("0.30"),
            "percentage_drop_threshold": Decimal("0.15"),
            "min_time_remaining_seconds": 60,
            "allowed_entry_segments": ["q1", "q2"],
        }
        
        market = {
            "current_price_yes": Decimal("0.25"),
            "baseline_price_yes": Decimal("0.50"),
        }
        
        game_state = {
            "segment": "q4",
            "time_remaining_seconds": 300,
            "is_live": True,
        }
        
        result = engine.evaluate_entry(config, market, game_state)
        
        assert result["should_enter"] is False
        assert "segment" in result["reason"].lower()


class TestExitEvaluation:
    """Tests for exit condition evaluation logic."""
    
    @pytest.fixture
    def engine(self):
        """Create TradingEngine instance with mocked dependencies."""
        engine = TradingEngine()
        engine.logger = MagicMock()
        return engine
    
    def test_take_profit_triggered(self, engine):
        """
        Test that exit is triggered when take profit threshold is reached.
        """
        config = {
            "take_profit_threshold": Decimal("0.20"),
            "stop_loss_threshold": Decimal("0.10"),
            "exit_segments": ["q4"],
        }
        
        position = {
            "entry_price": Decimal("0.40"),
            "side": "YES",
        }
        
        market = {
            "current_price_yes": Decimal("0.50"),
        }
        
        game_state = {
            "segment": "q2",
            "is_finished": False,
        }
        
        result = engine.evaluate_exit(config, position, market, game_state)
        
        assert result["should_exit"] is True
        assert result["reason"] == "take_profit"
    
    def test_stop_loss_triggered(self, engine):
        """
        Test that exit is triggered when stop loss threshold is reached.
        """
        config = {
            "take_profit_threshold": Decimal("0.20"),
            "stop_loss_threshold": Decimal("0.10"),
            "exit_segments": ["q4"],
        }
        
        position = {
            "entry_price": Decimal("0.40"),
            "side": "YES",
        }
        
        market = {
            "current_price_yes": Decimal("0.28"),
        }
        
        game_state = {
            "segment": "q2",
            "is_finished": False,
        }
        
        result = engine.evaluate_exit(config, position, market, game_state)
        
        assert result["should_exit"] is True
        assert result["reason"] == "stop_loss"
    
    def test_game_finished_exit(self, engine):
        """
        Test that exit is triggered when game finishes.
        """
        config = {
            "take_profit_threshold": Decimal("0.20"),
            "stop_loss_threshold": Decimal("0.10"),
            "exit_segments": ["q4"],
        }
        
        position = {
            "entry_price": Decimal("0.40"),
            "side": "YES",
        }
        
        market = {
            "current_price_yes": Decimal("0.42"),
        }
        
        game_state = {
            "segment": "final",
            "is_finished": True,
        }
        
        result = engine.evaluate_exit(config, position, market, game_state)
        
        assert result["should_exit"] is True
        assert result["reason"] == "game_finished"
    
    def test_time_based_exit(self, engine):
        """
        Test that exit is triggered when approaching restricted segment.
        """
        config = {
            "take_profit_threshold": Decimal("0.20"),
            "stop_loss_threshold": Decimal("0.10"),
            "exit_segments": ["q4"],
        }
        
        position = {
            "entry_price": Decimal("0.40"),
            "side": "YES",
        }
        
        market = {
            "current_price_yes": Decimal("0.42"),
        }
        
        game_state = {
            "segment": "q4",
            "is_finished": False,
        }
        
        result = engine.evaluate_exit(config, position, market, game_state)
        
        assert result["should_exit"] is True
        assert result["reason"] == "segment_exit"
    
    def test_no_exit_conditions_not_met(self, engine):
        """
        Test that no exit occurs when conditions are not met.
        """
        config = {
            "take_profit_threshold": Decimal("0.20"),
            "stop_loss_threshold": Decimal("0.10"),
            "exit_segments": ["q4"],
        }
        
        position = {
            "entry_price": Decimal("0.40"),
            "side": "YES",
        }
        
        market = {
            "current_price_yes": Decimal("0.42"),
        }
        
        game_state = {
            "segment": "q2",
            "is_finished": False,
        }
        
        result = engine.evaluate_exit(config, position, market, game_state)
        
        assert result["should_exit"] is False


class TestPositionSizing:
    """Tests for position sizing calculations."""
    
    @pytest.fixture
    def engine(self):
        """Create TradingEngine instance with mocked dependencies."""
        engine = TradingEngine()
        engine.logger = MagicMock()
        return engine
    
    def test_basic_position_size(self, engine):
        """
        Test basic position sizing based on balance and risk percentage.
        """
        balance = Decimal("1000.00")
        risk_pct = Decimal("0.05")
        price = Decimal("0.50")
        
        size = engine.calculate_position_size(balance, risk_pct, price)
        
        # With 5% risk on $1000 = $50, at $0.50 price = 100 contracts
        assert size == 100
    
    def test_position_size_minimum(self, engine):
        """
        Test that position size is at least 1 contract.
        """
        balance = Decimal("10.00")
        risk_pct = Decimal("0.01")
        price = Decimal("0.99")
        
        size = engine.calculate_position_size(balance, risk_pct, price)
        
        assert size >= 1
    
    def test_position_size_max_cap(self, engine):
        """
        Test that position size respects maximum limit.
        """
        balance = Decimal("100000.00")
        risk_pct = Decimal("0.10")
        price = Decimal("0.10")
        max_size = 1000
        
        size = engine.calculate_position_size(balance, risk_pct, price, max_size=max_size)
        
        assert size <= max_size
