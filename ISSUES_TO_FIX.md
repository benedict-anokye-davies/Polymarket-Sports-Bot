# Critical Issues To Fix - Trading Bot Audit

**Audit Date:** 2026-01-26
**Audited By:** Claude Code
**Status:** DEPLOY BLOCKER - Multiple critical issues will break Kalshi functionality

---

## Executive Summary

The bot has **6 CRITICAL issues** that will completely break Kalshi trading, plus **10+ HIGH/MEDIUM issues** that affect reliability. The Polymarket integration appears more complete, but Kalshi support is fundamentally broken and will fail at runtime.

---

## CRITICAL ISSUES (Must Fix Before Production)

### Issue #1: Kalshi Credential Keys Mismatch in Manual Orders
**File:** `src/api/routes/bot.py` (Lines 588-589)
**Severity:** CRITICAL
**Impact:** All manual Kalshi orders will fail with "credentials not configured"

**Problem:**
```python
# CURRENT CODE (WRONG)
kalshi_key = credentials.get("kalshi_api_key")
kalshi_private = credentials.get("kalshi_private_key")

# SHOULD BE
kalshi_key = credentials.get("api_key")
kalshi_private = credentials.get("api_secret")
```

**Database stores:** `api_key`, `api_secret` (from onboarding.py)
**Code looks for:** `kalshi_api_key`, `kalshi_private_key` (doesn't exist)

**Fix:** Change credential key names to match what's stored in database.

---

### Issue #2: No Kalshi Market Discovery
**File:** `src/services/market_discovery.py`
**Severity:** CRITICAL
**Impact:** Bot finds ZERO markets for Kalshi users - trading never starts

**Problem:**
- `MarketDiscovery.discover_sports_markets()` only queries Polymarket Gamma API
- No method exists to fetch Kalshi sports markets
- `KalshiClient.get_sports_markets()` exists but is NEVER called by the bot

**Fix Required:**
1. Add `discover_kalshi_markets()` method to MarketDiscovery
2. Or create separate `KalshiMarketDiscovery` class
3. Modify `bot_runner._discovery_loop()` to use platform-specific discovery

---

### Issue #3: No Kalshi WebSocket Support
**File:** `src/services/bot_runner.py` (Lines 313-314, 632-662)
**Severity:** CRITICAL
**Impact:** No real-time price updates for Kalshi - bot trades blind

**Problem:**
```python
# CURRENT CODE - Always creates Polymarket WebSocket
self.websocket = PolymarketWebSocket()
```

**Fix Required:**
1. Check platform before initializing WebSocket
2. Either implement `KalshiWebSocket` class
3. Or use polling-based price updates for Kalshi

---

### Issue #4: Dashboard Balance Fetch Fails for Kalshi
**File:** `src/api/routes/dashboard.py` (Lines 44-53)
**Severity:** CRITICAL
**Impact:** Kalshi users see $0.00 balance on dashboard

**Problem:**
```python
# CURRENT CODE - Always creates PolymarketClient
from src.services.polymarket_client import PolymarketClient
client = PolymarketClient(
    private_key=credentials["private_key"],      # Kalshi has no private_key
    funder_address=credentials["funder_address"] # Kalshi has no funder_address
)
```

**Fix Required:**
```python
platform = credentials.get("platform", "polymarket")
if platform == "kalshi":
    from src.services.kalshi_client import KalshiClient
    client = KalshiClient(
        api_key_id=credentials["api_key"],
        private_key_pem=credentials["api_secret"]
    )
    balance_data = await client.get_balance()
    balance_usdc = Decimal(str(balance_data.get("available_balance", 0)))
else:
    # existing Polymarket code
```

---

### Issue #5: Onboarding Wallet Test Crashes for Kalshi
**File:** `src/api/routes/onboarding.py` (Lines 200-206)
**Severity:** CRITICAL
**Impact:** Kalshi users cannot test wallet connection during onboarding

**Problem:**
```python
# CURRENT CODE - Always creates PolymarketClient
client = PolymarketClient(
    private_key=credentials["private_key"],      # KeyError for Kalshi
    funder_address=credentials["funder_address"] # KeyError for Kalshi
)
```

**Fix Required:** Check platform and create appropriate client.

---

### Issue #6: Balance Returns Different Types
**Files:** `src/services/kalshi_client.py` vs `src/services/polymarket_client.py`
**Severity:** CRITICAL
**Impact:** Type errors when bot tries to use balance for position sizing

**Kalshi returns:**
```python
{
    "available_balance": 1000.0,
    "total_balance": 1200.0,
    "pending_withdrawals": 0.0
}
```

**Polymarket returns:**
```python
Decimal("1000.00")
```

**Fix Required:** Standardize return format or handle both in bot_runner.

---

## HIGH SEVERITY ISSUES

### Issue #7: Paper Trading Not Implemented for Kalshi
**File:** `src/services/kalshi_client.py`
**Severity:** HIGH
**Impact:** Dry run mode doesn't simulate Kalshi orders properly

**Problem:**
- `dry_run` attribute exists but `place_order()` doesn't check it
- No simulated order tracking for Kalshi
- `wait_for_fill()` doesn't simulate fills in dry run mode

**Fix Required:** Add dry_run checks in Kalshi order methods like Polymarket has.

---

### Issue #8: Settings Page Cannot Update Kalshi Credentials
**File:** `frontend/src/pages/Settings.tsx`
**Severity:** HIGH
**Impact:** Users cannot change API keys after initial onboarding

**Problem:**
- Settings page has no Kalshi credential update form
- No platform selector to switch between Kalshi/Polymarket
- Users stuck with credentials entered during onboarding

**Fix Required:** Add platform-specific credential management to Settings page.

---

### Issue #9: Silent Exception Handling Hides Errors
**Files:** Multiple locations
**Severity:** HIGH
**Impact:** Errors occur but no one knows why - debugging impossible

**Locations with bare `except: pass`:**
- `src/services/bot_runner.py:628` - WebSocket errors
- `src/services/bot_runner.py:741` - Trade execution errors
- `src/services/bot_runner.py:1077` - Health check errors
- `src/db/database.py:66` - Database errors
- `src/api/routes/dashboard.py:52` - Balance fetch errors

**Fix Required:** Replace with proper error logging:
```python
except Exception as e:
    logger.error(f"Operation failed: {e}", exc_info=True)
```

---

### Issue #10: Kalshi RSA Key Validation Missing
**File:** `src/services/kalshi_client.py` (Lines 68-73)
**Severity:** HIGH
**Impact:** Cryptic errors if user provides invalid PEM format

**Problem:**
```python
self.private_key = serialization.load_pem_private_key(
    private_key_pem.encode() if isinstance(private_key_pem, str) else private_key_pem,
    password=None,
    backend=default_backend()
)
# No try/catch - fails with cryptography.exceptions.UnsupportedAlgorithm
```

**Fix Required:** Add validation with user-friendly error message.

---

## MEDIUM SEVERITY ISSUES

### Issue #11: Pending Orders Always Shows 0
**File:** `src/api/routes/bot.py` (Line 559)
**Severity:** MEDIUM
**Impact:** Dashboard shows incorrect pending order count

```python
pending_orders=0,  # TODO: Track pending orders
```

---

### Issue #12: Order Response Field Names Guessed
**File:** `src/api/routes/bot.py` (Line 659)
**Severity:** MEDIUM
**Impact:** May fail if Polymarket API changes response format

```python
order_id=result.get("orderID", result.get("order_id")),  # Guessing
```

---

### Issue #13: No Platform Filter in Market Configs
**File:** `src/api/routes/market_config.py`
**Severity:** MEDIUM
**Impact:** Kalshi tickers mixed with Polymarket token IDs

---

### Issue #14: Inconsistent Activity Log Categories
**File:** `src/api/routes/bot.py`
**Severity:** LOW
**Impact:** Hard to filter logs by platform

Uses both `"KALSHI_ORDER"` and `"POLYMARKET_ORDER"` - inconsistent.

---

## DEPLOYMENT CHECKLIST

Before going to production, ALL critical issues must be fixed:

- [ ] Fix Kalshi credential key names in bot.py
- [ ] Implement Kalshi market discovery
- [ ] Add platform check for WebSocket initialization
- [ ] Fix dashboard balance fetch for Kalshi
- [ ] Fix onboarding wallet test for Kalshi
- [ ] Standardize balance return format
- [ ] Add dry_run implementation for Kalshi
- [ ] Add Kalshi credentials to Settings page
- [ ] Replace bare except clauses with logging
- [ ] Add RSA key validation with friendly errors

---

## Files That Need Changes

| File | Changes Needed |
|------|----------------|
| `src/api/routes/bot.py` | Fix credential keys (lines 588-589) |
| `src/api/routes/dashboard.py` | Platform-aware balance fetch |
| `src/api/routes/onboarding.py` | Platform-aware wallet test |
| `src/services/market_discovery.py` | Add Kalshi market discovery |
| `src/services/bot_runner.py` | Platform-aware WebSocket, discovery |
| `src/services/kalshi_client.py` | Add dry_run to place_order, validate RSA key |
| `frontend/src/pages/Settings.tsx` | Add Kalshi credential management |

---

## Testing Recommendations

After fixes, test these flows:

1. **Kalshi Onboarding:** Register → Enter Kalshi credentials → Test connection → Complete
2. **Kalshi Dashboard:** Login → Check balance shows correctly
3. **Kalshi Paper Trading:** Start bot → Verify markets discovered → Check simulated trades
4. **Kalshi Live Trading:** (On testnet) Verify real orders placed
5. **Settings Update:** Change API keys → Verify bot uses new credentials

---

## Notes

- Polymarket integration appears more complete and may work
- Kalshi integration is fundamentally broken and needs significant work
- The codebase was clearly designed Polymarket-first with Kalshi added later
- Many Kalshi code paths were never tested
