"""
Unit tests for BotRunner.
Tests lifecycle management, initialization, and state transitions.

BotRunner constructor signature:
    def __init__(
        self,
        polymarket_client: PolymarketClient,
        trading_engine: TradingEngine,
        espn_service: ESPNService
    )

Key methods:
    - initialize(db, user_id): Load user config, recover positions
    - start(db): Start all background loops
    - stop(): Graceful shutdown
    - pause() / resume(): Pause/resume trading
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from uuid import uuid4

from src.services.bot_runner import BotRunner, BotState, TrackedGame, SportStats


class TestBotInitialization:
    """Tests for BotRunner initialization."""
    
    @pytest.fixture
    def mock_polymarket_client(self):
        """Create mock Polymarket client."""
        client = AsyncMock()
        client.__class__.__name__ = "PolymarketClient"
        client.get_balance = AsyncMock(return_value=1000.0)
        client.get_positions = AsyncMock(return_value=[])
        client.dry_run = True
        client.max_slippage = 0.02
        return client
    
    @pytest.fixture
    def mock_trading_engine(self):
        """Create mock trading engine."""
        engine = AsyncMock()
        return engine
    
    @pytest.fixture
    def mock_espn_service(self):
        """Create mock ESPN service."""
        espn = AsyncMock()
        espn.get_scoreboard = AsyncMock(return_value={"events": []})
        return espn
    
    @pytest.fixture
    def bot_runner(self, mock_polymarket_client, mock_trading_engine, mock_espn_service):
        """Create BotRunner instance with mocked dependencies."""
        return BotRunner(
            polymarket_client=mock_polymarket_client,
            trading_engine=mock_trading_engine,
            espn_service=mock_espn_service
        )
    
    def test_bot_runner_initial_state(self, bot_runner):
        """
        Test that BotRunner starts in STOPPED state.
        """
        assert bot_runner.state == BotState.STOPPED
    
    def test_bot_detects_polymarket_platform(self, bot_runner):
        """
        Test that BotRunner detects Polymarket from client class name.
        """
        assert bot_runner.platform == "polymarket"
    
    def test_bot_detects_kalshi_platform(self, mock_trading_engine, mock_espn_service):
        """
        Test that BotRunner detects Kalshi from client class name.
        """
        kalshi_client = AsyncMock()
        kalshi_client.__class__.__name__ = "KalshiClient"
        
        runner = BotRunner(
            polymarket_client=kalshi_client,
            trading_engine=mock_trading_engine,
            espn_service=mock_espn_service
        )
        
        assert runner.platform == "kalshi"
    
    def test_bot_runner_default_config(self, bot_runner):
        """
        Test that BotRunner has sensible default configuration.
        """
        assert bot_runner.dry_run is True  # Paper trading by default
        assert bot_runner.entry_threshold == 0.05
        assert bot_runner.take_profit == 0.15
        assert bot_runner.stop_loss == 0.10
        assert bot_runner.max_daily_loss == 100.0
    
    def test_tracked_games_empty_on_init(self, bot_runner):
        """
        Test that no games are tracked on initialization.
        """
        assert len(bot_runner.tracked_games) == 0
    
    def test_sport_stats_empty_on_init(self, bot_runner):
        """
        Test that sport stats are empty before initialize() is called.
        """
        assert len(bot_runner.sport_stats) == 0


class TestBotState:
    """Tests for BotState enum."""
    
    def test_all_states_exist(self):
        """
        Test that all expected states are defined.
        """
        expected_states = ["stopped", "starting", "running", "paused", "stopping", "error"]
        
        for state_value in expected_states:
            assert hasattr(BotState, state_value.upper())
    
    def test_state_values(self):
        """
        Test that state values match expected strings.
        """
        assert BotState.STOPPED.value == "stopped"
        assert BotState.RUNNING.value == "running"
        assert BotState.PAUSED.value == "paused"


class TestTrackedGame:
    """Tests for TrackedGame dataclass."""
    
    def test_tracked_game_creation(self):
        """
        Test creating a TrackedGame instance.
        """
        from src.services.market_discovery import DiscoveredMarket
        from datetime import datetime, timezone
        
        market = DiscoveredMarket(
            condition_id="cond-123",
            token_id_yes="token-yes",
            token_id_no="token-no",
            question="Lakers vs Celtics",
            description="NBA game outcome",
            sport="nba",
            home_team="LAL",
            away_team="BOS",
            game_start_time=datetime.now(timezone.utc),
            end_date=datetime.now(timezone.utc),
            volume_24h=10000.0,
            liquidity=50000.0,
            current_price_yes=0.50,
            current_price_no=0.50,
            spread=0.02,
            ticker="NBA-LAL-BOS"
        )
        
        game = TrackedGame(
            espn_event_id="event-456",
            sport="nba",
            home_team="LAL",
            away_team="BOS",
            market=market
        )
        
        assert game.espn_event_id == "event-456"
        assert game.sport == "nba"
        assert game.baseline_price is None
        assert game.has_position is False
    
    def test_tracked_game_defaults(self):
        """
        Test TrackedGame default values.
        """
        from src.services.market_discovery import DiscoveredMarket
        from datetime import datetime, timezone
        
        market = DiscoveredMarket(
            condition_id="cond-123",
            token_id_yes="token-yes",
            token_id_no="token-no",
            question="Test game",
            description="Test description",
            sport="nba",
            home_team="HOME",
            away_team="AWAY",
            game_start_time=datetime.now(timezone.utc),
            end_date=datetime.now(timezone.utc),
            volume_24h=5000.0,
            liquidity=25000.0,
            current_price_yes=0.50,
            current_price_no=0.50,
            spread=0.03
        )
        
        game = TrackedGame(
            espn_event_id="event-123",
            sport="nba",
            home_team="HOME",
            away_team="AWAY",
            market=market
        )
        
        assert game.game_status == "pre"
        assert game.period == 0
        assert game.clock == ""
        assert game.home_score == 0
        assert game.away_score == 0
        assert game.selected_side == "home"


class TestSportStats:
    """Tests for SportStats dataclass."""
    
    def test_sport_stats_creation(self):
        """
        Test creating SportStats instance.
        """
        stats = SportStats(sport="nba")
        
        assert stats.sport == "nba"
        assert stats.trades_today == 0
        assert stats.daily_pnl == 0.0
        assert stats.open_positions == 0
        assert stats.tracked_games == 0
        assert stats.enabled is True
    
    def test_sport_stats_custom_values(self):
        """
        Test SportStats with custom values.
        """
        stats = SportStats(
            sport="nfl",
            trades_today=5,
            daily_pnl=-25.50,
            open_positions=2,
            enabled=False,
            max_daily_loss=100.0,
            max_exposure=500.0
        )
        
        assert stats.sport == "nfl"
        assert stats.trades_today == 5
        assert stats.daily_pnl == -25.50
        assert stats.max_daily_loss == 100.0
        assert stats.max_exposure == 500.0


class TestPlatformDetection:
    """Tests for platform detection logic."""
    
    @pytest.fixture
    def mock_trading_engine(self):
        """Create mock trading engine."""
        return AsyncMock()
    
    @pytest.fixture
    def mock_espn_service(self):
        """Create mock ESPN service."""
        return AsyncMock()
    
    def test_polymarket_detection(self, mock_trading_engine, mock_espn_service):
        """
        Test Polymarket client detection.
        """
        client = AsyncMock()
        client.__class__.__name__ = "PolymarketClient"
        
        runner = BotRunner(client, mock_trading_engine, mock_espn_service)
        
        assert runner.platform == "polymarket"
    
    def test_kalshi_detection(self, mock_trading_engine, mock_espn_service):
        """
        Test Kalshi client detection.
        """
        client = AsyncMock()
        client.__class__.__name__ = "KalshiClient"
        
        runner = BotRunner(client, mock_trading_engine, mock_espn_service)
        
        assert runner.platform == "kalshi"
    
    def test_websocket_none_for_kalshi(self, mock_trading_engine, mock_espn_service):
        """
        Test that WebSocket is None for Kalshi platform.
        """
        kalshi_client = AsyncMock()
        kalshi_client.__class__.__name__ = "KalshiClient"
        
        runner = BotRunner(kalshi_client, mock_trading_engine, mock_espn_service)
        
        # WebSocket should not be initialized in __init__, only in initialize()
        # But the code shows websocket is set to None by default
        assert runner.websocket is None


class TestPollingIntervals:
    """Tests for polling interval constants."""
    
    def test_espn_poll_interval(self):
        """
        Test ESPN poll interval is set correctly.
        """
        assert BotRunner.ESPN_POLL_INTERVAL == 5.0
    
    def test_discovery_interval(self):
        """
        Test market discovery interval is set correctly.
        """
        assert BotRunner.DISCOVERY_INTERVAL == 300.0
    
    def test_health_check_interval(self):
        """
        Test health check interval is set correctly.
        """
        assert BotRunner.HEALTH_CHECK_INTERVAL == 60.0


class TestBotConfiguration:
    """Tests for bot configuration properties."""
    
    @pytest.fixture
    def bot_runner(self):
        """Create BotRunner with mocked dependencies."""
        client = AsyncMock()
        client.__class__.__name__ = "PolymarketClient"
        engine = AsyncMock()
        espn = AsyncMock()
        
        return BotRunner(client, engine, espn)
    
    def test_dry_run_default_true(self, bot_runner):
        """
        Test that dry_run defaults to True for safety.
        """
        assert bot_runner.dry_run is True
    
    def test_emergency_stop_default_false(self, bot_runner):
        """
        Test that emergency_stop defaults to False.
        """
        assert bot_runner.emergency_stop is False
    
    def test_enabled_sports_empty_initially(self, bot_runner):
        """
        Test that enabled_sports is empty before initialization.
        """
        assert len(bot_runner.enabled_sports) == 0
    
    def test_user_selected_games_empty_initially(self, bot_runner):
        """
        Test that user_selected_games is empty before initialization.
        """
        assert len(bot_runner.user_selected_games) == 0
