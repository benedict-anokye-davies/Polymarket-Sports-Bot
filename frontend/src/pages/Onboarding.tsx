import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  TrendingUp,
  Zap,
  Shield,
  BarChart3,
  Wallet,
  ChevronLeft,
  ChevronRight,
  Check,
  TestTube2,
  Eye,
  EyeOff,
  Loader2,
  Play,
  FlaskConical,
  BookOpen,
  Rocket
} from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Progress } from '@/components/ui/progress';
import { useToast } from '@/components/ui/use-toast';
import { cn } from '@/lib/utils';
import { apiClient } from '@/api/client';
import { useAuthStore } from '@/stores/useAuthStore';
import { useAppStore } from '@/stores/useAppStore';

const TOTAL_STEPS = 4;

// Supported platforms
const PLATFORMS = [
  { id: 'kalshi', name: 'Kalshi', desc: 'US-regulated prediction market' },
  { id: 'polymarket', name: 'Polymarket', desc: 'Crypto-based prediction market' },
] as const;

// Shared state interface for all form data
interface OnboardingData {
  // Platform selection
  platform: 'kalshi' | 'polymarket';
  // API credentials
  apiKey: string;
  apiSecret: string;
  apiPassphrase: string;
  funderAddress: string;
  // Risk
  maxDailyLoss: number;
  maxExposure: number;
  maxConcurrentPositions: number;
}

interface StepProps {
  onNext: () => void;
  onBack: () => void;
  data: OnboardingData;
  setData: React.Dispatch<React.SetStateAction<OnboardingData>>;
  loading: boolean;
}

// Step 1: Welcome
function WelcomeStep({ onNext }: { onNext: () => void }) {
  return (
    <motion.div
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -20 }}
      className="space-y-8"
    >
      <div className="text-center">
        <div className="w-20 h-20 rounded-2xl bg-primary/10 flex items-center justify-center mx-auto mb-6">
          <TrendingUp className="w-10 h-10 text-primary" />
        </div>
        <h2 className="text-2xl font-semibold text-foreground mb-2">Welcome to Kalshi Bot</h2>
        <p className="text-muted-foreground">Your automated edge in sports prediction markets</p>
      </div>

      <div className="grid grid-cols-3 gap-4">
        {[
          { icon: Zap, title: 'Fast Execution', desc: 'Millisecond latency', color: 'text-warning' },
          { icon: Shield, title: 'Secure Core', desc: 'Encrypted vault', color: 'text-primary' },
          { icon: BarChart3, title: 'Live Analytics', desc: 'Real-time P&L', color: 'text-info' },
        ].map((feature, i) => (
          <div
            key={i}
            className="p-4 rounded-lg bg-muted/30 border border-border text-center hover:border-primary/30 transition-colors"
          >
            <feature.icon className={cn('w-8 h-8 mx-auto mb-3', feature.color)} />
            <h3 className="text-sm font-medium text-foreground mb-1">{feature.title}</h3>
            <p className="text-xs text-muted-foreground">{feature.desc}</p>
          </div>
        ))}
      </div>

      <div className="bg-info/10 border border-info/20 rounded-lg p-4 flex gap-3">
        <div className="w-5 h-5 rounded-full bg-info/20 flex items-center justify-center flex-shrink-0 mt-0.5">
          <span className="text-info text-xs">i</span>
        </div>
        <p className="text-sm text-muted-foreground">
          This wizard will guide you through connecting your wallet and configuring your initial risk parameters.
        </p>
      </div>

      <Button onClick={onNext} className="w-full bg-primary hover:bg-primary/90">
        Get Started
        <ChevronRight className="w-4 h-4 ml-2" />
      </Button>
    </motion.div>
  );
}

