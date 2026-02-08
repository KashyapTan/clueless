import React, { createContext, useContext, useState, useEffect, useRef, ReactNode } from 'react';

interface WebSocketContextType {
  isHidden: boolean;
  setIsHidden: (val: boolean) => void;
  status: string;
  error: string;
  ws: WebSocket | null;
  // Common shared states that pages might need
  screenshots: any[];
  setScreenshots: React.Dispatch<React.SetStateAction<any[]>>;
  canSubmit: boolean;
  setCanSubmit: React.Dispatch<React.SetStateAction<boolean>>;
}

const WebSocketContext = createContext<WebSocketContextType | undefined>(undefined);

export const WebSocketProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [isHidden, setIsHidden] = useState<boolean>(false);
  const [status, setStatus] = useState<string>('Connecting...');
  const [error, setError] = useState<string>('');
  const [screenshots, setScreenshots] = useState<any[]>([]);
  const [canSubmit, setCanSubmit] = useState<boolean>(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    let ws: WebSocket | null = null;
    const connect = () => {
      ws = new WebSocket('ws://localhost:8000/ws');
      wsRef.current = ws;

      ws.onopen = () => {
        setStatus('Connected');
        setError('');
        ws?.send(JSON.stringify({ type: 'set_capture_mode', mode: 'fullscreen' }));
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          switch (data.type) {
            case 'screenshot_start':
              setIsHidden(true);
              break;
            case 'screenshot_ready':
              setIsHidden(false);
              setStatus('Screenshot captured!');
              break;
            case 'ready':
              setCanSubmit(true);
              setStatus('Ready');
              break;
            // Add other global handlers if needed
          }
        } catch (e) {
          console.error("Context WS error:", e);
        }
      };

      ws.onclose = () => {
        setStatus('Disconnected');
        setTimeout(connect, 2000);
      };
    };

    connect();
    return () => ws?.close();
  }, []);

  return (
    <WebSocketContext.Provider value={{ 
      isHidden, setIsHidden, status, error, ws: wsRef.current,
      screenshots, setScreenshots, canSubmit, setCanSubmit
    }}>
      {children}
    </WebSocketContext.Provider>
  );
};

export const useWebSocket = () => {
  const context = useContext(WebSocketContext);
  if (!context) throw new Error('useWebSocket must be used within a WebSocketProvider');
  return context;
};
