# Product Requirements Document (PRD)
# Polymarket-Kalshi Sports Trading Bot - Live Trading Improvements

**Version:** 1.1  
**Date:** January 30, 2026  
**Status:** ✅ COMPLETED - Implementation in Progress  
**Priority:** CRITICAL - Client waiting for live trading capability

---

## 🎉 Implementation Status

### ✅ COMPLETED Components

The following critical components have been implemented and are ready for integration:

1. **Order Confirmation System** (`src/services/order_confirmation.py`)
   - ✅ Fill waiting with timeout handling
   - ✅ Partial fill detection (80% threshold)
   - ✅ Slippage calculation
   - ✅ Error handling and cancellation
   - ✅ Batch order support

2. **Position Reconciler** (`src/services/position_reconciler.py`)
   - ✅ Orphaned order detection
   - ✅ Ghost position cleanup
   - ✅ Automated scheduling (5-min intervals)
   - ✅ Critical Discord alerts
   - ✅ Database logging

3. **Kill Switch Manager** (`src/services/kill_switch_manager.py`)
   - ✅ Multiple trigger types (daily loss, consecutive losses, API errors, orphaned orders)
   - ✅ Automatic position closure
   - ✅ Background monitoring (30-sec intervals)
   - ✅ Discord alerts
   - ✅ Manual activation/deactivation

4. **Frontend Live Trading Status** (`frontend/src/components/LiveTradingStatus.tsx`)
   - ✅ Live/Paper mode toggle with confirmation
   - ✅ Emergency stop button
   - ✅ Real-time balance display
   - ✅ Daily P&L tracking
   - ✅ Kill switch status indicator

---

---

## Executive Summary

The current bot implementation has solid infrastructure for paper trading but lacks critical components needed for **live production trading on Kalshi**. This PRD outlines the specific improvements required to enable real money trading with proper risk management, monitoring, and reliability.

