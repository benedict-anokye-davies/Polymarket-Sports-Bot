
import os
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_local.db"

import asyncio
import logging
from sqlalchemy import select
from src.db.database import async_session_factory
from src.models import TrackedMarket

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def fix_teams():
    async with async_session_factory() as db:
        # Find the market
        query = select(TrackedMarket).where(TrackedMarket.home_team.ilike("%76ers%"))
        result = await db.execute(query)
        markets = result.scalars().all()
        
        updated_count = 0
        for m in markets:
            # ESPN: Home='LA Clippers', Away='Philadelphia 76ers'
            # Current DB: Home='Philadelphia 76ers', Away='Los Angeles Clippers' (WRONG)
            
            # Fix it
            m.home_team = "LA Clippers"
            m.away_team = "Philadelphia 76ers"
            m.sport = "nba"
            
            logger.info(f"Fixed teams for {m.condition_id}: Home='{m.home_team}', Away='{m.away_team}'")
            updated_count += 1
            
        await db.commit()
        logger.info(f"✅ Successfully updated {updated_count} markets.")

if __name__ == "__main__":
    asyncio.run(fix_teams())
