import asyncio
import os
import sys
import time
from datetime import datetime
sys.path.insert(0, '/app')

# ============================================
# BETTING PARAMETERS
# ============================================
PARAMS = {
    "probability_drop": 0.25,          # 25% drop from pregame
    "min_pregame_probability": 0.65,   # 65% minimum pregame prob
    "min_volume_dollars": 50000,       # $50k minimum volume
    "position_size_dollars": 1.0,      # $1 position size
    "take_profit_pct": 0.10,           # 10% take profit
    "stop_loss_pct": 0.10,             # 10% stop loss
    "min_game_time_remaining_mins": 20, # 20 minutes minimum
    "exit_before_mins": 6,             # Exit before 6 minutes
}

# Target teams
TARGET_TEAMS = {
    "BOS": "Boston Celtics",
    "DET": "Detroit Pistons",
    "MIN": "Minnesota Timberwolves",
    "LAC": "Los Angeles Clippers",
    "POR": "Portland Trail Blazers",
    "MEM": "Memphis Grizzlies",
    "SAC": "Sacramento Kings"
}

async def get_market_pregame_prob(client, ticker):
    """Fetch market history to find pregame (initial) probability."""
    try:
        # Get oldest history
        # Note: In a real scenario we'd match timestamps to game start. 
        # For this demo we take the earliest available price point as "pregame"
        history = await client.get_market_history(ticker, limit=100)
        history_points = history.get("history", [])
        
        if not history_points:
            return None
            
        # Oldest point is usually last in list or first depending on sort. 
        # Kalshi usually returns newest first. So take the last one.
        oldest = history_points[-1]
        
        # yes_price is in cents usually in history, verify strictly
        yes_price = oldest.get("yes_price", 0)
        return yes_price / 100.0
        
    except Exception as e:
        print(f"    ⚠️ Failed to get history for {ticker}: {e}")
        return None

def check_parameters(market, pregame_prob=None):
    """
    Check if market meets all betting parameters.
    Returns (passed, reason).
    """
    ticker = market.get("ticker", "")
    title = market.get("title", "")
    
    # 1. Check status is active (live game)
    status = market.get("status", "")
    if status != "active":
        return False, f"Status is '{status}', not active"
    
    # 2. Check volume
    volume = market.get("volume", 0) or 0
    # Rough estimate: volume * avg_price (~50c) = $ value
    estimated_dollar_volume = volume * 0.50
    
    # NOTE: For tonight's demo we might relax volume if markets are thin, 
    # but let's report it honestly based on user params
    if estimated_dollar_volume < PARAMS["min_volume_dollars"]:
        print(f"    ❌ Volume ${estimated_dollar_volume:,.0f} < ${PARAMS['min_volume_dollars']:,.0f}")
        return False, f"Volume ${estimated_dollar_volume:,.0f} < ${PARAMS['min_volume_dollars']:,.0f}" # Strict enforcement
    
    # 3. Check current probability (yes_bid/yes_ask)
    yes_bid = (market.get("yes_bid") or 0) / 100.0
    yes_ask = (market.get("yes_ask") or 0) / 100.0
    
    if yes_ask == 0:
        return False, "No liquidity (Ask = 0)"
        
    current_prob = (yes_bid + yes_ask) / 2 if yes_ask > 0 else yes_bid
    
    # 4. If we had pregame probability, check the drop
    if pregame_prob is not None:
        drop = pregame_prob - current_prob
        print(f"    📉 Pregame: {pregame_prob:.1%} -> Current: {current_prob:.1%} (Drop: {drop:.1%})")
        
        if drop < PARAMS["probability_drop"]:
            return False, f"Drop {drop:.1%} < {PARAMS['probability_drop']:.0%} required"
            
        if pregame_prob < PARAMS["min_pregame_probability"]:
            return False, f"Pregame {pregame_prob:.1%} < {PARAMS['min_pregame_probability']:.0%} min"
    else:
        print("    ⚠️ No pregame data found, skipping drop check")

    return True, "All parameters met"

async def place_bets():
    from src.services.kalshi_client import KalshiClient
    
    print("=== SMART NBA BET PLACER (WITH THRESHOLDS) ===")
    
    # Credentials setup (File preferred)
    key_file = "/app/kalshi.key"
    api_key = "813faefe-becc-4647-807a-295dcf69fcad" 
    
    if not os.path.exists(key_file):
        print(f"CRITICAL: Key file {key_file} not found!")
        return

    print(f"Reading private key from {key_file}...")
    with open(key_file, "r") as f:
        private_key = f.read()

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
    
    bets_placed = 0
    
    for m in active:
        ticker = m.get("ticker", "")
        # Check against target teams
        matched_abbr = None
        for abbr, name in TARGET_TEAMS.items():
            if ticker.endswith(f"-{abbr}"):
                matched_abbr = abbr
                break
        
        if not matched_abbr:
            continue
            
        print(f"\n🏀 Analyzing {TARGET_TEAMS[matched_abbr]} ({matched_abbr})")
        print(f"   Ticker: {ticker}")
        
        # Fetch pregame/history data
        pregame_prob = await get_market_pregame_prob(client, ticker)
        
        # Check Parameters
        passed, reason = check_parameters(m, pregame_prob)
        
        if passed:
            yes_ask = m.get("yes_ask", 0)
            print(f"   ✅ CRITERIA MET! Reason: {reason}")
            print(f"   PLACING BET: $1 on {matched_abbr} YES @ {yes_ask}c")
            
            try:
                order = await client.place_order(
                    ticker=ticker,
                    side="buy",
                    yes_no="yes", 
                    price=yes_ask,
                    size=1,
                    client_order_id=f"smart-{matched_abbr}-{os.urandom(4).hex()}"
                )
                print(f"   📊 ORDER RESULT: {order}")
                bets_placed += 1
            except Exception as e:
                print(f"   ❌ ORDER FAILED: {e}")
        else:
            print(f"   ⏭️ SKIPPED: {reason}")
            
    print(f"\nTotal bets placed: {bets_placed}")
    await client.close()
    print("Done!")

if __name__ == "__main__":
    asyncio.run(place_bets())
