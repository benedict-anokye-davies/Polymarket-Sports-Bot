/**
 * WebSocket Hook for Real-Time Trading Updates (REQ-UX-002)
 *
 * Provides a React hook for connecting to the trading bot's WebSocket endpoint.
 * Handles authentication, automatic reconnection, and event dispatching.
 */

import { useEffect, useRef, useCallback, useState } from 'react';
import { useAppStore } from '@/stores/useAppStore';

const API_BASE_URL = import.meta.env.VITE_API_URL?.trim() || 'https://polymarket-sports-bot-production.up.railway.app/api/v1';

// Convert HTTP URL to WebSocket URL
const getWebSocketUrl = (): string => {
  const base = API_BASE_URL.replace(/^http/, 'ws');
  return `${base}/ws`;
};

export enum WebSocketEventType {
  // Trading events
  TRADE_EXECUTED = 'trade_executed',
  POSITION_OPENED = 'position_opened',
  POSITION_CLOSED = 'position_closed',
  POSITION_UPDATED = 'position_updated',
  ORDER_PLACED = 'order_placed',
  ORDER_FILLED = 'order_filled',
  ORDER_CANCELLED = 'order_cancelled',

  // Bot status events
  BOT_STARTED = 'bot_started',
  BOT_STOPPED = 'bot_stopped',
  BOT_ERROR = 'bot_error',
  BOT_STATUS_CHANGED = 'bot_status_changed',

  // Market events
  MARKET_ALERT = 'market_alert',
  PRICE_UPDATE = 'price_update',

  // System events
  CONNECTION_ESTABLISHED = 'connection_established',
  HEARTBEAT = 'heartbeat',
  ERROR = 'error',

  // Risk events
  DAILY_LOSS_WARNING = 'daily_loss_warning',
  KILL_SWITCH_ACTIVATED = 'kill_switch_activated',
}

export interface WebSocketMessage {
  event: WebSocketEventType;
  data: Record<string, unknown>;
  timestamp: string;
  correlation_id?: string;
}

export interface TradeExecutedData {
  trade_id: string;
  market_id: string;
  side: 'BUY' | 'SELL';
  size: number;
  price: number;
  filled_at: string;
}

export interface PositionData {
  position_id: string;
  market_id: string;
  side: 'YES' | 'NO';
  entry_price: number;
  current_price: number;
  size: number;
  unrealized_pnl: number;
  realized_pnl?: number;
}

export interface BotStatusData {
  status: 'running' | 'stopped' | 'paused' | 'error';
  message?: string;
  tracked_games?: number;
  active_positions?: number;
}

export interface UseWebSocketOptions {
  /** Enable/disable the WebSocket connection */
  enabled?: boolean;
  /** Callback for trade executed events */
  onTradeExecuted?: (data: TradeExecutedData) => void;
  /** Callback for position opened events */
  onPositionOpened?: (data: PositionData) => void;
  /** Callback for position closed events */
  onPositionClosed?: (data: PositionData) => void;
  /** Callback for position updated events */
  onPositionUpdated?: (data: PositionData) => void;
  /** Callback for bot status changes */
  onBotStatusChanged?: (data: BotStatusData) => void;
  /** Callback for bot errors */
  onBotError?: (data: { error: string; details?: string }) => void;
  /** Callback for any error */
  onError?: (error: Error) => void;
  /** Callback when connection is established */
  onConnected?: () => void;
  /** Callback when connection is lost */
  onDisconnected?: () => void;
}

const MAX_RECONNECT_ATTEMPTS = 10;
const BASE_RECONNECT_DELAY_MS = 1000;
const MAX_RECONNECT_DELAY_MS = 30000;
const HEARTBEAT_INTERVAL_MS = 30000;
const HEARTBEAT_TIMEOUT_MS = 45000;

