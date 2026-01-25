import { useState, useEffect, useCallback } from 'react';
import { 
  Search, 
  RefreshCw, 
  Eye, 
  EyeOff, 
  Loader2, 
  Check, 
  CheckCheck,
  X,
  Calendar,
  Clock,
  Zap
} from 'lucide-react';
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
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '@/components/ui/tabs';
import { cn } from '@/lib/utils';
import { apiClient, AvailableGame, GameListResponse } from '@/api/client';
import { TableSkeleton } from '@/components/TableSkeleton';

const statusStyles = {
  LIVE: 'bg-primary/10 text-primary border-primary/20',
  UPCOMING: 'bg-info/10 text-info border-info/20',
  FINISHED: 'bg-muted text-muted-foreground border-border',
};

const SPORTS_LIST = [
  { value: 'all', label: 'All Sports' },
  { value: 'nba', label: 'NBA' },
  { value: 'nfl', label: 'NFL' },
  { value: 'mlb', label: 'MLB' },
  { value: 'nhl', label: 'NHL' },
  { value: 'ncaab', label: 'NCAA Basketball' },
  { value: 'ncaaf', label: 'NCAA Football' },
  { value: 'soccer', label: 'Soccer' },
  { value: 'tennis', label: 'Tennis' },
  { value: 'mma', label: 'MMA/UFC' },
  { value: 'golf', label: 'Golf' },
];

