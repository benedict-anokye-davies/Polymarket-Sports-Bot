import { useState, useEffect } from 'react';
import { Settings2, Loader2, X, RotateCcw } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Separator } from '@/components/ui/separator';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { apiClient, MarketConfig, MarketConfigUpdate, Market } from '@/api/client';
import { useToast } from '@/components/ui/use-toast';

interface MarketConfigDialogProps {
  market: Market;
  onSave?: () => void;
}

/**
 * Dialog component for configuring per-market trading parameters.
 * Allows users to override sport-level defaults for specific markets.
 */
export function MarketConfigDialog({ market, onSave }: MarketConfigDialogProps) {
  const { toast } = useToast();
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [config, setConfig] = useState<MarketConfig | null>(null);
  const [hasCustomConfig, setHasCustomConfig] = useState(false);
  
  // Form state
  const [formData, setFormData] = useState<MarketConfigUpdate>({
    entry_threshold_drop: null,
    entry_threshold_absolute: null,
    min_time_remaining_seconds: null,
    take_profit_pct: null,
    stop_loss_pct: null,
    position_size_usdc: null,
    max_positions: null,
    enabled: true,
    auto_trade: true,
  });

  // Load existing config when dialog opens
  useEffect(() => {
    if (open) {
      loadConfig();
    }
  }, [open, market.condition_id]);

  const loadConfig = async () => {
    setLoading(true);
    try {
      const existingConfig = await apiClient.getMarketConfigByCondition(market.condition_id);
      if (existingConfig) {
        setConfig(existingConfig);
        setHasCustomConfig(true);
        setFormData({
          entry_threshold_drop: existingConfig.entry_threshold_drop,
          entry_threshold_absolute: existingConfig.entry_threshold_absolute,
          min_time_remaining_seconds: existingConfig.min_time_remaining_seconds,
          take_profit_pct: existingConfig.take_profit_pct,
          stop_loss_pct: existingConfig.stop_loss_pct,
          position_size_usdc: existingConfig.position_size_usdc,
          max_positions: existingConfig.max_positions,
          enabled: existingConfig.enabled,
          auto_trade: existingConfig.auto_trade,
        });
      } else {
        setConfig(null);
        setHasCustomConfig(false);
        // Reset to defaults (null = use sport config)
        setFormData({
          entry_threshold_drop: null,
          entry_threshold_absolute: null,
          min_time_remaining_seconds: null,
          take_profit_pct: null,
          stop_loss_pct: null,
          position_size_usdc: null,
          max_positions: null,
          enabled: true,
          auto_trade: true,
        });
      }
    } catch (err) {
      toast({
        title: 'Error',
        description: 'Failed to load market configuration.',
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await apiClient.upsertMarketConfig(market.condition_id, formData);
      setHasCustomConfig(true);
      toast({
        title: 'Configuration saved',
        description: 'Market trading parameters updated successfully.',
      });
      onSave?.();
      setOpen(false);
    } catch (err) {
      toast({
        title: 'Error',
        description: err instanceof Error ? err.message : 'Failed to save market configuration.',
        variant: 'destructive',
      });
    } finally {
      setSaving(false);
    }
  };

  const handleReset = async () => {
    if (!hasCustomConfig) return;

    setSaving(true);
    try {
      await apiClient.deleteMarketConfigByCondition(market.condition_id);
      setHasCustomConfig(false);
      setConfig(null);
      setFormData({
        entry_threshold_drop: null,
        entry_threshold_absolute: null,
        min_time_remaining_seconds: null,
        take_profit_pct: null,
        stop_loss_pct: null,
        position_size_usdc: null,
        max_positions: null,
        enabled: true,
        auto_trade: true,
      });
      toast({
        title: 'Configuration reset',
        description: 'Market will now use sport-level defaults.',
      });
      onSave?.();
    } catch (err) {
      toast({
        title: 'Error',
        description: err instanceof Error ? err.message : 'Failed to reset market configuration.',
        variant: 'destructive',
      });
    } finally {
      setSaving(false);
    }
  };

  // Helper to convert percentage input (15) to decimal (0.15)
  const pctToDecimal = (value: string): number | null => {
    if (!value || value === '') return null;
    const num = parseFloat(value);
    return isNaN(num) ? null : num / 100;
  };

  // Helper to convert decimal (0.15) to percentage display (15)
  const decimalToPct = (value: number | null): string => {
    if (value === null || value === undefined) return '';
    return (value * 100).toString();
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className={cn(
            'h-8 w-8',
            hasCustomConfig ? 'text-primary' : 'text-muted-foreground hover:text-foreground'
          )}
          title="Configure market settings"
        >
          <Settings2 className="w-4 h-4" />
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Settings2 className="w-5 h-5" />
            Market Configuration
          </DialogTitle>
          <DialogDescription>
            {market.away_team && market.home_team 
              ? `${market.away_team} @ ${market.home_team}`
              : market.question}
          </DialogDescription>
        </DialogHeader>

        {loading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
          </div>
        ) : (
          <div className="space-y-6 py-4">
            {/* Status Badge */}
            {hasCustomConfig && (
              <Badge variant="outline" className="border-primary text-primary">
                Custom Configuration Active
              </Badge>
            )}

            {/* Control Toggles */}
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <Label htmlFor="enabled">Trading Enabled</Label>
                  <p className="text-xs text-muted-foreground">Allow bot to trade this market</p>
                </div>
                <Switch
                  id="enabled"
                  checked={formData.enabled}
                  onCheckedChange={(checked) => setFormData(prev => ({ ...prev, enabled: checked }))}
                />
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <Label htmlFor="auto_trade">Auto Trading</Label>
                  <p className="text-xs text-muted-foreground">Execute trades automatically</p>
                </div>
                <Switch
                  id="auto_trade"
                  checked={formData.auto_trade}
                  onCheckedChange={(checked) => setFormData(prev => ({ ...prev, auto_trade: checked }))}
                />
              </div>
            </div>

            <Separator />

            {/* Entry Conditions */}
            <div className="space-y-4">
              <h4 className="text-sm font-medium">Entry Conditions</h4>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="entry_drop">Price Drop %</Label>
                  <Input
                    id="entry_drop"
                    type="number"
                    step="1"
                    min="0"
                    max="100"
                    placeholder="Default"
                    value={decimalToPct(formData.entry_threshold_drop ?? null)}
                    onChange={(e) => setFormData(prev => ({ 
                      ...prev, 
                      entry_threshold_drop: pctToDecimal(e.target.value)
                    }))}
                    className="bg-muted"
                  />
                  <p className="text-xs text-muted-foreground">Enter when price drops this %</p>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="entry_absolute">Absolute Entry %</Label>
                  <Input
                    id="entry_absolute"
                    type="number"
                    step="1"
                    min="0"
                    max="100"
                    placeholder="Default"
                    value={decimalToPct(formData.entry_threshold_absolute ?? null)}
                    onChange={(e) => setFormData(prev => ({ 
                      ...prev, 
                      entry_threshold_absolute: pctToDecimal(e.target.value)
                    }))}
                    className="bg-muted"
                  />
                  <p className="text-xs text-muted-foreground">Enter if price below this</p>
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="min_time">Min Time Remaining (seconds)</Label>
                <Input
                  id="min_time"
                  type="number"
                  step="60"
                  min="0"
                  placeholder="Default"
                  value={formData.min_time_remaining_seconds ?? ''}
                  onChange={(e) => setFormData(prev => ({ 
                    ...prev, 
                    min_time_remaining_seconds: e.target.value ? parseInt(e.target.value) : null
                  }))}
                  className="bg-muted"
                />
              </div>
            </div>

            <Separator />

            {/* Exit Conditions */}
            <div className="space-y-4">
              <h4 className="text-sm font-medium">Exit Conditions</h4>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="take_profit">Take Profit %</Label>
                  <Input
                    id="take_profit"
                    type="number"
                    step="1"
                    min="0"
                    max="100"
                    placeholder="Default"
                    value={decimalToPct(formData.take_profit_pct ?? null)}
                    onChange={(e) => setFormData(prev => ({ 
                      ...prev, 
                      take_profit_pct: pctToDecimal(e.target.value)
                    }))}
                    className="bg-muted"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="stop_loss">Stop Loss %</Label>
                  <Input
                    id="stop_loss"
                    type="number"
                    step="1"
                    min="0"
                    max="100"
                    placeholder="Default"
                    value={decimalToPct(formData.stop_loss_pct ?? null)}
                    onChange={(e) => setFormData(prev => ({ 
                      ...prev, 
                      stop_loss_pct: pctToDecimal(e.target.value)
                    }))}
                    className="bg-muted"
                  />
                </div>
              </div>
            </div>

            <Separator />

            {/* Position Sizing */}
            <div className="space-y-4">
              <h4 className="text-sm font-medium">Position Sizing</h4>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="position_size">Position Size (USDC)</Label>
                  <Input
                    id="position_size"
                    type="number"
                    step="5"
                    min="0"
                    placeholder="Default"
                    value={formData.position_size_usdc ?? ''}
                    onChange={(e) => setFormData(prev => ({ 
                      ...prev, 
                      position_size_usdc: e.target.value ? parseFloat(e.target.value) : null
                    }))}
                    className="bg-muted"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="max_positions">Max Positions</Label>
                  <Input
                    id="max_positions"
                    type="number"
                    step="1"
                    min="0"
                    placeholder="Default"
                    value={formData.max_positions ?? ''}
                    onChange={(e) => setFormData(prev => ({ 
                      ...prev, 
                      max_positions: e.target.value ? parseInt(e.target.value) : null
                    }))}
                    className="bg-muted"
                  />
                </div>
              </div>
            </div>
          </div>
        )}

        <DialogFooter className="flex gap-2 sm:gap-0">
          {hasCustomConfig && (
            <Button
              variant="outline"
              onClick={handleReset}
              disabled={saving}
              className="mr-auto"
            >
              <RotateCcw className="w-4 h-4 mr-2" />
              Reset to Defaults
            </Button>
          )}
          <Button variant="outline" onClick={() => setOpen(false)}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={saving}>
            {saving ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Saving...
              </>
            ) : (
              'Save Configuration'
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
