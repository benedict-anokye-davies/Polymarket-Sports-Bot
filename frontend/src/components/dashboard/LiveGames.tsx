import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { cn } from '@/lib/utils';

interface Game {
  id: string;
  homeTeam: string;
  awayTeam: string;
  homeScore: number;
  awayScore: number;
  period: string;
  probability: number;
  sport: 'NBA' | 'NFL' | 'MLB' | 'NHL';
}

const mockGames: Game[] = [
  { id: '1', homeTeam: 'LAL', awayTeam: 'BOS', homeScore: 112, awayScore: 108, period: 'Q4 2:34', probability: 0.72, sport: 'NBA' },
  { id: '2', homeTeam: 'GSW', awayTeam: 'MIA', homeScore: 98, awayScore: 95, period: 'Q3 8:12', probability: 0.58, sport: 'NBA' },
  { id: '3', homeTeam: 'NYK', awayTeam: 'CHI', homeScore: 86, awayScore: 91, period: 'Q3 4:45', probability: 0.34, sport: 'NBA' },
  { id: '4', homeTeam: 'KC', awayTeam: 'SF', homeScore: 21, awayScore: 17, period: 'Q4 6:02', probability: 0.65, sport: 'NFL' },
  { id: '5', homeTeam: 'NYY', awayTeam: 'BOS', homeScore: 4, awayScore: 3, period: 'Bot 7', probability: 0.55, sport: 'MLB' },
  { id: '6', homeTeam: 'TOR', awayTeam: 'MTL', homeScore: 2, awayScore: 2, period: '3rd 15:22', probability: 0.51, sport: 'NHL' },
];

const sportColors = {
  NBA: 'text-orange-400',
  NFL: 'text-green-400',
  MLB: 'text-red-400',
  NHL: 'text-blue-400',
};

export function LiveGames() {
  return (
    <Card className="bg-card border-border h-full">
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-medium text-foreground flex items-center gap-2">
          <span className="status-dot bg-primary status-dot-pulse" />
          Live Games
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-0">
        <div className="max-h-[320px] overflow-y-auto scrollbar-thin space-y-2">
          {mockGames.map((game) => (
            <div
              key={game.id}
              className="p-3 rounded-md bg-muted/30 hover:bg-muted/50 transition-colors border border-transparent hover:border-border"
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className={cn('text-xs font-medium', sportColors[game.sport])}>
                    {game.sport}
                  </span>
                  <span className="text-sm text-foreground font-medium">
                    {game.awayTeam} @ {game.homeTeam}
                  </span>
                </div>
                <span className="text-xs text-muted-foreground font-mono-numbers">
                  {game.period}
                </span>
              </div>
              
              <div className="flex items-center justify-between">
                <span className="text-lg font-mono-numbers text-foreground">
                  {game.awayScore} - {game.homeScore}
                </span>
                <div className="flex items-center gap-2">
                  <div className="w-24 h-2 bg-muted rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-primary/80 to-primary rounded-full transition-all duration-300"
                      style={{ width: `${game.probability * 100}%` }}
                    />
                  </div>
                  <span className="text-sm font-mono-numbers text-primary w-12 text-right">
                    {(game.probability * 100).toFixed(0)}%
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
