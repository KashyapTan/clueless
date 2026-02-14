/**
 * Tool calls display component.
 * 
 * Shows MCP tool calls and their results in a collapsible section.
 */
import type { ToolCall } from '../../types';

interface ToolCallsDisplayProps {
  toolCalls: ToolCall[];
}

export function ToolCallsDisplay({ toolCalls }: ToolCallsDisplayProps) {
  if (!toolCalls || toolCalls.length === 0) {
    return null;
  }

  return (
    <div className="tool-calls-section">
      <div className="tool-calls-header">
        <span className="tool-calls-icon">&#9881;</span>
        <span>Used {toolCalls.length} tool{toolCalls.length > 1 ? 's' : ''}</span>
      </div>
      <div className="tool-calls-list">
        {toolCalls.map((tc, idx) => (
          <div key={idx} className="tool-call-item">
            <div className="tool-call-name">
              <span className="tool-call-badge">{tc.server}</span>
              <code>
                {tc.name}({Object.entries(tc.args).map(([k, v]) => `${k}: ${JSON.stringify(v)}`).join(', ')})
              </code>
            </div>
            <div className="tool-call-result">
              <span className="tool-result-label">Result:</span>{' '}
              <code>{tc.result.slice(0, 100)}{tc.result.length > 100 ? '...' : ''}</code>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
