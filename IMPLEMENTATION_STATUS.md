# Polymarket/Kalshi Bot - Implementation Status & Remaining Work

## Overview
This document tracks what has been implemented vs what still needs work for the client.

---

## COMPLETED WORK (Jan 25, 2026)

### 1. Kalshi Credentials Support
- **Schema**: Updated `WalletConnectRequest` to accept platform, api_key, api_secret
- **CRUD**: Updated `PolymarketAccountCRUD.create()` to store Kalshi credentials
- **Backend**: Updated `/onboarding/wallet/connect` to handle both platforms
- **Frontend**: Updated Onboarding.tsx and Settings.tsx to pass correct credentials

### 2. Team/Side Selection UI
- **Schema**: Added `selected_side` field to `GameSelection` (home/away/both)
- **Frontend**: Added team selection buttons in BotConfig.tsx game cards
- **Frontend**: Selection summary shows which team is selected for each game

### 3. Multi-Sport Selection UI
- **Schema**: Added `additional_games` array to `BotConfigRequest`
- **Frontend**: Changing sports no longer clears selections from other sports
- **Frontend**: Selection badges show sport + team for each selection

---

## CRITICAL ISSUES - MUST FIX BEFORE CLIENT USE

### Issue 1: Bot Creates Wrong Client for Kalshi Users
**Severity**: CRITICAL - Bot will crash for Kalshi users
**Location**: `src/api/routes/bot.py`, lines 39-45

**Problem**:
The `_create_bot_dependencies()` function ALWAYS creates a PolymarketClient, even for Kalshi users. Kalshi users don't have private_key/funder_address, so this will fail.

**Current Code**:
```python
polymarket_client = PolymarketClient(
    private_key=credentials["private_key"],  # Kalshi doesn't have this!
    funder_address=credentials["funder_address"],
    ...
)
```

**Fix Required**:
```python
async def _create_bot_dependencies(db, user_id, credentials: dict):
    platform = credentials.get("platform", "polymarket")

    if platform == "kalshi":
        from src.services.kalshi_client import KalshiClient
        trading_client = KalshiClient(
            api_key=credentials["api_key"],
            private_key=credentials["api_secret"]  # Kalshi uses api_secret as private key
        )
    else:
        trading_client = PolymarketClient(
            private_key=credentials["private_key"],
            funder_address=credentials["funder_address"],
            api_key=credentials.get("api_key"),
            api_secret=credentials.get("api_secret"),
            passphrase=credentials.get("passphrase")
        )

    # ... rest of function, use trading_client instead of polymarket_client
```

---

### Issue 2: selected_side Field Not Used in Bot Logic
**Severity**: CRITICAL - Bot bets on both teams even when user selects one
**Location**: `src/services/bot_runner.py`

**Problem**:
User selects "Patriots" (home team) but bot can still enter positions on "Broncos" (away team) because `selected_side` is never checked.

**Fix Required** - Add validation in `bot_runner.py`:

```python
# In the entry logic (around line 600-700), before placing a trade:
def _should_enter_position(self, market_data, game_config):
    """Check if we should enter based on selected side."""
    selected_side = game_config.get("selected_side", "both")

    if selected_side == "both":
        return True  # Can trade either side

    # Determine which team the market represents
    market_team = self._get_market_team(market_data)

    if selected_side == "home" and market_team != "home":
        return False  # Skip - user only wants home team
    if selected_side == "away" and market_team != "away":
        return False  # Skip - user only wants away team

    return True
```

---

### Issue 3: additional_games Not Processed
**Severity**: CRITICAL - Multi-sport doesn't actually work
**Location**: `src/api/routes/bot.py` and `src/services/bot_runner.py`

**Problem**:
Frontend sends `additional_games` array but backend ignores it. Only the first game is tracked.

**Fix Required**:

1. **In bot.py `/config` endpoint** - Store all games:
```python
@router.post("/config", response_model=BotConfigResponse)
async def save_bot_config(...):
    # Store primary game
    all_games = [request.game.model_dump()]

    # Add additional games
    if request.additional_games:
        for game in request.additional_games:
            all_games.append(game.model_dump())

    _bot_configs[user_id] = {
        "sport": request.sport,
        "games": all_games,  # Store ALL games
        "parameters": request.parameters.model_dump(),
        ...
    }
```

2. **In bot_runner.py** - Track all games:
```python
async def initialize(self, db, user_id):
    config = _bot_configs.get(str(user_id), {})

    # Track ALL games, not just one
    games = config.get("games", [])
    for game_config in games:
        await self._start_tracking_game(
            sport=game_config["sport"],
            game_id=game_config["game_id"],
            selected_side=game_config.get("selected_side", "home")
        )
```

---

### Issue 4: useConnectWallet Hook Signature Mismatch
**Severity**: HIGH - Hook broken, causes TypeScript errors
**Location**: `frontend/src/hooks/useApi.ts`, lines 170-184

