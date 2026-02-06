
import asyncio
import os
import sys

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.services.bot_runner import _bot_instances
from src.db.database import async_session_factory
from src.db.crud.position import PositionCRUD

async def main():
    print("--- Bot Runtime State Check ---")
    
    if not _bot_instances:
        print("No bot instances running in this process.")
        # This is expected if run as a separate script.
        # But we want to check the DB too.
    
    async with async_session_factory() as db:
        open_positions = await PositionCRUD.get_open_for_user(db, None) # Get all
        print(f"\nOpen Positions in DB: {len(open_positions)}")
        for pos in open_positions:
            print(f"ID: {pos.id}, Ticker: {pos.token_id}, Entry: {pos.entry_price}, Side: {pos.side}")
            # Try to see if there is a tracked market
            from src.db.crud.tracked_market import TrackedMarketCRUD
            tm = await TrackedMarketCRUD.get_by_condition_id(db, pos.user_id, pos.condition_id)
            if tm:
                print(f"  Market: {tm.condition_id}, Finished: {tm.is_finished}, ESPN ID: {tm.espn_event_id}")
            else:
                print("  No TrackedMarket found for this position's condition_id.")

if __name__ == "__main__":
    asyncio.run(main())
