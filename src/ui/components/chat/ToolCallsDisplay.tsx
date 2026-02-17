/**
 * Tool calls display component.
 * 
 * Shows MCP tool calls and their results in a collapsible, sleek card design.
 */
import { useState, useEffect } from 'react';
import type { ToolCall } from '../../types';

interface ToolCallsDisplayProps {
  toolCalls: ToolCall[];
}

export function ToolCallsDisplay({ toolCalls }: ToolCallsDisplayProps) {
  // Collapsed by default to keep UI clean, but expand if there are active calls
  const [isExpanded, setIsExpanded] = useState(false);
  
  // Auto-expand when a new tool call starts
  useEffect(() => {
    const hasActiveCall = toolCalls.some(tc => tc.status === 'calling');
    if (hasActiveCall) {
      setIsExpanded(true);
    }
  }, [toolCalls]);

  if (!toolCalls || toolCalls.length === 0) {
    return null;
  }

  const toggle = () => setIsExpanded(!isExpanded);

  return (
    <div className="tool-calls-container">
      <div 
        className={`tool-calls-header ${isExpanded ? 'expanded' : ''}`} 
        onClick={toggle}
      >
        <div className="tool-header-left">
          {/* Gear Icon */}
          <svg className={`tool-icon-gear ${toolCalls.some(tc => tc.status === 'calling') ? 'spinning' : ''}`} viewBox="0 0 16 16" width="14" height="14" fill="currentColor">
            <path fillRule="evenodd" d="M7.429 1.525a6.593 6.593 0 0 1 1.142 0c.036.003.108.036.137.146l.253 1.174a2.25 2.25 0 0 0 1.452 1.452l1.174.253c.11.029.143.10.146.137.254.347.46.717.617 1.106a.125.125 0 0 1-.06.138l-1.047.604a2.25 2.25 0 0 0-1.121 1.942v.04c0 .8.444 1.543 1.121 1.942l1.047.604c.036.02.052.065.06.138a6.593 6.593 0 0 1-.617 1.106.125.125 0 0 1-.146.137l-1.174.253a2.25 2.25 0 0 0-1.452 1.452l-.253 1.174c-.029.11-.1.143-.137.146a6.593 6.593 0 0 1-1.142 0 .125.125 0 0 1-.137-.146l-.253-1.174a2.25 2.25 0 0 0-1.452-1.452l-1.174-.253a.125.125 0 0 1-.146-.137 6.593 6.593 0 0 1-.617-1.106.125.125 0 0 1 .06-.138l1.047-.604A2.25 2.25 0 0 0 4.633 8.04v-.04a2.25 2.25 0 0 0-1.121-1.942l-1.047-.604a.125.125 0 0 1-.06-.138 6.593 6.593 0 0 1 .617-1.106.125.125 0 0 1 .146-.137l1.174-.253a2.25 2.25 0 0 0 1.452-1.452l.253-1.174a.125.125 0 0 1 .137-.146ZM8 5.5a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5Z" />
          </svg>
          <span className="tool-header-text">
             {toolCalls.some(tc => tc.status === 'calling') ? 'Running tools...' : `Used ${toolCalls.length} tool${toolCalls.length > 1 ? 's' : ''}`}
          </span>
        </div>
        
        {/* Chevron Icon */}
        <svg 
          className={`tool-icon-chevron ${isExpanded ? 'expanded' : ''}`} 
          viewBox="0 0 16 16" 
          width="12" 
          height="12" 
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
        >
          <path d="M4 6l4 4 4-4" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      </div>

      {isExpanded && (
        <div className="tool-calls-list">
          {toolCalls.map((tc, idx) => (
            <div key={idx} className={`tool-call-card ${tc.status === 'calling' ? 'calling' : ''}`}>
              <div className="tool-call-top">
                <span className="tool-server-badge">{tc.server}</span>
                <code className="tool-function-sig">
                  <span className="tool-func-name">{tc.name}</span>
                  <span className="tool-paren">(</span>
                  {Object.entries(tc.args).map(([k, v], i, arr) => (
                    <span key={k} className="tool-arg">
                      <span className="tool-arg-key">{k}:</span>
                      <span className="tool-arg-val">{JSON.stringify(v)}</span>
                      {i < arr.length - 1 && <span className="tool-comma">, </span>}
                    </span>
                  ))}
                  <span className="tool-paren">)</span>
                </code>
                {tc.status === 'calling' && <span className="tool-status-indicator">...</span>}
              </div>
              <div className="tool-call-bottom">
                 {/* Provide visual connection to result */}
                 <div className="tool-result-connector"></div>
                 <div className="tool-result-content">
                    {tc.status === 'calling' ? (
                       <span className="tool-result-text italic">Running...</span>
                    ) : (
                       <>
                         <span className="tool-result-label">Result:</span>
                         <span className="tool-result-text">
                           {tc.result && tc.result.length > 300 
                             ? tc.result.slice(0, 300) + '...' 
                             : tc.result || 'No output'}
                         </span>
                       </>
                    )}
                 </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
