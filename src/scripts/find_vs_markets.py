
import asyncio
import os
import sys
import json
from datetime import datetime, timezone

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

async def main():
    import httpx
    client = httpx.AsyncClient()
    kalshi_api_base = "https://api.elections.kalshi.com/trade-api/v2"
    
    print("Scanning up to 5000 markets for 'vs' games...")
    
    all_markets = []
    cursor = None
    
    found_vs = 0
    
    for page in range(25): # 25 * 200 = 5000
        params = {
            "category": "Sports",
            "status": "open",
            "limit": 200
        }
        if cursor: params["cursor"] = cursor
        
        try:
            resp = await client.get(f"{kalshi_api_base}/markets", params=params)
            data = resp.json()
            markets = data.get("markets", [])
            all_markets.extend(markets)
            cursor = data.get("cursor")
            
            # Check this batch
            for m in markets:
                title = m.get('title', '').lower()
                if " vs " in title or " versus " in title:
                    found_vs += 1
                    # Detailed print for the first 10, then summary
                    if found_vs <= 10 or found_vs % 20 == 0:
                        event_start_ts = m.get('event_start_ts')
                        dt = datetime.fromtimestamp(event_start_ts, tz=timezone.utc) if event_start_ts else None
                        now = datetime.now(timezone.utc)
                        stale_str = ""
                        if dt and dt < now:
                            diff = (now - dt).total_seconds() / 3600
                            stale_str = f" [STARTED {diff:.1f}h AGO]"
                            
                        print(f"FOUND: {m.get('title')} {stale_str}")
                        print(f"   Ticker: {m.get('ticker')}")
                        print(f"   Start: {dt}")
                        print(f"   Close: {m.get('close_ts')}")
            
            if not cursor: break
        except Exception as e:
            print(f"Error: {e}")
            break
            
    print(f"Scanned {len(all_markets)} total markets. Found {found_vs} 'vs' markets.")
    await client.aclose()

if __name__ == "__main__":
    asyncio.run(main())
