import { useState, useEffect, useMemo } from 'react';
import { Download, Trophy, TrendingUp, Clock, Target, Loader2 } from 'lucide-react';
import { 
  AreaChart, 
  Area, 
  XAxis, 
  YAxis, 
  Tooltip, 
  ResponsiveContainer,
  CartesianGrid 
} from 'recharts';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { cn } from '@/lib/utils';
import { apiClient, Position } from '@/api/client';

export default function History() {
  const [positions, setPositions] = useState<Position[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Filter state
  const [dateRange, setDateRange] = useState('30d');
  const [statusFilter, setStatusFilter] = useState('all');

  useEffect(() => {
    fetchClosedPositions();
  }, []);

  const fetchClosedPositions = async () => {
    try {
      setLoading(true);
      const data = await apiClient.getPositions('closed');
      setPositions(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load history');
    } finally {
      setLoading(false);
    }
  };

  // Apply filters to positions
  const filteredPositions = useMemo(() => {
    let filtered = [...positions];
    
    // Date range filter
    const now = new Date();
    const dateRangeMap: Record<string, number> = {
      '7d': 7,
      '30d': 30,
      '90d': 90,
      'custom': 365, // Default to 1 year for custom (could add date picker)
    };
    const daysAgo = dateRangeMap[dateRange] || 30;
    const cutoffDate = new Date(now.getTime() - daysAgo * 24 * 60 * 60 * 1000);
    
    filtered = filtered.filter(p => {
      const closedDate = p.closed_at ? new Date(p.closed_at) : new Date(p.opened_at);
      return closedDate >= cutoffDate;
    });
    
    // Status filter (profit/loss)
    if (statusFilter === 'profit') {
      filtered = filtered.filter(p => (p.realized_pnl_usdc ?? 0) > 0);
    } else if (statusFilter === 'loss') {
      filtered = filtered.filter(p => (p.realized_pnl_usdc ?? 0) < 0);
    }
    
    return filtered;
  }, [positions, dateRange, statusFilter]);

  const totalPnl = filteredPositions.reduce((sum, p) => sum + (p.realized_pnl_usdc ?? 0), 0);
  const winCount = filteredPositions.filter(p => (p.realized_pnl_usdc ?? 0) > 0).length;
  const winRate = filteredPositions.length > 0 ? (winCount / filteredPositions.length) * 100 : 0;

  // Calculate average trade duration
  const formatDuration = (openedAt: string, closedAt: string | null): string => {
    if (!closedAt) return '---';
    const ms = new Date(closedAt).getTime() - new Date(openedAt).getTime();
    if (ms < 0) return '---';
    const totalMinutes = Math.floor(ms / 60000);
    if (totalMinutes < 60) return `${totalMinutes}m`;
    const hours = Math.floor(totalMinutes / 60);
    const minutes = totalMinutes % 60;
    if (hours < 24) return `${hours}h ${minutes}m`;
    const days = Math.floor(hours / 24);
    return `${days}d ${hours % 24}h`;
  };

  const avgDuration = useMemo(() => {
    const withDuration = filteredPositions.filter(p => p.closed_at);
    if (withDuration.length === 0) return '---';
    const totalMs = withDuration.reduce((sum, p) => {
      return sum + (new Date(p.closed_at!).getTime() - new Date(p.opened_at).getTime());
    }, 0);
    const avgMs = totalMs / withDuration.length;
    const avgMinutes = Math.floor(avgMs / 60000);
    if (avgMinutes < 60) return `${avgMinutes}m`;
    const hours = Math.floor(avgMinutes / 60);
    const minutes = avgMinutes % 60;
    if (hours < 24) return `${hours}h ${minutes}m`;
    const days = Math.floor(hours / 24);
    return `${days}d ${hours % 24}h`;
  }, [filteredPositions]);

  // Export CSV handler
  const handleExportCSV = () => {
    if (filteredPositions.length === 0) return;
    
    const headers = [
      'Market',
      'Side',
      'Entry Price',
      'Exit Price',
      'Size (USDC)',
      'Realized P&L',
      'Duration',
      'Opened At',
      'Closed At',
    ];

    const rows = filteredPositions.map(p => [
      p.team || p.token_id,
      p.side,
      p.entry_price.toFixed(4),
      (p.current_price ?? p.entry_price).toFixed(4),
      p.entry_cost_usdc.toFixed(2),
      (p.realized_pnl_usdc ?? 0).toFixed(2),
      formatDuration(p.opened_at, p.closed_at ?? null),
      new Date(p.opened_at).toISOString(),
      p.closed_at ? new Date(p.closed_at).toISOString() : '',
    ]);
    
    const csvContent = [
      headers.join(','),
      ...rows.map(row => row.join(','))
    ].join('\n');
    
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.setAttribute('href', url);
    link.setAttribute('download', `trade-history-${new Date().toISOString().slice(0, 10)}.csv`);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const stats = [
    { label: 'Total Trades', value: String(filteredPositions.length), icon: Target },
    { label: 'Win Rate', value: `${winRate.toFixed(1)}%`, icon: Trophy },
    { label: 'Total P&L', value: `${totalPnl >= 0 ? '+' : ''}$${totalPnl.toFixed(2)}`, positive: totalPnl >= 0, icon: TrendingUp },
    { label: 'Avg Duration', value: avgDuration, icon: Clock },
  ];

  // Generate P&L chart data from filtered positions
  const pnlData = useMemo(() => {
    if (filteredPositions.length === 0) {
      // Return empty chart data
      return Array.from({ length: 7 }, (_, i) => {
        const date = new Date();
        date.setDate(date.getDate() - (6 - i));
        return {
          date: date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
          pnl: 0,
        };
      });
    }
    
    // Group by date and calculate cumulative P&L
    const sorted = [...filteredPositions].sort((a, b) => 
      new Date(a.closed_at || 0).getTime() - new Date(b.closed_at || 0).getTime()
    );
    
    let cumulative = 0;
    return sorted.map(p => {
      cumulative += p.realized_pnl_usdc ?? 0;
      return {
        date: new Date(p.closed_at || Date.now()).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
        pnl: parseFloat(cumulative.toFixed(2)),
      };
    });
  }, [filteredPositions]);

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Page Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-foreground">History</h1>
            <p className="text-sm text-muted-foreground mt-1">
              View your trading performance and closed positions
            </p>
          </div>
          <Button 
            variant="outline" 
            className="border-border hover:bg-muted gap-2"
            onClick={handleExportCSV}
            disabled={filteredPositions.length === 0}
          >
            <Download className="w-4 h-4" />
            Export CSV
          </Button>
        </div>

        {/* Filters */}
        <Card className="p-4 bg-card border-border">
          <div className="flex flex-wrap items-center gap-4">
            <Select value={dateRange} onValueChange={setDateRange}>
              <SelectTrigger className="w-40 bg-muted border-border">
                <SelectValue placeholder="Date Range" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="7d">Last 7 Days</SelectItem>
                <SelectItem value="30d">Last 30 Days</SelectItem>
                <SelectItem value="90d">Last 90 Days</SelectItem>
                <SelectItem value="custom">All Time</SelectItem>
              </SelectContent>
            </Select>

            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-32 bg-muted border-border">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All</SelectItem>
                <SelectItem value="profit">Profit</SelectItem>
                <SelectItem value="loss">Loss</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </Card>

        {/* Stats Row */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {stats.map((stat, i) => (
            <Card key={i} className="p-4 bg-card border-border">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs text-muted-foreground uppercase tracking-wider">{stat.label}</p>
                  <p className={cn(
                    'text-xl font-semibold font-mono-numbers mt-1',
                    stat.positive !== undefined 
                      ? (stat.positive ? 'text-profit' : 'text-loss')
                      : 'text-foreground'
                  )}>
                    {stat.value}
                  </p>
                </div>
                <div className="w-8 h-8 rounded-lg bg-muted flex items-center justify-center">
                  <stat.icon className="w-4 h-4 text-muted-foreground" />
                </div>
              </div>
            </Card>
          ))}
        </div>

        {/* P&L Chart */}
        <Card className="bg-card border-border">
          <CardHeader className="pb-2">
            <CardTitle className="text-base font-medium text-foreground">
              Cumulative P&L
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[250px]">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={pnlData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                  <defs>
                    <linearGradient id="pnlGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="hsl(160, 84%, 39%)" stopOpacity={0.3} />
                      <stop offset="100%" stopColor="hsl(160, 84%, 39%)" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(0, 0%, 15%)" vertical={false} />
                  <XAxis 
                    dataKey="date" 
                    stroke="hsl(0, 0%, 40%)"
                    tick={{ fill: 'hsl(0, 0%, 50%)', fontSize: 11 }}
                    axisLine={{ stroke: 'hsl(0, 0%, 15%)' }}
                    tickLine={false}
                  />
                  <YAxis 
                    stroke="hsl(0, 0%, 40%)"
                    tick={{ fill: 'hsl(0, 0%, 50%)', fontSize: 11 }}
                    axisLine={{ stroke: 'hsl(0, 0%, 15%)' }}
                    tickLine={false}
                    tickFormatter={(value) => `$${value}`}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'hsl(0, 0%, 9%)',
                      border: '1px solid hsl(0, 0%, 20%)',
                      borderRadius: '8px',
                    }}
                    labelStyle={{ color: 'hsl(0, 0%, 70%)' }}
                    formatter={(value: number) => [`$${value.toFixed(2)}`, 'P&L']}
                  />
                  <Area
                    type="monotone"
                    dataKey="pnl"
                    stroke="hsl(160, 84%, 39%)"
                    strokeWidth={2}
                    fill="url(#pnlGradient)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* Closed Positions Table */}
        <Card className="bg-card border-border overflow-hidden">
          <div className="p-4 border-b border-border">
            <h2 className="text-base font-medium text-foreground">Closed Positions</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border bg-muted/30">
                  <th className="text-left py-3 px-4 text-xs uppercase tracking-wider text-muted-foreground font-medium">Market</th>
                  <th className="text-center py-3 px-4 text-xs uppercase tracking-wider text-muted-foreground font-medium">Side</th>
                  <th className="text-right py-3 px-4 text-xs uppercase tracking-wider text-muted-foreground font-medium">Entry</th>
                  <th className="text-right py-3 px-4 text-xs uppercase tracking-wider text-muted-foreground font-medium">Exit</th>
                  <th className="text-right py-3 px-4 text-xs uppercase tracking-wider text-muted-foreground font-medium">Size</th>
                  <th className="text-right py-3 px-4 text-xs uppercase tracking-wider text-muted-foreground font-medium">Realized P&L</th>
                  <th className="text-right py-3 px-4 text-xs uppercase tracking-wider text-muted-foreground font-medium">Duration</th>
                  <th className="text-right py-3 px-4 text-xs uppercase tracking-wider text-muted-foreground font-medium">Closed</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {loading ? (
                  <tr>
                    <td colSpan={8} className="py-16 text-center">
                      <Loader2 className="w-8 h-8 animate-spin text-muted-foreground mx-auto" />
                    </td>
                  </tr>
                ) : filteredPositions.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="py-16 text-center">
                      <p className="text-muted-foreground">No closed positions yet</p>
                      <p className="text-sm text-muted-foreground mt-1">Completed trades will appear here</p>
                    </td>
                  </tr>
                ) : (
                  filteredPositions.map((position) => {
                    const isProfitable = (position.realized_pnl_usdc ?? 0) >= 0;
                    return (
                      <tr key={position.id} className="hover:bg-muted/20 transition-colors">
                        <td className="py-3 px-4">
                          <span className="text-sm font-medium text-foreground">{position.team || position.token_id.slice(0, 12)}...</span>
                        </td>
                        <td className="py-3 px-4 text-center">
                          <Badge className={cn(
                            'border',
                            position.side === 'YES' 
                              ? 'bg-primary/10 text-primary border-primary/20' 
                              : 'bg-destructive/10 text-destructive border-destructive/20'
                          )}>
                            {position.side}
                          </Badge>
                        </td>
                        <td className="py-3 px-4 text-right">
                          <span className="text-sm font-mono-numbers text-muted-foreground">
                            ${position.entry_price.toFixed(2)}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-right">
                          <span className="text-sm font-mono-numbers text-foreground">
                            ${(position.current_price ?? position.entry_price).toFixed(2)}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-right">
                          <span className="text-sm font-mono-numbers text-foreground">
                            ${position.entry_cost_usdc.toFixed(2)}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-right">
                          <span className={cn(
                            'text-sm font-mono-numbers font-medium',
                            isProfitable ? 'text-profit' : 'text-loss'
                          )}>
                            {isProfitable ? '+' : ''}${(position.realized_pnl_usdc ?? 0).toFixed(2)}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-right">
                          <span className="text-sm font-mono-numbers text-muted-foreground">
                            {formatDuration(position.opened_at, position.closed_at ?? null)}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-right">
                          <span className="text-sm text-muted-foreground">
                            {position.closed_at ? new Date(position.closed_at).toLocaleDateString() : '---'}
                          </span>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </Card>
      </div>
    </DashboardLayout>
  );
}
