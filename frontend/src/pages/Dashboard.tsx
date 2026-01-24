import { Wallet, TrendingUp, Briefcase, Eye } from 'lucide-react';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { StatCard } from '@/components/dashboard/StatCard';
import { PriceChart } from '@/components/dashboard/PriceChart';
import { LiveGames } from '@/components/dashboard/LiveGames';
import { OrderBook } from '@/components/dashboard/OrderBook';

export default function Dashboard() {
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

        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
          <StatCard
            label="Portfolio Value"
            value="$12,847.52"
            change="+$1,234.56 all time"
            changeType="positive"
            icon={Wallet}
            iconColor="primary"
          />
          <StatCard
            label="Daily P&L"
            value="+$342.18"
            change="+2.7% vs yesterday"
            changeType="positive"
            icon={TrendingUp}
            iconColor="info"
          />
          <StatCard
            label="Open Positions"
            value="7"
            change="$3,420 exposed"
            changeType="neutral"
            icon={Briefcase}
            iconColor="warning"
          />
          <StatCard
            label="Tracked Markets"
            value="24"
            change="4 sports active"
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

        {/* Order Book */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <OrderBook />
          <div className="bg-card border border-border rounded-lg p-6">
            <h3 className="text-base font-medium text-foreground mb-4">Recent Trades</h3>
            <div className="space-y-3">
              {[
                { market: 'LAL vs BOS', side: 'YES', price: 0.68, size: 500, time: '2 min ago', pnl: '+$34.00' },
                { market: 'GSW vs MIA', side: 'NO', price: 0.42, size: 750, time: '15 min ago', pnl: '-$12.50' },
                { market: 'KC vs SF', side: 'YES', price: 0.55, size: 1000, time: '1 hr ago', pnl: '+$89.00' },
              ].map((trade, i) => (
                <div key={i} className="flex items-center justify-between py-2 border-b border-border last:border-0">
                  <div className="flex items-center gap-3">
                    <span className={`text-xs font-medium px-2 py-0.5 rounded ${
                      trade.side === 'YES' ? 'bg-primary/10 text-primary' : 'bg-destructive/10 text-destructive'
                    }`}>
                      {trade.side}
                    </span>
                    <div>
                      <p className="text-sm font-medium text-foreground">{trade.market}</p>
                      <p className="text-xs text-muted-foreground">
                        ${trade.price} × {trade.size.toLocaleString()}
                      </p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className={`text-sm font-mono-numbers ${
                      trade.pnl.startsWith('+') ? 'text-profit' : 'text-loss'
                    }`}>
                      {trade.pnl}
                    </p>
                    <p className="text-xs text-muted-foreground">{trade.time}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
