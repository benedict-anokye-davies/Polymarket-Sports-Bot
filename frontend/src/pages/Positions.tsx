import { ArrowUpRight, ArrowDownRight, DollarSign, TrendingUp, Briefcase, Calculator } from 'lucide-react';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

interface Position {
  id: string;
  market: string;
  side: 'YES' | 'NO';
  entryPrice: number;
  currentPrice: number;
  size: number;
  pnlPercent: number;
  pnlDollar: number;
  openedAt: string;
}

const mockPositions: Position[] = [
  { id: '1', market: 'Lakers vs Celtics', side: 'YES', entryPrice: 0.52, currentPrice: 0.68, size: 1500, pnlPercent: 30.77, pnlDollar: 240, openedAt: '2 hours ago' },
  { id: '2', market: 'Warriors vs Heat', side: 'NO', entryPrice: 0.45, currentPrice: 0.42, size: 2000, pnlPercent: 6.67, pnlDollar: 60, openedAt: '4 hours ago' },
  { id: '3', market: 'Chiefs vs 49ers', side: 'YES', entryPrice: 0.60, currentPrice: 0.55, size: 1000, pnlPercent: -8.33, pnlDollar: -50, openedAt: '1 day ago' },
  { id: '4', market: 'Yankees vs Red Sox', side: 'YES', entryPrice: 0.48, currentPrice: 0.52, size: 750, pnlPercent: 8.33, pnlDollar: 30, openedAt: '3 hours ago' },
  { id: '5', market: 'Eagles vs Cowboys', side: 'NO', entryPrice: 0.38, currentPrice: 0.42, size: 1200, pnlPercent: -10.53, pnlDollar: -48, openedAt: '6 hours ago' },
];

const stats = [
  { label: 'Total Invested', value: '$6,450', icon: DollarSign },
  { label: 'Unrealized P&L', value: '+$232', positive: true, icon: TrendingUp },
  { label: 'Active Trades', value: '5', icon: Briefcase },
  { label: 'Avg Entry Price', value: '$0.486', icon: Calculator },
];

export default function Positions() {
  const totalPnl = mockPositions.reduce((sum, p) => sum + p.pnlDollar, 0);

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Page Header */}
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Positions</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Manage your open trading positions
          </p>
        </div>

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

        {/* Positions Table */}
        <Card className="bg-card border-border overflow-hidden">
          <div className="p-4 border-b border-border flex items-center justify-between">
            <h2 className="text-base font-medium text-foreground">Open Positions</h2>
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">Total P&L:</span>
              <span className={cn(
                'text-sm font-mono-numbers font-medium',
                totalPnl >= 0 ? 'text-profit' : 'text-loss'
              )}>
                {totalPnl >= 0 ? '+' : ''}${totalPnl.toFixed(2)}
              </span>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border bg-muted/30">
                  <th className="text-left py-3 px-4 text-xs uppercase tracking-wider text-muted-foreground font-medium">Market</th>
                  <th className="text-center py-3 px-4 text-xs uppercase tracking-wider text-muted-foreground font-medium">Side</th>
                  <th className="text-right py-3 px-4 text-xs uppercase tracking-wider text-muted-foreground font-medium">Entry</th>
                  <th className="text-right py-3 px-4 text-xs uppercase tracking-wider text-muted-foreground font-medium">Current</th>
                  <th className="text-right py-3 px-4 text-xs uppercase tracking-wider text-muted-foreground font-medium">Size</th>
                  <th className="text-right py-3 px-4 text-xs uppercase tracking-wider text-muted-foreground font-medium">P&L</th>
                  <th className="text-right py-3 px-4 text-xs uppercase tracking-wider text-muted-foreground font-medium">Opened</th>
                  <th className="text-center py-3 px-4 text-xs uppercase tracking-wider text-muted-foreground font-medium">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {mockPositions.map((position) => {
                  const isProfitable = position.pnlDollar >= 0;
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
                          ${position.entryPrice.toFixed(2)}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-right">
                        <span className="text-sm font-mono-numbers text-foreground">
                          ${position.currentPrice.toFixed(2)}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-right">
                        <span className="text-sm font-mono-numbers text-foreground">
                          ${position.size.toLocaleString()}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-right">
                        <div className="flex items-center justify-end gap-1">
                          {isProfitable ? (
                            <ArrowUpRight className="w-4 h-4 text-profit" />
                          ) : (
                            <ArrowDownRight className="w-4 h-4 text-loss" />
                          )}
                          <div className="text-right">
                            <p className={cn(
                              'text-sm font-mono-numbers font-medium',
                              isProfitable ? 'text-profit' : 'text-loss'
                            )}>
                              {isProfitable ? '+' : ''}{position.pnlPercent.toFixed(2)}%
                            </p>
                            <p className={cn(
                              'text-xs font-mono-numbers',
                              isProfitable ? 'text-profit' : 'text-loss'
                            )}>
                              {isProfitable ? '+' : ''}${position.pnlDollar.toFixed(2)}
                            </p>
                          </div>
                        </div>
                      </td>
                      <td className="py-3 px-4 text-right">
                        <span className="text-sm text-muted-foreground">{position.openedAt}</span>
                      </td>
                      <td className="py-3 px-4 text-center">
                        <Button variant="outline" size="sm" className="border-border hover:bg-muted">
                          Close
                        </Button>
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
