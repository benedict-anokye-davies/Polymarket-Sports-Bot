"""
Test script to verify Kalshi API connectivity.
Tests unauthenticated endpoints (markets) to confirm API is reachable.
"""

import asyncio
import httpx

# Kalshi API URLs
KALSHI_API_PRODUCTION = "https://api.elections.kalshi.com/trade-api/v2"
KALSHI_API_DEMO = "https://demo-api.kalshi.co/trade-api/v2"


async def test_kalshi_api():
    print("=" * 60)
    print("KALSHI API CONNECTION TEST")
    print("=" * 60)
    
    async with httpx.AsyncClient(timeout=15.0) as client:
        # Test 1: Production API - Fetch markets (public endpoint)
        print("\n1. Testing PRODUCTION API (public markets endpoint)...")
        try:
            response = await client.get(
                f"{KALSHI_API_PRODUCTION}/markets",
                params={"limit": 5, "status": "open"}
            )
            if response.status_code == 200:
                data = response.json()
                markets = data.get("markets", [])
                print(f"   [OK] SUCCESS - Found {len(markets)} markets")
                if markets:
                    print(f"   Sample market: {markets[0].get('title', 'N/A')[:60]}...")
            else:
                print(f"   [FAIL] Status {response.status_code}: {response.text[:100]}")
        except Exception as e:
            print(f"   [ERROR] {type(e).__name__}: {e}")
        
        # Test 2: Demo API - Fetch markets
        print("\n2. Testing DEMO API (public markets endpoint)...")
        try:
            response = await client.get(
                f"{KALSHI_API_DEMO}/markets",
                params={"limit": 5, "status": "open"}
            )
            if response.status_code == 200:
                data = response.json()
                markets = data.get("markets", [])
                print(f"   [OK] SUCCESS - Found {len(markets)} markets")
                if markets:
                    print(f"   Sample market: {markets[0].get('title', 'N/A')[:60]}...")
            else:
                print(f"   [FAIL] Status {response.status_code}: {response.text[:100]}")
        except Exception as e:
            print(f"   [ERROR] {type(e).__name__}: {e}")
        
        # Test 3: Sports markets specifically
        print("\n3. Testing SPORTS markets fetch...")
        try:
            response = await client.get(
                f"{KALSHI_API_PRODUCTION}/markets",
                params={"limit": 10, "status": "open", "series_ticker": "NBA"}
            )
            if response.status_code == 200:
                data = response.json()
                markets = data.get("markets", [])
                if markets:
                    print(f"   [OK] SUCCESS - Found {len(markets)} NBA markets")
                    for m in markets[:3]:
                        print(f"      - {m.get('ticker')}: {m.get('title', 'N/A')[:50]}...")
                else:
                    print(f"   [WARN] No NBA markets found (may be off-season or none open)")
            else:
                print(f"   [FAIL] Status {response.status_code}")
        except Exception as e:
            print(f"   [ERROR] {type(e).__name__}: {e}")
        
        # Test 4: Check a market's orderbook (public)
        print("\n4. Testing market orderbook fetch...")
        try:
            # First get any open market
            response = await client.get(
                f"{KALSHI_API_PRODUCTION}/markets",
                params={"limit": 1, "status": "open"}
            )
            if response.status_code == 200:
                markets = response.json().get("markets", [])
                if markets:
                    ticker = markets[0].get("ticker")
                    # Fetch orderbook
                    ob_response = await client.get(
                        f"{KALSHI_API_PRODUCTION}/markets/{ticker}/orderbook"
                    )
                    if ob_response.status_code == 200:
                        ob = ob_response.json()
                        bids = len(ob.get("bids", []))
                        asks = len(ob.get("asks", []))
                        print(f"   [OK] SUCCESS - {ticker} orderbook: {bids} bids, {asks} asks")
                    else:
                        print(f"   [FAIL] {ob_response.status_code}")
        except Exception as e:
            print(f"   [ERROR] {type(e).__name__}: {e}")
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)
    print("\nNOTES:")
    print("- Public endpoints work = API client code is correct")
    print("- Authenticated endpoints (placing orders) require valid API credentials")
    print("- To test authenticated endpoints, user must connect their Kalshi account")


if __name__ == "__main__":
    asyncio.run(test_kalshi_api())
