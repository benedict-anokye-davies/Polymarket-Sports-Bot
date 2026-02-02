import { useState, useEffect } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { apiClient, Market } from '@/api/client';
import { Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

export function OrderBook() {
  const [market, setMarket] = useState<Market | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchMarket = async () => {
      try {
        const markets = await apiClient.getMarkets();
        // Find the first live market to display
        const liveMarket = markets.find(m => m.is_live && m.current_price_yes > 0) || markets[0];
        setMarket(liveMarket || null);
      } catch (err) {
        console.error('Failed to fetch market for order book:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchMarket();
    const interval = setInterval(fetchMarket, 5000); // 5s refresh for price updates
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <Card className="bg-card border-border h-full">
        <CardHeader className="pb-2">
          <CardTitle className="text-base font-medium text-foreground">Order Book</CardTitle>
        </CardHeader>
        <CardContent className="pt-0 flex items-center justify-center h-[200px]">
          <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="bg-card border-border h-full">
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-medium text-foreground">
          {market ? 'Live Prices' : 'Order Book'}
        </CardTitle>
        <p className="text-xs text-muted-foreground truncate">
          {market ? market.question : 'No market selected'}
        </p>
      </CardHeader>
      <CardContent className="pt-0">
        <div className="space-y-4">
          {/* Header */}
          <div className="grid grid-cols-3 text-xs text-muted-foreground uppercase tracking-wider pb-2 border-b border-border">
            <span>Outcome</span>
            <span className="text-right">Price</span>
            <span className="text-right">Action</span>
          </div>

          {market ? (
            <div className="space-y-2">
              {[
                { outcome: 'YES', price: market.current_price_yes, type: 'bid', color: 'text-green-500' },
                { outcome: 'NO', price: market.current_price_no, type: 'ask', color: 'text-red-500' }
              ].map((item) => (
                <div key={item.outcome} className="grid grid-cols-3 items-center py-2 hover:bg-muted/30 rounded-sm px-1">
                  <span className={cn("font-medium", item.color)}>{item.outcome}</span>
                  <span className="text-right font-mono text-sm">
                    {(item.price * 100).toFixed(1)}¢
                  </span>
                  <div className="text-right">
                    <span className={cn(
                      "text-xs px-2 py-0.5 rounded text-background font-medium",
                      item.outcome === 'YES' ? "bg-green-500" : "bg-red-500"
                    )}>
                      {item.outcome === 'YES' ? 'BUY' : 'SELL'}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            /* Empty State */
            <div className="py-8 text-center">
              <p className="text-sm text-muted-foreground">No active markets found</p>
              <p className="text-xs text-muted-foreground mt-1">Start tracking a market to see prices</p>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
