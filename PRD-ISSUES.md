# PRD: Bug Fixes and Technical Debt Resolution
## Polymarket-Kalshi Sports Trading Bot

**Date:** 2026-01-28
**Priority:** Critical
**Status:** In Progress

---

## Executive Summary

A comprehensive code audit identified **14 issues** across frontend, backend, and deployment configurations. This document outlines each issue, its impact, and the recommended fix.

---

## Critical Issues (Fix Immediately)

### 1. React State Serialization with Set Objects
**Location:** `frontend/src/pages/Markets.tsx` - Lines 76, 82, 89

**Problem:**
```typescript
const [selectedGameIds, setSelectedGameIds] = useState<Set<string>>(new Set());
const [togglingIds, setTogglingIds] = useState<Set<string>>(new Set());
const [selectedLeagues, setSelectedLeagues] = useState<Set<string>>(new Set());
```

JavaScript `Set` objects cannot be serialized to JSON. This causes:
- State loss on page refresh
- Serialization errors in debugging tools
- Potential hydration mismatches

**Fix:**
```typescript
// Option 1: Use string array
const [selectedLeagues, setSelectedLeagues] = useState<string[]>([]);

// Option 2: Use Record<string, boolean>
const [selectedGameIds, setSelectedGameIds] = useState<Record<string, boolean>>({});
```

**Impact:** High - Users may lose selections unexpectedly

---

### 2. Wrong Token Key in Settings.tsx
**Location:** `frontend/src/pages/Settings.tsx` - Lines 962-972

**Problem:**
```typescript
await fetch('/api/v1/settings/global', {
  headers: {
    Authorization: `Bearer ${localStorage.getItem('token')}`,  // WRONG!
  },
  // ...
});
```

The correct key is `'auth_token'`, not `'token'`. This means the kill switch reset button **always fails with 401 Unauthorized**.

**Fix:**
```typescript
// Use apiClient instead of raw fetch
await apiClient.updateGlobalSettings({
  kill_switch_active: false,
  current_losing_streak: 0,
});
```

**Impact:** Critical - Kill switch cannot be reset through UI

---

### 3. Passphrase Not Saved for Polymarket L2 Auth
**Location:** `frontend/src/pages/Settings.tsx` - Lines 271-276

**Problem:**
The `connectWallet()` call for Polymarket doesn't pass the `api_passphrase` field, only `privateKey` and `funderAddress`.

**Fix:**
```typescript
await apiClient.connectWallet(walletCredentials.platform, {
  privateKey: walletCredentials.api_secret,
  funderAddress: walletCredentials.funder_address,
  apiKey: walletCredentials.api_key,        // Add this
  apiSecret: walletCredentials.api_secret,  // Add this
  passphrase: walletCredentials.api_passphrase, // Add this
});
```

**Impact:** High - Polymarket CLOB API credentials won't work

---

## High Priority Issues

### 4. Unhandled Decryption Errors
**Location:** `src/db/crud/polymarket_account.py` - Lines 100-102

**Problem:**
```python
if account.api_key_encrypted:
    result["api_key"] = decrypt_credential(account.api_key_encrypted)
```

No try/catch around decryption. If credentials are corrupted, the entire request fails with 500 error.

**Fix:**
```python
try:
    if account.api_key_encrypted:
        result["api_key"] = decrypt_credential(account.api_key_encrypted)
except Exception as e:
    logger.error(f"Failed to decrypt credentials for user {user_id}: {e}")
    raise HTTPException(status_code=500, detail="Credentials corrupted")
```

**Impact:** Medium - Users with corrupted credentials see generic errors

---

### 5. Hardcoded Fallback API URL
**Location:** `frontend/src/api/client.ts` - Line 6

**Problem:**
```typescript
const API_BASE_URL = import.meta.env.VITE_API_URL?.trim() ||
  'https://polymarket-sports-bot-production.up.railway.app/api/v1';
```

Silent fallback makes debugging difficult when env vars fail to load.

**Fix:**
```typescript
const API_BASE_URL = (() => {
  const url = import.meta.env.VITE_API_URL?.trim();
  if (!url) {
    console.warn('[API Client] VITE_API_URL not set, using fallback');
  }
  return url || 'https://polymarket-sports-bot-production.up.railway.app/api/v1';
})();
```

**Impact:** Low - Harder to debug deployment issues

---

## Medium Priority Issues

### 6. Incomplete Vercel Configuration
**Location:** `frontend/vercel.json`

