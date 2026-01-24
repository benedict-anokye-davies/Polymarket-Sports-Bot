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

export function useSSE(options: UseSSEOptions = {}) {
  const { enabled = true, onStatus, onGames, onPositions, onError } = options;
  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [reconnectAttempts, setReconnectAttempts] = useState(0);
  
  const { setSseConnected, setBotStatus, updateLastUpdate } = useAppStore();

  const MAX_RECONNECT_ATTEMPTS = 10;
  const BASE_RECONNECT_DELAY = 1000;

  const connect = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    try {
      const eventSource = apiClient.createSSEConnection();
      eventSourceRef.current = eventSource;

      eventSource.onopen = () => {
        console.log('[SSE] Connected to event stream');
        setIsConnected(true);
        setReconnectAttempts(0);
        setSseConnected(true);
      };

      eventSource.onmessage = (event) => {
        try {
          const parsed: SSEEvent = JSON.parse(event.data);
          updateLastUpdate();

          switch (parsed.type) {
            case 'status':
              const statusData = parsed.data as StatusData;
              setBotStatus(statusData.state === 'running', statusData.tracked_games);
              onStatus?.(statusData);
              break;
            
            case 'games':
              onGames?.(parsed.data as GameData[]);
              break;
            
            case 'positions':
              onPositions?.(parsed.data as PositionData[]);
              break;
            
            case 'heartbeat':
              // Keep connection alive, no action needed
              break;
            
            case 'error':
              console.error('[SSE] Server error:', parsed.data);
              onError?.(new Error(String(parsed.data)));
              break;
          }
        } catch (e) {
          console.error('[SSE] Failed to parse message:', e);
        }
      };

      eventSource.onerror = (error) => {
        console.error('[SSE] Connection error:', error);
        setIsConnected(false);
        setSseConnected(false);
        eventSource.close();

        // Reconnect with exponential backoff
        if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
          const delay = Math.min(
            BASE_RECONNECT_DELAY * Math.pow(2, reconnectAttempts),
            30000 // Max 30 seconds
          );
          
          console.log(`[SSE] Reconnecting in ${delay}ms (attempt ${reconnectAttempts + 1}/${MAX_RECONNECT_ATTEMPTS})`);
          
          reconnectTimeoutRef.current = setTimeout(() => {
            setReconnectAttempts(prev => prev + 1);
            connect();
          }, delay);
        } else {
          console.error('[SSE] Max reconnection attempts reached');
          onError?.(new Error('Connection lost. Please refresh the page.'));
        }
      };
    } catch (error) {
      console.error('[SSE] Failed to create connection:', error);
      onError?.(error instanceof Error ? error : new Error('Failed to connect'));
    }
  }, [
    onStatus, 
    onGames, 
    onPositions, 
    onError, 
    reconnectAttempts, 
    setSseConnected, 
    setBotStatus, 
    updateLastUpdate
  ]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    
    setIsConnected(false);
    setSseConnected(false);
  }, [setSseConnected]);

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
    reconnectAttempts,
    connect,
    disconnect,
  };
}

export default useSSE;
