import { useState, useEffect } from 'react';
import { Check, ChevronDown, Globe, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { useToast } from '@/components/ui/use-toast';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import {
  apiClient,
  SportCategory,
  LeagueInfo,
  UserLeagueStatus,
} from '@/api/client';

/**
 * LeagueSelector Component
 * Allows users to browse and select leagues by category.
 * Supports bulk enable/disable and per-league configuration.
 */
export function LeagueSelector() {
  const { toast } = useToast();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [categories, setCategories] = useState<SportCategory[]>([]);
  const [userStatus, setUserStatus] = useState<UserLeagueStatus | null>(null);
  const [selectedLeagues, setSelectedLeagues] = useState<Set<string>>(new Set());
  const [openCategories, setOpenCategories] = useState<Set<string>>(new Set());

  // Load categories and user status on mount
  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      const [categoriesData, statusData] = await Promise.all([
        apiClient.getSportCategories(),
        apiClient.getUserLeagueStatus(),
      ]);
      setCategories(categoriesData);
      setUserStatus(statusData);
      
      // Initialize selected leagues from user status
      const enabledLeagues = new Set<string>();
      statusData.configured_leagues.forEach(league => {
        if (league.enabled) {
          enabledLeagues.add(league.league_key);
        }
      });
      setSelectedLeagues(enabledLeagues);
    } catch (error) {
      console.error('Failed to load league data:', error);
      toast({
        title: 'Error',
        description: 'Failed to load league data.',
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  };

  const toggleLeague = (leagueKey: string) => {
    setSelectedLeagues(prev => {
      const newSet = new Set(prev);
      if (newSet.has(leagueKey)) {
        newSet.delete(leagueKey);
      } else {
        newSet.add(leagueKey);
      }
      return newSet;
    });
  };

  const toggleCategory = (categoryLeagues: LeagueInfo[]) => {
    const leagueKeys = categoryLeagues.map(l => l.league_key);
    const allSelected = leagueKeys.every(key => selectedLeagues.has(key));
    
    setSelectedLeagues(prev => {
      const newSet = new Set(prev);
      if (allSelected) {
        // Deselect all in category
        leagueKeys.forEach(key => newSet.delete(key));
      } else {
        // Select all in category
        leagueKeys.forEach(key => newSet.add(key));
      }
      return newSet;
    });
  };

  const selectAll = () => {
    const allLeagueKeys = categories.flatMap(cat => 
      cat.leagues.map(l => l.league_key)
    );
    setSelectedLeagues(new Set(allLeagueKeys));
  };

  const deselectAll = () => {
    setSelectedLeagues(new Set());
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      
      // Get all league keys
      const allLeagueKeys = categories.flatMap(cat => 
        cat.leagues.map(l => l.league_key)
      );
      
      // Split into enabled and disabled
      const enabledKeys = Array.from(selectedLeagues);
      const disabledKeys = allLeagueKeys.filter(key => !selectedLeagues.has(key));
      
      // Enable selected leagues
      if (enabledKeys.length > 0) {
        await apiClient.bulkEnableLeagues(enabledKeys, true);
      }
      
      // Disable unselected leagues
      if (disabledKeys.length > 0) {
        await apiClient.bulkEnableLeagues(disabledKeys, false);
      }
      
      toast({
        title: 'Success',
        description: `${enabledKeys.length} leagues enabled, ${disabledKeys.length} leagues disabled.`,
      });
      
      // Reload status
      const statusData = await apiClient.getUserLeagueStatus();
      setUserStatus(statusData);
    } catch (error) {
      console.error('Failed to save league selection:', error);
      toast({
        title: 'Error',
        description: 'Failed to save league selection.',
        variant: 'destructive',
      });
    } finally {
      setSaving(false);
    }
  };

  const toggleCategoryOpen = (category: string) => {
    setOpenCategories(prev => {
      const newSet = new Set(prev);
      if (newSet.has(category)) {
        newSet.delete(category);
      } else {
        newSet.add(category);
      }
      return newSet;
    });
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
        <span className="ml-2 text-muted-foreground">Loading leagues...</span>
      </div>
    );
  }

  const totalLeagues = categories.reduce((sum, cat) => sum + cat.leagues.length, 0);

  return (
    <div className="space-y-4">
      {/* Header with stats and bulk actions */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Globe className="w-5 h-5 text-primary" />
          <span className="text-sm text-muted-foreground">
            {selectedLeagues.size} of {totalLeagues} leagues selected
          </span>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={selectAll}
            className="h-8"
          >
            Select All
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={deselectAll}
            className="h-8"
          >
            Clear All
          </Button>
          <Button
            size="sm"
            onClick={handleSave}
            disabled={saving}
            className="h-8"
          >
            {saving ? (
              <Loader2 className="w-4 h-4 animate-spin mr-1" />
            ) : (
              <Check className="w-4 h-4 mr-1" />
            )}
            Save Selection
          </Button>
        </div>
      </div>

      {/* Categories grid */}
      <div className="grid gap-3">
        {categories.map(category => {
          const categorySelected = category.leagues.filter(l => 
            selectedLeagues.has(l.league_key)
          ).length;
          const isOpen = openCategories.has(category.category);
          
          return (
            <Collapsible 
              key={category.category}
              open={isOpen}
              onOpenChange={() => toggleCategoryOpen(category.category)}
            >
              <div className="border border-border rounded-lg overflow-hidden">
                <CollapsibleTrigger className="flex items-center justify-between w-full p-3 bg-muted/30 hover:bg-muted/50 transition-colors">
                  <div className="flex items-center gap-3">
                    <ChevronDown 
                      className={`w-4 h-4 text-muted-foreground transition-transform ${
                        isOpen ? 'transform rotate-180' : ''
                      }`} 
                    />
                    <span className="font-medium">{category.display_name}</span>
                    <span className="text-xs text-muted-foreground">
                      ({categorySelected}/{category.leagues.length})
                    </span>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 text-xs"
                    onClick={(e) => {
                      e.stopPropagation();
                      toggleCategory(category.leagues);
                    }}
                  >
                    {categorySelected === category.leagues.length ? 'Deselect All' : 'Select All'}
                  </Button>
                </CollapsibleTrigger>
                <CollapsibleContent>
                  <div className="p-3 grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2">
                    {category.leagues.map(league => (
                      <div
                        key={league.league_key}
                        className={`flex items-center gap-2 p-2 rounded-md cursor-pointer transition-colors ${
                          selectedLeagues.has(league.league_key)
                            ? 'bg-primary/10 border border-primary/30'
                            : 'bg-muted/20 border border-transparent hover:border-border'
                        }`}
                        onClick={() => toggleLeague(league.league_key)}
                      >
                        <Checkbox
                          id={league.league_key}
                          checked={selectedLeagues.has(league.league_key)}
                          onCheckedChange={() => toggleLeague(league.league_key)}
                        />
                        <Label
                          htmlFor={league.league_key}
                          className="text-sm cursor-pointer flex-1"
                        >
                          {league.display_name}
                        </Label>
                      </div>
                    ))}
                  </div>
                </CollapsibleContent>
              </div>
            </Collapsible>
          );
        })}
      </div>

      {/* Help text */}
      <p className="text-xs text-muted-foreground">
        Select the leagues you want to monitor for trading opportunities. 
        The bot will track live games from enabled leagues and apply your trading parameters.
      </p>
    </div>
  );
}
