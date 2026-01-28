import { useState, useEffect, useCallback } from 'react';
import {
  Search,
  RefreshCw,
  Eye,
  Loader2,
  Check,
  CheckCheck,
  X,
  Calendar,
  Zap,
  ChevronDown,
  Globe,
  Filter,
  Clock,
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
import { logger } from '@/lib/logger';
import { TableSkeleton } from '@/components/TableSkeleton';

const statusStyles: Record<string, string> = {
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
  // Selected game IDs - using array instead of Set for proper serialization
  const [selectedGameIds, setSelectedGameIds] = useState<string[]>([]);

  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [togglingIds, setTogglingIds] = useState<string[]>([]);
  const [activeTab, setActiveTab] = useState<string>('available');
  const [selectingAll, setSelectingAll] = useState(false);

  // League selection state - using arrays instead of Sets for proper serialization
  const [categories, setCategories] = useState<SportCategory[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string>('');
  const [selectedLeagues, setSelectedLeagues] = useState<string[]>([]);
  const [loadingCategories, setLoadingCategories] = useState(true);

  // Load categories on mount
  useEffect(() => {
    const loadCategories = async () => {
      try {
        setLoadingCategories(true);
        const data = await apiClient.getSportCategories();
        setCategories(data);

        // Set default category to basketball
        if (data.length > 0) {
          const basketballCat = data.find(c => c.category === 'basketball') || data[0];
          setSelectedCategory(basketballCat.category);

          // Auto-select NBA as default
          const nbaLeague = basketballCat.leagues.find(l => l.league_key === 'nba');
          if (nbaLeague) {
            setSelectedLeagues(['nba']);
          } else if (basketballCat.leagues.length > 0) {
            setSelectedLeagues([basketballCat.leagues[0].league_key]);
          }
        }
      } catch (err) {
        logger.error('Failed to load categories:', err);
        setError('Failed to load sport categories');
      } finally {
        setLoadingCategories(false);
      }
    };
    loadCategories();
  }, []);

  // Get leagues for current category
  const getCurrentLeagues = useCallback((): LeagueInfo[] => {
    if (!selectedCategory) return [];
    const category = categories.find(c => c.category === selectedCategory);
    return category?.leagues || [];
  }, [categories, selectedCategory]);

  // Fetch games from ESPN for selected leagues
  const fetchGames = useCallback(async () => {
    if (selectedLeagues.length === 0) {
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
      const leaguePromises = selectedLeagues.map(async (league) => {
        try {
          const games: ESPNGame[] = await apiClient.getLiveGames(league);
          // Transform ESPN games to our GameData format
          return games.map((g): GameData => ({
            id: g.id,
            homeTeam: g.homeTeam || 'TBD',
            awayTeam: g.awayTeam || 'TBD',
            homeAbbr: g.homeAbbr || '',
            awayAbbr: g.awayAbbr || '',
            homeScore: g.homeScore || 0,
            awayScore: g.awayScore || 0,
            startTime: g.startTime
              ? new Date(g.startTime).toLocaleString('en-US', {
                  month: 'short',
                  day: 'numeric',
                  hour: 'numeric',
                  minute: '2-digit',
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
          logger.error(`Failed to fetch games for ${league}:`, err);
          return [];
        }
      });

      const results = await Promise.all(leaguePromises);
      results.forEach(games => allFetchedGames.push(...games));

      // Sort: live first, then upcoming, then final
      allFetchedGames.sort((a, b) => {
        if (a.status === 'live' && b.status !== 'live') return -1;
        if (b.status === 'live' && a.status !== 'live') return 1;
        if (a.status === 'upcoming' && b.status === 'final') return -1;
        if (b.status === 'upcoming' && a.status === 'final') return 1;
        return 0;
      });

      setAllGames(allFetchedGames);

      if (allFetchedGames.length === 0) {
        const leagueNames = selectedLeagues.join(', ').toUpperCase();
        setError(`No games currently scheduled for ${leagueNames}. Games only appear on days they're scheduled.`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load games');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [selectedLeagues]);

  // Fetch when leagues change
  useEffect(() => {
    if (!loadingCategories && selectedLeagues.length > 0) {
      fetchGames();
    }
  }, [selectedLeagues, loadingCategories, fetchGames]);

  const handleRefresh = () => {
    setRefreshing(true);
    fetchGames();
  };

  const toggleLeagueSelection = (leagueKey: string) => {
    setSelectedLeagues(prev => {
      if (prev.includes(leagueKey)) {
        return prev.filter(k => k !== leagueKey);
      } else {
        return [...prev, leagueKey];
      }
    });
  };

  const selectAllLeaguesInCategory = () => {
    const leagues = getCurrentLeagues();
    setSelectedLeagues(leagues.map(l => l.league_key));
  };

  const clearLeagueSelection = () => {
    setSelectedLeagues([]);
  };

  // Filter games by search
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
  const selectedGames = filteredGames.filter(g => selectedGameIds.includes(g.id));
  const availableGames = filteredGames.filter(g => !selectedGameIds.includes(g.id));

  // Toggle game selection
  const toggleGameSelection = async (game: GameData) => {
    setTogglingIds(prev => [...prev, game.id]);

    try {
      if (selectedGameIds.includes(game.id)) {
        setSelectedGameIds(prev => prev.filter(id => id !== game.id));
      } else {
        setSelectedGameIds(prev => [...prev, game.id]);
      }
    } finally {
      setTogglingIds(prev => prev.filter(id => id !== game.id));
    }
  };

  // Select all visible games
  const selectAllGames = () => {
    setSelectingAll(true);
    const newIds = [...selectedGameIds];
    filteredGames.forEach(g => {
      if (!newIds.includes(g.id)) newIds.push(g.id);
    });
    setSelectedGameIds(newIds);
    setSelectingAll(false);
  };

  // Unselect all visible games
  const unselectAllGames = () => {
    setSelectingAll(true);
    const gameIdsToRemove = filteredGames.map(g => g.id);
    setSelectedGameIds(prev => prev.filter(id => !gameIdsToRemove.includes(id)));
    setSelectingAll(false);
  };

  const GameRow = ({ game }: { game: GameData }) => {
    const isToggling = togglingIds.includes(game.id);
    const isSelected = selectedGameIds.includes(game.id);

    return (
      <tr className="hover:bg-muted/20 transition-colors">
        <td className="py-3 px-4">
          <div className="flex flex-col">
            <span className="text-sm font-medium text-foreground">
              {game.awayAbbr || game.awayTeam} @ {game.homeAbbr || game.homeTeam}
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
          <Badge className={cn('border', statusStyles[game.status] || statusStyles.upcoming)}>
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

  const GamesTable = ({ games, emptyMessage }: { games: GameData[]; emptyMessage: string }) => {
    if (games.length === 0) {
      return (
        <div className="text-center py-16">
          <p className="text-muted-foreground">{emptyMessage}</p>
          <p className="text-sm text-muted-foreground mt-2">
            {searchQuery
              ? 'Try a different search term'
              : selectedLeagues.length === 0
                ? 'Select leagues above to see games'
                : 'Try NBA, EPL, or MLS for more frequent games'}
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
              Choose games from multiple leagues to trade on
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
            <span className="text-sm">{error}</span>
            <Button variant="ghost" size="sm" onClick={() => setError(null)}>
              <X className="w-4 h-4" />
            </Button>
          </div>
        )}

        {/* Filters Card */}
        <Card className="p-4 bg-card border-border">
          <div className="flex flex-wrap items-center gap-4">
            {/* Category Selector */}
            <Select
              value={selectedCategory}
              onValueChange={(value) => {
                setSelectedCategory(value);
                // Auto-select first league in new category
                const cat = categories.find(c => c.category === value);
                if (cat && cat.leagues.length > 0) {
                  setSelectedLeagues([cat.leagues[0].league_key]);
                } else {
                  setSelectedLeagues([]);
                }
              }}
            >
              <SelectTrigger className="w-48 bg-muted border-border">
                <Globe className="w-4 h-4 mr-2 text-muted-foreground" />
                <SelectValue placeholder="Select Category" />
              </SelectTrigger>
              <SelectContent>
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
                    {selectedLeagues.length === 0
                      ? 'Select Leagues'
                      : `${selectedLeagues.length} League${selectedLeagues.length > 1 ? 's' : ''}`}
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
                ) : getCurrentLeagues().length === 0 ? (
                  <div className="p-4 text-center text-muted-foreground text-sm">
                    Select a category first
                  </div>
                ) : (
                  getCurrentLeagues().map(league => (
                    <DropdownMenuCheckboxItem
                      key={league.league_key}
                      checked={selectedLeagues.includes(league.league_key)}
                      onCheckedChange={() => toggleLeagueSelection(league.league_key)}
                    >
                      {league.display_name}
                    </DropdownMenuCheckboxItem>
                  ))
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
              {selectedLeagues.length > 0 && (
                <>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={selectAllGames}
                    disabled={selectingAll || availableGames.length === 0}
                    className="border-border hover:bg-muted gap-1.5"
                  >
                    <CheckCheck className="w-3.5 h-3.5" />
                    Select All
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={unselectAllGames}
                    disabled={selectingAll || selectedGames.length === 0}
                    className="border-border hover:bg-muted gap-1.5"
                  >
                    <X className="w-3.5 h-3.5" />
                    Clear
                  </Button>
                </>
              )}
              <Button
                variant="outline"
                size="icon"
                className="border-border hover:bg-muted"
                onClick={handleRefresh}
                disabled={refreshing || loading}
              >
                <RefreshCw className={cn("w-4 h-4", (refreshing || loading) && "animate-spin")} />
              </Button>
            </div>
          </div>

          {/* Selected leagues chips */}
          {selectedLeagues.length > 0 && (
            <div className="flex flex-wrap gap-2 mt-3 pt-3 border-t border-border">
              {selectedLeagues.map(league => {
                const leagueInfo = getCurrentLeagues().find(l => l.league_key === league);
                return (
                  <Badge key={league} variant="secondary" className="gap-1 pr-1">
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
            <TabsTrigger value="available" className="gap-2">
              <Eye className="w-4 h-4" />
              Available ({availableGames.length})
            </TabsTrigger>
            <TabsTrigger value="selected" className="gap-2">
              <Check className="w-4 h-4" />
              Selected ({selectedGames.length})
            </TabsTrigger>
          </TabsList>

          <TabsContent value="available" className="mt-4">
            <Card className="bg-card border-border overflow-hidden">
              <div className="p-4 border-b border-border bg-muted/20">
                <h3 className="font-medium text-foreground">Available Games</h3>
                <p className="text-sm text-muted-foreground">
                  Live and upcoming games from ESPN - select games to enable trading
                </p>
              </div>
              <div className="overflow-x-auto">
                {loading ? (
                  <TableSkeleton columns={5} rows={5} />
                ) : (
                  <GamesTable games={availableGames} emptyMessage="No available games found" />
                )}
              </div>
            </Card>
          </TabsContent>

          <TabsContent value="selected" className="mt-4">
            <Card className="bg-card border-border overflow-hidden">
              <div className="p-4 border-b border-border bg-muted/20">
                <h3 className="font-medium text-foreground">Selected for Trading</h3>
                <p className="text-sm text-muted-foreground">
                  These games will be monitored by the bot for trading opportunities
                </p>
              </div>
              <div className="overflow-x-auto">
                {loading ? (
                  <TableSkeleton columns={5} rows={5} />
                ) : (
                  <GamesTable games={selectedGames} emptyMessage="No games selected for trading" />
                )}
              </div>
            </Card>
          </TabsContent>
        </Tabs>

        {/* Help Card */}
        <Card className="p-4 bg-card border-border">
          <div className="flex items-start gap-3">
            <div className="p-2 rounded-lg bg-info/10">
              <Clock className="w-5 h-5 text-info" />
            </div>
            <div>
              <h4 className="font-medium text-foreground">How to Select Games</h4>
              <ul className="text-sm text-muted-foreground mt-1 space-y-1">
                <li>1. Choose a sport category (Basketball, Soccer, etc.)</li>
                <li>2. Select one or more leagues from the dropdown (NBA, EPL, etc.)</li>
                <li>3. Click "Select" on games you want the bot to trade</li>
                <li>4. You can select games from multiple leagues simultaneously</li>
                <li>5. Live game data refreshes automatically from ESPN</li>
              </ul>
            </div>
          </div>
        </Card>
      </div>
    </DashboardLayout>
  );
}
