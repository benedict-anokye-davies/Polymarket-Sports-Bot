import { useState, useEffect } from 'react';
import Joyride, { Step, CallBackProps, STATUS, EVENTS, ACTIONS } from 'react-joyride';
import { useNavigate, useLocation } from 'react-router-dom';

interface AppTourProps {
  run: boolean;
  onComplete: () => void;
  startStep?: number;
}

// Tour steps organized by page/feature
const tourSteps: Step[] = [
  // Welcome
  {
    target: 'body',
    content: (
      <div className="space-y-3">
        <h3 className="text-lg font-bold text-foreground">Welcome to Kalshi Sports Bot!</h3>
        <p className="text-muted-foreground">
          Let me show you around. This bot automates sports betting on Kalshi prediction markets
          using real-time game data and smart entry/exit strategies.
        </p>
        <div className="bg-primary/10 rounded-lg p-3 mt-2">
          <p className="text-sm font-medium text-primary">
            Paper Trading Mode is ON by default - all trades are simulated!
          </p>
        </div>
      </div>
    ),
    placement: 'center',
    disableBeacon: true,
  },
  // Sidebar Navigation
  {
    target: '[data-tour="sidebar"]',
    content: (
      <div className="space-y-2">
        <h3 className="text-lg font-bold text-foreground">Navigation</h3>
        <p className="text-muted-foreground">
          Use the sidebar to navigate between different sections of the app.
        </p>
      </div>
    ),
    placement: 'right',
    disableBeacon: true,
  },
  // Dashboard Stats
  {
    target: '[data-tour="dashboard-stats"]',
    content: (
      <div className="space-y-2">
        <h3 className="text-lg font-bold text-foreground">Your Stats</h3>
        <p className="text-muted-foreground">
          View your portfolio value, active P&L, open positions, and tracked markets at a glance.
          In paper trading mode, these numbers are simulated.
        </p>
      </div>
    ),
    placement: 'bottom',
    disableBeacon: true,
  },
  // Bot Status
  {
    target: '[data-tour="bot-status"]',
    content: (
      <div className="space-y-2">
        <h3 className="text-lg font-bold text-foreground">Bot Status</h3>
        <p className="text-muted-foreground">
          See if your bot is running, how many positions it has, and whether you're in 
          Paper Trading (safe) or Live Trading mode.
        </p>
        <div className="bg-warning/10 rounded-lg p-3 mt-2">
          <p className="text-sm text-warning">
            The paper trading badge means no real money is at risk!
          </p>
        </div>
      </div>
    ),
    placement: 'left',
    disableBeacon: true,
  },
  // Quick Actions
  {
    target: '[data-tour="quick-actions"]',
    content: (
      <div className="space-y-2">
        <h3 className="text-lg font-bold text-foreground">Quick Actions</h3>
        <p className="text-muted-foreground">
          Start or stop the bot, configure settings, and access paper trading controls quickly.
        </p>
      </div>
    ),
    placement: 'top',
    disableBeacon: true,
  },
  // Bot Config Page Intro
  {
    target: '[data-tour="bot-config-link"]',
    content: (
      <div className="space-y-2">
        <h3 className="text-lg font-bold text-foreground">Configure Your Bot</h3>
        <p className="text-muted-foreground">
          Click here to select games you want to trade, set your strategy parameters, 
          and start the bot.
        </p>
        <p className="text-sm text-primary font-medium mt-2">
          Let's go there now!
        </p>
      </div>
    ),
    placement: 'right',
    disableBeacon: true,
  },
];

