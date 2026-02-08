import asyncio
import os
import sys
import logging

# Add app to path
sys.path.insert(0, '/app')
from src.services.kalshi_client import KalshiClient

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ClosePositions")

async def main():
    api_key = "813faefe-becc-4647-807a-295dcf69fcad"
    key_file = "/app/kalshi.key"
    with open(key_file, "r") as f:
        key_pem = f.read()

    client = KalshiClient(api_key=api_key, private_key_pem=key_pem)
    logger.info("✅ Connected to Kalshi")

    try:
        # 1. Fetch current positions
        logger.info("🔍 Fetching positions...")
        pos_data = await client._authenticated_request("GET", "/portfolio/positions")
        raw_pos = pos_data.get("market_positions") or pos_data.get("positions") or []
        
        positions = [p for p in raw_pos if abs(int(p.get("position", 0))) > 0]
        
        if not positions:
            logger.info("✨ No open positions to close.")
            return

        logger.info(f"📋 Found {len(positions)} positions to close.")
        
        # 2. Sell each position at market bid
        for i, pos in enumerate(positions):
            ticker = pos.get("ticker")
            count = abs(int(pos.get("position", 0)))
            
            # Get current bid
            m_resp = await client.get_market(ticker)
            market = m_resp.get("market", m_resp)
            bid = market.get("yes_bid", 0)
            
            if bid == 0:
                logger.warning(f"   [{i+1}] SKIP {ticker}: No bid (0 liquidity)")
                continue
            
            logger.info(f"   [{i+1}/{len(positions)}] Selling {count}x {ticker} @ {bid}c...")
            try:
                order = await client.place_order(
                    ticker=ticker,
                    side="sell",
                    yes_no="yes",
                    price=bid,
                    size=count,
                    client_order_id=f"close-all-{os.urandom(4).hex()}"
                )
                logger.info(f"      ✅ SOLD: {order.get('order', {}).get('order_id', 'OK')}")
            except Exception as e:
                logger.error(f"      ❌ FAILED: {e}")
            
            await asyncio.sleep(0.2)

        # 3. Verify final balance
        logger.info("💰 Checking final balance...")
        bal = await client.get_balance()
        logger.info(f"   Available: ${bal.get('available_balance', 0):.2f} | Total: ${bal.get('balance', 0):.2f}")
        logger.info("✅ POSITION CLOSE COMPLETE.")

    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(main())
