
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
    print("--- Searching for NBA Game Markets ---")
    
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

        # 2. Iterate through markets to find NBA Games
        # Expanded search with Full Names and Abbreviations
        team_configs = [
            {"short": "Lakers", "full": "Los Angeles Lakers", "abbr": "LAL"},
            {"short": "Pistons", "full": "Detroit Pistons", "abbr": "DET"},
            {"short": "Magic", "full": "Orlando Magic", "abbr": "ORL"},
            {"short": "Hawks", "full": "Atlanta Hawks", "abbr": "ATL"},
            {"short": "Raptors", "full": "Toronto Raptors", "abbr": "TOR"},
            {"short": "Rockets", "full": "Houston Rockets", "abbr": "HOU"},
            {"short": "Spurs", "full": "San Antonio Spurs", "abbr": "SAS"},
            {"short": "Suns", "full": "Phoenix Suns", "abbr": "PHX"},
        ]
        
        print(f"Looking for teams (Full/Abbr/Short)...")
        
        cursor = None
        found_games = []
        total_fetched = 0
        
        # 2. Query specific series directly
        series_to_try = ["KXNBAGAME", "KXNBASPREAD", "KXNBATOTAL", "KXNBA"]
        
        for series in series_to_try:
            print(f"\n--- Querying Series: {series} ---")
            try:
                # We don't filter by status to see everything (scheduled, active, etc)
                resp = await client.get_markets(limit=100, series_ticker=series)
                markets = resp.get("markets", [])
                
                print(f"Found {len(markets)} markets for {series}")
                
                for m in markets[:20]:
                     print(f"Ticker: {m['ticker']}")
                     print(f"Title:  {m['title']}")
                     print(f"Status: {m.get('status')}")
                     print(f"Open:   {m.get('open_date')}")
                     print("-" * 30)
                     
            except Exception as e:
                print(f"Error querying {series}: {e}")
            
            if not cursor:
                break
                
        print(f"\n\nTotal Markets Scanned: {total_fetched}")
        print(f"Found {len(found_games)} potential matches.")
        
        print("\n--- SAMPLE MATCHES ---")
        for g in found_games[:20]:
            print(f"Ticker: {g['ticker']}")
            print(f"Title:  {g['title']}")
            print(f"Yes Ask: {g.get('yes_ask')}")
            print("-" * 30)

if __name__ == "__main__":
    asyncio.run(main())