**Current:**
```json
{
  "rewrites": [
    { "source": "/(.*)", "destination": "/" }
  ]
}
```

**Recommended:**
```json
{
  "buildCommand": "npm run build",
  "outputDirectory": "dist",
  "framework": "vite",
  "rewrites": [
    { "source": "/(.*)", "destination": "/" }
  ]
}
```

---

### 7. Poor API Error Messages
**Location:** `frontend/src/api/client.ts` - Lines 138-143

**Problem:**
```typescript
const error: ApiError = await response.json().catch(() => ({
  detail: 'An unexpected error occurred',
  status: response.status,
}));
```

Generic error messages don't help users or developers.

**Fix:**
```typescript
const error: ApiError = await response.json().catch(() => ({
  detail: `Request failed with status ${response.status}: ${response.statusText}`,
  status: response.status,
}));
```

---

### 8. No Auth State Migration Strategy
**Location:** `frontend/src/stores/useAuthStore.ts` - Lines 156-163

**Problem:** User object is persisted directly. If structure changes, old persisted data won't hydrate correctly.

**Fix:** Add version and migration:
```typescript
{
  name: 'auth-storage',
  version: 1,
  partialize: (state) => ({
    token: state.token,
    user: state.user,
    isAuthenticated: state.isAuthenticated,
  }),
  migrate: (persistedState, version) => {
    if (version === 0) {
      // Migration logic here
    }
    return persistedState;
  },
}
```

---

## Deployment Issues

### 9. Cloudflare Pages Not Deploying
**Root Cause:** Cloudflare Pages may not be configured correctly to:
1. Build from the `frontend` directory
2. Run `npm run build`
3. Serve from `dist` folder

**Verification Steps:**
1. Go to Cloudflare Dashboard → Pages → polymarket-sports-bot
2. Check Build Settings:
   - Build command: `cd frontend && npm install && npm run build`
   - Build output directory: `frontend/dist`
   - Root directory: `/` (or leave empty)

**Alternative:** Add `wrangler.toml` with explicit config:
```toml
name = "polymarket-sports-bot"
compatibility_date = "2024-01-01"

[build]
command = "cd frontend && npm install && npm run build"

[build.upload]
dir = "frontend/dist"
```

---

## Implementation Plan

### Phase 1: Critical Fixes (Today)
- [ ] Fix Set objects in Markets.tsx → use string[]
- [ ] Fix token key in Settings.tsx kill switch reset
- [ ] Add passphrase to Polymarket connectWallet

### Phase 2: High Priority (This Week)
- [ ] Add error handling for credential decryption
- [ ] Add API URL fallback warning
- [ ] Fix Cloudflare deployment configuration

### Phase 3: Polish (Next Week)
- [ ] Improve error messages in API client
- [ ] Add auth state migration strategy
- [ ] Complete Vercel configuration
- [ ] Add integration tests

---

## Files to Modify

| File | Changes |
|------|---------|
| `frontend/src/pages/Markets.tsx` | Replace Set with string[] |
| `frontend/src/pages/Settings.tsx` | Fix token key, add passphrase |
| `frontend/src/api/client.ts` | Add fallback warning, improve errors |
| `frontend/src/stores/useAuthStore.ts` | Add version and migration |
| `src/db/crud/polymarket_account.py` | Add decryption error handling |
| `frontend/wrangler.toml` | Add build configuration |

---

## Testing Checklist

- [ ] Markets page loads and shows ESPN games
- [ ] Can select multiple leagues
- [ ] BotConfig page works without errors
- [ ] Settings page kill switch reset works
- [ ] Polymarket credentials save correctly
- [ ] Cloudflare deployment succeeds
- [ ] All API endpoints return expected data

---

## Appendix: Full Issue List

| # | Severity | Location | Issue |
|---|----------|----------|-------|
| 1 | CRITICAL | Markets.tsx:76,82,89 | Set objects in React state |
| 2 | CRITICAL | Settings.tsx:962-972 | Wrong token key 'token' vs 'auth_token' |
| 3 | HIGH | Settings.tsx:271-276 | Missing passphrase in connectWallet |
| 4 | HIGH | polymarket_account.py:100-102 | Unhandled decrypt errors |
| 5 | HIGH | client.ts:6 | Silent fallback URL |
| 6 | MEDIUM | vercel.json | Incomplete config |
| 7 | MEDIUM | client.ts:138-143 | Poor error messages |
| 8 | MEDIUM | useAuthStore.ts:156-163 | No state migration |
| 9 | MEDIUM | Cloudflare | Deployment not working |
