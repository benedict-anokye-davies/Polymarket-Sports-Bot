
import asyncio
import os
import sys
import logging
from datetime import datetime

# Add src to path
sys.path.append(os.getcwd())

from sqlalchemy import select
from src.db.database import async_session_factory
from src.models import TrackedMarket

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("inspect_markets")

async def inspect():
    async with async_session_factory() as db:
        print("\n--- Inspecting ALL Tracked Markets ---")
        
        result = await db.execute(select(TrackedMarket).order_by(TrackedMarket.created_at.desc()))
        markets = result.scalars().all()
        
        print(f"Total Markets Found: {len(markets)}")
        print("-" * 100)
        print(f"{'ID':<38} | {'Sport':<6} | {'Selected':<8} | {'Start Time':<20} | {'Last Update':<20} | {'Question'}")
        print("-" * 100)
        
        for m in markets:
            start = m.game_start_time.strftime('%Y-%m-%d %H:%M') if m.game_start_time else "None"
            updated = m.last_updated_at.strftime('%Y-%m-%d %H:%M') if m.last_updated_at else "None"
            question = (m.question or "")[:40]
            
            print(f"{str(m.id):<38} | {m.sport:<6} | {str(m.is_user_selected):<8} | {start:<20} | {updated:<20} | {question}")

        print("-" * 100)

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(inspect())