// Step 2: Connect Trading Account
function WalletStep({ onNext, onBack, data, setData, loading }: StepProps) {
  const [showKey, setShowKey] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<'idle' | 'testing' | 'success' | 'error'>('idle');
  const { toast } = useToast();

  const testConnection = async () => {
    const isKalshiPlatform = data.platform === 'kalshi';

    if (isKalshiPlatform && (!data.apiKey || !data.apiSecret)) {
      toast({
        title: 'Error',
        description: 'Please enter API Key and API Secret.',
        variant: 'destructive',
      });
      return;
    }

    if (!isKalshiPlatform && (!data.apiKey || !data.funderAddress)) {
      toast({
        title: 'Error',
        description: 'Please enter Private Key and Wallet Address.',
        variant: 'destructive',
      });
      return;
    }

    setConnectionStatus('testing');
    try {
      await apiClient.connectWallet(data.platform, {
        apiKey: isKalshiPlatform ? data.apiKey : undefined,
        apiSecret: isKalshiPlatform ? data.apiSecret : undefined,
        privateKey: !isKalshiPlatform ? data.apiKey : undefined,
        funderAddress: !isKalshiPlatform ? data.funderAddress : undefined,
      });
      setConnectionStatus('success');
      toast({
        title: 'Success',
        description: 'Account connected successfully.',
      });
    } catch (error) {
      setConnectionStatus('error');
      toast({
        title: 'Error',
        description: error instanceof Error ? error.message : 'Connection failed. Please check your credentials.',
        variant: 'destructive',
      });
    }
  };

  // Allow proceeding if required credentials are filled (test is optional)
  const canProceed = data.apiKey.trim() && data.apiSecret.trim();
  const isKalshi = data.platform === 'kalshi';

  return (
    <motion.div
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -20 }}
      className="space-y-6"
    >
      <div className="text-center">
        <div className="w-16 h-16 rounded-xl bg-primary/10 flex items-center justify-center mx-auto mb-4">
          <Wallet className="w-8 h-8 text-primary" />
        </div>
        <h2 className="text-xl font-semibold text-foreground mb-1">Connect Your Account</h2>
        <p className="text-sm text-muted-foreground">Choose your platform and enter credentials</p>
      </div>

      {/* Platform Selection */}
      <div className="bg-muted/30 rounded-lg p-4 border border-border">
        <Label className="text-sm font-medium text-foreground mb-3 block">Trading Platform</Label>
        <div className="grid grid-cols-2 gap-3">
          {PLATFORMS.map((platform) => (
            <div
              key={platform.id}
              onClick={() => setData(prev => ({ ...prev, platform: platform.id as 'kalshi' | 'polymarket' }))}
              className={cn(
                'p-4 rounded-md border cursor-pointer transition-all',
                data.platform === platform.id
                  ? 'bg-primary/10 border-primary/30'
                  : 'bg-muted border-border hover:border-primary/20'
              )}
            >
              <span className={cn(
                'text-sm font-semibold block',
                data.platform === platform.id ? 'text-primary' : 'text-foreground'
              )}>
                {platform.name}
              </span>
              <span className="text-xs text-muted-foreground">{platform.desc}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="bg-warning/10 border border-warning/20 rounded-lg p-4 flex gap-3">
        <Shield className="w-5 h-5 text-warning flex-shrink-0" />
        <div>
          <p className="text-sm font-medium text-foreground">Security Notice</p>
          <p className="text-xs text-muted-foreground mt-1">
            Your credentials are encrypted before being stored in the database.
          </p>
        </div>
      </div>

      <div className="space-y-4">
        <div className="space-y-2">
          <Label className="text-muted-foreground">API Key</Label>
          <Input
            type="text"
            placeholder={isKalshi ? 'Your Kalshi API Key' : 'Your Polymarket API Key'}
            className="bg-muted border-border font-mono"
            value={data.apiKey}
            onChange={(e) => setData(prev => ({ ...prev, apiKey: e.target.value }))}
          />
          <p className="text-xs text-muted-foreground">
            {isKalshi ? 'From Kalshi Settings > API Keys' : 'From Polymarket Settings > API Keys'}
          </p>
        </div>

        <div className="space-y-2">
          <Label className="text-muted-foreground">API Secret</Label>
          <div className="relative">
            <Input
              type={showKey ? 'text' : 'password'}
              placeholder="Your API Secret"
              className="bg-muted border-border font-mono pr-10"
              value={data.apiSecret}
              onChange={(e) => setData(prev => ({ ...prev, apiSecret: e.target.value }))}
            />
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="absolute right-1 top-1/2 -translate-y-1/2 h-7 w-7"
              onClick={() => setShowKey(!showKey)}
            >
              {showKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </Button>
          </div>
        </div>

        {/* Polymarket-specific fields */}
        {!isKalshi && (
          <>
            <div className="space-y-2">
              <Label className="text-muted-foreground">API Passphrase</Label>
              <Input
                type="password"
                placeholder="Your API Passphrase"
                className="bg-muted border-border font-mono"
                value={data.apiPassphrase}
                onChange={(e) => setData(prev => ({ ...prev, apiPassphrase: e.target.value }))}
              />
            </div>

            <div className="space-y-2">
              <Label className="text-muted-foreground">Wallet Address</Label>
              <Input
                type="text"
                placeholder="0x..."
                className="bg-muted border-border font-mono"
                value={data.funderAddress}
                onChange={(e) => setData(prev => ({ ...prev, funderAddress: e.target.value }))}
              />
              <p className="text-xs text-muted-foreground">Your Polygon wallet holding USDC</p>
            </div>
          </>
        )}

        <Button
          variant="outline"
          className="w-full border-border hover:bg-muted gap-2"
          onClick={testConnection}
          disabled={connectionStatus === 'testing'}
        >
          {connectionStatus === 'testing' ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <TestTube2 className="w-4 h-4" />
          )}
          {connectionStatus === 'testing' ? 'Testing...' : 'Test Connection (Optional)'}
        </Button>

        {connectionStatus === 'success' && (
          <div className="flex items-center gap-2 text-sm text-primary">
            <Check className="w-4 h-4" />
            Connection successful
          </div>
        )}
        {connectionStatus === 'error' && (
          <div className="flex items-center gap-2 text-sm text-destructive">
            Connection failed. You can still continue and fix credentials later.
          </div>
        )}
      </div>

      <div className="flex gap-3">
        <Button variant="outline" onClick={onBack} className="flex-1 border-border">
          <ChevronLeft className="w-4 h-4 mr-2" />
          Back
        </Button>
        <Button
          onClick={onNext}
          className="flex-1 bg-primary hover:bg-primary/90"
          disabled={loading || !canProceed}
        >
          {loading ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null}
          Continue
          <ChevronRight className="w-4 h-4 ml-2" />
        </Button>
      </div>
    </motion.div>
  );
}

// Step 3: Risk Management
function RiskStep({ onNext, onBack, data, setData, loading }: StepProps) {
  return (
    <motion.div
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -20 }}
      className="space-y-6"
    >
      <div className="text-center">
        <div className="w-16 h-16 rounded-xl bg-warning/10 flex items-center justify-content mx-auto mb-4">
          <Shield className="w-8 h-8 text-warning" />
        </div>
        <h2 className="text-xl font-semibold text-foreground mb-1">Risk Management</h2>
        <p className="text-sm text-muted-foreground">Protect your capital with hard limits</p>
      </div>

      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label className="text-sm text-muted-foreground">Max Daily Loss (USDC)</Label>
            <Input
              type="number"
              min="0"
              placeholder="e.g. 100"
              className="bg-muted border-border"
              value={data.maxDailyLoss || ''}
              onChange={(e) => setData(prev => ({ ...prev, maxDailyLoss: parseFloat(e.target.value) || 0 }))}
            />
            <p className="text-xs text-muted-foreground">Bot stops if loss hits this amount</p>
          </div>
          <div className="space-y-2">
            <Label className="text-sm text-muted-foreground">Max Exposure (USDC)</Label>
            <Input
              type="number"
              min="0"
              placeholder="e.g. 500"
              className="bg-muted border-border"
              value={data.maxExposure || ''}
              onChange={(e) => setData(prev => ({ ...prev, maxExposure: parseFloat(e.target.value) || 0 }))}
            />
            <p className="text-xs text-muted-foreground">Total capital at risk limit</p>
          </div>
          <div className="space-y-2 col-span-2">
            <Label className="text-sm text-muted-foreground">Max Concurrent Positions</Label>
            <Input
              type="number"
              min="1"
              placeholder="e.g. 10"
              className="bg-muted border-border"
              value={data.maxConcurrentPositions || ''}
              onChange={(e) => setData(prev => ({ ...prev, maxConcurrentPositions: parseInt(e.target.value) || 0 }))}
            />
          </div>
        </div>

        <div className="bg-destructive/10 border border-destructive/20 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-foreground">Emergency Stop</p>
              <p className="text-xs text-muted-foreground mt-1">
                You can instantly halt all trading activity from the dashboard
              </p>
            </div>
          </div>
        </div>
      </div>

      <div className="flex gap-3">
        <Button variant="outline" onClick={onBack} className="flex-1 border-border">
          <ChevronLeft className="w-4 h-4 mr-2" />
          Back
        </Button>
        <Button
          onClick={onNext}
          className="flex-1 bg-primary hover:bg-primary/90"
          disabled={loading}
        >
          Continue
          <ChevronRight className="w-4 h-4 ml-2" />
        </Button>
      </div>
    </motion.div>
  );
}

