/**
 * MobileNav Component (REQ-UX-008)
 * 
 * Mobile-responsive navigation with hamburger menu toggle.
 * Shows bottom nav on mobile and integrates with existing Sidebar.
 */

import { useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { 
  LayoutGrid, 
  Layers, 
  Briefcase, 
  Settings, 
  Bot,
  BarChart3,
  Menu,
  X,
  TrendingUp,
  Clock,
  Terminal,
  Users,
  FlaskConical,
  LogOut
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { useAuthStore } from '@/stores/useAuthStore';

/**
 * Primary navigation items shown in bottom nav.
 */
const primaryNavItems = [
  { path: '/dashboard', label: 'Home', icon: LayoutGrid },
  { path: '/positions', label: 'Positions', icon: Briefcase },
  { path: '/bot', label: 'Bot', icon: Bot },
  { path: '/analytics', label: 'Analytics', icon: BarChart3 },
];

/**
 * All navigation items for slide-out menu.
 */
const allNavItems = [
  { path: '/dashboard', label: 'Dashboard', icon: LayoutGrid },
  { path: '/bot', label: 'Bot Config', icon: Bot },
  { path: '/markets', label: 'Markets', icon: Layers },
  { path: '/positions', label: 'Positions', icon: Briefcase },
  { path: '/history', label: 'History', icon: Clock },
  { path: '/analytics', label: 'Analytics', icon: BarChart3 },
  { path: '/backtesting', label: 'Backtesting', icon: FlaskConical },
  { path: '/accounts', label: 'Accounts', icon: Users },
  { path: '/settings', label: 'Settings', icon: Settings },
  { path: '/logs', label: 'Activity Logs', icon: Terminal },
];

/**
 * Mobile header with hamburger menu.
 */
export function MobileHeader() {
  const [menuOpen, setMenuOpen] = useState(false);
  const location = useLocation();
  const { logout } = useAuthStore();

  const currentPage = allNavItems.find(item => item.path === location.pathname);

  return (
    <>
      {/* Fixed Header */}
      <header className="fixed top-0 left-0 right-0 h-14 bg-sidebar border-b border-sidebar-border z-50 md:hidden">
        <div className="flex items-center justify-between h-full px-4">
          {/* Logo */}
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center">
              <TrendingUp className="w-4 h-4 text-primary" />
            </div>
            <span className="font-semibold text-foreground text-sm">Kalshi Bot</span>
          </div>

          {/* Current Page Title */}
          <span className="text-sm font-medium text-foreground">
            {currentPage?.label || 'Dashboard'}
          </span>

          {/* Menu Toggle */}
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setMenuOpen(true)}
            className="text-foreground"
          >
            <Menu className="w-5 h-5" />
          </Button>
        </div>
      </header>

      {/* Slide-out Menu */}
      {menuOpen && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-black/50 z-50 md:hidden"
            onClick={() => setMenuOpen(false)}
          />

          {/* Menu Panel */}
          <div className="fixed right-0 top-0 bottom-0 w-72 bg-sidebar border-l border-sidebar-border z-50 md:hidden animate-in slide-in-from-right duration-200">
            {/* Menu Header */}
            <div className="flex items-center justify-between h-14 px-4 border-b border-sidebar-border">
              <span className="font-semibold text-foreground">Menu</span>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setMenuOpen(false)}
              >
                <X className="w-5 h-5" />
              </Button>
            </div>

            {/* Navigation Items */}
            <nav className="p-4 space-y-1">
              {allNavItems.map((item) => {
                const isActive = location.pathname === item.path;
                return (
                  <NavLink
                    key={item.path}
                    to={item.path}
                    onClick={() => setMenuOpen(false)}
                    className={cn(
                      'flex items-center gap-3 px-3 py-2.5 rounded-md transition-colors',
                      isActive
                        ? 'bg-sidebar-accent text-sidebar-accent-foreground'
                        : 'text-sidebar-foreground hover:bg-sidebar-accent/50'
                    )}
                  >
                    <item.icon className={cn('w-5 h-5', isActive && 'text-primary')} />
                    <span className="text-sm font-medium">{item.label}</span>
                  </NavLink>
                );
              })}
            </nav>

            {/* Logout Button */}
            <div className="absolute bottom-0 left-0 right-0 p-4 border-t border-sidebar-border">
              <Button
                variant="ghost"
                className="w-full justify-start gap-3 text-muted-foreground hover:text-foreground"
                onClick={() => {
                  logout();
                  setMenuOpen(false);
                }}
              >
                <LogOut className="w-5 h-5" />
                <span>Logout</span>
              </Button>
            </div>
          </div>
        </>
      )}
    </>
  );
}

/**
 * Bottom navigation bar for mobile.
 */
export function MobileBottomNav() {
  const location = useLocation();

  return (
    <nav className="fixed bottom-0 left-0 right-0 h-16 bg-sidebar border-t border-sidebar-border z-40 md:hidden">
      <div className="flex items-center justify-around h-full">
        {primaryNavItems.map((item) => {
          const isActive = location.pathname === item.path;
          return (
            <NavLink
              key={item.path}
              to={item.path}
              className={cn(
                'flex flex-col items-center justify-center gap-1 flex-1 h-full transition-colors',
                isActive
                  ? 'text-primary'
                  : 'text-muted-foreground hover:text-foreground'
              )}
            >
              <item.icon className="w-5 h-5" />
              <span className="text-xs font-medium">{item.label}</span>
            </NavLink>
          );
        })}
      </div>
    </nav>
  );
}

/**
 * Wrapper component that adds mobile padding for fixed header/bottom nav.
 */
export function MobileContentWrapper({ children }: { children: React.ReactNode }) {
  return (
    <div className="pt-14 pb-16 md:pt-0 md:pb-0">
      {children}
    </div>
  );
}

export default MobileHeader;
