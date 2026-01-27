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
  Zap,
  ChevronDown,
  Globe,
  Filter,
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
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { cn } from '@/lib/utils';
import { apiClient, SportCategory, LeagueInfo, ESPNGame } from '@/api/client';
import { TableSkeleton } from '@/components/TableSkeleton';

const statusStyles = {
  live: 'bg-primary/10 text-primary border-primary/20',
  upcoming: 'bg-info/10 text-info border-info/20',
  final: 'bg-muted text-muted-foreground border-border',
};

// Game data from ESPN - transformed for display
interface GameData {
  id: string;
  homeTeam: string;
  awayTeam: string;
  homeAbbr: string;
  awayAbbr: string;
  homeScore: number;
  awayScore: number;
  startTime: string;
  status: 'upcoming' | 'live' | 'final';
  currentPeriod: string;
  clock: string;
  homeOdds: number;
  awayOdds: number;
  volume: number;
  sport: string;
}

export default function Markets() {
  // All available games from ESPN
  const [allGames, setAllGames] = useState<GameData[]>([]);
  // Selected game IDs (persisted to bot config)
  const [selectedGameIds, setSelectedGameIds] = useState<Set<string>>(new Set());
  
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [togglingIds, setTogglingIds] = useState<Set<string>>(new Set());
  const [activeTab, setActiveTab] = useState<string>('available');
  const [selectingAll, setSelectingAll] = useState(false);
  const [savingConfig, setSavingConfig] = useState(false);

  // League selection state - start empty, will be set after categories load
  const [categories, setCategories] = useState<SportCategory[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string>('');
  const [selectedLeagues, setSelectedLeagues] = useState<Set<string>>(new Set());
  const [loadingCategories, setLoadingCategories] = useState(true);

  // Load categories on mount
  useEffect(() => {
    const loadCategories = async () => {
      try {
        setLoadingCategories(true);
        const data = await apiClient.getSportCategories();
        setCategories(data);
        
        // Set default category to first one (usually basketball)
        if (data.length > 0) {
          const firstCategory = data[0];
          setSelectedCategory(firstCategory.category);
          
          // Auto-select first league (usually nba)
          if (firstCategory.leagues.length > 0) {
            setSelectedLeagues(new Set([firstCategory.leagues[0].league_key]));
          }
        }
      } catch (err) {
        console.error('Failed to load categories:', err);
        setError('Failed to load sport categories. Please refresh the page.');
      } finally {
        setLoadingCategories(false);
      }
    };
    loadCategories();
  }, []);

  // Load existing bot config to get selected games
  useEffect(() => {
    const loadSelectedGames = async () => {
      try {
        const config = await apiClient.getBotConfig();
        const selectedIds = new Set<string>();
        
        // Get the main game if exists
        if (config.game?.game_id) {
          selectedIds.add(config.game.game_id);
        }
        
        // Get additional games if exist
        if (config.additional_games) {
          for (const game of config.additional_games) {
            if (game.game_id) {
              selectedIds.add(game.game_id);
            }
          }
        }
        
        setSelectedGameIds(selectedIds);
      } catch (err) {
        console.log('No existing config found');
      }
    };
    loadSelectedGames();
  }, []);

  // Get leagues for current category
  const getCurrentLeagues = useCallback((): LeagueInfo[] => {
    if (selectedCategory === 'all') {
      return categories.flatMap(cat => cat.leagues);
    }
    const category = categories.find(c => c.category === selectedCategory);
    return category?.leagues || [];
  }, [categories, selectedCategory]);

  // Fetch games from ESPN for all selected leagues
  const fetchGames = useCallback(async () => {
    if (selectedLeagues.size === 0) {
      setAllGames([]);
      setLoading(false);
      setRefreshing(false);
      return;
    }

    try {
      setLoading(true);
      setError(null);
      const allFetchedGames: GameData[] = [];
      
      // Fetch games from each selected league in parallel
      const leaguePromises = Array.from(selectedLeagues).map(async (league) => {
        try {
          const games = await apiClient.getLiveGames(league);
          // Transform ESPN games to our GameData format
          return games.map((g: ESPNGame): GameData => ({
            id: g.id,
            homeTeam: g.homeTeam || 'TBD',
            awayTeam: g.awayTeam || 'TBD',
            homeAbbr: g.homeAbbr || (g.homeTeam ? g.homeTeam.substring(0, 3).toUpperCase() : 'TBD'),
            awayAbbr: g.awayAbbr || (g.awayTeam ? g.awayTeam.substring(0, 3).toUpperCase() : 'TBD'),
            homeScore: g.homeScore || 0,
            awayScore: g.awayScore || 0,
            startTime: g.startTime 
              ? new Date(g.startTime).toLocaleString('en-US', { 
                  month: 'short',
                  day: 'numeric',
                  hour: 'numeric', 
                  minute: '2-digit', 
                  timeZoneName: 'short' 
                })
              : 'TBD',
            status: g.status || 'upcoming',
            currentPeriod: g.currentPeriod || '',
            clock: g.clock || '',
            homeOdds: g.homeOdds || 50,
            awayOdds: g.awayOdds || 50,
            volume: g.volume || 0,
            sport: league,
          }));
        } catch (err) {
          console.error(`Failed to fetch games for ${league}:`, err);
          return [];
        }
      });

      const results = await Promise.all(leaguePromises);
      results.forEach(games => allFetchedGames.push(...games));

      // Sort by start time, live games first
      allFetchedGames.sort((a, b) => {
        // Live games first
        if (a.status === 'live' && b.status !== 'live') return -1;
        if (b.status === 'live' && a.status !== 'live') return 1;
        // Then upcoming
        if (a.status === 'upcoming' && b.status === 'final') return -1;
        if (b.status === 'upcoming' && a.status === 'final') return 1;
        return 0;
      });

      setAllGames(allFetchedGames);
      
      if (allFetchedGames.length === 0) {
        setError('No games found for selected leagues. Try selecting different leagues or check back later.');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load games');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [selectedLeagues]); // Only depend on selectedLeagues, not selectedGameIds

  useEffect(() => {
    fetchGames();
  }, [fetchGames]);

  const handleRefresh = () => {
    setRefreshing(true);
    fetchGames();
  };

  const toggleLeagueSelection = (leagueKey: string) => {
    setSelectedLeagues(prev => {
      const newSet = new Set(prev);
      if (newSet.has(leagueKey)) {
        newSet.delete(leagueKey);
      } else {
        newSet.add(leagueKey);
      }
      return newSet;
    });
  };

  const selectAllLeaguesInCategory = () => {
    const leagues = getCurrentLeagues();
    setSelectedLeagues(new Set(leagues.map(l => l.league_key)));
  };

  const clearLeagueSelection = () => {
    setSelectedLeagues(new Set());
  };

  // Filter games by search query
  const filterGames = (games: GameData[]) => {
    if (!searchQuery) return games;
    const searchLower = searchQuery.toLowerCase();
    return games.filter((game) => (
      game.homeTeam.toLowerCase().includes(searchLower) ||
      game.awayTeam.toLowerCase().includes(searchLower) ||
      game.homeAbbr.toLowerCase().includes(searchLower) ||
      game.awayAbbr.toLowerCase().includes(searchLower) ||
      game.sport.toLowerCase().includes(searchLower)
    ));
  };

  // Split into selected and available
  const filteredGames = filterGames(allGames);
  const selectedGames = filteredGames.filter(g => selectedGameIds.has(g.id));
  const availableGames = filteredGames.filter(g => !selectedGameIds.has(g.id));

  // Toggle game selection and save to bot config
  const toggleGameSelection = async (game: GameData) => {
    try {
      setTogglingIds(prev => new Set(prev).add(game.id));
      
      const newSelectedIds = new Set(selectedGameIds);
      if (newSelectedIds.has(game.id)) {
        newSelectedIds.delete(game.id);
      } else {
        newSelectedIds.add(game.id);
      }
      
      // Update local state immediately for responsiveness
      setSelectedGameIds(newSelectedIds);
      
      // Build the games array for API
      const selectedGamesArray = allGames
        .filter(g => newSelectedIds.has(g.id))
        .map(g => ({
          game_id: g.id,
          sport: g.sport,
          home_team: g.homeTeam,
          away_team: g.awayTeam,
          start_time: g.startTime,
          selected_side: 'home' as const, // Default to home team
        }));

      if (selectedGamesArray.length > 0) {
        const firstGame = selectedGamesArray[0];
        const additionalGames = selectedGamesArray.slice(1);

        await apiClient.saveBotConfig({
          sport: firstGame.sport,
          game: firstGame,
          additional_games: additionalGames.length > 0 ? additionalGames : undefined,
        });
      } else {
        // Clear config when no games selected
        await apiClient.saveBotConfig({
          sport: Array.from(selectedLeagues)[0] || 'nba',
          game: undefined,
        });
      }
    } catch (err) {
      // Revert on error
      setError(err instanceof Error ? err.message : 'Failed to update game selection');
    } finally {
      setTogglingIds(prev => {
        const next = new Set(prev);
        next.delete(game.id);
        return next;
      });
    }
  };

  // Select all visible games
  const selectAllGames = async () => {
    try {
      setSelectingAll(true);
      
      const newSelectedIds = new Set(selectedGameIds);
      filteredGames.forEach(g => newSelectedIds.add(g.id));
      
      setSelectedGameIds(newSelectedIds);
      
      // Build and save config
      const selectedGamesArray = allGames
        .filter(g => newSelectedIds.has(g.id))
        .map(g => ({
          game_id: g.id,
          sport: g.sport,
          home_team: g.homeTeam,
          away_team: g.awayTeam,
          start_time: g.startTime,
          selected_side: 'home' as const,
        }));

      if (selectedGamesArray.length > 0) {
        const firstGame = selectedGamesArray[0];
        const additionalGames = selectedGamesArray.slice(1);

        await apiClient.saveBotConfig({
          sport: firstGame.sport,
          game: firstGame,
          additional_games: additionalGames.length > 0 ? additionalGames : undefined,
        });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to select all games');
    } finally {
      setSelectingAll(false);
    }
  };

  // Unselect all visible games
  const unselectAllGames = async () => {
    try {
      setSelectingAll(true);
      
      const newSelectedIds = new Set(selectedGameIds);
      filteredGames.forEach(g => newSelectedIds.delete(g.id));
      
      setSelectedGameIds(newSelectedIds);
      
      // Build and save config
      const selectedGamesArray = allGames
        .filter(g => newSelectedIds.has(g.id))
        .map(g => ({
          game_id: g.id,
          sport: g.sport,
          home_team: g.homeTeam,
          away_team: g.awayTeam,
          start_time: g.startTime,
          selected_side: 'home' as const,
        }));

      if (selectedGamesArray.length > 0) {
        const firstGame = selectedGamesArray[0];
        const additionalGames = selectedGamesArray.slice(1);

        await apiClient.saveBotConfig({
          sport: firstGame.sport,
          game: firstGame,
          additional_games: additionalGames.length > 0 ? additionalGames : undefined,
        });
      } else {
        await apiClient.saveBotConfig({
          sport: Array.from(selectedLeagues)[0] || 'nba',
          game: undefined,
        });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to unselect all games');
    } finally {
      setSelectingAll(false);
    }
  };

  const GameRow = ({ game }: { game: GameData }) => {
    const isToggling = togglingIds.has(game.id);
    const isSelected = selectedGameIds.has(game.id);
    
    return (
      <tr className="hover:bg-muted/20 transition-colors">
        <td className="py-3 px-4">
          <div className="flex flex-col">
            <span className="text-sm font-medium text-foreground">
              {game.awayAbbr} @ {game.homeAbbr}
            </span>
            <span className="text-xs text-muted-foreground">
              {game.awayTeam} vs {game.homeTeam}
            </span>
            <span className="text-xs text-muted-foreground flex items-center gap-1 mt-0.5">
              <Calendar className="w-3 h-3" />
              {game.startTime}
            </span>
          </div>
        </td>
        <td className="py-3 px-4">
          <Badge variant="outline" className="border-border text-muted-foreground uppercase">
            {game.sport}
          </Badge>
        </td>
        <td className="py-3 px-4 text-right">
          {game.status === 'live' || game.status === 'final' ? (
            <span className="text-sm font-mono text-foreground">
              {game.awayScore} - {game.homeScore}
            </span>
          ) : (
            <span className="text-sm text-muted-foreground">-</span>
          )}
        </td>
        <td className="py-3 px-4 text-center">
          <Badge className={cn('border', statusStyles[game.status])}>
            {game.status === 'live' && <Zap className="w-3 h-3 mr-1" />}
            {game.status.toUpperCase()}
          </Badge>
          {game.status === 'live' && game.currentPeriod && (
            <div className="text-xs text-muted-foreground mt-1">
              {game.currentPeriod} {game.clock}
            </div>
          )}
        </td>
        <td className="py-3 px-4 text-center">
          <Button
            variant={isSelected ? 'default' : 'outline'}
            size="sm"
            onClick={() => toggleGameSelection(game)}
            disabled={isToggling}
            className={cn(
              'gap-1.5 min-w-[100px]',
              isSelected 
                ? 'bg-primary hover:bg-primary/90' 
                : 'border-border hover:bg-muted'
            )}
          >
            {isToggling ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : isSelected ? (
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
    games: GameData[]; 
    emptyMessage: string;
  }) => {
    if (games.length === 0) {
      return (
        <div className="text-center py-16">
          <p className="text-muted-foreground">{emptyMessage}</p>
          <p className="text-sm text-muted-foreground mt-1">
            {searchQuery ? 'Try a different search term' : 'Select leagues above to see games'}
          </p>
        </div>
      );
    }
    
    return (
      <table className="w-full">
        <thead>
          <tr className="border-b border-border bg-muted/30">
            <th className="text-left py-3 px-4 text-xs uppercase tracking-wider text-muted-foreground font-medium">Game</th>
            <th className="text-left py-3 px-4 text-xs uppercase tracking-wider text-muted-foreground font-medium">League</th>
            <th className="text-right py-3 px-4 text-xs uppercase tracking-wider text-muted-foreground font-medium">Score</th>
            <th className="text-center py-3 px-4 text-xs uppercase tracking-wider text-muted-foreground font-medium">Status</th>
            <th className="text-center py-3 px-4 text-xs uppercase tracking-wider text-muted-foreground font-medium">Action</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {games.map((game) => (
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
              Choose which games the bot should trade on across multiple leagues
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="bg-primary/10 text-primary border-primary/20">
              <Check className="w-3 h-3 mr-1" />
              {selectedGames.length} Selected
            </Badge>
            <Badge variant="outline" className="border-border">
              {availableGames.length} Available
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
            {/* Category Selector */}
            <Select 
              value={selectedCategory} 
              onValueChange={(value) => {
                setSelectedCategory(value);
                // Auto-select first league in new category
                if (value !== 'all') {
                  const cat = categories.find(c => c.category === value);
                  if (cat && cat.leagues.length > 0) {
                    setSelectedLeagues(new Set([cat.leagues[0].league_key]));
                  }
                } else {
                  setSelectedLeagues(new Set());
                }
              }}
            >
              <SelectTrigger className="w-48 bg-muted border-border">
                <Globe className="w-4 h-4 mr-2 text-muted-foreground" />
                <SelectValue placeholder="Select Category" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Categories</SelectItem>
                {categories.map(cat => (
                  <SelectItem key={cat.category} value={cat.category}>
                    {cat.display_name} ({cat.leagues.length})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            {/* League Multi-Select Dropdown */}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" className="w-56 justify-between bg-muted border-border">
                  <span className="flex items-center gap-2">
                    <Filter className="w-4 h-4 text-muted-foreground" />
                    {selectedLeagues.size === 0 
                      ? 'Select Leagues' 
                      : `${selectedLeagues.size} League${selectedLeagues.size > 1 ? 's' : ''} Selected`
                    }
                  </span>
                  <ChevronDown className="w-4 h-4 text-muted-foreground" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent className="w-64 max-h-80 overflow-y-auto">
                <DropdownMenuLabel className="flex justify-between items-center">
                  <span>Select Leagues</span>
                  <div className="flex gap-1">
                    <Button 
                      variant="ghost" 
                      size="sm" 
                      className="h-6 text-xs"
                      onClick={selectAllLeaguesInCategory}
                    >
                      All
                    </Button>
                    <Button 
                      variant="ghost" 
                      size="sm" 
                      className="h-6 text-xs"
                      onClick={clearLeagueSelection}
                    >
                      Clear
                    </Button>
                  </div>
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                {loadingCategories ? (
                  <div className="p-4 text-center text-muted-foreground">
                    <Loader2 className="w-4 h-4 animate-spin mx-auto" />
                  </div>
                ) : (
                  getCurrentLeagues().map(league => (
                    <DropdownMenuCheckboxItem
                      key={league.league_key}
                      checked={selectedLeagues.has(league.league_key)}
                      onCheckedChange={() => toggleLeagueSelection(league.league_key)}
                    >
                      {league.display_name}
                    </DropdownMenuCheckboxItem>
                  ))
                )}
                {!loadingCategories && getCurrentLeagues().length === 0 && (
                  <div className="p-4 text-center text-muted-foreground text-sm">
                    No leagues in this category
                  </div>
                )}
              </DropdownMenuContent>
            </DropdownMenu>

            {/* Search */}
            <div className="relative flex-1 max-w-xs">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                placeholder="Search games..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9 bg-muted border-border"
              />
            </div>

            {/* Action Buttons */}
            <div className="flex items-center gap-2 ml-auto">
              {selectedLeagues.size > 0 && (
                <>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={selectAllGames}
                    disabled={selectingAll || availableGames.length === 0}
                    className="border-border hover:bg-muted gap-1.5"
                  >
                    {selectingAll ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <CheckCheck className="w-3.5 h-3.5" />
                    )}
                    Select All
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={unselectAllGames}
                    disabled={selectingAll || selectedGames.length === 0}
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

          {/* Selected leagues display */}
          {selectedLeagues.size > 0 && (
            <div className="flex flex-wrap gap-2 mt-3 pt-3 border-t border-border">
              {Array.from(selectedLeagues).map(league => {
                const leagueInfo = getCurrentLeagues().find(l => l.league_key === league);
                return (
                  <Badge 
                    key={league} 
                    variant="secondary"
                    className="gap-1 pr-1"
                  >
                    {leagueInfo?.display_name || league.toUpperCase()}
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-4 w-4 p-0 hover:bg-transparent"
                      onClick={() => toggleLeagueSelection(league)}
                    >
                      <X className="w-3 h-3" />
                    </Button>
                  </Badge>
                );
              })}
            </div>
          )}
        </Card>

        {/* Games Tabs */}
        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <TabsList className="grid w-full max-w-md grid-cols-2">
            <TabsTrigger value="selected" className="gap-2">
              <Check className="w-4 h-4" />
              Selected ({selectedGames.length})
            </TabsTrigger>
            <TabsTrigger value="available" className="gap-2">
              <Eye className="w-4 h-4" />
              Available ({availableGames.length})
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
                  <TableSkeleton columns={5} rows={5} />
                ) : (
                  <GamesTable 
                    games={selectedGames} 
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
                  Live and upcoming games from selected leagues - click "Select" to enable trading
                </p>
              </div>
              <div className="overflow-x-auto">
                {loading ? (
                  <TableSkeleton columns={5} rows={5} />
                ) : (
                  <GamesTable 
                    games={availableGames} 
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
                <li>1. Select leagues from the dropdown to see available games</li>
                <li>2. You can select multiple leagues across different sports</li>
                <li>3. Select specific games you want the bot to trade on</li>
                <li>4. Only selected games will be evaluated against your trading thresholds</li>
                <li>5. Games auto-refresh - live data comes directly from ESPN</li>
              </ul>
            </div>
          </div>
        </Card>
      </div>
    </DashboardLayout>
  );
}
