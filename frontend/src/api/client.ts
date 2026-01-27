/**
 * API Client for Kalshi Trading Bot Backend
 * Handles all HTTP requests with authentication and error handling
 */

const API_BASE_URL = import.meta.env.VITE_API_URL?.trim() || 'https://polymarket-sports-bot-production.up.railway.app/api/v1';

const DEFAULT_TIMEOUT_MS = 30000;

interface ApiError {
  detail: string;
  status: number;
}

class ApiClient {
  private baseUrl: string;
  private isRefreshing = false;
  private refreshPromise: Promise<boolean> | null = null;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  private getToken(): string | null {
    return localStorage.getItem('auth_token');
  }

  private getRefreshToken(): string | null {
    return localStorage.getItem('refresh_token');
  }

  private setTokens(accessToken: string, refreshToken?: string): void {
    localStorage.setItem('auth_token', accessToken);
    if (refreshToken) {
      localStorage.setItem('refresh_token', refreshToken);
    }
  }

  private clearTokens(): void {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('refresh_token');
  }

  /**
   * Attempt to refresh the access token using the refresh token.
   * Uses a singleton pattern to prevent multiple concurrent refresh attempts.
   */
  private async attemptTokenRefresh(): Promise<boolean> {
    // If already refreshing, wait for that to complete
    if (this.isRefreshing && this.refreshPromise) {
      return this.refreshPromise;
    }

    const refreshToken = this.getRefreshToken();
    if (!refreshToken) {
      return false;
    }

    this.isRefreshing = true;
    this.refreshPromise = this.doTokenRefresh(refreshToken);

    try {
      return await this.refreshPromise;
    } finally {
      this.isRefreshing = false;
      this.refreshPromise = null;
    }
  }

  private async doTokenRefresh(refreshToken: string): Promise<boolean> {
    try {
      const response = await fetch(`${this.baseUrl}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });

      if (!response.ok) {
        return false;
      }

      const data = await response.json();
      this.setTokens(data.access_token, data.refresh_token);
      return true;
    } catch {
      return false;
    }
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {},
    timeoutMs: number = DEFAULT_TIMEOUT_MS,
    isRetry: boolean = false
  ): Promise<T> {
    const token = this.getToken();

    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    };

    if (token) {
      (headers as Record<string, string>)['Authorization'] = `Bearer ${token}`;
    }

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

    try {
      const response = await fetch(`${this.baseUrl}${endpoint}`, {
        ...options,
        headers,
        signal: controller.signal,
      });

      if (!response.ok) {
        // On 401, attempt token refresh (but only once)
        if (response.status === 401 && !isRetry) {
          const refreshed = await this.attemptTokenRefresh();
          if (refreshed) {
            // Retry the original request with the new token
            return this.request<T>(endpoint, options, timeoutMs, true);
          }

          // Refresh failed, clear tokens and redirect to login
          this.clearTokens();
          window.location.href = '/login';
          throw new Error('Unauthorized');
        }

        if (response.status === 401) {
          this.clearTokens();
          window.location.href = '/login';
          throw new Error('Unauthorized');
        }

        const error: ApiError = await response.json().catch(() => ({
          detail: 'An unexpected error occurred',
          status: response.status,
        }));

        throw new Error(error.detail || `HTTP Error: ${response.status}`);
      }

      // Handle empty responses
      const text = await response.text();
      return text ? JSON.parse(text) : ({} as T);
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        throw new Error('Request timed out. Please check your connection and try again.');
      }
      throw err;
    } finally {
      clearTimeout(timeoutId);
    }
  }

  // Auth endpoints
  async login(email: string, password: string): Promise<{ access_token: string; token_type: string }> {
    const formData = new URLSearchParams();
    formData.append('username', email);
    formData.append('password', password);

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), DEFAULT_TIMEOUT_MS);

    try {
      const response = await fetch(`${this.baseUrl}/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: formData,
        signal: controller.signal,
      });

      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Login failed' }));
        throw new Error(error.detail || 'Login failed');
      }

