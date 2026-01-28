import { useState, useEffect } from 'react';
import { BarChart3, TrendingUp, TrendingDown, DollarSign, Target, Calendar, Loader2 } from 'lucide-react';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { apiClient } from '@/api/client';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  Legend,
} from 'recharts';

interface PerformanceMetrics {
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate: number;
  total_pnl: number;
  gross_profit: number;
  gross_loss: number;
  avg_win: number;
  avg_loss: number;
  profit_factor: number;
  largest_win: number;
  largest_loss: number;
  avg_trade_duration_hours: number;
  current_streak: number;
  max_win_streak: number;
  max_lose_streak: number;
  max_drawdown: number;
  roi_pct: number;
  sharpe_ratio: number | null;
  calmar_ratio: number | null;
}

interface SportPerformance {
  sport: string;
  total_trades: number;
  win_rate: number;
  total_pnl: number;
  avg_return: number;
}

interface EquityPoint {
  timestamp: string;
  equity: number;
  drawdown: number;
}

interface DailyPnL {
  date: string;
  pnl: number;
}

export default function Analytics() {
  const [metrics, setMetrics] = useState<PerformanceMetrics | null>(null);
  const [sportBreakdown, setSportBreakdown] = useState<SportPerformance[]>([]);
  const [equityCurve, setEquityCurve] = useState<EquityPoint[]>([]);
  const [dailyPnL, setDailyPnL] = useState<DailyPnL[]>([]);
  const [loading, setLoading] = useState(true);
  const [timeframe, setTimeframe] = useState('30');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchAnalytics();
  }, [timeframe]);

  const fetchAnalytics = async () => {
    try {
      setLoading(true);
      
      const [metricsRes, sportsRes, equityRes, dailyRes] = await Promise.all([
        fetch('/api/v1/analytics/performance', {
          headers: { Authorization: `Bearer ${localStorage.getItem('auth_token')}` },
        }),
        fetch('/api/v1/analytics/sports', {
          headers: { Authorization: `Bearer ${localStorage.getItem('auth_token')}` },
        }),
        fetch('/api/v1/analytics/equity-curve', {
          headers: { Authorization: `Bearer ${localStorage.getItem('auth_token')}` },
        }),
        fetch(`/api/v1/analytics/daily-pnl?days=${timeframe}`, {
          headers: { Authorization: `Bearer ${localStorage.getItem('auth_token')}` },
        }),
      ]);

      if (metricsRes.ok) setMetrics(await metricsRes.json());
      if (sportsRes.ok) setSportBreakdown(await sportsRes.json());
      if (equityRes.ok) setEquityCurve(await equityRes.json());
      if (dailyRes.ok) setDailyPnL(await dailyRes.json());
      
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load analytics');
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(value);
  };

  const formatPercent = (value: number) => {
    return `${(value * 100).toFixed(1)}%`;
  };

  if (loading) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center h-64">
          <Loader2 className="w-8 h-8 animate-spin text-primary" />
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-foreground">Analytics</h1>
            <p className="text-sm text-muted-foreground mt-1">
              Detailed performance metrics and trade analysis
            </p>
          </div>
          <Select value={timeframe} onValueChange={setTimeframe}>
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder="Select timeframe" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="7">Last 7 days</SelectItem>
              <SelectItem value="30">Last 30 days</SelectItem>
              <SelectItem value="90">Last 90 days</SelectItem>
              <SelectItem value="365">Last year</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Key Metrics Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Total P&L</CardTitle>
              <DollarSign className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className={`text-2xl font-bold ${(metrics?.total_pnl ?? 0) >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                {formatCurrency(metrics?.total_pnl ?? 0)}
              </div>
              <p className="text-xs text-muted-foreground">
                ROI: {metrics?.roi_pct?.toFixed(1) ?? 0}%
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Win Rate</CardTitle>
              <Target className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {formatPercent(metrics?.win_rate ?? 0)}
              </div>
              <p className="text-xs text-muted-foreground">
                {metrics?.winning_trades ?? 0}W / {metrics?.losing_trades ?? 0}L
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Profit Factor</CardTitle>
              <TrendingUp className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {metrics?.profit_factor?.toFixed(2) ?? 0}
              </div>
              <p className="text-xs text-muted-foreground">
                Avg Win: {formatCurrency(metrics?.avg_win ?? 0)}
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Max Drawdown</CardTitle>
              <TrendingDown className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-red-500">
                -{metrics?.max_drawdown?.toFixed(1) ?? 0}%
              </div>
              <p className="text-xs text-muted-foreground">
                Sharpe: {metrics?.sharpe_ratio?.toFixed(2) ?? 'N/A'}
              </p>
            </CardContent>
          </Card>
        </div>

        {/* Charts */}
        <Tabs defaultValue="equity" className="space-y-4">
          <TabsList>
            <TabsTrigger value="equity">Equity Curve</TabsTrigger>
            <TabsTrigger value="daily">Daily P&L</TabsTrigger>
            <TabsTrigger value="sports">By Sport</TabsTrigger>
          </TabsList>

          <TabsContent value="equity" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Equity Curve</CardTitle>
                <CardDescription>Portfolio value over time</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="h-[400px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={equityCurve}>
                      <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                      <XAxis 
                        dataKey="timestamp" 
                        tickFormatter={(v) => new Date(v).toLocaleDateString()}
                        className="text-xs"
                      />
                      <YAxis 
                        tickFormatter={(v) => `$${v}`}
                        className="text-xs"
                      />
                      <Tooltip 
                        formatter={(value: number) => [formatCurrency(value), 'Equity']}
                        labelFormatter={(label) => new Date(label).toLocaleString()}
                      />
                      <Line 
                        type="monotone" 
                        dataKey="equity" 
                        stroke="hsl(var(--primary))" 
                        strokeWidth={2}
                        dot={false}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="daily" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Daily P&L</CardTitle>
                <CardDescription>Profit and loss by day</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="h-[400px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={dailyPnL}>
                      <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                      <XAxis 
                        dataKey="date" 
                        tickFormatter={(v) => new Date(v).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                        className="text-xs"
                      />
                      <YAxis 
                        tickFormatter={(v) => `$${v}`}
                        className="text-xs"
                      />
                      <Tooltip 
                        formatter={(value: number) => [formatCurrency(value), 'P&L']}
                      />
                      <Bar 
                        dataKey="pnl" 
                        fill="hsl(var(--primary))"
                        radius={[4, 4, 0, 0]}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="sports" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Performance by Sport</CardTitle>
                <CardDescription>Breakdown of results across different sports</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {sportBreakdown.length === 0 ? (
                    <p className="text-muted-foreground text-center py-8">
                      No sport-specific data available yet
                    </p>
                  ) : (
                    sportBreakdown.map((sport) => (
                      <div 
                        key={sport.sport}
                        className="flex items-center justify-between p-4 bg-muted/50 rounded-lg"
                      >
                        <div>
                          <p className="font-medium capitalize">{sport.sport}</p>
                          <p className="text-sm text-muted-foreground">
                            {sport.total_trades} trades | {formatPercent(sport.win_rate)} win rate
                          </p>
                        </div>
                        <div className={`text-lg font-semibold ${sport.total_pnl >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                          {formatCurrency(sport.total_pnl)}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>

        {/* Additional Stats */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Card>
            <CardHeader>
              <CardTitle>Trade Statistics</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Total Trades</span>
                <span className="font-medium">{metrics?.total_trades ?? 0}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Average Win</span>
                <span className="font-medium text-green-500">{formatCurrency(metrics?.avg_win ?? 0)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Average Loss</span>
                <span className="font-medium text-red-500">-{formatCurrency(metrics?.avg_loss ?? 0)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Largest Win</span>
                <span className="font-medium text-green-500">{formatCurrency(metrics?.largest_win ?? 0)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Largest Loss</span>
                <span className="font-medium text-red-500">-{formatCurrency(metrics?.largest_loss ?? 0)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Avg Trade Duration</span>
                <span className="font-medium">{metrics?.avg_trade_duration_hours?.toFixed(1) ?? 0}h</span>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Streak Analysis</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Current Streak</span>
                <span className={`font-medium ${(metrics?.current_streak ?? 0) >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                  {metrics?.current_streak ?? 0} {(metrics?.current_streak ?? 0) >= 0 ? 'wins' : 'losses'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Max Win Streak</span>
                <span className="font-medium text-green-500">{metrics?.max_win_streak ?? 0}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Max Lose Streak</span>
                <span className="font-medium text-red-500">{metrics?.max_lose_streak ?? 0}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Gross Profit</span>
                <span className="font-medium text-green-500">{formatCurrency(metrics?.gross_profit ?? 0)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Gross Loss</span>
                <span className="font-medium text-red-500">-{formatCurrency(metrics?.gross_loss ?? 0)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Calmar Ratio</span>
                <span className="font-medium">{metrics?.calmar_ratio?.toFixed(2) ?? 'N/A'}</span>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </DashboardLayout>
  );
}
