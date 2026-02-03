import os
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_local.db"

import asyncio
import sys
import logging
from sqlalchemy import select
from src.db.database import async_session_factory
from src.models.tracked_market import TrackedMarket

# Silence SQL logs
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)

async def dump_markets():
    print("\n=== MARKETS DUMP ===\n")
    async with async_session_factory() as db:
        query = select(TrackedMarket).limit(100)
        result = await db.execute(query)
        markets = result.scalars().all()
        
        if not markets:
            print("No markets found in DB.")
            return

        for m in markets:
            print(f"[{m.sport}] '{m.home_team}' vs '{m.away_team}' (ID: {m.condition_id})")
            print(f"    Title: {m.question}")
            print(f"    Live: {m.is_live}")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(dump_markets())