      return response.json();
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        throw new Error('Login request timed out. Please check your connection and try again.');
      }
      throw err;
    } finally {
      clearTimeout(timeoutId);
    }
  }

  async register(username: string, email: string, password: string): Promise<{ id: string; email: string }> {
    return this.request('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ username, email, password }),
    });
  }

  async getCurrentUser(): Promise<{ id: string; username: string; email: string; onboarding_completed: boolean; onboarding_step: number }> {
    return this.request('/auth/me');
  }

  // Dashboard endpoints
  async getDashboardStats(): Promise<DashboardStats> {
    return this.request('/dashboard/stats');
  }

  // Bot endpoints
  async getBotStatus(): Promise<BotStatus> {
    return this.request('/bot/status');
  }

  async startBot(): Promise<{ message: string }> {
    return this.request('/bot/start', { method: 'POST' });
  }

  async stopBot(): Promise<{ message: string }> {
    return this.request('/bot/stop', { method: 'POST' });
  }

  // ==========================================================================
  // Bot Configuration Endpoints (New)
  // ==========================================================================

  /**
   * Get current bot configuration including trading parameters
   */
  async getBotConfig(): Promise<BotConfigResponse> {
    return this.request('/bot/config');
  }

  /**
   * Save bot configuration with trading parameters
   * Does not start the bot - use startBot() for that
   */
  async saveBotConfig(config: BotConfigRequest): Promise<BotConfigResponse> {
    return this.request('/bot/config', {
      method: 'POST',
      body: JSON.stringify(config),
    });
  }

  /**
   * Get detailed bot status including positions and P&L
   */
  async getDetailedBotStatus(): Promise<DetailedBotStatus> {
    return this.request('/bot/status/detailed');
  }

  /**
   * Place a manual order on Kalshi or Polymarket
   */
  async placeManualOrder(order: PlaceOrderRequest): Promise<PlaceOrderResponse> {
    return this.request('/bot/order', {
      method: 'POST',
      body: JSON.stringify(order),
    });
  }

  /**
   * Get available sports markets from Kalshi or Polymarket
   */
  async getSportsMarkets(platform: 'kalshi' | 'polymarket', sport: string): Promise<SportsMarket[]> {
    return this.request(`/bot/markets/${platform}/${sport}`);
  }

  /**
   * Get live games from ESPN for a specific sport
   * Returns real-time game data including scores, periods, times
   */
  async getLiveGames(sport: string): Promise<ESPNGame[]> {
    return this.request(`/bot/live-games/${sport}`);
  }

  // Trading endpoints
  async getMarkets(sport?: string): Promise<Market[]> {
    const params = sport ? `?sport=${sport}` : '';
    return this.request(`/trading/markets${params}`);
  }

  async trackMarket(conditionId: string): Promise<GameSelectionResponse> {
    return this.request(`/trading/markets/${conditionId}/track`, { method: 'POST' });
  }

  async untrackMarket(conditionId: string): Promise<GameSelectionResponse> {
    return this.request(`/trading/markets/${conditionId}/track`, { method: 'DELETE' });
  }

  async getPositions(status?: 'open' | 'closed'): Promise<Position[]> {
    const params = status ? `?status=${status}` : '';
    return this.request(`/trading/positions${params}`);
  }

  async closePosition(positionId: string): Promise<{ message: string }> {
    return this.request(`/trading/positions/${positionId}/close`, { method: 'POST' });
  }

  // ==========================================================================
  // Game Selection Endpoints
  // ==========================================================================

  /**
   * Get all games organized by selection status
   */
  async getAllGames(sport?: string): Promise<GameListResponse> {
    const params = sport ? `?sport=${sport}` : '';
    return this.request(`/trading/games${params}`);
  }

  /**
   * Get only games selected for trading
   */
  async getSelectedGames(sport?: string): Promise<AvailableGame[]> {
    const params = sport ? `?sport=${sport}` : '';
    return this.request(`/trading/games/selected${params}`);
  }

  /**
   * Get games available but not selected for trading
   */
  async getAvailableGames(sport?: string): Promise<AvailableGame[]> {
    const params = sport ? `?sport=${sport}` : '';
    return this.request(`/trading/games/available${params}`);
  }

  /**
   * Select a specific game for trading
   */
  async selectGame(marketId: string): Promise<GameSelectionResponse> {
    return this.request(`/trading/games/${marketId}/select`, { method: 'POST' });
  }

  /**
   * Remove a game from trading selection
   */
  async unselectGame(marketId: string): Promise<GameSelectionResponse> {
    return this.request(`/trading/games/${marketId}/select`, { method: 'DELETE' });
  }

  /**
   * Select multiple games at once
   */
  async bulkSelectGames(marketIds: string[]): Promise<BulkGameSelectionResponse> {
    return this.request('/trading/games/select/bulk', {
      method: 'POST',
      body: JSON.stringify({ market_ids: marketIds }),
    });
  }

  /**
   * Remove multiple games from selection at once
   */
  async bulkUnselectGames(marketIds: string[]): Promise<BulkGameSelectionResponse> {
    return this.request('/trading/games/select/bulk', {
      method: 'DELETE',
      body: JSON.stringify({ market_ids: marketIds }),
    });
  }

  /**
   * Select all games for a specific sport
   */
  async selectAllGamesForSport(sport: string): Promise<BulkGameSelectionResponse> {
    return this.request(`/trading/games/select/sport/${sport}`, { method: 'POST' });
  }

  /**
   * Remove all games for a sport from selection
   */
  async unselectAllGamesForSport(sport: string): Promise<BulkGameSelectionResponse> {
    return this.request(`/trading/games/select/sport/${sport}`, { method: 'DELETE' });
  }

  // Sport Config endpoints
  async getSportConfigs(): Promise<SportConfigResponse[]> {
    return this.request('/settings/sports');
  }

  async getSportConfig(sport: string): Promise<SportConfigResponse> {
    return this.request(`/settings/sports/${sport}`);
  }

  async updateSportConfig(sport: string, config: SportConfigUpdate): Promise<SportConfigResponse> {
    return this.request(`/settings/sports/${sport}`, {
      method: 'PUT',
      body: JSON.stringify(config),
    });
  }

  async createSportConfig(config: SportConfigCreate): Promise<SportConfigResponse> {
    return this.request('/settings/sports', {
      method: 'POST',
      body: JSON.stringify(config),
    });
  }

  // ==========================================================================
  // League Selection Endpoints
  // ==========================================================================

  /**
   * Get all available leagues with display names
   */
  async getAvailableLeagues(): Promise<LeagueInfo[]> {
    return this.request('/bot/leagues');
  }

  /**
   * Get all sport categories with their leagues
   */
  async getSportCategories(): Promise<SportCategory[]> {
    return this.request('/bot/categories');
  }

  /**
   * Get leagues for a specific category
   */
  async getLeaguesByCategory(category: string): Promise<LeagueInfo[]> {
    return this.request(`/bot/categories/${category}/leagues`);
  }

  /**
   * Get soccer leagues only
   */
  async getSoccerLeagues(): Promise<LeagueInfo[]> {
    return this.request('/bot/soccer-leagues');
  }

  /**
   * Get user's league configuration status
   */
  async getUserLeagueStatus(): Promise<UserLeagueStatus[]> {
    return this.request('/settings/leagues/status');
  }

  /**
   * Bulk configure multiple leagues with same settings
   */
  async bulkConfigureLeagues(config: BulkLeagueConfig): Promise<BulkLeagueConfigResponse> {
    return this.request('/settings/leagues/bulk', {
      method: 'POST',
      body: JSON.stringify(config),
    });
  }

  /**
   * Enable or disable multiple leagues at once
   */
  async bulkEnableLeagues(leagues: string[], enabled: boolean): Promise<LeagueEnableResponse> {
    return this.request('/settings/leagues/enable', {
      method: 'POST',
      body: JSON.stringify({ leagues, enabled }),
    });
  }

  /**
   * Delete a league configuration
   */
  async deleteLeagueConfig(league: string): Promise<{ message: string }> {
    return this.request(`/settings/leagues/${league}`, {
      method: 'DELETE',
    });
  }

  // Global Settings endpoints
  async getGlobalSettings(): Promise<GlobalSettingsResponse> {
    return this.request('/settings/global');
  }

  async updateGlobalSettings(settings: GlobalSettingsUpdate): Promise<GlobalSettingsResponse> {
    return this.request('/settings/global', {
      method: 'PUT',
      body: JSON.stringify(settings),
    });
  }

  // Discord webhook test
  async testDiscordWebhook(): Promise<{ message: string }> {
    return this.request('/settings/discord/test', { method: 'POST' });
  }

  // Wallet/Credential Status endpoints
  async getWalletStatus(): Promise<WalletStatusResponse> {
    return this.request('/settings/wallet');
  }

  async updateWalletCredentials(credentials: WalletUpdateRequest): Promise<WalletStatusResponse> {
    return this.request('/settings/wallet', {
      method: 'PUT',
      body: JSON.stringify(credentials),
    });
  }

  // Session Management endpoints (REQ-SEC-003)
  async getActiveSessions(): Promise<SessionInfo[]> {
    return this.request('/auth/sessions');
  }

  async revokeSession(sessionId: string): Promise<{ message: string }> {
    return this.request(`/auth/sessions/${sessionId}`, {
      method: 'DELETE',
    });
  }

  async logoutAllDevices(): Promise<{ message: string }> {
    const refreshToken = localStorage.getItem('refresh_token');
    return this.request('/auth/logout', {
      method: 'POST',
      body: JSON.stringify({
        logout_all_devices: true,
        refresh_token: refreshToken,
      }),
    });
  }

  // Legacy Settings endpoints (for backwards compatibility)
  async getSettings(): Promise<Settings> {
    return this.request('/settings');
  }

  async updateSettings(settings: Partial<Settings>): Promise<Settings> {
    return this.request('/settings', {
      method: 'PUT',
      body: JSON.stringify(settings),
    });
  }

  async testWalletConnection(privateKey: string, funderAddress: string): Promise<{ success: boolean; balance?: number }> {
    return this.request('/settings/wallet/test', {
      method: 'POST',
      body: JSON.stringify({ private_key: privateKey, funder_address: funderAddress }),
    });
  }

  // Onboarding endpoints
  async getOnboardingStatus(): Promise<OnboardingStatus> {
    return this.request('/onboarding/status');
  }

  async completeOnboardingStep(step: number, data?: Record<string, unknown>): Promise<{ message: string }> {
    return this.request(`/onboarding/step/${step}/complete`, {
      method: 'POST',
      body: JSON.stringify(data || {}),
    });
  }

  async connectWallet(
    platform: 'kalshi' | 'polymarket',
    credentials: {
      apiKey?: string;
      apiSecret?: string;
      privateKey?: string;
      funderAddress?: string;
    }
  ): Promise<{ message: string }> {
    return this.request('/onboarding/wallet/connect', {
      method: 'POST',
      body: JSON.stringify({
        platform,
        api_key: credentials.apiKey,
        api_secret: credentials.apiSecret,
        private_key: credentials.privateKey,
        funder_address: credentials.funderAddress,
      }),
    });
  }

  async skipOnboarding(): Promise<{ message: string }> {
    return this.request('/onboarding/skip', {
      method: 'POST',
    });
  }

  // Logs endpoints
  async getLogs(level?: string, page: number = 1, limit: number = 50): Promise<PaginatedLogs> {
    const params = new URLSearchParams();
    if (level && level !== 'all') params.append('level', level);
    params.append('page', page.toString());
    params.append('limit', limit.toString());
    return this.request(`/logs?${params.toString()}`);
  }

  // Market Configuration endpoints (per-market overrides)
  async getMarketConfigs(sport?: string, enabledOnly: boolean = false): Promise<MarketConfig[]> {
    const params = new URLSearchParams();
    if (sport) params.append('sport', sport);
    if (enabledOnly) params.append('enabled_only', 'true');
    return this.request(`/market-configs?${params.toString()}`);
  }

  async getMarketConfig(configId: string): Promise<MarketConfigWithDefaults> {
    return this.request(`/market-configs/${configId}`);
  }

  async getMarketConfigByCondition(conditionId: string): Promise<MarketConfig | null> {
    return this.request(`/market-configs/by-market/${conditionId}`);
  }

  async createMarketConfig(config: MarketConfigCreate): Promise<MarketConfig> {
    return this.request('/market-configs', {
      method: 'POST',
      body: JSON.stringify(config),
    });
  }

  async updateMarketConfig(configId: string, config: MarketConfigUpdate): Promise<MarketConfig> {
    return this.request(`/market-configs/${configId}`, {
      method: 'PUT',
      body: JSON.stringify(config),
    });
  }

  async upsertMarketConfig(conditionId: string, config: MarketConfigUpdate): Promise<MarketConfig> {
    return this.request(`/market-configs/by-market/${conditionId}`, {
      method: 'PUT',
      body: JSON.stringify(config),
    });
  }

  async deleteMarketConfig(configId: string): Promise<void> {
    return this.request(`/market-configs/${configId}`, { method: 'DELETE' });
  }

  async deleteMarketConfigByCondition(conditionId: string): Promise<void> {
    return this.request(`/market-configs/by-market/${conditionId}`, { method: 'DELETE' });
  }

  async toggleMarketConfig(configId: string): Promise<MarketConfig> {
    return this.request(`/market-configs/${configId}/toggle`, { method: 'POST' });
  }

  // SSE Stream
  createSSEConnection(): EventSource {
    const token = this.getToken();
    const url = `${this.baseUrl}/dashboard/stream${token ? `?token=${token}` : ''}`;
    return new EventSource(url);
  }
}

