import { useState, useEffect } from 'react';
import { Wallet, TrendingUp, Briefcase, Eye, Loader2 } from 'lucide-react';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { StatCard } from '@/components/dashboard/StatCard';
import { PriceChart } from '@/components/dashboard/PriceChart';
import { LiveGames } from '@/components/dashboard/LiveGames';
import { OrderBook } from '@/components/dashboard/OrderBook';
import { apiClient, DashboardStats, ActivityLog } from '@/api/client';

export default function Dashboard() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        setLoading(true);
        const data = await apiClient.getDashboardStats();
        setStats(data);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load dashboard');
        // Set default values on error
        setStats(null);
      } finally {
        setLoading(false);
      }
    };

    fetchStats();
    // Refresh every 30 seconds
    const interval = setInterval(fetchStats, 30000);
    return () => clearInterval(interval);
  }, []);

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
    }).format(value);
  };

  const formatPnl = (value: number) => {
    const prefix = value >= 0 ? '+' : '';
    return prefix + formatCurrency(value);
  };

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Page Header */}
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Dashboard</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Real-time overview of your trading activity
          </p>
        </div>

        {/* Error Banner */}
        {error && (
          <div className="bg-destructive/10 border border-destructive/20 text-destructive px-4 py-3 rounded-lg">
            {error}
          </div>
        )}

        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
          <StatCard
            label="Portfolio Value"
            value={loading ? '...' : formatCurrency(stats?.balance_usdc ?? 0)}
            change={loading ? '' : `${formatPnl(stats?.total_pnl_all_time ?? 0)} all time`}
            changeType={(stats?.total_pnl_all_time ?? 0) >= 0 ? 'positive' : 'negative'}
            icon={Wallet}
            iconColor="primary"
          />
          <StatCard
            label="Daily P&L"
            value={loading ? '...' : formatPnl(stats?.total_pnl_today ?? 0)}
            change={loading ? '' : `${((stats?.win_rate ?? 0) * 100).toFixed(1)}% win rate`}
            changeType={(stats?.total_pnl_today ?? 0) >= 0 ? 'positive' : 'negative'}
            icon={TrendingUp}
            iconColor="info"
          />
          <StatCard
            label="Open Positions"
            value={loading ? '...' : String(stats?.open_positions_count ?? 0)}
            change={loading ? '' : `${formatCurrency(stats?.open_positions_value ?? 0)} exposed`}
            changeType="neutral"
            icon={Briefcase}
            iconColor="warning"
          />
          <StatCard
            label="Tracked Markets"
            value={loading ? '...' : String(stats?.active_markets_count ?? 0)}
            change={loading ? '' : `Bot ${stats?.bot_status ?? 'stopped'}`}
            changeType="neutral"
            icon={Eye}
            iconColor="destructive"
          />
        </div>

        {/* Charts & Live Data */}
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
          <div className="xl:col-span-2">
            <PriceChart />
          </div>
          <div>
            <LiveGames />
          </div>
        </div>

        {/* Order Book & Recent Activity */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <OrderBook />
          <div className="bg-card border border-border rounded-lg p-6">
            <h3 className="text-base font-medium text-foreground mb-4">Recent Activity</h3>
            <div className="space-y-3">
              {loading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
                </div>
              ) : stats?.recent_activity && stats.recent_activity.length > 0 ? (
                stats.recent_activity.slice(0, 5).map((activity: ActivityLog) => (
                  <div key={activity.id} className="flex items-center justify-between py-2 border-b border-border last:border-0">
                    <div className="flex items-center gap-3">
                      <span className={`text-xs font-medium px-2 py-0.5 rounded ${
                        activity.level === 'INFO' ? 'bg-primary/10 text-primary' : 
                        activity.level === 'WARNING' ? 'bg-warning/10 text-warning' :
                        'bg-destructive/10 text-destructive'
                      }`}>
                        {activity.level}
                      </span>
                      <div>
                        <p className="text-sm font-medium text-foreground">{activity.category}</p>
                        <p className="text-xs text-muted-foreground truncate max-w-[200px]">
                          {activity.message}
                        </p>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="text-xs text-muted-foreground">
                        {new Date(activity.created_at).toLocaleTimeString()}
                      </p>
                    </div>
                  </div>
                ))
              ) : (
                <p className="text-sm text-muted-foreground text-center py-8">
                  No recent activity. Start the bot to see trading activity here.
                </p>
              )}
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
