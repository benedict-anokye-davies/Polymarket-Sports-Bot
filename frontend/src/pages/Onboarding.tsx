import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  TrendingUp, 
  Zap, 
  Shield, 
  BarChart3, 
  Wallet, 
  Settings, 
  Bell,
  ChevronLeft,
  ChevronRight,
  Check,
  TestTube2,
  Eye,
  EyeOff
} from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Checkbox } from '@/components/ui/checkbox';
import { Switch } from '@/components/ui/switch';
import { Progress } from '@/components/ui/progress';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { cn } from '@/lib/utils';

const TOTAL_STEPS = 5;

interface StepProps {
  onNext: () => void;
  onBack: () => void;
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
        <h2 className="text-2xl font-semibold text-foreground mb-2">Welcome to Polymarket Bot</h2>
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

// Step 2: Connect Wallet
function WalletStep({ onNext, onBack }: StepProps) {
  const [showKey, setShowKey] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<'idle' | 'testing' | 'success' | 'error'>('idle');

  const testConnection = async () => {
    setConnectionStatus('testing');
    await new Promise(resolve => setTimeout(resolve, 1500));
    setConnectionStatus('success');
  };

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
        <h2 className="text-xl font-semibold text-foreground mb-1">Connect Your Wallet</h2>
        <p className="text-sm text-muted-foreground">Securely link your Polygon trading account</p>
      </div>

      <div className="bg-warning/10 border border-warning/20 rounded-lg p-4 flex gap-3">
        <Shield className="w-5 h-5 text-warning flex-shrink-0" />
        <div>
          <p className="text-sm font-medium text-foreground">Security Notice</p>
          <p className="text-xs text-muted-foreground mt-1">
            Your private key is encrypted locally before being stored in the database.
          </p>
        </div>
      </div>

      <div className="space-y-4">
        <div className="space-y-2">
          <Label className="text-muted-foreground">API Key</Label>
          <Input
            type="text"
            placeholder="Your Polymarket API Key"
            className="bg-muted border-border font-mono"
          />
          <p className="text-xs text-muted-foreground">From Polymarket Settings &gt; API Keys</p>
        </div>

        <div className="space-y-2">
          <Label className="text-muted-foreground">API Secret</Label>
          <div className="relative">
            <Input
              type={showKey ? 'text' : 'password'}
              placeholder="Your API Secret"
              className="bg-muted border-border font-mono pr-10"
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

        <div className="space-y-2">
          <Label className="text-muted-foreground">API Passphrase</Label>
          <Input
            type="password"
            placeholder="Your API Passphrase"
            className="bg-muted border-border font-mono"
          />
        </div>

        <div className="space-y-2">
          <Label className="text-muted-foreground">Wallet Address</Label>
          <Input
            type="text"
            placeholder="0x..."
            className="bg-muted border-border font-mono"
          />
          <p className="text-xs text-muted-foreground">Your Polygon wallet holding USDC</p>
        </div>

        <Button 
          variant="outline" 
          className="w-full border-border hover:bg-muted gap-2"
          onClick={testConnection}
          disabled={connectionStatus === 'testing'}
        >
          <TestTube2 className="w-4 h-4" />
          {connectionStatus === 'testing' ? 'Testing...' : 'Test Connection'}
        </Button>

        {connectionStatus === 'success' && (
          <div className="flex items-center gap-2 text-sm text-primary">
            <Check className="w-4 h-4" />
            Connection successful
          </div>
        )}
      </div>

      <div className="flex gap-3">
        <Button variant="outline" onClick={onBack} className="flex-1 border-border">
          <ChevronLeft className="w-4 h-4 mr-2" />
          Back
        </Button>
        <Button onClick={onNext} className="flex-1 bg-primary hover:bg-primary/90">
          Continue
          <ChevronRight className="w-4 h-4 ml-2" />
        </Button>
      </div>
    </motion.div>
  );
}

