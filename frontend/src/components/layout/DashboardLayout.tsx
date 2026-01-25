import { ReactNode, useEffect } from 'react';
import { cn } from '@/lib/utils';
import { Sidebar } from './Sidebar';
import { StatusBar } from './StatusBar';
import { useAppStore } from '@/stores/useAppStore';
import { apiClient } from '@/api/client';

interface DashboardLayoutProps {
  children: ReactNode;
}

export function DashboardLayout({ children }: DashboardLayoutProps) {
  const { sidebarCollapsed, setWalletConnected, setBotStatus } = useAppStore();

  // Initialize wallet and bot status on mount
  useEffect(() => {
    const initStatus = async () => {
      try {
        // Check wallet/credentials status
        const onboardingStatus = await apiClient.getOnboardingStatus();
        setWalletConnected(onboardingStatus.wallet_connected, 'Connected');
        
        // Check bot status
        const botStatus = await apiClient.getBotStatus();
        setBotStatus(botStatus.is_running, botStatus.active_positions || 0);
      } catch (err) {
        console.log('Failed to fetch status:', err);
      }
    };
    initStatus();
  }, [setWalletConnected, setBotStatus]);

  return (
    <div className="min-h-screen bg-background">
      <Sidebar />
      <div
        className={cn(
          'transition-all duration-300',
          sidebarCollapsed ? 'ml-16' : 'ml-sidebar'
        )}
      >
        <StatusBar />
        <main className="p-6">
          {children}
        </main>
      </div>
    </div>
  );
}
