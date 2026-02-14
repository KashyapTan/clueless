/**
 * Query input component.
 * 
 * Text input field for user queries with submit handling.
 */
import React, { forwardRef } from 'react';
import type { FormEvent } from 'react';

interface QueryInputProps {
  query: string;
  placeholder: string;
  canSubmit: boolean;
  onQueryChange: (value: string) => void;
  onSubmit: (e: FormEvent) => void;
  onStopStreaming: () => void;
}

export const QueryInput = forwardRef<HTMLInputElement, QueryInputProps>(
  ({ query, placeholder, canSubmit, onQueryChange, onSubmit, onStopStreaming }, ref) => {
    return (
      <div className="query-input-text-box-section">
        <form onSubmit={onSubmit} style={{ marginTop: '0.5rem' }} className="query-input-form">
          <input
            ref={ref}
            className="query-input"
            type="text"
            placeholder={placeholder}
            value={query}
            onChange={(e) => onQueryChange(e.target.value)}
          />
        </form>
        {!canSubmit && (
          <button
            className="stop-streaming-button"
            onClick={onStopStreaming}
            title="Stop generating"
          >
            <div className="stop-icon" />
          </button>
        )}
      </div>
    );
  }
);

QueryInput.displayName = 'QueryInput';
