
import asyncio
import os
import sys
import json
from datetime import datetime, timezone

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

async def main():
    import httpx
    client = httpx.AsyncClient()
    kalshi_api_base = "https://api.elections.kalshi.com/trade-api/v2"
    
    params = {
        "category": "Sports",
        "status": "open",
        "limit": 200
    }
    
    print(f"Fetching raw markets from {kalshi_api_base}/markets...")
    response = await client.get(f"{kalshi_api_base}/markets", params=params)
    
    data = response.json()
    markets = data.get("markets", [])
    print(f"Fetched {len(markets)} markets.")
    
    now = datetime.now(timezone.utc)
    print(f"Current UTC: {now}")
    
    count = 0
    for m in markets:
        ticker = m.get('ticker', '')
        title = m.get('title', '')
        
        # Filter for something that looks like a game market
        if "NBA" not in ticker and "NFL" not in ticker and "NBA" not in title and "NFL" not in title:
            continue
            
        count += 1
        if count > 20: break
        
        print(f"\nTicker: {ticker}")
        print(f"  Title: {title}")
        print(f"  Status: {m.get('status')}")
        
        close_ts = m.get('close_ts')
        event_start_ts = m.get('event_start_ts')
        
        close_dt = datetime.fromtimestamp(close_ts, tz=timezone.utc) if close_ts else None
        start_dt = datetime.fromtimestamp(event_start_ts, tz=timezone.utc) if event_start_ts else None
        
        print(f"  Close TS: {close_ts} -> {close_dt}")
        print(f"  Event Start: {event_start_ts} -> {start_dt}")
        
        if start_dt:
            hours_since_start = (now - start_dt).total_seconds() / 3600
            print(f"  Hours since start: {hours_since_start:.2f}")
            
    await client.aclose()

if __name__ == "__main__":
    asyncio.run(main())
