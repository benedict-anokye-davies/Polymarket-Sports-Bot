import os
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_local.db"
import asyncio
from sqlalchemy import select, func
from src.db.database import async_session_factory
from src.models import TrackedMarket, User

async def verify():
    async with async_session_factory() as db:
        print("--- DB Verification ---")
        
        # Check User
        user_res = await db.execute(select(User).where(User.username == "live_tester"))
        user = user_res.scalars().first()
        if user:
            print(f"User 'live_tester' found: {user.id}")
        else:
            print("User 'live_tester' NOT FOUND")
            
        # Count all
        total = await db.scalar(select(func.count(TrackedMarket.id)))
        print(f"Total TrackedMarkets: {total}")
        
        if user:
            # Count for user
            user_total = await db.scalar(select(func.count(TrackedMarket.id)).where(TrackedMarket.user_id == user.id))
            print(f"TrackedMarkets for live_tester: {user_total}")
            
            # Count selected
            selected = await db.scalar(select(func.count(TrackedMarket.id)).where(TrackedMarket.user_id == user.id, TrackedMarket.is_user_selected == True))
            print(f"Selected for live_tester: {selected}")
            
            # Count finished
            finished = await db.scalar(select(func.count(TrackedMarket.id)).where(TrackedMarket.user_id == user.id, TrackedMarket.is_finished == True))
            print(f"Finished for live_tester: {finished}")
            
            # Show first 3
            res = await db.execute(select(TrackedMarket).where(TrackedMarket.user_id == user.id).limit(3))
            rows = res.scalars().all()
            for i, r in enumerate(rows):
                print(f"Row {i}: Ticker={r.condition_id}, Selected={r.is_user_selected} (Type: {type(r.is_user_selected)}), Finished={r.is_finished}, Sport={r.sport}")

if __name__ == "__main__":
    asyncio.run(verify())
