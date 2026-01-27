/**
 * OnboardingProgress Component (REQ-UX-005)
 * 
 * Visual step indicator for the onboarding wizard with icons,
 * completion status, and estimated time remaining.
 */

import { Check, Circle, CircleDot, Clock } from 'lucide-react';
import { cn } from '@/lib/utils';

/**
 * Step configuration for the onboarding progress indicator.
 */
export interface OnboardingStep {
  id: number;
  title: string;
  description?: string;
  estimatedMinutes?: number;
  icon?: React.ReactNode;
}

interface OnboardingProgressProps {
  currentStep: number;
  totalSteps: number;
  steps?: OnboardingStep[];
  className?: string;
  variant?: 'horizontal' | 'vertical';
  showEstimate?: boolean;
}

/**
 * Default step configuration if not provided.
 */
const DEFAULT_STEPS: OnboardingStep[] = [
  { id: 1, title: 'Welcome', description: 'Introduction', estimatedMinutes: 1 },
  { id: 2, title: 'Connect', description: 'API credentials', estimatedMinutes: 3 },
  { id: 3, title: 'Configure', description: 'Risk settings', estimatedMinutes: 2 },
  { id: 4, title: 'Start', description: 'Begin trading', estimatedMinutes: 1 },
];

/**
 * Calculates estimated time remaining based on current step.
 */
function calculateTimeRemaining(
  currentStep: number,
  steps: OnboardingStep[]
): number {
  return steps
    .filter((step) => step.id >= currentStep)
    .reduce((total, step) => total + (step.estimatedMinutes || 1), 0);
}

/**
 * Horizontal progress bar variant.
 */
function HorizontalProgress({
  currentStep,
  steps,
  showEstimate,
}: {
  currentStep: number;
  steps: OnboardingStep[];
  showEstimate: boolean;
}) {
  const timeRemaining = calculateTimeRemaining(currentStep, steps);
  const progressPercent = ((currentStep - 1) / (steps.length - 1)) * 100;

  return (
    <div className="space-y-4">
      {/* Progress bar */}
      <div className="relative">
        <div className="h-2 bg-muted rounded-full overflow-hidden">
          <div
            className="h-full bg-primary transition-all duration-500 ease-out"
            style={{ width: `${progressPercent}%` }}
          />
        </div>
        
        {/* Step markers */}
        <div className="absolute top-0 left-0 right-0 flex justify-between -translate-y-1/2">
          {steps.map((step) => {
            const isCompleted = step.id < currentStep;
            const isCurrent = step.id === currentStep;
            
            return (
              <div
                key={step.id}
                className={cn(
                  'w-5 h-5 rounded-full flex items-center justify-center transition-all duration-300',
                  isCompleted && 'bg-primary text-primary-foreground',
                  isCurrent && 'bg-primary text-primary-foreground ring-4 ring-primary/20',
                  !isCompleted && !isCurrent && 'bg-muted border-2 border-border'
                )}
              >
                {isCompleted ? (
                  <Check className="w-3 h-3" />
                ) : isCurrent ? (
                  <CircleDot className="w-3 h-3" />
                ) : (
                  <Circle className="w-3 h-3 text-muted-foreground" />
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Step labels */}
      <div className="flex justify-between">
        {steps.map((step) => {
          const isCompleted = step.id < currentStep;
          const isCurrent = step.id === currentStep;
          
          return (
            <div
              key={step.id}
              className={cn(
                'text-center flex-1',
                isCurrent && 'text-primary font-medium',
                isCompleted && 'text-muted-foreground',
                !isCompleted && !isCurrent && 'text-muted-foreground/50'
              )}
            >
              <span className="text-xs">{step.title}</span>
            </div>
          );
        })}
      </div>

      {/* Time estimate */}
      {showEstimate && (
        <div className="flex items-center justify-center gap-1.5 text-xs text-muted-foreground">
          <Clock className="w-3 h-3" />
          <span>About {timeRemaining} min remaining</span>
        </div>
      )}
    </div>
  );
}

/**
 * Vertical progress list variant.
 */
function VerticalProgress({
  currentStep,
  steps,
}: {
  currentStep: number;
  steps: OnboardingStep[];
}) {
  return (
    <div className="space-y-1">
      {steps.map((step, index) => {
        const isCompleted = step.id < currentStep;
        const isCurrent = step.id === currentStep;
        const isLast = index === steps.length - 1;
        
        return (
          <div key={step.id} className="flex gap-3">
            {/* Line and circle */}
            <div className="flex flex-col items-center">
              <div
                className={cn(
                  'w-8 h-8 rounded-full flex items-center justify-center transition-all duration-300 flex-shrink-0',
                  isCompleted && 'bg-primary/10 text-primary',
                  isCurrent && 'bg-primary text-primary-foreground',
                  !isCompleted && !isCurrent && 'bg-muted text-muted-foreground'
                )}
              >
                {isCompleted ? (
                  <Check className="w-4 h-4" />
                ) : (
                  <span className="text-sm font-medium">{step.id}</span>
                )}
              </div>
              {!isLast && (
                <div
                  className={cn(
                    'w-0.5 flex-1 min-h-8 transition-colors duration-300',
                    isCompleted ? 'bg-primary' : 'bg-border'
                  )}
                />
              )}
            </div>
            
            {/* Content */}
            <div className={cn('pb-6', isLast && 'pb-0')}>
              <p
                className={cn(
                  'text-sm font-medium leading-none mt-2',
                  isCurrent && 'text-primary',
                  isCompleted && 'text-foreground',
                  !isCompleted && !isCurrent && 'text-muted-foreground'
                )}
              >
                {step.title}
              </p>
              {step.description && (
                <p className="text-xs text-muted-foreground mt-1">
                  {step.description}
                </p>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

/**
 * OnboardingProgress displays visual step progress for the onboarding wizard.
 * 
 * @example
 * ```tsx
 * <OnboardingProgress
 *   currentStep={2}
 *   totalSteps={4}
 *   variant="horizontal"
 *   showEstimate
 * />
 * ```
 */
export function OnboardingProgress({
  currentStep,
  totalSteps,
  steps,
  className,
  variant = 'horizontal',
  showEstimate = true,
}: OnboardingProgressProps) {
  // Use provided steps or generate default based on totalSteps
  const effectiveSteps = steps || DEFAULT_STEPS.slice(0, totalSteps);
  
  return (
    <div className={cn('w-full', className)}>
      {variant === 'horizontal' ? (
        <HorizontalProgress
          currentStep={currentStep}
          steps={effectiveSteps}
          showEstimate={showEstimate}
        />
      ) : (
        <VerticalProgress
          currentStep={currentStep}
          steps={effectiveSteps}
        />
      )}
    </div>
  );
}

/**
 * Simple step counter display.
 */
export function StepCounter({
  currentStep,
  totalSteps,
  className,
}: {
  currentStep: number;
  totalSteps: number;
  className?: string;
}) {
  return (
    <div className={cn('text-sm text-muted-foreground', className)}>
      Step <span className="text-foreground font-medium">{currentStep}</span> of{' '}
      <span className="text-foreground font-medium">{totalSteps}</span>
    </div>
  );
}

export default OnboardingProgress;
