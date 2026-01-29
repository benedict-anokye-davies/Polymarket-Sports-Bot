import { useState, useEffect } from 'react';
import { Users, Plus, Trash2, Star, Settings, DollarSign, Loader2 } from 'lucide-react';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Badge } from '@/components/ui/badge';
import { Slider } from '@/components/ui/slider';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog';
import { useToast } from '@/hooks/use-toast';
import { apiClient, AccountInfo, AccountSummary } from '@/api/client';

interface Account {
  id: string;
  account_name: string;
  platform: 'polymarket' | 'kalshi';
  environment: 'production' | 'demo';
  is_primary: boolean;
  is_active: boolean;
  allocation_pct: number;
  funder_address?: string;
  balance?: number;
  error?: string;
}

export default function Accounts() {
  const [summary, setSummary] = useState<AccountSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const { toast } = useToast();

  const [newAccount, setNewAccount] = useState({
    account_name: '',
    platform: 'polymarket' as 'polymarket' | 'kalshi',
    environment: 'demo' as 'production' | 'demo',  // Default to demo for safety
    private_key: '',
    funder_address: '',
    api_key: '',
    api_secret: '',
    api_passphrase: '',
    allocation_pct: 100,
    is_primary: false,
  });

  useEffect(() => {
    fetchAccounts();
  }, []);

  const fetchAccounts = async () => {
    try {
      setLoading(true);
      const data = await apiClient.getAccountSummary();
      setSummary(data);
    } catch (err) {
      toast({
        title: 'Error',
        description: 'Failed to load accounts',
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  };

  const createAccount = async () => {
    // Create a copy of credentials before clearing them from state
    const accountData = { ...newAccount };
    
    // Clear sensitive data from state immediately to minimize exposure
    setNewAccount((prev) => ({
      ...prev,
      private_key: '',
      api_key: '',
      api_secret: '',
      api_passphrase: '',
    }));
    
    try {
      setSaving(true);
      await apiClient.createAccount(accountData);
      toast({
        title: 'Success',
        description: 'Account created successfully',
      });
      setDialogOpen(false);
      setNewAccount({
        account_name: '',
        platform: 'polymarket',
        environment: 'demo',
        private_key: '',
        funder_address: '',
        api_key: '',
        api_secret: '',
        api_passphrase: '',
        allocation_pct: 100,
        is_primary: false,
      });
      fetchAccounts();
    } catch (err) {
      toast({
        title: 'Error',
        description: err instanceof Error ? err.message : 'Failed to create account',
        variant: 'destructive',
      });
    } finally {
      setSaving(false);
    }
  };

  const deleteAccount = async (accountId: string) => {
    try {
      await apiClient.deleteAccount(accountId);
      toast({
        title: 'Success',
        description: 'Account deleted',
      });
      fetchAccounts();
    } catch (err) {
      toast({
        title: 'Error',
        description: 'Failed to delete account',
        variant: 'destructive',
      });
    }
  };

  const setPrimary = async (accountId: string) => {
    try {
      await apiClient.setPrimaryAccount(accountId);
      toast({
        title: 'Success',
        description: 'Primary account updated',
      });
      fetchAccounts();
    } catch (err) {
      toast({
        title: 'Error',
        description: 'Failed to set primary account',
        variant: 'destructive',
      });
    }
  };

  const toggleActive = async (accountId: string, currentState: boolean) => {
    try {
      await apiClient.updateAccount(accountId, { is_active: !currentState });
      fetchAccounts();
    } catch (err) {
      toast({
        title: 'Error',
        description: 'Failed to update account',
        variant: 'destructive',
      });
    }
  };

  const updateAllocation = async (accountId: string, pct: number) => {
    if (!summary) return;

    const newAllocations = summary.accounts.map((acc) => ({
      account_id: acc.id,
      allocation_pct: acc.id === accountId ? pct : acc.allocation_pct,
    }));

    // Don't save if total doesn't equal 100
    const total = newAllocations.reduce((sum, a) => sum + a.allocation_pct, 0);
    if (Math.abs(total - 100) > 0.01) {
      setSummary({
        ...summary,
        accounts: summary.accounts.map((acc) =>
          acc.id === accountId ? { ...acc, allocation_pct: pct } : acc
        ),
        allocation_valid: false,
        total_allocation_pct: total,
      });
      return;
    }

    try {
      await apiClient.updateAllocations(newAllocations);
      fetchAccounts();
    } catch (err) {
      toast({
        title: 'Error',
        description: 'Failed to update allocations',
        variant: 'destructive',
      });
    }
  };

  const formatCurrency = (value: number | null | undefined) => {
    if (value === null || value === undefined) return 'N/A';
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(value);
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
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-foreground">Accounts</h1>
            <p className="text-sm text-muted-foreground mt-1">
              Manage multiple trading accounts and allocations
            </p>
          </div>
          <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
            <DialogTrigger asChild>
              <Button>
                <Plus className="w-4 h-4 mr-2" />
                Add Account
              </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-[500px]">
              <DialogHeader>
                <DialogTitle>Add Trading Account</DialogTitle>
                <DialogDescription>
                  Connect a new trading account. Your credentials will be encrypted.
                </DialogDescription>
              </DialogHeader>
              <div className="grid gap-4 py-4">
                <div className="grid gap-2">
                  <Label htmlFor="platform">Platform</Label>
                  <Select
                    value={newAccount.platform}
                    onValueChange={(value: 'polymarket' | 'kalshi') => setNewAccount({ ...newAccount, platform: value })}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select platform" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="polymarket">Polymarket</SelectItem>
                      <SelectItem value="kalshi">Kalshi</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="name">Account Name</Label>
                  <Input
                    id="name"
                    placeholder="e.g., Main Trading"
                    value={newAccount.account_name}
                    onChange={(e) => setNewAccount({ ...newAccount, account_name: e.target.value })}
                  />
                </div>
                {newAccount.platform === 'polymarket' ? (
                  <>
                    <div className="grid gap-2">
                      <Label htmlFor="private_key">Private Key</Label>
                      <Input
                        id="private_key"
                        type="password"
                        placeholder="0x..."
                        value={newAccount.private_key}
                        onChange={(e) => setNewAccount({ ...newAccount, private_key: e.target.value })}
                      />
                    </div>
                    <div className="grid gap-2">
                      <Label htmlFor="funder">Funder Address</Label>
                      <Input
                        id="funder"
                        placeholder="0x..."
                        value={newAccount.funder_address}
                        onChange={(e) => setNewAccount({ ...newAccount, funder_address: e.target.value })}
                      />
                    </div>
                  </>
                ) : (
                  <>
                    <div className="grid gap-2">
                      <Label htmlFor="environment">Environment</Label>
                      <Select
                        value={newAccount.environment}
                        onValueChange={(value: 'production' | 'demo') => setNewAccount({ ...newAccount, environment: value })}
                      >
                        <SelectTrigger>
                          <SelectValue placeholder="Select environment" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="demo">Demo (Paper Trading)</SelectItem>
                          <SelectItem value="production">Production (Real Money)</SelectItem>
                        </SelectContent>
                      </Select>
                      <p className="text-xs text-muted-foreground">
                        {newAccount.environment === 'demo' 
                          ? 'Uses demo.kalshi.com API - no real money involved'
                          : 'Uses production Kalshi API - real money trades'}
                      </p>
                    </div>
                    <div className="grid gap-2">
                      <Label htmlFor="api_key">API Key</Label>
                      <Input
                        id="api_key"
                        type="password"
                        placeholder="Your Kalshi API key"
                        value={newAccount.api_key}
                        onChange={(e) => setNewAccount({ ...newAccount, api_key: e.target.value })}
                      />
                    </div>
                    <div className="grid gap-2">
                      <Label htmlFor="api_secret">Private Key (RSA PEM)</Label>
                      <Input
                        id="api_secret"
                        type="password"
                        placeholder="Your Kalshi RSA private key"
                        value={newAccount.api_secret}
                        onChange={(e) => setNewAccount({ ...newAccount, api_secret: e.target.value })}
                      />
                      <p className="text-xs text-muted-foreground">
                        The RSA private key from your Kalshi API settings
                      </p>
                    </div>
                  </>
                )}
                <div className="grid gap-2">
                  <Label htmlFor="allocation">Allocation (%)</Label>
                  <Input
                    id="allocation"
                    type="number"
                    min="0"
                    max="100"
                    value={newAccount.allocation_pct}
                    onChange={(e) => setNewAccount({ ...newAccount, allocation_pct: parseFloat(e.target.value) })}
                  />
                </div>
                <div className="flex items-center space-x-2">
                  <Switch
                    id="primary"
                    checked={newAccount.is_primary}
                    onCheckedChange={(checked) => setNewAccount({ ...newAccount, is_primary: checked })}
                  />
                  <Label htmlFor="primary">Set as primary account</Label>
                </div>
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setDialogOpen(false)}>
                  Cancel
                </Button>
                <Button onClick={createAccount} disabled={saving}>
                  {saving && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
                  Create Account
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>

        {/* Summary Card */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <DollarSign className="w-5 h-5" />
              Total Balance
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">
              {formatCurrency(summary?.total_balance)}
            </div>
            <p className="text-sm text-muted-foreground mt-1">
              Across {summary?.total_accounts ?? 0} accounts
            </p>
            {!summary?.allocation_valid && (
              <Badge variant="destructive" className="mt-2">
                Allocations must sum to 100% (currently {summary?.total_allocation_pct?.toFixed(1)}%)
              </Badge>
            )}
          </CardContent>
        </Card>

        {/* Accounts List */}
        <div className="grid gap-4">
          {summary?.accounts.map((account) => (
            <Card key={account.id}>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <CardTitle className="flex items-center gap-2">
                      <Users className="w-5 h-5" />
                      {account.account_name}
                    </CardTitle>
                    <Badge variant={account.platform === 'kalshi' ? 'secondary' : 'default'} className="capitalize">
                      {account.platform || 'polymarket'}
                    </Badge>
                    {account.platform === 'kalshi' && (
                      <Badge variant={account.environment === 'demo' ? 'outline' : 'destructive'} className="capitalize">
                        {account.environment === 'demo' ? 'Demo' : 'Live'}
                      </Badge>
                    )}
                    {account.is_primary && (
                      <Badge variant="default">
                        <Star className="w-3 h-3 mr-1" />
                        Primary
                      </Badge>
                    )}
                    <Badge variant={account.is_active ? 'outline' : 'secondary'}>
                      {account.is_active ? 'Active' : 'Inactive'}
                    </Badge>
                  </div>
                  <div className="flex items-center gap-2">
                    <Switch
                      checked={account.is_active}
                      onCheckedChange={() => toggleActive(account.id, account.is_active)}
                    />
                    {!account.is_primary && (
                      <>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setPrimary(account.id)}
                        >
                          <Star className="w-4 h-4" />
                        </Button>
                        <AlertDialog>
                          <AlertDialogTrigger asChild>
                            <Button variant="outline" size="sm">
                              <Trash2 className="w-4 h-4 text-destructive" />
                            </Button>
                          </AlertDialogTrigger>
                          <AlertDialogContent>
                            <AlertDialogHeader>
                              <AlertDialogTitle>Delete Account</AlertDialogTitle>
                              <AlertDialogDescription>
                                Are you sure you want to delete "{account.account_name}"?
                                This action cannot be undone.
                              </AlertDialogDescription>
                            </AlertDialogHeader>
                            <AlertDialogFooter>
                              <AlertDialogCancel>Cancel</AlertDialogCancel>
                              <AlertDialogAction onClick={() => deleteAccount(account.id)}>
                                Delete
                              </AlertDialogAction>
                            </AlertDialogFooter>
                          </AlertDialogContent>
                        </AlertDialog>
                      </>
                    )}
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                  <div>
                    <p className="text-sm text-muted-foreground">Balance</p>
                    <p className="text-lg font-semibold">
                      {account.error ? (
                        <span className="text-destructive text-sm">{account.error}</span>
                      ) : (
                        formatCurrency(account.balance)
                      )}
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Allocation</p>
                    <div className="flex items-center gap-2">
                      <Input
                        type="number"
                        className="w-20 h-8"
                        min="0"
                        max="100"
                        value={account.allocation_pct}
                        onChange={(e) => updateAllocation(account.id, parseFloat(e.target.value))}
                      />
                      <span className="text-sm">%</span>
                    </div>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Funder</p>
                    <p className="text-sm font-mono truncate">
                      {account.funder_address || 'N/A'}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}

          {(summary?.accounts.length ?? 0) === 0 && (
            <Card>
              <CardContent className="text-center py-12">
                <Users className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
                <p className="text-muted-foreground">
                  No accounts configured yet. Add your first trading account to get started.
                </p>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </DashboardLayout>
  );
}
