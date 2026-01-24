import { useState, useEffect } from 'react';
import { ArrowUpRight, ArrowDownRight, DollarSign, TrendingUp, Briefcase, Calculator, Loader2 } from 'lucide-react';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { apiClient, Position } from '@/api/client';

export default function Positions() {
  const [positions, setPositions] = useState<Position[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [closingId, setClosingId] = useState<string | null>(null);

  useEffect(() => {
    fetchPositions();
    const interval = setInterval(fetchPositions, 30000);
    return () => clearInterval(interval);
  }, []);

  const fetchPositions = async () => {
    try {
      const data = await apiClient.getPositions('open');
      setPositions(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load positions');
    } finally {
      setLoading(false);
    }
  };

  const handleClosePosition = async (positionId: string) => {
    try {
      setClosingId(positionId);
      await apiClient.closePosition(positionId);
      await fetchPositions();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to close position');
    } finally {
      setClosingId(null);
    }
  };

  const totalInvested = positions.reduce((sum, p) => sum + p.entry_cost_usdc, 0);
  const totalPnl = positions.reduce((sum, p) => sum + (p.unrealized_pnl ?? 0), 0);
  const avgEntryPrice = positions.length > 0 
    ? positions.reduce((sum, p) => sum + p.entry_price, 0) / positions.length 
    : 0;

  const stats = [
    { label: 'Total Invested', value: `$${totalInvested.toFixed(2)}`, icon: DollarSign },
    { label: 'Unrealized P&L', value: `${totalPnl >= 0 ? '+' : ''}$${totalPnl.toFixed(2)}`, positive: totalPnl >= 0, icon: TrendingUp },
    { label: 'Active Trades', value: String(positions.length), icon: Briefcase },
    { label: 'Avg Entry Price', value: `$${avgEntryPrice.toFixed(3)}`, icon: Calculator },
  ];

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

        {/* Error Banner */}
        {error && (
          <div className="bg-destructive/10 border border-destructive/20 text-destructive px-4 py-3 rounded-lg">
            {error}
          </div>
        )}

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
                    {loading ? '...' : stat.value}
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
            {loading ? (
              <div className="flex items-center justify-center py-16">
                <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
              </div>
            ) : positions.length === 0 ? (
              <div className="text-center py-16">
                <p className="text-muted-foreground">No open positions</p>
                <p className="text-sm text-muted-foreground mt-1">Positions will appear here when the bot enters trades</p>
              </div>
            ) : (
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
                  {positions.map((position) => {
                    const pnl = position.unrealized_pnl ?? 0;
                    const isProfitable = pnl >= 0;
                    const pnlPercent = position.entry_price > 0 
                      ? ((position.current_price ?? position.entry_price) - position.entry_price) / position.entry_price * 100
                      : 0;
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
                                {isProfitable ? '+' : ''}{pnlPercent.toFixed(2)}%
                              </p>
                              <p className={cn(
                                'text-xs font-mono-numbers',
                                isProfitable ? 'text-profit' : 'text-loss'
                              )}>
                                {isProfitable ? '+' : ''}${pnl.toFixed(2)}
                              </p>
                            </div>
                          </div>
                        </td>
                        <td className="py-3 px-4 text-right">
                          <span className="text-sm text-muted-foreground">
                            {new Date(position.opened_at).toLocaleDateString()}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-center">
                          <Button 
                            variant="outline" 
                            size="sm" 
                            className="border-border hover:bg-muted"
                            onClick={() => handleClosePosition(position.id)}
                            disabled={closingId === position.id}
                          >
                            {closingId === position.id ? (
                              <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                              'Close'
                            )}
                          </Button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        </Card>
      </div>
    </DashboardLayout>
  );
}