// Types
export interface DashboardStats {
  balance_usdc: number;
  open_positions_count: number;
  open_positions_value: number;
  total_pnl_today: number;
  total_pnl_all_time: number;
  win_rate: number;
  active_markets_count: number;
  bot_status: 'running' | 'stopped';
  open_positions: PositionSummary[];
  recent_activity: ActivityLog[];
}

// Sport Config Types (matches backend schema)
export interface SportConfigResponse {
  id: string;
  sport: string;
  enabled: boolean;
  entry_threshold_drop: number;
  entry_threshold_absolute: number;
  take_profit_pct: number;
  stop_loss_pct: number;
  position_size_usdc: number;
  max_positions_per_game: number;
  max_total_positions: number;
  min_time_remaining_seconds: number;
  exit_time_remaining_seconds: number | null;
  min_volume_threshold: number | null;
  max_daily_loss_usdc: number | null;
  max_exposure_usdc: number | null;
  priority: number;
  trading_hours_start: string | null;
  trading_hours_end: string | null;
  updated_at: string;
}

export interface SportConfigUpdate {
  enabled?: boolean;
  entry_threshold_drop?: number;
  entry_threshold_absolute?: number;
  take_profit_pct?: number;
  stop_loss_pct?: number;
  position_size_usdc?: number;
  max_positions_per_game?: number;
  max_total_positions?: number;
  min_time_remaining_seconds?: number;
  exit_time_remaining_seconds?: number;
  min_volume_threshold?: number;
  max_daily_loss_usdc?: number;
  max_exposure_usdc?: number;
  priority?: number;
  trading_hours_start?: string;
  trading_hours_end?: string;
}

