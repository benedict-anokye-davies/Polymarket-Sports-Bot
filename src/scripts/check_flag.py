
import os
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_local.db"

import asyncio
from sqlalchemy import select
from src.db.database import async_session_factory
from src.models import TrackedMarket

async def check_flag():
    async with async_session_factory() as db:
        query = select(TrackedMarket).where(TrackedMarket.home_team == "LA Clippers")
        res = await db.execute(query)
        markets = res.scalars().all()
        
        for m in markets:
            print(f"Market: {m.condition_id} | User Selected: {m.is_user_selected}")

if __name__ == "__main__":
    asyncio.run(check_flag())
