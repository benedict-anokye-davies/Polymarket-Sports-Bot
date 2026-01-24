import { LucideIcon } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Card } from '@/components/ui/card';

interface StatCardProps {
  label: string;
  value: string;
  change?: string;
  changeType?: 'positive' | 'negative' | 'neutral';
  icon: LucideIcon;
  iconColor?: 'primary' | 'info' | 'warning' | 'destructive';
}

const iconColorMap = {
  primary: 'bg-primary/10 text-primary',
  info: 'bg-info/10 text-info',
  warning: 'bg-warning/10 text-warning',
  destructive: 'bg-destructive/10 text-destructive',
};

export function StatCard({ 
  label, 
  value, 
  change, 
  changeType = 'neutral',
  icon: Icon, 
  iconColor = 'primary' 
}: StatCardProps) {
  return (
    <Card className="p-5 bg-card border-border card-hover relative overflow-hidden">
      {/* Subtle gradient overlay */}
      <div className="absolute inset-0 bg-gradient-to-br from-transparent via-transparent to-muted/20 pointer-events-none" />
      
      <div className="relative flex items-start justify-between">
        <div className="space-y-2">
          <p className="text-xs uppercase tracking-wider text-muted-foreground font-medium">
            {label}
          </p>
          <p className="text-2xl font-semibold font-mono-numbers text-foreground">
            {value}
          </p>
          {change && (
            <p className={cn(
              'text-xs font-medium',
              changeType === 'positive' && 'text-profit',
              changeType === 'negative' && 'text-loss',
              changeType === 'neutral' && 'text-muted-foreground'
            )}>
              {change}
            </p>
          )}
        </div>
        
        <div className={cn(
          'w-10 h-10 rounded-lg flex items-center justify-center',
          iconColorMap[iconColor]
        )}>
          <Icon className="w-5 h-5" />
        </div>
      </div>
    </Card>
  );
}