export interface SportConfigCreate {
  sport: string;
  enabled?: boolean;
  entry_threshold_drop?: number;
  entry_threshold_absolute?: number;
  take_profit_pct?: number;
  stop_loss_pct?: number;
  position_size_usdc?: number;
  max_positions_per_game?: number;
  max_total_positions?: number;
  min_time_remaining_seconds?: number;
  exit_time_remaining_seconds?: number;
  min_volume_threshold?: number;
  max_daily_loss_usdc?: number;
  max_exposure_usdc?: number;
  priority?: number;
}

// Global Settings Types (matches backend schema)
export interface GlobalSettingsResponse {
  id: string;
  bot_enabled: boolean;
  max_daily_loss_usdc: number;
  max_portfolio_exposure_usdc: number;
  discord_webhook_url: string | null;
  discord_alerts_enabled: boolean;
  poll_interval_seconds: number;
  updated_at: string;
  // Balance Guardian fields
  min_balance_threshold: number | null;
  kill_switch_active: boolean;
  kill_switch_activated_at: string | null;
  kill_switch_reason: string | null;
  current_losing_streak: number;
  max_losing_streak: number;
  streak_reduction_pct: number;
}

export interface GlobalSettingsUpdate {
  bot_enabled?: boolean;
  max_daily_loss_usdc?: number;
  max_portfolio_exposure_usdc?: number;
  discord_webhook_url?: string | null;
  discord_alerts_enabled?: boolean;
  poll_interval_seconds?: number;
  // Balance Guardian fields
  min_balance_threshold?: number | null;
  kill_switch_active?: boolean;
  current_losing_streak?: number;
  max_losing_streak?: number;
  streak_reduction_pct?: number;
}

