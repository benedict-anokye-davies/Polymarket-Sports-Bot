# Product Requirements Document (PRD)
## Polymarket-Kalshi Sports Trading Bot

### Overview
A sports betting automation bot that monitors live sports games via ESPN API and executes trades on Polymarket/Kalshi prediction markets when favorable opportunities arise.

---

## Completed Work

### 1. Multi-League Selection Support
**Status:** Completed

- Users can now select multiple leagues within a sport category to bet on
- Categories include: Basketball, Football, Baseball, Hockey, Soccer, Tennis, Golf, MMA
- Each category contains multiple leagues (e.g., Basketball includes NBA, WNBA, NCAA Men's, NCAA Women's, EuroLeague, etc.)
- Settings page allows bulk configuration of multiple leagues with uniform parameters

### 2. Markets Page Overhaul
**Status:** Completed

- Completely rewrote Markets.tsx to fetch live games from ESPN API
- Previously fetched from database which required bot to be running for market discovery
- Now fetches directly from ESPN via `/bot/live-games/{sport}` endpoint
- Features:
  - Category dropdown to select sport type
  - Multi-league selection with checkboxes
  - Real-time game data display
  - Status badges (Live, Upcoming, Final)
  - Team logos and scores
  - Automatic refresh every 30 seconds for live games

### 3. Credential Persistence Fix
**Status:** Completed

- Added missing `update` method to `PolymarketAccountCRUD` class
- Fixed auth store to properly store and clear refresh tokens
- Updated apiClient login return type to include refresh_token
- Credentials now persist correctly across sessions

### 4. ESPN Service Enhancements
**Status:** Completed

- Fixed game filtering to show all games (not just Top 25 for college basketball)
- Fixed MLS-only bug for soccer - now supports all configured leagues
- Added comprehensive league support across all sports

### 5. Bulk League Configuration API
**Status:** Completed

- Added `POST /settings/leagues/bulk` endpoint for configuring multiple leagues at once
- Added `POST /settings/leagues/enable` endpoint for quick enable/disable of leagues
- Added `GET /settings/leagues/status` endpoint to view all leagues and their config status
- Schemas: `BulkLeagueConfigRequest`, `BulkLeagueConfigResponse`, `LeagueEnableRequest`, `LeagueEnableResponse`, `UserLeagueStatus`

---

## Planned Work

### 1. Real Market Integration
**Priority:** High

- Connect ESPN games to actual Polymarket/Kalshi markets
- Implement market matching algorithm to pair ESPN games with prediction markets
- Add market price tracking and execution

### 2. Position Management UI
**Priority:** High

- Display active positions on dashboard
- Show P&L tracking per position
- Add manual position close capability

### 3. Trade Execution Engine
**Priority:** High

- Implement automated trade execution based on configured thresholds
- Entry threshold drop detection
- Take profit and stop loss automation
- Position sizing per sport/league configuration

### 4. Notifications System
**Priority:** Medium

- Discord webhook integration for trade alerts
- Email notifications for important events
- In-app notification center

### 5. Analytics Dashboard
**Priority:** Medium

- Historical trade performance
- Win/loss statistics by sport/league
- ROI tracking

### 6. Paper Trading Mode
**Priority:** Medium

- Simulate trades without real money
- Track hypothetical P&L
- Validate strategy before going live

---

## Technical Architecture

### Backend
- **Framework:** FastAPI (Python 3.11+)
- **Database:** PostgreSQL with async SQLAlchemy
- **Authentication:** JWT with refresh token rotation
- **External APIs:** ESPN, Polymarket, Kalshi

### Frontend
- **Framework:** React 18 with TypeScript
- **Build Tool:** Vite
- **State Management:** Zustand with localStorage persistence
- **UI:** Tailwind CSS with custom components

### Deployment
- **Frontend:** Cloudflare Pages
- **Backend:** Railway
- **Database:** Railway PostgreSQL

---

## API Endpoints

### Authentication
- `POST /auth/register` - User registration
- `POST /auth/login` - User login
- `POST /auth/refresh` - Refresh access token
- `GET /auth/me` - Get current user

### Settings
- `GET /settings/global` - Get global bot settings
- `PUT /settings/global` - Update global settings
- `GET /settings/sports` - Get all sport configs
- `POST /settings/sports` - Create sport config
- `PUT /settings/sports/{sport}` - Update sport config
- `POST /settings/leagues/bulk` - Bulk configure leagues
- `POST /settings/leagues/enable` - Enable/disable leagues
- `GET /settings/leagues/status` - Get all leagues status

### Bot Control
- `GET /bot/live-games/{sport}` - Get live games from ESPN
- `POST /bot/start` - Start the trading bot
- `POST /bot/stop` - Stop the trading bot
- `GET /bot/status` - Get bot status

### Trading
- `GET /trading/positions` - Get active positions
- `GET /trading/history` - Get trade history

---

## Changelog

### 2026-01-28
- Rewrote Markets.tsx to fetch from ESPN API
- Added multi-league selection support
- Fixed credential persistence issues
- Created PRD documentation

### Previous Updates
- Added bulk league configuration support
- Expanded sports coverage with comprehensive league selection
- Fixed ESPN service tests for new league structure
