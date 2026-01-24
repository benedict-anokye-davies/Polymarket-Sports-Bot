import { useState } from 'react';
import { Eye, EyeOff, Bell, Shield, Wallet, TestTube2 } from 'lucide-react';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Separator } from '@/components/ui/separator';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';

export default function Settings() {
  const [showPrivateKey, setShowPrivateKey] = useState(false);
  const [notifications, setNotifications] = useState({
    tradeExecuted: true,
    positionClosed: true,
    errorAlerts: true,
  });

  return (
    <DashboardLayout>
      <div className="space-y-6 max-w-4xl">
        {/* Page Header */}
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Settings</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Configure your bot and trading parameters
          </p>
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
                />
                <Button
                  variant="ghost"
                  size="icon"
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
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="walletAddress" className="text-muted-foreground">Wallet Address</Label>
              <Input
                id="walletAddress"
                placeholder="0x..."
                className="bg-muted border-border font-mono"
              />
              <p className="text-xs text-muted-foreground">Your Polygon wallet holding USDC</p>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-primary" />
              <span className="text-sm text-primary">Connected</span>
            </div>
            <Button variant="outline" className="border-border hover:bg-muted gap-2">
              <TestTube2 className="w-4 h-4" />
              Test Connection
            </Button>
          </CardContent>
        </Card>

        {/* Trading Parameters */}
        <Card className="bg-card border-border">
          <CardHeader>
            <CardTitle className="text-base font-medium text-foreground">Trading Parameters</CardTitle>
          </CardHeader>
          <CardContent>
            <Accordion type="multiple" className="space-y-2">
              {['NBA', 'NFL', 'MLB', 'NHL', 'NCAA CBB', 'Soccer', 'Tennis', 'Cricket', 'UFC'].map((sport) => (
                <AccordionItem key={sport} value={sport} className="border-border">
                  <AccordionTrigger className="hover:no-underline px-4 py-3 bg-muted/30 rounded-md">
                    <div className="flex items-center justify-between w-full pr-4">
                      <span className="font-medium">{sport}</span>
                      <Switch defaultChecked />
                    </div>
                  </AccordionTrigger>
                  <AccordionContent className="pt-4 px-4">
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label className="text-muted-foreground text-xs">Probability Drop %</Label>
                        <Input type="number" defaultValue="5" className="bg-muted border-border" />
                      </div>
                      <div className="space-y-2">
                        <Label className="text-muted-foreground text-xs">Min Volume Threshold ($)</Label>
                        <Input type="number" defaultValue="1000" className="bg-muted border-border" />
                      </div>
                      <div className="space-y-2">
                        <Label className="text-muted-foreground text-xs">Take Profit %</Label>
                        <Input type="number" defaultValue="25" className="bg-muted border-border" />
                      </div>
                      <div className="space-y-2">
                        <Label className="text-muted-foreground text-xs">Stop Loss %</Label>
                        <Input type="number" defaultValue="15" className="bg-muted border-border" />
                      </div>
                      <div className="space-y-2">
                        <Label className="text-muted-foreground text-xs">Position Size ($)</Label>
                        <Input type="number" defaultValue="50" className="bg-muted border-border" />
                      </div>
                      <div className="space-y-2">
                        <Label className="text-muted-foreground text-xs">Latest Entry Time (min)</Label>
                        <Input type="number" defaultValue="5" className="bg-muted border-border" />
                      </div>
                      <div className="space-y-2 col-span-2">
                        <Label className="text-muted-foreground text-xs">Latest Exit Time (min)</Label>
                        <Input type="number" defaultValue="2" className="bg-muted border-border" />
                      </div>
                    </div>
                  </AccordionContent>
                </AccordionItem>
              ))}
            </Accordion>
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
                <Label className="text-muted-foreground">Max Daily Loss ($)</Label>
                <Input type="number" defaultValue="500" className="bg-muted border-border" />
              </div>
              <div className="space-y-2">
                <Label className="text-muted-foreground">Max Total Exposure ($)</Label>
                <Input type="number" defaultValue="5000" className="bg-muted border-border" />
              </div>
              <div className="space-y-2">
                <Label className="text-muted-foreground">Max Concurrent Positions</Label>
                <Input type="number" defaultValue="10" className="bg-muted border-border" />
              </div>
              <div className="space-y-2">
                <Label className="text-muted-foreground">Default Position Size ($)</Label>
                <Input type="number" defaultValue="500" className="bg-muted border-border" />
              </div>
            </div>
            <Separator className="bg-border" />
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-foreground">Emergency Stop</p>
                <p className="text-xs text-muted-foreground">Halt all trading immediately</p>
              </div>
              <Switch />
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
              />
            </div>
            <Button variant="outline" size="sm" className="border-border hover:bg-muted">
              Test Webhook
            </Button>
            <Separator className="bg-border" />
            <div className="space-y-3">
              {[
                { key: 'tradeExecuted', label: 'Trade Executed', desc: 'Notify when a trade is placed' },
                { key: 'positionClosed', label: 'Position Closed', desc: 'Notify when a position is closed' },
                { key: 'errorAlerts', label: 'Error Alerts', desc: 'Notify on bot errors or issues' },
              ].map((item) => (
                <div key={item.key} className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-foreground">{item.label}</p>
                    <p className="text-xs text-muted-foreground">{item.desc}</p>
                  </div>
                  <Switch 
                    checked={notifications[item.key as keyof typeof notifications]}
                    onCheckedChange={(checked) => 
                      setNotifications(prev => ({ ...prev, [item.key]: checked }))
                    }
                  />
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Save Button */}
        <div className="flex justify-end">
          <Button className="bg-primary hover:bg-primary/90">
            Save Changes
          </Button>
        </div>
      </div>
    </DashboardLayout>
  );
}
