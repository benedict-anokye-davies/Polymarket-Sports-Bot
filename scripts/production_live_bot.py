
import asyncio
import os
import sys
import time
import logging
from datetime import datetime, timedelta, timezone

# Add app to path
sys.path.insert(0, '/app')

# PROD LOGGING SETUP
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("ProdBot")

# ============================================
# CONFIGURATION
# ============================================
CONFIG = {
    "timezone_offset_hours": -6,  # US Central Standard Time (CST)
    
    # Risk Parameters
    "min_volume_dollars": 50000,
    "min_liquidity_dollars": 100, # Minimum bid/ask size available
    "max_spread_cents": 5,        # Maximum bid-ask spread to avoid bad fills
    
    # Strategy Parameters
    "probability_drop_threshold": 0.25, # 25% drop
    "min_pregame_prob": 0.65,           # 65% start
    
    # Execution
    "position_size_dollars": 1.0,
    "dry_run": False,             # Set True to simulate only
    
    # Risk Management (Soft Limits)
    "stop_loss_pct": 0.20,        # 20% Stop Loss
    "take_profit_pct": 0.20,      # 20% Take Profit
}

TARGET_TEAMS = {
    "BOS": "Boston Celtics", "DET": "Detroit Pistons", "MIN": "Minnesota Timberwolves",
    "LAC": "Los Angeles Clippers", "POR": "Portland Trail Blazers", "MEM": "Memphis Grizzlies",
    "SAC": "Sacramento Kings", "NYK": "New York Knicks", "CLE": "Cleveland Cavaliers"
}

# ============================================
# UTILITIES
# ============================================

def get_cst_now():
    """Get current time in US Central."""
    offset = timezone(timedelta(hours=CONFIG["timezone_offset_hours"]))
    return datetime.now(offset)

def parse_ticker_date(ticker):
    """Extract date from ticker like KXNBAGAME-26FEB08..."""
    try:
        parts = ticker.split("-")
        if len(parts) >= 2:
            # 26FEB08 (YYMMMDD)
            date_part = parts[1][:7]
            # Parse
            dt = datetime.strptime(date_part, "%y%b%d")
            # Assign CST year/month/day to a date object
            return dt.date()
    except Exception as e:
        logger.error(f"Failed to parse date from {ticker}: {e}")
    return None

def calculate_implied_prob(market):
    """Calculate mid-market probability."""
    bid = market.get("yes_bid", 0)
    ask = market.get("yes_ask", 0)
    if ask == 0: return 0.0
    return ((bid + ask) / 2) / 100.0

# ============================================
# CORE LOGIC
# ============================================

