
import asyncio
import sys
sys.path.append("/app")
from src.db.database import async_session_factory
from src.models.tracked_market import TrackedMarket
from sqlalchemy import select
import json

async def main():
    async with async_session_factory() as db:
        result = await db.execute(select(TrackedMarket))
        games = result.scalars().all()
        
        print(f"Found {len(games)} tracked games/markets:")
        for game in games:
            print(f"\n--- Game: {game.home_team} vs {game.away_team} ---")
            print(f"ESPN ID: {game.espn_event_id}")
            print(f"Condition ID/Ticker: {game.condition_id}")
            print(f"Status: Live={game.is_live}, Finished={game.is_finished}")
            print(f"Start Time: {game.game_start_time}")
            print(f"User Selected: {game.is_user_selected}")
            
            # Print price data
            print(f"Current Prices: Yes={game.current_price_yes} No={game.current_price_no}")
            print(f"Baseline Prices: Yes={game.baseline_price_yes} No={game.baseline_price_no}")

if __name__ == "__main__":
    asyncio.run(main())
