import asyncio
import sys
import logging
import httpx
import json
import uuid
from datetime import datetime, timedelta, timezone

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("VERIFY_BET")

BASE_URL = "http://localhost:8000/api/v1"
KALSHI_API_BASE = "https://api.elections.kalshi.com/trade-api/v2"

async def place_bet():
    logger.info("🚀 Starting Bet Execution Test (Real Money on Kalshi)...")
    
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
            
        # 3. Test Wallet Connection
        logger.info("3️⃣  Verifying Wallet Connection & Balance...")
        resp = await client.post("/onboarding/wallet/test", headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            balance = float(data.get('balance_usdc', 0))
            logger.info(f"✅ Wallet Verified! Balance: ${balance}")
            if balance < 1.0:
                logger.error("❌ Insufficient funds to place a bet (need at least $1)")
                return
        else:
            logger.error(f"❌ Wallet Test Error: {resp.text}")
            return

        await client.post("/onboarding/complete", headers=headers)

        # 4. Find valid market (with pagination)
        logger.info("4️⃣  Finding a cheap Single Game market to bet on...")
        valid_markets = []
        cursor = None
        pages = 0
        
        async with httpx.AsyncClient() as k_client:
            while pages < 20 and not valid_markets:
                params = {"limit": 100, "status": "open", "category": "Sports"}
                if cursor:
                    params["cursor"] = cursor
                    
                try:
                    resp = await k_client.get(f"{KALSHI_API_BASE}/markets", params=params)
                    data = resp.json()
                    markets = data.get("markets", [])
                    cursor = data.get("cursor")
                    
                    logger.info(f"   Page {pages+1}: Fetched {len(markets)} markets...")
                    
                    for m in markets:
                        ticker = m.get("ticker", "")
                        title = m.get("title", "")
                        
                        # Exclude Parlays/Combos (KXMV prefix or commas in title)
                        if ticker.startswith("KXMV") or "MULTIGAME" in ticker or "," in title:
                            # logger.debug(f"      Skipping Combo: {title[:30]}...") 
                            continue
                            
                        ask = m.get("yes_ask", 0)
                        if ask > 0 and ask <= 98: 
                            valid_markets.append(m)
                            
                    if not cursor:
                        break
                    pages += 1
                    
                except Exception as e:
                    logger.error(f"   Failed to fetch markets: {e}")
                    break
        
        target_market = None
        if valid_markets:
            valid_markets.sort(key=lambda m: m.get("volume", 0), reverse=True)
            target_market = valid_markets[0]
            logger.info(f"   Selected Single Market: {target_market.get('title')} ({target_market.get('ticker')})")
        else:
            logger.error("❌ No Single-Game markets found after scanning 10 pages.")
            return

        raw_price = target_market.get("yes_ask")
        logger.info(f"   Raw YES Ask Price (cents): {raw_price}")
        
        # Normalize to dollars for Bot API
        price = float(raw_price) / 100.0 if raw_price > 1 else raw_price
        
        # Ensure within bounds
        if price > 0.99: price = 0.99
        if price < 0.01: price = 0.01
        
        logger.info(f"   Normalized Price: {price}")
        
        # 5. Place Bet
        logger.info("5️⃣  Placing Manual Order (Buy YES)...")
        
        order_payload = {
            "platform": "kalshi",
            "ticker": target_market.get("ticker"),
            "side": "buy",
            "outcome": "yes",
            "price": price, # Limit price at ask
            "size": 1 # 1 contract (start small)
        }
        
        resp = await client.post("/bot/order", headers=headers, json=order_payload)
        
        if resp.status_code == 200:
            order_data = resp.json()
            if order_data.get('status') == 'failed':
                logger.error(f"❌ Order Failed: {order_data.get('message')}")
            else:
                logger.info("✅ ORDER PLACED SUCCESSFULLY!")
                logger.info(f"   Order ID: {order_data.get('order_id')}")
                logger.info(f"   Status: {order_data.get('status')}")
                logger.info(f"   Filled Size: {order_data.get('filled_size')}")
        else:
            logger.error(f"❌ API Error: {resp.text}")

if __name__ == "__main__":
    asyncio.run(place_bet())
