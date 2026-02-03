/**
 * Production-safe logger utility.
 * In production, only errors and warnings are logged.
 * Set VITE_DEBUG=true in environment to enable all logs.
 */

const isDebug = import.meta.env.VITE_DEBUG === 'true' || import.meta.env.DEV;

export const logger = {
  /**
   * Debug-level logging (only in development or when VITE_DEBUG=true)
   */
  debug: (...args: unknown[]) => {
    if (isDebug) {
      if (import.meta.env.DEV) {
        console.log(...args);
      }
    }
  },

  /**
   * Info-level logging (only in development or when VITE_DEBUG=true)
   */
  info: (...args: unknown[]) => {
    if (isDebug) {
      console.info(...args);
    }
  },

  /**
   * Warning-level logging (always logged)
   */
  warn: (...args: unknown[]) => {
    console.warn(...args);
  },

  /**
   * Error-level logging (always logged)
   */
  error: (...args: unknown[]) => {
    console.error(...args);
  },
};

export default logger;
