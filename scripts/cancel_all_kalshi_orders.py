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
        # 1. Fetch all orders (try with and without resting status)
        logger.info("🔍 Fetching all open orders...")
        resp = await client._authenticated_request("GET", "/portfolio/orders")
        orders = resp.get("orders", [])
        
        if not orders:
            logger.info("   No orders found at /portfolio/orders. Trying ?status=resting...")
            resp = await client._authenticated_request("GET", "/portfolio/orders?status=resting")
            orders = resp.get("orders", [])

        if not orders:
            logger.info("✨ Still no orders found. Nothing to cancel.")
            return

        logger.info(f"📋 Found {len(orders)} total orders in portfolio.")
        
        # 2. Cancel everything that's not already filled/canceled
        cancelled_count = 0
        for i, order in enumerate(orders):
            order_id = order.get("order_id")
            ticker = order.get("ticker")
            status = order.get("status", "unknown")
            
            # Log statuses for debugging
            if i < 5: logger.info(f"   Sample Order: {order_id} | Status: {status} | Ticker: {ticker}")

            if status not in ["filled", "executed", "canceled", "cancelled", "expired"]:
                try:
                    await client.cancel_order(order_id)
                    cancelled_count += 1
                    if cancelled_count % 10 == 0:
                        logger.info(f"   Progress: Cancelled {cancelled_count} orders...")
                except Exception as e:
                    logger.error(f"   FAILED to cancel {order_id}: {e}")
            
            # Small sleep to avoid rate limiting
            if i % 5 == 0: await asyncio.sleep(0.05)

        logger.info(f"✅ ORDER CLEANUP COMPLETE. Cancelled {cancelled_count} orders.")
        
        # 3. Verify final balance
        balance_data = await client.get_balance()
        available = balance_data.get("available_balance", 0)
        logger.info(f"💰 UPDATED BALANCE: ${available:.2f} available to trade.")

    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(main())
