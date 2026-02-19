import { useState, useEffect } from 'react';
import type { ToolCall } from '../../types';

interface ToolCallsDisplayProps {
  toolCalls: ToolCall[];
}

export function ToolCallsDisplay({ toolCalls }: ToolCallsDisplayProps) {
  // State for the main container (all tools)
  const [isMainExpanded, setIsMainExpanded] = useState(false);
  
  // State for individual tool details (keyed by index)
  const [expandedToolIndices, setExpandedToolIndices] = useState<Set<number>>(new Set());

  // Auto-expand main container if tools are active
  useEffect(() => {
    const hasActiveCall = toolCalls.some(tc => tc.status === 'calling');
    if (hasActiveCall) {
      setIsMainExpanded(true);
    }
  }, [toolCalls]);

  if (!toolCalls || toolCalls.length === 0) {
    return null;
  }

  const toggleMain = () => setIsMainExpanded(!isMainExpanded);

  const toggleTool = (index: number) => {
    const newSet = new Set(expandedToolIndices);
    if (newSet.has(index)) {
      newSet.delete(index);
    } else {
      newSet.add(index);
    }
    setExpandedToolIndices(newSet);
  };

  const getHumanReadableDescription = (tc: ToolCall): { badge: string, text: string } => {
    const { server, name, args } = tc;
    
    // Default fallback
    let badge = server.toUpperCase();
    let text = `${name}(${JSON.stringify(args)})`;

    // Demo Server
    if (server === 'demo') {
      badge = 'CALCULATOR';
      if (name === 'add') text = `Adding ${args.a} + ${args.b}`;
      if (name === 'divide') text = `Dividing ${args.a} / ${args.b}`;
    }

    // Filesystem Server
    else if (server === 'filesystem') {
      badge = 'FILESYSTEM';
      if (name === 'list_directory') text = `Listing contents of '${args.path}'`;
      if (name === 'read_file') text = `Reading file '${args.path}'`;
      if (name === 'write_file') text = `Writing to file '${args.path}'`;
      if (name === 'create_folder') text = `Creating folder '${args.folder_name}' in '${args.path}'`;
      if (name === 'move_file') text = `Moving '${args.source_path}' to '${args.destination_folder}'`;
      if (name === 'rename_file') text = `Renaming '${args.source_path}' to '${args.new_name}'`;
    }

    // Websearch Server
    else if (server === 'websearch') {
      badge = 'WEBSEARCH';
      if (name === 'search_web_pages') text = `Searching the web for "${args.query}"`;
      if (name === 'read_website') text = `Reading website "${args.url}"`;
    }
    
    // Common overrides for clarity if badge is still generic
    if (badge === 'FILESYSTEM') badge = 'FILE';
    if (badge === 'WEBSEARCH') badge = 'WEB';

    return { badge, text };
  };

  const isAnyRunning = toolCalls.some(tc => tc.status === 'calling');

  return (
    <div className="tool-calls-container-simple">
      {/* Main Collapsible Header */}
      <div 
        className={`tool-main-header ${isMainExpanded ? 'expanded' : ''}`} 
        onClick={toggleMain}
      >
        <div className="tool-main-header-left">
           {isAnyRunning ? (
             <svg className="tool-spinner small" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
             </svg>
           ) : (
             <svg className="tool-icon-static" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
               <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>
             </svg>
           )}
           <span>{isAnyRunning ? 'Running Tools' : `Used ${toolCalls.length} tool${toolCalls.length !== 1 ? 's' : ''}`}</span>
        </div>
        
        <svg 
          className={`tool-chevron ${isMainExpanded ? 'expanded' : ''}`} 
          viewBox="0 0 24 24" 
          fill="none" 
          stroke="currentColor" 
          strokeWidth="2"
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </div>

      {/* Main List */}
      {isMainExpanded && (
        <div className="tool-list-wrapper">
          {toolCalls.map((tc, idx) => {
            const { badge, text } = getHumanReadableDescription(tc);
            const isRunning = tc.status === 'calling';
            const isItemExpanded = expandedToolIndices.has(idx);
            
            return (
              <div key={idx} className="tool-item-container">
                {/* Tool Header (Always Visible) */}
                <div 
                  className={`tool-timeline-item ${isItemExpanded ? 'expanded' : ''} ${isRunning ? 'running' : ''}`}
                  onClick={() => !isRunning && toggleTool(idx)}
                >
                  <div className="tool-status-icon-wrapper">
                    {isRunning ? (
                      <svg className="tool-spinner" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
                      </svg>
                    ) : (
                      <svg className="tool-check" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                        <polyline points="20 6 9 17 4 12" />
                      </svg>
                    )}
                  </div>

                  <div className="tool-badge">{badge}</div>
                  <div className="tool-desc">{text}</div>
                  
                  {!isRunning && (
                     <svg 
                       className={`tool-item-chevron ${isItemExpanded ? 'expanded' : ''}`} 
                       viewBox="0 0 24 24" 
                       fill="none" 
                       stroke="currentColor" 
                       strokeWidth="2"
                     >
                       <polyline points="6 9 12 15 18 9" />
                     </svg>
                  )}
                </div>

                {/* Tool Details (Expanded) */}
                {isItemExpanded && !isRunning && (
                  <div className="tool-details-panel">
                    <div className="tool-details-label">Result:</div>
                    <pre className="tool-details-content">
                      {tc.result || 'No output returned.'}
                    </pre>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
