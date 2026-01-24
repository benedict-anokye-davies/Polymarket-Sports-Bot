import { ReactNode } from 'react';
import { cn } from '@/lib/utils';
import { Sidebar } from './Sidebar';
import { StatusBar } from './StatusBar';
import { useAppStore } from '@/stores/useAppStore';

interface DashboardLayoutProps {
  children: ReactNode;
}

export function DashboardLayout({ children }: DashboardLayoutProps) {
  const { sidebarCollapsed } = useAppStore();

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
