import { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import './App.css'

function App() {
  const [query, setQuery] = useState<string>('');
  const [response, setResponse] = useState<string>('');
  const [status, setStatus] = useState<string>('Connecting to server...');
  const [error, setError] = useState<string>('');

  useEffect(() => {
    let ws: WebSocket;
    let connectInterval: number;

    const connect = () => {
      ws = new WebSocket('ws://localhost:8000/ws');

      ws.onopen = () => {
        setStatus('Waiting for screenshot...');
        setError('');
        if (connectInterval) {
          clearInterval(connectInterval);
        }
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          switch (data.type) {
            case 'query':
              setQuery(data.content);
              setResponse('');
              setError('');
              setStatus('Receiving response...');
              break;
            case 'response_chunk':
              setResponse(prev => prev + data.content);
              break;
            case 'response_complete':
              setStatus('Response complete.');
              break;
            case 'error':
              setError(data.content);
              setQuery('');
              setResponse('');
              setStatus('An error occurred.');
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
      if (connectInterval) {
        clearInterval(connectInterval);
      }
      // Cleanly close the WebSocket connection when the component unmounts
      if (ws) {
        ws.onclose = null; // Prevent automatic reconnection on component unmount
        ws.close();
      }
    };
  }, []);

  return (
    <>
    <div className="container">
      <div className="title-bar" />
      <div className="response-area">
        {error && <div className="error"><strong>Error:</strong> {error}</div>}
        {!error && query && <div className="query"><strong>Query:</strong><p>{query}</p></div>}
        {!error && response && (
          <div className="response">
            <strong>Response:</strong>
            <ReactMarkdown
              components={{
                code({ node, inline, className, children, ...props }) {
                  const match = /language-(\w+)/.exec(className || '');
                  return !inline && match ? (
                    <SyntaxHighlighter
                      style={vscDarkPlus}
                      language={match[1]}
                      PreTag="div"
                      {...props}
                    >
                      {String(children).replace(/\n$/, '')}
                    </SyntaxHighlighter>
                  ) : (
                    <code className={className} {...props}>
                      {children}
                    </code>
                  );
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
