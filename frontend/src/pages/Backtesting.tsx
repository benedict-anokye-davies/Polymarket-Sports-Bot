import { useState, useEffect } from 'react';
import { Play, Clock, CheckCircle, XCircle, Trash2, BarChart3, Loader2 } from 'lucide-react';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { useToast } from '@/hooks/use-toast';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';

interface BacktestConfig {
  start_date: string;
  end_date: string;
  initial_capital: number;
  entry_threshold_drop_pct: number;
  exit_take_profit_pct: number;
  exit_stop_loss_pct: number;
  max_position_size_pct: number;
  max_concurrent_positions: number;
  min_confidence_score: number;
  use_kelly_sizing: boolean;
  kelly_fraction: number;
  sport_filter: string | null;
  name: string;
}

interface BacktestSummary {
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate: number;
  total_pnl: number;
  max_drawdown: number;
  sharpe_ratio: number | null;
  profit_factor: number;
  avg_trade_pnl: number;
  avg_win: number;
  avg_loss: number;
  final_capital: number;
  roi_pct: number;
}

interface BacktestResult {
  id: string;
  name: string;
  status: string;
  config: BacktestConfig;
  summary: BacktestSummary | null;
  trades_count: number;
  created_at: string;
  completed_at: string | null;
}

interface EquityPoint {
  timestamp: string;
  equity: number;
  drawdown_pct: number;
}

