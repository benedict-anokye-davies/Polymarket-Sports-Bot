# Testing Guide - Live Trading Implementation

**Date:** January 30, 2026  
**Purpose:** Verify all live trading components work correctly  
**Status:** Test suite created, ready for execution

---

## 🚨 Critical Issues to Fix First

The LSP diagnostics show **existing errors** in the codebase that must be fixed before testing:

### 1. Type Mismatch Errors (High Priority)
**Files:** `src/services/trading_engine.py`, `src/services/bot_runner.py`

**Issue:** String user_id being passed where UUID expected
```python
# ERROR: Argument of type "str" cannot be assigned to parameter "user_id" of type "UUID"
await PositionCRUD.count_open_for_market(db, self.user_id, ...)
```

**Fix Required:**
```python
from uuid import UUID

# Convert string to UUID
user_id_uuid = UUID(self.user_id) if isinstance(self.user_id, str) else self.user_id
await PositionCRUD.count_open_for_market(db, user_id_uuid, ...)
```

### 2. KalshiClient Type Errors (High Priority)
**Files:** `src/api/routes/bot.py`, `src/services/trading_engine.py`

**Issue:** KalshiClient not compatible with PolymarketClient type hints
```python
# ERROR: "KalshiClient" is not assignable to "PolymarketClient"
trading_engine = TradingEngine(..., polymarket_client=kalshi_client)
```

**Fix Required:**
Update TradingEngine to accept both client types:
```python
from typing import Union
from src.services.kalshi_client import KalshiClient
from src.services.polymarket_client import PolymarketClient

class TradingEngine:
    def __init__(
        self,
        ...,
        trading_client: Union[PolymarketClient, KalshiClient],
        ...
    ):
        self.trading_client = trading_client
```

### 3. Missing Parameters (Medium Priority)
**File:** `src/services/bot_runner.py`

**Issue:** Function calls missing required parameters
```python
# ERROR: No parameter named "ticker"
await self.client.place_order(...)
```

**Fix Required:** Update function signatures to match KalshiClient API

---

## 🧪 Test Execution Plan

### Step 1: Fix Critical Errors
```bash
# 1. Fix type mismatches
python scripts/fix_type_errors.py

# 2. Verify imports
python -c "from src.services.trading_engine import TradingEngine; print('OK')"

# 3. Check for syntax errors
python -m py_compile src/services/*.py
```

### Step 2: Run Unit Tests
```bash
# Install test dependencies
pip install pytest pytest-asyncio

# Run order confirmation tests
pytest tests/test_order_confirmation.py -v

# Run position reconciler tests (when created)
pytest tests/test_position_reconciler.py -v

# Run kill switch tests (when created)
pytest tests/test_kill_switch.py -v
```

### Step 3: Integration Testing
```bash
# Start the API
python -m src.main

# Test health endpoint
curl http://localhost:8000/api/health/quick

# Test trading health (requires auth)
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/health/trading
```

### Step 4: Manual Testing Checklist

#### Paper Trading Mode (48 Hours)
- [ ] Start bot in paper mode
- [ ] Verify orders are placed
- [ ] Check Discord alerts received
- [ ] Monitor position reconciliation logs
- [ ] Verify no orphaned orders detected
- [ ] Check kill switch not triggered falsely

#### Order Confirmation
- [ ] Place test order
- [ ] Verify confirmation waits for fill
- [ ] Test partial fill handling
- [ ] Test timeout scenario
- [ ] Verify slippage calculation

#### Position Reconciliation
- [ ] Run manual reconciliation
- [ ] Verify no orphaned orders in paper mode
- [ ] Check ghost position detection
- [ ] Verify Discord alerts work

#### Kill Switch
- [ ] Test manual activation
- [ ] Test daily loss trigger (set low limit)
- [ ] Verify positions close on activation
- [ ] Test reset procedure
- [ ] Check Discord alerts

#### Emergency Stop
- [ ] Click emergency stop button
- [ ] Verify trading stops immediately
- [ ] Check positions are closed
- [ ] Verify cannot restart until cleared

---

## 🔧 Pre-Testing Fixes Required

### Fix 1: Update TradingEngine Type Hints
**File:** `src/services/trading_engine.py` (Line ~80)
```python
# BEFORE:
from src.services.polymarket_client import PolymarketClient

def __init__(..., polymarket_client: PolymarketClient, ...):
    self.polymarket_client = polymarket_client

# AFTER:
from typing import Union
from src.services.polymarket_client import PolymarketClient
from src.services.kalshi_client import KalshiClient

def __init__(..., trading_client: Union[PolymarketClient, KalshiClient], ...):
    self.trading_client = trading_client
```

