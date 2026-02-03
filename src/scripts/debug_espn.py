
import asyncio
from src.services.espn_service import ESPNService
import logging

logging.basicConfig(level=logging.INFO)

async def check_espn():
    espn = ESPNService()
    print("Fetching ESPN NBA Scoreboard...")
    games = await espn.get_scoreboard("nba")
    
    print(f"\nFound {len(games)} NBA games:")
    found_76ers = False
    for g in games:
        # Check if g is dict or object
        if isinstance(g, dict):
            gid = g.get('id')
            name = g.get('shortName') or g.get('name')
            date = g.get('date')
            status = g.get('status', {}).get('type', {}).get('name')
            
            competitors = g.get('competitions', [{}])[0].get('competitors', [])
            home = next((c['team']['displayName'] for c in competitors if c['homeAway'] == 'home'), "Unknown")
            away = next((c['team']['displayName'] for c in competitors if c['homeAway'] == 'away'), "Unknown")
        else:
            # Fallback if it is an object (unlikely in this codebase based on error)
            gid = g.id
            name = g.short_name
            date = g.date
            status = g.status
            home = g.home_team
            away = g.away_team

        print(f"  [{gid}] {name} ({date}) - Status: {status}")
        print(f"     Home: '{home}' | Away: '{away}'")
        
        if "76ers" in home or "76ers" in away:
            found_76ers = True
            
    if not found_76ers:
        print("\n⚠️ WARNING: No 76ers game found in ESPN response!")

if __name__ == "__main__":
    asyncio.run(check_espn())
