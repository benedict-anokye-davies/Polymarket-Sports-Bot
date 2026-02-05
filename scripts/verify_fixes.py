import asyncio
import os
import sys
import uuid
from decimal import Decimal
from unittest.mock import MagicMock, AsyncMock

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.services.account_manager import AccountManager
from src.services.kalshi_client import KalshiClient
from src.services.trading_engine import TradingEngine, EffectiveConfig
from src.services.bot_runner import BotRunner
from src.models.sport_config import SportConfig
from src.models.market_config import MarketConfig
from src.models.tracked_market import TrackedMarket

async def verify_account_manager():
    print("\n--- Verifying AccountManager ---")
    mock_db = AsyncMock()
    am = AccountManager(mock_db, uuid.uuid4())
    if hasattr(am, 'get_client_for_account'):
        print("✅ AccountManager.get_client_for_account exists")
    else:
        print("❌ AccountManager.get_client_for_account MISSING")

async def verify_kalshi_client():
    print("\n--- Verifying KalshiClient ---")
    if hasattr(KalshiClient, 'get_orders'):
         print("✅ KalshiClient.get_orders alias exists")
    else:
         print("❌ KalshiClient.get_orders MISSING")
    
    if hasattr(KalshiClient, 'get_balance'):
         print("✅ KalshiClient.get_balance exists")
    else:
         print("❌ KalshiClient.get_balance MISSING")

async def verify_trading_engine_overrides():
    print("\n--- Verifying TradingEngine Overrides ---")
    # Use mock instead of real SportConfig to avoid DB/initialization issues
    sport_config = MagicMock()
    sport_config.entry_threshold_pct = Decimal("0.05") # 5%
    sport_config.take_profit_pct = Decimal("0.10")
    sport_config.stop_loss_pct = Decimal("0.05")
    sport_config.default_position_size_usdc = Decimal("10.0")
    sport_config.is_enabled = True
    
    # Init engine with mock dependencies
    engine = TradingEngine(
        db=AsyncMock(),
        user_id=uuid.uuid4(),
        trading_client=AsyncMock(),
        global_settings=AsyncMock(),
        sport_configs={"nba": sport_config}
    )
    
    # Test EffectiveConfig with overrides
    market = TrackedMarket(sport="nba", condition_id="test")
    
    overrides = {
        "entry_threshold_drop": Decimal("0.08"), # 8% override
        "position_size_usdc": Decimal("50.0")
    }
    
    config = engine._get_effective_config(market, overrides)
    
    if config.entry_threshold_pct == Decimal("0.08"):
        print("✅ Entry threshold override applied correctly (0.08)")
    else:
        print(f"❌ Entry threshold override FAILED: {config.entry_threshold_pct}")
        
    if config.default_position_size_usdc == Decimal("50.0"):
        print("✅ Position size override applied correctly (50.0)")
    else:
        print(f"❌ Position size override FAILED: {config.default_position_size_usdc}")

async def verify_bot_runner_cleanup():
    print("\n--- Verifying BotRunner Attributes ---")
    if hasattr(BotRunner, '_cleanup_loop'):
        print("✅ BotRunner has _cleanup_loop")
    else:
        print("❌ BotRunner missing _cleanup_loop")

async def main():
    await verify_account_manager()
    await verify_kalshi_client()
    await verify_trading_engine_overrides()
    await verify_bot_runner_cleanup()

if __name__ == "__main__":
    asyncio.run(main())
