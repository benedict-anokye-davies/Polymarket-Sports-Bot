import { ReactNode, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { cn } from '@/lib/utils';
import { Sidebar } from './Sidebar';
import { StatusBar } from './StatusBar';
import { useAppStore } from '@/stores/useAppStore';
import { useAuthStore } from '@/stores/useAuthStore';
import { apiClient } from '@/api/client';
import { AppTour } from '@/components/AppTour';

interface DashboardLayoutProps {
  children: ReactNode;
}

export function DashboardLayout({ children }: DashboardLayoutProps) {
  const navigate = useNavigate();
  const { sidebarCollapsed, setWalletConnected, setBotStatus, tour, stopTour } = useAppStore();
  const { refreshUser } = useAuthStore();

  // Initialize wallet and bot status on mount
  useEffect(() => {
    const initStatus = async () => {
      try {
        // Check wallet/credentials status and sync onboarding state
        const onboardingStatus = await apiClient.getOnboardingStatus();
        setWalletConnected(onboardingStatus.wallet_connected, 'Connected');

        // If backend says onboarding is not complete (step < 5), refresh user and redirect
        if (onboardingStatus.current_step < 5) {
          await refreshUser();
          navigate('/onboarding');
          return;
        }

        // Check bot status
        const botStatus = await apiClient.getBotStatus();
        setBotStatus(botStatus.is_running, botStatus.active_positions || 0);
      } catch (err) {
        console.log('Failed to fetch status:', err);
      }
    };
    initStatus();
  }, [setWalletConnected, setBotStatus, refreshUser, navigate]);

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
      
      {/* App Tour */}
      <AppTour 
        run={tour.isRunning} 
        onComplete={stopTour}
        startStep={tour.stepIndex}
      />
    </div>
  );
}
