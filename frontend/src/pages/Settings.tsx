import { useState, useEffect } from 'react';
import { Eye, EyeOff, Bell, Shield, Wallet, TestTube2, Save, Loader2 } from 'lucide-react';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Separator } from '@/components/ui/separator';
import { useToast } from '@/components/ui/use-toast';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
import { apiClient } from '@/api/client';

// Backend sport config interface matching API response
interface SportConfig {
  id: string;
  sport: string;
  enabled: boolean;
  entry_threshold_drop: number;
  entry_threshold_absolute: number;
  take_profit_pct: number;
  stop_loss_pct: number;
  position_size_usdc: number;
  max_positions_per_game: number;
  max_total_positions: number;
  min_time_remaining_seconds: number;
  updated_at: string;
}

// Backend global settings interface
interface GlobalSettings {
  id: string;
  bot_enabled: boolean;
  max_daily_loss_usdc: number;
  max_portfolio_exposure_usdc: number;
  discord_webhook_url: string | null;
  discord_alerts_enabled: boolean;
  poll_interval_seconds: number;
  updated_at: string;
}

// Wallet credentials interface
interface WalletCredentials {
  api_key: string;
  api_secret: string;
  api_passphrase: string;
  funder_address: string;
}

const SPORTS = ['nba', 'nfl', 'mlb', 'nhl'] as const;
const SPORT_LABELS: Record<string, string> = {
  nba: 'NBA',
  nfl: 'NFL',
  mlb: 'MLB',
  nhl: 'NHL',
};

