/**
 * WebSocket connection hook.
 * 
 * Manages WebSocket connection lifecycle, reconnection, and message handling.
 */
import { useEffect, useRef, useCallback } from 'react';
import type { WebSocketMessage } from '../types';

const WS_URL = 'ws://localhost:8000/ws';
const RECONNECT_DELAY = 2000;

interface UseWebSocketOptions {
  onMessage: (data: WebSocketMessage) => void;
  onOpen?: () => void;
  onClose?: () => void;
  onError?: (error: Event) => void;
}

interface UseWebSocketReturn {
  send: (message: Record<string, unknown>) => void;
  isConnected: boolean;
  wsRef: React.RefObject<WebSocket | null>;
}

export function useWebSocket(options: UseWebSocketOptions): UseWebSocketReturn {
  const { onMessage, onOpen, onClose, onError } = options;
  const wsRef = useRef<WebSocket | null>(null);
  const isConnectedRef = useRef(false);

  const connect = useCallback(() => {
    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      isConnectedRef.current = true;
      onOpen?.();
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        onMessage(data);
      } catch (e) {
        console.error('Failed to parse WebSocket message:', e);
      }
    };

    ws.onclose = () => {
      isConnectedRef.current = false;
      onClose?.();
      // Attempt to reconnect
      setTimeout(connect, RECONNECT_DELAY);
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      onError?.(error);
    };
  }, [onMessage, onOpen, onClose, onError]);

  useEffect(() => {
    connect();

    return () => {
      if (wsRef.current) {
        wsRef.current.onclose = null; // Prevent reconnection on unmount
        wsRef.current.close();
      }
    };
  }, [connect]);

  const send = useCallback((message: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
    }
  }, []);

  return {
    send,
    isConnected: isConnectedRef.current,
    wsRef,
  };
}
