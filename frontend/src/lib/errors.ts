/**
 * Actionable Error Messages Utility (REQ-UX-006)
 * 
 * Maps API error codes and messages to user-friendly, actionable messages.
 * Provides specific guidance on how to resolve each error type.
 */

/**
 * Structure for actionable error information.
 */
export interface ActionableError {
  title: string;
  message: string;
  action?: string;
  actionLink?: string;
  retryable: boolean;
  severity: 'info' | 'warning' | 'error';
}

/**
 * Default error for unknown error types.
 */
const DEFAULT_ERROR: ActionableError = {
  title: 'Something went wrong',
  message: 'An unexpected error occurred. Please try again.',
  action: 'Retry the operation',
  retryable: true,
  severity: 'error',
};

/**
 * Map of HTTP status codes to actionable errors.
 */
const HTTP_STATUS_ERRORS: Record<number, ActionableError> = {
  400: {
    title: 'Invalid Request',
    message: 'The request was invalid. Please check your input and try again.',
    action: 'Review your input fields',
    retryable: true,
    severity: 'warning',
  },
  401: {
    title: 'Session Expired',
    message: 'Your session has expired. Please log in again to continue.',
    action: 'Log in again',
    actionLink: '/login',
    retryable: false,
    severity: 'warning',
  },
  403: {
    title: 'Access Denied',
    message: 'You do not have permission to perform this action.',
    action: 'Contact support if you believe this is an error',
    retryable: false,
    severity: 'error',
  },
  404: {
    title: 'Not Found',
    message: 'The requested resource could not be found.',
    action: 'Check that the item exists',
    retryable: false,
    severity: 'warning',
  },
  408: {
    title: 'Request Timeout',
    message: 'The server took too long to respond. Please try again.',
    action: 'Retry the operation',
    retryable: true,
    severity: 'warning',
  },
  409: {
    title: 'Conflict',
    message: 'This action conflicts with existing data. Please refresh and try again.',
    action: 'Refresh the page',
    retryable: true,
    severity: 'warning',
  },
  422: {
    title: 'Validation Error',
    message: 'The provided data is invalid. Please check the fields and try again.',
    action: 'Fix the highlighted fields',
    retryable: true,
    severity: 'warning',
  },
  429: {
    title: 'Too Many Requests',
    message: 'You are making requests too quickly. Please wait a moment before trying again.',
    action: 'Wait 30 seconds and retry',
    retryable: true,
    severity: 'warning',
  },
  500: {
    title: 'Server Error',
    message: 'An internal server error occurred. Our team has been notified.',
    action: 'Try again in a few minutes',
    retryable: true,
    severity: 'error',
  },
  502: {
    title: 'Service Unavailable',
    message: 'The server is temporarily unavailable. Please try again shortly.',
    action: 'Try again in a few minutes',
    retryable: true,
    severity: 'error',
  },
  503: {
    title: 'Service Unavailable',
    message: 'The service is undergoing maintenance. Please try again later.',
    action: 'Try again in a few minutes',
    retryable: true,
    severity: 'error',
  },
  504: {
    title: 'Gateway Timeout',
    message: 'The server connection timed out. Please try again.',
    action: 'Retry the operation',
    retryable: true,
    severity: 'warning',
  },
};

/**
 * Map of specific error codes/messages to actionable errors.
 * These take precedence over generic HTTP status errors.
 */
