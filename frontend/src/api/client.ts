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

  async getCurrentUser(): Promise<{ id: string; username: string; email: string }> {
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

  // Settings endpoints
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

// Export singleton instance
export const apiClient = new ApiClient();
export default apiClient;
