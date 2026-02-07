import asyncio
import os
import sys
sys.path.insert(0, '/app')

async def cancel_all_bets():
    from src.services.kalshi_client import KalshiClient
    
    print("=== CANCELLING ALL OPEN ORDERS ===")
    
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
        # Get open orders
        print("Fetching open orders...")
        orders_resp = await client.get_open_orders()
        orders = orders_resp.get("orders", [])
        
        print(f"Found {len(orders)} open orders")
        
        for order in orders:
            order_id = order.get("order_id")
            ticker = order.get("ticker")
            print(f"Cancelling order {order_id} ({ticker})...")
            try:
                await client.cancel_order(order_id)
                print("  ✅ Cancelled")
            except Exception as e:
                print(f"  ❌ Failed to cancel: {e}")
                
    except Exception as e:
        print(f"Error fetching orders: {e}")
    finally:
        await client.close()
    
    print("Done!")

if __name__ == "__main__":
    asyncio.run(cancel_all_bets())
