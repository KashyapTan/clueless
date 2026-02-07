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
import settingsIcon from './assets/settings-icon.svg';
import chatHistoryIcon from './assets/chat-history-icon.svg';
import recordedMeetingsAlbumIcon from './assets/recorded-meetings-album-icon.svg';
import newChatIcon from './assets/new-chat-icon.svg';
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
  // Multiple screenshots support
  const [screenshots, setScreenshots] = useState<Array<{id: string, name: string, thumbnail: string}>>([]);
  // Capture mode: 'fullscreen' | 'precision' | 'none'
  const [captureMode, setCaptureMode] = useState<'fullscreen' | 'precision' | 'none'>('fullscreen');
  const [meetingRecordingMode, setMeetingRecordingMode] = useState<boolean>(false);
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
        // Send initial capture mode to backend
        ws?.send(JSON.stringify({ type: 'set_capture_mode', mode: 'fullscreen' }));
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
              setError('');
              setIsHidden(false);
              // Don't reset chat history - allow continuing conversation with new screenshot context
              break;
            case 'screenshot_added': {
              // New screenshot added to context
              try {
                const ssData = typeof data.content === 'string' ? JSON.parse(data.content) : data.content;
                setScreenshots(prev => [...prev, {
                  id: ssData.id,
                  name: ssData.name,
                  thumbnail: ssData.thumbnail
                }]);
                setStatus('Screenshot added to context.');
                setIsHidden(false);
              } catch (e) {
                console.error('Error parsing screenshot data:', e);
              }
              break;
            }
            case 'screenshot_removed': {
              // Screenshot removed from context
              try {
                const removeData = typeof data.content === 'string' ? JSON.parse(data.content) : data.content;
                setScreenshots(prev => prev.filter(ss => ss.id !== removeData.id));
              } catch (e) {
                console.error('Error parsing screenshot removal:', e);
              }
              break;
            }
            case 'screenshots_cleared':
              // Only clear screenshots, preserve chat history (used in fullscreen mode)
              setScreenshots([]);
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
              setScreenshots([]);
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
              // Note: query input is already cleared in handleSubmit
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
    setQuery(''); // Clear input immediately
    
    // Send query with capture mode
    wsRef.current.send(JSON.stringify({ 
      type: 'submit_query', 
      content: query.trim(),
      capture_mode: captureMode
    }));
  };

  const handleClearContext = () => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    wsRef.current.send(JSON.stringify({ type: 'clear_context' }));
  };

  const handleRemoveScreenshot = (id: string) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    wsRef.current.send(JSON.stringify({ type: 'remove_screenshot', id }));
  };

  // Helper to get appropriate placeholder text
  const getPlaceholder = () => {
    if (chatHistory.length > 0) {
      return screenshots.length > 0 ? "Ask a follow-up about the screenshot(s)..." : "Ask a follow-up question...";
    }
    if (captureMode === 'fullscreen') {
      return "Ask anything... (auto-captures screen on submit)";
    }
    if (captureMode === 'precision') {
      return screenshots.length > 0 ? "Ask about the screenshot(s)..." : "Press Ctrl+Shift+Alt+S to capture a region...";
    }
    return "Ask Clueless anything...";
  };
  
  const sendCaptureMode = (mode: 'fullscreen' | 'precision' | 'none') => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'set_capture_mode', mode }));
    }
  };
  
  const fullscreenModeEnabled = () => {
    setCaptureMode('fullscreen');
    setMeetingRecordingMode(false);
    sendCaptureMode('fullscreen');
  };
  
  const precisionModeEnabled = () => {
    setCaptureMode('precision');
    setMeetingRecordingMode(false);
    sendCaptureMode('precision');
  };
  
  const meetingRecordingModeEnabled = () => {
    setCaptureMode('none');
    setMeetingRecordingMode(true);
    sendCaptureMode('none');
  }
  return (
    <>
      <div className="container" style={{ opacity: isHidden ? 0 : 1 }}>
        <div className="title-bar">
          <div className="nav-bar">
            <div className="settingsButton">
              <img src={settingsIcon} alt="Settings" className='settings-icon' />
            </div>
            <div className="chatHistoryButton">
              <img src={chatHistoryIcon} alt="Chat History" className='chat-history-icon'/>
            </div>
            <div className="recordedMeetingsAlbumButton">
              <img src={recordedMeetingsAlbumIcon} alt="Recorded Meetings Album" className='recorded-meetings-album-icon'/>
            </div>
          </div>
          <div className="blank-space-to-drag"></div>
          <div className="nav-bar-right-side">
            <div className="newChatButton" onClick={handleClearContext} title="Start new chat">
              <img src={newChatIcon} alt="New Chat" className='new-chat-icon'/>
            </div>
            <div className="clueless-logo-holder">
              <img src={cluelessLogo} alt="Clueless Logo" className='clueless-logo' />
            </div>
          </div>

        </div>
        <div className="response-area">
          {error && <div className="error"><strong>Error:</strong> {error}</div>}

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
              {/* <div className="add-attachments-section">
                <img src={plusSignSvg} alt="Add attachment" className='plus-sign-svg' />
              </div> */}
              
              {/* Fixed container for context chips - maintains layout stability */}
              <div className="chips-container-wrapper">
                {screenshots.length > 0 && (
                  <div className="context-chips">
                    {screenshots.map((ss, index) => (
                      <div key={ss.id} className="context-chip">
                        <div className="chip-preview">
                          {ss.thumbnail ? (
                            <img 
                              src={`data:image/png;base64,${ss.thumbnail}`} 
                              alt={ss.name}
                              className="chip-thumb"
                            />
                          ) : (
                            <span className="chip-icon">📷</span>
                          )}
                        </div>
                        <span className="chip-name">SS{index + 1}</span>
                        <button 
                          className="chip-remove" 
                          onClick={() => handleRemoveScreenshot(ss.id)}
                          title="Remove"
                        >
                          ×
                        </button>
                        {/* Hover preview popup */}
                        <div className="chip-hover-preview">
                          {ss.thumbnail && (
                            <img 
                              src={`data:image/png;base64,${ss.thumbnail}`} 
                              alt={ss.name}
                              className="hover-preview-img"
                            />
                          )}
                          <span className="hover-preview-name">{ss.name}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
              <div className="additional-inputs-section">
                <div className="model-selection-section">
                  <select name="model-selector" className='model-select'>
                    <option value="gpt-4">GPT-4</option>
                    <option value="gpt-3.5">GPT-3.5</option>
                  </select>
                </div>
                <div className="mic-input-section">
                  <img src={micSignSvg} alt="Voice input" className='mic-icon' />
                </div>
              </div>
            </div>
          </div>
          <div className="mode-selection-section">
            <div className={`fullscreenssmode${captureMode === 'fullscreen' ? '-active' : ''}`} onClick={fullscreenModeEnabled} title="Talk to anything on your screen">
              <img src={fullscreenSSIcon} alt="Full Screen Screenshot Mode" className='fullscreen-ss-icon' />
            </div>
            <div className={`regionssmode${captureMode === 'precision' ? '-active' : ''}`} onClick={precisionModeEnabled} title="Talk to a specific region of your screen">
              <img src={regionSSIcon} alt="Region Screenshot Mode" className='region-ss-icon' />
            </div>
            <div className={`meetingrecordermode${meetingRecordingMode ? '-active' : ''}`} onClick={meetingRecordingModeEnabled} title="Meeting recorder mode">
              <img src={meetingRecordingIcon} alt="Meeting Recorder Mode" className='meeting-recording-icon' />
            </div>
          </div>
        </div>
      </div>
    </>
  )
}

export default App