// Wallet/Credential Status Types
export interface WalletStatusResponse {
  is_connected: boolean;
  platform: 'kalshi' | 'polymarket' | null;
  masked_identifier: string | null;
  last_tested_at: string | null;
  connection_error: string | null;
}

export interface WalletUpdateRequest {
  platform: 'kalshi' | 'polymarket';
  // Kalshi credentials
  api_key?: string;
  api_secret?: string;
  // Polymarket credentials
  private_key?: string;
  funder_address?: string;
}

// Session Management Types (REQ-SEC-003)
export interface SessionInfo {
  id: string;
  device_info: string | null;
  ip_address: string | null;
  created_at: string;
  last_used_at: string | null;
  expires_at: string;
}

export interface PositionSummary {
  id: string;
  token_id: string;
  side: string;
  team: string | null;
  entry_price: number;
  current_price: number | null;
  unrealized_pnl: number | null;
  size: number;
  opened_at: string;
}

export interface ActivityLog {
  id: string;
  level: string;
  category: string;
  message: string;
  created_at: string;
}

export interface BotStatus {
  bot_enabled: boolean;
  tracked_markets: number;
  daily_pnl: number;
  trades_today: number;
}

export interface Market {
  id: string;
  condition_id: string;
  token_id_yes: string;
  token_id_no: string;
  question: string;
  sport: string;
  home_team: string;
  away_team: string;
  home_abbrev?: string;
  away_abbrev?: string;
  game_start_time?: string;
  baseline_price_yes: number;
  current_price_yes: number;
  is_live: boolean;
  is_finished: boolean;
  is_tracked: boolean;
  is_user_selected: boolean;
  match_confidence?: number;
}

export interface Position {
  id: string;
  condition_id: string;
  token_id: string;
  side: 'YES' | 'NO';
  team: string;
  entry_price: number;
  entry_size: number;
  entry_cost_usdc: number;
  current_price?: number;
  unrealized_pnl?: number;
  realized_pnl_usdc?: number;
  status: 'open' | 'closed';
  opened_at: string;
  closed_at?: string;
}

export interface Settings {
  wallet_connected: boolean;
  funder_address?: string;
  sport_configs: SportConfig[];
  risk_settings: RiskSettings;
  discord_webhook?: string;
  notifications: NotificationSettings;
}

export interface SportConfig {
  sport: string;
  enabled: boolean;
  entry_threshold_pct: number;
  absolute_entry_price: number;
  take_profit_pct: number;
  stop_loss_pct: number;
  max_position_size: number;
}

export interface RiskSettings {
  max_daily_loss: number;
  max_exposure: number;
  default_position_size: number;
  max_concurrent_positions: number;
  emergency_stop: boolean;
}

export interface NotificationSettings {
  trade_executed: boolean;
  position_closed: boolean;
  error_alerts: boolean;
}

