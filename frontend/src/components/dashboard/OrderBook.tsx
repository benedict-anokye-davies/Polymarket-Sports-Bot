import { useMemo } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { cn } from '@/lib/utils';

interface OrderLevel {
  price: number;
  size: number;
  total: number;
}

const generateOrders = (side: 'bid' | 'ask', count: number): OrderLevel[] => {
  const orders: OrderLevel[] = [];
  let basePrice = side === 'bid' ? 0.68 : 0.72;
  let runningTotal = 0;
  
  for (let i = 0; i < count; i++) {
    const size = Math.floor(Math.random() * 5000) + 500;
    runningTotal += size;
    orders.push({
      price: parseFloat((basePrice + (side === 'bid' ? -i : i) * 0.01).toFixed(2)),
      size,
      total: runningTotal,
    });
  }
  return orders;
};

export function OrderBook() {
  const bids = useMemo(() => generateOrders('bid', 6), []);
  const asks = useMemo(() => generateOrders('ask', 6), []);
  
  const maxTotal = Math.max(
    bids[bids.length - 1]?.total || 0,
    asks[asks.length - 1]?.total || 0
  );

  return (
    <Card className="bg-card border-border">
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-medium text-foreground">Order Book</CardTitle>
      </CardHeader>
      <CardContent className="pt-0">
        <div className="space-y-4">
          {/* Header */}
          <div className="grid grid-cols-3 text-xs text-muted-foreground uppercase tracking-wider pb-2 border-b border-border">
            <span>Price</span>
            <span className="text-right">Size</span>
            <span className="text-right">Total</span>
          </div>
          
          {/* Asks (Sells) - reversed to show highest at top */}
          <div className="space-y-1">
            {[...asks].reverse().map((order, i) => (
              <div
                key={`ask-${i}`}
                className="relative grid grid-cols-3 text-sm py-1.5 rounded"
              >
                <div
                  className="absolute inset-0 bg-destructive/10 rounded"
                  style={{ width: `${(order.total / maxTotal) * 100}%`, right: 0, left: 'auto' }}
                />
                <span className="relative font-mono-numbers text-destructive">${order.price.toFixed(2)}</span>
                <span className="relative font-mono-numbers text-muted-foreground text-right">
                  {order.size.toLocaleString()}
                </span>
                <span className="relative font-mono-numbers text-foreground text-right">
                  {order.total.toLocaleString()}
                </span>
              </div>
            ))}
          </div>
          
          {/* Spread */}
          <div className="py-2 border-y border-border flex items-center justify-center">
            <span className="text-xs text-muted-foreground">
              Spread: <span className="font-mono-numbers text-foreground">$0.04</span> (5.7%)
            </span>
          </div>
          
          {/* Bids (Buys) */}
          <div className="space-y-1">
            {bids.map((order, i) => (
              <div
                key={`bid-${i}`}
                className="relative grid grid-cols-3 text-sm py-1.5 rounded"
              >
                <div
                  className="absolute inset-0 bg-primary/10 rounded"
                  style={{ width: `${(order.total / maxTotal) * 100}%` }}
                />
                <span className="relative font-mono-numbers text-primary">${order.price.toFixed(2)}</span>
                <span className="relative font-mono-numbers text-muted-foreground text-right">
                  {order.size.toLocaleString()}
                </span>
                <span className="relative font-mono-numbers text-foreground text-right">
                  {order.total.toLocaleString()}
                </span>
              </div>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