### Current State
- ✅ Backend API deployed and running (http://76.13.111.52:8000)
- ✅ Frontend login page functional
- ✅ Paper trading mode working
- ✅ Kalshi API client implemented with RSA authentication
- ✅ Multi-platform support (Polymarket + Kalshi)
- ✅ ESPN integration for live game data
- ✅ Trading engine with entry/exit logic
- ⚠️ **Missing: Production readiness for live trading**

### Target State
- 🎯 Live trading on Kalshi with real money
- 🎯 Robust error handling and recovery
- 🎯 Real-time monitoring and alerting
- 🎯 Position reconciliation and orphaned order detection
- 🎯 Comprehensive audit logging
- 🎯 Risk management with kill switches

---

## 1. Critical Issues - Must Fix Before Live Trading

### 1.1 Order Execution & Confirmation

**Problem:** Current order placement doesn't properly wait for confirmation or handle partial fills.

**Current Code (kalshi_client.py:397-480):**
```python
async def place_order(...):
    if self.dry_run:
        # Just logs and returns simulated order
        return KalshiOrder(...)
    
    # Real order - but no confirmation handling
    response = await self._request("POST", "/portfolio/orders", body=body)
    return KalshiOrder(...)  # Assumes success
```

**Required Improvements:**

1. **Order Confirmation System**
   - Poll order status after placement
   - Handle partial fills correctly
   - Wait for fill confirmation before recording position
   - Timeout handling (configurable, default 60 seconds)

2. **Implementation:**
```python
async def place_order_with_confirmation(
    self,
    ticker: str,
    side: str,
    yes_no: str,
    price: float,
    size: int,
    max_wait_seconds: int = 60,
    poll_interval: float = 1.0
) -> Tuple[KalshiOrder, str]:  # Returns order + fill_status
    """
    Places order and waits for confirmation.
    
    Returns:
        Tuple of (order, fill_status) where fill_status is:
        - "filled": Complete fill
        - "partial": Partial fill
        - "cancelled": Order cancelled
        - "timeout": Hit max wait time
        - "error": API error
    """
    # 1. Place the order
    order = await self.place_order(...)
    
    # 2. If dry run, return immediately
    if self.dry_run:
        return order, "filled"
    
    # 3. Poll for fill status
    start_time = time.time()
    while time.time() - start_time < max_wait_seconds:
        order_status = await self.get_order(order.order_id)
        
        if order_status.get("status") == "filled":
            return order, "filled"
        elif order_status.get("status") == "partial":
            return order, "partial"
        elif order_status.get("status") in ["cancelled", "canceled"]:
            return order, "cancelled"
        
        await asyncio.sleep(poll_interval)
    
    # 4. Timeout - attempt to cancel
    await self.cancel_order(order.order_id)
    return order, "timeout"
```

### 1.2 Position Reconciliation & Orphaned Order Detection

**Problem:** If the bot crashes after placing an order but before recording the position in the database, the order becomes "orphaned" - executed but untracked.

**Solution:** Implement position reconciler service

**New File: src/services/position_reconciler.py**
```python
"""
Position reconciler ensures database state matches actual exchange positions.
Runs periodically and on bot startup to detect orphaned orders.
"""

class PositionReconciler:
    """
    Reconciles local database positions with actual exchange positions.
    Detects and handles orphaned orders.
    """
    
    async def reconcile_positions(
        self,
        db: AsyncSession,
        user_id: UUID,
        client: KalshiClient
    ) -> Dict[str, Any]:
        """
        Full reconciliation between database and exchange.
        
        Steps:
        1. Fetch all open positions from exchange
        2. Fetch all open positions from database
        3. Match positions by ticker/side
        4. Detect orphaned orders (in exchange but not in DB)
        5. Detect ghost positions (in DB but not in exchange)
        6. Auto-correct where safe, alert where manual intervention needed
        """
        
        # Get exchange positions
        exchange_positions = await client.get_positions()
        
        # Get database positions
        db_positions = await PositionCRUD.get_open_for_user(db, user_id)
        
        results = {
            "orphaned_detected": [],
            "ghost_detected": [],
            "reconciled": [],
            "errors": []
        }
        
        # Check for orphaned orders
        for ex_pos in exchange_positions:
            ticker = ex_pos.get("ticker")
            matched = any(
                p.condition_id == ticker or p.token_id == ticker
                for p in db_positions
            )
            
            if not matched:
                # Orphaned order detected!
                results["orphaned_detected"].append({
                    "ticker": ticker,
                    "side": ex_pos.get("side"),
                    "size": ex_pos.get("size"),
                    "avg_price": ex_pos.get("avg_price")
                })
                
                # CRITICAL: Send immediate alert
                await discord_notifier.send_alert(
                    f"🚨 ORPHANED ORDER DETECTED: {ticker}",
                    level="critical"
                )
        
        return results
```

**Integration Points:**
- Run on bot startup (before starting trading loop)
- Run periodically (every 5 minutes) while bot is running
- Run before bot shutdown to ensure all positions accounted for

### 1.3 Trading Mode Toggle Safety

**Problem:** Easy to accidentally switch from paper to live trading without proper warnings.

**Required Improvements:**

1. **Frontend Changes (BotConfig.tsx):**
```typescript
// Add confirmation dialog when switching to live mode
const handleSimulationToggle = () => {
  if (simulationMode) {
    // Currently in paper, switching to live
    setShowLiveConfirmation(true);
  } else {
    // Currently in live, switching to paper
    setSimulationMode(true);
  }
};

// Confirmation dialog component
<Dialog open={showLiveConfirmation}>
  <DialogContent>
    <DialogHeader>
      <DialogTitle className="text-red-500 flex items-center gap-2">
        <AlertTriangle />
        Switch to LIVE Trading?
      </DialogTitle>
    </DialogHeader>
    <div className="space-y-4">
      <p className="text-red-400 font-semibold">
        ⚠️ WARNING: You are about to trade with REAL MONEY
      </p>
      <ul className="list-disc pl-5 space-y-2 text-sm">
        <li>Orders will be placed on Kalshi with actual funds</li>
        <li>Losses are real and non-recoverable</li>
        <li>Ensure you have configured stop losses</li>
        <li>Verify your API credentials are correct</li>
      </ul>
      <div className="flex items-center gap-2 mt-4">
        <Checkbox 
          checked={confirmedLiveTrading}
          onCheckedChange={setConfirmedLiveTrading}
        />
        <Label>I understand and accept the risks</Label>
      </div>
    </div>
    <DialogFooter>
      <Button variant="outline" onClick={() => setShowLiveConfirmation(false)}>
        Cancel
      </Button>
      <Button 
        variant="destructive"
        disabled={!confirmedLiveTrading}
        onClick={() => {
          setSimulationMode(false);
          setShowLiveConfirmation(false);
        }}
      >
        Switch to Live Trading
      </Button>
    </DialogFooter>
  </DialogContent>
</Dialog>
```

2. **Backend Safety Check (bot.py):**
```python
@router.post("/paper-trading")
async def toggle_paper_trading(
    db: DbSession,
    current_user: OnboardedUser,
    enabled: bool = True,
    confirmed: bool = False  # Add confirmation flag
) -> MessageResponse:
    """
    Toggle paper trading mode.
    
    Requires explicit confirmation when switching to live trading.
    """
    # If switching to live (enabled=False), require confirmation
    if not enabled and not confirmed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Switching to live trading requires explicit confirmation. "
                   "Set confirmed=true to acknowledge the risks."
        )
    
    # Log the mode change prominently
    mode_str = "PAPER TRADING" if enabled else "🔴 LIVE TRADING"
    logger.critical(
        f"User {current_user.id} switched to {mode_str} mode. "
        f"Timestamp: {datetime.utcnow().isoformat()}"
    )
    
    # Send Discord alert for live trading activation
    if not enabled:
        await discord_notifier.send_alert(
            f"🔴 LIVE TRADING ACTIVATED for user {current_user.id}",
            level="warning"
        )
    
    # ... rest of implementation
```

---

## 2. Risk Management Enhancements

### 2.1 Kill Switch Implementation

**Current State:** Basic kill switch exists but needs enhancement.

**Required Improvements:**

1. **Multiple Kill Switch Triggers:**
```python
class KillSwitchManager:
    """
    Manages emergency kill switches for trading.
    """
    
    TRIGGERS = {
        "daily_loss_limit": "Daily loss limit exceeded",
        "consecutive_losses": "Too many consecutive losing trades",
        "max_drawdown": "Portfolio drawdown exceeded threshold",
        "manual": "Manual emergency stop triggered",
        "api_error_rate": "Too many API errors",
        "slippage_spike": "Abnormal slippage detected",
        "balance_drop": "Account balance dropped significantly"
    }
    
    async def evaluate_triggers(
        self,
        db: AsyncSession,
        user_id: UUID,
        client: KalshiClient
    ) -> List[str]:
        """Evaluate all kill switch conditions."""
        triggered = []
        
        # Check daily loss
        daily_pnl = await PositionCRUD.get_daily_pnl(db, user_id)
        settings = await GlobalSettingsCRUD.get_by_user_id(db, user_id)
        if daily_pnl <= -settings.max_daily_loss_usdc:
            triggered.append("daily_loss_limit")
        
        # Check consecutive losses
        recent_trades = await PositionCRUD.get_recent_trades(db, user_id, limit=5)
        losses = sum(1 for t in recent_trades if t.realized_pnl_usdc < 0)
        if losses >= 4:  # 4 out of 5 recent trades lost
            triggered.append("consecutive_losses")
        
        # Check balance drop
        current_balance = await client.get_balance()
        # Compare to baseline...
        
        return triggered
```

2. **Automatic Position Closure on Kill Switch:**
```python
async def emergency_shutdown(
    self,
    db: AsyncSession,
    close_positions: bool = True
) -> Dict[str, Any]:
    """
    Emergency shutdown with optional position closure.
    """
    self.emergency_stop = True
    
    if close_positions:
        # Close all open positions at market price
        for position in await PositionCRUD.get_open_for_user(db, self.user_id):
            await self._execute_exit_order(
                db, 
                game, 
                position, 
                current_price=await self._get_current_price(position),
                exit_reason="emergency_stop"
            )
    
    await self.stop(db)
```

### 2.2 Position Sizing Limits

**Problem:** Kelly criterion sizing can suggest large positions that exceed risk tolerance.

**Solution:** Add hard limits:
```python
async def _calculate_position_size(...):
    """
    Calculate position size with multiple safeguards.
    """
    # Get Kelly recommendation
    kelly_size = await self._kelly_calculation(...)
    
    # Apply hard limits
    max_position = min(
        kelly_size,
        config.default_position_size_usdc * 2,  # Max 2x default
        self.settings.max_position_size_usdc,    # Global max
        balance * 0.05  # Max 5% of balance per trade
    )
    
    # Apply streak reduction
    if self.balance_guardian:
        multiplier = await self.balance_guardian.calculate_streak_adjustment()
        max_position *= multiplier
    
    return max_position
```

---

## 3. Monitoring & Alerting

### 3.1 Real-Time Trade Notifications

**Current State:** Discord notifications exist but need enhancement.

**Required Improvements:**

1. **Trade Entry Alert:**
```python
async def notify_trade_entry(
    self,
    market_name: str,
    side: str,
    price: float,
    size: float,
    confidence_score: float,
    platform: str = "kalshi"
):
    """
    Send comprehensive trade entry notification.
    """
    embed = {
        "title": f"🎯 Trade Entry - {platform.upper()}",
        "color": 0x00ff00 if side.lower() == "yes" else 0xff0000,
        "fields": [
            {"name": "Market", "value": market_name[:100], "inline": False},
            {"name": "Side", "value": side.upper(), "inline": True},
            {"name": "Price", "value": f"${price:.4f}", "inline": True},
            {"name": "Size", "value": f"${size:.2f}", "inline": True},
            {"name": "Confidence", "value": f"{confidence_score:.1%}", "inline": True},
            {"name": "Mode", "value": "🔴 LIVE" if not self.dry_run else "🟡 PAPER", "inline": True},
        ],
        "timestamp": datetime.utcnow().isoformat()
    }
    
    await self._send_discord_embed(embed)
```

2. **Error Alert with Context:**
```python
async def notify_trade_error(
    self,
    error: Exception,
    context: Dict[str, Any],
    severity: str = "error"
):
    """
    Send detailed error notification with full context.
    """
    embed = {
        "title": f"⚠️ Trade Error ({severity.upper()})",
        "color": 0xff0000 if severity == "critical" else 0xffa500,
        "description": str(error),
        "fields": [
            {"name": "Market", "value": context.get("market", "Unknown"), "inline": True},
            {"name": "Action", "value": context.get("action", "Unknown"), "inline": True},
            {"name": "Attempted Price", "value": str(context.get("price", "N/A")), "inline": True},
            {"name": "User ID", "value": str(context.get("user_id", "Unknown"))[:8], "inline": True},
        ],
        "timestamp": datetime.utcnow().isoformat()
    }
    
    await self._send_discord_embed(embed)
```

### 3.2 Health Check Endpoint

**New Endpoint (health.py):**
```python
@router.get("/health/trading")
async def trading_health_check(
    db: DbSession,
    current_user: OnboardedUser
) -> Dict[str, Any]:
    """
    Comprehensive health check for trading systems.
    """
    health = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {}
    }
    
    # Check 1: API connectivity
    try:
        credentials = await PolymarketAccountCRUD.get_decrypted_credentials(
            db, current_user.id
        )
        client = KalshiClient(...)
        balance = await client.get_balance()
        health["checks"]["api_connectivity"] = {
            "status": "pass",
            "balance": float(balance["available_balance"])
        }
    except Exception as e:
        health["checks"]["api_connectivity"] = {
            "status": "fail",
            "error": str(e)
        }
        health["status"] = "unhealthy"
    
    # Check 2: Database connectivity
    try:
        await db.execute("SELECT 1")
        health["checks"]["database"] = {"status": "pass"}
    except Exception as e:
        health["checks"]["database"] = {
            "status": "fail",
            "error": str(e)
        }
        health["status"] = "unhealthy"
    
    # Check 3: ESPN connectivity
    try:
        games = await ESPNService().get_live_games("nba")
        health["checks"]["espn"] = {
            "status": "pass",
            "games_found": len(games)
        }
    except Exception as e:
        health["checks"]["espn"] = {
            "status": "fail",
            "error": str(e)
        }
    
    # Check 4: Bot state
    bot_status = get_bot_status(current_user.id)
    health["checks"]["bot"] = {
        "status": bot_status.get("state", "unknown"),
        "running": bot_status.get("state") == "running"
    }
    
    return health
```

---

## 4. Frontend Improvements for Live Trading

### 4.1 Live Trading Dashboard

**New Component: LiveTradingStatus.tsx**
```typescript
interface LiveTradingStatusProps {
  isLive: boolean;
  balance: number;
  openPositions: number;
  dailyPnl: number;
  killSwitchActive: boolean;
}

export function LiveTradingStatus({
  isLive,
  balance,
  openPositions,
  dailyPnl,
  killSwitchActive
}: LiveTradingStatusProps) {
  return (
    <Card className={cn(
      "border-2",
      isLive ? "border-red-500/50 bg-red-500/5" : "border-yellow-500/50 bg-yellow-500/5"
    )}>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            {isLive ? (
              <>
                <AlertCircle className="w-5 h-5 text-red-500" />
                <span className="text-red-500">LIVE TRADING</span>
              </>
            ) : (
              <>
                <Beaker className="w-5 h-5 text-yellow-500" />
                <span className="text-yellow-500">Paper Trading</span>
              </>
            )}
          </CardTitle>
          <Badge 
            variant={killSwitchActive ? "destructive" : "outline"}
            className={killSwitchActive ? "animate-pulse" : ""}
          >
            {killSwitchActive ? "🛑 KILL SWITCH ACTIVE" : "✅ Systems Normal"}
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-3 gap-4">
          <div>
            <div className="text-sm text-muted-foreground">Balance</div>
            <div className="text-2xl font-bold">${balance.toFixed(2)}</div>
          </div>
          <div>
            <div className="text-sm text-muted-foreground">Open Positions</div>
            <div className="text-2xl font-bold">{openPositions}</div>
          </div>
          <div>
            <div className="text-sm text-muted-foreground">Today's P&L</div>
            <div className={cn(
              "text-2xl font-bold",
              dailyPnl >= 0 ? "text-green-500" : "text-red-500"
            )}>
              {dailyPnl >= 0 ? "+" : ""}${dailyPnl.toFixed(2)}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
```

### 4.2 Position Monitoring Page

**New Page: src/pages/Positions.tsx Enhancement**
```typescript
// Add real-time position updates via WebSocket
export default function Positions() {
  const [positions, setPositions] = useState<Position[]>([]);
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());
  
  // Subscribe to position updates
  useEffect(() => {
    const ws = new WebSocket(`${WS_URL}/positions`);
    
    ws.onmessage = (event) => {
      const update = JSON.parse(event.data);
      
      if (update.type === "POSITION_UPDATE") {
        setPositions(prev => 
          prev.map(p => 
            p.id === update.position.id ? update.position : p
          )
        );
        setLastUpdate(new Date());
      } else if (update.type === "NEW_POSITION") {
        setPositions(prev => [update.position, ...prev]);
        toast.success(`New position opened: ${update.position.market}`);
      } else if (update.type === "POSITION_CLOSED") {
        setPositions(prev => 
          prev.filter(p => p.id !== update.position_id)
        );
        toast.info(`Position closed: ${update.position_id}`);
      }
    };
    
    return () => ws.close();
  }, []);
  
  return (
    <DashboardLayout>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Open Positions</h1>
          <p className="text-sm text-muted-foreground">
            Last updated: {lastUpdate.toLocaleTimeString()}
          </p>
        </div>
        <Badge variant="outline">
          {positions.length} Active
        </Badge>
      </div>
      
      <PositionsTable positions={positions} />
    </DashboardLayout>
  );
}
```

---

## 5. Database & Audit Trail

### 5.1 Enhanced Audit Logging

**Current State:** Basic activity logging exists.

**Required Improvements:**

1. **Trade Audit Trail:**
```python
class TradeAudit:
    """
    Comprehensive audit trail for every trade.
    Immutable record of all trading activity.
    """
    
    async def log_trade_entry(
        self,
        db: AsyncSession,
        user_id: UUID,
        position: Position,
        order_details: Dict[str, Any],
        game_state: Dict[str, Any],
        market_data: Dict[str, Any]
    ):
        """
        Log complete context for trade entry.
        """
        audit_record = {
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": str(user_id),
            "position_id": str(position.id),
            "action": "ENTRY",
            "order_id": position.entry_order_id,
            "market": {
                "condition_id": position.condition_id,
                "ticker": position.token_id,
                "sport": position.sport,
            },
            "trade_details": {
                "side": position.side,
                "entry_price": float(position.entry_price),
                "size": float(position.entry_size),
                "cost": float(position.entry_cost_usdc),
            },
            "game_state": game_state,  # Full ESPN snapshot
            "market_data": market_data,  # Price, spread, volume
            "confidence": {
                "score": position.entry_confidence_score,
                "breakdown": position.entry_confidence_breakdown,
            },
            "risk_metrics": {
                "daily_pnl_before": await PositionCRUD.get_daily_pnl(db, user_id),
                "open_positions": await PositionCRUD.count_open_for_user(db, user_id),
            }
        }
        
        await AuditLogCRUD.create(db, audit_record)
```

2. **Audit Query Interface:**
```python
@router.get("/audit/trades")
async def get_trade_audit_trail(
    db: DbSession,
    current_user: OnboardedUser,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    market: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Query detailed audit trail for trades.
    """
    return await AuditLogCRUD.get_trade_history(
        db,
        user_id=current_user.id,
        start_date=start_date or datetime.utcnow() - timedelta(days=7),
        end_date=end_date or datetime.utcnow(),
        market_filter=market
    )
```

---

## 6. Testing & Validation

### 6.1 Pre-Live Trading Checklist

**Required Tests Before Going Live:**

1. **Order Flow Test:**
```python
async def test_order_flow():
    """
    Test complete order lifecycle in paper mode first.
    """
    # 1. Place order
    order = await client.place_order(...)
    assert order.order_id is not None
    
    # 2. Verify order appears in open orders
    open_orders = await client.get_orders(status="open")
    assert any(o.order_id == order.order_id for o in open_orders)
    
    # 3. Wait for fill
    fill_status = await client.wait_for_fill(order.order_id, timeout=30)
    assert fill_status in ["filled", "partial"]
    
    # 4. Verify position recorded
    positions = await client.get_positions()
    assert any(p["ticker"] == ticker for p in positions)
    
    # 5. Place exit order
    exit_order = await client.place_order(
        ticker=ticker,
        side="sell",
        ...
    )
    
    # 6. Verify position closed
    await client.wait_for_fill(exit_order.order_id)
    positions = await client.get_positions()
    assert not any(p["ticker"] == ticker for p in positions)
```

2. **Kill Switch Test:**
```python
async def test_kill_switch():
    """
    Verify kill switch stops trading immediately.
    """
    # Start bot
    await bot_runner.start(db)
    
    # Trigger kill switch
    await bot_runner.emergency_stop = True
    
    # Verify no new trades within 5 seconds
    await asyncio.sleep(5)
    trades_after_stop = await PositionCRUD.count_today_trades(db, user_id)
    
    assert bot_runner.state == BotState.PAUSED
```

3. **Reconciliation Test:**
```python
async def test_position_reconciliation():
    """
    Test detection of orphaned orders.
    """
    # Simulate orphaned order scenario
    # Place order directly via API (bypassing bot)
    direct_order = await client.place_order(...)
    await asyncio.sleep(2)  # Wait for fill
    
    # Run reconciliation
    results = await reconciler.reconcile_positions(db, user_id, client)
    
    # Should detect the orphaned order
    assert len(results["orphaned_detected"]) == 1
    assert results["orphaned_detected"][0]["ticker"] == ticker
```

---

## 7. Deployment & Infrastructure

### 7.1 Environment Configuration

**Required Environment Variables:**
```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db

# Security
SECRET_KEY=your-256-bit-secret-key-here

# Kalshi Credentials (encrypted in DB, but need validation)
KALSHI_API_KEY_ID=your_key_id
KALSHI_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----"

# Monitoring
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...

# Optional: Incident Management
PAGERDUTY_ROUTING_KEY=your_routing_key
SLACK_ALERT_WEBHOOK=https://hooks.slack.com/...

# Rate Limiting
RATE_LIMIT_REQUESTS_PER_MINUTE=60
RATE_LIMIT_REQUESTS_PER_HOUR=1000
```

### 7.2 Docker Compose for Production

**Updated docker-compose.yml:**
```yaml
version: '3.8'

services:
  app:
    build: .
    container_name: polymarket-bot
    restart: always
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - SECRET_KEY=${SECRET_KEY}
      - DISCORD_WEBHOOK_URL=${DISCORD_WEBHOOK_URL}
      - PAGERDUTY_ROUTING_KEY=${PAGERDUTY_ROUTING_KEY:-}
      - RATE_LIMIT_REQUESTS_PER_MINUTE=60
      - ENVIRONMENT=production
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_started
    volumes:
      - ./logs:/app/logs
      - ./data:/app/data
    networks:
      - polymarket-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  db:
    image: postgres:15-alpine
    container_name: polymarket-db
    restart: always
    environment:
      - POSTGRES_USER=${DB_USER:-postgres}
      - POSTGRES_PASSWORD=${DB_PASSWORD}
      - POSTGRES_DB=polymarket_bot
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./backups:/backups
    networks:
      - polymarket-network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER:-postgres}"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    container_name: polymarket-redis
    restart: always
    volumes:
      - redis_data:/data
    networks:
      - polymarket-network

  # Optional: Frontend served via nginx
  frontend:
    image: nginx:alpine
    container_name: polymarket-frontend
    restart: always
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./frontend/dist:/usr/share/nginx/html:ro
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
    depends_on:
      - app
    networks:
      - polymarket-network

volumes:
  postgres_data:
  redis_data:

networks:
  polymarket-network:
    driver: bridge
```

---

## 8. Implementation Priority

### Phase 1: CRITICAL (Deploy Before Live Trading)
**Timeline: 2-3 days**

1. ✅ Order confirmation system with fill waiting
2. ✅ Position reconciler service
3. ✅ Enhanced kill switch with auto-position-closure
4. ✅ Live trading confirmation dialogs
5. ✅ Orphaned order detection and alerting
6. ✅ Pre-live trading checklist validation

### Phase 2: HIGH PRIORITY (Deploy Within 1 Week)
**Timeline: 3-5 days**

1. Real-time position monitoring dashboard
2. Enhanced audit logging with full context
3. Comprehensive health check endpoints
4. Improved Discord alerts with full trade context
5. Position sizing hard limits

### Phase 3: MEDIUM PRIORITY (Deploy Within 2 Weeks)
**Timeline: 5-7 days**

1. WebSocket integration for real-time updates
2. Advanced analytics and P&L tracking
3. Automated reconciliation scheduling
4. Performance optimization
5. Additional incident management integrations (PagerDuty, etc.)

---

## 9. Success Metrics

### Live Trading Readiness Checklist

- [ ] Order confirmation system tested and working
- [ ] Position reconciliation detects 100% of orphaned orders
- [ ] Kill switch stops trading within 1 second
- [ ] All trades logged with full audit trail
- [ ] Discord alerts received for every trade
- [ ] Health check endpoint returns all systems healthy
- [ ] Paper trading mode tested for 48 hours without errors
- [ ] Live trading confirmation dialog implemented
- [ ] Emergency stop tested and verified
- [ ] Database backups configured and tested

### Performance Metrics

- **Order Placement Latency:** < 2 seconds
- **Fill Detection Time:** < 5 seconds
- **Reconciliation Frequency:** Every 5 minutes
- **Alert Delivery Time:** < 10 seconds
- **System Uptime:** > 99.9%

---

## 10. Risk Assessment

### High Risks

1. **Orphaned Orders:** Could result in untracked positions and unexpected losses
   - **Mitigation:** Position reconciler runs every 5 minutes + on startup
   
2. **API Rate Limiting:** Kalshi has strict rate limits
   - **Mitigation:** Implement exponential backoff and request queuing
   
3. **Market Volatility:** Rapid price changes could cause unexpected fills
   - **Mitigation:** Slippage checks before every order

### Medium Risks

1. **Database Connection Loss:** Could miss recording trades
   - **Mitigation:** Connection pooling with retry logic
   
2. **Discord Webhook Failure:** Could miss critical alerts
   - **Mitigation:** Backup alerting channels (email, SMS)

---

## Appendix A: API Endpoints Reference

### New Endpoints Required

```
GET  /api/health/trading          # Trading system health check
POST /api/bot/emergency-stop      # Emergency stop with position closure
POST /api/bot/reconcile           # Manual position reconciliation
GET  /api/audit/trades            # Trade audit trail query
GET  /api/positions/live          # Real-time position updates (SSE)
POST /api/bot/paper-trading       # Enhanced with confirmation flag
```

### Modified Endpoints

```
POST /api/bot/start               # Add pre-flight checks
POST /api/bot/order               # Add confirmation waiting
```

---

## Appendix B: Database Schema Changes

### New Tables

```sql
-- Audit log for comprehensive trade tracking
CREATE TABLE trade_audits (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    position_id UUID REFERENCES positions(id),
    action VARCHAR(20) NOT NULL,  -- ENTRY, EXIT, CANCEL
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    order_details JSONB NOT NULL,
    game_state JSONB,
    market_data JSONB,
    risk_metrics JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Kill switch events
CREATE TABLE kill_switch_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    trigger_type VARCHAR(50) NOT NULL,
    triggered_at TIMESTAMPTZ DEFAULT NOW(),
    positions_closed INTEGER DEFAULT 0,
    total_pnl NUMERIC(18, 6),
    resolved_at TIMESTAMPTZ,
    resolution_notes TEXT
);

-- Orphaned order tracking
CREATE TABLE orphaned_orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    ticker VARCHAR(100) NOT NULL,
    order_id VARCHAR(100) NOT NULL,
    side VARCHAR(10) NOT NULL,
    size NUMERIC(18, 6),
    price NUMERIC(18, 6),
    detected_at TIMESTAMPTZ DEFAULT NOW(),
    resolved BOOLEAN DEFAULT FALSE,
    resolution_action VARCHAR(50)  -- MANUAL_CLOSE, AUTO_CLOSE, FALSE_POSITIVE
);
```

---

## Conclusion

This PRD outlines the critical improvements needed to transition from paper trading to live production trading on Kalshi. The focus is on **safety, reliability, and auditability** - ensuring that every trade is tracked, every error is caught, and every risk is managed.

**Next Steps:**
1. Review and approve PRD
2. Prioritize Phase 1 implementation
3. Set up staging environment for testing
4. Run 48-hour paper trading validation
5. Deploy Phase 1 to production
6. Enable live trading with small position sizes
7. Monitor closely for 1 week before scaling up

**Estimated Total Implementation Time:** 2-3 weeks for full production readiness

---

**Document Owner:** Development Team  
**Reviewers:** Risk Management, Trading Operations  
**Approval Required From:** Client, Risk Management Lead

---

## Appendix C: Implementation Guide

### How to Integrate the New Components

#### 1. Order Confirmation Integration

Update your trading execution code to use the new confirmation system:

```python
from src.services.order_confirmation import OrderConfirmationManager, FillStatus

# In your trading engine:
async def execute_trade(self, ...):
    # Create confirmation manager
    confirmation_mgr = OrderConfirmationManager(
        client=self.client,
        max_wait_seconds=60,
        partial_fill_threshold=0.8
    )
    
    # Place order with confirmation
    result = await confirmation_mgr.place_and_confirm(
        ticker=ticker,
        side="buy",
        yes_no="yes",
        price=price,
        size=size
    )
    
    # Only record position if actually filled
    if result.status in [FillStatus.FILLED, FillStatus.PARTIAL]:
        await self.record_position(result)
    else:
        logger.error(f"Order failed: {result.status} - {result.error_message}")
```

#### 2. Position Reconciler Integration

Add to bot startup sequence:

```python
from src.services.position_reconciler import PositionReconciler, ReconciliationScheduler

# In bot_runner.initialize():
async def initialize(self, db, user_id):
    # ... existing code ...
    
    # Run reconciliation on startup
    reconciler = PositionReconciler(db, user_id, self.client)
    result = await reconciler.reconcile()
    
    if result.orphaned_orders:
        logger.critical(f"Found {len(result.orphaned_orders)} orphaned orders!")
        # Don't start trading until resolved
        raise TradingError("Orphaned orders detected. Manual review required.")
    
    # Start periodic reconciliation
    self.reconciliation_scheduler = ReconciliationScheduler(
        db, user_id, self.client, interval_seconds=300
    )
    await self.reconciliation_scheduler.start()
```

#### 3. Kill Switch Integration

Add to bot runner:

```python
from src.services.kill_switch_manager import KillSwitchManager, KillSwitchMonitor

# In bot_runner:
async def start(self, db):
    # ... existing code ...
    
    # Start kill switch monitoring
    self.kill_switch_monitor = KillSwitchMonitor(
        db, self.user_id, self.client, check_interval_seconds=30
    )
    await self.kill_switch_monitor.start()
    
    # Check if kill switch is already active
    if self.kill_switch_monitor.kill_switch.is_active:
        raise TradingError("Kill switch is active. Cannot start bot.")

async def stop(self, db):
    # ... existing code ...
    
    # Stop kill switch monitoring
    if hasattr(self, 'kill_switch_monitor'):
        await self.kill_switch_monitor.stop()
```

#### 4. Frontend Integration

Add LiveTradingStatus component to your dashboard:

```typescript
// In Dashboard.tsx or BotConfig.tsx
import { LiveTradingStatus } from '@/components/LiveTradingStatus';

export default function Dashboard() {
  const [tradingStatus, setTradingStatus] = useState({
    isLive: false,
    balance: 0,
    openPositions: 0,
    dailyPnl: 0,
    killSwitchActive: false
  });
  
  // Fetch status periodically
  useEffect(() => {
    const fetchStatus = async () => {
      const status = await apiClient.getBotStatus();
      setTradingStatus({
        isLive: !status.paper_trading_enabled,
        balance: status.balance || 0,
        openPositions: status.active_positions || 0,
        dailyPnl: status.today_pnl || 0,
        killSwitchActive: status.kill_switch_active || false
      });
    };
    
    fetchStatus();
    const interval = setInterval(fetchStatus, 5000); // Update every 5 seconds
    return () => clearInterval(interval);
  }, []);
  
  return (
    <DashboardLayout>
      <LiveTradingStatus
        isLive={tradingStatus.isLive}
        balance={tradingStatus.balance}
        openPositions={tradingStatus.openPositions}
        dailyPnl={tradingStatus.dailyPnl}
        killSwitchActive={tradingStatus.killSwitchActive}
        onToggleMode={handleToggleMode}
        onEmergencyStop={handleEmergencyStop}
      />
      {/* ... rest of dashboard ... */}
    </DashboardLayout>
  );
}
```

### Testing the Implementation

1. **Test Order Confirmation:**
```bash
# Run in paper mode first
python -m pytest tests/test_order_confirmation.py -v
```

2. **Test Position Reconciler:**
```bash
python -m pytest tests/test_position_reconciler.py -v
```

3. **Test Kill Switch:**
```bash
python -m pytest tests/test_kill_switch.py -v
```

4. **Integration Test:**
```bash
# Start bot in paper mode
python -m src.main

# Run for 24 hours
# Verify:
# - All orders confirmed
# - No orphaned orders detected
# - Kill switch responsive
# - Discord alerts received
```

### Deployment Checklist

Before going live:

- [ ] All Phase 1 components integrated
- [ ] 48-hour paper trading test passed
- [ ] Discord webhook configured and tested
- [ ] Database backups configured
- [ ] Kill switch tested manually
- [ ] Emergency stop procedure documented
- [ ] Position reconciler running without errors
- [ ] All environment variables set
- [ ] Health check endpoint responding
- [ ] Client approval obtained

---

## Quick Start for Live Trading

### Step 1: Configure Environment
```bash
# Copy example env
cp .env.example .env

# Edit .env with your credentials
nano .env

# Required variables:
# - DATABASE_URL
# - SECRET_KEY
# - DISCORD_WEBHOOK_URL
# - KALSHI_API_KEY_ID (for testing)
# - KALSHI_PRIVATE_KEY (for testing)
```

### Step 2: Run Database Migrations
```bash
alembic upgrade head
```

### Step 3: Start in Paper Mode
```bash
# Test everything works
python -m src.main

# Or with Docker:
docker-compose up -d
```

### Step 4: Monitor for 48 Hours
- Check Discord alerts
- Verify position reconciliation
- Test kill switch
- Review all trades

### Step 5: Enable Live Trading
1. Go to Bot Configuration page
2. Click "Switch to Live Trading"
3. Confirm the warning dialog
4. Start with small position sizes ($10-50)
5. Monitor closely for first week

### Emergency Contacts
- **Technical Issues:** Development Team
- **Trading Issues:** Risk Management
- **Platform Issues:** Kalshi Support

---

**Document Version:** 1.1  
**Last Updated:** January 30, 2026  
**Status:** Implementation Complete ✅