export interface OnboardingStatus {
  current_step: number;
  total_steps: number;
  completed_steps: number[];
  can_proceed: boolean;
  wallet_connected: boolean;
}

export interface PaginatedLogs {
  items: LogEntry[];
  total: number;
  page: number;
  limit: number;
  total_pages: number;
}

export interface LogEntry {
  id: string;
  timestamp: string;
  level: 'INFO' | 'WARNING' | 'ERROR';
  module: string;
  message: string;
}

// Market Configuration Types (Per-Market Overrides)
export interface MarketConfig {
  id: string;
  condition_id: string;
  market_question: string | null;
  sport: string | null;
  home_team: string | null;
  away_team: string | null;
  
  // Entry conditions (null = use sport default)
  entry_threshold_drop: number | null;
  entry_threshold_absolute: number | null;
  min_time_remaining_seconds: number | null;
  
  // Exit conditions
  take_profit_pct: number | null;
  stop_loss_pct: number | null;
  
  // Position sizing
  position_size_usdc: number | null;
  max_positions: number | null;
  
  // Control flags
  enabled: boolean;
  auto_trade: boolean;
  
  created_at: string;
  updated_at: string;
}

export interface MarketConfigWithDefaults extends MarketConfig {
  // Effective values (override or default)
  effective_entry_threshold_drop: number;
  effective_entry_threshold_absolute: number;
  effective_take_profit_pct: number;
  effective_stop_loss_pct: number;
  effective_position_size_usdc: number;
  effective_min_time_remaining_seconds: number;
  effective_max_positions: number;
}

export interface MarketConfigCreate {
  condition_id: string;
  market_question?: string;
  sport?: string;
  home_team?: string;
  away_team?: string;
  entry_threshold_drop?: number;
  entry_threshold_absolute?: number;
  min_time_remaining_seconds?: number;
  take_profit_pct?: number;
  stop_loss_pct?: number;
  position_size_usdc?: number;
  max_positions?: number;
  enabled?: boolean;
  auto_trade?: boolean;
}

export interface MarketConfigUpdate {
  entry_threshold_drop?: number | null;
  entry_threshold_absolute?: number | null;
  min_time_remaining_seconds?: number | null;
  take_profit_pct?: number | null;
  stop_loss_pct?: number | null;
  position_size_usdc?: number | null;
  max_positions?: number | null;
  enabled?: boolean;
  auto_trade?: boolean;
}

// =============================================================================
// League Selection Types
// =============================================================================

export interface LeagueInfo {
  league_key: string;
  display_name: string;
  sport_type: string;
  category: string;
}

export interface SportCategory {
  category: string;
  display_name: string;
  leagues: LeagueInfo[];
}

export interface UserLeagueConfig {
  league_key: string;
  enabled: boolean;
  entry_threshold_drop: number | null;
  entry_threshold_absolute: number | null;
  take_profit_pct: number | null;
  stop_loss_pct: number | null;
  position_size_usdc: number | null;
  min_time_remaining_seconds: number | null;
  max_positions: number | null;
}

export interface UserLeagueStatus {
  configured_leagues: UserLeagueConfig[];
  available_leagues: LeagueInfo[];
  enabled_count: number;
  total_available: number;
}

export interface BulkLeagueConfigItem {
  league_key: string;
  entry_threshold_drop?: number;
  entry_threshold_absolute?: number;
  take_profit_pct?: number;
  stop_loss_pct?: number;
  position_size_usdc?: number;
  min_time_remaining_seconds?: number;
  max_positions?: number;
}

export interface BulkLeagueConfigRequest {
  leagues: BulkLeagueConfigItem[];
  apply_same_settings: boolean;
}

export interface BulkLeagueConfigResponse {
  success: boolean;
  message: string;
  configured_count: number;
  leagues: string[];
}

export interface LeagueEnableRequest {
  league_keys: string[];
  enabled: boolean;
}

export interface LeagueEnableResponse {
  success: boolean;
  message: string;
  updated_count: number;
}

// =============================================================================
// Game Selection Types
// =============================================================================

export interface AvailableGame {
  id: string;
  condition_id: string;
  question: string | null;
  sport: string;
  home_team: string | null;
  away_team: string | null;
  home_abbrev: string | null;
  away_abbrev: string | null;
  game_start_time: string | null;
  current_price_yes: number | null;
  current_price_no: number | null;
  is_live: boolean;
  is_finished: boolean;
  is_user_selected: boolean;
  match_confidence: number | null;
}

export interface GameListResponse {
  selected: AvailableGame[];
  available: AvailableGame[];
  total_selected: number;
  total_available: number;
}

export interface GameSelectionResponse {
  success: boolean;
  message: string;
  market_id?: string;
  condition_id?: string;
  is_user_selected?: boolean;
}

export interface BulkGameSelectionResponse {
  success: boolean;
  message: string;
  updated_count: number;
}

