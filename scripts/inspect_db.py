
import asyncio
import os
import sys
from datetime import datetime, timezone

# Add src to path
sys.path.append(os.getcwd())

from sqlalchemy import select
from src.db.database import async_session_factory
from src.models.tracked_market import TrackedMarket

async def inspect_db():
    async with async_session_factory() as db:
        print("\n--- Inspecting 'Available Games' (Unselected Markets) ---")
        
        # Query unselected games
        query = select(TrackedMarket).where(
            TrackedMarket.is_user_selected == False
        ).order_by(TrackedMarket.game_start_time.asc())
        
        result = await db.execute(query)
        markets = result.scalars().all()
        
        now = datetime.now(timezone.utc)
        count = 0
        old_count = 0
        finished_count = 0
        
        print(f"{'ID':<36} | {'Game':<40} | {'Start Time':<20} | {'Status':<10} | {'Last Update':<20}")
        print("-" * 130)
        
        for m in markets:
            start_time = m.game_start_time.replace(tzinfo=timezone.utc) if m.game_start_time.tzinfo is None else m.game_start_time
            is_old = start_time < now
            status = "FINISHED" if m.is_finished else ("LIVE" if m.is_live else "PRE")
            
            # Highlight potentially problematic ones (Old but not finished)
            if is_old and not m.is_finished:
                status = ">>> OLD <<<"
                old_count += 1
            
            if m.is_finished:
                finished_count += 1
                
            print(f"{str(m.id):<36} | {m.home_team} vs {m.away_team:<20} | {start_time.strftime('%Y-%m-%d %H:%M')} | {status:<10} | {m.last_updated_at.strftime('%Y-%m-%d %H:%M') if m.last_updated_at else 'None'}")
            count += 1
            
        print("-" * 130)
        print(f"Total Unselected Markets: {count}")
        print(f"Finished (hidden from UI?): {finished_count}")
        print(f"OLD but NOT FINISHED (Problematic): {old_count}")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(inspect_db())
