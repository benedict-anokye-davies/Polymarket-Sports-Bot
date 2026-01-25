import { useState, useEffect } from 'react';
import { Eye, EyeOff, Bell, Shield, Wallet, TestTube2, Save, Loader2 } from 'lucide-react';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Separator } from '@/components/ui/separator';
import { Skeleton } from '@/components/ui/skeleton';
import { useToast } from '@/components/ui/use-toast';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
import { apiClient, SportConfigResponse } from '@/api/client';
import { useSportConfigs, useGlobalSettings, useUpdateSportConfig, useUpdateGlobalSettings } from '@/hooks/useApi';

// Wallet credentials interface
interface WalletCredentials {
  api_key: string;
  api_secret: string;
  api_passphrase: string;
  funder_address: string;
}

const SPORTS = ['nba', 'nfl', 'mlb', 'nhl', 'soccer', 'mma', 'tennis', 'golf', 'ncaab', 'ncaaf'] as const;
const SPORT_LABELS: Record<string, string> = {
  nba: 'NBA',
  nfl: 'NFL',
  mlb: 'MLB',
  nhl: 'NHL',
  soccer: 'Soccer',
  mma: 'MMA/UFC',
  tennis: 'Tennis',
  golf: 'Golf',
  ncaab: 'NCAA BB',
  ncaaf: 'NCAA FB',
};

