
import asyncio
import os
import sys

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.config import settings
from src.core.encryption import decrypt_credential
from src.db.database import async_session_factory
from sqlalchemy import select
from src.models.trading_account import TradingAccount
from src.services.kalshi_client import KalshiClient

TEAMS = ["Lakers", "Pistons", "Magic", "Hawks", "Raptors", "Rockets", "Spurs", "Suns"]

async def main():
    print("--- Verifying Kalshi Betting Capability ---")
    
    async with async_session_factory() as db:
        # 1. Get Primary Credentials directly
        stmt = select(TradingAccount).where(TradingAccount.is_primary == True).limit(1)
        result = await db.execute(stmt)
        account = result.scalar_one_or_none()
        
        if not account:
            # Fallback to any account
            stmt = select(TradingAccount).limit(1)
            result = await db.execute(stmt)
            account = result.scalar_one_or_none()

        if not account:
            print("ERROR: No trading account found in DB.")
            return

        # Manual credential decryption
        from src.core.encryption import decrypt_credential
        
        creds = {}
        if account.api_key_encrypted:
            creds["api_key"] = decrypt_credential(account.api_key_encrypted)
        
        # Kalshi might use private_key OR api_secret depending on onboarding
        if account.private_key_encrypted:
            creds["private_key"] = decrypt_credential(account.private_key_encrypted)
        
        if account.api_secret_encrypted:
            creds["api_secret"] = decrypt_credential(account.api_secret_encrypted)
            
        print(f"Using Account: {account.account_name}")
        
        # 2. Init Client
        client = KalshiClient(
            api_key=creds.get("api_key"),
            private_key_pem=creds.get("private_key") or creds.get("api_secret")
        )
        
        # 3. Find Markets
        print(f"Searching for markets...")
        markets_resp = await client.get_markets(limit=200)
        markets = markets_resp.get("markets", markets_resp)
        print(f"Total markets fetched: {len(markets)}")
        
        # DEBUG: Print first 10 active markets to understand naming convention
        print("\n--- SAMPLE ACTIVE MARKETS (For Debugging) ---")
        active_sample = [m for m in markets if m.get("status") == "active"][:10]
        for m in active_sample:
            print(f"- [{m.get('ticker')}] {m.get('title')} (Ask: {m.get('yes_ask')})")
        print("---------------------------------------------\n")

        found_markets = []
        for market in markets:
            # Broad search: Active, Liquid, not expired
            if market.get("status") == "active" and market.get("yes_ask", 0) > 0:
                print(f"FOUND TARGET MARKET: {market['ticker']} - {market['title']}")
                found_markets.append(market)
                break
        
        if not found_markets:
            print("No liquid active markets found.")
            return

        # 4. Place ONE Test Bet
        target = found_markets[0]
        ticker = target["ticker"]
        print(f"\n--- PLACING TEST BET ---")
        print(f"Target: {ticker}")
        print("Size: $1.00")
        print("Side: YES")
        
        try:
            # Place order (Limit order at current ASK price to ensure fill, or slightly higher)
            # Fetch current book directly (bypass missing client method)
            print(f"Fetching orderbook for {ticker}...")
            book_data = await client._authenticated_request("GET", f"/markets/{ticker}/orderbook")
            yes_ask = book_data.get("orderbook", {}).get("yes", [])
            
            price = 50 # Default safe price (50c)
            if yes_ask:
                # Take the best ask price
                price = yes_ask[0][0]
                print(f"Current Ask Price: {price} cents")
            
            print(f"Placing 1 contract bet on {ticker} at {price} cents...")
            
            # AUTO-CONFIRM (No input() for VPS automation)
            resp = await client.place_order(
                ticker=ticker,
                side="buy", # Action: buy
                yes_no="yes", # Contract: yes
                price=price,
                size=1 # 1 contract
            )
            print("RESPONSE:", resp)
            print("\nSUCCESS: Bet placed successfully. API is working.")
            
        except Exception as e:
            print(f"\nERROR placing bet: {e}")

if __name__ == "__main__":
    asyncio.run(main())