**Current Code** (WRONG):
```typescript
export function useConnectWallet() {
  return useMutation({
    mutationFn: ({ privateKey, funderAddress, signatureType }: {
      privateKey: string;
      funderAddress: string;
      signatureType: number;
    }) => apiClient.connectWallet(privateKey, funderAddress, signatureType),
```

**Fix Required**:
```typescript
export function useConnectWallet() {
  return useMutation({
    mutationFn: ({ platform, credentials }: {
      platform: 'kalshi' | 'polymarket';
      credentials: {
        apiKey?: string;
        apiSecret?: string;
        privateKey?: string;
        funderAddress?: string;
      };
    }) => apiClient.connectWallet(platform, credentials),
    onError: (error: Error) => {
      console.error('Failed to connect wallet:', error);
    },
  });
}
```

---

## HIGH PRIORITY ISSUES

### Issue 5: Settings Page Missing Platform Selector
**Severity**: HIGH - Users can't switch platforms
**Location**: `frontend/src/pages/Settings.tsx`

**Problem**:
Platform defaults to 'kalshi' with no UI to change it.

**Fix Required** - Add platform toggle in the Wallet Configuration card:
```tsx
{/* Platform Selection */}
<div className="space-y-2 mb-4">
  <Label>Trading Platform</Label>
  <div className="grid grid-cols-2 gap-3">
    <button
      onClick={() => setWallet(prev => ({ ...prev, platform: 'kalshi' }))}
      className={cn(
        'p-3 rounded-md border text-left',
        wallet.platform === 'kalshi' ? 'bg-primary/10 border-primary' : 'border-border'
      )}
    >
      <span className="font-medium">Kalshi</span>
      <p className="text-xs text-muted-foreground">US-regulated</p>
    </button>
    <button
      onClick={() => setWallet(prev => ({ ...prev, platform: 'polymarket' }))}
      className={cn(
        'p-3 rounded-md border text-left',
        wallet.platform === 'polymarket' ? 'bg-primary/10 border-primary' : 'border-border'
      )}
    >
      <span className="font-medium">Polymarket</span>
      <p className="text-xs text-muted-foreground">Crypto-based</p>
    </button>
  </div>
</div>

{/* Conditionally show fields based on platform */}
{wallet.platform === 'kalshi' ? (
  <>
    <Input label="Kalshi API Key" ... />
    <Input label="Kalshi API Secret" ... />
  </>
) : (
  <>
    <Input label="Polymarket Private Key" ... />
    <Input label="Wallet Address" ... />
    <Input label="API Passphrase" ... />
  </>
)}
```

---

## IMPLEMENTATION CHECKLIST

### Phase 1: Critical Bot Fixes (Required for basic functionality)
- [ ] Fix `_create_bot_dependencies()` to use correct client based on platform
- [ ] Add `selected_side` validation in bot_runner.py entry logic
- [ ] Process `additional_games` array in bot config storage
- [ ] Track multiple games in bot_runner initialization

### Phase 2: Frontend Fixes (Required for proper UX)
- [ ] Fix `useConnectWallet` hook signature in useApi.ts
- [ ] Add platform selector UI in Settings.tsx
- [ ] Conditional rendering of credential fields based on platform

### Phase 3: Testing (Required before client demo)
- [ ] Test Kalshi user flow: onboarding -> credentials -> start bot
- [ ] Test Polymarket user flow: onboarding -> credentials -> start bot
- [ ] Test team selection: select Patriots only, verify bot only trades Patriots
- [ ] Test multi-sport: select NBA + NFL games, verify both tracked
- [ ] Test paper trading mode with all above scenarios

---

## FILES TO MODIFY

| File | Changes Needed |
|------|---------------|
| `src/api/routes/bot.py` | Fix _create_bot_dependencies for Kalshi |
| `src/services/bot_runner.py` | Add selected_side filtering, multi-game support |
| `src/services/trading_engine.py` | Add team validation before entry |
| `frontend/src/hooks/useApi.ts` | Fix useConnectWallet signature |
| `frontend/src/pages/Settings.tsx` | Add platform selector UI |

---

## TESTING COMMANDS

```bash
# Start backend
cd /path/to/project
uvicorn src.main:app --reload --port 8000

# Start frontend
cd frontend
npm run dev

# Run migrations (if DB changes needed)
alembic upgrade head
```

---

## DEPLOYMENT NOTES

The project auto-deploys via GitHub to:
- **Backend**: Railway (runs `alembic upgrade head && uvicorn...`)
- **Frontend**: Vercel or Netlify (auto-builds on push)

After fixing all issues, push to GitHub and both will auto-deploy.

---

## Contact

If issues persist after implementing these fixes, check:
1. Railway logs for backend errors
2. Browser console for frontend errors
3. Network tab for API response errors

Last updated: January 25, 2026
