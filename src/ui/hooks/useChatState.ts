/**
 * Chat state management hook.
 * 
 * Manages chat history, current query/response, and conversation state.
 */
import { useState, useRef, useCallback } from 'react';
import type { ChatMessage, ToolCall } from '../types';

interface UseChatStateReturn {
  // State
  chatHistory: ChatMessage[];
  currentQuery: string;
  response: string;
  thinking: string;
  isThinking: boolean;
  thinkingCollapsed: boolean;
  toolCalls: ToolCall[];
  conversationId: string | null;
  query: string;
  canSubmit: boolean;
  status: string;
  error: string;
  
  // Refs for WebSocket callbacks
  currentQueryRef: React.RefObject<string>;
  responseRef: React.RefObject<string>;
  thinkingRef: React.RefObject<string>;
  toolCallsRef: React.RefObject<ToolCall[]>;
  
  // Actions
  setQuery: React.Dispatch<React.SetStateAction<string>>;
  setCanSubmit: (canSubmit: boolean) => void;
  setStatus: (status: string) => void;
  setError: (error: string) => void;
  setThinkingCollapsed: (collapsed: boolean) => void;
  setIsThinking: (isThinking: boolean) => void;
  appendThinking: (chunk: string) => void;
  appendResponse: (chunk: string) => void;
  addToolCall: (toolCall: ToolCall) => void;
  updateToolCall: (toolCall: ToolCall) => void;
  startQuery: (query: string) => void;
  completeResponse: (attachedImages?: Array<{name: string; thumbnail: string}>, model?: string) => void;
  resetForNewChat: () => void;
  loadConversation: (id: string, messages: ChatMessage[]) => void;
  setConversationId: (id: string | null) => void;
}

const DEFAULT_TOKEN_LIMIT = 128000;

export function useChatState(): UseChatStateReturn {
  // UI State
  const [query, setQuery] = useState('');
  const [response, setResponse] = useState('');
  const [thinking, setThinking] = useState('');
  const [isThinking, setIsThinking] = useState(false);
  const [thinkingCollapsed, setThinkingCollapsed] = useState(true);
  const [toolCalls, setToolCalls] = useState<ToolCall[]>([]);
  const [status, setStatus] = useState('Connecting to server...');
  const [error, setError] = useState('');
  const [canSubmit, setCanSubmit] = useState(false);
  
  // Chat State
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [currentQuery, setCurrentQuery] = useState('');
  const [conversationId, setConversationId] = useState<string | null>(null);
  
  // Refs for WebSocket callbacks (avoid stale closures)
  const currentQueryRef = useRef('');
  const responseRef = useRef('');
  const thinkingRef = useRef('');
  const toolCallsRef = useRef<ToolCall[]>([]);

  const appendThinking = useCallback((chunk: string) => {
    setThinking(prev => prev + chunk);
    thinkingRef.current += chunk;
  }, []);

  const appendResponse = useCallback((chunk: string) => {
    setResponse(prev => prev + chunk);
    responseRef.current += chunk;
  }, []);

  const addToolCall = useCallback((toolCall: ToolCall) => {
    setToolCalls(prev => [...prev, toolCall]);
    toolCallsRef.current = [...toolCallsRef.current, toolCall];
  }, []);

  const updateToolCall = useCallback((updatedToolCall: ToolCall) => {
    setToolCalls(prev => prev.map(tc => 
      (tc.name === updatedToolCall.name && JSON.stringify(tc.args) === JSON.stringify(updatedToolCall.args)) 
        ? { ...tc, ...updatedToolCall } 
        : tc
    ));
    
    // Update ref as well
    toolCallsRef.current = toolCallsRef.current.map(tc => 
       (tc.name === updatedToolCall.name && JSON.stringify(tc.args) === JSON.stringify(updatedToolCall.args))
        ? { ...tc, ...updatedToolCall }
        : tc
    );
  }, []);

  const startQuery = useCallback((queryText: string) => {
    setCurrentQuery(queryText);
    currentQueryRef.current = queryText;
    setError('');
    setStatus('Thinking...');
    setIsThinking(true);
    setCanSubmit(false);
    // Reset tool calls for new query
    setToolCalls([]);
    toolCallsRef.current = [];
  }, []);

  const completeResponse = useCallback((attachedImages?: Array<{name: string; thumbnail: string}>, model?: string) => {
    const completedQuery = currentQueryRef.current;
    const completedResponse = responseRef.current;
    const completedThinking = thinkingRef.current;
    const completedToolCalls = toolCallsRef.current.length > 0 ? [...toolCallsRef.current] : undefined;

    // Add to chat history
    setChatHistory(prev => [
      ...prev,
      { 
        role: 'user', 
        content: completedQuery, 
        images: attachedImages && attachedImages.length > 0 ? attachedImages : undefined 
      },
      { 
        role: 'assistant', 
        content: completedResponse, 
        thinking: completedThinking || undefined, 
        toolCalls: completedToolCalls,
        model: model
      }
    ]);

    // Reset current state
    setResponse('');
    setThinking('');
    setCurrentQuery('');
    setToolCalls([]);
    
    // Reset refs
    currentQueryRef.current = '';
    responseRef.current = '';
    thinkingRef.current = '';
    toolCallsRef.current = [];
    
    setStatus('Ready for follow-up question.');
    setCanSubmit(true);
  }, []);

  const resetForNewChat = useCallback(() => {
    setStatus('Context cleared. Ready for new conversation.');
    setResponse('');
    setThinking('');
    setIsThinking(false);
    setThinkingCollapsed(true);
    setToolCalls([]);
    setError('');
    setQuery('');
    setCurrentQuery('');
    setChatHistory([]);
    setCanSubmit(true);
    setConversationId(null);
    
    // Reset refs
    currentQueryRef.current = '';
    responseRef.current = '';
    thinkingRef.current = '';
    toolCallsRef.current = [];
  }, []);

  const loadConversation = useCallback((id: string, messages: ChatMessage[]) => {
    setConversationId(id);
    setChatHistory(messages);
    setResponse('');
    setThinking('');
    setCurrentQuery('');
    
    // Reset refs
    currentQueryRef.current = '';
    responseRef.current = '';
    thinkingRef.current = '';
    
    setStatus('Conversation loaded. Ask a follow-up question.');
    setCanSubmit(true);
  }, []);

  return {
    // State
    chatHistory,
    currentQuery,
    response,
    thinking,
    toolCalls,
    isThinking,
    thinkingCollapsed,
    conversationId,
    query,
    canSubmit,
    status,
    error,
    
    // Refs
    currentQueryRef,
    responseRef,
    thinkingRef,
    toolCallsRef,
    
    // Actions
    setQuery,
    setCanSubmit,
    setStatus,
    setError,
    setThinkingCollapsed,
    setIsThinking,
    appendThinking,
    appendResponse,
    addToolCall,
    updateToolCall,
    startQuery,
    completeResponse,
    resetForNewChat,
    loadConversation,
    setConversationId,
  };
}
