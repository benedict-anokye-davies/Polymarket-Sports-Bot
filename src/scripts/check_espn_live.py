import asyncio
import logging
from src.services.espn_service import ESPNService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def check_live_games():
    print("\n=== CHECKING LIVE ESPN GAMES ===\n")
    service = ESPNService()
    
    # Check NBA
    print("Checking NBA...")
    nba_games = await service.get_live_games("nba")
    for game in nba_games:
        status = "LIVE" if game.get("formatted_period") else "PREGAME/FINAL"
        print(f"[{status}] {game['away_team']} @ {game['home_team']}")
        print(f"   Score: {game.get('away_score')} - {game.get('home_score')}")
        print(f"   Period: {game.get('formatted_period')} ({game.get('clock')})")
        print(f"   ESPN ID: {game.get('espn_event_id')}")
        print("-" * 30)

    # Check NCAAB
    print("\nChecking NCAAB...")
    ncaab_games = await service.get_live_games("ncaab")
    for game in ncaab_games:
        if game.get("status") == "in": # rough check for live
             print(f"[LIVE] {game['away_team']} @ {game['home_team']} (Score: {game.get('away_score')}-{game.get('home_score')})")

    await service.close()

if __name__ == "__main__":
    asyncio.run(check_live_games())
