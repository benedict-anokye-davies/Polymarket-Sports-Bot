/**
 * API Client for Polymarket Trading Bot Backend
 * Handles all HTTP requests with authentication and error handling
 */

const API_BASE_URL = import.meta.env.VITE_API_URL?.trim() || 'https://polymarket-sports-bot-production.up.railway.app/api/v1';

interface ApiError {
  detail: string;
  status: number;
}

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  private getToken(): string | null {
    return localStorage.getItem('auth_token');
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const token = this.getToken();
    
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    };

    if (token) {
      (headers as Record<string, string>)['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      ...options,
      headers,
    });

    if (!response.ok) {
      if (response.status === 401) {
        // Clear token and redirect to login
        localStorage.removeItem('auth_token');
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
  }

  // Auth endpoints
  async login(email: string, password: string): Promise<{ access_token: string; token_type: string }> {
    const formData = new URLSearchParams();
    formData.append('username', email);
    formData.append('password', password);

    const response = await fetch(`${this.baseUrl}/auth/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Login failed' }));
      throw new Error(error.detail || 'Login failed');
    }

    return response.json();
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

  // Trading endpoints
  async getMarkets(sport?: string): Promise<Market[]> {
    const params = sport ? `?sport=${sport}` : '';
    return this.request(`/trading/markets${params}`);
  }

  async trackMarket(conditionId: string): Promise<{ message: string }> {
    return this.request(`/trading/markets/${conditionId}/track`, { method: 'POST' });
  }

  async untrackMarket(conditionId: string): Promise<{ message: string }> {
    return this.request(`/trading/markets/${conditionId}/track`, { method: 'DELETE' });
  }

  async getPositions(status?: 'open' | 'closed'): Promise<Position[]> {
    const params = status ? `?status=${status}` : '';
    return this.request(`/trading/positions${params}`);
  }

  async closePosition(positionId: string): Promise<{ message: string }> {
    return this.request(`/trading/positions/${positionId}/close`, { method: 'POST' });
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
    return this.request(`/onboarding/step/${step}`, {
      method: 'POST',
      body: JSON.stringify(data || {}),
    });
  }

  async connectWallet(privateKey: string, funderAddress: string, signatureType: number): Promise<{ message: string }> {
    return this.request('/onboarding/wallet/connect', {
      method: 'POST',
      body: JSON.stringify({
        private_key: privateKey,
        funder_address: funderAddress,
        signature_type: signatureType,
      }),
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
}

export interface GlobalSettingsUpdate {
  bot_enabled?: boolean;
  max_daily_loss_usdc?: number;
  max_portfolio_exposure_usdc?: number;
  discord_webhook_url?: string | null;
  discord_alerts_enabled?: boolean;
  poll_interval_seconds?: number;
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
  baseline_price_yes: number;
  current_price_yes: number;
  is_live: boolean;
  is_tracked: boolean;
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

// Export singleton instance
export const apiClient = new ApiClient();
export default apiClient;