import { ReactNode, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { cn } from '@/lib/utils';
import { Sidebar } from './Sidebar';
import { StatusBar } from './StatusBar';
import { MobileHeader, MobileBottomNav } from './MobileNav';
import { useAppStore } from '@/stores/useAppStore';
import { useAuthStore } from '@/stores/useAuthStore';
import { apiClient } from '@/api/client';
import { AppTour } from '@/components/AppTour';
import { useSSE } from '@/hooks/useSSE';

interface DashboardLayoutProps {
  children: ReactNode;
}

export function DashboardLayout({ children }: DashboardLayoutProps) {
  const navigate = useNavigate();
  const { sidebarCollapsed, setWalletConnected, setBotStatus, tour, stopTour } = useAppStore();
  const { refreshUser } = useAuthStore();

  // Connect to SSE for real-time status updates (shows "Online" in StatusBar)
  useSSE({ enabled: true });

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

        // Check bot status - use correct property names from BotStatus interface
        const botStatus = await apiClient.getBotStatus();
        setBotStatus(botStatus.bot_enabled, botStatus.tracked_markets || 0);
      } catch (err) {
        // Silent failure - non-critical status check
      }
    };
    initStatus();
  }, [setWalletConnected, setBotStatus, refreshUser, navigate]);

  return (
    <div className="min-h-screen bg-background">
      {/* Mobile Navigation */}
      <MobileHeader />
      <MobileBottomNav />

      {/* Desktop Sidebar - hidden on mobile */}
      <div className="hidden md:block">
        <Sidebar />
      </div>

      <div
        className={cn(
          'transition-all duration-300',
          // Desktop: margin for sidebar
          'md:ml-sidebar',
          sidebarCollapsed && 'md:ml-16',
          // Mobile: no margin, but pad for fixed header/bottom nav
          'pt-14 pb-16 md:pt-0 md:pb-0'
        )}
      >
        {/* Status bar - hidden on mobile */}
        <div className="hidden md:block">
          <StatusBar />
        </div>
        <main className="p-4 md:p-6">
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
