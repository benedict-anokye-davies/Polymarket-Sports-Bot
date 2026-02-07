
import asyncio
import os
import sys
import logging
from pprint import pprint

# Add app to path
sys.path.insert(0, '/app')
from src.services.kalshi_client import KalshiClient

# Setup
API_KEY = "813faefe-becc-4647-807a-295dcf69fcad"
KEY_FILE = "/app/kalshi.key"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestHistory")

async def main():
    if not os.path.exists(KEY_FILE):
        print("Key file not found")
        return

    with open(KEY_FILE, "r") as f:
        pk = f.read()

    client = KalshiClient(api_key=API_KEY, private_key_pem=pk)
    
    # Target Ticker (HOU vs OKC)
    # Ticker from logs: KXNBAGAME-26FEB07HOUOKC-OKC
    ticker = "KXNBAGAME-26FEB07HOUOKC-OKC" 
    
    print(f"\n--- Testing Ticker: {ticker} ---")

    # 1. Standard History (Failing)
    print("\n1. GET /markets/{ticker}/history")
    try:
        res = await client.get_market_history(ticker)
        print("SUCCESS:", res.keys())
    except Exception as e:
        print("FAILED:", e)

    # 2. Candlesticks (Guess)
    print("\n2. GET /markets/{ticker}/candlesticks")
    try:
        res = await client._authenticated_request("GET", f"/markets/{ticker}/candlesticks?limit=100")
        print("SUCCESS:", res.keys())
    except Exception as e:
        print("FAILED:", e)

    # 3. Series Candlesticks probing
    series_ticker = "KXNBAGAME-26FEB07HOUOKC"
    ticker = "KXNBAGAME-26FEB07HOUOKC-OKC"
    base_path = f"/series/{series_ticker}/markets/{ticker}/candlesticks"

    import time
    start = int(time.time() - 86400*5)

    variations = [
        {"start_ts": start, "limit": 100},
        {"start_time": start, "limit": 100},
        {"begin_ts": start, "limit": 100},
        {"start": start, "limit": 100},
        {"min_ts": start, "limit": 100},
        # Maybe period is required?
        {"start_ts": start, "limit": 100, "period": "1h"},
    ]

    print(f"\n3. Probing {base_path} ...")
    
    for v in variations:
        print(f"Testing params: {v}")
        try:
            res = await client._authenticated_request("GET", base_path, params=v)
            print("SUCCESS!", res.keys())
            if "candlesticks" in res:
                print(f"Found {len(res['candlesticks'])} candles")
            break
        except Exception as e:
            print(f"FAILED: {e}")
            # Try to print response text if possible (client logs it)


    # 4. Get Market Details (Verify Ticker)
    print("\n4. GET /markets/{ticker}")
    try:
        res = await client.get_market(ticker)
        print("MARKET STATUS:", res.get("market", {}).get("status"))
    except Exception as e:
        print("FAILED:", e)
        
    await client.close()

if __name__ == "__main__":
    asyncio.run(main())
