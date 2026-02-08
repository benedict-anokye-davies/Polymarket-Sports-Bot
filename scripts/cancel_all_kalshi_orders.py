import asyncio
import os
import sys
import logging
from datetime import datetime

# Add app to path
sys.path.insert(0, '/app')
from src.services.kalshi_client import KalshiClient

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("CancelAllOrders")

async def main():
    api_key = "813faefe-becc-4647-807a-295dcf69fcad"
    key_file = "/app/kalshi.key"
    
    if not os.path.exists(key_file):
        logger.error(f"Private key file not found at {key_file}. Are you running inside the container?")
        return

    with open(key_file, "r") as f:
        private_key = f.read()

    client = KalshiClient(api_key=api_key, private_key_pem=private_key)
    logger.info("✅ Connected to Kalshi")

    try:
        # 1. Fetch all resting/pending orders
        logger.info("🔍 Fetching all open orders...")
        resp = await client._authenticated_request("GET", "/portfolio/orders")
        orders = resp.get("orders", [])
        
        # Filter for cancelable statuses
        to_cancel = [o for o in orders if o.get("status") in ["resting", "open", "pending"]]
        
        if not to_cancel:
            logger.info("✨ No open orders found to cancel.")
            return

        logger.info(f"🛑 Found {len(to_cancel)} cancelable orders. Starting cleanup...")
        
        # 2. Cancel them!
        for i, order in enumerate(to_cancel):
            order_id = order.get("order_id")
            ticker = order.get("ticker")
            try:
                await client.cancel_order(order_id)
                logger.info(f"   [{i+1}/{len(to_cancel)}] Cancelled: {order_id} ({ticker})")
            except Exception as e:
                logger.error(f"   [{i+1}/{len(to_cancel)}] FAILED to cancel {order_id}: {e}")
            
            # Small sleep to avoid rate limiting
            await asyncio.sleep(0.1)

        logger.info("✅ ORDER CLEANUP COMPLETE.")
        
        # 3. Verify final balance
        balance_data = await client.get_balance()
        available = balance_data.get("available_balance", 0)
        logger.info(f"💰 UPDATED BALANCE: ${available:.2f} available to trade.")

    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(main())