export default function Markets() {
  const [gameData, setGameData] = useState<GameListResponse>({
    selected: [],
    available: [],
    total_selected: 0,
    total_available: 0,
  });
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sportFilter, setSportFilter] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [togglingIds, setTogglingIds] = useState<Set<string>>(new Set());
  const [activeTab, setActiveTab] = useState<string>('selected');
  const [selectingAll, setSelectingAll] = useState(false);

  const fetchGames = useCallback(async () => {
    try {
      setLoading(true);
      const sport = sportFilter !== 'all' ? sportFilter.toLowerCase() : undefined;
      const data = await apiClient.getAllGames(sport);
      setGameData(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load games');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [sportFilter]);

  useEffect(() => {
    fetchGames();
  }, [fetchGames]);

  const handleRefresh = () => {
    setRefreshing(true);
    fetchGames();
  };

  const toggleGameSelection = async (game: AvailableGame) => {
    try {
      setTogglingIds(prev => new Set(prev).add(game.id));
      
      if (game.is_user_selected) {
        await apiClient.unselectGame(game.id);
      } else {
        await apiClient.selectGame(game.id);
      }
      
      // Update local state
      setGameData(prev => {
        const updatedGame = { ...game, is_user_selected: !game.is_user_selected };
        
        if (game.is_user_selected) {
          // Moving from selected to available
          return {
            ...prev,
            selected: prev.selected.filter(g => g.id !== game.id),
            available: [...prev.available, updatedGame].sort((a, b) => 
              new Date(a.game_start_time || 0).getTime() - new Date(b.game_start_time || 0).getTime()
            ),
            total_selected: prev.total_selected - 1,
            total_available: prev.total_available + 1,
          };
        } else {
          // Moving from available to selected
          return {
            ...prev,
            available: prev.available.filter(g => g.id !== game.id),
            selected: [...prev.selected, updatedGame].sort((a, b) =>
              new Date(a.game_start_time || 0).getTime() - new Date(b.game_start_time || 0).getTime()
            ),
            total_selected: prev.total_selected + 1,
            total_available: prev.total_available - 1,
          };
        }
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update game selection');
    } finally {
      setTogglingIds(prev => {
        const next = new Set(prev);
        next.delete(game.id);
        return next;
      });
    }
  };

  const selectAllForSport = async () => {
    if (sportFilter === 'all') {
      setError('Please select a specific sport to select all games');
      return;
    }
    
    try {
      setSelectingAll(true);
      const result = await apiClient.selectAllGamesForSport(sportFilter);
      if (result.success) {
        fetchGames(); // Refresh to get updated state
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to select all games');
    } finally {
      setSelectingAll(false);
    }
  };

  const unselectAllForSport = async () => {
    if (sportFilter === 'all') {
      setError('Please select a specific sport to unselect all games');
      return;
    }
    
    try {
      setSelectingAll(true);
      const result = await apiClient.unselectAllGamesForSport(sportFilter);
      if (result.success) {
        fetchGames(); // Refresh to get updated state
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to unselect all games');
    } finally {
      setSelectingAll(false);
    }
  };

  const filterGames = (games: AvailableGame[]) => {
    return games.filter((game) => {
      const searchLower = searchQuery.toLowerCase();
      const matchesSearch = 
        game.question?.toLowerCase().includes(searchLower) ||
        game.home_team?.toLowerCase().includes(searchLower) ||
        game.away_team?.toLowerCase().includes(searchLower) ||
        game.home_abbrev?.toLowerCase().includes(searchLower) ||
        game.away_abbrev?.toLowerCase().includes(searchLower);
      return matchesSearch;
    });
  };

  const formatGameTime = (dateString: string | null) => {
    if (!dateString) return 'TBD';
    const date = new Date(dateString);
    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    });
  };

  const getGameStatus = (game: AvailableGame) => {
    if (game.is_finished) return 'FINISHED';
    if (game.is_live) return 'LIVE';
    return 'UPCOMING';
  };

  const GameRow = ({ game }: { game: AvailableGame }) => {
    const status = getGameStatus(game);
    const isToggling = togglingIds.has(game.id);
    
    return (
      <tr className="hover:bg-muted/20 transition-colors">
        <td className="py-3 px-4">
          <div className="flex flex-col">
            <span className="text-sm font-medium text-foreground">
              {game.away_team && game.home_team 
                ? `${game.away_abbrev || game.away_team} @ ${game.home_abbrev || game.home_team}`
                : game.question || 'Unknown Game'}
            </span>
            {game.game_start_time && (
              <span className="text-xs text-muted-foreground flex items-center gap-1 mt-0.5">
                <Calendar className="w-3 h-3" />
                {formatGameTime(game.game_start_time)}
              </span>
            )}
          </div>
        </td>
        <td className="py-3 px-4">
          <Badge variant="outline" className="border-border text-muted-foreground uppercase">
            {game.sport}
          </Badge>
        </td>
        <td className="py-3 px-4 text-right">
          <span className="text-sm font-mono text-foreground">
            {game.current_price_yes !== null 
              ? `${(game.current_price_yes * 100).toFixed(0)}%` 
              : '-'}
          </span>
        </td>
        <td className="py-3 px-4 text-center">
          <Badge className={cn('border', statusStyles[status])}>
            {status === 'LIVE' && <Zap className="w-3 h-3 mr-1" />}
            {status}
          </Badge>
        </td>
        <td className="py-3 px-4 text-center">
          {game.match_confidence !== null && (
            <span className={cn(
              'text-xs font-medium',
              game.match_confidence >= 0.9 ? 'text-profit' : 
              game.match_confidence >= 0.7 ? 'text-warning' : 'text-muted-foreground'
            )}>
              {(game.match_confidence * 100).toFixed(0)}%
            </span>
          )}
        </td>
        <td className="py-3 px-4 text-center">
          <Button
            variant={game.is_user_selected ? 'default' : 'outline'}
            size="sm"
            onClick={() => toggleGameSelection(game)}
            disabled={isToggling}
            className={cn(
              'gap-1.5 min-w-[100px]',
              game.is_user_selected 
                ? 'bg-primary hover:bg-primary/90' 
                : 'border-border hover:bg-muted'
            )}
          >
            {isToggling ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : game.is_user_selected ? (
              <>
                <Check className="w-3.5 h-3.5" />
                Selected
              </>
            ) : (
              <>
                <Eye className="w-3.5 h-3.5" />
                Select
              </>
            )}
          </Button>
        </td>
      </tr>
    );
  };

  const GamesTable = ({ games, emptyMessage }: { 
    games: AvailableGame[]; 
    emptyMessage: string;
  }) => {
    const filteredGames = filterGames(games);
    
    if (filteredGames.length === 0) {
      return (
        <div className="text-center py-16">
          <p className="text-muted-foreground">{emptyMessage}</p>
          <p className="text-sm text-muted-foreground mt-1">
            {searchQuery ? 'Try a different search term' : 'Games will appear here when discovered by the bot'}
          </p>
        </div>
      );
    }
    
    return (
      <table className="w-full">
        <thead>
          <tr className="border-b border-border bg-muted/30">
            <th className="text-left py-3 px-4 text-xs uppercase tracking-wider text-muted-foreground font-medium">Game</th>
            <th className="text-left py-3 px-4 text-xs uppercase tracking-wider text-muted-foreground font-medium">Sport</th>
            <th className="text-right py-3 px-4 text-xs uppercase tracking-wider text-muted-foreground font-medium">Price</th>
            <th className="text-center py-3 px-4 text-xs uppercase tracking-wider text-muted-foreground font-medium">Status</th>
            <th className="text-center py-3 px-4 text-xs uppercase tracking-wider text-muted-foreground font-medium">Match</th>
            <th className="text-center py-3 px-4 text-xs uppercase tracking-wider text-muted-foreground font-medium">Action</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {filteredGames.map((game) => (
            <GameRow key={game.id} game={game} />
          ))}
        </tbody>
      </table>
    );
  };

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Page Header */}
        <div className="flex justify-between items-start">
          <div>
            <h1 className="text-2xl font-semibold text-foreground">Game Selection</h1>
            <p className="text-sm text-muted-foreground mt-1">
              Choose which games the bot should trade on
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="bg-primary/10 text-primary border-primary/20">
              <Check className="w-3 h-3 mr-1" />
              {gameData.total_selected} Selected
            </Badge>
            <Badge variant="outline" className="border-border">
              {gameData.total_available} Available
            </Badge>
          </div>
        </div>

        {/* Error Banner */}
        {error && (
          <div className="bg-destructive/10 border border-destructive/20 text-destructive px-4 py-3 rounded-lg flex justify-between items-center">
            <span>{error}</span>
            <Button variant="ghost" size="sm" onClick={() => setError(null)}>
              <X className="w-4 h-4" />
            </Button>
          </div>
        )}

        {/* Filters */}
        <Card className="p-4 bg-card border-border">
          <div className="flex flex-wrap items-center gap-4">
            <Select value={sportFilter} onValueChange={setSportFilter}>
              <SelectTrigger className="w-44 bg-muted border-border">
                <SelectValue placeholder="All Sports" />
              </SelectTrigger>
              <SelectContent>
                {SPORTS_LIST.map(sport => (
                  <SelectItem key={sport.value} value={sport.value}>
                    {sport.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <div className="relative flex-1 max-w-xs">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                placeholder="Search games..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9 bg-muted border-border"
              />
            </div>

            <div className="flex items-center gap-2 ml-auto">
              {sportFilter !== 'all' && (
                <>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={selectAllForSport}
                    disabled={selectingAll || gameData.available.length === 0}
                    className="border-border hover:bg-muted gap-1.5"
                  >
                    {selectingAll ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <CheckCheck className="w-3.5 h-3.5" />
                    )}
                    Select All {sportFilter.toUpperCase()}
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={unselectAllForSport}
                    disabled={selectingAll || gameData.selected.length === 0}
                    className="border-border hover:bg-muted gap-1.5"
                  >
                    <EyeOff className="w-3.5 h-3.5" />
                    Unselect All
                  </Button>
                </>
              )}
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
          </div>
        </Card>

        {/* Games Tabs */}
        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <TabsList className="grid w-full max-w-md grid-cols-2">
            <TabsTrigger value="selected" className="gap-2">
              <Check className="w-4 h-4" />
              Selected ({gameData.total_selected})
            </TabsTrigger>
            <TabsTrigger value="available" className="gap-2">
              <Eye className="w-4 h-4" />
              Available ({gameData.total_available})
            </TabsTrigger>
          </TabsList>

          <TabsContent value="selected" className="mt-4">
            <Card className="bg-card border-border overflow-hidden">
              <div className="p-4 border-b border-border bg-muted/20">
                <h3 className="font-medium text-foreground">Selected for Trading</h3>
                <p className="text-sm text-muted-foreground">
                  These games are actively monitored by the bot for trading opportunities
                </p>
              </div>
              <div className="overflow-x-auto">
                {loading ? (
                  <TableSkeleton columns={6} rows={5} />
                ) : (
                  <GamesTable 
                    games={gameData.selected} 
                    emptyMessage="No games selected for trading" 
                  />
                )}
              </div>
            </Card>
          </TabsContent>

          <TabsContent value="available" className="mt-4">
            <Card className="bg-card border-border overflow-hidden">
              <div className="p-4 border-b border-border bg-muted/20">
                <h3 className="font-medium text-foreground">Available Games</h3>
                <p className="text-sm text-muted-foreground">
                  Discovered games you can select for trading - click "Select" to enable trading
                </p>
              </div>
              <div className="overflow-x-auto">
                {loading ? (
                  <TableSkeleton columns={6} rows={5} />
                ) : (
                  <GamesTable 
                    games={gameData.available} 
                    emptyMessage="No available games found" 
                  />
                )}
              </div>
            </Card>
          </TabsContent>
        </Tabs>

        {/* Quick Info */}
        <Card className="p-4 bg-card border-border">
          <div className="flex items-start gap-3">
            <div className="p-2 rounded-lg bg-info/10">
              <Clock className="w-5 h-5 text-info" />
            </div>
            <div>
              <h4 className="font-medium text-foreground">How Game Selection Works</h4>
              <ul className="text-sm text-muted-foreground mt-1 space-y-1">
                <li>• The bot automatically discovers sports markets from Polymarket</li>
                <li>• Select specific games you want the bot to trade on</li>
                <li>• Only selected games will be evaluated against your trading thresholds</li>
                <li>• Use "Select All" to enable all games for a specific sport</li>
              </ul>
            </div>
          </div>
        </Card>
      </div>
    </DashboardLayout>
  );
}