// Step 4: Tour & Paper Trading Demo
function TourStep({ onNext, onBack, loading }: { onNext: () => void; onBack: () => void; loading: boolean }) {
  return (
    <motion.div
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -20 }}
      className="space-y-6"
    >
      <div className="text-center">
        <div className="w-16 h-16 rounded-xl bg-primary/10 flex items-center justify-center mx-auto mb-4">
          <Rocket className="w-8 h-8 text-primary" />
        </div>
        <h2 className="text-xl font-semibold text-foreground mb-1">You're All Set!</h2>
        <p className="text-sm text-muted-foreground">Let's take a quick tour and try paper trading</p>
      </div>

      {/* How it works */}
      <div className="bg-muted/30 rounded-lg p-4 border border-border space-y-3">
        <h3 className="font-medium text-foreground flex items-center gap-2">
          <BookOpen className="w-4 h-4 text-primary" />
          How the Bot Works
        </h3>
        <ol className="text-sm text-muted-foreground space-y-2 list-decimal pl-4">
          <li><strong>Select Games:</strong> Choose which sports games you want to trade</li>
          <li><strong>Set Strategy:</strong> Configure probability thresholds and position sizes</li>
          <li><strong>Monitor:</strong> Bot watches live game data and market odds in real-time</li>
          <li><strong>Auto-Trade:</strong> When odds drop to your threshold, bot enters position</li>
          <li><strong>Exit:</strong> Bot exits at take-profit or stop-loss automatically</li>
        </ol>
      </div>

      {/* Paper Trading Explanation */}
      <div className="bg-success/10 border border-success/20 rounded-lg p-4">
        <div className="flex gap-3">
          <FlaskConical className="w-5 h-5 text-success flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-foreground">Paper Trading Mode</p>
            <p className="text-xs text-muted-foreground mt-1">
              Paper trading is <strong>enabled by default</strong>. This means all trades are simulated - 
              no real money is used. You can test strategies, see how the bot performs, and gain 
              confidence before switching to live trading.
            </p>
            <div className="mt-3 flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-success animate-pulse" />
              <span className="text-xs text-success font-medium">Safe to experiment!</span>
            </div>
          </div>
        </div>
      </div>

      {/* What's Next */}
      <div className="bg-info/10 border border-info/20 rounded-lg p-4">
        <div className="flex gap-3">
          <Play className="w-5 h-5 text-info flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-foreground">Try Your First Demo Trade</p>
            <p className="text-xs text-muted-foreground mt-1">
              After entering the dashboard, go to <strong>Bot Config</strong>, select a game, 
              and start the bot with paper trading ON. Watch it monitor odds and simulate trades!
            </p>
          </div>
        </div>
      </div>

      <div className="flex gap-3">
        <Button variant="outline" onClick={onBack} className="flex-1 border-border">
          <ChevronLeft className="w-4 h-4 mr-2" />
          Back
        </Button>
        <Button
          onClick={onNext}
          className="flex-1 bg-primary hover:bg-primary/90"
          disabled={loading}
        >
          {loading ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null}
          Launch Dashboard
          <Rocket className="w-4 h-4 ml-2" />
        </Button>
      </div>
    </motion.div>
  );
}

