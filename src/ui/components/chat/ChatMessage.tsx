/**
 * Chat message component.
 * 
 * Renders a single chat message (user or assistant).
 */
import React from 'react';
import ReactMarkdown from 'react-markdown';
import { CodeBlock } from './CodeBlock';
import { ToolCallsDisplay } from './ToolCallsDisplay';
import type { ChatMessage as ChatMessageType } from '../../types';

interface ChatMessageProps {
  message: ChatMessageType;
  selectedModel: string;
}

export function ChatMessage({ message, selectedModel }: ChatMessageProps) {
  if (message.role === 'user') {
    return (
      <div className="chat-user">
        <div className="query">
          <p>{message.content}</p>
          {message.images && message.images.length > 0 && (
            <MessageImages images={message.images} />
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="chat-assistant">
      <div className="response">
        <div className="assistant-header">Clueless • {message.model || selectedModel}</div>
        {message.toolCalls && <ToolCallsDisplay toolCalls={message.toolCalls} />}
        <ReactMarkdown
          components={{
            code: CodeBlock as React.ComponentType<React.ComponentPropsWithRef<'code'>>,
          }}
        >
          {message.content}
        </ReactMarkdown>
      </div>
    </div>
  );
}

interface MessageImagesProps {
  images: Array<{ name: string; thumbnail: string }>;
}

function MessageImages({ images }: MessageImagesProps) {
  return (
    <div className="message-image-chips">
      {images.map((img, idx) => (
        <div key={idx} className="message-image-chip">
          {img.thumbnail ? (
            <img
              src={`data:image/png;base64,${img.thumbnail}`}
              alt={img.name || `Image ${idx + 1}`}
              className="message-chip-thumb"
            />
          ) : (
            <span className="message-chip-icon">📷</span>
          )}
          <span className="message-chip-name">{img.name || `Image ${idx + 1}`}</span>
          {img.thumbnail && (
            <div className="message-chip-hover-preview">
              <img
                src={`data:image/png;base64,${img.thumbnail}`}
                alt={img.name || `Image ${idx + 1}`}
              />
              <span>{img.name || `Image ${idx + 1}`}</span>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