// Bot config specific steps (shown when on /bot page)
const botConfigSteps: Step[] = [
  {
    target: '[data-tour="sport-selector"]',
    content: (
      <div className="space-y-2">
        <h3 className="text-lg font-bold text-foreground">Select Sport</h3>
        <p className="text-muted-foreground">
          Choose which sport you want to trade. The bot will show available games for that sport.
        </p>
      </div>
    ),
    placement: 'bottom',
    disableBeacon: true,
  },
  {
    target: '[data-tour="games-list"]',
    content: (
      <div className="space-y-2">
        <h3 className="text-lg font-bold text-foreground">Select Games</h3>
        <p className="text-muted-foreground">
          Click on games to select them for trading. You can pick which team to bet on (home or away).
          The bot monitors odds and enters when conditions are right.
        </p>
      </div>
    ),
    placement: 'right',
    disableBeacon: true,
  },
  {
    target: '[data-tour="trading-params"]',
    content: (
      <div className="space-y-2">
        <h3 className="text-lg font-bold text-foreground">Trading Parameters</h3>
        <p className="text-muted-foreground">
          Adjust your strategy settings:
        </p>
        <ul className="text-sm text-muted-foreground list-disc pl-4 space-y-1">
          <li><strong>Probability Drop:</strong> How much odds must drop to trigger entry</li>
          <li><strong>Position Size:</strong> How much to risk per trade</li>
          <li><strong>Take Profit / Stop Loss:</strong> When to exit</li>
        </ul>
      </div>
    ),
    placement: 'left',
    disableBeacon: true,
  },
  {
    target: '[data-tour="simulation-toggle"]',
    content: (
      <div className="space-y-2">
        <h3 className="text-lg font-bold text-foreground">Paper Trading Toggle</h3>
        <p className="text-muted-foreground">
          Keep this ON to test the bot safely without real money. 
          All trades will be simulated and you'll see how the bot would perform.
        </p>
        <div className="bg-success/10 rounded-lg p-3 mt-2">
          <p className="text-sm text-success font-medium">
            Perfect for testing your strategy!
          </p>
        </div>
      </div>
    ),
    placement: 'top',
    disableBeacon: true,
  },
  {
    target: '[data-tour="start-bot"]',
    content: (
      <div className="space-y-2">
        <h3 className="text-lg font-bold text-foreground">Start the Bot!</h3>
        <p className="text-muted-foreground">
          Once you've selected games and configured parameters, click here to start the bot.
          In paper trading mode, it will simulate trades and show you results.
        </p>
        <div className="bg-primary/10 rounded-lg p-3 mt-2">
          <p className="text-sm text-primary font-medium">
            Ready to try it? Select a game and start paper trading!
          </p>
        </div>
      </div>
    ),
    placement: 'top',
    disableBeacon: true,
  },
];

export function AppTour({ run, onComplete, startStep = 0 }: AppTourProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const [stepIndex, setStepIndex] = useState(startStep);
  const [steps, setSteps] = useState<Step[]>(tourSteps);

  // Update steps based on current page
  useEffect(() => {
    if (location.pathname === '/bot') {
      setSteps(botConfigSteps);
      setStepIndex(0);
    } else if (location.pathname === '/dashboard') {
      setSteps(tourSteps);
    }
  }, [location.pathname]);

  const handleJoyrideCallback = (data: CallBackProps) => {
    const { action, index, status, type } = data;

    // Tour finished or skipped
    if (status === STATUS.FINISHED || status === STATUS.SKIPPED) {
      onComplete();
      return;
    }

    // Handle step navigation
    if (type === EVENTS.STEP_AFTER) {
      // Check if we need to navigate to bot config page
      if (location.pathname === '/dashboard' && index === tourSteps.length - 1) {
        navigate('/bot');
        return;
      }
      setStepIndex(index + 1);
    }

    // Handle back button
    if (type === EVENTS.STEP_BEFORE && action === ACTIONS.PREV) {
      setStepIndex(index - 1);
    }
  };

  return (
    <Joyride
      steps={steps}
      run={run}
      stepIndex={stepIndex}
      continuous
      showSkipButton
      showProgress
      disableScrolling={false}
      callback={handleJoyrideCallback}
      styles={{
        options: {
          primaryColor: 'hsl(var(--primary))',
          backgroundColor: 'hsl(var(--card))',
          textColor: 'hsl(var(--foreground))',
          arrowColor: 'hsl(var(--card))',
          overlayColor: 'rgba(0, 0, 0, 0.7)',
          zIndex: 10000,
        },
        tooltip: {
          borderRadius: '12px',
          padding: '20px',
        },
        buttonNext: {
          backgroundColor: 'hsl(var(--primary))',
          borderRadius: '8px',
          padding: '8px 16px',
        },
        buttonBack: {
          color: 'hsl(var(--muted-foreground))',
          marginRight: '8px',
        },
        buttonSkip: {
          color: 'hsl(var(--muted-foreground))',
        },
        spotlight: {
          borderRadius: '8px',
        },
      }}
      locale={{
        back: 'Back',
        close: 'Close',
        last: 'Done!',
        next: 'Next',
        skip: 'Skip Tour',
      }}
    />
  );
}

export default AppTour;
