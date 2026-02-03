
import os
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_local.db"

import asyncio
import logging
from datetime import datetime, timezone
from sqlalchemy import select
from src.db.database import async_session_factory
from src.models import TrackedMarket

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def fix_time():
    async with async_session_factory() as db:
        # Find the market
        query = select(TrackedMarket).where(TrackedMarket.home_team == "LA Clippers")
        result = await db.execute(query)
        markets = result.scalars().all()
        
        # Set to specific time: 2026-02-03 03:00:00 UTC
        start_time = datetime(2026, 2, 3, 3, 0, 0, tzinfo=timezone.utc)
        
        updated_count = 0
        for m in markets:
            m.game_start_time = start_time
            updated_count += 1
            
        await db.commit()
        logger.info(f"✅ Successfully updated start time for {updated_count} markets.")

if __name__ == "__main__":
    asyncio.run(fix_time())
