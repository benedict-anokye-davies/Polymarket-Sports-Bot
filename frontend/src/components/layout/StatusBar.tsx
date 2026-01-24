import { Wallet, Play, Pause, Wifi, WifiOff } from 'lucide-react';
import { format } from 'date-fns';
import { cn } from '@/lib/utils';
import { useAppStore } from '@/stores/useAppStore';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';

export function StatusBar() {
  const { wallet, bot, connection, toggleBot } = useAppStore();

  return (
    <header className="h-header bg-card border-b border-border flex items-center justify-between px-6 sticky top-0 z-40">
      {/* Wallet Status */}
      <div className="flex items-center gap-3">
        <div className={cn(
          'flex items-center gap-2 px-3 py-1.5 rounded-md border',
          wallet.connected 
            ? 'bg-primary/5 border-primary/20' 
            : 'bg-muted border-border'
        )}>
          <div className={cn(
            'status-dot',
            wallet.connected ? 'bg-primary status-dot-pulse' : 'bg-muted-foreground'
          )} />
          <Wallet className="w-4 h-4 text-muted-foreground" />
          <span className="text-sm font-mono-numbers text-foreground">
            {wallet.connected ? wallet.address : 'Not Connected'}
          </span>
        </div>
      </div>

      {/* Bot Status */}
      <div className="flex items-center gap-3">
        <div className={cn(
          'flex items-center gap-2 px-3 py-1.5 rounded-md border',
          bot.running 
            ? 'bg-primary/5 border-primary/20' 
            : 'bg-warning/5 border-warning/20'
        )}>
          <div className={cn(
            'status-dot',
            bot.running ? 'bg-primary status-dot-pulse' : 'bg-warning'
          )} />
          <span className="text-sm text-foreground">
            {bot.running ? 'Running' : 'Stopped'}
          </span>
          <span className="text-xs text-muted-foreground">
            ({bot.activeMarkets} mkts)
          </span>
        </div>
        <Button
          variant="ghost"
          size="icon"
          onClick={toggleBot}
          className={cn(
            'w-8 h-8',
            bot.running 
              ? 'text-primary hover:text-primary hover:bg-primary/10' 
              : 'text-warning hover:text-warning hover:bg-warning/10'
          )}
        >
          {bot.running ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
        </Button>
      </div>

      {/* Connection & Time */}
      <div className="flex items-center gap-4">
        <Badge 
          variant={connection.sseConnected ? 'default' : 'destructive'}
          className={cn(
            'gap-1.5 font-normal',
            connection.sseConnected 
              ? 'bg-primary/10 text-primary hover:bg-primary/20' 
              : 'bg-destructive/10 text-destructive hover:bg-destructive/20'
          )}
        >
          {connection.sseConnected ? (
            <Wifi className="w-3 h-3" />
          ) : (
            <WifiOff className="w-3 h-3" />
          )}
          {connection.sseConnected ? 'Online' : 'Offline'}
        </Badge>
        
        <div className="text-right">
          <p className="text-sm font-mono-numbers text-foreground">
            {format(new Date(), 'MMM d, yyyy')}
          </p>
          <p className="text-xs text-muted-foreground font-mono-numbers">
            {format(new Date(), 'HH:mm:ss')}
          </p>
        </div>
      </div>
    </header>
  );
}