export default function Settings() {
  const { toast } = useToast();
  const [loading, setLoading] = useState(true);
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
  
  // Sport configs
  const [sportConfigs, setSportConfigs] = useState<Record<string, SportConfig>>({});
  
  // Global settings
  const [globalSettings, setGlobalSettings] = useState<GlobalSettings | null>(null);

  // Load settings on mount
  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      setLoading(true);
      
      // Load sport configs
      const configs = await apiClient.getSportConfigs();
      const configMap: Record<string, SportConfig> = {};
      configs.forEach((config: SportConfig) => {
        configMap[config.sport] = config;
      });
      setSportConfigs(configMap);
      
      // Load global settings
      const global = await apiClient.getGlobalSettings();
      setGlobalSettings(global);
      
      // Check wallet connection status
      const user = await apiClient.getCurrentUser();
      setWalletConnected(user.onboarding_completed);
      
    } catch (error) {
      console.error('Failed to load settings:', error);
      toast({
        title: 'Error',
        description: 'Failed to load settings. Please refresh the page.',
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  };

  const updateSportConfig = (sport: string, field: keyof SportConfig, value: number | boolean) => {
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
      
      // Save each sport config that has changes
      for (const sport of SPORTS) {
        const config = sportConfigs[sport];
        if (config) {
          await apiClient.updateSportConfig(sport, {
            enabled: config.enabled,
            entry_threshold_drop: config.entry_threshold_drop,
            entry_threshold_absolute: config.entry_threshold_absolute,
            take_profit_pct: config.take_profit_pct,
            stop_loss_pct: config.stop_loss_pct,
            position_size_usdc: config.position_size_usdc,
            max_positions_per_game: config.max_positions_per_game,
            max_total_positions: config.max_total_positions,
            min_time_remaining_seconds: config.min_time_remaining_seconds,
          });
        }
      }
      
      // Save global settings
      if (globalSettings) {
        await apiClient.updateGlobalSettings({
          bot_enabled: globalSettings.bot_enabled,
          max_daily_loss_usdc: globalSettings.max_daily_loss_usdc,
          max_portfolio_exposure_usdc: globalSettings.max_portfolio_exposure_usdc,
          discord_webhook_url: globalSettings.discord_webhook_url,
          discord_alerts_enabled: globalSettings.discord_alerts_enabled,
        });
      }
      
      toast({
        title: 'Success',
        description: 'Settings saved successfully.',
      });
      
    } catch (error) {
      console.error('Failed to save settings:', error);
      toast({
        title: 'Error',
        description: 'Failed to save settings. Please try again.',
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
      console.error('Connection test failed:', error);
      toast({
        title: 'Error',
        description: 'Connection test failed. Please check your credentials.',
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
      console.error('Webhook test failed:', error);
      toast({
        title: 'Error',
        description: 'Webhook test failed. Please check the URL.',
        variant: 'destructive',
      });
    } finally {
      setTestingWebhook(false);
    }
  };

  if (loading) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center h-64">
          <Loader2 className="w-8 h-8 animate-spin text-primary" />
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
                placeholder="Your Polymarket API Key"
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
                    <AccordionContent className="pt-4 px-4">
                      <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                          <Label className="text-muted-foreground text-xs">Entry Threshold Drop (%)</Label>
                          <Input 
                            type="number" 
                            step="0.01"
                            min="0"
                            max="1"
                            placeholder="e.g. 0.15" 
                            className="bg-muted border-border"
                            value={config.entry_threshold_drop}
                            onChange={(e) => updateSportConfig(sport, 'entry_threshold_drop', parseFloat(e.target.value) || 0)}
                          />
                          <p className="text-xs text-muted-foreground">15% drop = 0.15</p>
                        </div>
                        <div className="space-y-2">
                          <Label className="text-muted-foreground text-xs">Absolute Entry Price</Label>
                          <Input 
                            type="number" 
                            step="0.01"
                            min="0"
                            max="1"
                            placeholder="e.g. 0.50" 
                            className="bg-muted border-border"
                            value={config.entry_threshold_absolute}
                            onChange={(e) => updateSportConfig(sport, 'entry_threshold_absolute', parseFloat(e.target.value) || 0)}
                          />
                          <p className="text-xs text-muted-foreground">Enter when price below this</p>
                        </div>
                        <div className="space-y-2">
                          <Label className="text-muted-foreground text-xs">Take Profit (%)</Label>
                          <Input 
                            type="number" 
                            step="0.01"
                            min="0"
                            max="1"
                            placeholder="e.g. 0.20" 
                            className="bg-muted border-border"
                            value={config.take_profit_pct}
                            onChange={(e) => updateSportConfig(sport, 'take_profit_pct', parseFloat(e.target.value) || 0)}
                          />
                          <p className="text-xs text-muted-foreground">20% profit = 0.20</p>
                        </div>
                        <div className="space-y-2">
                          <Label className="text-muted-foreground text-xs">Stop Loss (%)</Label>
                          <Input 
                            type="number" 
                            step="0.01"
                            min="0"
                            max="1"
                            placeholder="e.g. 0.10" 
                            className="bg-muted border-border"
                            value={config.stop_loss_pct}
                            onChange={(e) => updateSportConfig(sport, 'stop_loss_pct', parseFloat(e.target.value) || 0)}
                          />
                          <p className="text-xs text-muted-foreground">10% loss = 0.10</p>
                        </div>
                        <div className="space-y-2">
                          <Label className="text-muted-foreground text-xs">Position Size (USDC)</Label>
                          <Input 
                            type="number" 
                            min="1"
                            placeholder="e.g. 50" 
                            className="bg-muted border-border"
                            value={config.position_size_usdc}
                            onChange={(e) => updateSportConfig(sport, 'position_size_usdc', parseFloat(e.target.value) || 50)}
                          />
                        </div>
                        <div className="space-y-2">
                          <Label className="text-muted-foreground text-xs">Min Time Remaining (sec)</Label>
                          <Input 
                            type="number" 
                            min="0"
                            placeholder="e.g. 300" 
                            className="bg-muted border-border"
                            value={config.min_time_remaining_seconds}
                            onChange={(e) => updateSportConfig(sport, 'min_time_remaining_seconds', parseInt(e.target.value) || 0)}
                          />
                          <p className="text-xs text-muted-foreground">300 = 5 minutes</p>
                        </div>
                        <div className="space-y-2">
                          <Label className="text-muted-foreground text-xs">Max Positions Per Game</Label>
                          <Input 
                            type="number" 
                            min="1"
                            max="10"
                            placeholder="e.g. 1" 
                            className="bg-muted border-border"
                            value={config.max_positions_per_game}
                            onChange={(e) => updateSportConfig(sport, 'max_positions_per_game', parseInt(e.target.value) || 1)}
                          />
                        </div>
                        <div className="space-y-2">
                          <Label className="text-muted-foreground text-xs">Max Total Positions</Label>
                          <Input 
                            type="number" 
                            min="1"
                            max="50"
                            placeholder="e.g. 5" 
                            className="bg-muted border-border"
                            value={config.max_total_positions}
                            onChange={(e) => updateSportConfig(sport, 'max_total_positions', parseInt(e.target.value) || 5)}
                          />
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
