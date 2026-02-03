
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
    
    print("Fetching up to 1000 markets to sample...")
    
    all_markets = []
    cursor = None
    
    for _ in range(5): # 5 pages of 200 = 1000 markets
        params = {
            "category": "Sports",
            "status": "open",
            "limit": 200
        }
        if cursor: params["cursor"] = cursor
        
        try:
            resp = await client.get(f"{kalshi_api_base}/markets", params=params)
            data = resp.json()
            page = data.get("markets", [])
            all_markets.extend(page)
            cursor = data.get("cursor")
            if not cursor: break
        except Exception as e:
            print(f"Error: {e}")
            break
            
    print(f"Fetched {len(all_markets)} markets.")
    
    print("\n--- Sample Markets (Every 50th) ---")
    for i, m in enumerate(all_markets):
        if i % 50 == 0:
            print(f"[{i}] {m.get('ticker')}")
            print(f"     Title: {m.get('title')}")
            print(f"     Status: {m.get('status')}")
            ts = m.get('event_start_ts')
            dt = datetime.fromtimestamp(ts, tz=timezone.utc) if ts else "None"
            print(f"     Start: {dt}")
            
    await client.aclose()

if __name__ == "__main__":
    asyncio.run(main())
