
import os
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_local.db"

import asyncio
from sqlalchemy import select, or_
from src.db.database import async_session_factory
from src.models import TrackedMarket

async def check_price():
    async with async_session_factory() as db:
        query = select(TrackedMarket).where(
            or_(
                TrackedMarket.home_team.ilike("%76ers%"),
                TrackedMarket.away_team.ilike("%76ers%")
            )
        )
        res = await db.execute(query)
        markets = res.scalars().all()
        
        for m in markets:
            print(f"Market: {m.condition_id}")
            print(f"  Teams: {m.home_team} vs {m.away_team}")
            print(f"  Price YES: {m.current_price_yes}")
            print(f"  Live: {m.is_live}")

if __name__ == "__main__":
    asyncio.run(check_price())