// Step 3: Sport Configuration
function SportConfigStep({ onNext, onBack }: StepProps) {
  const [activeSports, setActiveSports] = useState<string[]>(['nba']);

  const toggleSport = (sport: string) => {
    setActiveSports(prev => 
      prev.includes(sport) 
        ? prev.filter(s => s !== sport)
        : [...prev, sport]
    );
  };

  return (
    <motion.div
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -20 }}
      className="space-y-6"
    >
      <div className="text-center">
        <div className="w-16 h-16 rounded-xl bg-primary/10 flex items-center justify-center mx-auto mb-4">
          <Settings className="w-8 h-8 text-primary" />
        </div>
        <h2 className="text-xl font-semibold text-foreground mb-1">Sport Configuration</h2>
        <p className="text-sm text-muted-foreground">Choose which markets to trade</p>
      </div>

      <div className="space-y-4">
        <div className="bg-muted/30 rounded-lg p-4 border border-border">
          <Label className="text-sm font-medium text-foreground mb-3 block">Active Sports</Label>
          <div className="grid grid-cols-4 gap-3">
            {['nba', 'nfl', 'mlb', 'nhl', 'ncaab', 'ncaaf', 'soccer', 'mma'].map((sport) => (
              <div
                key={sport}
                onClick={() => toggleSport(sport)}
                className={cn(
                  'p-3 rounded-md border text-center cursor-pointer transition-all',
                  activeSports.includes(sport)
                    ? 'bg-primary/10 border-primary/30 text-primary'
                    : 'bg-muted border-border text-muted-foreground hover:border-primary/20'
                )}
              >
                <span className="text-sm font-medium uppercase">{sport}</span>
              </div>
            ))}
          </div>
          <p className="text-xs text-muted-foreground mt-3">Select multiple sports to diversify</p>
        </div>

        <div>
          <Label className="text-xs uppercase tracking-wider text-muted-foreground font-medium">Position Sizing</Label>
          <div className="grid grid-cols-2 gap-4 mt-3">
            <div className="space-y-2">
              <Label className="text-sm text-muted-foreground">Position Size ($)</Label>
              <div className="relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground text-sm">$</span>
                <Input type="number" defaultValue="25" className="bg-muted border-border pl-7" />
              </div>
              <p className="text-xs text-muted-foreground">Amount per trade</p>
            </div>
            <div className="space-y-2">
              <Label className="text-sm text-muted-foreground">Max Open Positions</Label>
              <Input type="number" defaultValue="5" className="bg-muted border-border" />
              <p className="text-xs text-muted-foreground">Concurrent trades limit</p>
            </div>
          </div>
        </div>

        <div>
          <Label className="text-xs uppercase tracking-wider text-muted-foreground font-medium">Entry Thresholds</Label>
          <div className="grid grid-cols-2 gap-4 mt-3">
            <div className="space-y-2">
              <Label className="text-sm text-muted-foreground">Price Drop (%)</Label>
              <div className="relative">
                <Input type="number" defaultValue="5" className="bg-muted border-border pr-8" />
                <span className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground text-sm">%</span>
              </div>
              <p className="text-xs text-muted-foreground">Trigger entry when price drops</p>
            </div>
            <div className="space-y-2">
              <Label className="text-sm text-muted-foreground">Absolute Floor ($)</Label>
              <div className="relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground text-sm">$</span>
                <Input type="number" defaultValue="0.35" step="0.01" className="bg-muted border-border pl-7" />
              </div>
              <p className="text-xs text-muted-foreground">Buy if price falls below</p>
            </div>
          </div>
        </div>

        <div>
          <Label className="text-xs uppercase tracking-wider text-muted-foreground font-medium">Exit Thresholds</Label>
          <div className="grid grid-cols-2 gap-4 mt-3">
            <div className="space-y-2">
              <Label className="text-sm text-muted-foreground">Take Profit (%)</Label>
              <div className="relative">
                <Input type="number" defaultValue="10" className="bg-muted border-border pr-8" />
                <span className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground text-sm">%</span>
              </div>
            </div>
            <div className="space-y-2">
              <Label className="text-sm text-muted-foreground">Stop Loss (%)</Label>
              <div className="relative">
                <Input type="number" defaultValue="15" className="bg-muted border-border pr-8" />
                <span className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground text-sm">%</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="flex gap-3">
        <Button variant="outline" onClick={onBack} className="flex-1 border-border">
          <ChevronLeft className="w-4 h-4 mr-2" />
          Back
        </Button>
        <Button onClick={onNext} className="flex-1 bg-primary hover:bg-primary/90">
          Continue
          <ChevronRight className="w-4 h-4 ml-2" />
        </Button>
      </div>
    </motion.div>
  );
}

// Step 4: Risk Management
function RiskStep({ onNext, onBack }: StepProps) {
  return (
    <motion.div
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -20 }}
      className="space-y-6"
    >
      <div className="text-center">
        <div className="w-16 h-16 rounded-xl bg-warning/10 flex items-center justify-center mx-auto mb-4">
          <Shield className="w-8 h-8 text-warning" />
        </div>
        <h2 className="text-xl font-semibold text-foreground mb-1">Risk Management</h2>
        <p className="text-sm text-muted-foreground">Protect your capital with hard limits</p>
      </div>

      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label className="text-sm text-muted-foreground">Max Daily Loss ($)</Label>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground text-sm">$</span>
              <Input type="number" defaultValue="100" className="bg-muted border-border pl-7" />
            </div>
            <p className="text-xs text-muted-foreground">Bot stops if loss hits this amount</p>
          </div>
          <div className="space-y-2">
            <Label className="text-sm text-muted-foreground">Max Exposure ($)</Label>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground text-sm">$</span>
              <Input type="number" defaultValue="500" className="bg-muted border-border pl-7" />
            </div>
            <p className="text-xs text-muted-foreground">Total capital at risk limit</p>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label className="text-sm text-muted-foreground">Default Position Size ($)</Label>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground text-sm">$</span>
              <Input type="number" defaultValue="50" className="bg-muted border-border pl-7" />
            </div>
          </div>
          <div className="space-y-2">
            <Label className="text-sm text-muted-foreground">Max Concurrent Positions</Label>
            <Input type="number" defaultValue="10" className="bg-muted border-border" />
          </div>
        </div>

        <div className="bg-destructive/10 border border-destructive/20 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-foreground">Emergency Stop</p>
              <p className="text-xs text-muted-foreground mt-1">
                Instantly halt all trading activity
              </p>
            </div>
            <Switch />
          </div>
        </div>
      </div>

      <div className="flex gap-3">
        <Button variant="outline" onClick={onBack} className="flex-1 border-border">
          <ChevronLeft className="w-4 h-4 mr-2" />
          Back
        </Button>
        <Button onClick={onNext} className="flex-1 bg-primary hover:bg-primary/90">
          Continue
          <ChevronRight className="w-4 h-4 ml-2" />
        </Button>
      </div>
    </motion.div>
  );
}

