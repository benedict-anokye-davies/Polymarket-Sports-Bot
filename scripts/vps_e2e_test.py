
import asyncio
import os
import sys
import httpx
from datetime import datetime

# Set up logging
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VPS_TEST")

BASE_URL = "http://localhost:8000/api/v1"

async def run_test():
    logger.info("Starting VPS End-to-End Test")
    
    # Check if configured
    kalshi_key = os.environ.get("KALSHI_API_KEY")
    kalshi_secret = os.environ.get("KALSHI_API_SECRET")
    
    if not kalshi_key or not kalshi_secret:
        logger.warning("⚠️  KALSHI_API_KEY or KALSHI_API_SECRET not found in environment.")
        logger.warning("⚠️  Skipping Onboarding and Bot Start tests.")
        logger.warning("⚠️  Please add KALSHI_API_KEY and KALSHI_API_SECRET to .env file on VPS to fully test.")
        should_skip_trading = True
    else:
        should_skip_trading = False

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        # 1. Health Check
        try:
            resp = await client.get("/health")
            logger.info(f"✅ Health Check: {resp.status_code} - {resp.json()}")
        except Exception as e:
            logger.error(f"❌ Cannot connect to API: {e}")
            return

        # 2. Register/Login Test User
        email = f"test_vps_{int(datetime.now().timestamp())}@example.com"
        password = "TestPassword123!"
        
        logger.info(f"Registering user: {email}")
        resp = await client.post("/auth/register", json={
            "email": email,
            "password": password,
            "full_name": "VPS Test User"
        })
        
        if resp.status_code != 201:
            logger.error(f"❌ Registration failed: {resp.text}")
            return
            
        logger.info("Login...")
        resp = await client.post("/auth/token", data={
            "username": email,
            "password": password
        })
        
        if resp.status_code != 200:
            logger.error(f"❌ Login failed: {resp.text}")
            return
            
        token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        logger.info("✅ Logged in successfully.")

        if should_skip_trading:
            logger.info("🏁 Test finished (Partial Success). Bot is reachable and DB is working.")
            return

        # 3. Onboard (Save Credentials)
        logger.info("Saving Kalshi credentials...")
        resp = await client.post("/auth/onboard", headers=headers, json={
            "platform": "kalshi",
            "api_key": kalshi_key,
            "api_secret": kalshi_secret,
            "environment": "production"
        })
        
        if resp.status_code not in [200, 201]:
             logger.error(f"❌ Onboarding failed: {resp.text}")
             return
             
        logger.info("✅ Credentials saved.")

        # 4. Start Bot
        logger.info("Starting Bot...")
        resp = await client.post("/bot/start", headers=headers)
        if resp.status_code != 200:
             # It might say "already running"
             if "already running" in resp.text:
                 logger.info("ℹ️  Bot already running.")
             else:
                 logger.error(f"❌ Bot start failed: {resp.text}")
        else:
             logger.info(f"✅ Bot start response: {resp.json()}")

        # 5. Check Status loop
        logger.info("Checking status for 30 seconds...")
        for i in range(6):
            await asyncio.sleep(5)
            resp = await client.get("/bot/status", headers=headers)
            status_data = resp.json()
            state = status_data.get("state")
            tracked = status_data.get("tracked_games", 0)
            logger.info(f"Status: {state} | Tracked Games: {tracked}")
            
            if tracked > 0:
                logger.info("✅ SUCCESS: Bot is tracking games!")
                break
        
        # 6. Stop Bot (cleanup)
        logger.info("Stopping Bot...")
        await client.post("/bot/stop", headers=headers)

if __name__ == "__main__":
    asyncio.run(run_test())
