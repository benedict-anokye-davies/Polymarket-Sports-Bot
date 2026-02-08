import asyncio
import sys
import json
sys.path.insert(0, '/app')
from src.services.espn_service import ESPNService

async def main():
    print("Fetching ESPN NBA Scoreboard...")
    espn = ESPNService()
    try:
        games = await espn.get_scoreboard("nba")
        print(f"Found {len(games)} games.")
        
        for game in games:
            name = game.get("name", "Unknown")
            status = game.get("status", {})
            state = status.get("type", {}).get("state", "unknown")
            detail = status.get("type", {}).get("detail", "no detail")
            period = status.get("period", 0)
            clock = status.get("displayClock", "0:00")
            
            parsed = espn.parse_game_state(game, "nba")
            is_live = parsed["is_live"]
            
            print(f"Game: {name}")
            print(f"  Status: {state} ({detail})")
            print(f"  Period: {period}, Clock: {clock}")
            print(f"  Is Live (Parsed): {is_live}")
            
            # Print competitors to check abbreviations
            comps = game.get("competitions", [{}])[0].get("competitors", [])
            teams = []
            for c in comps:
                team = c.get("team", {})
                teams.append(f"{team.get('abbreviation')} ({team.get('displayName')})")
            print(f"  Teams: {', '.join(teams)}")
            print("-" * 30)
            
    finally:
        await espn.close()

if __name__ == "__main__":
    asyncio.run(main())
