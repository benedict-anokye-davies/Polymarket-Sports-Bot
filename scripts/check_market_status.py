
import asyncio
import sys
import os
sys.path.append("/app")

import logging
from src.services.kalshi_client import KalshiClient
from src.db.database import async_session_factory
from src.db.crud.account import AccountCRUD
import json

logging.basicConfig(level=logging.INFO)

async def main():
    target_ticker = "KXMVESPORTSMULTIGAMEEXTENDED-S2026B330D2DCB50-893DD71BDDC"
    print(f"--- Checking Status for {target_ticker} ---")
    
    async with async_session_factory() as db:
        from src.db.crud.user import UserCRUD
        user = await UserCRUD.get_by_email(db, "e2e@test.com")
        if not user:
            print("User not found")
            return
            
        creds = await AccountCRUD.get_decrypted_credentials(db, user.id)
        if not creds:
            print("Creds not found")
            return

        client = KalshiClient(
            api_key=creds["api_key"],
            private_key_pem=creds.get("private_key") or creds.get("api_secret")
        )
        
        try:
            mkt = await client.get_market(target_ticker)
            
            # Print Key Details
            print(f"Ticker: {mkt.get('ticker')}")
            print(f"Status: {mkt.get('status')}")
            print(f"Result: {mkt.get('result')}")
            print(f"Settlement: {mkt.get('settlement_timer')}")
            print(f"Expiration: {mkt.get('expiration_time')}")
            print(f"Yes Price: {mkt.get('yes_price')}")
            print(f"Volume: {mkt.get('volume')}")
            
            print("\nFull Details:")
            print(json.dumps(mkt, indent=2, default=str))
            
        except Exception as e:
            print(f"Error: {e}")
        finally:
            await client.close()

if __name__ == "__main__":
    asyncio.run(main())
