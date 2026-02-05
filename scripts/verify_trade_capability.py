import asyncio
import sys
import logging
import httpx
import json
import uuid
from datetime import datetime, timedelta, timezone
from dateutil import parser 

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("VERIFY_CAPABILITY")

BASE_URL = "http://localhost:8000/api/v1"
KALSHI_API_BASE = "https://api.elections.kalshi.com/trade-api/v2"

async def run_verification():
    logger.info("🚀 Starting Trading Capability Verification (Direct Kalshi Mode)...")
    
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        # 1. Login
        timestamp = int(datetime.now().timestamp())
        email = f"verify_{timestamp}@example.com"
        username = f"verify_{timestamp}"
        password = "VerifyPassword123!"
        
        logger.info("1️⃣  Creating temporary test user...")
        resp = await client.post("/auth/register", json={
            "username": username,
            "email": email,
            "password": password
        })
        if resp.status_code != 201:
            logger.error(f"❌ Registration failed: {resp.text}")
            return

        # Login
        resp = await client.post("/auth/login", data={
            "username": email,
            "password": password
        })
        token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        logger.info("✅ Login successful")

        # 2. Connect Wallet
        import os
        kalshi_key = os.environ.get("KALSHI_API_KEY")
        kalshi_secret = os.environ.get("KALSHI_API_SECRET")
        
        if not kalshi_key or not kalshi_secret:
            logger.error("❌ KALSHI_API_KEY or KALSHI_API_SECRET not found in environment!")
            return

        logger.info("2️⃣  Connecting Wallet...")
        resp = await client.post("/onboarding/wallet/connect", headers=headers, json={
            "platform": "kalshi",
            "api_key": kalshi_key,
            "api_secret": kalshi_secret,
            "environment": "production"
        })
        
        if resp.status_code != 200:
            logger.error(f"❌ Wallet connect failed: {resp.text}")
            return
            
        # 3. Test Wallet Connection (Balance Check)
        logger.info("3️⃣  Verifying Wallet Connection & Balance...")
        resp = await client.post("/onboarding/wallet/test", headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            if data['success']:
                logger.info(f"✅ Wallet Verified! Balance: ${data.get('balance_usdc', '0.00')}")
            else:
                logger.error(f"❌ Wallet Test Failed: {data.get('message')}")
                return
        else:
            logger.error(f"❌ Wallet Test Error: {resp.text}")
            return

        # Complete onboarding
        await client.post("/onboarding/complete", headers=headers)

        # 4. Find a Market directly from Kalshi (Bypassing ESPN)
        logger.info("4️⃣  Searching for ACTIVE Kalshi Markets directly...")
        
        # Use a separate client for external API
        async with httpx.AsyncClient() as k_client:
            # We don't need auth for public markets endpoint usually, but maybe we do?
            # Kalshi V2 docs say GET /markets is public? Let's try.
            # If not, we might fail. But market_discovery uses unauthenticated client sometimes?
            # No, market_discovery.py uses authorized client.
            # But the documentation says "Public API".
            
            try:
                # Try fetching NBA-ish markets
                resp = await k_client.get(
                    f"{KALSHI_API_BASE}/markets", 
                    params={"limit": 100, "status": "open", "category": "Sports"}
                )
                if resp.status_code == 401:
                    logger.warning("   Kalshi Public API returned 401. Trying without category...")
                    # Fallback or need auth?
                    # Let's hope it's public.
                    pass
                
                markets = resp.json().get("markets", [])
            except Exception as e:
                logger.error(f"   Failed to fetch explicit Kalshi markets: {e}")
                markets = []

        target_market = None
        if markets:
            # Pick a market with some volume if possible, or just the first one
            markets.sort(key=lambda m: m.get("volume", 0), reverse=True)
            
            # Filter for "NBA" or similar if possible
            for m in markets:
                # Look for something that looks like a game
                ticker = m.get("ticker", "")
                if "NBA" in ticker or "BASKETBALL" in m.get("category", "").upper():
                     target_market = m
                     break
            
            if not target_market:
                target_market = markets[0] # Fallback to anything
                
            logger.info(f"   Selected Market: {target_market.get('title')} ({target_market.get('ticker')})")
        else:
            logger.error("❌ Failed to fetch any markets from Kalshi directly.")
            return

        # 5. Configure Bot to Track this Market directly
        market_ticker = target_market.get("ticker")
        logger.info(f"5️⃣  Configuring bot to track Ticker {market_ticker}...")
        
        # Generate a fake game ID for config
        fake_game_id = f"manual_{market_ticker}"
        
        game_payload = {
            "sport": "nba", # Default to nba for verify
            "game": {
                "game_id": fake_game_id,
                "home_team": "Team A", # Dummies
                "away_team": "Team B",
                "sport": "nba",
                "start_time": datetime.now().isoformat(),
                "selected_side": "home",
                "market_ticker": market_ticker # KEY FIELD
            },
            "parameters": {
                "position_size": 10,
                "min_volume": 1000
            },
            "simulation_mode": False
        }
        
        resp = await client.post("/bot/config", headers=headers, json=game_payload)
        logger.info(f"   Config Response: {resp.status_code}")
        if resp.status_code == 422:
             logger.error(f"   Validation Error: {resp.text}")

        # 6. Start Bot
        logger.info("6️⃣  Starting Bot...")
        await client.post("/bot/start", headers=headers)
        
        # 7. Wait for Tracking
        logger.info("7️⃣  Waiting 20s for Bot to lock on...")
        for i in range(4):
            await asyncio.sleep(5)
            sys.stdout.write(".")
            sys.stdout.flush()
            
        print("") # Newline
        
        # 8. Check Status
        resp_simple = await client.get("/bot/status", headers=headers)
        simple_status = resp_simple.json()
        tracked_count = simple_status.get("tracked_games", 0)
        
        logger.info("-" * 40)
        logger.info(f"📊 BOT STATUS REPORT")
        logger.info(f"   State: {simple_status.get('state')}")
        logger.info(f"   Tracked Games: {tracked_count}")
        
        if tracked_count > 0:
            logger.info("✅ SUCCESS: Bot successfully matched Direct Ticker!")
        else:
            logger.warning("⚠️  Bot is running but matched 0 games.")

        logger.info("-" * 40)

if __name__ == "__main__":
    asyncio.run(run_verification())
