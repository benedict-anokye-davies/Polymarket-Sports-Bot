# Polymarket Sports Trading Bot - Product Requirements Document

## Project Overview
Automated sports betting bot for Polymarket prediction markets. The bot monitors live sports events, captures pre-game baseline prices, and executes trades when prices hit configured thresholds.

---

## Recent Changes (January 27, 2026)

### Completed Fixes

#### 1. Markets Page - Now Shows Live Games from ESPN
**File**: [frontend/src/pages/Markets.tsx](frontend/src/pages/Markets.tsx)

**Problem**: Markets page was empty because it fetched from `tracked_markets` database which required bot discovery to run first.

**Solution**: Rewrote Markets page to fetch games directly from ESPN API (like BotConfig does), allowing users to see and select games immediately without waiting for bot discovery.

**Features**:
- Fetches live and upcoming games directly from ESPN
- Supports multiple league selection (e.g., NBA + NFL + EPL simultaneously)
- Games display with real-time scores and status
- Category-based filtering (Basketball, Football, Soccer, etc.)
- Search functionality across teams and leagues
- Selected games persist to bot configuration

#### 2. Multi-League Selection Support
**Files**: 
- [frontend/src/pages/Markets.tsx](frontend/src/pages/Markets.tsx)
- [frontend/src/api/client.ts](frontend/src/api/client.ts)
- [src/schemas/bot_config.py](src/schemas/bot_config.py)
- [src/api/routes/bot.py](src/api/routes/bot.py)

**Problem**: Client requested ability to select games from multiple leagues/sports simultaneously.

**Solution**: 
- Markets page dropdown allows selecting multiple leagues at once
- Games from all selected leagues load in parallel
- Bot configuration now stores `additional_games` array alongside primary game
- Backend returns all selected games in response

**API Changes**:
- `BotConfigRequest.game` is now optional
- `BotConfigRequest.parameters` is now optional
- `BotConfigResponse` now includes `additional_games: GameSelection[]`

#### 3. Added Missing CRUD Update Method for Polymarket Account
**File**: [src/db/crud/polymarket_account.py](src/db/crud/polymarket_account.py) (lines 106-136)

**Problem**: Settings page called `PolymarketAccountCRUD.update()` but this method didn't exist.

**Solution**: Added the `update` method to allow credential updates from Settings page.

#### 4. Fixed Auth Store Refresh Token Handling
**File**: [frontend/src/stores/useAuthStore.ts](frontend/src/stores/useAuthStore.ts)

**Problem**: Refresh tokens weren't being stored, causing authentication issues for returning users.

**Solution**:
- `login()`: Now stores `refresh_token` when returned by server (line 47-49)
- `register()`: Now stores `refresh_token` after auto-login (line 81-83)
- `logout()`: Now clears `refresh_token` along with `auth_token` (line 105)
- `checkAuth()`: Now clears `refresh_token` when clearing auth state (lines 117, 127)

#### 5. Updated API Client Login Return Type
**File**: [frontend/src/api/client.ts](frontend/src/api/client.ts) (line 160)

**Problem**: TypeScript didn't recognize `refresh_token` field in login response.

**Solution**: Added `refresh_token?: string` to the login response type.

---

## Known Issues Addressed

| Issue | Status | Solution |
|-------|--------|----------|
| "Save API keys so I don't have to keep onboarding" | Fixed | Credentials ARE saved. Auth flow now properly stores refresh tokens. |
| "Once onboarded, go to dashboard instead of onboarding screen" | Fixed | App.tsx checks `user.onboarding_completed`. With proper refresh token storage, returning users are correctly identified. |
| "Access settings section to change keys" | Fixed | Settings page UI exists. Added missing `update` CRUD method. |
| "Markets page shows nothing" | Fixed | Now fetches from ESPN directly, not bot-discovered markets. |
| "Can't select multiple leagues" | Fixed | Multi-select dropdown in Markets page, parallel fetching. |

---

## Planned Work

### Short-term
1. **Persist Game Selection to Database** - Currently uses in-memory store, need DB persistence
2. **Add Auto-refresh for Live Games** - Periodic polling to update scores/status
3. **Game Selection Sync Across Pages** - Ensure Markets and BotConfig pages stay in sync

### Medium-term
1. **Side Selection UI** - Allow user to choose home/away/both for each game
2. **Per-Game Trading Parameters** - Different thresholds for different games
3. **Market Matching Status** - Show which games have matching Polymarket markets

### Long-term
1. **Real-time WebSocket Updates** - Live price updates from Polymarket
2. **Advanced Analytics Dashboard** - Historical performance by sport/league
3. **Auto-Discovery Mode** - Automatically select high-value games based on criteria

---

## API Reference

### Bot Configuration Endpoints

#### GET /api/v1/bot/config
Returns current bot configuration including selected games.

**Response**:
```json
{
  "is_running": false,
  "sport": "nba",
  "game": {
    "game_id": "401584722",
    "sport": "nba",
    "home_team": "Lakers",
    "away_team": "Celtics",
    "start_time": "Jan 28, 7:00 PM EST",
    "selected_side": "home"
  },
  "additional_games": [
    {
      "game_id": "401584723",
      "sport": "nfl",
      "home_team": "Chiefs",
      "away_team": "Bills",
      "start_time": "Jan 28, 8:00 PM EST",
      "selected_side": "home"
    }
  ],
  "parameters": {
    "probability_drop": 15,
    "min_volume": 50000,
    "position_size": 100,
    "take_profit": 25,
    "stop_loss": 15,
    "latest_entry_time": 10,
    "latest_exit_time": 2
  },
  "simulation_mode": true,
  "last_updated": "2026-01-27T14:30:00Z"
}
```

#### POST /api/v1/bot/config
Saves bot configuration with game selections.

**Request**:
```json
{
  "sport": "nba",
  "game": {
    "game_id": "401584722",
    "sport": "nba",
    "home_team": "Lakers",
    "away_team": "Celtics",
    "start_time": "Jan 28, 7:00 PM EST",
    "selected_side": "home"
  },
  "additional_games": [],
  "parameters": {
    "probability_drop": 15,
    "min_volume": 50000,
    "position_size": 100,
    "take_profit": 25,
    "stop_loss": 15,
    "latest_entry_time": 10,
    "latest_exit_time": 2
  },
  "simulation_mode": true
}
```

#### GET /api/v1/bot/live-games/{sport}
Returns live and upcoming games from ESPN for a specific sport/league.

**Supported Sports**: nba, nfl, mlb, nhl, ncaab, ncaaf, epl, laliga, bundesliga, seriea, ligue1, mls, ucl, and 100+ more.

---

## Deployment

### Cloudflare (Frontend)
- Auto-deploys on push to `master` branch
- Domain: Configured in Cloudflare dashboard

### Railway (Backend)
- Auto-deploys on push to `master` branch
- Environment variables configured in Railway dashboard

### Git Commands
```bash
# Push changes to trigger deployment
git add .
git commit -m "Markets page: ESPN integration, multi-league selection"
git push origin master
```

---

## Technical Stack

| Component | Technology |
|-----------|------------|
| Backend | Python 3.11+, FastAPI, SQLAlchemy 2.0 |
| Frontend | React, TypeScript, Vite, Tailwind CSS |
| Database | PostgreSQL (Supabase) |
| Auth | JWT tokens with refresh |
| Data Sources | ESPN API (games), Polymarket CLOB API (markets/trading) |
| Deployment | Railway (backend), Cloudflare Pages (frontend) |