export function useWebSocket(options: UseWebSocketOptions = {}) {
  const {
    enabled = true,
    onTradeExecuted,
    onPositionOpened,
    onPositionClosed,
    onPositionUpdated,
    onBotStatusChanged,
    onBotError,
    onError,
    onConnected,
    onDisconnected,
  } = options;

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const heartbeatIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const heartbeatTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttemptsRef = useRef(0);

  const [isConnected, setIsConnected] = useState(false);
  const [connectionError, setConnectionError] = useState<string | null>(null);

  const { setWsConnected } = useAppStore();

  // Store callbacks in refs to prevent reconnection on callback identity change
  const callbacksRef = useRef({
    onTradeExecuted,
    onPositionOpened,
    onPositionClosed,
    onPositionUpdated,
    onBotStatusChanged,
    onBotError,
    onError,
    onConnected,
    onDisconnected,
  });
  callbacksRef.current = {
    onTradeExecuted,
    onPositionOpened,
    onPositionClosed,
    onPositionUpdated,
    onBotStatusChanged,
    onBotError,
    onError,
    onConnected,
    onDisconnected,
  };

  const getToken = useCallback((): string | null => {
    return localStorage.getItem('auth_token');
  }, []);

  const clearTimers = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    if (heartbeatIntervalRef.current) {
      clearInterval(heartbeatIntervalRef.current);
      heartbeatIntervalRef.current = null;
    }
    if (heartbeatTimeoutRef.current) {
      clearTimeout(heartbeatTimeoutRef.current);
      heartbeatTimeoutRef.current = null;
    }
  }, []);

  const resetHeartbeatTimeout = useCallback(() => {
    if (heartbeatTimeoutRef.current) {
      clearTimeout(heartbeatTimeoutRef.current);
    }
    heartbeatTimeoutRef.current = setTimeout(() => {
      console.warn('[WS] Heartbeat timeout - connection stale, reconnecting');
      wsRef.current?.close();
    }, HEARTBEAT_TIMEOUT_MS);
  }, []);

  const startHeartbeat = useCallback(() => {
    if (heartbeatIntervalRef.current) {
      clearInterval(heartbeatIntervalRef.current);
    }
    heartbeatIntervalRef.current = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ action: 'ping' }));
      }
    }, HEARTBEAT_INTERVAL_MS);
  }, []);

  const handleMessage = useCallback((event: MessageEvent) => {
    try {
      const message: WebSocketMessage = JSON.parse(event.data);
      const { event: eventType, data } = message;

      // Reset heartbeat timeout on any message
      resetHeartbeatTimeout();

      switch (eventType) {
        case WebSocketEventType.CONNECTION_ESTABLISHED:
          console.log('[WS] Connection established:', data);
          break;

        case WebSocketEventType.HEARTBEAT:
          // Heartbeat received, timeout already reset
          break;

        case WebSocketEventType.TRADE_EXECUTED:
          callbacksRef.current.onTradeExecuted?.(data as unknown as TradeExecutedData);
          break;

        case WebSocketEventType.POSITION_OPENED:
          callbacksRef.current.onPositionOpened?.(data as unknown as PositionData);
          break;

        case WebSocketEventType.POSITION_CLOSED:
          callbacksRef.current.onPositionClosed?.(data as unknown as PositionData);
          break;

        case WebSocketEventType.POSITION_UPDATED:
          callbacksRef.current.onPositionUpdated?.(data as unknown as PositionData);
          break;

        case WebSocketEventType.BOT_STARTED:
        case WebSocketEventType.BOT_STOPPED:
        case WebSocketEventType.BOT_STATUS_CHANGED:
          callbacksRef.current.onBotStatusChanged?.(data as unknown as BotStatusData);
          break;

        case WebSocketEventType.BOT_ERROR:
          callbacksRef.current.onBotError?.(data as unknown as { error: string; details?: string });
          break;

        case WebSocketEventType.ERROR:
          console.error('[WS] Server error:', data);
          callbacksRef.current.onError?.(new Error((data as { message?: string }).message || 'Unknown error'));
          break;

        case WebSocketEventType.DAILY_LOSS_WARNING:
        case WebSocketEventType.KILL_SWITCH_ACTIVATED:
          // These are risk alerts - could add specific handlers
          console.warn('[WS] Risk alert:', eventType, data);
          break;

        default:
          console.log('[WS] Unhandled event:', eventType, data);
      }
    } catch (err) {
      console.error('[WS] Failed to parse message:', err);
    }
  }, [resetHeartbeatTimeout]);

  const connect = useCallback(() => {
    const token = getToken();
    if (!token) {
      console.warn('[WS] No auth token available, skipping connection');
      return;
    }

    // Close existing connection
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    clearTimers();

    try {
      const wsUrl = `${getWebSocketUrl()}?token=${encodeURIComponent(token)}`;
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('[WS] Connected');
        setIsConnected(true);
        setConnectionError(null);
        setWsConnected(true);
        reconnectAttemptsRef.current = 0;
        startHeartbeat();
        resetHeartbeatTimeout();
        callbacksRef.current.onConnected?.();
      };

      ws.onmessage = handleMessage;

      ws.onerror = (error) => {
        console.error('[WS] Error:', error);
        setConnectionError('WebSocket connection error');
        callbacksRef.current.onError?.(new Error('WebSocket connection error'));
      };

      ws.onclose = (event) => {
        console.log('[WS] Disconnected:', event.code, event.reason);
        setIsConnected(false);
        setWsConnected(false);
        clearTimers();
        callbacksRef.current.onDisconnected?.();

        // Attempt reconnection if not a clean close
        if (event.code !== 1000 && enabled) {
          const attempts = reconnectAttemptsRef.current;
          if (attempts < MAX_RECONNECT_ATTEMPTS) {
            const delay = Math.min(
              BASE_RECONNECT_DELAY_MS * Math.pow(2, attempts),
              MAX_RECONNECT_DELAY_MS
            );
            console.log(`[WS] Reconnecting in ${delay}ms (attempt ${attempts + 1}/${MAX_RECONNECT_ATTEMPTS})`);
            reconnectAttemptsRef.current = attempts + 1;
            reconnectTimeoutRef.current = setTimeout(connect, delay);
          } else {
            console.error('[WS] Max reconnection attempts reached');
            setConnectionError('Unable to connect to server');
          }
        }
      };
    } catch (err) {
      console.error('[WS] Failed to create connection:', err);
      setConnectionError('Failed to create WebSocket connection');
    }
  }, [getToken, enabled, clearTimers, startHeartbeat, resetHeartbeatTimeout, handleMessage, setWsConnected]);

  const disconnect = useCallback(() => {
    clearTimers();
    if (wsRef.current) {
      wsRef.current.close(1000, 'User initiated disconnect');
      wsRef.current = null;
    }
    setIsConnected(false);
    setWsConnected(false);
  }, [clearTimers, setWsConnected]);

  const sendMessage = useCallback((action: string, payload?: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action, ...payload }));
    } else {
      console.warn('[WS] Cannot send message, not connected');
    }
  }, []);

  // Connect/disconnect based on enabled state
  useEffect(() => {
    if (enabled) {
      connect();
    } else {
      disconnect();
    }

    return () => {
      disconnect();
    };
  }, [enabled, connect, disconnect]);

  // Reconnect if token changes
  useEffect(() => {
    const handleStorageChange = (event: StorageEvent) => {
      if (event.key === 'auth_token' && enabled) {
        if (event.newValue) {
          // Token changed, reconnect
          reconnectAttemptsRef.current = 0;
          connect();
        } else {
          // Token removed, disconnect
          disconnect();
        }
      }
    };

    window.addEventListener('storage', handleStorageChange);
    return () => window.removeEventListener('storage', handleStorageChange);
  }, [enabled, connect, disconnect]);

  return {
    isConnected,
    connectionError,
    connect,
    disconnect,
    sendMessage,
  };
}
