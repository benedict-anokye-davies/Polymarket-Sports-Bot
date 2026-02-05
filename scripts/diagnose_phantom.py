
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
logger = logging.getLogger(__name__)

async def main():
    print("--- Checking All Kalshi Positions (Verbose Diagnosis) ---")
    sys.stdout.flush()
    async with async_session_factory() as db:
        from src.db.crud.user import UserCRUD
        user = await UserCRUD.get_by_email(db, "e2e@test.com")
        if not user:
            print("Error: User e2e@test.com not found")
            return

        creds = await AccountCRUD.get_decrypted_credentials(db, user.id)
        if not creds:
            print("Error: No credentials found")
            return

        client = KalshiClient(
            api_key=creds["api_key"],
            private_key_pem=creds.get("private_key") or creds.get("api_secret")
        )

        try:
            print("Client initialized.")
            balance = await client.get_balance()
            print(f"Kalshi Balance: {balance}")

            # Positions
            data = await client.get_positions()
            if isinstance(data, dict):
                positions = data.get("market_positions", [])
                event_positions = data.get("event_positions", [])
            else:
                positions = data
                event_positions = []

            print(f"DEBUG: Positions Raw Data type: {type(data)}")
            
            print(f"\nFound {len(positions)} Open Market Positions:")
            if positions:
                print(json.dumps(positions, indent=2, default=str))

            print(f"\nFound {len(event_positions)} Open Event Positions:")
            if event_positions:
                print(json.dumps(event_positions, indent=2, default=str))

            # Orders
            orders_data = await client.get_orders()
            print(f"DEBUG: Orders Raw Data type: {type(orders_data)}")
            
            if isinstance(orders_data, dict):
                orders = orders_data.get("orders", [])
            else:
                orders = orders_data
            
            print(f"\nFound {len(orders)} Orders:")
            sys.stdout.flush()
            
            print(f"DEBUG: Orders list type: {type(orders)}")
            if orders:
                try:
                    print(json.dumps(orders, indent=2, default=str))
                except Exception as e:
                    print(f"JSON Dump failed: {e}")
            
            print("--- Detailed Order Loop ---")
            for i, o in enumerate(orders):
                print(f"Order #{i+1}:")
                # Dump all keys
                for k, v in o.items():
                    print(f"  {k}: {v}")
                print("-" * 20)
                sys.stdout.flush()
            print("--- End Order Loop ---")

            # Check status of the executed ticker
            target_ticker = "KXMVESPORTSMULTIGAMEEXTENDED-S2026B330D2DCB50-893DD71BDDC"
            print(f"--- Checking Market Details for {target_ticker} ---")
            try:
                mkt = await client.get_market(target_ticker)
                print(json.dumps(mkt, indent=2, default=str))
            except Exception as e:
                print(f"Could not fetch market: {e}")

        except Exception as e:
            print(f"CRITICAL ERROR: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await client.close()

if __name__ == "__main__":
    asyncio.run(main())
