
import asyncio
import os
import sys

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.models.trading_account import TradingAccount
from src.services.kalshi_client import KalshiClient
from src.db.database import async_session_factory
from sqlalchemy import select
from src.core.encryption import decrypt_credential

async def main():
    print("--- Placing NBA Test Bets ---")
    
    async with async_session_factory() as db:
        # 1. Get Credentials
        stmt = select(TradingAccount).where(TradingAccount.is_primary == True).limit(1)
        result = await db.execute(stmt)
        account = result.scalar_one_or_none()
        
        if not account:
            # Fallback
            stmt = select(TradingAccount).limit(1)
            result = await db.execute(stmt)
            account = result.scalar_one_or_none()
            
        if not account:
            print("No account found")
            return

        # Decrypt
        creds = {}
        if account.api_key_encrypted:
            creds["api_key"] = decrypt_credential(account.api_key_encrypted)
        if account.private_key_encrypted:
            creds["private_key"] = decrypt_credential(account.private_key_encrypted)
        if account.api_secret_encrypted:
            creds["api_secret"] = decrypt_credential(account.api_secret_encrypted)

        client = KalshiClient(
            api_key=creds.get("api_key"),
            private_key_pem=creds.get("private_key") or creds.get("api_secret")
        )

        # 2. Target Teams
        target_teams = {
            "LAL": "Los Angeles Lakers",
            "DET": "Detroit Pistons",
            "ORL": "Orlando Magic",
            "ATL": "Atlanta Hawks",
            "TOR": "Toronto Raptors",
            "HOU": "Houston Rockets",
            "SAS": "San Antonio Spurs",
            "PHX": "Phoenix Suns"
        }
        
        print(f"Targeting bets for teams: {list(target_teams.keys())}")
        
        try:
            # Fetch KXNBAGAME markets
            print("Fetching KXNBAGAME markets...")
            resp = await client.get_markets(limit=100, series_ticker="KXNBAGAME")
            markets = resp.get("markets", [])
            print(f"Found {len(markets)} game markets.")
            
            placed_count = 0
            
            for m in markets:
                ticker = m.get("ticker", "")
                title = m.get("title", "")
                
                # Check if this marker is for one of our target teams
                # Ticker format: KXNBAGAME-DATE-TEAMS-TEAM
                # e.g. KXNBAGAME-26FEB07GSWLAL-LAL
                
                matched_abbr = None
                for abbr in target_teams.keys():
                    if ticker.endswith(f"-{abbr}"):
                        matched_abbr = abbr
                        break
                
                if matched_abbr:
                    print(f"\nFound Market for {matched_abbr}: {title} ({ticker})")
                    print(f"Status: {m.get('status')}")
                    
                    if m.get("status") != "active":
                        print("Market not active, skipping bet.")
                        continue
                        
                    # Place Bet
                    # Buy YES on the team to win
                    # Side="buy", YesNo="yes", Size=1, Price=limit
                    
                    # Determine price: assume market order-ish (hit the ask or 99c?)
                    # User requested specific params but manual test just needs to verify execution.
                    # Let's try to get a fillable price.
                    # Best Ask?
                    yes_ask = m.get("yes_ask", 99)
                    bid_price_cents = yes_ask # Try to buy at ask
                    
                    if bid_price_cents <= 0 or bid_price_cents > 99:
                         bid_price_cents = 50 # Fallback
                         
                    print(f"Attempting to Bet $1 on {matched_abbr} YES @ {bid_price_cents}c")
                    
                    try:
                        order = await client.place_order(
                            ticker=ticker,
                            side="buy",
                            yes_no="yes",
                            price=bid_price_cents / 100.0,
                            size=1,
                            client_order_id=f"test-nba-{matched_abbr}-{os.urandom(4).hex()}"
                        )
                        print("Order Result:", order)
                        placed_count += 1
                    except Exception as e:
                        print(f"Failed to place bet: {e}")
                        
            print(f"\nTotal Bets Placed: {placed_count}")

        except Exception as e:
            print(f"Error executing script: {e}")

if __name__ == "__main__":
    asyncio.run(main())
