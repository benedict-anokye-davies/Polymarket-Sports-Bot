import { useState, useEffect, useCallback } from 'react';
import {
  Bot,
  Play,
  Pause,
  Settings2,
  Zap,
  Clock,
  Target,
  TrendingUp,
  TrendingDown,
  Shield,
  Check,
  Loader2,
  RefreshCw,
  Calendar,
  Timer,
  DollarSign,
  BarChart3,
  AlertTriangle,
  CheckCircle2,
  X,
  FlaskConical,
  Wallet,
} from 'lucide-react';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Slider } from '@/components/ui/slider';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Separator } from '@/components/ui/separator';
import { cn } from '@/lib/utils';
import { apiClient, type TradingParameters, type BotConfigResponse, type ESPNGame } from '@/api/client';

// All supported sports with their configurations
const SPORTS = [
  { id: 'nba', name: 'NBA', icon: '🏀', hasGameClock: true },
  { id: 'nfl', name: 'NFL', icon: '🏈', hasGameClock: true },
  { id: 'mlb', name: 'MLB', icon: '⚾', hasGameClock: false },
  { id: 'nhl', name: 'NHL', icon: '🏒', hasGameClock: true },
  { id: 'soccer', name: 'Soccer', icon: '⚽', hasGameClock: true },
  { id: 'ncaab', name: 'NCAA CBB', icon: '🏀', hasGameClock: true },
  { id: 'tennis', name: 'Tennis', icon: '🎾', hasGameClock: false },
  { id: 'cricket', name: 'Cricket', icon: '🏏', hasGameClock: false },
  { id: 'ufc', name: 'UFC', icon: '🥊', hasGameClock: true },
];

// Game type for frontend display
interface GameData {
  id: string;
  homeTeam: string;
  awayTeam: string;
  startTime: string;
  status: 'upcoming' | 'live' | 'final';
  currentPeriod?: string;
  clock?: string;
  homeOdds: number;
  awayOdds: number;
  volume: number;
}

// Trading parameters interface (matches API TradingParameters)
interface TradingParams {
  probabilityDrop: number;      // % drop from pregame to trigger entry
  minVolume: number;            // Minimum market volume ($)
  positionSize: number;         // Max investment per market ($)
  takeProfit: number;           // Take profit %
  stopLoss: number;             // Stop loss %
  latestEntryTime: number;      // Minutes remaining - no buys after this
  latestExitTime: number;       // Minutes remaining - must sell by this
}

// Default parameters
const DEFAULT_PARAMS: TradingParams = {
  probabilityDrop: 15,
  minVolume: 50000,
  positionSize: 100,
  takeProfit: 25,
  stopLoss: 15,
  latestEntryTime: 10,
  latestExitTime: 2,
};

// Convert local params to API format
const toApiParams = (params: TradingParams): TradingParameters => ({
  probability_drop: params.probabilityDrop,
  min_volume: params.minVolume,
  position_size: params.positionSize,
  take_profit: params.takeProfit,
  stop_loss: params.stopLoss,
  latest_entry_time: params.latestEntryTime,
  latest_exit_time: params.latestExitTime,
});

// Convert API params to local format
const fromApiParams = (params: TradingParameters): TradingParams => ({
  probabilityDrop: params.probability_drop,
  minVolume: params.min_volume,
  positionSize: params.position_size,
  takeProfit: params.take_profit,
  stopLoss: params.stop_loss,
  latestEntryTime: params.latest_entry_time,
  latestExitTime: params.latest_exit_time,
});