// =============================================================================
// Bot Configuration Types (New)
// =============================================================================

export interface TradingParameters {
  probability_drop: number;       // Minimum probability drop to trigger entry (%)
  min_volume: number;             // Minimum market volume ($)
  position_size: number;          // Amount to invest per market ($)
  take_profit: number;            // Take profit percentage (%)
  stop_loss: number;              // Stop loss percentage (%)
  latest_entry_time: number;      // No new positions after X minutes remaining
  latest_exit_time: number;       // Must close positions by X minutes remaining
}

export interface GameSelection {
  game_id: string;
  sport: string;
  home_team: string;
  away_team: string;
  start_time: string;
  // Which team to bet on: 'home', 'away', or 'both'
  selected_side?: 'home' | 'away' | 'both';
  market_ticker?: string;
  token_id_yes?: string;
  token_id_no?: string;
}

export interface BotConfigRequest {
  sport: string;
  game: GameSelection;
  // Additional games for multi-sport support
  additional_games?: GameSelection[];
  parameters: TradingParameters;
  simulation_mode?: boolean;
}

export interface BotConfigResponse {
  is_running: boolean;
  sport?: string;
  game?: GameSelection;
  parameters: TradingParameters;
  simulation_mode?: boolean;
  last_updated?: string;
}

export interface DetailedBotStatus {
  is_running: boolean;
  current_game?: string;
  current_sport?: string;
  active_positions: number;
  pending_orders: number;
  today_pnl: number;
  today_trades: number;
}

export interface PlaceOrderRequest {
  platform: 'kalshi' | 'polymarket';
  ticker: string;                 // Market ticker or token_id
  side: 'buy' | 'sell';
  outcome: 'yes' | 'no';
  price: number;                  // 0.01 - 0.99
  size: number;                   // $ or contracts
}

export interface PlaceOrderResponse {
  success: boolean;
  order_id?: string;
  status: string;
  filled_size: number;
  message?: string;
}

export interface SportsMarket {
  ticker: string;
  title: string;
  status: string;
  yes_price: number;
}

// ESPN Live Game data from API
export interface ESPNGame {
  id: string;
  homeTeam: string;
  awayTeam: string;
  homeAbbr: string;
  awayAbbr: string;
  homeScore: number;
  awayScore: number;
  startTime: string | null;
  status: 'upcoming' | 'live' | 'final';
  currentPeriod: string;
  clock: string;
  name: string;
  shortName: string;
  homeOdds: number;
  awayOdds: number;
  volume: number;
  no_price: number;
  volume: number;
  close_time?: string;
}

// =============================================================================
// WebSocket Client (REQ-UX-002)
// =============================================================================

export type WebSocketEventType =
  | 'trade_executed'
  | 'position_opened'
  | 'position_closed'
  | 'position_updated'
  | 'order_placed'
  | 'order_filled'
  | 'order_cancelled'
  | 'bot_started'
  | 'bot_stopped'
  | 'bot_error'
  | 'bot_status_changed'
  | 'market_alert'
  | 'price_update'
  | 'connection_established'
  | 'heartbeat'
  | 'error'
  | 'daily_loss_warning'
  | 'kill_switch_activated';

export interface WebSocketMessage {
  event: WebSocketEventType;
  data: Record<string, unknown>;
  timestamp: string;
  correlation_id?: string;
}

export type WebSocketEventHandler = (message: WebSocketMessage) => void;

export interface WebSocketClientOptions {
  reconnect?: boolean;
  maxReconnectAttempts?: number;
  initialReconnectDelay?: number;
  maxReconnectDelay?: number;
  heartbeatInterval?: number;
}

/**
 * WebSocket client with automatic reconnection and exponential backoff.
 *
 * Usage:
 *   const wsClient = new WebSocketClient();
 *   wsClient.on('trade_executed', (msg) => console.log('Trade:', msg.data));
 *   wsClient.connect();
 */
export class WebSocketClient {
  private ws: WebSocket | null = null;
  private baseUrl: string;
  private options: Required<WebSocketClientOptions>;
  private eventHandlers: Map<WebSocketEventType | '*', Set<WebSocketEventHandler>> = new Map();
  private reconnectAttempts = 0;
  private reconnectTimeout: ReturnType<typeof setTimeout> | null = null;
  private heartbeatInterval: ReturnType<typeof setInterval> | null = null;
  private isConnecting = false;
  private manualDisconnect = false;

  constructor(options: WebSocketClientOptions = {}) {
    // Convert HTTP URL to WebSocket URL
    const httpUrl = API_BASE_URL.replace(/\/api\/v1$/, '');
    this.baseUrl = httpUrl.replace(/^http/, 'ws');

    this.options = {
      reconnect: options.reconnect ?? true,
      maxReconnectAttempts: options.maxReconnectAttempts ?? 10,
      initialReconnectDelay: options.initialReconnectDelay ?? 1000,
      maxReconnectDelay: options.maxReconnectDelay ?? 30000,
      heartbeatInterval: options.heartbeatInterval ?? 30000,
    };
  }