// Step 5: Discord Alerts
function AlertsStep({ onNext, onBack }: StepProps) {
  const [webhookUrl, setWebhookUrl] = useState('');
  const [testStatus, setTestStatus] = useState<'idle' | 'testing' | 'success' | 'error'>('idle');

  const testWebhook = async () => {
    if (!webhookUrl) return;
    setTestStatus('testing');
    await new Promise(resolve => setTimeout(resolve, 1000));
    setTestStatus('success');
  };

  return (
    <motion.div
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -20 }}
      className="space-y-6"
    >
      <div className="text-center">
        <div className="w-16 h-16 rounded-xl bg-info/10 flex items-center justify-center mx-auto mb-4">
          <Bell className="w-8 h-8 text-info" />
        </div>
        <h2 className="text-xl font-semibold text-foreground mb-1">Discord Alerts</h2>
        <p className="text-sm text-muted-foreground">Get notified about trades and events</p>
      </div>

      <div className="space-y-4">
        <div className="space-y-2">
          <Label className="text-sm text-muted-foreground">Discord Webhook URL (Optional)</Label>
          <Input
            type="url"
            placeholder="https://discord.com/api/webhooks/..."
            className="bg-muted border-border font-mono text-sm"
            value={webhookUrl}
            onChange={(e) => setWebhookUrl(e.target.value)}
          />
        </div>

        <Button 
          variant="outline" 
          className="w-full border-border hover:bg-muted gap-2"
          onClick={testWebhook}
          disabled={!webhookUrl || testStatus === 'testing'}
        >
          <TestTube2 className="w-4 h-4" />
          {testStatus === 'testing' ? 'Testing...' : 'Test Webhook'}
        </Button>

        {testStatus === 'success' && (
          <div className="flex items-center gap-2 text-sm text-primary">
            <Check className="w-4 h-4" />
            Test message sent successfully
          </div>
        )}

        <div className="space-y-3 bg-muted/30 rounded-lg p-4 border border-border">
          <Label className="text-sm font-medium text-foreground">Notification Types</Label>
          <div className="space-y-3">
            {[
              { id: 'trade', label: 'Trade Executed', desc: 'When orders are filled' },
              { id: 'position', label: 'Position Closed', desc: 'When positions are closed' },
              { id: 'error', label: 'Error Alerts', desc: 'When errors occur' },
            ].map((item) => (
              <div key={item.id} className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-foreground">{item.label}</p>
                  <p className="text-xs text-muted-foreground">{item.desc}</p>
                </div>
                <Switch defaultChecked />
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="flex gap-3">
        <Button variant="outline" onClick={onBack} className="flex-1 border-border">
          <ChevronLeft className="w-4 h-4 mr-2" />
          Back
        </Button>
        <Button onClick={onNext} className="flex-1 bg-primary hover:bg-primary/90">
          Launch Dashboard
          <ChevronRight className="w-4 h-4 ml-2" />
        </Button>
      </div>

      <Button 
        variant="ghost" 
        className="w-full text-muted-foreground hover:text-foreground"
        onClick={onNext}
      >
        Skip for now
      </Button>
    </motion.div>
  );
}

export default function Onboarding() {
  const navigate = useNavigate();
  const [currentStep, setCurrentStep] = useState(1);

  const handleNext = () => {
    if (currentStep < TOTAL_STEPS) {
      setCurrentStep(currentStep + 1);
    } else {
      navigate('/dashboard');
    }
  };

  const handleBack = () => {
    if (currentStep > 1) {
      setCurrentStep(currentStep - 1);
    }
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
              {currentStep === 2 && <WalletStep key="wallet" onNext={handleNext} onBack={handleBack} />}
              {currentStep === 3 && <SportConfigStep key="sport" onNext={handleNext} onBack={handleBack} />}
              {currentStep === 4 && <RiskStep key="risk" onNext={handleNext} onBack={handleBack} />}
              {currentStep === 5 && <AlertsStep key="alerts" onNext={handleNext} onBack={handleBack} />}
            </AnimatePresence>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
