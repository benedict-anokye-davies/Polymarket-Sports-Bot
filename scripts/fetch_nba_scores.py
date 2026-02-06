
import asyncio
import httpx

async def get_nba():
    url = "https://site.web.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.get(url)
            res.raise_for_status()
            data = res.json()
            events = data.get("events", [])
            print(f"Found {len(events)} events.")
            for event in events:
                eid = event.get("id")
                name = event.get("name")
                date = event.get("date")
                status = event.get("status", {}).get("type", {}).get("name")
                
                competitors = event.get("competitions", [{}])[0].get("competitors", [])
                home_team = "Unknown"
                away_team = "Unknown"
                for comp in competitors:
                    team_name = comp.get("team", {}).get("displayName")
                    abb = comp.get("team", {}).get("abbreviation")
                    if comp.get("homeAway") == "home":
                        home_team = f"{team_name} ({abb})"
                    else:
                        away_team = f"{team_name} ({abb})"
                
                print(f"ID: {eid} | {name} | {date} | Status: {status} | Home: {home_team} | Away: {away_team}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(get_nba())
