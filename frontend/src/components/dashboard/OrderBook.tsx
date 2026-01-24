import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';

export function OrderBook() {
  return (
    <Card className="bg-card border-border">
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-medium text-foreground">Order Book</CardTitle>
        <p className="text-xs text-muted-foreground">Select a market to view order book</p>
      </CardHeader>
      <CardContent className="pt-0">
        <div className="space-y-4">
          {/* Header */}
          <div className="grid grid-cols-3 text-xs text-muted-foreground uppercase tracking-wider pb-2 border-b border-border">
            <span>Price</span>
            <span className="text-right">Size</span>
            <span className="text-right">Total</span>
          </div>
          
          {/* Empty State */}
          <div className="py-8 text-center">
            <p className="text-sm text-muted-foreground">No order book data</p>
            <p className="text-xs text-muted-foreground mt-1">Track a market to see live order book</p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
