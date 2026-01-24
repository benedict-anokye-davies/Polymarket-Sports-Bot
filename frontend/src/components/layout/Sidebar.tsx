import { NavLink, useLocation } from 'react-router-dom';
import { 
  LayoutGrid, 
  Layers, 
  Briefcase, 
  Clock, 
  Settings, 
  Terminal,
  TrendingUp,
  LogOut,
  ChevronLeft,
  ChevronRight
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAppStore } from '@/stores/useAppStore';
import { Button } from '@/components/ui/button';

const navItems = [
  { path: '/dashboard', label: 'Dashboard', icon: LayoutGrid },
  { path: '/markets', label: 'Markets', icon: Layers },
  { path: '/positions', label: 'Positions', icon: Briefcase },
  { path: '/history', label: 'History', icon: Clock },
  { path: '/settings', label: 'Settings', icon: Settings },
  { path: '/logs', label: 'Activity Logs', icon: Terminal },
];

export function Sidebar() {
  const location = useLocation();
  const { sidebarCollapsed, toggleSidebar } = useAppStore();

  return (
    <aside
      className={cn(
        'fixed left-0 top-0 h-screen bg-sidebar border-r border-sidebar-border flex flex-col transition-all duration-300 z-50',
        sidebarCollapsed ? 'w-16' : 'w-sidebar'
      )}
    >
      {/* Logo Header */}
      <div className="h-header flex items-center px-4 border-b border-sidebar-border">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center">
            <TrendingUp className="w-5 h-5 text-primary" />
          </div>
          {!sidebarCollapsed && (
            <div className="flex flex-col">
              <span className="font-semibold text-foreground text-sm">Polymarket</span>
              <span className="text-xs text-muted-foreground">Trading Bot</span>
            </div>
          )}
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-4 px-2 space-y-1 overflow-y-auto scrollbar-thin">
        {navItems.map((item) => {
          const isActive = location.pathname === item.path;
          return (
            <NavLink
              key={item.path}
              to={item.path}
              className={cn(
                'flex items-center gap-3 px-3 py-2.5 rounded-md transition-all duration-200 group relative',
                isActive
                  ? 'bg-sidebar-accent text-sidebar-accent-foreground'
                  : 'text-sidebar-foreground hover:bg-sidebar-accent/50 hover:text-sidebar-accent-foreground'
              )}
            >
              {isActive && (
                <div className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-5 bg-primary rounded-r" />
              )}
              <item.icon className={cn('w-5 h-5 flex-shrink-0', isActive && 'text-primary')} />
              {!sidebarCollapsed && (
                <span className="text-sm font-medium">{item.label}</span>
              )}
            </NavLink>
          );
        })}
      </nav>

      {/* Collapse Toggle */}
      <div className="px-2 pb-2">
        <Button
          variant="ghost"
          size="sm"
          onClick={toggleSidebar}
          className="w-full justify-center text-muted-foreground hover:text-foreground"
        >
          {sidebarCollapsed ? (
            <ChevronRight className="w-4 h-4" />
          ) : (
            <>
              <ChevronLeft className="w-4 h-4 mr-2" />
              <span className="text-xs">Collapse</span>
            </>
          )}
        </Button>
      </div>

      {/* User Footer */}
      <div className={cn(
        'border-t border-sidebar-border p-3',
        sidebarCollapsed ? 'flex justify-center' : ''
      )}>
        <div className={cn('flex items-center gap-3', sidebarCollapsed && 'flex-col')}>
          <div className="w-9 h-9 rounded-full bg-gradient-to-br from-primary/30 to-primary/10 flex items-center justify-center text-sm font-medium text-primary">
            JD
          </div>
          {!sidebarCollapsed && (
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-foreground truncate">John Doe</p>
              <p className="text-xs text-primary">Pro Plan</p>
            </div>
          )}
          {!sidebarCollapsed && (
            <Button variant="ghost" size="icon" className="text-muted-foreground hover:text-foreground">
              <LogOut className="w-4 h-4" />
            </Button>
          )}
        </div>
      </div>
    </aside>
  );
}
