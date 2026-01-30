import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { AlertTriangle, Wallet, Beaker, Activity, Shield, XCircle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { apiClient } from '@/api/client';
import { toast } from 'sonner';

interface LiveTradingStatusProps {
  isLive: boolean;
  balance: number;
  openPositions: number;
  dailyPnl: number;
  killSwitchActive: boolean;
  onToggleMode: () => void;
  onEmergencyStop: () => void;
}

export function LiveTradingStatus({
  isLive,
  balance,
  openPositions,
  dailyPnl,
  killSwitchActive,
  onToggleMode,
  onEmergencyStop,
}: LiveTradingStatusProps) {
  const [showEmergencyConfirm, setShowEmergencyConfirm] = useState(false);
  const [showLiveConfirm, setShowLiveConfirm] = useState(false);
  const [confirmedLiveTrading, setConfirmedLiveTrading] = useState(false);

  const handleEmergencyStop = async () => {
    try {
      await apiClient.emergencyStop();
      toast.error('🛑 EMERGENCY STOP ACTIVATED', {
        description: 'All trading halted. Positions may have been closed.',
      });
      onEmergencyStop();
    } catch (error) {
      toast.error('Failed to activate emergency stop');
    }
    setShowEmergencyConfirm(false);
  };

  const handleLiveModeToggle = () => {
    if (!isLive) {
      // Switching to live - show confirmation
      setShowLiveConfirm(true);
    } else {
      // Switching to paper - just do it
      onToggleMode();
    }
  };

  const confirmLiveTrading = () => {
    if (confirmedLiveTrading) {
      onToggleMode();
      setShowLiveConfirm(false);
      setConfirmedLiveTrading(false);
      toast.success('Switched to LIVE TRADING', {
        description: 'You are now trading with real money.',
      });
    }
  };

  return (
    <>
      <Card className={cn(
        "border-2",
        isLive 
          ? "border-red-500/50 bg-red-500/5" 
          : "border-yellow-500/50 bg-yellow-500/5"
      )}>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2 text-lg">
              {isLive ? (
                <>
                  <AlertTriangle className="w-5 h-5 text-red-500" />
                  <span className="text-red-500">LIVE TRADING</span>
                </>
              ) : (
                <>
                  <Beaker className="w-5 h-5 text-yellow-500" />
                  <span className="text-yellow-500">Paper Trading</span>
                </>
              )}
            </CardTitle>
            <Badge 
              variant={killSwitchActive ? "destructive" : "outline"}
              className={killSwitchActive ? "animate-pulse" : ""}
            >
              {killSwitchActive ? "🛑 KILL SWITCH ACTIVE" : "✅ Systems Normal"}
            </Badge>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-3 gap-4 mb-4">
            <div>
              <div className="text-sm text-muted-foreground">Balance</div>
              <div className="text-2xl font-bold">
                ${balance.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </div>
            </div>
            <div>
              <div className="text-sm text-muted-foreground">Open Positions</div>
              <div className="text-2xl font-bold">{openPositions}</div>
            </div>
            <div>
              <div className="text-sm text-muted-foreground">Today's P&L</div>
              <div className={cn(
                "text-2xl font-bold",
                dailyPnl >= 0 ? "text-green-500" : "text-red-500"
              )}>
                {dailyPnl >= 0 ? "+" : ""}
                ${dailyPnl.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </div>
            </div>
          </div>

          <div className="flex gap-2">
            <Button
              variant={isLive ? "outline" : "default"}
              onClick={handleLiveModeToggle}
              className={cn(
                "flex-1",
                !isLive && "bg-green-600 hover:bg-green-700"
              )}
            >
              {isLive ? (
                <>
                  <Beaker className="w-4 h-4 mr-2" />
                  Switch to Paper Trading
                </>
              ) : (
                <>
                  <Wallet className="w-4 h-4 mr-2" />
                  Switch to Live Trading
                </>
              )}
            </Button>

            <Button
              variant="destructive"
              onClick={() => setShowEmergencyConfirm(true)}
              disabled={killSwitchActive}
              className="flex-1"
            >
              <Shield className="w-4 h-4 mr-2" />
              Emergency Stop
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Emergency Stop Confirmation Dialog */}
      {showEmergencyConfirm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <Card className="w-full max-w-md mx-4 border-red-500">
            <CardHeader>
              <CardTitle className="text-red-500 flex items-center gap-2">
                <AlertTriangle className="w-6 h-6" />
                EMERGENCY STOP
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-red-400 font-semibold">
                ⚠️ This will immediately halt all trading activity!
              </p>
              <ul className="list-disc pl-5 space-y-2 text-sm">
                <li>All open positions will be closed at market price</li>
                <li>No new trades will be entered</li>
                <li>Bot will be stopped immediately</li>
                <li>This action cannot be undone</li>
              </ul>
              <div className="flex gap-2 pt-4">
                <Button
                  variant="outline"
                  onClick={() => setShowEmergencyConfirm(false)}
                  className="flex-1"
                >
                  Cancel
                </Button>
                <Button
                  variant="destructive"
                  onClick={handleEmergencyStop}
                  className="flex-1"
                >
                  <XCircle className="w-4 h-4 mr-2" />
                  STOP TRADING
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Live Trading Confirmation Dialog */}
      {showLiveConfirm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <Card className="w-full max-w-md mx-4 border-red-500">
            <CardHeader>
              <CardTitle className="text-red-500 flex items-center gap-2">
                <AlertTriangle className="w-6 h-6" />
                Switch to LIVE Trading?
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-red-400 font-semibold">
                ⚠️ WARNING: You are about to trade with REAL MONEY
              </p>
              <ul className="list-disc pl-5 space-y-2 text-sm">
                <li>Orders will be placed on Kalshi with actual funds</li>
                <li>Losses are real and non-recoverable</li>
                <li>Ensure you have configured stop losses</li>
                <li>Verify your API credentials are correct</li>
                <li>Start with small position sizes to test</li>
              </ul>
              <div className="flex items-center gap-2 pt-2">
                <input
                  type="checkbox"
                  id="confirm-live"
                  checked={confirmedLiveTrading}
                  onChange={(e) => setConfirmedLiveTrading(e.target.checked)}
                  className="w-4 h-4"
                />
                <label htmlFor="confirm-live" className="text-sm">
                  I understand and accept the risks of live trading
                </label>
              </div>
              <div className="flex gap-2 pt-4">
                <Button
                  variant="outline"
                  onClick={() => {
                    setShowLiveConfirm(false);
                    setConfirmedLiveTrading(false);
                  }}
                  className="flex-1"
                >
                  Cancel
                </Button>
                <Button
                  variant="destructive"
                  onClick={confirmLiveTrading}
                  disabled={!confirmedLiveTrading}
                  className="flex-1"
                >
                  <Wallet className="w-4 h-4 mr-2" />
                  Switch to Live
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </>
  );
}
