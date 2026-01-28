import { useState, useEffect } from 'react';
import { Eye, EyeOff, Bell, Shield, Wallet, TestTube2, Save, Loader2, ShieldAlert, RefreshCw, Monitor, Smartphone, Trash2, Globe } from 'lucide-react';
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
import { apiClient, SportConfigResponse, WalletStatusResponse, SessionInfo } from '@/api/client';
import { useSportConfigs, useGlobalSettings, useUpdateSportConfig, useUpdateGlobalSettings } from '@/hooks/useApi';
import { LeagueSelector } from '@/components/LeagueSelector';

// Wallet credentials interface
interface WalletCredentials {
  platform: 'kalshi' | 'polymarket';
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

  // Wallet status from server
  const [walletStatus, setWalletStatus] = useState<WalletStatusResponse | null>(null);
  const [loadingWalletStatus, setLoadingWalletStatus] = useState(true);
  const [showCredentialForm, setShowCredentialForm] = useState(false);

  // Wallet credentials for editing
  const [wallet, setWallet] = useState<WalletCredentials>({
    platform: 'kalshi',
    api_key: '',
    api_secret: '',
    api_passphrase: '',
    funder_address: '',
  });
  const [walletConnected, setWalletConnected] = useState(false);

  // Session management state
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  const [loadingSessions, setLoadingSessions] = useState(false);
  const [revokingSession, setRevokingSession] = useState<string | null>(null);

  // Fetch wallet status on mount
  useEffect(() => {
    const fetchWalletStatus = async () => {
      try {
        setLoadingWalletStatus(true);
        const status = await apiClient.getWalletStatus();
        setWalletStatus(status);
        setWalletConnected(status.is_connected);
        if (status.is_connected && status.platform) {
          setWallet(prev => ({ ...prev, platform: status.platform! }));
        }
      } catch (error) {
        console.error('Failed to fetch wallet status:', error);
      } finally {
        setLoadingWalletStatus(false);
      }
    };
    fetchWalletStatus();
  }, []);

  // Fetch active sessions on mount
  useEffect(() => {
    const fetchSessions = async () => {
      try {
        setLoadingSessions(true);
        const activeSessions = await apiClient.getActiveSessions();
        setSessions(activeSessions);
      } catch (error) {
        console.error('Failed to fetch sessions:', error);
      } finally {
        setLoadingSessions(false);
      }
    };
    fetchSessions();
  }, []);

