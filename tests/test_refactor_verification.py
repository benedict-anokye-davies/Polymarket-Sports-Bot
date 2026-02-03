import asyncio
import logging
import sys
from unittest.mock import MagicMock, AsyncMock

# Add src to path
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.services.bot_runner import BotRunner
from src.services.game_tracker_service import GameTrackerService
from src.services.espn_service import ESPNService
from src.services.trading_engine import TradingEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VERIFY")

async def test_bot_refactor():
    logger.info("Initializing services...")
    
    # Mock dependencies
    trading_client = AsyncMock()
    trading_client.get_balance.return_value = {"usdc": 1000.0}
    
    # Mock TradingEngine dependencies
    mock_db = AsyncMock()
    mock_settings = MagicMock()
    mock_settings.max_daily_loss_usdc = 100
    mock_settings.max_portfolio_exposure_usdc = 1000
    
    start_time = MagicMock()
    start_time.hour = 17
    start_time.minute = 0
    
    mock_sport_config = MagicMock()
    mock_sport_config.enabled = True
    mock_sport_config.min_liquidity = 1000
    mock_sport_config.min_volume = 1000
    mock_sport_config.max_spread = 0.1
    mock_sport_config.min_time_remaining_seconds = 300
    mock_sport_config.game_start_window_hours_min = 0
    mock_sport_config.game_start_window_hours_max = 24
    mock_sport_config.min_entry_confidence_score = 0.6
    
    mock_configs = {"nba": mock_sport_config}
    
    trading_engine = TradingEngine(
        db=mock_db,
        user_id="test_user",
        trading_client=trading_client,
        global_settings=mock_settings,
        sport_configs=mock_configs
    )
    
    # Mock ESPN service to avoid real network calls during test
    espn_service = AsyncMock(spec=ESPNService)
    espn_service.get_scoreboard.return_value = [
        {
            "id": "123",
            "name": "Lakers vs Celtics",
            "shortName": "LAL @ BOS",
            "date": "2024-01-01T00:00:00Z",
            "status": {"type": {"state": "in"}, "period": 1, "displayClock": "10:00"},
            "competitions": [{
                "competitors": [
                    {"homeAway": "home", "team": {"displayName": "Celtics", "abbreviation": "BOS", "id": "1"}},
                    {"homeAway": "away", "team": {"displayName": "Lakers", "abbreviation": "LAL", "id": "2"}}
                ]
            }]
        }
    ]
    espn_service.get_game_details.return_value = {
        "status": {"type": {"state": "in"}, "period": 1, "displayClock": "9:30"},
        "competitions": [{
            "competitors": [
                {"homeAway": "home", "score": "10"},
                {"homeAway": "away", "score": "8"}
            ]
        }]
    }
    
    # Initialize BotRunner
    logger.info("Creating BotRunner...")
    bot = BotRunner(trading_client, trading_engine, espn_service)
    
    # Verify GameTrackerService initialization
    if not isinstance(bot.game_tracker, GameTrackerService):
        logger.error("❌ match: bot.game_tracker is not instance of GameTrackerService")
        return False
    logger.info("✅ GameTrackerService initialized correctly")
    
    # Simulate tracking a game
    from src.services.market_discovery import DiscoveredMarket
    market = DiscoveredMarket(
        condition_id="test_cond",
        token_id_yes="yes123",
        token_id_no="no123",
        question="Lakers vs Celtics",
        description="desc",
        sport="nba",
        home_team="Celtics",
        away_team="Lakers",
        game_start_time=None,
        end_date=None,
        volume_24h=10000,
        liquidity=5000,
        current_price_yes=0.5,
        current_price_no=0.5,
        spread=0.01
    )
    
    logger.info("Manually adding tracked game...")
    # We call the method directly to simulate _start_tracking_game logic
    from src.services.types import TrackedGame
    tracked = TrackedGame(
        espn_event_id="123",
        sport="nba",
        home_team="Celtics",
        away_team="Lakers",
        market=market
    )
    
    bot.tracked_games["123"] = tracked
    bot.game_tracker.add_game(tracked)
    
    # Run one poll cycle
    logger.info("Running manual update cycle...")
    finished_games = await bot.game_tracker.update_all_games()
    
    # Verify Sync
    game = bot.tracked_games["123"]
    if game.home_score == 10 and game.away_score == 8 and game.clock == "9:30":
        logger.info("✅ Game state synced successfully via GameTrackerService")
    else:
        logger.error(f"❌ Game state mismatch: Score {game.home_score}-{game.away_score}, Clock {game.clock}")
        return False
        
    logger.info("All refactor tests passed!")
    return True

if __name__ == "__main__":
    try:
        success = asyncio.run(test_bot_refactor())
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
