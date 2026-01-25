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
import { apiClient, type TradingParameters, type BotConfigResponse } from '@/api/client';

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

// Mock games data - in production this comes from ESPN/API
const MOCK_GAMES: Record<string, Array<{
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
}>> = {
  nba: [
    { id: 'nba-1', homeTeam: 'Lakers', awayTeam: 'Celtics', startTime: '7:30 PM ET', status: 'live', currentPeriod: 'Q2', clock: '5:23', homeOdds: 0.45, awayOdds: 0.55, volume: 125000 },
    { id: 'nba-2', homeTeam: 'Warriors', awayTeam: 'Nets', startTime: '10:00 PM ET', status: 'upcoming', homeOdds: 0.72, awayOdds: 0.28, volume: 85000 },
    { id: 'nba-3', homeTeam: 'Bucks', awayTeam: 'Heat', startTime: '8:00 PM ET', status: 'upcoming', homeOdds: 0.65, awayOdds: 0.35, volume: 92000 },
  ],
  nfl: [
    { id: 'nfl-1', homeTeam: 'Chiefs', awayTeam: 'Bills', startTime: '4:25 PM ET', status: 'live', currentPeriod: 'Q3', clock: '8:45', homeOdds: 0.58, awayOdds: 0.42, volume: 450000 },
    { id: 'nfl-2', homeTeam: 'Eagles', awayTeam: '49ers', startTime: '8:20 PM ET', status: 'upcoming', homeOdds: 0.48, awayOdds: 0.52, volume: 380000 },
  ],
  mlb: [
    { id: 'mlb-1', homeTeam: 'Yankees', awayTeam: 'Red Sox', startTime: '7:05 PM ET', status: 'live', currentPeriod: '5th', clock: 'Top', homeOdds: 0.55, awayOdds: 0.45, volume: 65000 },
    { id: 'mlb-2', homeTeam: 'Dodgers', awayTeam: 'Giants', startTime: '10:10 PM ET', status: 'upcoming', homeOdds: 0.62, awayOdds: 0.38, volume: 72000 },
  ],
  nhl: [
    { id: 'nhl-1', homeTeam: 'Bruins', awayTeam: 'Rangers', startTime: '7:00 PM ET', status: 'live', currentPeriod: 'P2', clock: '12:34', homeOdds: 0.52, awayOdds: 0.48, volume: 45000 },
  ],
  soccer: [
    { id: 'soccer-1', homeTeam: 'Man City', awayTeam: 'Liverpool', startTime: '12:30 PM ET', status: 'upcoming', homeOdds: 0.55, awayOdds: 0.45, volume: 320000 },
    { id: 'soccer-2', homeTeam: 'Real Madrid', awayTeam: 'Barcelona', startTime: '3:00 PM ET', status: 'upcoming', homeOdds: 0.48, awayOdds: 0.52, volume: 410000 },
  ],
  ncaab: [
    { id: 'ncaab-1', homeTeam: 'Duke', awayTeam: 'UNC', startTime: '9:00 PM ET', status: 'upcoming', homeOdds: 0.58, awayOdds: 0.42, volume: 125000 },
    { id: 'ncaab-2', homeTeam: 'Kansas', awayTeam: 'Kentucky', startTime: '7:00 PM ET', status: 'live', currentPeriod: '1H', clock: '8:12', homeOdds: 0.51, awayOdds: 0.49, volume: 98000 },
  ],
  tennis: [
    { id: 'tennis-1', homeTeam: 'Djokovic', awayTeam: 'Alcaraz', startTime: '11:00 AM ET', status: 'live', currentPeriod: 'Set 2', homeOdds: 0.45, awayOdds: 0.55, volume: 85000 },
  ],
  cricket: [
    { id: 'cricket-1', homeTeam: 'India', awayTeam: 'Australia', startTime: '4:00 AM ET', status: 'upcoming', homeOdds: 0.52, awayOdds: 0.48, volume: 220000 },
  ],
  ufc: [
    { id: 'ufc-1', homeTeam: 'Jones', awayTeam: 'Miocic', startTime: '10:00 PM ET', status: 'upcoming', homeOdds: 0.75, awayOdds: 0.25, volume: 180000 },
  ],
};

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
  const [selectedGame, setSelectedGame] = useState<string>('');
  const [tradingParams, setTradingParams] = useState<TradingParams>(DEFAULT_PARAMS);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Load existing bot config on mount
  useEffect(() => {
    const loadConfig = async () => {
      try {
        const config: BotConfigResponse = await apiClient.getBotConfig();
        setBotEnabled(config.is_running);
        if (config.sport) setSelectedSport(config.sport);
        if (config.game) setSelectedGame(config.game.game_id);
        if (config.parameters) setTradingParams(fromApiParams(config.parameters));
      } catch (err) {
        console.log('No existing config found, using defaults');
      }
    };
    loadConfig();
  }, []);

  // Get current sport config
  const currentSport = SPORTS.find(s => s.id === selectedSport);
  const availableGames = MOCK_GAMES[selectedSport] || [];

  // Get selected game details
  const selectedGameData = availableGames.find(g => g.id === selectedGame);

  // Handle sport change
  const handleSportChange = (sportId: string) => {
    setSelectedSport(sportId);
    setSelectedGame(''); // Reset game selection
    setError(null);
    setSuccessMessage(null);
  };

  // Handle parameter change
  const updateParam = (key: keyof TradingParams, value: number) => {
    setTradingParams(prev => ({ ...prev, [key]: value }));
  };

  // Save configuration to API
  const handleSave = useCallback(async () => {
    if (!selectedGameData) {
      setError('Please select a game first');
      return;
    }
    
    setIsSaving(true);
    setError(null);
    setSuccessMessage(null);
    
    try {
      await apiClient.saveBotConfig({
        sport: selectedSport,
        game: {
          game_id: selectedGame,
          sport: selectedSport,
          home_team: selectedGameData.homeTeam,
          away_team: selectedGameData.awayTeam,
          start_time: selectedGameData.startTime,
        },
        parameters: toApiParams(tradingParams),
      });
      setSuccessMessage('Configuration saved successfully!');
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save configuration');
    } finally {
      setIsSaving(false);
    }
  }, [selectedSport, selectedGame, selectedGameData, tradingParams]);

  // Toggle bot on/off
  const handleToggleBot = useCallback(async () => {
    if (!selectedGame) {
      setError('Please select a game first');
      return;
    }
    
    setIsLoading(true);
    setError(null);
    
    try {
      // First save the config
      if (selectedGameData) {
        await apiClient.saveBotConfig({
          sport: selectedSport,
          game: {
            game_id: selectedGame,
            sport: selectedSport,
            home_team: selectedGameData.homeTeam,
            away_team: selectedGameData.awayTeam,
            start_time: selectedGameData.startTime,
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
        setSuccessMessage('Bot started');
      }
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to toggle bot');
    } finally {
      setIsLoading(false);
    }
  }, [botEnabled, selectedGame, selectedGameData, selectedSport, tradingParams]);

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
              Select a game and configure trading parameters
            </p>
          </div>
          <div className="flex items-center gap-4">
            <Badge 
              variant={botEnabled ? 'default' : 'secondary'} 
              className={cn(
                'px-3 py-1',
                botEnabled && 'bg-green-500/20 text-green-400 border border-green-500/30'
              )}
            >
              {botEnabled ? 'Bot Running' : 'Bot Stopped'}
            </Badge>
            <Button
              onClick={handleToggleBot}
              variant={botEnabled ? 'destructive' : 'default'}
              disabled={isLoading || !selectedGame}
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
                  Choose a sport and game to trade on
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

                {/* Game Selector */}
                <div className="space-y-2">
                  <Label>Game</Label>
                  <Select value={selectedGame} onValueChange={setSelectedGame}>
                    <SelectTrigger>
                      <SelectValue placeholder="Select game" />
                    </SelectTrigger>
                    <SelectContent>
                      {availableGames.length === 0 ? (
                        <SelectItem value="none" disabled>
                          No games available
                        </SelectItem>
                      ) : (
                        availableGames.map(game => (
                          <SelectItem key={game.id} value={game.id}>
                            <span className="flex items-center gap-2">
                              <Badge 
                                variant={game.status === 'live' ? 'default' : 'secondary'}
                                className={cn(
                                  'text-xs',
                                  game.status === 'live' && 'bg-red-500/20 text-red-400'
                                )}
                              >
                                {game.status === 'live' ? 'LIVE' : 'Upcoming'}
                              </Badge>
                              <span>{game.awayTeam} @ {game.homeTeam}</span>
                            </span>
                          </SelectItem>
                        ))
                      )}
                    </SelectContent>
                  </Select>
                </div>

                {/* Selected Game Info */}
                {selectedGameData && (
                  <div className="mt-4 p-4 rounded-lg bg-muted/50 space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">Matchup</span>
                      <span className="font-medium">
                        {selectedGameData.awayTeam} @ {selectedGameData.homeTeam}
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">Start Time</span>
                      <span className="font-medium">{selectedGameData.startTime}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">Status</span>
                      <Badge variant={selectedGameData.status === 'live' ? 'default' : 'secondary'}>
                        {selectedGameData.status === 'live' 
                          ? `${selectedGameData.currentPeriod} - ${selectedGameData.clock}`
                          : 'Upcoming'
                        }
                      </Badge>
                    </div>
                    <Separator />
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">{selectedGameData.homeTeam} Win</span>
                      <span className="font-mono text-primary">
                        {(selectedGameData.homeOdds * 100).toFixed(0)}%
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">{selectedGameData.awayTeam} Win</span>
                      <span className="font-mono text-primary">
                        {(selectedGameData.awayOdds * 100).toFixed(0)}%
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">Volume</span>
                      <span className="font-mono">
                        ${selectedGameData.volume.toLocaleString()}
                      </span>
                    </div>
                  </div>
                )}

                {/* Refresh Button */}
                <Button variant="outline" className="w-full gap-2">
                  <RefreshCw className="w-4 h-4" />
                  Refresh Games
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
            <div className="text-sm text-muted-foreground">Selected Game</div>
            <div className="text-lg font-semibold truncate">
              {selectedGameData 
                ? `${selectedGameData.awayTeam} @ ${selectedGameData.homeTeam}`
                : 'None'
              }
            </div>
          </Card>
          <Card className="p-4">
            <div className="text-sm text-muted-foreground">Position Size</div>
            <div className="text-lg font-semibold">${tradingParams.positionSize}</div>
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
      </div>
    </DashboardLayout>
  );
}
