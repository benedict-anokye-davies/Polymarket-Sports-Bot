
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

    # 3. Series / Markets / Candlesticks ?
    # Need series ticker. 'KXNBAGAME-26FEB07HOUOKC' ?
    series_ticker = "KXNBAGAME-26FEB07HOUOKC"
    print(f"\n3. GET /series/{series_ticker}/markets/{ticker}/candlesticks")
    try:
        path = f"/series/{series_ticker}/markets/{ticker}/candlesticks?limit=100"
        res = await client._authenticated_request("GET", path)
        print("SUCCESS:", res.keys())
    except Exception as e:
        print("FAILED:", e)

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
