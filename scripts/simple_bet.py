import asyncio
import os
import sys
sys.path.insert(0, '/app')

async def place_bets():
    from src.services.kalshi_client import KalshiClient
    
    print("=== SIMPLE NBA BET PLACER ===")
    
    key_file = "/app/kalshi.key"
    # User provided API key
    api_key = "813faefe-becc-4647-807a-295dcf69fcad" 
    
    if not os.path.exists(key_file):
        print(f"CRITICAL: Key file {key_file} not found!")
        try:
            print(f"Files in /app: {os.listdir('/app')}")
        except:
            pass
        return

    print(f"Reading private key from {key_file}")
    with open(key_file, "r") as f:
        private_key = f.read()

    print("Initializing Kalshi Client...")
    try:
        client = KalshiClient(api_key=api_key, private_key_pem=private_key)
    except Exception as e:
        print(f"Failed to init client: {e}")
        return

    # Get live NBA markets
    print("Fetching live NBA markets...")
    try:
        resp = await client.get_markets(limit=200, series_ticker="KXNBAGAME")
    except Exception as e:
         print(f"Failed to get markets: {e}")
         await client.close()
         return

    markets = resp.get("markets", [])
    
    active = [m for m in markets if m.get("status") == "active"]
    print(f"Found {len(active)} active games")
    
    # Target teams from user request/context
    teams = ["BOS", "DET", "MIN", "LAC", "POR", "MEM", "SAC"]
    
    bets_placed = 0
    
    for m in active:
        ticker = m.get("ticker", "")
        for team in teams:
            if ticker.endswith(f"-{team}"):
                title = m.get("title", "")
                yes_ask = m.get("yes_ask", 0)
                print(f"\n{team}: {title}")
                print(f"  Ticker: {ticker}, Ask: {yes_ask}c")
                
                if yes_ask > 0 and yes_ask < 99:
                    print(f"  PLACING $1 BET on {ticker}...")
                    try:
                        # Place order
                        order = await client.place_order(
                            ticker=ticker,
                            side="buy",
                            yes_no="yes", 
                            price=yes_ask, # 1-99
                            count=1, # Number of contracts
                            client_order_id=f"demo-{team}-{os.urandom(4).hex()}"
                        )
                        print(f"  ORDER RESULT: {order}")
                        bets_placed += 1
                    except Exception as e:
                        print(f"  ERROR placing bet: {e}")
                else:
                    print(f"  Skipping (price {yes_ask} not in 1-99)")
                break
    
    print(f"\nTotal bets placed: {bets_placed}")
    await client.close()
    print("Done!")

if __name__ == "__main__":
    asyncio.run(place_bets())
