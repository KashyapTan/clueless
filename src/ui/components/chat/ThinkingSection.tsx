/**
 * Thinking section component.
 * 
 * Shows the model's reasoning process in a collapsible section.
 */
import ReactMarkdown from 'react-markdown';

interface ThinkingSectionProps {
  thinking: string;
  isThinking: boolean;
  collapsed: boolean;
  onToggle: () => void;
}

export function ThinkingSection({ thinking, isThinking, collapsed, onToggle }: ThinkingSectionProps) {
  if (!thinking) {
    return null;
  }

  return (
    <div className="thinking-section">
      <div className="thinking-header" onClick={onToggle}>
        <span className={`thinking-arrow ${collapsed ? '' : 'expanded'}`}>▶</span>
        <span className="thinking-label">
          {isThinking ? 'Thinking...' : 'Thought process'}
        </span>
      </div>
      {!collapsed && (
        <div className="thinking-content">
          <ReactMarkdown>{thinking}</ReactMarkdown>
        </div>
      )}
    </div>
  );
}
