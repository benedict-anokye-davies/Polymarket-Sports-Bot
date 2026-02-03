
import os
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_local.db"

import asyncio
import logging
from src.db.database import async_session_factory
from sqlalchemy import select
from src.models import TrackedMarket
from src.services.espn_service import ESPNService
from src.services.game_tracker_service import GameTrackerService
from src.services.types import TrackedGame

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def debug_tracking():
    # 1. Setup Services
    espn = ESPNService()
    tracker = GameTrackerService(espn)
    
    # 2. Get DB Market
    async with async_session_factory() as db:
        query = select(TrackedMarket).where(TrackedMarket.home_team == "LA Clippers")
        res = await db.execute(query)
        markets = res.scalars().all()
        
        if not markets:
            print("❌ No 'LA Clippers' markets found in DB!")
            return
            
        print(f"✅ Found {len(markets)} Markets in DB.")
        
        # 3. Test get_live_games
        print("\n--- Testing get_live_games('nba') ---")
        live_games = await espn.get_live_games("nba")
        print(f"Fetched {len(live_games)} LIVE games from ESPN.")
        
        for g in live_games:
            print(f"Live Game: {g.get('id')} - {g.get('name')} (Status: {g.get('status', {}).get('type', {}).get('state')})")

        # 4. Simulate BotRunner Logic (Game Matching)
        print("\n--- Simulating Matching ---")
        for m in markets:
            matched = False
            for event in live_games: # Use LIVE games only
                 # Standardize access
                 if isinstance(event, dict):
                     competitors = event.get('competitions', [{}])[0].get('competitors', [])
                     e_home = next((c['team']['displayName'] for c in competitors if c['homeAway'] == 'home'), "Unknown")
                     e_away = next((c['team']['displayName'] for c in competitors if c['homeAway'] == 'away'), "Unknown")
                     e_id = event.get('id')
                 else:
                     # Parsed state logic if revert happen
                     pass

                 if m.home_team in e_home or m.away_team in e_away:
                      print(f"MATCH FOUND for {m.condition_id} -> ESPN {e_id}")
                      matched = True
                      break
            
            if matched:
                break 

if __name__ == "__main__":
    asyncio.run(debug_tracking())
