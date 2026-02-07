#!/usr/bin/env python
"""Cancel orders and sell positions for a specific ticker."""
import asyncio
import os
import sys
sys.path.insert(0, '/app')

async def close_lal_positions():
    from src.services.kalshi_client import KalshiClient
    
    TARGET_TICKER = "KXNBAGAME-26FEB07GSWLAL-LAL"
    
    print(f"=== CLOSING POSITIONS FOR {TARGET_TICKER} ===")
    
    # Credentials setup
    key_file = "/app/kalshi.key"
    api_key = "813faefe-becc-4647-807a-295dcf69fcad" 
    
    if not os.path.exists(key_file):
        print(f"CRITICAL: Key file {key_file} not found!")
        return

    with open(key_file, "r") as f:
        private_key = f.read()

    client = KalshiClient(api_key=api_key, private_key_pem=private_key)

    try:
        # 1. Cancel any open orders for this ticker
        print("\n1. Cancelling open orders...")
        orders_resp = await client.get_open_orders()
        orders = orders_resp.get("orders", [])
        
        for order in orders:
            if order.get("ticker") == TARGET_TICKER:
                order_id = order.get("order_id")
                print(f"   Cancelling order {order_id}...")
                try:
                    await client.cancel_order(order_id)
                    print("   ✅ Cancelled")
                except Exception as e:
                    print(f"   ❌ Failed: {e}")
        
        # 2. Get current positions
        print("\n2. Checking positions...")
        pos_resp = await client._authenticated_request("GET", "/portfolio/positions")
        positions = pos_resp.get("market_positions", [])
        
        for pos in positions:
            if pos.get("ticker") == TARGET_TICKER:
                count = abs(int(pos.get("position", 0)))
                if count == 0:
                    print(f"   No position in {TARGET_TICKER}")
                    continue
                    
                print(f"   Found {count} contracts in {TARGET_TICKER}")
                
                # Get current bid to sell at
                market_resp = await client.get_market(TARGET_TICKER)
                market = market_resp.get("market", market_resp)
                bid = market.get("yes_bid", 0)
                
                print(f"   Current bid: {bid}c")
                
                if bid == 0:
                    print("   ❌ Cannot sell - no bid available")
                    continue
                
                # Place sell order
                print(f"   Selling {count} contracts at {bid}c...")
                try:
                    order = await client.place_order(
                        ticker=TARGET_TICKER,
                        side="sell",
                        yes_no="yes",
                        price=bid,
                        size=count,
                        client_order_id=f"close-lal-{os.urandom(4).hex()}"
                    )
                    print(f"   ✅ Sell order placed: {order}")
                except Exception as e:
                    print(f"   ❌ Failed to sell: {e}")
                    
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await client.close()
    
    print("\nDone!")

if __name__ == "__main__":
    asyncio.run(close_lal_positions())