export default function Settings() {
  const { toast } = useToast();
  const [saving, setSaving] = useState(false);
  const [testingConnection, setTestingConnection] = useState(false);
  const [testingWebhook, setTestingWebhook] = useState(false);
  const [showPrivateKey, setShowPrivateKey] = useState(false);

  // Wallet credentials
  const [wallet, setWallet] = useState<WalletCredentials>({
    api_key: '',
    api_secret: '',
    api_passphrase: '',
    funder_address: '',
  });
  const [walletConnected, setWalletConnected] = useState(false);

  // React Query hooks
  const { data: sportConfigsData, isLoading: loadingSports } = useSportConfigs();
  const { data: globalSettingsData, isLoading: loadingGlobal } = useGlobalSettings();
  const updateSportConfigMutation = useUpdateSportConfig();
  const updateGlobalSettingsMutation = useUpdateGlobalSettings();

  // Local editable copies of server data
  const [sportConfigs, setSportConfigs] = useState<Record<string, SportConfigResponse>>({});
  const [globalSettings, setGlobalSettings] = useState<typeof globalSettingsData | null>(null);

  // Sync fetched data into local state for editing
  useEffect(() => {
    if (sportConfigsData) {
      const configMap: Record<string, SportConfigResponse> = {};
      sportConfigsData.forEach((config) => {
        configMap[config.sport] = config;
      });
      setSportConfigs(configMap);
    }
  }, [sportConfigsData]);

  useEffect(() => {
    if (globalSettingsData) {
      setGlobalSettings(globalSettingsData);
    }
  }, [globalSettingsData]);

  const loading = loadingSports || loadingGlobal;

  const updateSportConfig = (sport: string, field: keyof SportConfigResponse, value: number | boolean) => {
    setSportConfigs(prev => ({
      ...prev,
      [sport]: {
        ...prev[sport],
        [field]: value,
      },
    }));
  };

  const handleSave = async () => {
    try {
      setSaving(true);

      // Save each sport config
      const sportPromises = SPORTS
        .filter(sport => sportConfigs[sport])
        .map(sport => {
          const config = sportConfigs[sport];
          return updateSportConfigMutation.mutateAsync({
            sport,
            config: {
              enabled: config.enabled,
              entry_threshold_drop: config.entry_threshold_drop,
              entry_threshold_absolute: config.entry_threshold_absolute,
              take_profit_pct: config.take_profit_pct,
              stop_loss_pct: config.stop_loss_pct,
              position_size_usdc: config.position_size_usdc,
              max_positions_per_game: config.max_positions_per_game,
              max_total_positions: config.max_total_positions,
              min_time_remaining_seconds: config.min_time_remaining_seconds,
              exit_time_remaining_seconds: config.exit_time_remaining_seconds,
              min_volume_threshold: config.min_volume_threshold,
              max_daily_loss_usdc: config.max_daily_loss_usdc,
              max_exposure_usdc: config.max_exposure_usdc,
              priority: config.priority,
            },
          });
        });

      // Save global settings
      const globalPromise = globalSettings
        ? updateGlobalSettingsMutation.mutateAsync({
            bot_enabled: globalSettings.bot_enabled,
            max_daily_loss_usdc: globalSettings.max_daily_loss_usdc,
            max_portfolio_exposure_usdc: globalSettings.max_portfolio_exposure_usdc,
            discord_webhook_url: globalSettings.discord_webhook_url,
            discord_alerts_enabled: globalSettings.discord_alerts_enabled,
          })
        : Promise.resolve();

      await Promise.all([...sportPromises, globalPromise]);

      toast({
        title: 'Success',
        description: 'Settings saved successfully.',
      });

    } catch (error) {
      toast({
        title: 'Error',
        description: error instanceof Error ? error.message : 'Failed to save settings. Please try again.',
        variant: 'destructive',
      });
    } finally {
      setSaving(false);
    }
  };

  const handleTestConnection = async () => {
    if (!wallet.api_key || !wallet.funder_address) {
      toast({
        title: 'Error',
        description: 'Please enter API Key and Wallet Address.',
        variant: 'destructive',
      });
      return;
    }

    try {
      setTestingConnection(true);
      await apiClient.connectWallet(wallet.api_key, wallet.funder_address, 1);
      setWalletConnected(true);
      toast({
        title: 'Success',
        description: 'Wallet connection successful.',
      });
    } catch (error) {
      toast({
        title: 'Error',
        description: error instanceof Error ? error.message : 'Connection test failed. Please check your credentials.',
        variant: 'destructive',
      });
    } finally {
      setTestingConnection(false);
    }
  };

  const handleTestWebhook = async () => {
    if (!globalSettings?.discord_webhook_url) {
      toast({
        title: 'Error',
        description: 'Please enter a Discord webhook URL.',
        variant: 'destructive',
      });
      return;
    }

    try {
      setTestingWebhook(true);
      await apiClient.testDiscordWebhook();
      toast({
        title: 'Success',
        description: 'Test message sent to Discord.',
      });
    } catch (error) {
      toast({
        title: 'Error',
        description: error instanceof Error ? error.message : 'Webhook test failed. Please check the URL.',
        variant: 'destructive',
      });
    } finally {
      setTestingWebhook(false);
    }
  };

  if (loading) {
    return (
      <DashboardLayout>
        <div className="space-y-6 max-w-4xl">
          <div className="flex items-center justify-between">
            <div>
              <Skeleton className="h-7 w-32" />
              <Skeleton className="h-4 w-56 mt-2" />
            </div>
            <Skeleton className="h-10 w-32" />
          </div>
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="bg-card border border-border rounded-lg p-6 space-y-4">
              <Skeleton className="h-5 w-40" />
              <div className="grid grid-cols-2 gap-4">
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
              </div>
            </div>
          ))}
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="space-y-6 max-w-4xl">
        {/* Page Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-foreground">Settings</h1>
            <p className="text-sm text-muted-foreground mt-1">
              Configure your bot and trading parameters
            </p>
          </div>
          <Button
            onClick={handleSave}
            disabled={saving}
            className="bg-primary hover:bg-primary/90"
          >
            {saving ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <Save className="w-4 h-4 mr-2" />
            )}
            Save Changes
          </Button>
        </div>

        {/* Wallet Configuration */}
        <Card className="bg-card border-border">
          <CardHeader>
            <CardTitle className="text-base font-medium text-foreground flex items-center gap-2">
              <Wallet className="w-5 h-5 text-primary" />
              API Configuration
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="apiKey" className="text-muted-foreground">API Key</Label>
              <Input
                id="apiKey"
                type="text"
                placeholder="Your Kalshi API Key"
                className="bg-muted border-border font-mono"
                value={wallet.api_key}
                onChange={(e) => setWallet(prev => ({ ...prev, api_key: e.target.value }))}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="apiSecret" className="text-muted-foreground">API Secret</Label>
              <div className="relative">
                <Input
                  id="apiSecret"
                  type={showPrivateKey ? 'text' : 'password'}
                  placeholder="Your API Secret"
                  className="bg-muted border-border pr-10 font-mono"
                  value={wallet.api_secret}
                  onChange={(e) => setWallet(prev => ({ ...prev, api_secret: e.target.value }))}
                />
                <Button
                  variant="ghost"
                  size="icon"
                  type="button"
                  className="absolute right-1 top-1/2 -translate-y-1/2 h-7 w-7"
                  onClick={() => setShowPrivateKey(!showPrivateKey)}
                >
                  {showPrivateKey ? (
                    <EyeOff className="w-4 h-4 text-muted-foreground" />
                  ) : (
                    <Eye className="w-4 h-4 text-muted-foreground" />
                  )}
                </Button>
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="apiPassphrase" className="text-muted-foreground">API Passphrase</Label>
              <Input
                id="apiPassphrase"
                type="password"
                placeholder="Your API Passphrase"
                className="bg-muted border-border font-mono"
                value={wallet.api_passphrase}
                onChange={(e) => setWallet(prev => ({ ...prev, api_passphrase: e.target.value }))}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="walletAddress" className="text-muted-foreground">Wallet Address</Label>
              <Input
                id="walletAddress"
                placeholder="0x..."
                className="bg-muted border-border font-mono"
                value={wallet.funder_address}
                onChange={(e) => setWallet(prev => ({ ...prev, funder_address: e.target.value }))}
              />
              <p className="text-xs text-muted-foreground">Your Polygon wallet holding USDC</p>
            </div>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <div className={`w-2 h-2 rounded-full ${walletConnected ? 'bg-primary' : 'bg-muted-foreground'}`} />
                <span className={`text-sm ${walletConnected ? 'text-primary' : 'text-muted-foreground'}`}>
                  {walletConnected ? 'Connected' : 'Not Connected'}
                </span>
              </div>
              <Button
                variant="outline"
                className="border-border hover:bg-muted gap-2"
                onClick={handleTestConnection}
                disabled={testingConnection}
              >
                {testingConnection ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <TestTube2 className="w-4 h-4" />
                )}
                Test Connection
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Trading Parameters */}
        <Card className="bg-card border-border">
          <CardHeader>
            <CardTitle className="text-base font-medium text-foreground">Trading Parameters</CardTitle>
          </CardHeader>
          <CardContent>
            <Accordion type="multiple" className="space-y-2">
              {SPORTS.map((sport) => {
                const config = sportConfigs[sport];
                if (!config) return null;

                return (
                  <AccordionItem key={sport} value={sport} className="border-border">
                    <AccordionTrigger className="hover:no-underline px-4 py-3 bg-muted/30 rounded-md">
                      <div className="flex items-center justify-between w-full pr-4">
                        <span className="font-medium">{SPORT_LABELS[sport]}</span>
                        <Switch
                          checked={config.enabled}
                          onCheckedChange={(checked) => {
                            updateSportConfig(sport, 'enabled', checked);
                          }}
                          onClick={(e) => e.stopPropagation()}
                        />
                      </div>
                    </AccordionTrigger>
                    <AccordionContent className="pt-4 px-4 space-y-4">
                      {/* Entry Conditions */}
                      <div>
                        <p className="text-xs font-medium text-muted-foreground mb-2">Entry Conditions</p>
                        <div className="grid grid-cols-2 gap-3">
                          <div className="space-y-1">
                            <Label className="text-muted-foreground text-xs">Price Drop (%)</Label>
                            <Input
                              type="number"
                              step="1"
                              min="0"
                              max="100"
                              placeholder="15"
                              className="bg-muted border-border h-8"
                              value={config.entry_threshold_drop ? Math.round(config.entry_threshold_drop * 100) : ''}
                              onChange={(e) => updateSportConfig(sport, 'entry_threshold_drop', (parseFloat(e.target.value) || 0) / 100)}
                            />
                          </div>
                          <div className="space-y-1">
                            <Label className="text-muted-foreground text-xs">Absolute Entry</Label>
                            <Input
                              type="number"
                              step="0.01"
                              min="0"
                              max="1"
                              placeholder="0.35"
                              className="bg-muted border-border h-8"
                              value={config.entry_threshold_absolute || ''}
                              onChange={(e) => updateSportConfig(sport, 'entry_threshold_absolute', parseFloat(e.target.value) || 0)}
                            />
                          </div>
                          <div className="space-y-1">
                            <Label className="text-muted-foreground text-xs">Min Volume ($)</Label>
                            <Input
                              type="number"
                              min="0"
                              placeholder="1000"
                              className="bg-muted border-border h-8"
                              value={config.min_volume_threshold || ''}
                              onChange={(e) => updateSportConfig(sport, 'min_volume_threshold', parseFloat(e.target.value) || 0)}
                            />
                          </div>
                          <div className="space-y-1">
                            <Label className="text-muted-foreground text-xs">Latest Entry (sec)</Label>
                            <Input
                              type="number"
                              min="0"
                              placeholder="300"
                              className="bg-muted border-border h-8"
                              value={config.min_time_remaining_seconds || ''}
                              onChange={(e) => updateSportConfig(sport, 'min_time_remaining_seconds', parseInt(e.target.value) || 0)}
                            />
                          </div>
                        </div>
                      </div>

                      {/* Exit Conditions */}
                      <div>
                        <p className="text-xs font-medium text-muted-foreground mb-2">Exit Conditions</p>
                        <div className="grid grid-cols-3 gap-3">
                          <div className="space-y-1">
                            <Label className="text-muted-foreground text-xs">Take Profit (%)</Label>
                            <Input
                              type="number"
                              step="1"
                              min="0"
                              max="100"
                              placeholder="20"
                              className="bg-muted border-border h-8"
                              value={config.take_profit_pct ? Math.round(config.take_profit_pct * 100) : ''}
                              onChange={(e) => updateSportConfig(sport, 'take_profit_pct', (parseFloat(e.target.value) || 0) / 100)}
                            />
                          </div>
                          <div className="space-y-1">
                            <Label className="text-muted-foreground text-xs">Stop Loss (%)</Label>
                            <Input
                              type="number"
                              step="1"
                              min="0"
                              max="100"
                              placeholder="10"
                              className="bg-muted border-border h-8"
                              value={config.stop_loss_pct ? Math.round(config.stop_loss_pct * 100) : ''}
                              onChange={(e) => updateSportConfig(sport, 'stop_loss_pct', (parseFloat(e.target.value) || 0) / 100)}
                            />
                          </div>
                          <div className="space-y-1">
                            <Label className="text-muted-foreground text-xs">Latest Exit (sec)</Label>
                            <Input
                              type="number"
                              min="0"
                              placeholder="120"
                              className="bg-muted border-border h-8"
                              value={config.exit_time_remaining_seconds || ''}
                              onChange={(e) => updateSportConfig(sport, 'exit_time_remaining_seconds', parseInt(e.target.value) || 0)}
                            />
                          </div>
                        </div>
                      </div>

                      {/* Position Sizing */}
                      <div>
                        <p className="text-xs font-medium text-muted-foreground mb-2">Position & Risk</p>
                        <div className="grid grid-cols-4 gap-3">
                          <div className="space-y-1">
                            <Label className="text-muted-foreground text-xs">Size ($)</Label>
                            <Input
                              type="number"
                              min="1"
                              placeholder="50"
                              className="bg-muted border-border h-8"
                              value={config.position_size_usdc || ''}
                              onChange={(e) => updateSportConfig(sport, 'position_size_usdc', parseFloat(e.target.value) || 50)}
                            />
                          </div>
                          <div className="space-y-1">
                            <Label className="text-muted-foreground text-xs">Max/Game</Label>
                            <Input
                              type="number"
                              min="1"
                              max="10"
                              placeholder="1"
                              className="bg-muted border-border h-8"
                              value={config.max_positions_per_game || ''}
                              onChange={(e) => updateSportConfig(sport, 'max_positions_per_game', parseInt(e.target.value) || 1)}
                            />
                          </div>
                          <div className="space-y-1">
                            <Label className="text-muted-foreground text-xs">Max Total</Label>
                            <Input
                              type="number"
                              min="1"
                              max="50"
                              placeholder="5"
                              className="bg-muted border-border h-8"
                              value={config.max_total_positions || ''}
                              onChange={(e) => updateSportConfig(sport, 'max_total_positions', parseInt(e.target.value) || 5)}
                            />
                          </div>
                          <div className="space-y-1">
                            <Label className="text-muted-foreground text-xs">Priority</Label>
                            <Input
                              type="number"
                              min="1"
                              max="10"
                              placeholder="1"
                              className="bg-muted border-border h-8"
                              value={config.priority || ''}
                              onChange={(e) => updateSportConfig(sport, 'priority', parseInt(e.target.value) || 1)}
                            />
                          </div>
                        </div>
                      </div>
                    </AccordionContent>
                  </AccordionItem>
                );
              })}
            </Accordion>
            {Object.keys(sportConfigs).length === 0 && (
              <p className="text-sm text-muted-foreground text-center py-4">
                No sport configurations found. Complete onboarding to set up your trading parameters.
              </p>
            )}
          </CardContent>
        </Card>

        {/* Risk Management */}
        <Card className="bg-card border-border">
          <CardHeader>
            <CardTitle className="text-base font-medium text-foreground flex items-center gap-2">
              <Shield className="w-5 h-5 text-warning" />
              Risk Management
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label className="text-muted-foreground">Max Daily Loss (USDC)</Label>
                <Input
                  type="number"
                  min="0"
                  placeholder="e.g. 500"
                  className="bg-muted border-border"
                  value={globalSettings?.max_daily_loss_usdc || ''}
                  onChange={(e) => setGlobalSettings(prev => prev ? {
                    ...prev,
                    max_daily_loss_usdc: parseFloat(e.target.value) || 0
                  } : null)}
                />
              </div>
              <div className="space-y-2">
                <Label className="text-muted-foreground">Max Total Exposure (USDC)</Label>
                <Input
                  type="number"
                  min="0"
                  placeholder="e.g. 5000"
                  className="bg-muted border-border"
                  value={globalSettings?.max_portfolio_exposure_usdc || ''}
                  onChange={(e) => setGlobalSettings(prev => prev ? {
                    ...prev,
                    max_portfolio_exposure_usdc: parseFloat(e.target.value) || 0
                  } : null)}
                />
              </div>
            </div>
            <Separator className="bg-border" />
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-foreground">Emergency Stop</p>
                <p className="text-xs text-muted-foreground">Halt all trading immediately</p>
              </div>
              <Switch
                checked={globalSettings?.bot_enabled === false}
                onCheckedChange={(checked) => setGlobalSettings(prev => prev ? {
                  ...prev,
                  bot_enabled: !checked
                } : null)}
              />
            </div>
          </CardContent>
        </Card>

        {/* Notifications */}
        <Card className="bg-card border-border">
          <CardHeader>
            <CardTitle className="text-base font-medium text-foreground flex items-center gap-2">
              <Bell className="w-5 h-5 text-info" />
              Notifications
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label className="text-muted-foreground">Discord Webhook URL</Label>
              <Input
                type="url"
                placeholder="https://discord.com/api/webhooks/..."
                className="bg-muted border-border"
                value={globalSettings?.discord_webhook_url || ''}
                onChange={(e) => setGlobalSettings(prev => prev ? {
                  ...prev,
                  discord_webhook_url: e.target.value || null
                } : null)}
              />
            </div>
            <Button
              variant="outline"
              size="sm"
              className="border-border hover:bg-muted"
              onClick={handleTestWebhook}
              disabled={testingWebhook || !globalSettings?.discord_webhook_url}
            >
              {testingWebhook ? (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <TestTube2 className="w-4 h-4 mr-2" />
              )}
              Test Webhook
            </Button>
            <Separator className="bg-border" />
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-foreground">Discord Alerts</p>
                <p className="text-xs text-muted-foreground">Enable notifications for trades and errors</p>
              </div>
              <Switch
                checked={globalSettings?.discord_alerts_enabled || false}
                onCheckedChange={(checked) => setGlobalSettings(prev => prev ? {
                  ...prev,
                  discord_alerts_enabled: checked
                } : null)}
              />
            </div>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}
