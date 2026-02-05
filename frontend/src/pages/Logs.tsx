import { useState, useEffect } from 'react';
import { Search, RefreshCw, Loader2, ChevronLeft, ChevronRight, Download, Play, Pause } from 'lucide-react';
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
import { apiClient, LogEntry } from '@/api/client';
import { TableSkeleton } from '@/components/TableSkeleton';

const levelStyles = {
  INFO: 'bg-primary/10 text-primary border-primary/20',
  WARNING: 'bg-warning/10 text-warning border-warning/20',
  ERROR: 'bg-destructive/10 text-destructive border-destructive/20',
};

export default function Logs() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [levelFilter, setLevelFilter] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [refreshing, setRefreshing] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(false);

  useEffect(() => {
    fetchLogs();
  }, [levelFilter, page]);

  // Auto-refresh every 5 seconds when enabled
  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(fetchLogs, 5000);
    return () => clearInterval(interval);
  }, [autoRefresh, levelFilter, page]);

  const fetchLogs = async () => {
    try {
      setLoading(true);
      const data = await apiClient.getLogs(levelFilter, page, 50);
      setLogs(data.items);
      setTotalPages(data.total_pages);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load logs');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const handleRefresh = () => {
    setRefreshing(true);
    fetchLogs();
  };

  const handleExportLogs = () => {
    if (filteredLogs.length === 0) return;
    const headers = ['Timestamp', 'Level', 'Module', 'Message'];
    const rows = filteredLogs.map(log => [
      log.timestamp,
      log.level,
      log.module,
      `"${log.message.replace(/"/g, '""')}"`,
    ]);
    const csvContent = [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `bot-logs-${new Date().toISOString().slice(0, 10)}.csv`;
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(link.href);
  };

  const filteredLogs = logs.filter((log) => {
    const matchesSearch = 
      log.message.toLowerCase().includes(searchQuery.toLowerCase()) ||
      log.module.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesSearch;
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

            <Button
              variant="outline"
              size="sm"
              className={cn(
                "border-border gap-1.5",
                autoRefresh ? "bg-primary/10 text-primary border-primary/20" : "hover:bg-muted"
              )}
              onClick={() => setAutoRefresh(!autoRefresh)}
            >
              {autoRefresh ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
              {autoRefresh ? 'Live' : 'Auto'}
            </Button>

            <Button
              variant="outline"
              size="icon"
              className="border-border hover:bg-muted"
              onClick={handleRefresh}
              disabled={refreshing}
            >
              <RefreshCw className={cn("w-4 h-4", refreshing && "animate-spin")} />
            </Button>

            <Button
              variant="outline"
              size="icon"
              className="border-border hover:bg-muted"
              onClick={handleExportLogs}
              disabled={filteredLogs.length === 0}
              title="Export logs as CSV"
            >
              <Download className="w-4 h-4" />
            </Button>
          </div>
        </Card>

        {/* Error Banner */}
        {error && (
          <div className="bg-destructive/10 border border-destructive/20 text-destructive px-4 py-3 rounded-lg">
            {error}
          </div>
        )}

        {/* Logs Table */}
        <Card className="bg-card border-border overflow-hidden">
          <div className="max-h-[600px] overflow-y-auto scrollbar-thin">
            {loading ? (
              <TableSkeleton columns={4} rows={10} />
            ) : filteredLogs.length === 0 ? (
              <div className="text-center py-16">
                <p className="text-muted-foreground">No logs found</p>
                <p className="text-sm text-muted-foreground mt-1">Activity logs will appear here as the bot runs</p>
              </div>
            ) : (
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
            )}
          </div>
        </Card>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground">
              Page {page} of {totalPages}
            </p>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                className="border-border hover:bg-muted gap-1"
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page <= 1 || loading}
              >
                <ChevronLeft className="w-4 h-4" />
                Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="border-border hover:bg-muted gap-1"
                onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages || loading}
              >
                Next
                <ChevronRight className="w-4 h-4" />
              </Button>
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
