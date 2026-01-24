import { useMemo } from 'react';
import { 
  AreaChart, 
  Area, 
  XAxis, 
  YAxis, 
  Tooltip, 
  ResponsiveContainer,
  CartesianGrid 
} from 'recharts';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';

// Generate mock price data
const generateMockData = () => {
  const data = [];
  const now = new Date();
  let price = 0.65;
  
  for (let i = 24; i >= 0; i--) {
    const time = new Date(now.getTime() - i * 60 * 60 * 1000);
    price = Math.max(0.1, Math.min(0.9, price + (Math.random() - 0.48) * 0.05));
    data.push({
      time: time.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }),
      probability: parseFloat(price.toFixed(3)),
    });
  }
  return data;
};

export function PriceChart() {
  const data = useMemo(() => generateMockData(), []);

  return (
    <Card className="bg-card border-border">
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-medium text-foreground">
          Win Probability History
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-0">
        <div className="h-[300px]">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="probabilityGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="hsl(160, 84%, 39%)" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="hsl(160, 84%, 39%)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid 
                strokeDasharray="3 3" 
                stroke="hsl(0, 0%, 15%)" 
                vertical={false} 
              />
              <XAxis 
                dataKey="time" 
                stroke="hsl(0, 0%, 40%)"
                tick={{ fill: 'hsl(0, 0%, 50%)', fontSize: 11 }}
                axisLine={{ stroke: 'hsl(0, 0%, 15%)' }}
                tickLine={false}
                interval="preserveStartEnd"
              />
              <YAxis 
                domain={[0, 1]}
                stroke="hsl(0, 0%, 40%)"
                tick={{ fill: 'hsl(0, 0%, 50%)', fontSize: 11 }}
                axisLine={{ stroke: 'hsl(0, 0%, 15%)' }}
                tickLine={false}
                tickFormatter={(value) => `${(value * 100).toFixed(0)}%`}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'hsl(0, 0%, 9%)',
                  border: '1px solid hsl(0, 0%, 20%)',
                  borderRadius: '8px',
                  boxShadow: '0 4px 12px rgba(0, 0, 0, 0.5)',
                }}
                labelStyle={{ color: 'hsl(0, 0%, 70%)' }}
                itemStyle={{ color: 'hsl(160, 84%, 50%)' }}
                formatter={(value: number) => [`${(value * 100).toFixed(1)}%`, 'Probability']}
              />
              <Area
                type="monotone"
                dataKey="probability"
                stroke="hsl(160, 84%, 39%)"
                strokeWidth={2}
                fill="url(#probabilityGradient)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}
