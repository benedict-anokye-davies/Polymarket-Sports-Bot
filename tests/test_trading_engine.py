"""
Unit tests for TradingEngine.
Tests entry/exit evaluation logic and configuration merging.

TradingEngine constructor signature:
    def __init__(
        self,
        db: AsyncSession,
        user_id: str,
        polymarket_client: PolymarketClient,
        global_settings: GlobalSettings,
        sport_configs: dict[str, SportConfig],
        market_configs: dict[str, MarketConfig] | None = None
    )

Key classes:
    - EffectiveConfig: Merges market-specific and sport-level configs
    - TradingEngine: Evaluates entry/exit conditions
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal
from datetime import datetime, timezone
from uuid import uuid4

from src.services.trading_engine import TradingEngine, EffectiveConfig


class MockSportConfig:
    """Mock sport configuration for testing."""
    
    def __init__(
        self,
        sport: str = "nba",
        is_enabled: bool = True,
        entry_threshold_pct: Decimal = Decimal("0.15"),
        absolute_entry_price: Decimal = Decimal("0.30"),
        min_time_remaining_seconds: int = 120,
        take_profit_pct: Decimal = Decimal("0.20"),
        stop_loss_pct: Decimal = Decimal("0.10"),
        default_position_size_usdc: Decimal = Decimal("50.00"),
        max_positions_per_game: int = 2,
        allowed_entry_segments: list = None
    ):
        self.sport = sport
        self.is_enabled = is_enabled
        self.entry_threshold_pct = entry_threshold_pct
        self.absolute_entry_price = absolute_entry_price
        self.min_time_remaining_seconds = min_time_remaining_seconds
        self.take_profit_pct = take_profit_pct
        self.stop_loss_pct = stop_loss_pct
        self.default_position_size_usdc = default_position_size_usdc
        self.max_positions_per_game = max_positions_per_game
        self.allowed_entry_segments = allowed_entry_segments or ["q1", "q2", "q3", "q4"]


class MockMarketConfig:
    """Mock market-specific configuration for testing."""
    
    def __init__(
        self,
        condition_id: str = "cond-123",
        enabled: bool = True,
        auto_trade: bool = True,
        entry_threshold_drop: Decimal = None,
        entry_threshold_absolute: Decimal = None,
        min_time_remaining_seconds: int = None,
        take_profit_pct: Decimal = None,
        stop_loss_pct: Decimal = None,
        position_size_usdc: Decimal = None,
        max_positions: int = None
    ):
        self.condition_id = condition_id
        self.enabled = enabled
        self.auto_trade = auto_trade
        self.entry_threshold_drop = entry_threshold_drop
        self.entry_threshold_absolute = entry_threshold_absolute
        self.min_time_remaining_seconds = min_time_remaining_seconds
        self.take_profit_pct = take_profit_pct
        self.stop_loss_pct = stop_loss_pct
        self.position_size_usdc = position_size_usdc
        self.max_positions = max_positions


class MockGlobalSettings:
    """Mock global settings for testing."""
    
    def __init__(
        self,
        max_daily_loss_usdc: Decimal = Decimal("100.00"),
        max_total_exposure_usdc: Decimal = Decimal("500.00"),
        dry_run_mode: bool = True
    ):
        self.max_daily_loss_usdc = max_daily_loss_usdc
        self.max_total_exposure_usdc = max_total_exposure_usdc
        self.dry_run_mode = dry_run_mode


class MockTrackedMarket:
    """Mock tracked market for testing."""
    
    def __init__(
        self,
        condition_id: str = "cond-123",
        sport: str = "nba"
    ):
        self.condition_id = condition_id
        self.sport = sport


class TestEffectiveConfig:
    """Tests for EffectiveConfig configuration merging."""
    
    def test_effective_config_uses_sport_defaults(self):
        """
        Test that EffectiveConfig uses sport config values by default.
        """
        sport_config = MockSportConfig(
            entry_threshold_pct=Decimal("0.15"),
            take_profit_pct=Decimal("0.20"),
            stop_loss_pct=Decimal("0.10")
        )
        
        effective = EffectiveConfig(sport_config)
        
        assert effective.entry_threshold_pct == Decimal("0.15")
        assert effective.take_profit_pct == Decimal("0.20")
        assert effective.stop_loss_pct == Decimal("0.10")
    
    def test_effective_config_market_override(self):
        """
        Test that market config overrides sport config values.
        """
        sport_config = MockSportConfig(
            entry_threshold_pct=Decimal("0.15"),
            take_profit_pct=Decimal("0.20")
        )
        market_config = MockMarketConfig(
            entry_threshold_drop=Decimal("0.10"),
            take_profit_pct=Decimal("0.25")
        )
        
        effective = EffectiveConfig(sport_config, market_config)
        
        assert effective.entry_threshold_pct == Decimal("0.10")  # Market override
        assert effective.take_profit_pct == Decimal("0.25")  # Market override
    
    def test_effective_config_disabled_market(self):
        """
        Test that disabled market config returns is_enabled=False.
        """
        sport_config = MockSportConfig(is_enabled=True)
        market_config = MockMarketConfig(enabled=False)
        
        effective = EffectiveConfig(sport_config, market_config)
        
        assert effective.is_enabled is False
    
    def test_effective_config_auto_trade(self):
        """
        Test auto_trade property from market config.
        """
        sport_config = MockSportConfig()
        market_config = MockMarketConfig(auto_trade=False)
        
        effective = EffectiveConfig(sport_config, market_config)
        
        assert effective.auto_trade is False
    
    def test_effective_config_allowed_segments(self):
        """
        Test that allowed_entry_segments comes from sport config.
        """
        sport_config = MockSportConfig(allowed_entry_segments=["q1", "q2"])
        
        effective = EffectiveConfig(sport_config)
        
        assert effective.allowed_entry_segments == ["q1", "q2"]


class TestTradingEngineCreation:
    """Tests for TradingEngine instantiation."""
    
    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return AsyncMock()
    
    @pytest.fixture
    def mock_client(self):
        """Create mock Polymarket client."""
        client = AsyncMock()
        client.get_midpoint_price = AsyncMock(return_value=0.45)
        return client
    
    @pytest.fixture
    def mock_settings(self):
        """Create mock global settings."""
        return MockGlobalSettings()
    
    @pytest.fixture
    def mock_sport_configs(self):
        """Create mock sport configs dictionary."""
        return {"nba": MockSportConfig(sport="nba")}
    
    def test_engine_creation(self, mock_db, mock_client, mock_settings, mock_sport_configs):
        """
        Test TradingEngine can be instantiated with required args.
        """
        engine = TradingEngine(
            db=mock_db,
            user_id="test-user-123",
            polymarket_client=mock_client,
            global_settings=mock_settings,
            sport_configs=mock_sport_configs
        )
        
        assert engine.user_id == "test-user-123"
        assert engine.client == mock_client
        assert engine.settings == mock_settings
    
    def test_engine_with_market_configs(self, mock_db, mock_client, mock_settings, mock_sport_configs):
        """
        Test TradingEngine with market-specific configs.
        """
        market_configs = {
            "cond-123": MockMarketConfig(condition_id="cond-123")
        }
        
        engine = TradingEngine(
            db=mock_db,
            user_id="test-user-123",
            polymarket_client=mock_client,
            global_settings=mock_settings,
            sport_configs=mock_sport_configs,
            market_configs=market_configs
        )
        
        assert "cond-123" in engine.market_configs


class TestEffectiveConfigRetrieval:
    """Tests for _get_effective_config method."""
    
    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return AsyncMock()
    
    @pytest.fixture
    def mock_client(self):
        """Create mock Polymarket client."""
        return AsyncMock()
    
    @pytest.fixture
    def mock_settings(self):
        """Create mock global settings."""
        return MockGlobalSettings()
    
    def test_get_effective_config_sport_only(self, mock_db, mock_client, mock_settings):
        """
        Test getting effective config with sport config only.
        """
        sport_configs = {"nba": MockSportConfig(sport="nba")}
        
        engine = TradingEngine(
            db=mock_db,
            user_id="test-user",
            polymarket_client=mock_client,
            global_settings=mock_settings,
            sport_configs=sport_configs
        )
        
        market = MockTrackedMarket(condition_id="cond-123", sport="nba")
        config = engine._get_effective_config(market)
        
        assert config is not None
        assert config.sport_config.sport == "nba"
    
    def test_get_effective_config_with_market_override(self, mock_db, mock_client, mock_settings):
        """
        Test getting effective config with market override.
        """
        sport_configs = {"nba": MockSportConfig(sport="nba", take_profit_pct=Decimal("0.20"))}
        market_configs = {
            "cond-123": MockMarketConfig(
                condition_id="cond-123",
                take_profit_pct=Decimal("0.30")
            )
        }
        
        engine = TradingEngine(
            db=mock_db,
            user_id="test-user",
            polymarket_client=mock_client,
            global_settings=mock_settings,
            sport_configs=sport_configs,
            market_configs=market_configs
        )
        
        market = MockTrackedMarket(condition_id="cond-123", sport="nba")
        config = engine._get_effective_config(market)
        
        assert config is not None
        assert config.take_profit_pct == Decimal("0.30")  # Market override
    
    def test_get_effective_config_unknown_sport(self, mock_db, mock_client, mock_settings):
        """
        Test getting effective config for unknown sport returns None.
        """
        sport_configs = {"nba": MockSportConfig(sport="nba")}
        
        engine = TradingEngine(
            db=mock_db,
            user_id="test-user",
            polymarket_client=mock_client,
            global_settings=mock_settings,
            sport_configs=sport_configs
        )
        
        market = MockTrackedMarket(condition_id="cond-123", sport="unknown_sport")
        config = engine._get_effective_config(market)
        
        assert config is None


class TestConfigProperties:
    """Tests for EffectiveConfig property accessors."""
    
    def test_all_properties_accessible(self):
        """
        Test that all EffectiveConfig properties are accessible.
        """
        sport_config = MockSportConfig()
        effective = EffectiveConfig(sport_config)
        
        # All properties should be accessible without error
        _ = effective.is_enabled
        _ = effective.auto_trade
        _ = effective.entry_threshold_pct
        _ = effective.absolute_entry_price
        _ = effective.min_time_remaining_seconds
        _ = effective.take_profit_pct
        _ = effective.stop_loss_pct
        _ = effective.default_position_size_usdc
        _ = effective.max_positions_per_game
        _ = effective.allowed_entry_segments
    
    def test_position_size_override(self):
        """
        Test position size override from market config.
        """
        sport_config = MockSportConfig(default_position_size_usdc=Decimal("50.00"))
        market_config = MockMarketConfig(position_size_usdc=Decimal("100.00"))
        
        effective = EffectiveConfig(sport_config, market_config)
        
        assert effective.default_position_size_usdc == Decimal("100.00")
    
    def test_max_positions_override(self):
        """
        Test max positions override from market config.
        """
        sport_config = MockSportConfig(max_positions_per_game=2)
        market_config = MockMarketConfig(max_positions=5)
        
        effective = EffectiveConfig(sport_config, market_config)
        
        assert effective.max_positions_per_game == 5


class TestDecimalPrecision:
    """Tests for decimal precision in configurations."""
    
    def test_threshold_decimal_precision(self):
        """
        Test that decimal thresholds maintain precision.
        """
        sport_config = MockSportConfig(
            entry_threshold_pct=Decimal("0.0525"),
            take_profit_pct=Decimal("0.1575")
        )
        
        effective = EffectiveConfig(sport_config)
        
        assert effective.entry_threshold_pct == Decimal("0.0525")
        assert effective.take_profit_pct == Decimal("0.1575")
    
    def test_usdc_amount_precision(self):
        """
        Test that USDC amounts maintain precision.
        """
        sport_config = MockSportConfig(
            default_position_size_usdc=Decimal("25.50")
        )
        
        effective = EffectiveConfig(sport_config)
        
        assert effective.default_position_size_usdc == Decimal("25.50")
