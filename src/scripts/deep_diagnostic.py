import asyncio
import logging
import sys
from sqlalchemy import select
from src.db.database import async_session_factory
from src.models.tracked_market import TrackedMarket
from src.models.position import Position
from src.services.espn_service import ESPNService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def run_diagnostic():
    print("\n=== DEEP DIAGNOSTIC ===\n")
    
    async with async_session_factory() as db:
        # 1. Check Specific Market (76ers or Clippers)
        print("Searching for Clippers/76ers market in DB...")
        query = select(TrackedMarket).where(
            (TrackedMarket.home_team.ilike('%Clippers%')) | 
            (TrackedMarket.away_team.ilike('%Clippers%'))
        )
        result = await db.execute(query)
        markets = result.scalars().all()
        
        if not markets:
            print("❌ CRITICAL: No market found for Clippers in DB!")
            # Check user id association
            return

        for m in markets:
            print(f"\nMarket ID: {m.id}")
            print(f"  Condition ID: {m.condition_id}")
            print(f"  Match: {m.away_team} @ {m.home_team}")
            print(f"  Status: is_live={m.is_live}, is_finished={m.is_finished}")
            print(f"  Prices: YES={m.current_price_yes}, NO={m.current_price_no}")
            print(f"  Baselines: YES={m.baseline_price_yes} (Captured: {m.baseline_captured_at})")
            print(f"  Last Update: {m.last_updated_at}")
            print(f"  ESPN ID: {m.espn_event_id}")
            
            # Check for positions
            pos_query = select(Position).where(Position.tracked_market_id == m.id)
            pos_result = await db.execute(pos_query)
            positions = pos_result.scalars().all()
            print(f"  Positions: {len(positions)} open")
            
            # Check ESPN directly for this game
            if m.espn_event_id:
                print(f"  Verifying ESPN ID {m.espn_event_id}...")
                espn = ESPNService()
                try:
                    # We can't fetch single event easily without logic, but we can search live
                    games = await espn.get_live_games("nba")
                    matched_game = next((g for g in games if g['event_id'] == m.espn_event_id), None)
                    if matched_game:
                        print(f"  ✅ ESPN Confirmation: LIVE")
                        print(f"     Score: {matched_game.get('score_diff')}")
                        print(f"     Period: {matched_game.get('period')}")
                        print(f"     Clock: {matched_game.get('clock')}")
                    else:
                        print("  ⚠️ ESPN Warning: Game not found in 'get_live_games' list.")
                        # Try finding it in full scoreboard
                        scoreboard = await espn.get_scoreboard("nba")
                        sb_game = next((g for g in scoreboard if g['id'] == m.espn_event_id), None)
                        if sb_game:
                             status = sb_game.get('status',{}).get('type',{}).get('state')
                             print(f"     Found in Scoreboard. Status: {status}")
                except Exception as e:
                    print(f"  ESPN Check Error: {e}")
                finally:
                    await espn.close()

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run_diagnostic())
