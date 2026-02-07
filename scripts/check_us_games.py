
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone

# Add app to path
sys.path.insert(0, '/app')
from src.services.kalshi_client import KalshiClient

# CONFIG (Same as Prod)
CONFIG = {
    "timezone_offset_hours": -6,  # CST
}

def get_cst_now():
    offset = timezone(timedelta(hours=CONFIG["timezone_offset_hours"]))
    return datetime.now(offset)

def parse_ticker_date(ticker):
    try:
        parts = ticker.split("-")
        if len(parts) >= 2:
            date_part = parts[1][:7]
            dt = datetime.strptime(date_part, "%y%b%d")
            return dt.date()
    except:
        return None

async def main():
    api_key = "813faefe-becc-4647-807a-295dcf69fcad"
    key_file = "/app/kalshi.key"
    
    with open(key_file, "r") as f:
        pk = f.read()
    
    client = KalshiClient(api_key=api_key, private_key_pem=pk)
    
    print(f"\n🕒 Bot Time (CST): {get_cst_now().strftime('%Y-%m-%d %I:%M %p')}\n")
    
    # scan for NBA
    resp = await client.get_markets(series_ticker="KXNBAGAME", limit=200, status="open")
    markets = resp.get("markets", [])
    
    print(f"🔎 Found {len(markets)} open markets. Filtering for TODAY...")
    
    today = get_cst_now().date()
    found_today = 0
    
    for m in markets:
        ticker = m.get("ticker", "")
        game_date = parse_ticker_date(ticker)
        
        if not game_date: continue
        
        # Logic from Prod Bot
        status = "✅ TODAY (LIVE)"
        if game_date > today:
            status = "⏭️ FUTURE (TOMORROW+)"
        elif (today - game_date).days > 1:
            status = "❌ OLD"
            
        print(f"   {status}: {ticker}")
        if status.startswith("✅"):
            found_today += 1
            
    print(f"\n📊 Summary: {found_today} games found for TODAY ({today}).")
    await client.close()

if __name__ == "__main__":
    asyncio.run(main())
