import { useState, useEffect, useRef } from 'react';
import type { FormEvent } from 'react';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import './App.css'
import cluelessLogo from './assets/transparent-clueless-logo.png';
import plusSignSvg from './assets/plus-icon.svg';
import micSignSvg from './assets/mic-icon.svg';
import fullscreenSSIcon from './assets/entire-screen-shot-icon.svg';
import regionSSIcon from './assets/region-screen-shot-icon.svg';
import meetingRecordingIcon from './assets/meeting-record-icon.svg';
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
  const [thinking, setThinking] = useState<string>('');
  const [isThinking, setIsThinking] = useState<boolean>(false);
  const [thinkingCollapsed, setThinkingCollapsed] = useState<boolean>(true);
  const [status, setStatus] = useState<string>('Connecting to server...');
  const [error, setError] = useState<string>('');
  const [canSubmit, setCanSubmit] = useState<boolean>(false);
  const [isHidden, setIsHidden] = useState<boolean>(false);
  const [hasScreenshot, setHasScreenshot] = useState<boolean>(false);
  // Chat history for multi-turn conversations
  const [chatHistory, setChatHistory] = useState<Array<{role: 'user' | 'assistant', content: string, thinking?: string}>>([]);
  const [currentQuery, setCurrentQuery] = useState<string>('');
  const wsRef = useRef<WebSocket | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);
  // Refs to track current values for WebSocket handler
  const currentQueryRef = useRef<string>('');
  const responseRef = useRef<string>('');
  const thinkingRef = useRef<string>('');

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
        setStatus('Connected to server');
        setError('');
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          switch (data.type) {
            case 'ready':
              // Server is ready - enable input immediately (no screenshot required)
              setStatus(data.content || 'Ready to chat. Take a screenshot (Ctrl+Shift+Alt+S) or just type.');
              setCanSubmit(true);
              setError('');
              break;
            case 'screenshot_start':
              setIsHidden(true);
              break;
            case 'screenshot_ready':
              setStatus('Screenshot captured! Ask about it or continue chatting.');
              setHasScreenshot(true);
              setError('');
              setIsHidden(false);
              // Don't reset chat history - allow continuing conversation with new screenshot context
              break;
            case 'context_cleared':
              setStatus(data.content || 'Context cleared. Ready for new conversation.');
              setResponse('');
              setThinking('');
              setIsThinking(false);
              setThinkingCollapsed(true);
              setError('');
              setQuery('');
              setCurrentQuery('');
              setChatHistory([]);
              setHasScreenshot(false);
              setCanSubmit(true);
              // Reset refs
              currentQueryRef.current = '';
              responseRef.current = '';
              thinkingRef.current = '';
              break;
            case 'query':
              // Server echoes the submitted query
              setCurrentQuery(data.content);
              currentQueryRef.current = data.content;
              setError('');
              setStatus('Thinking...');
              setIsThinking(true);
              setCanSubmit(false);
              break;
            case 'thinking_chunk':
              setThinking(prev => prev + data.content);
              thinkingRef.current += data.content;
              break;
            case 'thinking_complete':
              setIsThinking(false);
              setStatus('Receiving response...');
              break;
            case 'response_chunk':
              setResponse(prev => prev + data.content);
              responseRef.current += data.content;
              break;
            case 'response_complete': {
              // Capture values BEFORE resetting - React's setState callback runs async!
              const completedQuery = currentQueryRef.current;
              const completedResponse = responseRef.current;
              const completedThinking = thinkingRef.current;
              
              // Add the completed exchange to chat history
              setChatHistory(prev => [
                ...prev,
                { role: 'user', content: completedQuery },
                { role: 'assistant', content: completedResponse, thinking: completedThinking || undefined }
              ]);
              // Clear current response/thinking for next turn
              setResponse('');
              setThinking('');
              setCurrentQuery('');
              setQuery('');
              // Reset refs
              currentQueryRef.current = '';
              responseRef.current = '';
              thinkingRef.current = '';
              setStatus('Ready for follow-up question.');
              setCanSubmit(true); // Allow follow-up questions
              break;
            }
            case 'error':
              setError(data.content);
              setResponse('');
              setStatus('An error occurred.');
              setCanSubmit(true); // Allow retry
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
    if (!query.trim()) return; // Don't submit empty queries

    setResponse('');
    setThinking('');
    setThinkingCollapsed(true);
    wsRef.current.send(JSON.stringify({ type: 'submit_query', content: query.trim() }));
  };

  const handleClearContext = () => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    wsRef.current.send(JSON.stringify({ type: 'clear_context' }));
  };

  // Helper to get appropriate placeholder text
  const getPlaceholder = () => {
    if (chatHistory.length > 0) {
      return hasScreenshot ? "Ask a follow-up about the screenshot..." : "Ask a follow-up question...";
    }
    return hasScreenshot ? "Ask about this screenshot..." : "Ask anything or take a screenshot (Ctrl+Shift+Alt+S)...";
  };

  return (
    <>
      <div className="container" style={{ opacity: isHidden ? 0 : 1 }}>
        <div className="title-bar">
          <img src={cluelessLogo} alt="Clueless Logo" className='clueless-logo' />
        </div>
        <div className="response-area">
          {error && <div className="error"><strong>Error:</strong> {error}</div>}

          {/* Screenshot indicator */}
          {hasScreenshot && (
            <div className="screenshot-indicator">
              <span className="screenshot-badge">📷 Screenshot attached</span>
              <button className="clear-btn" onClick={handleClearContext} title="Clear context">×</button>
            </div>
          )}

          {/* Display chat history */}
          {!error && chatHistory.map((msg, idx) => (
            <div key={idx} className={msg.role === 'user' ? 'chat-user' : 'chat-assistant'}>
              {msg.role === 'user' ? (
                <div className="query">
                  <strong>You:</strong>
                  <p>{msg.content}</p>
                </div>
              ) : (
                <div className="response">
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
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                  <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                                  <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                                </svg>
                              </button>
                              {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
                              <SyntaxHighlighter style={vscDarkPlus as any} language={match[1]} PreTag="div" {...props}>
                                {codeContent}
                              </SyntaxHighlighter>
                            </div>
                          );
                        }
                        return <code className={className} {...props}>{children}</code>;
                      },
                    }}
                  >{msg.content}</ReactMarkdown>
                </div>
              )}
            </div>
          ))}

          {/* Current query being processed */}
          {!error && currentQuery && !canSubmit && (
            <div className="query">
              <strong>You:</strong>
              <p>{currentQuery}</p>
            </div>
          )}

          {/* Current thinking process */}
          {!error && thinking && (
            <div className="thinking-section">
              <div
                className="thinking-header"
                onClick={() => setThinkingCollapsed(!thinkingCollapsed)}
              >
                <span className={`thinking-arrow ${thinkingCollapsed ? '' : 'expanded'}`}>▶</span>
                <span className="thinking-label">
                  {isThinking ? 'Thinking...' : 'Thought process'}
                </span>
              </div>
              {!thinkingCollapsed && (
                <div className="thinking-content">
                  <ReactMarkdown>{thinking}</ReactMarkdown>
                </div>
              )}
            </div>
          )}

          {/* Current response being streamed */}
          {!error && response && (
            <div className="response">
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
          {/* <div className="status">{status}</div> */}

        </div>
        <div className="main-interaction-section">
            <div className="query-input-section">
              <div className="query-input-text-box-section">
                <form onSubmit={handleSubmit} style={{ marginTop: '0.5rem' }} className='query-input-form'>
                  <input
                    ref={inputRef}
                    className="query-input"
                    type="text"
                    placeholder={getPlaceholder()}
                    value={query}
                    onChange={e => setQuery(e.target.value)}
                  />
                </form>
              </div>

              <div className="input-options-section">
                <div className="add-attachments-section">
                  <img src={plusSignSvg} alt="Add attachment" className='plus-sign-svg'/>
                </div>
                <div className="additional-inputs-section">
                  <div className="model-selection-section">
                    <select name="model-selector" className='model-select'>
                      <option value="gpt-4">GPT-4</option>
                      <option value="gpt-3.5">GPT-3.5</option>
                    </select>
                  </div>
                  <div className="mic-input-section">
                    <img src={micSignSvg} alt="Voice input" className='mic-sign-svg'/>
                  </div>
                </div>
              </div>
            </div>
            <div className="mode-selection-section">
              <div className="fullscreenssmode">
                <img src={fullscreenSSIcon} alt="Full Screen Screenshot Mode" className='fullscreen-ss-icon'/>
              </div>
              <div className="regionssmode">
                <img src={regionSSIcon} alt="Region Screenshot Mode" className='region-ss-icon'/>
              </div>
              <div className="meetingrecordermode">
                <img src={meetingRecordingIcon} alt="Meeting Recorder Mode" className='meeting-recording-icon'/>
              </div>
            </div>
          </div>
      </div>
    </>
  )
}

export default App