export default function Backtesting() {
  const [results, setResults] = useState<BacktestResult[]>([]);
  const [selectedResult, setSelectedResult] = useState<BacktestResult | null>(null);
  const [equityCurve, setEquityCurve] = useState<EquityPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const { toast } = useToast();

  const defaultConfig: BacktestConfig = {
    start_date: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().slice(0, 16),
    end_date: new Date().toISOString().slice(0, 16),
    initial_capital: 1000,
    entry_threshold_drop_pct: 0.05,
    exit_take_profit_pct: 0.10,
    exit_stop_loss_pct: 0.08,
    max_position_size_pct: 0.20,
    max_concurrent_positions: 5,
    min_confidence_score: 0.6,
    use_kelly_sizing: false,
    kelly_fraction: 0.25,
    sport_filter: null,
    name: '',
  };

  const [config, setConfig] = useState<BacktestConfig>(defaultConfig);

  useEffect(() => {
    fetchResults();
  }, []);

  const fetchResults = async () => {
    try {
      setLoading(true);
      const res = await fetch('/api/v1/backtest/results', {
        headers: { Authorization: `Bearer ${localStorage.getItem('auth_token')}` },
      });
      if (res.ok) {
        setResults(await res.json());
      }
    } catch (err) {
      toast({
        title: 'Error',
        description: 'Failed to load backtest results',
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  };

  const runBacktest = async () => {
    try {
      setRunning(true);
      const res = await fetch('/api/v1/backtest/run', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${localStorage.getItem('auth_token')}`,
        },
        body: JSON.stringify({
          ...config,
          start_date: new Date(config.start_date).toISOString(),
          end_date: new Date(config.end_date).toISOString(),
        }),
      });

      if (res.ok) {
        toast({
          title: 'Backtest Started',
          description: 'Your backtest is running in the background',
        });
        setDialogOpen(false);
        // Poll for results
        setTimeout(fetchResults, 5000);
        setTimeout(fetchResults, 15000);
        setTimeout(fetchResults, 30000);
      } else {
        const error = await res.json();
        throw new Error(error.detail || 'Failed to start backtest');
      }
    } catch (err) {
      toast({
        title: 'Error',
        description: err instanceof Error ? err.message : 'Failed to start backtest',
        variant: 'destructive',
      });
    } finally {
      setRunning(false);
    }
  };

  const viewResult = async (result: BacktestResult) => {
    setSelectedResult(result);
    
    if (result.status === 'completed') {
      try {
        const res = await fetch(`/api/v1/backtest/results/${result.id}/equity-curve`, {
          headers: { Authorization: `Bearer ${localStorage.getItem('auth_token')}` },
        });
        if (res.ok) {
          setEquityCurve(await res.json());
        }
      } catch (err) {
        console.error('Failed to load equity curve');
      }
    }
  };

  const deleteResult = async (id: string) => {
    try {
      const res = await fetch(`/api/v1/backtest/results/${id}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${localStorage.getItem('auth_token')}` },
      });

      if (res.ok) {
        toast({
          title: 'Deleted',
          description: 'Backtest result deleted',
        });
        fetchResults();
        if (selectedResult?.id === id) {
          setSelectedResult(null);
        }
      }
    } catch (err) {
      toast({
        title: 'Error',
        description: 'Failed to delete backtest',
        variant: 'destructive',
      });
    }
  };

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(value);
  };

  const formatPercent = (value: number) => {
    return `${(value * 100).toFixed(1)}%`;
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'completed':
        return <Badge variant="default" className="bg-green-500"><CheckCircle className="w-3 h-3 mr-1" />Completed</Badge>;
      case 'running':
        return <Badge variant="secondary"><Loader2 className="w-3 h-3 mr-1 animate-spin" />Running</Badge>;
      case 'failed':
        return <Badge variant="destructive"><XCircle className="w-3 h-3 mr-1" />Failed</Badge>;
      default:
        return <Badge variant="outline"><Clock className="w-3 h-3 mr-1" />Pending</Badge>;
    }
  };

  if (loading) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center h-64">
          <Loader2 className="w-8 h-8 animate-spin text-primary" />
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-foreground">Backtesting</h1>
            <p className="text-sm text-muted-foreground mt-1">
              Test your strategies against historical data
            </p>
          </div>
          <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
            <DialogTrigger asChild>
              <Button>
                <Play className="w-4 h-4 mr-2" />
                New Backtest
              </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-[600px] max-h-[90vh] overflow-y-auto">
              <DialogHeader>
                <DialogTitle>Configure Backtest</DialogTitle>
                <DialogDescription>
                  Set parameters for your strategy backtest
                </DialogDescription>
              </DialogHeader>
              <div className="grid gap-4 py-4">
                <div className="grid gap-2">
                  <Label htmlFor="name">Name (optional)</Label>
                  <Input
                    id="name"
                    placeholder="e.g., Conservative NBA Strategy"
                    value={config.name}
                    onChange={(e) => setConfig({ ...config, name: e.target.value })}
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="grid gap-2">
                    <Label htmlFor="start">Start Date</Label>
                    <Input
                      id="start"
                      type="datetime-local"
                      value={config.start_date}
                      onChange={(e) => setConfig({ ...config, start_date: e.target.value })}
                    />
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="end">End Date</Label>
                    <Input
                      id="end"
                      type="datetime-local"
                      value={config.end_date}
                      onChange={(e) => setConfig({ ...config, end_date: e.target.value })}
                    />
                  </div>
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="capital">Initial Capital ($)</Label>
                  <Input
                    id="capital"
                    type="number"
                    min="100"
                    value={config.initial_capital}
                    onChange={(e) => setConfig({ ...config, initial_capital: parseFloat(e.target.value) })}
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="grid gap-2">
                    <Label htmlFor="entry">Entry Threshold (%)</Label>
                    <Input
                      id="entry"
                      type="number"
                      min="1"
                      max="50"
                      step="0.5"
                      value={config.entry_threshold_drop_pct * 100}
                      onChange={(e) => setConfig({ ...config, entry_threshold_drop_pct: parseFloat(e.target.value) / 100 })}
                    />
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="tp">Take Profit (%)</Label>
                    <Input
                      id="tp"
                      type="number"
                      min="1"
                      max="100"
                      step="1"
                      value={config.exit_take_profit_pct * 100}
                      onChange={(e) => setConfig({ ...config, exit_take_profit_pct: parseFloat(e.target.value) / 100 })}
                    />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="grid gap-2">
                    <Label htmlFor="sl">Stop Loss (%)</Label>
                    <Input
                      id="sl"
                      type="number"
                      min="1"
                      max="50"
                      step="1"
                      value={config.exit_stop_loss_pct * 100}
                      onChange={(e) => setConfig({ ...config, exit_stop_loss_pct: parseFloat(e.target.value) / 100 })}
                    />
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="positions">Max Positions</Label>
                    <Input
                      id="positions"
                      type="number"
                      min="1"
                      max="50"
                      value={config.max_concurrent_positions}
                      onChange={(e) => setConfig({ ...config, max_concurrent_positions: parseInt(e.target.value) })}
                    />
                  </div>
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="confidence">Min Confidence Score</Label>
                  <Input
                    id="confidence"
                    type="number"
                    min="0"
                    max="1"
                    step="0.05"
                    value={config.min_confidence_score}
                    onChange={(e) => setConfig({ ...config, min_confidence_score: parseFloat(e.target.value) })}
                  />
                </div>
                <div className="flex items-center space-x-2">
                  <Switch
                    id="kelly"
                    checked={config.use_kelly_sizing}
                    onCheckedChange={(checked) => setConfig({ ...config, use_kelly_sizing: checked })}
                  />
                  <Label htmlFor="kelly">Use Kelly Criterion Sizing</Label>
                </div>
                {config.use_kelly_sizing && (
                  <div className="grid gap-2">
                    <Label htmlFor="kelly_fraction">Kelly Fraction</Label>
                    <Input
                      id="kelly_fraction"
                      type="number"
                      min="0.1"
                      max="1"
                      step="0.05"
                      value={config.kelly_fraction}
                      onChange={(e) => setConfig({ ...config, kelly_fraction: parseFloat(e.target.value) })}
                    />
                  </div>
                )}
                <div className="grid gap-2">
                  <Label htmlFor="sport">Sport Filter</Label>
                  <Select
                    value={config.sport_filter || 'all'}
                    onValueChange={(v) => setConfig({ ...config, sport_filter: v === 'all' ? null : v })}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="All sports" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Sports</SelectItem>
                      <SelectItem value="nba">NBA</SelectItem>
                      <SelectItem value="nfl">NFL</SelectItem>
                      <SelectItem value="mlb">MLB</SelectItem>
                      <SelectItem value="nhl">NHL</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setDialogOpen(false)}>
                  Cancel
                </Button>
                <Button onClick={runBacktest} disabled={running}>
                  {running && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
                  Run Backtest
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>

        {/* Content */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Results List */}
          <Card className="lg:col-span-1">
            <CardHeader>
              <CardTitle>Backtest History</CardTitle>
              <CardDescription>{results.length} results</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2 max-h-[600px] overflow-y-auto">
              {results.length === 0 ? (
                <p className="text-muted-foreground text-center py-8">
                  No backtests yet. Run your first backtest to see results.
                </p>
              ) : (
                results.map((result) => (
                  <div
                    key={result.id}
                    className={`p-3 rounded-lg border cursor-pointer transition-colors ${
                      selectedResult?.id === result.id
                        ? 'bg-primary/10 border-primary'
                        : 'hover:bg-muted/50'
                    }`}
                    onClick={() => viewResult(result)}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-medium truncate">
                        {result.name || `Backtest ${result.id.slice(0, 8)}`}
                      </span>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          deleteResult(result.id);
                        }}
                      >
                        <Trash2 className="w-4 h-4 text-muted-foreground" />
                      </Button>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      {getStatusBadge(result.status)}
                      <span className="text-muted-foreground">
                        {new Date(result.created_at).toLocaleDateString()}
                      </span>
                    </div>
                    {result.summary && (
                      <div className="mt-2 text-sm">
                        <span className={result.summary.total_pnl >= 0 ? 'text-green-500' : 'text-red-500'}>
                          {formatCurrency(result.summary.total_pnl)}
                        </span>
                        <span className="text-muted-foreground ml-2">
                          {formatPercent(result.summary.win_rate)} win rate
                        </span>
                      </div>
                    )}
                  </div>
                ))
              )}
            </CardContent>
          </Card>

          {/* Result Detail */}
          <Card className="lg:col-span-2">
            {selectedResult ? (
              <>
                <CardHeader>
                  <CardTitle>{selectedResult.name || `Backtest ${selectedResult.id.slice(0, 8)}`}</CardTitle>
                  <CardDescription>
                    {selectedResult.status === 'completed' ? (
                      <>Completed on {new Date(selectedResult.completed_at!).toLocaleString()}</>
                    ) : (
                      <>Status: {selectedResult.status}</>
                    )}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {selectedResult.summary ? (
                    <Tabs defaultValue="summary" className="space-y-4">
                      <TabsList>
                        <TabsTrigger value="summary">Summary</TabsTrigger>
                        <TabsTrigger value="equity">Equity Curve</TabsTrigger>
                        <TabsTrigger value="config">Configuration</TabsTrigger>
                      </TabsList>

                      <TabsContent value="summary" className="space-y-4">
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                          <div className="p-3 bg-muted/50 rounded-lg">
                            <p className="text-sm text-muted-foreground">Total P&L</p>
                            <p className={`text-xl font-bold ${selectedResult.summary.total_pnl >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                              {formatCurrency(selectedResult.summary.total_pnl)}
                            </p>
                          </div>
                          <div className="p-3 bg-muted/50 rounded-lg">
                            <p className="text-sm text-muted-foreground">Win Rate</p>
                            <p className="text-xl font-bold">{formatPercent(selectedResult.summary.win_rate)}</p>
                          </div>
                          <div className="p-3 bg-muted/50 rounded-lg">
                            <p className="text-sm text-muted-foreground">Total Trades</p>
                            <p className="text-xl font-bold">{selectedResult.summary.total_trades}</p>
                          </div>
                          <div className="p-3 bg-muted/50 rounded-lg">
                            <p className="text-sm text-muted-foreground">Max Drawdown</p>
                            <p className="text-xl font-bold text-red-500">-{selectedResult.summary.max_drawdown}%</p>
                          </div>
                        </div>

                        <div className="grid grid-cols-2 gap-4">
                          <div className="space-y-2">
                            <div className="flex justify-between">
                              <span className="text-muted-foreground">Profit Factor</span>
                              <span className="font-medium">{selectedResult.summary.profit_factor.toFixed(2)}</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-muted-foreground">Sharpe Ratio</span>
                              <span className="font-medium">{selectedResult.summary.sharpe_ratio?.toFixed(2) ?? 'N/A'}</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-muted-foreground">Average Win</span>
                              <span className="font-medium text-green-500">{formatCurrency(selectedResult.summary.avg_win)}</span>
                            </div>
                          </div>
                          <div className="space-y-2">
                            <div className="flex justify-between">
                              <span className="text-muted-foreground">ROI</span>
                              <span className="font-medium">{selectedResult.summary.roi_pct.toFixed(1)}%</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-muted-foreground">Final Capital</span>
                              <span className="font-medium">{formatCurrency(selectedResult.summary.final_capital)}</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-muted-foreground">Average Loss</span>
                              <span className="font-medium text-red-500">-{formatCurrency(selectedResult.summary.avg_loss)}</span>
                            </div>
                          </div>
                        </div>
                      </TabsContent>

                      <TabsContent value="equity" className="h-[400px]">
                        {equityCurve.length > 0 ? (
                          <ResponsiveContainer width="100%" height="100%">
                            <LineChart data={equityCurve}>
                              <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                              <XAxis
                                dataKey="timestamp"
                                tickFormatter={(v) => new Date(v).toLocaleDateString()}
                                className="text-xs"
                              />
                              <YAxis tickFormatter={(v) => `$${v}`} className="text-xs" />
                              <Tooltip
                                formatter={(value: number) => [formatCurrency(value), 'Equity']}
                                labelFormatter={(label) => new Date(label).toLocaleString()}
                              />
                              <Line
                                type="monotone"
                                dataKey="equity"
                                stroke="hsl(var(--primary))"
                                strokeWidth={2}
                                dot={false}
                              />
                            </LineChart>
                          </ResponsiveContainer>
                        ) : (
                          <div className="flex items-center justify-center h-full text-muted-foreground">
                            No equity data available
                          </div>
                        )}
                      </TabsContent>

                      <TabsContent value="config" className="space-y-2">
                        <div className="grid grid-cols-2 gap-4 text-sm">
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">Initial Capital</span>
                            <span>{formatCurrency(selectedResult.config.initial_capital)}</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">Entry Threshold</span>
                            <span>{(selectedResult.config.entry_threshold_drop_pct * 100).toFixed(1)}%</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">Take Profit</span>
                            <span>{(selectedResult.config.exit_take_profit_pct * 100).toFixed(1)}%</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">Stop Loss</span>
                            <span>{(selectedResult.config.exit_stop_loss_pct * 100).toFixed(1)}%</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">Max Positions</span>
                            <span>{selectedResult.config.max_concurrent_positions}</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">Kelly Sizing</span>
                            <span>{selectedResult.config.use_kelly_sizing ? 'Yes' : 'No'}</span>
                          </div>
                        </div>
                      </TabsContent>
                    </Tabs>
                  ) : (
                    <div className="flex items-center justify-center h-32 text-muted-foreground">
                      {selectedResult.status === 'running' ? (
                        <>
                          <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                          Backtest in progress...
                        </>
                      ) : (
                        'No results available'
                      )}
                    </div>
                  )}
                </CardContent>
              </>
            ) : (
              <CardContent className="flex flex-col items-center justify-center h-96">
                <BarChart3 className="w-16 h-16 text-muted-foreground mb-4" />
                <p className="text-muted-foreground text-center">
                  Select a backtest result to view details, or run a new backtest.
                </p>
              </CardContent>
            )}
          </Card>
        </div>
      </div>
    </DashboardLayout>
  );
}