class KalshiProductionBot:
    def __init__(self):
        self.api_key = "813faefe-becc-4647-807a-295dcf69fcad"
        self.key_file = "/app/kalshi.key"
        self.client = None
        
        logger.info("Initializing Production Bot v1.0")
        logger.info(f"Target Timezone: UTC{CONFIG['timezone_offset_hours']}")
        logger.info(f"Min Volume: ${CONFIG['min_volume_dollars']:,.2f}")
        logger.info(f"Min Drop: {CONFIG['probability_drop_threshold']:.1%}")

    async def connect(self):
        """Robust connection with file check."""
        from src.services.kalshi_client import KalshiClient
        
        if not os.path.exists(self.key_file):
            logger.critical(f"Key file missing at {self.key_file}")
            return False
            
        try:
            with open(self.key_file, "r") as f:
                pk = f.read()
            self.client = KalshiClient(api_key=self.api_key, private_key_pem=pk)
            # Test connection
            await self.client.get_balance()
            logger.info("✅ Connected to Kalshi API")
            return True
        except Exception as e:
            logger.critical(f"Connection failed: {e}")
            return False

    async def validate_market(self, market):
        """Detailed market validation pipeline."""
        reasons = []
        ticker = market.get("ticker", "")
        
        # 1. Date Check (US Time)
        game_date = parse_ticker_date(ticker)
        today = get_cst_now().date()
        
        if not game_date:
            reasons.append("Invalid ticker date format")
        elif game_date > today:
            reasons.append(f"Future Game (Game: {game_date}, Now: {today})")
        elif (today - game_date).days > 1:
            reasons.append(f"Old Game (Game: {game_date}, Now: {today})")

        # 2. Status Check
        if market.get("status") != "active":
            reasons.append(f"Status not active: {market.get('status')}")

        # 3. Liquidity/Spread Check
        bid = market.get("yes_bid", 0)
        ask = market.get("yes_ask", 0)
        spread = ask - bid
        
        if ask == 0 or ask > 99:
            reasons.append("No liquidity (Ask invalid)")
        elif spread > CONFIG["max_spread_cents"]:
            reasons.append(f"Spread too wide ({spread}c > {CONFIG['max_spread_cents']}c)")
            
        # 4. Volume Check
        # Estimate volume in dollars (contracts * avg price ~50c)
        vol_cnt = market.get("volume", 0)
        vol_usd = vol_cnt * 0.50
        if vol_usd < CONFIG["min_volume_dollars"]:
            reasons.append(f"Low Volume (${vol_usd:,.0f} < ${CONFIG['min_volume_dollars']:,.0f})")

        if reasons:
            return False, "; ".join(reasons)
        return True, "Market Valid"

    async def check_strategy(self, market):
        """Check the specific strategy logic (Drop from pregame)."""
        ticker = market.get("ticker")
        
        # Fetch history
        try:
            hist_resp = await self.client.get_market_history(ticker, limit=100)
            history = hist_resp.get("history", [])
        except Exception as e:
            return False, f"API Error fetching history: {e}"
            
        if not history:
            return False, "No historical data available (Safety Halt)"
            
        # Find pregame price (oldest point relative to game start?)
        # For this logic we assume oldest available point is the best proxy for 'pregame'
        # in a live context if we don't have our own DB.
        pregame_point = history[-1] # Oldest
        pregame_price = pregame_point.get("yes_price", 0) / 100.0
        
        current_prob = calculate_implied_prob(market)
        
        # CALCULATION
        drop = pregame_price - current_prob
        
        logger.info(f"   📊 Strategy Check: {ticker}")
        logger.info(f"      Pregame: {pregame_price:.1%}")
        logger.info(f"      Current: {current_prob:.1%}")
        logger.info(f"      Drop:    {drop:.1%}")
        
        if pregame_price < CONFIG["min_pregame_prob"]:
            return False, f"Pregame prob too low ({pregame_price:.1%} < {CONFIG['min_pregame_prob']:.0%})"
            
        if drop < CONFIG["probability_drop_threshold"]:
            return False, f"Drop insufficient ({drop:.1%} < {CONFIG['probability_drop_threshold']:.0%})"
            
        return True, "Strategy Triggered"

    async def run_cycle(self):
        """Main execution cycle."""
        logger.info(f"🕒 Cycle Start (CST: {get_cst_now()})")
        
        # Get Markets
        try:
            resp = await self.client.get_markets(series_ticker="KXNBAGAME", limit=200, status="open")
            markets = resp.get("markets", [])
        except Exception as e:
            logger.error(f"Failed to fetch markets: {e}")
            return

        logger.info(f"🔎 Found {len(markets)} active markets. Filtering...")
        
        for m in markets:
            ticker = m.get("ticker", "")
            
            # Team Filter
            matched_team = None
            for abbr in TARGET_TEAMS:
                if ticker.endswith(f"-{abbr}"):
                    matched_team = abbr
                    break
            
            # Skip if not a target team
            if not matched_team: 
                continue

            logger.info(f"--------------------------------------------------")
            logger.info(f"🏀 Analyzing {TARGET_TEAMS[matched_team]} ({ticker})")
            
            # 1. Validation (Market Health)
            is_valid, reason = await self.validate_market(m)
            if not is_valid:
                logger.info(f"   🚫 REJECTED (Validation): {reason}")
                continue
                
            # 2. Strategy Check (Logic)
            is_good_trade, strat_reason = await self.check_strategy(m)
            if not is_good_trade:
                logger.info(f"   ⏭️ SKIPPED (Strategy): {strat_reason}")
                continue
                
            # 3. Execution
            await self.execute_trade(m, matched_team)
            
        logger.info("🏁 Cycle Complete")

    async def execute_trade(self, market, team):
        """Execute the order."""
        ticker = market.get("ticker")
        price_cents = market.get("yes_ask")
        
        if CONFIG["dry_run"]:
            logger.info(f"   👀 [DRY RUN] Would Buy {ticker} @ {price_cents}c")
            return

        logger.info(f"   🚀 EXECUTING BUY: {ticker} @ {price_cents}c")
        try:
            # We use 'size' because we fixed that bug :)
            order = await self.client.place_order(
                ticker=ticker,
                side="buy",
                yes_no="yes",
                price=price_cents,
                size=1, # Fixed size for now
                client_order_id=f"prod-{team}-{os.urandom(4).hex()}"
            )
            # Log simplified result
            if "order_id" in str(order):
                logger.info(f"   ✅ ORDER SUCCEEDED: {order.get('order', {}).get('order_id')}")
            else:
                logger.info(f"   ⚠️ ORDER RESPONSE: {order}")
                
        except Exception as e:
            logger.error(f"   ❌ ORDER FAILED: {e}")

    async def monitor_positions(self):
        """Monitor open positions for Stop Loss / Take Profit."""
        try:
            # Fetch current positions
            portfolio = await self.client.get_positions()
            positions = portfolio.get("market_positions", [])
            
            for pos in positions:
                ticker = pos.get("ticker")
                entry_cost = pos.get("cost_basis", 0) / 100.0 # Convert to dollars if needed, checks API spec
                count = pos.get("position", 0)
                
                if count <= 0: continue
                
                # Get current market price
                market_resp = await self.client.get_market(ticker)
                market = market_resp.get("market", market_resp)
                
                # Sell price is the 'yes_bid' (best price we can sell into immediately)
                current_bid = market.get("yes_bid", 0)
                current_price = current_bid / 100.0
                
                # Calculate PnL %
                # Approx average price per contract
                avg_entry = (entry_cost / count) if count > 0 else 0
                if avg_entry == 0: continue
                
                pnl_pct = (current_price - avg_entry) / avg_entry
                
                logger.info(f"   Positions: {ticker} | Entry: {avg_entry:.2f} | Current: {current_price:.2f} | PnL: {pnl_pct:.1%}")
                
                # TAKE PROFIT
                if pnl_pct >= CONFIG.get("take_profit_pct", 0.10):
                    logger.info(f"   💰 TAKE PROFIT TRIGGERED: {ticker} (+{pnl_pct:.1%})")
                    await self.close_position(ticker, count, "take_profit")
                    
                # STOP LOSS
                elif pnl_pct <= -CONFIG.get("stop_loss_pct", 0.10):
                    logger.info(f"   🛑 STOP LOSS TRIGGERED: {ticker} ({pnl_pct:.1%})")
                    await self.close_position(ticker, count, "stop_loss")
                    
        except Exception as e:
            logger.error(f"Position monitor error: {e}")

    async def close_position(self, ticker, count, reason):
        """Execute a sell order to close position."""
        if CONFIG["dry_run"]:
            logger.info(f"   👀 [DRY RUN] Would Close {ticker}")
            return
            
        try:
            # Sell 'yes' position
            logger.info(f"   📉 CLOSING {ticker} ({reason})...")
            # We sell into the bid (market sell essentially)
            # Fetch market again to ensure fresh price or just place limitsell 1c
            # Kalshi limit orders: To dump immediately, sell at 1c? No, sell at bid.
            # Best practice: get top bid.
            m = await self.client.get_market(ticker)
            bid = m.get("market", m).get("yes_bid", 0)
            
            if bid == 0:
                logger.warning(f"   ⚠️ Cannot close {ticker}: No Liquidity (Bid 0)")
                return

            await self.client.place_order(
                ticker=ticker,
                side="sell",
                yes_no="yes",
                price=bid, # Sell into the bid
                size=count,
                client_order_id=f"close-{reason}-{os.urandom(4).hex()}"
            )
            logger.info(f"   ✅ Position Closed: {ticker}")
        except Exception as e:
            logger.error(f"   ❌ Failed to close position: {e}")

    async def run_daemon(self):
        """Continuous execution loop."""
        logger.info(f"🚀 DAEMON STARTED (CST: {get_cst_now()})")
        logger.info("   Press Ctrl+C to stop.")
        
        while True:
            try:
                logger.info(f"\n--- Cycle Start: {get_cst_now().strftime('%H:%M:%S')} ---")
                
                # 1. Scan Markets
                await self.run_cycle()
                
                # 2. Monitor Positions (SL/TP)
                await self.monitor_positions()
                
                logger.info("   Sleeping 60s...")
                await asyncio.sleep(60)
                
            except KeyboardInterrupt:
                logger.info("   🛑 Manual Stop")
                break
            except Exception as e:
                logger.error(f"   ⚠️ Cycle Error: {e}")
                await asyncio.sleep(60) # Wait before retry

async def main():
    bot = KalshiProductionBot()
    if await bot.connect():
        await bot.run_daemon()
        await bot.close()

if __name__ == "__main__":
    asyncio.run(main())
