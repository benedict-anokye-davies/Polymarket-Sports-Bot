import { useState, useEffect } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import { Loader2 } from 'lucide-react';
import { apiClient, Market } from '@/api/client';

const sportColors: Record<string, string> = {
  nba: 'text-orange-400',
  nfl: 'text-green-400',
  mlb: 'text-red-400',
  nhl: 'text-blue-400',
  ncaab: 'text-orange-400',
  ncaaf: 'text-green-400',
  soccer: 'text-purple-400',
  mma: 'text-red-400',
};

export function LiveGames() {
  const [markets, setMarkets] = useState<Market[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchLiveMarkets = async () => {
      try {
        const data = await apiClient.getMarkets();
        // Filter to only live markets
        const liveMarkets = data.filter(m => m.is_live);
        setMarkets(liveMarkets.slice(0, 6)); // Show top 6
      } catch (err) {
        console.error('Failed to fetch live markets:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchLiveMarkets();
    const interval = setInterval(fetchLiveMarkets, 30000);
    return () => clearInterval(interval);
  }, []);

  return (
    <Card className="bg-card border-border h-full">
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-medium text-foreground flex items-center gap-2">
          <span className="status-dot bg-primary status-dot-pulse" />
          Live Games
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-0">
        {loading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
          </div>
        ) : markets.length === 0 ? (
          <div className="text-center py-8">
            <p className="text-sm text-muted-foreground">No live games at the moment</p>
            <p className="text-xs text-muted-foreground mt-1">Games will appear here when live</p>
          </div>
        ) : (
        <div className="max-h-[320px] overflow-y-auto scrollbar-thin space-y-2">
          {markets.map((market) => (
            <div
              key={market.id}
              className="p-3 rounded-md bg-muted/30 hover:bg-muted/50 transition-colors border border-transparent hover:border-border"
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className={cn('text-xs font-medium', sportColors[market.sport.toLowerCase()] || 'text-gray-400')}>
                    {market.sport.toUpperCase()}
                  </span>
                  <span className="text-sm text-foreground font-medium">
                    {market.away_team && market.home_team 
                      ? `${market.away_team} @ ${market.home_team}`
                      : market.question.slice(0, 30)}
                  </span>
                </div>
                <span className="text-xs text-muted-foreground font-mono-numbers">
                  LIVE
                </span>
              </div>
              
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">
                  {market.is_tracked ? 'Tracked' : 'Not tracked'}
                </span>
                <div className="flex items-center gap-2">
                  <div className="w-24 h-2 bg-muted rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-primary/80 to-primary rounded-full transition-all duration-300"
                      style={{ width: `${market.current_price_yes * 100}%` }}
                    />
                  </div>
                  <span className="text-sm font-mono-numbers text-primary w-12 text-right">
                    {(market.current_price_yes * 100).toFixed(0)}%
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
        )}
      </CardContent>
    </Card>
  );
}
