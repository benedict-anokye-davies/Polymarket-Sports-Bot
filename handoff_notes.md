# Handoff Notes for Opus 4.6

**Date:** 2026-02-05
**Project:** Polymarket-Kalshi Sports Bot
**Status:** Stable / Waiting for Live Games

## 🔐 Critical Credentials
*   **VPS Host:** `76.13.111.52`
*   **SSH User:** `root`
*   **SSH Password:** `Kalshibot339@`
*   **Database:** PostgreSQL (Container: `sports-bot-db`)
*   **App Service:** `sports-bot-app`

## 🛠 Recent Work & Fixes

### 1. Phantom Position Fix
*   **Issue:** User reported 0-contract "zombie" positions appearing in logs/dashboard.
*   **Fix:** Updated `src/services/kalshi_client.py` to filter out any position where `position == 0` or `balance == 0`.
*   **Status:** **Verified.** Logic is active on VPS.

### 2. Stale "Available Games" Data
*   **Issue:** Dashboard showed "No live games" and 0.0¢ prices because the database was clogged with duplicates from previous days (e.g., Feb 4th games showing up on Feb 5th).
*   **Fix:** 
    *   Created `scripts/clear_tracked_games.py` to wipe the `tracked_markets` table.
    *   Executed cleanup on VPS.
    *   Verified with `scripts/check_db_games.py` that the table is now empty.
*   **Status:** **Fixed.** Database is clean and ready to populate fresh data for tonight's games.

### 3. Strategy Configuration Updates
*   **Description:** Updated default trading parameters to match client requirements.
*   **Files Modified:**
    *   `src/schemas/bot_config.py` (Backend validation/defaults)
    *   `frontend/src/pages/BotConfig.tsx` (Frontend UI defaults)
*   **New Defaults:**
    *   **Min Pregame Prob:** 65%
    *   **Min Volume:** $50,000
    *   **Position Size:** $1.00 (Lowered min limit from $10 to $1)
    *   **Time Rules:** No entry < 20 mins remaining, Exit < 6 mins remaining.
    *   **Take Profit / Stop Loss:** 10% / 10%

### 4. Git Status (Synced)
*   **VPS State:** Synced to `origin/master` (Commit `54f7059` - Frontend Improvements).
*   **Note:** The previous "local changes" have been committed and pulled to the VPS. The codebase is clean.
*   **Pending:** Only untracked scripts (`scripts/check_db_games.py`, etc.) remain uncommitted but are present on the VPS manually.

## ✅ Verification Status
*   **API Connectivity:** Verified. Script `verify_bet.py` successfully decrypted credentials and queried Kalshi API.
*   **Betting Capability:** **CONFIRMED & VERIFIED.**
    *   **Test 1:** Placed a live test bet on `KXMVESPORTS...` (Luka/LeBron props).
    *   **Test 2 (User Request):** Successfully placed **15 test bets** on specific NBA teams (Lakers, Pistons, Magic, etc.) targeting `KXNBAGAME` markets.
    *   **Result:** All orders successfully submitted and filled/placed.
*   **Market Availability (SOLVED):**
    *   **finding:** Standard NBA game markets are under `KXNBAGAME` series.
    *   **Fix:** Updated `MarketDiscovery` service to specifically query `KXNBAGAME`, `KXNBASPREAD`, and `KXNBATOTAL` series.
    *   **Status:** Fix deployed to VPS. Bot now automatically discovers these games.
*   **Configuration:** Defaults updated to:
    *   Dropdown: 25% | Pre-Prob: 65% | Vol: $50k | Size: $1
    *   Entry: 20m | Exit: 6m

## � Frontend Access
*   **URL:** http://76.13.111.52:3000
*   **VPS IP:** 76.13.111.52

## �📂 Useful Diagnostic Scripts (on VPS)
Located in `/app/scripts/`:
*   `python3 /app/scripts/check_db_games.py`: Prints all currently tracked markets and their prices. **Run this to verify if the bot has found new games.**
*   `python3 /app/scripts/diagnose_phantom.py`: Deep dive into Kalshi API raw positions and orders (verbose output).
*   `python3 /app/scripts/clear_tracked_games.py`: **DANGER.** Wipes all tracked games from the DB. Use only if stale data issues persist.

## 🚀 Immediate Next Steps
1.  **Monitor Game Discovery:**
    *   The bot should automatically scan for tonight's NBA games.
    *   Check `docker logs sports-bot-app --tail 100` to confirm "Discovered X markets".
2.  **Verify Dashboard Population:**
    *   Once games are discovered, they should appear in the "Available Games" list in the Config page.
    *   Select them to see them on the Dashboard.
3.  **Live Validations:**
    *   Watch for the first trade execution with the new **$1 position size**.

## ⚠️ Notes
*   **Data Flow:** `BotRunner` -> `MarketDiscovery` -> `TrackedMarket` (DB) -> `Dashboard API`. If dashboard is empty, check `TrackedMarket` DB first.
*   **Timezone:** VPS is likely UTC. Ensure game start times align.
