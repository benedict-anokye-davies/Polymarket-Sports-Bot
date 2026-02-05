
import asyncio
import sys
import os
sys.path.append("/app")

import logging
from src.services.kalshi_client import KalshiClient
from src.db.database import async_session_factory
from src.db.crud.account import AccountCRUD

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    print("--- Checking All Kalshi Positions ---")
    async with async_session_factory() as db:
        # 1. Get Credentials (assumes single user e2e@test.com logic or similar)
        # We need to find the user ID first.
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
            # 2. Authenticate (handled internally)
            # await client.authenticate()
            print("Client initialized.")

            # 3. Get Portfolio Balance
            balance = await client.get_balance()
            print(f"Kalshi Balance: {balance}")

            # 4. Get All Positions
            data = await client.get_positions()
            
            # Handle dictionary response
            if isinstance(data, dict):
                positions = data.get("market_positions", []) # Renamed market_positions to positions
                event_positions = data.get("event_positions", [])
            else:
                positions = data # Renamed market_positions to positions
                event_positions = []

            print(f"\nFound {len(positions)} Open Market Positions:")
            if positions:
                import json
                print(json.dumps(positions, indent=2))
                
            for p in positions:
                ticker = p.get('ticker')
                count = p.get('position')
                cost = p.get('market_exposure') # This is cost basis usually
                print(f" - {ticker}: {count} contracts (Cost: {cost})")

            print(f"\nFound {len(event_positions)} Open Event Positions:")
            if event_positions:
                import json
                print(json.dumps(event_positions, indent=2))
            for p in event_positions:
                print(f" - Event {p.get('event_ticker')}: Exposure {p.get('exposure')}, Value {p.get('position_value')}")

            # Check orders too
            orders_data = await client.get_orders()
            # Handle dictionary response for orders if needed
            if isinstance(orders_data, dict):
                 orders = orders_data.get("orders", [])
            else:
                 orders = orders_data
            
            print(f"\nFound {len(orders)} Orders:")
            print(f"Type of orders: {type(orders)}")
            print(f"Raw orders: {orders}")
            sys.stdout.flush()
            
            print("--- Starting Order Loop ---")
            for i, o in enumerate(orders):
                print(f"Loop iteration {i}")
                try:
                    print(f" Order {i+1}:")
                    print(f"   ID: {o.get('order_id')}")
                    print(f"   Ticker: {o.get('ticker')}")
                except Exception as e:
                    print(f"Error in loop {i}: {e}")
                sys.stdout.flush()
            print("--- End Order Loop ---")


        except Exception as e:
            print(f"Error checking Kalshi: {e}")
        finally:
            await client.close()

if __name__ == "__main__":
    asyncio.run(main())
