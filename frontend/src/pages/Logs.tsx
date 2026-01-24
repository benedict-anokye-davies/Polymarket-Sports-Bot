import { useState } from 'react';
import { Search, RefreshCw } from 'lucide-react';
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

interface LogEntry {
  id: string;
  timestamp: string;
  level: 'INFO' | 'WARNING' | 'ERROR';
  module: string;
  message: string;
}

const mockLogs: LogEntry[] = [
  { id: '1', timestamp: '2024-01-20 14:32:15.234', level: 'INFO', module: 'PriceMonitor', message: 'Price update received for LAL@BOS market: 0.68 → 0.72' },
  { id: '2', timestamp: '2024-01-20 14:32:14.891', level: 'INFO', module: 'TradeExecutor', message: 'Order filled: BUY 500 YES @ 0.68 for LAL@BOS' },
  { id: '3', timestamp: '2024-01-20 14:32:12.456', level: 'WARNING', module: 'RiskManager', message: 'Approaching daily loss limit: $423.50 / $500.00' },
  { id: '4', timestamp: '2024-01-20 14:32:10.123', level: 'INFO', module: 'SSEClient', message: 'Connected to event stream' },
  { id: '5', timestamp: '2024-01-20 14:31:58.789', level: 'ERROR', module: 'TradeExecutor', message: 'Order rejected: Insufficient balance for position size' },
  { id: '6', timestamp: '2024-01-20 14:31:45.567', level: 'INFO', module: 'MarketScanner', message: 'New market detected: GSW@MIA - tracking initiated' },
  { id: '7', timestamp: '2024-01-20 14:31:30.234', level: 'INFO', module: 'PriceMonitor', message: 'Baseline captured for GSW@MIA: 0.52' },
  { id: '8', timestamp: '2024-01-20 14:31:15.891', level: 'WARNING', module: 'SSEClient', message: 'Connection timeout, attempting reconnect...' },
  { id: '9', timestamp: '2024-01-20 14:31:00.456', level: 'INFO', module: 'BotEngine', message: 'Bot started successfully with 24 tracked markets' },
  { id: '10', timestamp: '2024-01-20 14:30:45.123', level: 'INFO', module: 'WalletManager', message: 'Wallet connected: 0x7a23...4f9d' },
];

const levelStyles = {
  INFO: 'bg-primary/10 text-primary border-primary/20',
  WARNING: 'bg-warning/10 text-warning border-warning/20',
  ERROR: 'bg-destructive/10 text-destructive border-destructive/20',
};

export default function Logs() {
  const [levelFilter, setLevelFilter] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');

  const filteredLogs = mockLogs.filter((log) => {
    const matchesLevel = levelFilter === 'all' || log.level === levelFilter;
    const matchesSearch = 
      log.message.toLowerCase().includes(searchQuery.toLowerCase()) ||
      log.module.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesLevel && matchesSearch;
  });

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Page Header */}
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Activity Logs</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Monitor bot activity and debug issues
          </p>
        </div>

        {/* Filters */}
        <Card className="p-4 bg-card border-border">
          <div className="flex flex-wrap items-center gap-4">
            <Select value={levelFilter} onValueChange={setLevelFilter}>
              <SelectTrigger className="w-32 bg-muted border-border">
                <SelectValue placeholder="Level" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Levels</SelectItem>
                <SelectItem value="INFO">INFO</SelectItem>
                <SelectItem value="WARNING">WARNING</SelectItem>
                <SelectItem value="ERROR">ERROR</SelectItem>
              </SelectContent>
            </Select>

            <div className="relative flex-1 max-w-sm">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                placeholder="Search logs..."
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

        {/* Logs Table */}
        <Card className="bg-card border-border overflow-hidden">
          <div className="max-h-[600px] overflow-y-auto scrollbar-thin">
            <table className="w-full">
              <thead className="sticky top-0 bg-card z-10">
                <tr className="border-b border-border bg-muted/30">
                  <th className="text-left py-3 px-4 text-xs uppercase tracking-wider text-muted-foreground font-medium w-52">Timestamp</th>
                  <th className="text-center py-3 px-4 text-xs uppercase tracking-wider text-muted-foreground font-medium w-24">Level</th>
                  <th className="text-left py-3 px-4 text-xs uppercase tracking-wider text-muted-foreground font-medium w-36">Module</th>
                  <th className="text-left py-3 px-4 text-xs uppercase tracking-wider text-muted-foreground font-medium">Message</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border font-mono text-sm">
                {filteredLogs.map((log) => (
                  <tr 
                    key={log.id} 
                    className={cn(
                      'hover:bg-muted/20 transition-colors',
                      log.level === 'ERROR' && 'bg-destructive/5'
                    )}
                  >
                    <td className="py-2.5 px-4">
                      <span className="text-muted-foreground text-xs">{log.timestamp}</span>
                    </td>
                    <td className="py-2.5 px-4 text-center">
                      <Badge className={cn('border text-xs', levelStyles[log.level])}>
                        {log.level}
                      </Badge>
                    </td>
                    <td className="py-2.5 px-4">
                      <span className="text-primary text-xs">{log.module}</span>
                    </td>
                    <td className="py-2.5 px-4">
                      <span className="text-foreground text-xs">{log.message}</span>
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
