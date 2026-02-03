
import os
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_local.db"

import asyncio
import logging
from sqlalchemy import select
from src.db.database import async_session_factory
from src.models import Position, TrackedMarket

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def check_status():
    async with async_session_factory() as db:
        # 1. Check Positions
        result = await db.execute(select(Position))
        positions = result.scalars().all()
        
        if positions:
            print(f"\n✅ FOUND {len(positions)} POSITIONS:")
            for p in positions:
                print(f"  - Market: {p.condition_id} | Side: {p.side} | Size: ${p.size_usdc} | Status: {p.status}")
        else:
            print("\nℹ️ NO POSITIONS OPEN YET.")

        # 2. Check Market Odds for 76ers
        query = select(TrackedMarket).where(TrackedMarket.home_team.ilike("%76ers%"))
        res = await db.execute(query)
        markets = res.scalars().all()
        
        if markets:
            print(f"\n🏀 Found {len(markets)} '76ers' Markets:")
            for market in markets:
                print(f"  --- Market: {market.condition_id} ---")
                print(f"  Title: {market.question}")
                print(f"  Yes Price: {market.current_price_yes}")
                print(f"  No Price: {market.current_price_no}")
                print(f"  Live: {market.is_live}")
                
                if market.current_price_yes and market.current_price_yes < 0.25:
                     print("  🚀 ENTRY SIGNAL MET (< 0.25)!")
                else:
                     print(f"  ⏳ WAITING for odds < 0.25 (Current: {market.current_price_yes})")

if __name__ == "__main__":
    asyncio.run(check_status())