const SPECIFIC_ERRORS: Record<string, ActionableError> = {
  // Authentication errors
  INVALID_CREDENTIALS: {
    title: 'Invalid Credentials',
    message: 'The username or password you entered is incorrect.',
    action: 'Double-check your credentials',
    retryable: true,
    severity: 'warning',
  },
  TOKEN_EXPIRED: {
    title: 'Session Expired',
    message: 'Your session has expired for security reasons.',
    action: 'Log in again',
    actionLink: '/login',
    retryable: false,
    severity: 'warning',
  },
  ACCOUNT_LOCKED: {
    title: 'Account Locked',
    message: 'Your account has been locked due to too many failed login attempts.',
    action: 'Wait 15 minutes or reset your password',
    retryable: false,
    severity: 'error',
  },
  
  // Trading platform errors
  POLYMARKET_CONNECTION_FAILED: {
    title: 'Connection Failed',
    message: 'Could not connect to Polymarket. Please verify your private key and funder address.',
    action: 'Check your API credentials in Settings',
    actionLink: '/settings',
    retryable: true,
    severity: 'error',
  },
  KALSHI_CONNECTION_FAILED: {
    title: 'Connection Failed',
    message: 'Could not connect to Kalshi. Please verify your API key and secret.',
    action: 'Check your API credentials in Settings',
    actionLink: '/settings',
    retryable: true,
    severity: 'error',
  },
  INSUFFICIENT_BALANCE: {
    title: 'Insufficient Balance',
    message: 'Your account does not have enough funds to execute this trade.',
    action: 'Deposit more funds to your trading account',
    retryable: false,
    severity: 'error',
  },
  ORDER_REJECTED: {
    title: 'Order Rejected',
    message: 'The exchange rejected your order. This may be due to market conditions.',
    action: 'Check order parameters and try again',
    retryable: true,
    severity: 'warning',
  },
  MARKET_CLOSED: {
    title: 'Market Closed',
    message: 'This market is no longer accepting orders.',
    retryable: false,
    severity: 'info',
  },
  POSITION_LIMIT_EXCEEDED: {
    title: 'Position Limit Exceeded',
    message: 'You have reached the maximum number of concurrent positions.',
    action: 'Close existing positions or increase your limit in Settings',
    actionLink: '/settings',
    retryable: false,
    severity: 'warning',
  },
  DAILY_LOSS_LIMIT_REACHED: {
    title: 'Daily Loss Limit Reached',
    message: 'Trading paused because you reached your daily loss limit.',
    action: 'Wait until tomorrow or adjust your limit in Settings',
    actionLink: '/settings',
    retryable: false,
    severity: 'warning',
  },
  
  // ESPN/Data errors
  ESPN_DATA_UNAVAILABLE: {
    title: 'Game Data Unavailable',
    message: 'Could not fetch live game data from ESPN. Retrying automatically.',
    retryable: true,
    severity: 'warning',
  },
  MARKET_NOT_MATCHED: {
    title: 'Market Not Matched',
    message: 'Could not match this game to a Polymarket market.',
    action: 'The market may not exist yet',
    retryable: true,
    severity: 'info',
  },
  
  // WebSocket errors
  WS_CONNECTION_LOST: {
    title: 'Connection Lost',
    message: 'Real-time connection was interrupted. Reconnecting automatically.',
    retryable: true,
    severity: 'warning',
  },
  WS_AUTH_FAILED: {
    title: 'WebSocket Auth Failed',
    message: 'Could not authenticate real-time connection.',
    action: 'Refresh the page',
    retryable: true,
    severity: 'warning',
  },
  
  // Network errors
  NETWORK_ERROR: {
    title: 'Network Error',
    message: 'Could not connect to the server. Please check your internet connection.',
    action: 'Check your internet connection',
    retryable: true,
    severity: 'error',
  },
  TIMEOUT: {
    title: 'Request Timeout',
    message: 'The request took too long. Please try again.',
    action: 'Retry the operation',
    retryable: true,
    severity: 'warning',
  },
  
  // Onboarding errors
  ONBOARDING_INCOMPLETE: {
    title: 'Setup Incomplete',
    message: 'Please complete the onboarding process to access this feature.',
    action: 'Complete onboarding',
    actionLink: '/onboarding',
    retryable: false,
    severity: 'info',
  },
  CREDENTIALS_NOT_CONFIGURED: {
    title: 'Credentials Not Configured',
    message: 'Trading platform credentials have not been set up yet.',
    action: 'Configure credentials in Settings',
    actionLink: '/settings',
    retryable: false,
    severity: 'info',
  },
};

/**
 * Extracts error code from various error formats.
 * Handles API responses, Error objects, and string messages.
 */
function extractErrorCode(error: unknown): string | null {
  if (typeof error === 'string') {
    return error.toUpperCase().replace(/\s+/g, '_');
  }
  
  if (error && typeof error === 'object') {
    const errorObj = error as Record<string, unknown>;
    
    // Check for common error code fields
    if (typeof errorObj.code === 'string') {
      return errorObj.code.toUpperCase();
    }
    if (typeof errorObj.error_code === 'string') {
      return errorObj.error_code.toUpperCase();
    }
    if (typeof errorObj.errorCode === 'string') {
      return errorObj.errorCode.toUpperCase();
    }
    
    // Extract from detail field (FastAPI validation errors)
    if (typeof errorObj.detail === 'string') {
      // Try to find known error patterns
      const detail = errorObj.detail.toLowerCase();
      if (detail.includes('insufficient') && detail.includes('balance')) {
        return 'INSUFFICIENT_BALANCE';
      }
      if (detail.includes('session') && detail.includes('expired')) {
        return 'TOKEN_EXPIRED';
      }
      if (detail.includes('credentials')) {
        return 'INVALID_CREDENTIALS';
      }
    }
  }
  
  return null;
}

