import { useEffect, useRef, useCallback, useState } from 'react';
import apiClient from '@/api/client';
import { useAppStore } from '@/stores/useAppStore';

interface SSEEvent {
  type: 'status' | 'games' | 'positions' | 'heartbeat' | 'error';
  data: unknown;
}

interface UseSSEOptions {
  enabled?: boolean;
  onStatus?: (data: StatusData) => void;
  onGames?: (data: GameData[]) => void;
  onPositions?: (data: PositionData[]) => void;
  onError?: (error: Error) => void;
}

interface StatusData {
  state: 'running' | 'stopped';
  tracked_games: number;
  trades_today: number;
  daily_pnl: number;
}

interface GameData {
  id: string;
  home_team: string;
  away_team: string;
  home_score: number;
  away_score: number;
  period: string;
  probability: number;
  sport: string;
}

interface PositionData {
  id: string;
  market: string;
  side: 'YES' | 'NO';
  entry_price: number;
  current_price: number;
  unrealized_pnl: number;
}

const MAX_RECONNECT_ATTEMPTS = 10;
const BASE_RECONNECT_DELAY = 1000;
const HEARTBEAT_TIMEOUT_MS = 45000; // 45 seconds without heartbeat = stale

export function useSSE(options: UseSSEOptions = {}) {
  const { enabled = true, onStatus, onGames, onPositions, onError } = options;
  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const heartbeatTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const [isConnected, setIsConnected] = useState(false);

  const { setSseConnected, setBotStatus, updateLastUpdate } = useAppStore();

  // Store callbacks in refs to avoid reconnect on callback identity change
  const callbacksRef = useRef({ onStatus, onGames, onPositions, onError });
  callbacksRef.current = { onStatus, onGames, onPositions, onError };

  const clearHeartbeatTimeout = useCallback(() => {
    if (heartbeatTimeoutRef.current) {
      clearTimeout(heartbeatTimeoutRef.current);
      heartbeatTimeoutRef.current = null;
    }
  }, []);

  const resetHeartbeatTimeout = useCallback((reconnectFn: () => void) => {
    clearHeartbeatTimeout();
    heartbeatTimeoutRef.current = setTimeout(() => {
      console.warn('[SSE] Heartbeat timeout - connection may be stale');
      // Close and reconnect
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      setIsConnected(false);
      setSseConnected(false);
      reconnectFn();
    }, HEARTBEAT_TIMEOUT_MS);
  }, [clearHeartbeatTimeout, setSseConnected]);

  const connect = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }
    clearHeartbeatTimeout();

    try {
      const eventSource = apiClient.createSSEConnection();
      eventSourceRef.current = eventSource;

      eventSource.onopen = () => {
        console.log('[SSE] Connected to event stream');
        setIsConnected(true);
        reconnectAttemptsRef.current = 0;
        setSseConnected(true);
        resetHeartbeatTimeout(connect);
      };

      eventSource.onmessage = (event) => {
        try {
          const parsed: SSEEvent = JSON.parse(event.data);
          updateLastUpdate();
          resetHeartbeatTimeout(connect);

          switch (parsed.type) {
            case 'status': {
              const statusData = parsed.data as StatusData;
              setBotStatus(statusData.state === 'running', statusData.tracked_games);
              callbacksRef.current.onStatus?.(statusData);
              break;
            }
            case 'games':
              callbacksRef.current.onGames?.(parsed.data as GameData[]);
              break;

            case 'positions':
              callbacksRef.current.onPositions?.(parsed.data as PositionData[]);
              break;

            case 'heartbeat':
              // Heartbeat received - timeout already reset above
              break;

            case 'error':
              console.error('[SSE] Server error:', parsed.data);
              callbacksRef.current.onError?.(new Error(String(parsed.data)));
              break;
          }
        } catch (e) {
          console.error('[SSE] Failed to parse message:', e);
        }
      };

      eventSource.onerror = () => {
        setIsConnected(false);
        setSseConnected(false);
        clearHeartbeatTimeout();
        eventSource.close();
        eventSourceRef.current = null;

        const attempts = reconnectAttemptsRef.current;
        if (attempts < MAX_RECONNECT_ATTEMPTS) {
          const delay = Math.min(
            BASE_RECONNECT_DELAY * Math.pow(2, attempts),
            30000
          );

          console.log(`[SSE] Reconnecting in ${delay}ms (attempt ${attempts + 1}/${MAX_RECONNECT_ATTEMPTS})`);

          reconnectTimeoutRef.current = setTimeout(() => {
            reconnectAttemptsRef.current += 1;
            connect();
          }, delay);
        } else {
          console.error('[SSE] Max reconnection attempts reached');
          callbacksRef.current.onError?.(new Error('Connection lost. Please refresh the page.'));
        }
      };
    } catch (error) {
      console.error('[SSE] Failed to create connection:', error);
      callbacksRef.current.onError?.(error instanceof Error ? error : new Error('Failed to connect'));
    }
  }, [setSseConnected, setBotStatus, updateLastUpdate, clearHeartbeatTimeout, resetHeartbeatTimeout]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    clearHeartbeatTimeout();

    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }

    reconnectAttemptsRef.current = 0;
    setIsConnected(false);
    setSseConnected(false);
  }, [setSseConnected, clearHeartbeatTimeout]);

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

  return {
    isConnected,
    reconnectAttempts: reconnectAttemptsRef.current,
    connect,
    disconnect,
  };
}

export default useSSE;