  // Handle session revocation
  const handleRevokeSession = async (sessionId: string) => {
    try {
      setRevokingSession(sessionId);
      await apiClient.revokeSession(sessionId);
      setSessions(prev => prev.filter(s => s.id !== sessionId));
      toast({
        title: 'Session Revoked',
        description: 'The session has been logged out.',
      });
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to revoke session.',
        variant: 'destructive',
      });
    } finally {
      setRevokingSession(null);
    }
  };

  // Handle logout all devices
  const handleLogoutAllDevices = async () => {
    try {
      await apiClient.logoutAllDevices();
      toast({
        title: 'Success',
        description: 'All devices have been logged out. You will be redirected to login.',
      });
      // Clear local auth and redirect
      localStorage.removeItem('auth_token');
      localStorage.removeItem('refresh_token');
      window.location.href = '/login';
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to logout all devices.',
        variant: 'destructive',
      });
    }
  };

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
    const isKalshi = wallet.platform === 'kalshi';

    if (isKalshi && (!wallet.api_key || !wallet.api_secret)) {
      toast({
        title: 'Error',
        description: 'Please enter API Key and API Secret.',
        variant: 'destructive',
      });
      return;
    }

    if (!isKalshi && (!wallet.api_key || !wallet.funder_address)) {
      toast({
        title: 'Error',
        description: 'Please enter Private Key and Wallet Address.',
        variant: 'destructive',
      });
      return;
    }

    try {
      setTestingConnection(true);
      await apiClient.connectWallet(wallet.platform, {
        // Kalshi uses api_key and api_secret (RSA private key)
        apiKey: isKalshi ? wallet.api_key : wallet.api_key,
        apiSecret: isKalshi ? wallet.api_secret : wallet.api_secret,
        // Polymarket uses private_key, funder_address, and passphrase
        privateKey: !isKalshi ? wallet.api_secret : undefined,
        funderAddress: !isKalshi ? wallet.funder_address : undefined,
        passphrase: !isKalshi ? wallet.api_passphrase : undefined,
      });
      setWalletConnected(true);

      // Refresh wallet status to show connected state
      const updatedStatus = await apiClient.getWalletStatus();
      setWalletStatus(updatedStatus);

      // Hide credential form and clear fields
      setShowCredentialForm(false);
      setWallet({
        platform: updatedStatus.platform || 'kalshi',
        api_key: '',
        api_secret: '',
        api_passphrase: '',
        funder_address: '',
      });

      toast({
        title: 'Success',
        description: `${isKalshi ? 'Kalshi' : 'Polymarket'} connection successful.`,
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
              Trading Platform Configuration
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Show Connected State or Credential Form */}
            {loadingWalletStatus ? (
              <div className="space-y-3">
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
              </div>
            ) : walletStatus?.is_connected && !showCredentialForm ? (
              /* Connected State - Show wallet info */
              <div className="p-4 bg-primary/10 border border-primary/30 rounded-lg">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-3 h-3 bg-primary rounded-full animate-pulse" />
                    <div>
                      <p className="font-medium text-foreground">
                        {walletStatus.platform === 'kalshi' ? 'Kalshi' : 'Polymarket'} Connected
                      </p>
                      <p className="text-sm text-muted-foreground font-mono">
                        {walletStatus.masked_identifier || 'Credentials saved'}
                      </p>
                      {walletStatus.last_tested_at && (
                        <p className="text-xs text-muted-foreground mt-1">
                          Last verified: {new Date(walletStatus.last_tested_at).toLocaleDateString()}
                        </p>
                      )}
                    </div>
                  </div>
                  <Button
                    variant="outline"
                    className="border-border hover:bg-muted"
                    onClick={() => setShowCredentialForm(true)}
                  >
                    <RefreshCw className="w-4 h-4 mr-2" />
                    Update Credentials
                  </Button>
                </div>
                {walletStatus.connection_error && (
                  <p className="text-sm text-destructive mt-2">{walletStatus.connection_error}</p>
                )}
              </div>
            ) : (
              /* Credential Form - Show when not connected or updating */
              <>
                {showCredentialForm && walletStatus?.is_connected && (
                  <div className="flex items-center justify-between p-3 bg-muted/30 rounded-lg mb-4">
                    <span className="text-sm text-muted-foreground">
                      Currently connected to {walletStatus.platform === 'kalshi' ? 'Kalshi' : 'Polymarket'}
                    </span>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setShowCredentialForm(false)}
                    >
                      Cancel
                    </Button>
                  </div>
                )}

                {/* Platform Selector */}
                <div className="space-y-2">
                  <Label className="text-muted-foreground">Trading Platform</Label>
                  <div className="grid grid-cols-2 gap-3">
                    <button
                      type="button"
                      onClick={() => setWallet(prev => ({ ...prev, platform: 'kalshi' }))}
                      className={`p-3 rounded-lg border text-left transition-all ${
                        wallet.platform === 'kalshi'
                          ? 'bg-primary/10 border-primary/50'
                          : 'bg-muted/30 border-border hover:border-primary/30'
                      }`}
                    >
                      <span className={`font-medium ${wallet.platform === 'kalshi' ? 'text-primary' : 'text-foreground'}`}>
                        Kalshi
                      </span>
                      <p className="text-xs text-muted-foreground mt-1">US-regulated prediction market</p>
                    </button>
                    <button
                      type="button"
                      onClick={() => setWallet(prev => ({ ...prev, platform: 'polymarket' }))}
                      className={`p-3 rounded-lg border text-left transition-all ${
                        wallet.platform === 'polymarket'
                          ? 'bg-primary/10 border-primary/50'
                          : 'bg-muted/30 border-border hover:border-primary/30'
                      }`}
                    >
                      <span className={`font-medium ${wallet.platform === 'polymarket' ? 'text-primary' : 'text-foreground'}`}>
                        Polymarket
                      </span>
                      <p className="text-xs text-muted-foreground mt-1">Crypto-based prediction market</p>
                    </button>
                  </div>
                </div>

                <Separator />

            {/* Kalshi Credentials */}
            {wallet.platform === 'kalshi' ? (
              <>
                <div className="space-y-2">
                  <Label htmlFor="apiKey" className="text-muted-foreground">Kalshi API Key</Label>
                  <Input
                    id="apiKey"
                    type="text"
                    placeholder="Your Kalshi API Key"
                    className="bg-muted border-border font-mono"
                    value={wallet.api_key}
                    onChange={(e) => setWallet(prev => ({ ...prev, api_key: e.target.value }))}
                  />
                  <p className="text-xs text-muted-foreground">From Kalshi Settings {'>'} API Keys</p>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="apiSecret" className="text-muted-foreground">Kalshi API Secret</Label>
                  <div className="relative">
                    <Input
                      id="apiSecret"
                      type={showPrivateKey ? 'text' : 'password'}
                      placeholder="Your Kalshi API Secret"
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
                  <p className="text-xs text-muted-foreground">Keep this secret! Used for signing requests.</p>
                </div>
              </>
            ) : (
              /* Polymarket Credentials */
              <>
                <div className="space-y-2">
                  <Label htmlFor="privateKey" className="text-muted-foreground">Private Key</Label>
                  <div className="relative">
                    <Input
                      id="privateKey"
                      type={showPrivateKey ? 'text' : 'password'}
                      placeholder="0x..."
                      className="bg-muted border-border pr-10 font-mono"
                      value={wallet.api_key}
                      onChange={(e) => setWallet(prev => ({ ...prev, api_key: e.target.value }))}
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
                  <p className="text-xs text-muted-foreground">Your Polygon wallet private key (64 hex chars)</p>
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
                <div className="space-y-2">
                  <Label htmlFor="apiPassphrase" className="text-muted-foreground">API Passphrase (Optional)</Label>
                  <Input
                    id="apiPassphrase"
                    type="password"
                    placeholder="For L2 authentication"
                    className="bg-muted border-border font-mono"
                    value={wallet.api_passphrase}
                    onChange={(e) => setWallet(prev => ({ ...prev, api_passphrase: e.target.value }))}
                  />
                </div>
              </>
            )}
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
              </>
            )}
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

        {/* League Selection */}
        <Card className="bg-card border-border">
          <CardHeader>
            <CardTitle className="text-base font-medium text-foreground flex items-center gap-2">
              <Globe className="w-5 h-5 text-primary" />
              League Selection
            </CardTitle>
            <p className="text-sm text-muted-foreground">
              Choose which leagues to monitor across all sports. 126 leagues available.
            </p>
          </CardHeader>
          <CardContent>
            <LeagueSelector />
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

        {/* Balance Guardian */}
        <Card className="bg-card border-border">
          <CardHeader>
            <CardTitle className="text-base font-medium text-foreground flex items-center gap-2">
              <ShieldAlert className="w-5 h-5 text-destructive" />
              Balance Guardian
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Automatically stops trading when balance drops below threshold or after consecutive losses.
            </p>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label className="text-muted-foreground">Minimum Balance (USDC)</Label>
                <Input
                  type="number"
                  min="0"
                  placeholder="e.g. 100"
                  className="bg-muted border-border"
                  value={globalSettings?.min_balance_threshold || ''}
                  onChange={(e) => setGlobalSettings(prev => prev ? {
                    ...prev,
                    min_balance_threshold: parseFloat(e.target.value) || 0
                  } : null)}
                />
                <p className="text-xs text-muted-foreground">Kill switch activates if balance goes below this</p>
              </div>
              <div className="space-y-2">
                <Label className="text-muted-foreground">Max Losing Streak</Label>
                <Input
                  type="number"
                  min="1"
                  max="20"
                  placeholder="e.g. 5"
                  className="bg-muted border-border"
                  value={globalSettings?.max_losing_streak || ''}
                  onChange={(e) => setGlobalSettings(prev => prev ? {
                    ...prev,
                    max_losing_streak: parseInt(e.target.value) || 5
                  } : null)}
                />
                <p className="text-xs text-muted-foreground">Reduce position size after this many losses</p>
              </div>
            </div>
            <div className="space-y-2">
              <Label className="text-muted-foreground">Streak Size Reduction (%)</Label>
              <Input
                type="number"
                min="10"
                max="90"
                placeholder="e.g. 50"
                className="bg-muted border-border"
                value={globalSettings?.streak_reduction_pct ? Math.round(globalSettings.streak_reduction_pct * 100) : ''}
                onChange={(e) => setGlobalSettings(prev => prev ? {
                  ...prev,
                  streak_reduction_pct: (parseFloat(e.target.value) || 50) / 100
                } : null)}
              />
              <p className="text-xs text-muted-foreground">Reduce position size by this percentage during losing streak</p>
            </div>
            <Separator className="bg-border" />
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-foreground flex items-center gap-2">
                  Kill Switch Status
                  {globalSettings?.kill_switch_active && (
                    <span className="text-xs bg-destructive/20 text-destructive px-2 py-0.5 rounded">ACTIVE</span>
                  )}
                </p>
                <p className="text-xs text-muted-foreground">
                  {globalSettings?.kill_switch_active 
                    ? `Activated at ${globalSettings.kill_switch_activated_at ? new Date(globalSettings.kill_switch_activated_at).toLocaleString() : 'unknown time'}`
                    : 'Not activated'}
                </p>
              </div>
              {globalSettings?.kill_switch_active && (
                <Button
                  variant="outline"
                  size="sm"
                  className="border-border hover:bg-muted gap-2"
                  onClick={async () => {
                    try {
                      // Use apiClient instead of raw fetch to ensure proper auth
                      await apiClient.updateGlobalSettings({
                        kill_switch_active: false,
                        current_losing_streak: 0,
                      });
                      setGlobalSettings(prev => prev ? {
                        ...prev,
                        kill_switch_active: false,
                        current_losing_streak: 0,
                      } : null);
                      toast({
                        title: 'Kill Switch Reset',
                        description: 'Trading has been re-enabled.',
                      });
                    } catch (err) {
                      toast({
                        title: 'Error',
                        description: 'Failed to reset kill switch.',
                        variant: 'destructive',
                      });
                    }
                  }}
                >
                  <RefreshCw className="w-4 h-4" />
                  Reset Kill Switch
                </Button>
              )}
            </div>
            {globalSettings?.current_losing_streak !== undefined && globalSettings.current_losing_streak > 0 && (
              <div className="p-3 bg-warning/10 border border-warning/30 rounded-lg">
                <p className="text-sm text-warning">
                  Current losing streak: {globalSettings.current_losing_streak} trades
                </p>
              </div>
            )}
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

        {/* Session Management (REQ-SEC-003) */}
        <Card className="bg-card border-border">
          <CardHeader>
            <CardTitle className="text-base font-medium text-foreground flex items-center gap-2">
              <Monitor className="w-5 h-5 text-primary" />
              Active Sessions
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Manage devices where you're currently logged in. Revoke access to any device you don't recognize.
            </p>

            {loadingSessions ? (
              <div className="space-y-3">
                {Array.from({ length: 3 }).map((_, i) => (
                  <Skeleton key={i} className="h-16 w-full" />
                ))}
              </div>
            ) : sessions.length === 0 ? (
              <div className="text-center py-6 text-muted-foreground">
                <Monitor className="w-8 h-8 mx-auto mb-2 opacity-50" />
                <p className="text-sm">No active sessions found</p>
              </div>
            ) : (
              <div className="space-y-3">
                {sessions.map((session) => {
                  const isCurrentSession = session.id === 'current'; // You might want to mark the current session
                  const isMobile = session.device_info?.toLowerCase().includes('mobile') ||
                                   session.device_info?.toLowerCase().includes('android') ||
                                   session.device_info?.toLowerCase().includes('iphone');

                  return (
                    <div
                      key={session.id}
                      className="flex items-center justify-between p-3 bg-muted/30 border border-border rounded-lg"
                    >
                      <div className="flex items-center gap-3">
                        {isMobile ? (
                          <Smartphone className="w-5 h-5 text-muted-foreground" />
                        ) : (
                          <Monitor className="w-5 h-5 text-muted-foreground" />
                        )}
                        <div>
                          <p className="text-sm font-medium text-foreground">
                            {session.device_info || 'Unknown Device'}
                          </p>
                          <div className="flex items-center gap-2 text-xs text-muted-foreground">
                            {session.ip_address && <span>{session.ip_address}</span>}
                            {session.ip_address && session.last_used_at && <span>•</span>}
                            {session.last_used_at && (
                              <span>Last active: {new Date(session.last_used_at).toLocaleDateString()}</span>
                            )}
                          </div>
                          <p className="text-xs text-muted-foreground mt-0.5">
                            Expires: {new Date(session.expires_at).toLocaleDateString()}
                          </p>
                        </div>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-destructive hover:text-destructive hover:bg-destructive/10"
                        onClick={() => handleRevokeSession(session.id)}
                        disabled={revokingSession === session.id}
                      >
                        {revokingSession === session.id ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <Trash2 className="w-4 h-4" />
                        )}
                      </Button>
                    </div>
                  );
                })}
              </div>
            )}

            <Separator className="bg-border" />

            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-foreground">Logout All Devices</p>
                <p className="text-xs text-muted-foreground">End all sessions including this one</p>
              </div>
              <Button
                variant="outline"
                size="sm"
                className="border-destructive text-destructive hover:bg-destructive/10"
                onClick={handleLogoutAllDevices}
              >
                Logout All
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}
