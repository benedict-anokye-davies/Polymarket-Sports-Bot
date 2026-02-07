
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
        
            return False, "Invalid Date Parse"
            
        today = get_cst_now().date()
        
        if game_date > today:
            return False, f"Future game date: {market.get('open_date')} (Today CST: {today})"
        if (today - game_date).days > 1:
            return False, "Old game"

        # 2. Volume Check
        yes_ask = market.get("yes_ask", 0)
        volume = market.get("volume", 0)
        # contracts * ~50c estimate (or actual price)
        est_volume_dollars = volume * (yes_ask / 100.0) if yes_ask else volume * 0.50
        
        if est_volume_dollars < CONFIG["min_volume_dollars"]:
            return False, f"Low Volume (${est_volume_dollars:,.0f} < ${CONFIG['min_volume_dollars']:,.0f})"

        # 3. Strategy: Check for Drop
        # Need pregame prob
        pregame_prob = await self.get_pregame_probability(ticker)
        if pregame_prob is None:
            return False, "No pregame data found. STRICT MODE violation."
            
        current_prob = float(yes_ask) / 100.0
        
        # Calc drop
        drop = pregame_prob - current_prob
        
        if drop > CONFIG["drop_threshold"]:
             # Also ensure pregame was high enough (e.g. was favorite)
             if pregame_prob < CONFIG["min_pregame_prob"]:
                 return False, f"Was not favorite enough pregame ({pregame_prob:.2%})"
                 
             return True, f"DROP DETECTED! {pregame_prob:.1%} -> {current_prob:.1%} (Drop {drop:.1%})"
        
        return False, f"Drop {drop:.1%} < {CONFIG['drop_threshold']:.1%}"

    async def execute_trade(self, market, team):
        """Execute the order."""
        ticker = market.get("ticker")
        price_cents = market.get("yes_ask")
        
        if CONFIG["dry_run"]:
            logger.info(f"   👀 [DRY RUN] Would Buy {ticker} @ {price_cents}c")
            return

        logger.info(f"   🚀 EXECUTING BUY: {ticker} @ {price_cents}c")
        try:
            order = await self.client.place_order(
                ticker=ticker,
                side="buy",
                yes_no="yes",
                price=price_cents,
                size=int(CONFIG["position_size_dollars"]), # $1 size usually means 1 contract if size=count? No, size=count.
                # Client param says 'size'. 
                # If Position Size is $100 and price is 50c, we need 200 contracts.
                # contracts = dollars / (price_cents / 100)
                client_order_id=f"prod-{team}-{os.urandom(4).hex()}"
            )
            logger.info(f"   ✅ ORDER SENT: {order}")
        except Exception as e:
            logger.error(f"   ❌ ORDER FAILED: {e}")

    async def monitor_positions(self):
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
                
                logger.info("   Sleeping 3s...")
                await asyncio.sleep(3)
                
            except KeyboardInterrupt:
                logger.info("   🛑 Manual Stop")
                break
            except Exception as e:
                logger.error(f"   ⚠️ Cycle Error: {e}")
                await asyncio.sleep(3) # Wait before retry

async def main():
    bot = KalshiProductionBot()
    if await bot.connect():
        await bot.run_daemon()
        await bot.close()

if __name__ == "__main__":
    asyncio.run(main())
