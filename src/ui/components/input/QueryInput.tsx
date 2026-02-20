/**
 * Query input component.
 * 
 * Text input field for user queries with submit handling.
 */
import React, { forwardRef, useState, useRef } from 'react';
import type { FormEvent } from 'react';
import SlashCommandMenu from '../chat/SlashCommandMenu';

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
    const [cursorPos, setCursorPos] = useState(0);
    const [menuPos, setMenuPos] = useState({ top: 0, left: 0 });
    const localInputRef = useRef<HTMLInputElement>(null);

    // Sync external ref and local ref
    const inputRef = (ref as any) || localInputRef;

    const handleSelectCommand = (cmd: string) => {
      // Find the start of the current slash command being typed
      const textBeforeCursor = query.slice(0, cursorPos);
      const slashIndex = textBeforeCursor.lastIndexOf('/');

      if (slashIndex !== -1) {
        const beforeSlash = query.slice(0, slashIndex);
        const afterCursor = query.slice(cursorPos);

        // Add a space after the command for better UX
        const newQuery = beforeSlash + cmd + ' ' + afterCursor;
        onQueryChange(newQuery);

        // Set cursor position after the newly inserted command + space
        const newCursorPos = slashIndex + cmd.length + 1;
        setCursorPos(newCursorPos);

        // Refocus and set selection
        setTimeout(() => {
          if (inputRef.current) {
            inputRef.current.focus();
            inputRef.current.setSelectionRange(newCursorPos, newCursorPos);
          }
        }, 0);
      }
    };


    const handleSubmit = (e: FormEvent) => {
      e.preventDefault();
      if (!query.trim()) return;
      onSubmit(e);
    };

    const handleKeyDown = (_e: React.KeyboardEvent<HTMLInputElement>) => {
      // If menu is open and we hit ArrowUp/Down/Enter/Tab, let the menu handle it via its global listener
      // We just stop propagation if needed, but actually the global listener runs in capture phase so it's fine
    };

    const handleKeyUp = () => {
      if (inputRef.current) {
        const el = inputRef.current;
        const start = el.selectionStart || 0;
        setCursorPos(start);

        // Position the slash command menu near the cursor
        const textBefore = query.slice(0, start);
        const canvas = document.createElement("canvas");
        const context = canvas.getContext("2d");
        if (context) {
          const style = window.getComputedStyle(el);
          context.font = `${style.fontWeight} ${style.fontSize} ${style.fontFamily}`;
          const metrics = context.measureText(textBefore);
          const textWidth = metrics.width;

          const rect = el.getBoundingClientRect();
          const paddingLeft = parseFloat(style.paddingLeft);
          const scrollLeft = el.scrollLeft;

          setMenuPos({
            top: 0,
            left: Math.min(paddingLeft + textWidth - scrollLeft, rect.width - 200)
          });
        }
      }
    };

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      onQueryChange(e.target.value);
      setCursorPos(e.target.selectionStart || 0);
    };

    const highlightsRef = useRef<HTMLDivElement>(null);

    const handleScroll = (e: React.UIEvent<HTMLInputElement>) => {
      if (highlightsRef.current) {
        highlightsRef.current.scrollLeft = e.currentTarget.scrollLeft;
      }
    };

    const renderHighlights = () => {
      if (!query) return null;
      const parts = query.split(/(\/\w+)/g);
      return parts.map((part, i) => {
        if (part.startsWith('/') && part.match(/^\/\w+$/)) {
          return <span key={i} className="slash-command-bg">{part}</span>;
        }
        return <span key={i}>{part}</span>;
      });
    };

    return (
      <div className="query-input-text-box-section" style={{ position: 'relative' }}>
        <SlashCommandMenu
          inputValue={query}
          cursorPosition={cursorPos}
          position={menuPos}
          onSelect={handleSelectCommand}
          onClose={() => { }} // Auto-closes when conditions fail
        />

        <form onSubmit={handleSubmit} className="query-input-form" style={{ position: 'relative' }}>
          <div ref={highlightsRef} className="query-input-highlights" aria-hidden="true">
            {renderHighlights()}
          </div>
          <input
            ref={inputRef}
            className="query-input"
            type="text"
            placeholder={placeholder}
            value={query}
            onChange={handleChange}
            onKeyUp={handleKeyUp}
            onKeyDown={handleKeyDown}
            onClick={handleKeyUp as any}
            onScroll={handleScroll}
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
