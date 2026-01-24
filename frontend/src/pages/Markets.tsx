import { useState } from 'react';
import { Search, RefreshCw, Eye, EyeOff } from 'lucide-react';
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

interface Market {
  id: string;
  teams: string;
  sport: 'NBA' | 'NFL' | 'MLB' | 'NHL';
  volume: number;
  baseline: number;
  current: number;
  status: 'LIVE' | 'UPCOMING' | 'FINISHED';
  tracked: boolean;
}

const mockMarkets: Market[] = [
  { id: '1', teams: 'Lakers vs Celtics', sport: 'NBA', volume: 125400, baseline: 0.52, current: 0.68, status: 'LIVE', tracked: true },
  { id: '2', teams: 'Warriors vs Heat', sport: 'NBA', volume: 89200, baseline: 0.48, current: 0.55, status: 'LIVE', tracked: true },
  { id: '3', teams: 'Chiefs vs 49ers', sport: 'NFL', volume: 234500, baseline: 0.55, current: 0.62, status: 'UPCOMING', tracked: false },
  { id: '4', teams: 'Yankees vs Red Sox', sport: 'MLB', volume: 67800, baseline: 0.50, current: 0.48, status: 'LIVE', tracked: true },
  { id: '5', teams: 'Maple Leafs vs Canadiens', sport: 'NHL', volume: 45600, baseline: 0.58, current: 0.51, status: 'LIVE', tracked: false },
  { id: '6', teams: 'Knicks vs Bulls', sport: 'NBA', volume: 78900, baseline: 0.45, current: 0.42, status: 'FINISHED', tracked: false },
  { id: '7', teams: 'Eagles vs Cowboys', sport: 'NFL', volume: 189000, baseline: 0.52, current: 0.58, status: 'UPCOMING', tracked: true },
  { id: '8', teams: 'Dodgers vs Giants', sport: 'MLB', volume: 56700, baseline: 0.54, current: 0.61, status: 'UPCOMING', tracked: false },
];

const statusStyles = {
  LIVE: 'bg-primary/10 text-primary border-primary/20',
  UPCOMING: 'bg-info/10 text-info border-info/20',
  FINISHED: 'bg-muted text-muted-foreground border-border',
};

export default function Markets() {
  const [markets, setMarkets] = useState(mockMarkets);
  const [sportFilter, setSportFilter] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');

  const filteredMarkets = markets.filter((market) => {
    const matchesSport = sportFilter === 'all' || market.sport === sportFilter;
    const matchesSearch = market.teams.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesSport && matchesSearch;
  });

  const toggleTracking = (id: string) => {
    setMarkets(markets.map(m => 
      m.id === id ? { ...m, tracked: !m.tracked } : m
    ));
  };

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

            <Button variant="outline" size="icon" className="border-border hover:bg-muted">
              <RefreshCw className="w-4 h-4" />
            </Button>
          </div>
        </Card>

        {/* Markets Table */}
        <Card className="bg-card border-border overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border bg-muted/30">
                  <th className="text-left py-3 px-4 text-xs uppercase tracking-wider text-muted-foreground font-medium">Market</th>
                  <th className="text-left py-3 px-4 text-xs uppercase tracking-wider text-muted-foreground font-medium">Sport</th>
                  <th className="text-right py-3 px-4 text-xs uppercase tracking-wider text-muted-foreground font-medium">Volume</th>
                  <th className="text-right py-3 px-4 text-xs uppercase tracking-wider text-muted-foreground font-medium">Baseline</th>
                  <th className="text-right py-3 px-4 text-xs uppercase tracking-wider text-muted-foreground font-medium">Current</th>
                  <th className="text-center py-3 px-4 text-xs uppercase tracking-wider text-muted-foreground font-medium">Status</th>
                  <th className="text-center py-3 px-4 text-xs uppercase tracking-wider text-muted-foreground font-medium">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {filteredMarkets.map((market) => (
                  <tr 
                    key={market.id} 
                    className="hover:bg-muted/20 transition-colors"
                  >
                    <td className="py-3 px-4">
                      <span className="text-sm font-medium text-foreground">{market.teams}</span>
                    </td>
                    <td className="py-3 px-4">
                      <Badge variant="outline" className="border-border text-muted-foreground">
                        {market.sport}
                      </Badge>
                    </td>
                    <td className="py-3 px-4 text-right">
                      <span className="text-sm font-mono-numbers text-foreground">
                        ${market.volume.toLocaleString()}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-right">
                      <span className="text-sm font-mono-numbers text-muted-foreground">
                        {(market.baseline * 100).toFixed(0)}%
                      </span>
                    </td>
                    <td className="py-3 px-4 text-right">
                      <span className={cn(
                        'text-sm font-mono-numbers font-medium',
                        market.current > market.baseline ? 'text-profit' : 'text-loss'
                      )}>
                        {(market.current * 100).toFixed(0)}%
                      </span>
                    </td>
                    <td className="py-3 px-4 text-center">
                      <Badge className={cn('border', statusStyles[market.status])}>
                        {market.status}
                      </Badge>
                    </td>
                    <td className="py-3 px-4 text-center">
                      <Button
                        variant={market.tracked ? 'default' : 'outline'}
                        size="sm"
                        onClick={() => toggleTracking(market.id)}
                        className={cn(
                          'gap-1.5',
                          market.tracked 
                            ? 'bg-primary hover:bg-primary/90' 
                            : 'border-border hover:bg-muted'
                        )}
                      >
                        {market.tracked ? (
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
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>
    </DashboardLayout>
  );
}