### Fix 2: Convert user_id to UUID
**File:** `src/services/trading_engine.py` (Multiple locations)
```python
# BEFORE:
open_positions = await PositionCRUD.count_open_for_user(db, self.user_id)

# AFTER:
from uuid import UUID
user_id = UUID(self.user_id) if isinstance(self.user_id, str) else self.user_id
open_positions = await PositionCRUD.count_open_for_user(db, user_id)
```

### Fix 3: Update Bot Runner Dependencies
**File:** `src/services/bot_runner.py`
```python
# BEFORE:
from src.services.trading_engine import TradingEngine

# AFTER:
from src.services.trading_engine import TradingEngine
from src.services.order_confirmation import OrderConfirmationManager
from src.services.position_reconciler import PositionReconciler, ReconciliationScheduler
from src.services.kill_switch_manager import KillSwitchMonitor
```

---

## 📝 Test Results Log

### Unit Tests
| Test Suite | Status | Pass | Fail | Notes |
|------------|--------|------|------|-------|
| Order Confirmation | ⏳ PENDING | - | - | Run: `pytest tests/test_order_confirmation.py` |
| Position Reconciler | ⏳ PENDING | - | - | File needs creation |
| Kill Switch | ⏳ PENDING | - | - | File needs creation |
| Health API | ⏳ PENDING | - | - | Manual testing required |

### Integration Tests
| Component | Status | Result | Notes |
|-----------|--------|--------|-------|
| Health Endpoint | ⏳ PENDING | - | Test with curl |
| Reconciliation API | ⏳ PENDING | - | Test with curl |
| Emergency Stop | ⏳ PENDING | - | Test via frontend |
| Live Trading Toggle | ⏳ PENDING | - | Test via frontend |

### Manual Tests
| Test | Status | Duration | Result |
|------|--------|----------|--------|
| 48hr Paper Trading | ⏳ PENDING | 48 hours | - |
| Kill Switch Trigger | ⏳ PENDING | 5 min | - |
| Emergency Stop | ⏳ PENDING | 2 min | - |
| Discord Alerts | ⏳ PENDING | 10 min | - |

---

## 🚀 Quick Test Commands

```bash
# 1. Check for syntax errors
python -m py_compile src/services/order_confirmation.py
python -m py_compile src/services/position_reconciler.py
python -m py_compile src/services/kill_switch_manager.py

# 2. Run order confirmation tests
pytest tests/test_order_confirmation.py -v --tb=short

# 3. Start API and test health
cd src && python -m uvicorn main:app --reload &
sleep 3
curl http://localhost:8000/api/health/quick

# 4. Test with real credentials (paper mode only!)
# Set KALSHI_API_KEY and KALSHI_PRIVATE_KEY in .env
# Ensure dry_run=True
python scripts/test_live_trading.py
```

---

## ⚠️ Safety Warnings

### BEFORE Running Tests:
1. ✅ Ensure `dry_run=True` in settings
2. ✅ Use paper trading mode only
3. ✅ Set small position sizes ($10-50)
4. ✅ Have Discord webhook configured
5. ✅ Test emergency stop first
6. ✅ Monitor all alerts closely

### NEVER:
- ❌ Test with real money initially
- ❌ Skip paper trading phase
- ❌ Ignore Discord alerts
- ❌ Disable kill switch
- ❌ Run without monitoring

---

## 📊 Success Criteria

The implementation is **verified working** when:

✅ All unit tests pass (90%+ coverage)  
✅ Health endpoint returns 200 OK  
✅ Order confirmation works in paper mode  
✅ Position reconciliation runs without errors  
✅ Kill switch triggers correctly  
✅ Emergency stop works immediately  
✅ Discord alerts received for all events  
✅ 48-hour paper trading completes without issues  

---

## 🐛 Known Issues

1. **Type Mismatches:** String/UUID conversions needed
2. **Client Type Errors:** TradingEngine needs Union type hints
3. **Import Errors:** Some bot_runner dependencies need updating
4. **Missing Tests:** Position reconciler and kill switch tests need creation

**Estimated fix time:** 2-3 hours  
**Estimated test time:** 4-6 hours (including 48hr paper trading)

---

## 📞 Debugging Tips

### If Tests Fail:
```bash
# Run with verbose output
pytest tests/test_order_confirmation.py -vvs

# Run specific test
pytest tests/test_order_confirmation.py::TestOrderConfirmationManager::test_place_and_confirm_successful_fill -v

# Check logs
tail -f logs/trading.log
```

### If API Won't Start:
```bash
# Check for import errors
python -c "from src.api.routes.health import router; print('OK')"

# Check database connection
python scripts/test_db_connection.py

# Verify environment variables
python -c "from src.config import settings; print(settings.database_url)"
```

---

**Last Updated:** January 30, 2026  
**Status:** Test suite created, fixes required before execution  
**Next Action:** Fix type errors, then run test suite