export default function Onboarding() {
  const navigate = useNavigate();
  const { toast } = useToast();
  const { refreshUser, setOnboardingCompleted } = useAuthStore();
  const { startTour } = useAppStore();
  const [currentStep, setCurrentStep] = useState(1);
  const [loading, setLoading] = useState(false);

  // Centralized form data
  const [data, setData] = useState<OnboardingData>({
    platform: 'kalshi',
    apiKey: '',
    apiSecret: '',
    apiPassphrase: '',
    funderAddress: '',
    maxDailyLoss: 100,
    maxExposure: 500,
    maxConcurrentPositions: 10,
  });

  const saveDataToBackend = async () => {
    setLoading(true);
    try {
      // Save global settings
      await apiClient.updateGlobalSettings({
        max_daily_loss_usdc: data.maxDailyLoss,
        max_portfolio_exposure_usdc: data.maxExposure,
        bot_enabled: true,
      });

      // Complete onboarding step 4
      await apiClient.completeOnboardingStep(4, {
        platform: data.platform,
      });

      // Refresh user state
      await refreshUser();

      toast({
        title: 'Success',
        description: 'Onboarding complete! Welcome to your dashboard.',
      });

      // Navigate first, then start tour with a delay
      navigate('/dashboard');
      setTimeout(() => {
        startTour();
      }, 500);
    } catch (error) {
      console.error('Failed to save onboarding data:', error);
      toast({
        title: 'Error',
        description: error instanceof Error ? error.message : 'Failed to save settings. Please try again.',
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  };

  const handleNext = async () => {
    if (currentStep < TOTAL_STEPS) {
      setCurrentStep(currentStep + 1);
    } else {
      await saveDataToBackend();
    }
  };

  const handleBack = () => {
    if (currentStep > 1) {
      setCurrentStep(currentStep - 1);
    }
  };

  const skipOnboarding = () => {
    // Mark onboarding as completed in local state to bypass route guard
    setOnboardingCompleted();
    toast({
      title: 'Skipped',
      description: 'You can configure settings later from the Settings page.',
    });
    navigate('/dashboard');
  };

  const progressPercent = (currentStep / TOTAL_STEPS) * 100;

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4 relative overflow-hidden">
      {/* Background effects */}
      <div className="absolute inset-0 bg-gradient-to-br from-primary/5 via-transparent to-primary/10 pointer-events-none" />
      <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-primary/5 rounded-full blur-3xl" />
      <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-primary/5 rounded-full blur-3xl" />

      <div className="w-full max-w-lg">
        {/* Progress */}
        <div className="mb-6">
          <div className="flex items-center justify-between text-sm mb-2">
            <span className="text-muted-foreground">Setup Progress</span>
            <span className="text-foreground">Step {currentStep} of {TOTAL_STEPS}</span>
          </div>
          <Progress value={progressPercent} className="h-1.5" />
        </div>

        {/* Card */}
        <Card className="bg-card/80 backdrop-blur border-border shadow-2xl">
          <CardContent className="p-6 md:p-8">
            <AnimatePresence mode="wait">
              {currentStep === 1 && <WelcomeStep key="welcome" onNext={handleNext} />}
              {currentStep === 2 && <WalletStep key="wallet" onNext={handleNext} onBack={handleBack} data={data} setData={setData} loading={loading} />}
              {currentStep === 3 && <RiskStep key="risk" onNext={handleNext} onBack={handleBack} data={data} setData={setData} loading={loading} />}
              {currentStep === 4 && <TourStep key="tour" onNext={handleNext} onBack={handleBack} loading={loading} />}
            </AnimatePresence>
          </CardContent>
        </Card>

        {/* Skip Button */}
        <div className="mt-4 text-center">
          <Button
            variant="ghost"
            className="text-muted-foreground hover:text-foreground text-sm"
            onClick={skipOnboarding}
            disabled={loading}
          >
            Skip setup and go to Dashboard
          </Button>
        </div>
      </div>
    </div>
  );
}