  /**
   * Connect to the WebSocket server.
   */
  connect(): void {
    if (this.ws?.readyState === WebSocket.OPEN || this.isConnecting) {
      return;
    }

    const token = localStorage.getItem('auth_token');
    if (!token) {
      console.warn('WebSocket: No auth token, skipping connection');
      return;
    }

    this.isConnecting = true;
    this.manualDisconnect = false;

    const wsUrl = `${this.baseUrl}/api/v1/ws?token=${encodeURIComponent(token)}`;

    try {
      this.ws = new WebSocket(wsUrl);
      this.setupEventListeners();
    } catch (error) {
      console.error('WebSocket connection error:', error);
      this.isConnecting = false;
      this.scheduleReconnect();
    }
  }

  /**
   * Disconnect from the WebSocket server.
   */
  disconnect(): void {
    this.manualDisconnect = true;
    this.clearReconnectTimeout();
    this.clearHeartbeat();

    if (this.ws) {
      this.ws.close(1000, 'Client disconnect');
      this.ws = null;
    }
  }

  /**
   * Register an event handler.
   * Use '*' to listen to all events.
   */
  on(event: WebSocketEventType | '*', handler: WebSocketEventHandler): void {
    if (!this.eventHandlers.has(event)) {
      this.eventHandlers.set(event, new Set());
    }
    this.eventHandlers.get(event)!.add(handler);
  }

  /**
   * Remove an event handler.
   */
  off(event: WebSocketEventType | '*', handler: WebSocketEventHandler): void {
    this.eventHandlers.get(event)?.delete(handler);
  }

  /**
   * Send a message to the server.
   */
  send(action: string, data?: Record<string, unknown>): void {
    if (this.ws?.readyState !== WebSocket.OPEN) {
      console.warn('WebSocket: Cannot send, not connected');
      return;
    }

    this.ws.send(JSON.stringify({ action, ...data }));
  }

  /**
   * Request a ping/heartbeat from the server.
   */
  ping(): void {
    this.send('ping');
  }

  /**
   * Check if connected.
   */
  get isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  private setupEventListeners(): void {
    if (!this.ws) return;

    this.ws.onopen = () => {
      console.log('WebSocket connected');
      this.isConnecting = false;
      this.reconnectAttempts = 0;
      this.startHeartbeat();
    };

    this.ws.onmessage = (event) => {
      try {
        const message: WebSocketMessage = JSON.parse(event.data);
        this.dispatchEvent(message);
      } catch (error) {
        console.error('WebSocket: Failed to parse message:', error);
      }
    };

    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    this.ws.onclose = (event) => {
      console.log(`WebSocket closed: ${event.code} ${event.reason}`);
      this.isConnecting = false;
      this.clearHeartbeat();

      if (!this.manualDisconnect && this.options.reconnect) {
        this.scheduleReconnect();
      }
    };
  }

  private dispatchEvent(message: WebSocketMessage): void {
    // Dispatch to specific event handlers
    const handlers = this.eventHandlers.get(message.event as WebSocketEventType);
    if (handlers) {
      handlers.forEach((handler) => {
        try {
          handler(message);
        } catch (error) {
          console.error('WebSocket event handler error:', error);
        }
      });
    }

    // Dispatch to wildcard handlers
    const wildcardHandlers = this.eventHandlers.get('*');
    if (wildcardHandlers) {
      wildcardHandlers.forEach((handler) => {
        try {
          handler(message);
        } catch (error) {
          console.error('WebSocket wildcard handler error:', error);
        }
      });
    }
  }

  private scheduleReconnect(): void {
    if (this.reconnectAttempts >= this.options.maxReconnectAttempts) {
      console.error('WebSocket: Max reconnect attempts reached');
      return;
    }

    // Exponential backoff with jitter
    const delay = Math.min(
      this.options.initialReconnectDelay * Math.pow(2, this.reconnectAttempts) + Math.random() * 1000,
      this.options.maxReconnectDelay
    );

    console.log(`WebSocket: Reconnecting in ${Math.round(delay)}ms (attempt ${this.reconnectAttempts + 1})`);

    this.reconnectTimeout = setTimeout(() => {
      this.reconnectAttempts++;
      this.connect();
    }, delay);
  }

  private clearReconnectTimeout(): void {
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
  }

  private startHeartbeat(): void {
    this.clearHeartbeat();
    this.heartbeatInterval = setInterval(() => {
      this.ping();
    }, this.options.heartbeatInterval);
  }

  private clearHeartbeat(): void {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
  }
}

// Export singleton instances
export const apiClient = new ApiClient();
export const wsClient = new WebSocketClient();
export default apiClient;