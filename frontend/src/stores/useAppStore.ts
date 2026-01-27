import { create } from 'zustand';

interface WalletState {
  address: string | null;
  connected: boolean;
  balance: number;
}

interface BotState {
  running: boolean;
  activeMarkets: number;
  lastUpdate: Date | null;
}

interface ConnectionState {
  sseConnected: boolean;
  wsConnected: boolean;
  lastHeartbeat: Date | null;
}

interface TourState {
  isRunning: boolean;
  currentPage: 'dashboard' | 'bot-config' | null;
  stepIndex: number;
}

interface AppState {
  wallet: WalletState;
  bot: BotState;
  connection: ConnectionState;
  tour: TourState;
  sidebarCollapsed: boolean;
  
  // Actions
  setWalletConnected: (connected: boolean, address?: string) => void;
  setWalletBalance: (balance: number) => void;
  toggleBot: () => void;
  setBotStatus: (running: boolean, activeMarkets?: number) => void;
  setSseConnected: (connected: boolean) => void;
  setWsConnected: (connected: boolean) => void;
  toggleSidebar: () => void;
  updateLastUpdate: () => void;
  startTour: () => void;
  stopTour: () => void;
  setTourPage: (page: 'dashboard' | 'bot-config' | null) => void;
  setTourStep: (index: number) => void;
}

export const useAppStore = create<AppState>((set) => ({
  wallet: {
    address: null,
    connected: false,
    balance: 0,
  },
  bot: {
    running: false,
    activeMarkets: 0,
    lastUpdate: null,
  },
  connection: {
    sseConnected: false,
    wsConnected: false,
    lastHeartbeat: null,
  },
  tour: {
    isRunning: false,
    currentPage: null,
    stepIndex: 0,
  },
  sidebarCollapsed: false,

  setWalletConnected: (connected, address) =>
    set((state) => ({
      wallet: { ...state.wallet, connected, address: address ?? state.wallet.address },
    })),

  setWalletBalance: (balance) =>
    set((state) => ({
      wallet: { ...state.wallet, balance },
    })),

  toggleBot: () =>
    set((state) => ({
      bot: { ...state.bot, running: !state.bot.running },
    })),

  setBotStatus: (running, activeMarkets) =>
    set((state) => ({
      bot: {
        ...state.bot,
        running,
        activeMarkets: activeMarkets ?? state.bot.activeMarkets,
      },
    })),

  setSseConnected: (connected) =>
    set((state) => ({
      connection: { ...state.connection, sseConnected: connected, lastHeartbeat: new Date() },
    })),

  setWsConnected: (connected) =>
    set((state) => ({
      connection: { ...state.connection, wsConnected: connected, lastHeartbeat: new Date() },
    })),

  toggleSidebar: () =>
    set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),

  updateLastUpdate: () =>
    set((state) => ({
      bot: { ...state.bot, lastUpdate: new Date() },
    })),

  startTour: () =>
    set((state) => ({
      tour: { ...state.tour, isRunning: true, currentPage: 'dashboard', stepIndex: 0 },
    })),

  stopTour: () =>
    set((state) => ({
      tour: { ...state.tour, isRunning: false, currentPage: null, stepIndex: 0 },
    })),

  setTourPage: (page) =>
    set((state) => ({
      tour: { ...state.tour, currentPage: page },
    })),

  setTourStep: (index) =>
    set((state) => ({
      tour: { ...state.tour, stepIndex: index },
    })),
}));