/**
 * Extracts HTTP status code from error response.
 */
function extractStatusCode(error: unknown): number | null {
  if (error && typeof error === 'object') {
    const errorObj = error as Record<string, unknown>;
    
    if (typeof errorObj.status === 'number') {
      return errorObj.status;
    }
    if (typeof errorObj.statusCode === 'number') {
      return errorObj.statusCode;
    }
    if (errorObj.response && typeof errorObj.response === 'object') {
      const response = errorObj.response as Record<string, unknown>;
      if (typeof response.status === 'number') {
        return response.status;
      }
    }
  }
  
  return null;
}

/**
 * Extracts error message from various error formats.
 */
function extractErrorMessage(error: unknown): string | null {
  if (typeof error === 'string') {
    return error;
  }
  
  if (error instanceof Error) {
    return error.message;
  }
  
  if (error && typeof error === 'object') {
    const errorObj = error as Record<string, unknown>;
    
    if (typeof errorObj.message === 'string') {
      return errorObj.message;
    }
    if (typeof errorObj.detail === 'string') {
      return errorObj.detail;
    }
    if (Array.isArray(errorObj.detail)) {
      // FastAPI validation errors
      const messages = errorObj.detail.map((d: Record<string, unknown>) => d.msg);
      return messages.join(', ');
    }
  }
  
  return null;
}

/**
 * Maps an error to an actionable error message.
 * 
 * Priority order:
 * 1. Specific error code match
 * 2. HTTP status code match
 * 3. Default error
 * 
 * @param error - The error to map (can be Error, API response, or string)
 * @returns Actionable error information with user guidance
 */
export function mapToActionableError(error: unknown): ActionableError {
  // Check for network/fetch errors
  if (error instanceof TypeError && error.message.includes('fetch')) {
    return SPECIFIC_ERRORS.NETWORK_ERROR;
  }
  
  // Try to match specific error code first
  const errorCode = extractErrorCode(error);
  if (errorCode && SPECIFIC_ERRORS[errorCode]) {
    return SPECIFIC_ERRORS[errorCode];
  }
  
  // Try to match HTTP status code
  const statusCode = extractStatusCode(error);
  if (statusCode && HTTP_STATUS_ERRORS[statusCode]) {
    const baseError = HTTP_STATUS_ERRORS[statusCode];
    const customMessage = extractErrorMessage(error);
    
    // Use custom message if available, but keep the actionable info
    if (customMessage && customMessage !== baseError.message) {
      return {
        ...baseError,
        message: customMessage,
      };
    }
    
    return baseError;
  }
  
  // Return default with extracted message if available
  const message = extractErrorMessage(error);
  if (message) {
    return {
      ...DEFAULT_ERROR,
      message,
    };
  }
  
  return DEFAULT_ERROR;
}

/**
 * Formats an error for display in a toast notification.
 * 
 * @param error - The error to format
 * @returns Object suitable for toast({ ... })
 */
export function formatErrorForToast(error: unknown): {
  title: string;
  description: string;
  variant: 'default' | 'destructive';
} {
  const actionable = mapToActionableError(error);
  
  return {
    title: actionable.title,
    description: actionable.action
      ? `${actionable.message} ${actionable.action}.`
      : actionable.message,
    variant: actionable.severity === 'error' ? 'destructive' : 'default',
  };
}

/**
 * Hook-friendly error handler that returns display-ready error info.
 * 
 * @example
 * ```tsx
 * const { showError } = useErrorHandler();
 * try {
 *   await api.doSomething();
 * } catch (error) {
 *   showError(error);
 * }
 * ```
 */
export function createErrorHandler(
  toastFn: (options: { title: string; description: string; variant: 'default' | 'destructive' }) => void
) {
  return {
    showError: (error: unknown) => {
      const formatted = formatErrorForToast(error);
      toastFn(formatted);
    },
    getActionableError: (error: unknown) => mapToActionableError(error),
  };
}

/**
 * Checks if an error is retryable.
 */
export function isRetryableError(error: unknown): boolean {
  const actionable = mapToActionableError(error);
  return actionable.retryable;
}

/**
 * Gets the suggested action link for an error, if any.
 */
export function getErrorActionLink(error: unknown): string | undefined {
  const actionable = mapToActionableError(error);
  return actionable.actionLink;
}
