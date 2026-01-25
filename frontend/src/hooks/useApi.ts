import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import apiClient, { DashboardStats, BotStatus, Market, Position, Settings, PaginatedLogs, SportConfigResponse, SportConfigUpdate, GlobalSettingsResponse, GlobalSettingsUpdate } from '@/api/client';

// Query keys
export const queryKeys = {
  dashboardStats: ['dashboard', 'stats'] as const,
  botStatus: ['bot', 'status'] as const,
  markets: (sport?: string) => ['markets', sport] as const,
  positions: (status?: string) => ['positions', status] as const,
  settings: ['settings'] as const,
  sportConfigs: ['settings', 'sports'] as const,
  globalSettings: ['settings', 'global'] as const,
  logs: (level?: string, page?: number) => ['logs', level, page] as const,
  onboarding: ['onboarding'] as const,
};

// Dashboard hooks
export function useDashboardStats() {
  return useQuery({
    queryKey: queryKeys.dashboardStats,
    queryFn: () => apiClient.getDashboardStats(),
    refetchInterval: 10000, // Refetch every 10 seconds
    staleTime: 5000,
  });
}

// Bot hooks
export function useBotStatus() {
  return useQuery({
    queryKey: queryKeys.botStatus,
    queryFn: () => apiClient.getBotStatus(),
    refetchInterval: 5000,
    staleTime: 2000,
  });
}

export function useStartBot() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: () => apiClient.startBot(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.botStatus });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboardStats });
    },
  });
}

export function useStopBot() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: () => apiClient.stopBot(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.botStatus });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboardStats });
    },
  });
}

// Markets hooks
export function useMarkets(sport?: string) {
  return useQuery({
    queryKey: queryKeys.markets(sport),
    queryFn: () => apiClient.getMarkets(sport),
    staleTime: 30000,
  });
}

export function useTrackMarket() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (conditionId: string) => apiClient.trackMarket(conditionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['markets'] });
    },
  });
}

export function useUntrackMarket() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (conditionId: string) => apiClient.untrackMarket(conditionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['markets'] });
    },
  });
}

// Positions hooks
export function usePositions(status?: 'open' | 'closed') {
  return useQuery({
    queryKey: queryKeys.positions(status),
    queryFn: () => apiClient.getPositions(status),
    refetchInterval: 10000,
    staleTime: 5000,
  });
}

export function useClosePosition() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (positionId: string) => apiClient.closePosition(positionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['positions'] });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboardStats });
    },
  });
}

// Settings hooks
export function useSettings() {
  return useQuery({
    queryKey: queryKeys.settings,
    queryFn: () => apiClient.getSettings(),
    staleTime: 60000, // Cache for 1 minute
  });
}

export function useUpdateSettings() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (settings: Partial<Settings>) => apiClient.updateSettings(settings),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.settings });
    },
  });
}

export function useTestWalletConnection() {
  return useMutation({
    mutationFn: ({ privateKey, funderAddress }: { privateKey: string; funderAddress: string }) =>
      apiClient.testWalletConnection(privateKey, funderAddress),
  });
}

// Logs hooks
export function useLogs(level?: string, page: number = 1, limit: number = 50) {
  return useQuery({
    queryKey: queryKeys.logs(level, page),
    queryFn: () => apiClient.getLogs(level, page, limit),
    staleTime: 10000,
  });
}

// Onboarding hooks
export function useOnboardingStatus() {
  return useQuery({
    queryKey: queryKeys.onboarding,
    queryFn: () => apiClient.getOnboardingStatus(),
  });
}

export function useCompleteOnboardingStep() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ step, data }: { step: number; data?: Record<string, unknown> }) =>
      apiClient.completeOnboardingStep(step, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.onboarding });
    },
  });
}

export function useConnectWallet() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ privateKey, funderAddress, signatureType }: {
      privateKey: string;
      funderAddress: string;
      signatureType: number;
    }) => apiClient.connectWallet(privateKey, funderAddress, signatureType),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.onboarding });
      queryClient.invalidateQueries({ queryKey: queryKeys.settings });
    },
  });
}

// Sport Config hooks
export function useSportConfigs() {
  return useQuery<SportConfigResponse[]>({
    queryKey: queryKeys.sportConfigs,
    queryFn: () => apiClient.getSportConfigs(),
    staleTime: 60000,
  });
}

export function useUpdateSportConfig() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ sport, config }: { sport: string; config: SportConfigUpdate }) =>
      apiClient.updateSportConfig(sport, config),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.sportConfigs });
    },
  });
}

// Global Settings hooks
export function useGlobalSettings() {
  return useQuery<GlobalSettingsResponse>({
    queryKey: queryKeys.globalSettings,
    queryFn: () => apiClient.getGlobalSettings(),
    staleTime: 60000,
  });
}

export function useUpdateGlobalSettings() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (settings: GlobalSettingsUpdate) =>
      apiClient.updateGlobalSettings(settings),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.globalSettings });
    },
  });
}
