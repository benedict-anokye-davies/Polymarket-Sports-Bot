import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Eye, EyeOff, TrendingUp, Check, X } from 'lucide-react';
import { motion } from 'framer-motion';
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Checkbox } from '@/components/ui/checkbox';
import { cn } from '@/lib/utils';

interface PasswordStrength {
  hasMinLength: boolean;
  hasUppercase: boolean;
  hasLowercase: boolean;
  hasNumber: boolean;
  hasSpecial: boolean;
}

export default function Register() {
  const navigate = useNavigate();
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [acceptTerms, setAcceptTerms] = useState(false);

  const checkPasswordStrength = (pwd: string): PasswordStrength => ({
    hasMinLength: pwd.length >= 8,
    hasUppercase: /[A-Z]/.test(pwd),
    hasLowercase: /[a-z]/.test(pwd),
    hasNumber: /[0-9]/.test(pwd),
    hasSpecial: /[!@#$%^&*(),.?":{}|<>]/.test(pwd),
  });

  const passwordStrength = checkPasswordStrength(password);
  const strengthScore = Object.values(passwordStrength).filter(Boolean).length;
  const passwordsMatch = password === confirmPassword && password.length > 0;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (strengthScore < 4 || !passwordsMatch || !acceptTerms) return;
    
    setIsLoading(true);
    // Simulate registration
    await new Promise(resolve => setTimeout(resolve, 1500));
    setIsLoading(false);
    navigate('/onboarding');
  };

  const StrengthIndicator = ({ met, label }: { met: boolean; label: string }) => (
    <div className="flex items-center gap-2 text-xs">
      {met ? (
        <Check className="w-3 h-3 text-primary" />
      ) : (
        <X className="w-3 h-3 text-muted-foreground" />
      )}
      <span className={cn(met ? 'text-primary' : 'text-muted-foreground')}>{label}</span>
    </div>
  );

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4 relative overflow-hidden">
      {/* Background gradient */}
      <div className="absolute inset-0 bg-gradient-to-br from-primary/5 via-transparent to-primary/10 pointer-events-none" />
      <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-primary/5 rounded-full blur-3xl" />
      <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-primary/5 rounded-full blur-3xl" />

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="w-full max-w-md"
      >
        <Card className="bg-card/80 backdrop-blur border-border shadow-2xl">
          <CardHeader className="text-center pb-2">
            <div className="w-14 h-14 rounded-xl bg-primary/10 flex items-center justify-center mx-auto mb-4">
              <TrendingUp className="w-7 h-7 text-primary" />
            </div>
            <CardTitle className="text-2xl text-foreground">Create account</CardTitle>
            <CardDescription className="text-muted-foreground">
              Start your automated trading journey
            </CardDescription>
          </CardHeader>
          
          <form onSubmit={handleSubmit}>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="username" className="text-muted-foreground">Username</Label>
                <Input
                  id="username"
                  type="text"
                  placeholder="johndoe"
                  className="bg-muted border-border"
                  required
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="email" className="text-muted-foreground">Email</Label>
                <Input
                  id="email"
                  type="email"
                  placeholder="trader@example.com"
                  className="bg-muted border-border"
                  required
                />
              </div>
              
              <div className="space-y-2">
                <Label htmlFor="password" className="text-muted-foreground">Password</Label>
                <div className="relative">
                  <Input
                    id="password"
                    type={showPassword ? 'text' : 'password'}
                    placeholder="Create a strong password"
                    className="bg-muted border-border pr-10"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="absolute right-1 top-1/2 -translate-y-1/2 h-7 w-7"
                    onClick={() => setShowPassword(!showPassword)}
                  >
                    {showPassword ? (
                      <EyeOff className="w-4 h-4 text-muted-foreground" />
                    ) : (
                      <Eye className="w-4 h-4 text-muted-foreground" />
                    )}
                  </Button>
                </div>
                
                {/* Password Strength Bar */}
                {password && (
                  <div className="space-y-2 mt-2">
                    <div className="flex gap-1">
                      {[1, 2, 3, 4, 5].map((level) => (
                        <div
                          key={level}
                          className={cn(
                            'h-1 flex-1 rounded-full transition-colors',
                            level <= strengthScore
                              ? strengthScore <= 2 ? 'bg-destructive' 
                              : strengthScore <= 3 ? 'bg-warning'
                              : 'bg-primary'
                              : 'bg-muted'
                          )}
                        />
                      ))}
                    </div>
                    <div className="grid grid-cols-2 gap-1">
                      <StrengthIndicator met={passwordStrength.hasMinLength} label="8+ characters" />
                      <StrengthIndicator met={passwordStrength.hasUppercase} label="Uppercase" />
                      <StrengthIndicator met={passwordStrength.hasLowercase} label="Lowercase" />
                      <StrengthIndicator met={passwordStrength.hasNumber} label="Number" />
                      <StrengthIndicator met={passwordStrength.hasSpecial} label="Special char" />
                    </div>
                  </div>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="confirmPassword" className="text-muted-foreground">Confirm Password</Label>
                <div className="relative">
                  <Input
                    id="confirmPassword"
                    type={showConfirmPassword ? 'text' : 'password'}
                    placeholder="Confirm your password"
                    className={cn(
                      'bg-muted border-border pr-10',
                      confirmPassword && (passwordsMatch ? 'border-primary' : 'border-destructive')
                    )}
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    required
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="absolute right-1 top-1/2 -translate-y-1/2 h-7 w-7"
                    onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                  >
                    {showConfirmPassword ? (
                      <EyeOff className="w-4 h-4 text-muted-foreground" />
                    ) : (
                      <Eye className="w-4 h-4 text-muted-foreground" />
                    )}
                  </Button>
                </div>
                {confirmPassword && !passwordsMatch && (
                  <p className="text-xs text-destructive">Passwords do not match</p>
                )}
              </div>

              <div className="flex items-start space-x-2">
                <Checkbox 
                  id="terms" 
                  checked={acceptTerms}
                  onCheckedChange={(checked) => setAcceptTerms(checked as boolean)}
                />
                <label
                  htmlFor="terms"
                  className="text-sm text-muted-foreground cursor-pointer leading-tight"
                >
                  I agree to the{' '}
                  <Link to="/terms" className="text-primary hover:underline">Terms of Service</Link>
                  {' '}and{' '}
                  <Link to="/privacy" className="text-primary hover:underline">Privacy Policy</Link>
                </label>
              </div>
            </CardContent>

            <CardFooter className="flex flex-col gap-4">
              <Button 
                type="submit" 
                className="w-full bg-primary hover:bg-primary/90"
                disabled={isLoading || strengthScore < 4 || !passwordsMatch || !acceptTerms}
              >
                {isLoading ? 'Creating account...' : 'Create Account'}
              </Button>
              
              <p className="text-sm text-muted-foreground text-center">
                Already have an account?{' '}
                <Link 
                  to="/login" 
                  className="text-primary hover:text-primary/80 transition-colors"
                >
                  Sign in
                </Link>
              </p>
            </CardFooter>
          </form>
        </Card>
      </motion.div>
    </div>
  );
}
