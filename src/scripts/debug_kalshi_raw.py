
import asyncio
import os
import sys
import json
from datetime import datetime, timezone

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.config import settings
from src.services.kalshi_client import KalshiClient

async def main():
    print("Initializing KalshiClient...")
    # Use dummy keys if env vars missing, just for fetching public markets
    key_id = settings.secret_key or "test" # This is wrong, secret_key is internal. 
    # But KalshiClient needs args. 
    # We can try to instantiate it with dummy values since we only want public endpoints?
    # Actually, KalshiClient.__init__ validates the key format.
    # Let's try to get credentials from env or just mock them if we are only calling public endpoints.
    # Wait, `get_markets` calls `_authenticated_request`. 
    # BUT `discover_kalshi_markets` in `market_discovery.py` says:
    # "Create a temporary unauthenticated client for market discovery... Market data endpoints don't require authentication"
    # It uses a raw `httpx.AsyncClient` there.
    
    # So let's reproduce THAT logic exactly.
    
    import httpx
    client = httpx.AsyncClient()
    kalshi_api_base = "https://api.elections.kalshi.com/trade-api/v2"
    
    params = {
        "category": "Sports",
        "status": "open",
        "limit": 20
    }
    
    print(f"Fetching raw markets from {kalshi_api_base}/markets...")
    response = await client.get(f"{kalshi_api_base}/markets", params=params)
    
    if response.status_code != 200:
        print(f"Error: {response.status_code} {response.text}")
        return

    data = response.json()
    markets = data.get("markets", [])
    print(f"Fetched {len(markets)} markets.")
    
    now = datetime.now(timezone.utc)
    print(f"Current UTC: {now}")
    
    for i, m in enumerate(markets):
        print(f"\n[{i}] {m.get('ticker')}")
        print(f"  Title: {m.get('title')}")
        print(f"  Status: {m.get('status')}")
        print(f"  Close TS: {m.get('close_ts')} -> {datetime.fromtimestamp(m.get('close_ts'), tz=timezone.utc) if m.get('close_ts') else 'None'}")
        print(f"  Event Start: {m.get('event_start_ts')} -> {datetime.fromtimestamp(m.get('event_start_ts'), tz=timezone.utc) if m.get('event_start_ts') else 'None'}")
        print(f"  SubTitle: {m.get('subtitle')}")
        
    await client.aclose()

if __name__ == "__main__":
    asyncio.run(main())
