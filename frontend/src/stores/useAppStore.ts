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
  lastHeartbeat: Date | null;
}

interface AppState {
  wallet: WalletState;
  bot: BotState;
  connection: ConnectionState;
  sidebarCollapsed: boolean;
  
  // Actions
  setWalletConnected: (connected: boolean, address?: string) => void;
  setWalletBalance: (balance: number) => void;
  toggleBot: () => void;
  setBotStatus: (running: boolean, activeMarkets?: number) => void;
  setSseConnected: (connected: boolean) => void;
  toggleSidebar: () => void;
  updateLastUpdate: () => void;
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
    lastHeartbeat: null,
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

  toggleSidebar: () =>
    set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),

  updateLastUpdate: () =>
    set((state) => ({
      bot: { ...state.bot, lastUpdate: new Date() },
    })),
}));
