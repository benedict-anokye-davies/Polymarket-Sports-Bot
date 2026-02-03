
import asyncio
import os
import sys
import json
from datetime import datetime, timezone

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.services.kalshi_client import KalshiClient

async def main():
    import httpx
    client = httpx.AsyncClient()
    kalshi_api_base = "https://api.elections.kalshi.com/trade-api/v2"
    
    # We will fetch multiple pages
    cursor = None
    total_fetched = 0
    found_games = 0
    
    now = datetime.now(timezone.utc)
    print(f"Current UTC: {now}")
    print("Searching for potentially stale games (started > 4 hours ago)...")
    
    for page in range(10): # Check first 2000 markets
        params = {
            "category": "Sports",
            "status": "open",
            "limit": 200
        }
        if cursor: 
            params["cursor"] = cursor
            
        try:
            response = await client.get(f"{kalshi_api_base}/markets", params=params)
            data = response.json()
            markets = data.get("markets", [])
            cursor = data.get("cursor")
        except Exception as e:
            print(f"Fetch error: {e}")
            break
            
        if not markets:
            break
            
        total_fetched += len(markets)
        
        for m in markets:
            ticker = m.get('ticker', '')
            title = m.get('title', '')
            
            # Simple heuristic for game markets from market_discovery.py
            is_game = False
            sport = None
            if "NBA" in ticker or "NBA" in title: is_game = True; sport = "NBA"
            elif "NFL" in ticker or "NFL" in title: is_game = True; sport = "NFL"
            elif "MLB" in ticker or "MLB" in title: is_game = True; sport = "MLB"
            elif "NHL" in ticker or "NHL" in title: is_game = True; sport = "NHL"
            elif "Soccer" in title: is_game = True; sport = "Soccer"
            
            if not is_game: continue

            event_start_ts = m.get('event_start_ts')
            if not event_start_ts: continue
            
            start_dt = datetime.fromtimestamp(event_start_ts, tz=timezone.utc)
            hours_since_start = (now - start_dt).total_seconds() / 3600
            
            # Print ALL games to see what's happening, but highlight OLD ones
            if hours_since_start > 4:
                print(f"\n[STALE CANDIDATE] {ticker} ({sport})")
                print(f"  Title: {title}")
                print(f"  Starts: {start_dt} ({hours_since_start:.2f} hours ago)")
                print(f"  Close TS: {m.get('close_ts')} -> {datetime.fromtimestamp(m.get('close_ts'), tz=timezone.utc) if m.get('close_ts') else 'None'}")
                print(f"  Status: {m.get('status')}")
                found_games += 1
                
        if found_games > 10:
            print("Found enough examples.")
            break
            
        if not cursor:
            break
            
    print(f"Scanned {total_fetched} markets.")
    await client.aclose()

if __name__ == "__main__":
    asyncio.run(main())
