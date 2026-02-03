
import asyncio
import logging
from src.services.market_discovery import MarketDiscovery

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    print("--- Starting Kalshi Discovery Check ---")
    service = MarketDiscovery()
    try:
        print("Discovering Kalshi markets...")
        markets = await service.discover_kalshi_markets(
            min_volume=0,
            hours_ahead=168,
            include_live=True
        )
        print(f"\n✅ Discovered {len(markets)} Kalshi markets.")
        
        for m in markets[:5]:
            print(f" - {m.condition_id}: {m.question} ({m.sport}) - Liq: {m.liquidity}")
            
    except Exception as e:
        print(f"\n❌ Error during discovery: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await service.close()

if __name__ == "__main__":
    asyncio.run(main())
