import { useState, useEffect, useRef } from 'react';
import type { FormEvent } from 'react';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import './App.css'

// Extend the Window interface to include electronAPI
declare global {
  interface Window {
    electronAPI?: {
      focusWindow: () => Promise<void>;
    };
  }
}

function App() {
  const [query, setQuery] = useState<string>('');
  const [response, setResponse] = useState<string>('');
  const [status, setStatus] = useState<string>('Connecting to server...');
  const [error, setError] = useState<string>('');
  const [canSubmit, setCanSubmit] = useState<boolean>(false);
  const [isHidden, setIsHidden] = useState<boolean>(false);
  const wsRef = useRef<WebSocket | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
    } catch (err) {
      console.error('Failed to copy text: ', err);
      // Fallback for older browsers
      const textArea = document.createElement('textarea');
      textArea.value = text;
      document.body.appendChild(textArea);
      textArea.focus();
      textArea.select();
      try {
        document.execCommand('copy');
      } catch (fallbackErr) {
        console.error('Fallback copy failed: ', fallbackErr);
      }
      document.body.removeChild(textArea);
    }
  };

  useEffect(() => {
  let ws: WebSocket | null = null;

    const connect = () => {
  ws = new WebSocket('ws://localhost:8000/ws');
  wsRef.current = ws;

      ws.onopen = () => {
        setStatus('Waiting for screenshot...');
        setError('');
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          switch (data.type) {
            case 'screenshot_start':
              setIsHidden(true);
              break;
            case 'screenshot_ready':
              setStatus(data.content || 'Screenshot captured. Enter your query.');
              setResponse('');
              setError('');
              setQuery('');
              setCanSubmit(true);
              setIsHidden(false);
              break;
            case 'query':
              // Server echoes the submitted query
              setQuery(data.content);
              setError('');
              setStatus('Receiving response...');
              setCanSubmit(false);
              break;
            case 'response_chunk':
              setResponse(prev => prev + data.content);
              break;
            case 'response_complete':
              setStatus('Response complete.');
              setCanSubmit(false);
              break;
            case 'error':
              setError(data.content);
              setResponse('');
              setStatus('An error occurred.');
              setCanSubmit(false);
              break;
          }
        } catch (e) {
          console.error("Failed to parse WebSocket message:", e);
          setError('Failed to parse message from server.');
          setStatus('An error occurred.');
        }
      };

      ws.onclose = () => {
        setStatus('Disconnected. Retrying connection...');
        // Don't clear query/response here to preserve state during brief disconnects
        setTimeout(connect, 2000); // Attempt to reconnect after 2 seconds
      };

      ws.onerror = (err) => {
        console.error("WebSocket error:", err);
        // The onclose event will be fired next, which will handle the retry.
      };
    };

    connect(); // Initial connection attempt

    return () => {
      // Cleanly close the WebSocket connection when the component unmounts
    if (ws) {
          ws.onclose = null; // Prevent automatic reconnection on component unmount
          ws.close();
        }
      };
    }, []);

  // Focus the input field whenever canSubmit becomes true (new screenshot taken)
  useEffect(() => {
    if (canSubmit && inputRef.current) {
      // For Electron apps, use the electronAPI to focus the window
      const focusInput = async () => {
        try {
          console.log('Attempting to focus window...', { electronAPI: window.electronAPI });
          if (window.electronAPI) {
            console.log('Calling electronAPI.focusWindow()');
            await window.electronAPI.focusWindow();
            console.log('electronAPI.focusWindow() completed');
          } else {
            console.log('electronAPI not available, using fallback');
            window.focus();
          }
          // Small delay to ensure window focus happens first
          setTimeout(() => {
            if (inputRef.current) {
              inputRef.current.focus();
              console.log('Input focused');
            }
          }, 50);
        } catch (error) {
          console.error('Failed to focus window:', error);
          // Fallback to just focusing the input
          if (inputRef.current) {
            inputRef.current.focus();
          }
        }
      };
      
      focusInput();
    }
  }, [canSubmit]);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;

    const PROMPT = "Analyze the following image in detail. Then predict what the users follow up questions/tasks could be. Based on the prediction/tasks, answer the question(s) or do the task(s). MAKE SURE YOU LIST AND ANSWER THE FOLLOW-UP QUESTIONS.";
    // Use a default prompt if query is empty
    const queryToSend = query.trim() || PROMPT;
    setResponse('');
    wsRef.current.send(JSON.stringify({ type: 'submit_query', content: queryToSend }));
  };

  return (
    <>
    <div className="container" style={{ opacity: isHidden ? 0 : 1 }}>
      <div className="title-bar" />
      <div className="response-area">
        {error && <div className="error"><strong>Error:</strong> {error}</div>}
        {!error && query && !canSubmit && (
          <div className="query">
            <strong>Query:</strong>
            <p>{query}</p>
          </div>
        )}
        {!error && canSubmit && (
          <div className="query-input-section">
            <strong>Query:</strong>
            <form onSubmit={handleSubmit} style={{ marginTop: '0.5rem' }}>
              <input
                ref={inputRef}
                className="query-input"
                type="text"
                placeholder="Enter query or press enter to describe "
                value={query}
                onChange={e => setQuery(e.target.value)}
              />
            </form>
          </div>
        )}
        {!error && response && (
          <div className="response">
            {/* <strong>Response:</strong> */}
            <ReactMarkdown
              components={{
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                code({ inline, className, children, ...props }: any) {
                  const match = /language-(\w+)/.exec(className || '');
                  const codeContent = String(children).replace(/\n$/, '');
                  
                  if (!inline && match) {
                    return (
                      <div className="code-block-container">
                        <button
                          onClick={() => copyToClipboard(codeContent)}
                          className="copy-button"
                          title="Copy code"
                        >
                          <svg
                            width="14"
                            height="14"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="2"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          >
                            <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                          </svg>
                        </button>
                        <SyntaxHighlighter
                          // eslint-disable-next-line @typescript-eslint/no-explicit-any
                          style={vscDarkPlus as any}
                          language={match[1]}
                          PreTag="div"
                          {...props}
                        >
                          {codeContent}
                        </SyntaxHighlighter>
                      </div>
                    );
                  }
                  return <code className={className} {...props}>{children}</code>;
                },
              }}
            >{response}</ReactMarkdown>
          </div>
        )}
        <div className="status">{status}</div>
      </div>
    </div>
    </>
  )
}

export default App
