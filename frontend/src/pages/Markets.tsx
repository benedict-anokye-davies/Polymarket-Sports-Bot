import { useState, useEffect } from 'react';
import { Search, RefreshCw, Eye, EyeOff, Loader2 } from 'lucide-react';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
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
import { apiClient, Market } from '@/api/client';

const statusStyles = {
  LIVE: 'bg-primary/10 text-primary border-primary/20',
  UPCOMING: 'bg-info/10 text-info border-info/20',
  FINISHED: 'bg-muted text-muted-foreground border-border',
};

export default function Markets() {
  const [markets, setMarkets] = useState<Market[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sportFilter, setSportFilter] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [togglingId, setTogglingId] = useState<string | null>(null);

  useEffect(() => {
    fetchMarkets();
  }, [sportFilter]);

  const fetchMarkets = async () => {
    try {
      setLoading(true);
      const sport = sportFilter !== 'all' ? sportFilter.toLowerCase() : undefined;
      const data = await apiClient.getMarkets(sport);
      setMarkets(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load markets');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const handleRefresh = () => {
    setRefreshing(true);
    fetchMarkets();
  };

  const toggleTracking = async (conditionId: string, currentlyTracked: boolean) => {
    try {
      setTogglingId(conditionId);
      if (currentlyTracked) {
        await apiClient.untrackMarket(conditionId);
      } else {
        await apiClient.trackMarket(conditionId);
      }
      setMarkets(markets.map(m => 
        m.condition_id === conditionId ? { ...m, is_tracked: !m.is_tracked } : m
      ));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update tracking');
    } finally {
      setTogglingId(null);
    }
  };

  const filteredMarkets = markets.filter((market) => {
    const matchesSearch = 
      market.question.toLowerCase().includes(searchQuery.toLowerCase()) ||
      market.home_team?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      market.away_team?.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesSearch;
  });

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Page Header */}
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Markets</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Browse and track prediction markets
          </p>
        </div>

        {/* Error Banner */}
        {error && (
          <div className="bg-destructive/10 border border-destructive/20 text-destructive px-4 py-3 rounded-lg">
            {error}
          </div>
        )}

        {/* Filters */}
        <Card className="p-4 bg-card border-border">
          <div className="flex flex-wrap items-center gap-4">
            <Select value={sportFilter} onValueChange={setSportFilter}>
              <SelectTrigger className="w-40 bg-muted border-border">
                <SelectValue placeholder="All Sports" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Sports</SelectItem>
                <SelectItem value="NBA">NBA</SelectItem>
                <SelectItem value="NFL">NFL</SelectItem>
                <SelectItem value="MLB">MLB</SelectItem>
                <SelectItem value="NHL">NHL</SelectItem>
                <SelectItem value="NCAAB">NCAA CBB</SelectItem>
                <SelectItem value="Soccer">Soccer</SelectItem>
                <SelectItem value="Tennis">Tennis</SelectItem>
                <SelectItem value="Cricket">Cricket</SelectItem>
                <SelectItem value="UFC">UFC</SelectItem>
              </SelectContent>
            </Select>

            <div className="relative flex-1 max-w-xs">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                placeholder="Search markets..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9 bg-muted border-border"
              />
            </div>

            <Button 
              variant="outline" 
              size="icon" 
              className="border-border hover:bg-muted"
              onClick={handleRefresh}
              disabled={refreshing}
            >
              <RefreshCw className={cn("w-4 h-4", refreshing && "animate-spin")} />
            </Button>
          </div>
        </Card>

        {/* Markets Table */}
        <Card className="bg-card border-border overflow-hidden">
          <div className="overflow-x-auto">
            {loading ? (
              <div className="flex items-center justify-center py-16">
                <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
              </div>
            ) : filteredMarkets.length === 0 ? (
              <div className="text-center py-16">
                <p className="text-muted-foreground">No markets found</p>
                <p className="text-sm text-muted-foreground mt-1">Markets will appear here when discovered by the bot</p>
              </div>
            ) : (
            <table className="w-full">
              <thead>
                <tr className="border-b border-border bg-muted/30">
                  <th className="text-left py-3 px-4 text-xs uppercase tracking-wider text-muted-foreground font-medium">Market</th>
                  <th className="text-left py-3 px-4 text-xs uppercase tracking-wider text-muted-foreground font-medium">Sport</th>
                  <th className="text-right py-3 px-4 text-xs uppercase tracking-wider text-muted-foreground font-medium">Baseline</th>
                  <th className="text-right py-3 px-4 text-xs uppercase tracking-wider text-muted-foreground font-medium">Current</th>
                  <th className="text-center py-3 px-4 text-xs uppercase tracking-wider text-muted-foreground font-medium">Status</th>
                  <th className="text-center py-3 px-4 text-xs uppercase tracking-wider text-muted-foreground font-medium">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {filteredMarkets.map((market) => {
                  const status = market.is_live ? 'LIVE' : 'UPCOMING';
                  return (
                  <tr 
                    key={market.id} 
                    className="hover:bg-muted/20 transition-colors"
                  >
                    <td className="py-3 px-4">
                      <span className="text-sm font-medium text-foreground">
                        {market.away_team && market.home_team 
                          ? `${market.away_team} @ ${market.home_team}`
                          : market.question}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <Badge variant="outline" className="border-border text-muted-foreground">
                        {market.sport.toUpperCase()}
                      </Badge>
                    </td>
                    <td className="py-3 px-4 text-right">
                      <span className="text-sm font-mono-numbers text-muted-foreground">
                        {(market.baseline_price_yes * 100).toFixed(0)}%
                      </span>
                    </td>
                    <td className="py-3 px-4 text-right">
                      <span className={cn(
                        'text-sm font-mono-numbers font-medium',
                        market.current_price_yes > market.baseline_price_yes ? 'text-profit' : 'text-loss'
                      )}>
                        {(market.current_price_yes * 100).toFixed(0)}%
                      </span>
                    </td>
                    <td className="py-3 px-4 text-center">
                      <Badge className={cn('border', statusStyles[status])}>
                        {status}
                      </Badge>
                    </td>
                    <td className="py-3 px-4 text-center">
                      <Button
                        variant={market.is_tracked ? 'default' : 'outline'}
                        size="sm"
                        onClick={() => toggleTracking(market.condition_id, market.is_tracked)}
                        disabled={togglingId === market.condition_id}
                        className={cn(
                          'gap-1.5',
                          market.is_tracked 
                            ? 'bg-primary hover:bg-primary/90' 
                            : 'border-border hover:bg-muted'
                        )}
                      >
                        {togglingId === market.condition_id ? (
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        ) : market.is_tracked ? (
                          <>
                            <Eye className="w-3.5 h-3.5" />
                            Tracking
                          </>
                        ) : (
                          <>
                            <EyeOff className="w-3.5 h-3.5" />
                            Track
                          </>
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
