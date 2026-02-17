/**
 * Response area component.
 * 
 * Container for chat history and current streaming response.
 */
import React from 'react';
import ReactMarkdown from 'react-markdown';
import { ChatMessage } from './ChatMessage';
import { ThinkingSection } from './ThinkingSection';
import { CodeBlock } from './CodeBlock';
import { LoadingDots } from './LoadingDots';
import type { ChatMessage as ChatMessageType } from '../../types';

interface ResponseAreaProps {
  chatHistory: ChatMessageType[];
  currentQuery: string;
  response: string;
  thinking: string;
  isThinking: boolean;
  thinkingCollapsed: boolean;
  generatingModel: string;
  canSubmit: boolean;
  error: string;
  showScrollBottom: boolean;
  onToggleThinking: () => void;
  onScroll: () => void;
  onScrollToBottom: () => void;
  responseAreaRef: React.RefObject<HTMLDivElement | null>;
  scrollDownIcon: string;
}

export function ResponseArea({
  chatHistory,
  currentQuery,
  response,
  thinking,
  isThinking,
  thinkingCollapsed,
  generatingModel,
  canSubmit,
  error,
  showScrollBottom,
  onToggleThinking,
  onScroll,
  onScrollToBottom,
  responseAreaRef,
  scrollDownIcon,
}: ResponseAreaProps) {
  return (
    <>
      <div className="response-area" ref={responseAreaRef} onScroll={onScroll}>
        {error && (
          <div className="error">
            <strong>Error:</strong> {error}
          </div>
        )}

        {/* Chat history */}
        {!error &&
          chatHistory.map((msg, idx) => (
            <ChatMessage key={idx} message={msg} selectedModel={generatingModel} />
          ))}

        {/* Current query being processed */}
        {!error && currentQuery && !canSubmit && (
          <div className="query">
            <p>{currentQuery}</p>
          </div>
        )}

        {/* Loading animation while waiting for response start */}
        {!error && !canSubmit && !thinking && !response && (
           <div className="response">
             <div className="assistant-header">Clueless • {generatingModel}</div>
             <LoadingDots />
           </div>
        )}

        {/* Current thinking process */}
        {!error && thinking && (
          <ThinkingSection
            thinking={thinking}
            isThinking={isThinking}
            collapsed={thinkingCollapsed}
            onToggle={onToggleThinking}
          />
        )}

        {/* Current response being streamed */}
        {!error && response && (
          <div className="response">
            <div className="assistant-header">Clueless • {generatingModel}</div>
            <ReactMarkdown
              components={{
                code: CodeBlock as React.ComponentType<React.ComponentPropsWithRef<'code'>>,
              }}
            >
              {response}
            </ReactMarkdown>
          </div>
        )}
      </div>

      {showScrollBottom && (
        <button
          className="scroll-bottom-button"
          onClick={onScrollToBottom}
          title="Scroll to bottom"
        >
          <img src={scrollDownIcon} alt="Scroll down" className="scroll-down-icon" />
        </button>
      )}
    </>
  );
}
