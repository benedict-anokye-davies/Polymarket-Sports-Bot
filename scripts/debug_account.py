import asyncio
import os
import sys
import logging
import json

# Add app to path
sys.path.insert(0, '/app')
from src.services.kalshi_client import KalshiClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DebugAccount")

async def main():
    api_key = "813faefe-becc-4647-807a-295dcf69fcad"
    key_file = "/app/kalshi.key"
    with open(key_file, "r") as f:
        key_pem = f.read()

    client = KalshiClient(api_key=api_key, private_key_pem=key_pem)
    
    try:
        logger.info("--- BALANCE ---")
        bal = await client._authenticated_request("GET", "/portfolio/balance")
        print(json.dumps(bal, indent=2))

        logger.info("--- POSITIONS ---")
        pos = await client._authenticated_request("GET", "/portfolio/positions")
        print(json.dumps(pos, indent=2))

        logger.info("--- ORDERS (No Status) ---")
        orders_raw = await client._authenticated_request("GET", "/portfolio/orders")
        print(f"Count: {len(orders_raw.get('orders', []))}")
        if orders_raw.get("orders"):
            print(json.dumps(orders_raw["orders"][:2], indent=2))

        logger.info("--- ORDERS (Status: resting) ---")
        orders_resting = await client._authenticated_request("GET", "/portfolio/orders?status=resting")
        print(f"Count: {len(orders_resting.get('orders', []))}")
        if orders_resting.get("orders"):
            print(json.dumps(orders_resting["orders"][:2], indent=2))

    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(main())
