import { useMemo } from 'react';
import { Download, Trophy, TrendingUp, Clock, Target } from 'lucide-react';
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

interface ClosedPosition {
  id: string;
  market: string;
  side: 'YES' | 'NO';
  entry: number;
  exit: number;
  size: number;
  realizedPnl: number;
  duration: string;
  closedAt: string;
}

const mockHistory: ClosedPosition[] = [
  { id: '1', market: 'Suns vs Nuggets', side: 'YES', entry: 0.45, exit: 0.72, size: 2000, realizedPnl: 540, duration: '4h 32m', closedAt: 'Jan 20, 2024' },
  { id: '2', market: 'Bills vs Dolphins', side: 'NO', entry: 0.55, exit: 0.38, size: 1500, realizedPnl: 255, duration: '2h 15m', closedAt: 'Jan 19, 2024' },
  { id: '3', market: 'Mets vs Braves', side: 'YES', entry: 0.52, exit: 0.48, size: 1000, realizedPnl: -40, duration: '5h 45m', closedAt: 'Jan 19, 2024' },
  { id: '4', market: 'Bruins vs Rangers', side: 'YES', entry: 0.60, exit: 0.78, size: 800, realizedPnl: 144, duration: '3h 20m', closedAt: 'Jan 18, 2024' },
  { id: '5', market: 'Packers vs Lions', side: 'NO', entry: 0.42, exit: 0.51, size: 1200, realizedPnl: -108, duration: '6h 10m', closedAt: 'Jan 17, 2024' },
  { id: '6', market: 'Celtics vs Heat', side: 'YES', entry: 0.58, exit: 0.82, size: 1800, realizedPnl: 432, duration: '1h 55m', closedAt: 'Jan 16, 2024' },
];

const generatePnlData = () => {
  const data = [];
  let cumulative = 0;
  for (let i = 30; i >= 0; i--) {
    const date = new Date();
    date.setDate(date.getDate() - i);
    const dailyPnl = (Math.random() - 0.35) * 500;
    cumulative += dailyPnl;
    data.push({
      date: date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
      pnl: parseFloat(cumulative.toFixed(2)),
    });
  }
  return data;
};

const stats = [
  { label: 'Total Trades', value: '156', icon: Target },
  { label: 'Win Rate', value: '68.2%', icon: Trophy },
  { label: 'Total P&L', value: '+$4,823', positive: true, icon: TrendingUp },
  { label: 'Avg Duration', value: '3h 42m', icon: Clock },
];

export default function History() {
  const pnlData = useMemo(() => generatePnlData(), []);

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
          <Button variant="outline" className="border-border hover:bg-muted gap-2">
            <Download className="w-4 h-4" />
            Export CSV
          </Button>
        </div>

        {/* Filters */}
        <Card className="p-4 bg-card border-border">
          <div className="flex flex-wrap items-center gap-4">
            <Select defaultValue="30d">
              <SelectTrigger className="w-40 bg-muted border-border">
                <SelectValue placeholder="Date Range" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="7d">Last 7 Days</SelectItem>
                <SelectItem value="30d">Last 30 Days</SelectItem>
                <SelectItem value="90d">Last 90 Days</SelectItem>
                <SelectItem value="custom">Custom Range</SelectItem>
              </SelectContent>
            </Select>

            <Select defaultValue="all">
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
                {mockHistory.map((position) => {
                  const isProfitable = position.realizedPnl >= 0;
                  return (
                    <tr key={position.id} className="hover:bg-muted/20 transition-colors">
                      <td className="py-3 px-4">
                        <span className="text-sm font-medium text-foreground">{position.market}</span>
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
                          ${position.entry.toFixed(2)}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-right">
                        <span className="text-sm font-mono-numbers text-foreground">
                          ${position.exit.toFixed(2)}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-right">
                        <span className="text-sm font-mono-numbers text-foreground">
                          ${position.size.toLocaleString()}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-right">
                        <span className={cn(
                          'text-sm font-mono-numbers font-medium',
                          isProfitable ? 'text-profit' : 'text-loss'
                        )}>
                          {isProfitable ? '+' : ''}${position.realizedPnl.toFixed(2)}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-right">
                        <span className="text-sm font-mono-numbers text-muted-foreground">
                          {position.duration}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-right">
                        <span className="text-sm text-muted-foreground">{position.closedAt}</span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      </div>
    </DashboardLayout>
  );
}
