# PRD: "Failed to Fetch" Network Error Resolution

**Date:** 2026-01-28
**Priority:** Critical
**Status:** In Progress

---

## Problem Statement

Users see "Failed to fetch" error when trying to register/login. This is a generic browser error that provides no useful information to users or developers.

---

## Root Cause Analysis

### 1. No Network Error Handling in API Client
**Location:** `frontend/src/api/client.ts` - Lines 149-153

**Problem:**
```typescript
catch (err) {
  if (err instanceof DOMException && err.name === 'AbortError') {
    throw new Error('Request timed out. Please check your connection and try again.');
  }
  throw err;  // ← Raw error thrown with "Failed to fetch" message
}
```

When `fetch()` fails due to:
- Network offline
- Backend unreachable
- CORS preflight failure
- DNS resolution failure
- SSL certificate issues

The browser throws a `TypeError` with message "Failed to fetch" which is not helpful.

**Impact:** Users have no idea what went wrong or how to fix it.

---

### 2. Missing Backend Health Check
**Problem:** Frontend has no way to verify backend is reachable before making requests.

**Impact:** Users get cryptic errors when backend is down instead of a clear message.

---

### 3. CORS Configuration May Be Missing Environment Variables
**Location:** `src/config.py` - Lines 41-47

**Problem:** CORS origins are hardcoded. If environment variable `CORS_ALLOWED_ORIGINS` isn't set in Railway, the defaults may not match the actual frontend URL.

**Current Default:**
```python
cors_allowed_origins: str = "http://localhost:3000,http://localhost:5173,...,https://polymarket-sports-bot.pages.dev"
```

**Potential Issue:** If Cloudflare Pages URL is slightly different (e.g., with subdomain), CORS would block requests.

---

### 4. No Retry Logic for Transient Failures
**Problem:** If the first request fails due to a temporary network issue, there's no automatic retry.

---

### 5. No Offline Detection
**Problem:** App doesn't check if browser is offline before making requests.

---

## Solutions

### Solution 1: Improve Network Error Messages (CRITICAL)
**File:** `frontend/src/api/client.ts`

Add specific error handling for network failures:

```typescript
catch (err) {
  if (err instanceof DOMException && err.name === 'AbortError') {
    throw new Error('Request timed out. Please check your connection and try again.');
  }

  // Handle network errors (Failed to fetch)
  if (err instanceof TypeError && err.message === 'Failed to fetch') {
    // Check if offline
    if (!navigator.onLine) {
      throw new Error('You appear to be offline. Please check your internet connection.');
    }
    // Backend likely down or CORS issue
    throw new Error('Unable to connect to server. Please try again later or contact support if the problem persists.');
  }

  throw err;
}
```

**Status:** TO BE IMPLEMENTED

---

### Solution 2: Add Backend Health Check
**File:** `frontend/src/api/client.ts`

Add a health check method:

```typescript
async checkBackendHealth(): Promise<boolean> {
  try {
    const response = await fetch(`${this.baseUrl.replace('/api/v1', '')}/health`, {
      method: 'GET',
      signal: AbortSignal.timeout(5000),
    });
    return response.ok;
  } catch {
    return false;
  }
}
```

**Status:** TO BE IMPLEMENTED

---

### Solution 3: Add CORS Wildcard for Development
**File:** `src/config.py`

For development, consider allowing all origins or ensure env var is properly set:

```python
# In Railway environment variables, set:
CORS_ALLOWED_ORIGINS=*
# OR for production:
CORS_ALLOWED_ORIGINS=https://polymarket-sports-bot.pages.dev,https://*.pages.dev
```

**Status:** TO BE VERIFIED

---

### Solution 4: Add Retry Logic
**File:** `frontend/src/api/client.ts`

Add automatic retry for transient failures:

```typescript
private async requestWithRetry<T>(
  endpoint: string,
  options: RequestInit = {},
  maxRetries: number = 2
): Promise<T> {
  let lastError: Error | null = null;

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      return await this.request<T>(endpoint, options);
    } catch (err) {
      lastError = err instanceof Error ? err : new Error(String(err));

      // Don't retry on client errors (4xx)
      if (lastError.message.includes('HTTP Error: 4')) {
        throw lastError;
      }

      // Wait before retry (exponential backoff)
      if (attempt < maxRetries) {
        await new Promise(r => setTimeout(r, Math.pow(2, attempt) * 1000));
      }
    }
  }

  throw lastError;
}
```

**Status:** OPTIONAL - May be overkill for MVP

---

### Solution 5: Add Offline Banner
**File:** `frontend/src/App.tsx`

Add an offline detection banner:

```typescript
const [isOffline, setIsOffline] = useState(!navigator.onLine);

useEffect(() => {
  const handleOnline = () => setIsOffline(false);
  const handleOffline = () => setIsOffline(true);

  window.addEventListener('online', handleOnline);
  window.addEventListener('offline', handleOffline);

  return () => {
    window.removeEventListener('online', handleOnline);
    window.removeEventListener('offline', handleOffline);
  };
}, []);

// In render:
{isOffline && (
  <div className="bg-destructive text-destructive-foreground p-2 text-center">
    You are offline. Some features may not work.
  </div>
)}
```

**Status:** OPTIONAL - Nice to have

---

## Implementation Plan

### Phase 1: Critical Fixes (Now)
1. [x] Improve network error messages in API client - DONE
   - Added TypeError handling for "Failed to fetch" errors
   - Added offline detection with `navigator.onLine`
   - User-friendly messages instead of cryptic errors
2. [x] Add health check method to API client - DONE
   - Added `checkHealth()` method
   - Can be used to verify backend connectivity
3. [x] Fixed login method error handling - DONE
   - Same improvements as general request method
4. [ ] Verify CORS configuration in Railway (requires Railway dashboard access)

### Phase 2: Nice to Have (Later)
4. [ ] Add retry logic for transient failures
5. [ ] Add offline detection banner
6. [ ] Add connection status indicator in UI

---

## Testing Checklist

- [ ] Test registration with backend running → Should succeed
- [ ] Test registration with backend down → Should show "Unable to connect to server"
- [ ] Test registration with network offline → Should show "You appear to be offline"
- [ ] Test registration with slow network → Should show timeout message
- [ ] Verify CORS works from pages.dev domain

---

## Environment Variables to Verify in Railway

```
CORS_ALLOWED_ORIGINS=https://polymarket-sports-bot.pages.dev,http://localhost:5173,http://localhost:3000
DATABASE_URL=<your-db-url>
SECRET_KEY=<your-secret>
DEBUG=false
```

---

## Appendix: Common "Failed to Fetch" Causes

| Cause | Detection | User Message |
|-------|-----------|--------------|
| Network offline | `!navigator.onLine` | "You appear to be offline" |
| Backend down | Health check fails | "Server is currently unavailable" |
| CORS blocked | Preflight fails | "Unable to connect to server" |
| DNS failure | Fetch throws TypeError | "Unable to connect to server" |
| SSL error | Fetch throws TypeError | "Unable to connect to server" |
| Request timeout | AbortError | "Request timed out" |
