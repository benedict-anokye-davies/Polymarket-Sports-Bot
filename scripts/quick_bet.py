#!/usr/bin/env python3
"""Quick bet placer - uses VPS database for credentials."""
import asyncio
import sys
import os
sys.path.insert(0, '/app')

async def place_bets():
    from src.db.database import async_session_factory
    from src.models.trading_account import TradingAccount  
    from src.services.kalshi_client import KalshiClient
    from sqlalchemy import select
    from src.core.encryption import decrypt_credential
    
    print("=== QUICK NBA BET PLACER ===")
    
    print(f"Got credentials for account")
        
    # Check for direct env var overrides
    if os.environ.get("KALSHI_API_KEY") and os.environ.get("KALSHI_PRIVATE_KEY"):
        print("Using credentials from Environment Variables")
        api_key = os.environ.get("KALSHI_API_KEY")
        private_key = os.environ.get("KALSHI_PRIVATE_KEY")
    else:
        async with async_session_factory() as db:
            result = await db.execute(select(TradingAccount).limit(1))
            account = result.scalar_one_or_none()
            
            if not account:
                print("No account!")
                return
                
            api_key = decrypt_credential(account.api_key_encrypted) if account.api_key_encrypted else None
            private_key = decrypt_credential(account.api_secret_encrypted) if account.api_secret_encrypted else None
            
    if not api_key or not private_key:
        print("Missing credentials!")
        return
        
        client = KalshiClient(api_key=api_key, private_key_pem=private_key)
        
        # Get live NBA markets
        print("Fetching live NBA markets...")
        resp = await client.get_markets(limit=200, series_ticker="KXNBAGAME")
        markets = resp.get("markets", [])
        
        active = [m for m in markets if m.get("status") == "active"]
        print(f"Found {len(active)} active games")
        
        # Target teams
        teams = ["BOS", "DET", "MIN", "LAC", "POR"]
        
        for m in active:
            ticker = m.get("ticker", "")
            for team in teams:
                if ticker.endswith(f"-{team}"):
                    title = m.get("title", "")
                    yes_ask = m.get("yes_ask", 0)
                    print(f"\n{team}: {title}")
                    print(f"  Ticker: {ticker}, Ask: {yes_ask}c")
                    
                    if yes_ask > 0 and yes_ask < 99:
                        print(f"  PLACING $1 BET...")
                        try:
                            order = await client.place_order(
                                ticker=ticker,
                                side="buy",
                                yes_no="yes", 
                                price=yes_ask / 100.0,
                                size=1,
                                client_order_id=f"demo-{team}-{os.urandom(4).hex()}"
                            )
                            print(f"  ORDER: {order}")
                        except Exception as e:
                            print(f"  ERROR: {e}")
                    break
        
        await client.close()
        print("\nDone!")

if __name__ == "__main__":
    asyncio.run(place_bets())
