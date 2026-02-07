#!/usr/bin/env python
"""Diagnostic: Check market data for finished vs live games."""
import asyncio
import sys
sys.path.insert(0, '/app')

from src.services.kalshi_client import KalshiClient

async def main():
    key = open("/app/kalshi.key").read()
    c = KalshiClient(
        api_key="813faefe-becc-4647-807a-295dcf69fcad", 
        private_key_pem=key
    )
    
    # Compare finished game vs live game
    tickers = [
        "KXNBAGAME-26FEB07GSWLAL-LAL",  # GSW vs LAL - FINISHED
        "KXNBAGAME-26FEB07DALSAS-DAL",  # DAL vs SAS - LIVE NOW
    ]
    
    for ticker in tickers:
        print(f"\n{'='*60}")
        print(f"TICKER: {ticker}")
        print('='*60)
        try:
            resp = await c.get_market(ticker)
            m = resp.get("market", resp)
            
            # Print all fields that might indicate game status
            print(f"  status:        {m.get('status')}")
            print(f"  result:        {m.get('result')}")
            print(f"  close_time:    {m.get('close_time')}")
            print(f"  expiration_time: {m.get('expiration_time')}")
            print(f"  end_time:      {m.get('end_time')}")
            print(f"  settled:       {m.get('settled')}")
            print(f"  winning_outcome: {m.get('winning_outcome')}")
            print(f"  can_close_early: {m.get('can_close_early')}")
            print(f"  market_type:   {m.get('market_type')}")
            
            # Print all keys for investigation
            print(f"\n  ALL KEYS: {list(m.keys())}")
            
        except Exception as e:
            print(f"  ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(main())
