
import asyncio
import sys
sys.path.append("/app")
from src.db.database import async_session_factory
from src.models.tracked_market import TrackedMarket
from sqlalchemy import delete

async def main():
    print("--- Clearing All Tracked Markets ---")
    async with async_session_factory() as db:
        # Delete all records from tracked_markets table
        result = await db.execute(delete(TrackedMarket))
        await db.commit()
        print(f"Deleted {result.rowcount} tracked markets.")

if __name__ == "__main__":
    asyncio.run(main())
