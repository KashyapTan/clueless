/**
 * API Service.
 * 
 * Abstraction layer for communicating with the Python backend.
 * Currently uses WebSocket, but can be extended to support HTTP REST APIs.
 * 
 * ## How to Add a New API Endpoint
 * 
 * ### For WebSocket-based APIs (real-time, bidirectional):
 * 
 * 1. Add a new method to this ApiService class
 * 2. The method should call `this.send()` with the appropriate message type
 * 3. Handle the response in the WebSocket message handler (useWebSocket hook)
 * 
 * ### For HTTP REST APIs (request/response, one-time):
 * 
 * 1. Add a new method that uses fetch() to call your Python endpoint
 * 2. In Python, add a new route in `source/api/http.py` (create if needed)
 * 3. Register the route in `source/app.py`
 * 
 * ### Example: Adding an HTTP REST API
 * 
 * **Frontend (this file):**
 * ```typescript
 * async getModels(): Promise<string[]> {
 *   const response = await fetch(`${HTTP_BASE_URL}/api/models`);
 *   return response.json();
 * }
 * ```
 * 
 * **Backend (source/api/http.py):**
 * ```python
 * from fastapi import APIRouter
 * 
 * router = APIRouter(prefix="/api")
 * 
 * @router.get("/models")
 * async def get_models():
 *     return ["qwen3-vl:8b-instruct", "llama3.2"]
 * ```
 * 
 * **Register in app.py:**
 * ```python
 * from .api.http import router as http_router
 * app.include_router(http_router)
 * ```
 */

const WS_BASE_URL = 'ws://localhost:8000';
const HTTP_BASE_URL = 'http://localhost:8000';

export interface ApiService {
  // WebSocket methods
  submitQuery: (query: string, captureMode: string) => void;
  clearContext: () => void;
  removeScreenshot: (id: string) => void;
  setCaptureMode: (mode: string) => void;
  stopStreaming: () => void;
  getConversations: (limit?: number, offset?: number) => void;
  searchConversations: (query: string) => void;
  resumeConversation: (conversationId: string) => void;
  deleteConversation: (conversationId: string) => void;
  
  // HTTP methods (examples for future use)
  // getModels: () => Promise<string[]>;
  // getHealth: () => Promise<{ status: string }>;
}

/**
 * Creates an API service bound to a WebSocket send function.
 */
export function createApiService(send: (message: Record<string, unknown>) => void): ApiService {
  return {
    submitQuery(query: string, captureMode: string) {
      send({
        type: 'submit_query',
        content: query,
        capture_mode: captureMode,
      });
    },

    clearContext() {
      send({ type: 'clear_context' });
    },

    removeScreenshot(id: string) {
      send({ type: 'remove_screenshot', id });
    },

    setCaptureMode(mode: string) {
      send({ type: 'set_capture_mode', mode });
    },

    stopStreaming() {
      send({ type: 'stop_streaming' });
    },

    getConversations(limit = 50, offset = 0) {
      send({ type: 'get_conversations', limit, offset });
    },

    searchConversations(query: string) {
      send({ type: 'search_conversations', query });
    },

    resumeConversation(conversationId: string) {
      send({ type: 'resume_conversation', conversation_id: conversationId });
    },

    deleteConversation(conversationId: string) {
      send({ type: 'delete_conversation', conversation_id: conversationId });
    },

    // HTTP API examples (uncomment and implement as needed):
    // async getModels() {
    //   const response = await fetch(`${HTTP_BASE_URL}/api/models`);
    //   if (!response.ok) throw new Error('Failed to fetch models');
    //   return response.json();
    // },
    //
    // async getHealth() {
    //   const response = await fetch(`${HTTP_BASE_URL}/health`);
    //   if (!response.ok) throw new Error('Health check failed');
    //   return response.json();
    // },
  };
}

// Singleton for direct imports (when WebSocket context is not needed)
export const api = {
  HTTP_BASE_URL,
  WS_BASE_URL,
  
  /**
   * Fetch all Ollama models installed on the user's machine.
   * Calls GET /api/models/ollama on the Python backend,
   * which in turn calls `ollama.list()`.
   */
  async getOllamaModels(): Promise<{ name: string; size: number; parameter_size: string; quantization: string }[]> {
    try {
      const response = await fetch(`${HTTP_BASE_URL}/api/models/ollama`);
      if (!response.ok) throw new Error('Failed to fetch Ollama models');
      return response.json();
    } catch {
      return [];
    }
  },

  /**
   * Fetch the list of model names the user has toggled on.
   * Calls GET /api/models/enabled which reads from the SQLite settings table.
   */
  async getEnabledModels(): Promise<string[]> {
    try {
      const response = await fetch(`${HTTP_BASE_URL}/api/models/enabled`);
      if (!response.ok) throw new Error('Failed to fetch enabled models');
      return response.json();
    } catch {
      return [];
    }
  },

  /**
   * Save the full list of enabled model names.
   * Calls PUT /api/models/enabled which writes to the SQLite settings table.
   */
  async setEnabledModels(models: string[]): Promise<void> {
    try {
      await fetch(`${HTTP_BASE_URL}/api/models/enabled`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ models }),
      });
    } catch {
      console.error('Failed to save enabled models');
    }
  },

  /**
   * Check if the server is healthy.
   */
  async healthCheck(): Promise<boolean> {
    try {
      const response = await fetch(`${HTTP_BASE_URL}/health`);
      return response.ok;
    } catch {
      return false;
    }
  },
};