export default function BotConfig() {
  const [botEnabled, setBotEnabled] = useState(false);
  const [selectedSport, setSelectedSport] = useState<string>('nba');
  const [selectedGames, setSelectedGames] = useState<Set<string>>(new Set());
  const [tradingParams, setTradingParams] = useState<TradingParams>(DEFAULT_PARAMS);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  
  // Simulation mode - test bot without real money
  const [simulationMode, setSimulationMode] = useState(true);

  // Load existing bot config on mount
  useEffect(() => {
    const loadConfig = async () => {
      try {
        const config: BotConfigResponse = await apiClient.getBotConfig();
        setBotEnabled(config.is_running);
        if (config.sport) setSelectedSport(config.sport);
        if (config.game) setSelectedGames(new Set([config.game.game_id]));
        if (config.parameters) setTradingParams(fromApiParams(config.parameters));
      } catch (err) {
        console.log('No existing config found, using defaults');
      }
    };
    loadConfig();
  }, []);

  // State for real games from ESPN
  const [availableGames, setAvailableGames] = useState<GameData[]>([]);
  const [isLoadingGames, setIsLoadingGames] = useState(false);

  // Fetch games from ESPN API when sport changes
  const fetchGames = useCallback(async (sport: string) => {
    setIsLoadingGames(true);
    setError(null);
    try {
      const games = await apiClient.getLiveGames(sport);
      // Transform ESPN games to our GameData format
      const transformed: GameData[] = games.map((g) => ({
        id: g.id,
        homeTeam: g.homeTeam,
        awayTeam: g.awayTeam,
        startTime: g.startTime 
          ? new Date(g.startTime).toLocaleString('en-US', { 
              hour: 'numeric', 
              minute: '2-digit', 
              timeZoneName: 'short' 
            })
          : 'TBD',
        status: g.status,
        currentPeriod: g.currentPeriod,
        clock: g.clock,
        homeOdds: g.homeOdds,
        awayOdds: g.awayOdds,
        volume: g.volume,
      }));
      setAvailableGames(transformed);
    } catch (err) {
      console.error('Failed to fetch games:', err);
      setAvailableGames([]);
      // Don't show error to user - just show empty list
    } finally {
      setIsLoadingGames(false);
    }
  }, []);

  // Fetch games when sport changes
  useEffect(() => {
    fetchGames(selectedSport);
  }, [selectedSport, fetchGames]);

  // Get current sport config
  const currentSport = SPORTS.find(s => s.id === selectedSport);

  // Get selected games data
  const selectedGamesData = availableGames.filter(g => selectedGames.has(g.id));

  // Toggle game selection
  const toggleGameSelection = (gameId: string) => {
    setSelectedGames(prev => {
      const newSet = new Set(prev);
      if (newSet.has(gameId)) {
        newSet.delete(gameId);
      } else {
        newSet.add(gameId);
      }
      return newSet;
    });
  };

  // Select all games
  const selectAllGames = () => {
    setSelectedGames(new Set(availableGames.map(g => g.id)));
  };

  // Clear all selections
  const clearAllGames = () => {
    setSelectedGames(new Set());
  };

  // Handle sport change
  const handleSportChange = (sportId: string) => {
    setSelectedSport(sportId);
    setSelectedGames(new Set()); // Reset game selection
    setError(null);
    setSuccessMessage(null);
  };

  // Handle parameter change
  const updateParam = (key: keyof TradingParams, value: number) => {
    setTradingParams(prev => ({ ...prev, [key]: value }));
  };

  // Save configuration to API
  const handleSave = useCallback(async () => {
    if (selectedGames.size === 0) {
      setError('Please select at least one game');
      return;
    }
    
    setIsSaving(true);
    setError(null);
    setSuccessMessage(null);
    
    try {
      // Save config for the first selected game (API will handle multiple games)
      const firstGame = selectedGamesData[0];
      if (firstGame) {
        await apiClient.saveBotConfig({
          sport: selectedSport,
          game: {
            game_id: firstGame.id,
            sport: selectedSport,
            home_team: firstGame.homeTeam,
            away_team: firstGame.awayTeam,
            start_time: firstGame.startTime,
          },
          parameters: toApiParams(tradingParams),
        });
      }
      setSuccessMessage(`Configuration saved for ${selectedGames.size} game${selectedGames.size > 1 ? 's' : ''}!`);
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save configuration');
    } finally {
      setIsSaving(false);
    }
  }, [selectedSport, selectedGames.size, selectedGamesData, tradingParams]);

  // Toggle bot on/off
  const handleToggleBot = useCallback(async () => {
    if (selectedGames.size === 0) {
      setError('Please select at least one game');
      return;
    }
    
    setIsLoading(true);
    setError(null);
    
    try {
      // First save the config
      const firstGame = selectedGamesData[0];
      if (firstGame) {
        await apiClient.saveBotConfig({
          sport: selectedSport,
          game: {
            game_id: firstGame.id,
            sport: selectedSport,
            home_team: firstGame.homeTeam,
            away_team: firstGame.awayTeam,
            start_time: firstGame.startTime,
          },
          parameters: toApiParams(tradingParams),
        });
      }
      
      // Then start/stop the bot
      if (botEnabled) {
        await apiClient.stopBot();
        setBotEnabled(false);
        setSuccessMessage('Bot stopped');
      } else {
        await apiClient.startBot();
        setBotEnabled(true);
        setSuccessMessage(`Bot started monitoring ${selectedGames.size} game${selectedGames.size > 1 ? 's' : ''}`);
      }
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to toggle bot');
    } finally {
      setIsLoading(false);
    }
  }, [botEnabled, selectedGames.size, selectedGamesData, selectedSport, tradingParams]);

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-foreground flex items-center gap-2">
              <Bot className="w-6 h-6" />
              Bot Configuration
            </h1>
            <p className="text-muted-foreground mt-1">
              Select games and configure trading parameters
            </p>
          </div>
          <div className="flex items-center gap-4">
            {/* Simulation Mode Toggle */}
            <div 
              onClick={() => setSimulationMode(!simulationMode)}
              className={cn(
                'flex items-center gap-2 px-3 py-1.5 rounded-lg cursor-pointer transition-all border',
                simulationMode 
                  ? 'bg-yellow-500/10 border-yellow-500/30 text-yellow-400' 
                  : 'bg-green-500/10 border-green-500/30 text-green-400'
              )}
            >
              {simulationMode ? (
                <>
                  <FlaskConical className="w-4 h-4" />
                  <span className="text-sm font-medium">Paper Trading</span>
                </>
              ) : (
                <>
                  <Wallet className="w-4 h-4" />
                  <span className="text-sm font-medium">Live Trading</span>
                </>
              )}
            </div>
            <Badge 
              variant={botEnabled ? 'default' : 'secondary'} 
              className={cn(
                'px-3 py-1',
                botEnabled && 'bg-green-500/20 text-green-400 border border-green-500/30'
              )}
            >
              {botEnabled ? `Bot Running (${selectedGames.size} game${selectedGames.size !== 1 ? 's' : ''})` : 'Bot Stopped'}
            </Badge>
            <Button
              onClick={handleToggleBot}
              variant={botEnabled ? 'destructive' : 'default'}
              disabled={isLoading || selectedGames.size === 0}
              className="gap-2"
            >
              {isLoading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : botEnabled ? (
                <Pause className="w-4 h-4" />
              ) : (
                <Play className="w-4 h-4" />
              )}
              {botEnabled ? 'Stop Bot' : 'Start Bot'}
            </Button>
          </div>
        </div>

        {/* Error/Success Messages */}
        {/* Simulation Mode Banner */}
        {simulationMode && (
          <div className="p-4 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
            <div className="flex items-start gap-3">
              <FlaskConical className="w-5 h-5 text-yellow-400 mt-0.5" />
              <div>
                <h3 className="font-semibold text-yellow-400">Paper Trading Mode (Simulation)</h3>
                <p className="text-sm text-yellow-400/80 mt-1">
                  The bot will simulate trades without using real money. Perfect for testing your strategy.
                  All trades will be logged but no actual orders will be placed on Polymarket.
                </p>
                <button 
                  onClick={() => setSimulationMode(false)}
                  className="mt-2 text-xs text-yellow-400 underline hover:no-underline"
                >
                  Switch to Live Trading
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Error/Success Messages */}
        {error && (
          <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4" />
            {error}
          </div>
        )}
        {successMessage && (
          <div className="p-4 bg-green-500/10 border border-green-500/30 rounded-lg text-green-400 flex items-center gap-2">
            <Check className="w-4 h-4" />
            {successMessage}
          </div>
        )}

        {/* Main Content */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column - Game Selection */}
          <div className="lg:col-span-1 space-y-4">
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-lg flex items-center gap-2">
                  <Calendar className="w-5 h-5" />
                  Game Selection
                </CardTitle>
                <CardDescription>
                  Select multiple games to trade on simultaneously
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Sport Selector */}
                <div className="space-y-2">
                  <Label>Sport</Label>
                  <Select value={selectedSport} onValueChange={handleSportChange}>
                    <SelectTrigger>
                      <SelectValue placeholder="Select sport" />
                    </SelectTrigger>
                    <SelectContent>
                      {SPORTS.map(sport => (
                        <SelectItem key={sport.id} value={sport.id}>
                          <span className="flex items-center gap-2">
                            <span>{sport.icon}</span>
                            <span>{sport.name}</span>
                          </span>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {/* Games List Header */}
                <div className="flex items-center justify-between pt-2">
                  <Label>
                    Games {isLoadingGames && <span className="text-xs text-muted-foreground">(loading...)</span>}
                  </Label>
                  <div className="flex gap-2">
                    <Button 
                      variant="ghost" 
                      size="sm" 
                      onClick={selectAllGames}
                      disabled={availableGames.length === 0}
                      className="text-xs h-7"
                    >
                      Select All
                    </Button>
                    <Button 
                      variant="ghost" 
                      size="sm" 
                      onClick={clearAllGames}
                      disabled={selectedGames.size === 0}
                      className="text-xs h-7"
                    >
                      Clear
                    </Button>
                  </div>
                </div>

                {/* Games List - Multi-select with checkboxes */}
                <div className="space-y-2 max-h-[350px] overflow-y-auto pr-1">
                  {isLoadingGames ? (
                    <div className="flex items-center justify-center py-8">
                      <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
                      <span className="ml-2 text-muted-foreground">Loading games from ESPN...</span>
                    </div>
                  ) : availableGames.length === 0 ? (
                    <div className="text-center py-8 text-muted-foreground">
                      <Calendar className="w-8 h-8 mx-auto mb-2 opacity-50" />
                      <p>No games scheduled</p>
                      <p className="text-xs mt-1">Try selecting a different sport</p>
                    </div>
                  ) : (
                    availableGames.map(game => (
                      <div
                        key={game.id}
                        onClick={() => toggleGameSelection(game.id)}
                        className={cn(
                          'p-3 rounded-lg border cursor-pointer transition-all',
                          selectedGames.has(game.id)
                            ? 'bg-primary/10 border-primary/50'
                            : 'bg-muted/30 border-border hover:border-primary/30'
                        )}
                      >
                        <div className="flex items-start justify-between">
                          <div className="flex-1">
                            <div className="flex items-center gap-2 mb-1">
                              <Badge 
                                variant={game.status === 'live' ? 'default' : 'secondary'}
                                className={cn(
                                  'text-xs',
                                  game.status === 'live' && 'bg-red-500/20 text-red-400 animate-pulse'
                                )}
                              >
                                {game.status === 'live' ? 'LIVE' : game.status === 'final' ? 'Final' : 'Upcoming'}
                              </Badge>
                              {game.status === 'live' && game.currentPeriod && (
                                <span className="text-xs text-muted-foreground">
                                  {game.currentPeriod} {game.clock}
                                </span>
                              )}
                            </div>
                            <p className="font-medium text-sm">
                              {game.awayTeam} @ {game.homeTeam}
                            </p>
                            <p className="text-xs text-muted-foreground mt-1">
                              {game.startTime}
                            </p>
                          </div>
                          <div className={cn(
                            'w-5 h-5 rounded-full border-2 flex items-center justify-center transition-colors mt-1',
                            selectedGames.has(game.id)
                              ? 'bg-primary border-primary'
                              : 'border-muted-foreground/30'
                          )}>
                            {selectedGames.has(game.id) && (
                              <Check className="w-3 h-3 text-primary-foreground" />
                            )}
                          </div>
                        </div>
                      </div>
                    ))
                  )}
                </div>

                {/* Selection Summary */}
                {selectedGames.size > 0 && (
                  <div className="p-3 rounded-lg bg-primary/10 border border-primary/30">
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="w-4 h-4 text-primary" />
                      <span className="text-sm font-medium">
                        {selectedGames.size} game{selectedGames.size > 1 ? 's' : ''} selected
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground mt-1">
                      Bot will monitor all selected games simultaneously
                    </p>
                  </div>
                )}

                {/* Refresh Button */}
                <Button 
                  variant="outline" 
                  className="w-full gap-2"
                  onClick={() => fetchGames(selectedSport)}
                  disabled={isLoadingGames}
                >
                  {isLoadingGames ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <RefreshCw className="w-4 h-4" />
                  )}
                  {isLoadingGames ? 'Loading...' : 'Refresh Games'}
                </Button>
              </CardContent>
            </Card>
          </div>

          {/* Right Column - Trading Parameters */}
          <div className="lg:col-span-2">
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-lg flex items-center gap-2">
                  <Settings2 className="w-5 h-5" />
                  Trading Parameters
                </CardTitle>
                <CardDescription>
                  Configure entry/exit conditions and position sizing
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* Entry Conditions */}
                <div>
                  <h3 className="text-sm font-semibold text-foreground mb-4 flex items-center gap-2">
                    <Target className="w-4 h-4 text-primary" />
                    Entry Conditions
                  </h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    {/* Probability Drop */}
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <Label className="flex items-center gap-2">
                          <TrendingDown className="w-4 h-4 text-red-400" />
                          Probability Drop
                        </Label>
                        <span className="font-mono text-sm text-primary">
                          {tradingParams.probabilityDrop}%
                        </span>
                      </div>
                      <p className="text-xs text-muted-foreground">
                        Minimum drop from pregame odds to trigger entry
                      </p>
                      <Slider
                        value={[tradingParams.probabilityDrop]}
                        onValueChange={([v]) => updateParam('probabilityDrop', v)}
                        min={5}
                        max={50}
                        step={1}
                      />
                      <div className="flex justify-between text-xs text-muted-foreground">
                        <span>5%</span>
                        <span>50%</span>
                      </div>
                    </div>

                    {/* Minimum Volume */}
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <Label className="flex items-center gap-2">
                          <BarChart3 className="w-4 h-4 text-blue-400" />
                          Minimum Volume
                        </Label>
                        <span className="font-mono text-sm text-primary">
                          ${tradingParams.minVolume.toLocaleString()}
                        </span>
                      </div>
                      <p className="text-xs text-muted-foreground">
                        Minimum market volume to enter a position
                      </p>
                      <Slider
                        value={[tradingParams.minVolume]}
                        onValueChange={([v]) => updateParam('minVolume', v)}
                        min={10000}
                        max={500000}
                        step={10000}
                      />
                      <div className="flex justify-between text-xs text-muted-foreground">
                        <span>$10K</span>
                        <span>$500K</span>
                      </div>
                    </div>
                  </div>
                </div>

                <Separator />

                {/* Position Sizing */}
                <div>
                  <h3 className="text-sm font-semibold text-foreground mb-4 flex items-center gap-2">
                    <DollarSign className="w-4 h-4 text-primary" />
                    Position Sizing
                  </h3>
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <Label className="flex items-center gap-2">
                        <Zap className="w-4 h-4 text-yellow-400" />
                        Position Size
                      </Label>
                      <span className="font-mono text-sm text-primary">
                        ${tradingParams.positionSize}
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      Maximum amount to invest in this market
                    </p>
                    <Slider
                      value={[tradingParams.positionSize]}
                      onValueChange={([v]) => updateParam('positionSize', v)}
                      min={10}
                      max={1000}
                      step={10}
                    />
                    <div className="flex justify-between text-xs text-muted-foreground">
                      <span>$10</span>
                      <span>$1,000</span>
                    </div>
                  </div>
                </div>

                <Separator />

                {/* Exit Conditions */}
                <div>
                  <h3 className="text-sm font-semibold text-foreground mb-4 flex items-center gap-2">
                    <Shield className="w-4 h-4 text-primary" />
                    Exit Conditions
                  </h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    {/* Take Profit */}
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <Label className="flex items-center gap-2">
                          <TrendingUp className="w-4 h-4 text-green-400" />
                          Take Profit
                        </Label>
                        <span className="font-mono text-sm text-green-400">
                          +{tradingParams.takeProfit}%
                        </span>
                      </div>
                      <p className="text-xs text-muted-foreground">
                        Automatically sell when profit reaches this level
                      </p>
                      <Slider
                        value={[tradingParams.takeProfit]}
                        onValueChange={([v]) => updateParam('takeProfit', v)}
                        min={5}
                        max={100}
                        step={5}
                      />
                      <div className="flex justify-between text-xs text-muted-foreground">
                        <span>5%</span>
                        <span>100%</span>
                      </div>
                    </div>

                    {/* Stop Loss */}
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <Label className="flex items-center gap-2">
                          <AlertTriangle className="w-4 h-4 text-red-400" />
                          Stop Loss
                        </Label>
                        <span className="font-mono text-sm text-red-400">
                          -{tradingParams.stopLoss}%
                        </span>
                      </div>
                      <p className="text-xs text-muted-foreground">
                        Automatically sell to limit losses
                      </p>
                      <Slider
                        value={[tradingParams.stopLoss]}
                        onValueChange={([v]) => updateParam('stopLoss', v)}
                        min={5}
                        max={50}
                        step={5}
                      />
                      <div className="flex justify-between text-xs text-muted-foreground">
                        <span>5%</span>
                        <span>50%</span>
                      </div>
                    </div>
                  </div>
                </div>

                <Separator />

                {/* Time-Based Rules */}
                <div>
                  <h3 className="text-sm font-semibold text-foreground mb-4 flex items-center gap-2">
                    <Timer className="w-4 h-4 text-primary" />
                    Time-Based Rules
                    {!currentSport?.hasGameClock && (
                      <Badge variant="secondary" className="text-xs">
                        N/A for {currentSport?.name}
                      </Badge>
                    )}
                  </h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    {/* Latest Entry Time */}
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <Label className="flex items-center gap-2">
                          <Clock className="w-4 h-4 text-orange-400" />
                          Latest Entry Time
                        </Label>
                        <span className="font-mono text-sm text-primary">
                          {tradingParams.latestEntryTime} min
                        </span>
                      </div>
                      <p className="text-xs text-muted-foreground">
                        No new positions after this much time remaining
                      </p>
                      <Slider
                        value={[tradingParams.latestEntryTime]}
                        onValueChange={([v]) => updateParam('latestEntryTime', v)}
                        min={1}
                        max={30}
                        step={1}
                        disabled={!currentSport?.hasGameClock}
                      />
                      <div className="flex justify-between text-xs text-muted-foreground">
                        <span>1 min</span>
                        <span>30 min</span>
                      </div>
                    </div>

                    {/* Latest Exit Time */}
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <Label className="flex items-center gap-2">
                          <Clock className="w-4 h-4 text-purple-400" />
                          Latest Exit Time
                        </Label>
                        <span className="font-mono text-sm text-primary">
                          {tradingParams.latestExitTime} min
                        </span>
                      </div>
                      <p className="text-xs text-muted-foreground">
                        Must close all positions by this time remaining
                      </p>
                      <Slider
                        value={[tradingParams.latestExitTime]}
                        onValueChange={([v]) => updateParam('latestExitTime', v)}
                        min={0}
                        max={15}
                        step={1}
                        disabled={!currentSport?.hasGameClock}
                      />
                      <div className="flex justify-between text-xs text-muted-foreground">
                        <span>0 min</span>
                        <span>15 min</span>
                      </div>
                    </div>
                  </div>
                </div>

                <Separator />

                {/* Save Button */}
                <div className="flex justify-end gap-3">
                  <Button 
                    variant="outline" 
                    onClick={() => setTradingParams(DEFAULT_PARAMS)}
                  >
                    Reset to Defaults
                  </Button>
                  <Button 
                    onClick={handleSave} 
                    disabled={isSaving}
                    className="gap-2"
                  >
                    {isSaving ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <Check className="w-4 h-4" />
                    )}
                    Save Configuration
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>

        {/* Quick Stats Footer */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card className="p-4">
            <div className="text-sm text-muted-foreground">Selected Games</div>
            <div className="text-lg font-semibold">
              {selectedGames.size > 0 
                ? `${selectedGames.size} game${selectedGames.size !== 1 ? 's' : ''}`
                : 'None'
              }
            </div>
          </Card>
          <Card className="p-4">
            <div className="text-sm text-muted-foreground">Max Exposure</div>
            <div className="text-lg font-semibold">${tradingParams.positionSize * Math.max(1, selectedGames.size)}</div>
          </Card>
          <Card className="p-4">
            <div className="text-sm text-muted-foreground">Risk/Reward</div>
            <div className="text-lg font-semibold">
              <span className="text-red-400">-{tradingParams.stopLoss}%</span>
              {' / '}
              <span className="text-green-400">+{tradingParams.takeProfit}%</span>
            </div>
          </Card>
          <Card className="p-4">
            <div className="text-sm text-muted-foreground">Bot Status</div>
            <div className={cn(
              'text-lg font-semibold',
              botEnabled ? 'text-green-400' : 'text-muted-foreground'
            )}>
              {botEnabled ? 'Active' : 'Inactive'}
            </div>
          </Card>
        </div>

        {/* Selected Games Summary - shown below stats when games are selected */}
        {selectedGames.size > 0 && (
          <Card className="p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Zap className="w-4 h-4 text-primary" />
                <span className="font-medium">Active Game Selection</span>
              </div>
              <Badge variant="outline">{selectedGames.size} game{selectedGames.size !== 1 ? 's' : ''}</Badge>
            </div>
            <div className="flex flex-wrap gap-2">
              {selectedGamesData.map(game => (
                <Badge 
                  key={game.id} 
                  variant="secondary"
                  className="flex items-center gap-1 pr-1"
                >
                  <span className={cn(
                    game.status === 'live' && 'text-red-400'
                  )}>
                    {game.awayTeam} @ {game.homeTeam}
                  </span>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      toggleGameSelection(game.id);
                    }}
                    className="ml-1 hover:bg-muted rounded p-0.5"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </Badge>
              ))}
            </div>
          </Card>
        )}
      </div>
    </DashboardLayout>
  );
}
