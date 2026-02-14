/**
 * Code block component with syntax highlighting and copy functionality.
 */
import React from 'react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { copyToClipboard } from '../../utils/clipboard';

interface CodeBlockProps {
  inline?: boolean;
  className?: string;
  children?: React.ReactNode;
}

export function CodeBlock({ inline, className, children, ...props }: CodeBlockProps) {
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
        {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
        <SyntaxHighlighter style={vscDarkPlus as any} language={match[1]} PreTag="div" {...props}>
          {codeContent}
        </SyntaxHighlighter>
      </div>
    );
  }
  
  return <code className={className} {...props}>{children}</code>;
}
