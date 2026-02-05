import asyncio
import sys
import logging
import httpx
import json
import os
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("CANCEL_ORDERS")

# Fix path to import src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_URL = "http://localhost:8000/api/v1"

async def cancel_orders():
    logger.info("🛑 Starting Order Cancellation...")
    
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        # Login
        timestamp = int(datetime.now().timestamp())
        email = f"verify_{timestamp}@example.com"
        username = f"verify_{timestamp}"
        password = "VerifyPassword123!"
        
        await client.post("/auth/register", json={"username": username, "email": email, "password": password})
        resp = await client.post("/auth/login", data={"username": email, "password": password})
        token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Connect Wallet
        kalshi_key = os.environ.get("KALSHI_API_KEY")
        kalshi_secret = os.environ.get("KALSHI_API_SECRET")
        await client.post("/onboarding/wallet/connect", headers=headers, json={
            "platform": "kalshi",
            "api_key": kalshi_key, 
            "api_secret": kalshi_secret, 
            "environment": "production"
        })

        # Get Open Orders via direct Kalshi Client usage (since API endpoint for getting orders might not be exposed)
        # Actually, let's use the KalshiClient directly to be safe and quick
        from src.services.kalshi_client import KalshiClient
        k_client = KalshiClient(kalshi_key, kalshi_secret)
        
        try:
            logger.info("   Fetching RESTING orders...")
            # KalshiClient.get_open_orders doesn't accept status param in my current wrapper if I recall
            # Let's check src/services/kalshi_client.py
            # It accepts ticker.
            # I'll use _authenticated_request directly here or modify client?
            # Accessing private method is risky.
            # I'll assume get_open_orders returns everything if no params.
            # Maybe I should try manually request.
            
            resp = await k_client._authenticated_request("GET", "/portfolio/orders?status=resting")
            orders = resp.get("orders", [])
            logger.info(f"   Found {len(orders)} RESTING orders.")
            
            for order in orders:
                oid = order.get("order_id")
                status = order.get("status")
                logger.info(f"   Order {oid}: Status={status}")
                
                if status in ["resting", "open", "pending"]:
                    logger.info(f"   Canceling Order: {oid} ({order.get('ticker')})")
                    try:
                        await k_client.cancel_order(oid)
                        logger.info("      Cancelled.")
                    except Exception as e:
                        logger.error(f"      Failed to cancel: {e}")
                else:
                    logger.info("      Skipping (not cancelable).")
                
        except Exception as e:
            logger.error(f"Error: {e}")
        finally:
            await k_client.close()

if __name__ == "__main__":
    asyncio.run(cancel_orders())
