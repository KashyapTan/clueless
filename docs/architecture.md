# Architecture

This document provides a detailed overview of the Clueless system architecture, covering the three main layers (Electron, React, Python) and how they communicate.

## High-Level Overview

Clueless is a desktop application built on three independent layers that communicate through well-defined interfaces:

```
+---------------------------+
|        Electron           |  Window management, Python lifecycle, IPC bridge
|     (src/electron/)       |
+---------------------------+
          |          |
          v          v
+-------------+  +------------------+
|   React UI  |  |  Python Backend  |
| (src/ui/)   |  |  (source/)       |
+-------------+  +------------------+
     |  WebSocket (ws://localhost:8000/ws)  |
     +<----------------------------------->+
                                |
                    +-----------+-----------+
                    |           |           |
                    v           v           v
                 LLMs       SQLite      MCP Servers
           (Ollama/Cloud)    (DB)      (child processes)
```

## Layer Details

### 1. Electron Layer (`src/electron/`)

The Electron layer manages the desktop application shell:

| File | Responsibility |
|------|---------------|
| `main.ts` | Window creation, IPC handlers, Python server lifecycle |
| `preload.ts` | Secure bridge exposing `electronAPI` to the renderer |
| `pythonApi.ts` | Python process management (start, stop, port discovery, cleanup) |
| `utils.ts` | Environment detection (`isDev()`) |

**Window Configuration:**
- Frameless, transparent window (`frame: false`, `transparent: true`)
- Always-on-top at `screen-saver` level (stays above full-screen apps)
- Content protection enabled (`setContentProtection(true)`)
- Normal mode: 450x450 | Mini mode: 52x52
- `skipTaskbar: true` for minimal desktop footprint

**IPC Channels:**
- `set-mini-mode` - Toggles between normal and mini window sizes
- `focus-window` - Programmatically brings the window to foreground

**Python Lifecycle (Production):**
1. On `app.whenReady()`, spawns the bundled Python executable
2. Monitors stdout for "Application startup complete"
3. Performs health check on the discovered port
4. On `app.quit()`, terminates the Python process and cleans up orphaned processes

### 2. React Frontend (`src/ui/`)

The frontend follows a modular architecture with custom hooks for state management:

```
src/ui/
  main.tsx                    # HashRouter setup (/, /settings, /history, /album)
  pages/
    App.tsx                   # Main chat interface
    ChatHistory.tsx           # Conversation browser with search
    Settings.tsx              # Tabbed settings interface
  components/
    Layout.tsx                # App shell with mini mode transitions
    TitleBar.tsx              # Custom draggable title bar
    WebSocketContext.tsx      # WebSocket provider
    chat/
      ChatMessage.tsx         # Individual message rendering
      ThinkingSection.tsx     # Collapsible reasoning display
      ToolCallsDisplay.tsx    # MCP tool execution cards
      CodeBlock.tsx           # Syntax-highlighted code blocks
      ResponseArea.tsx        # Chat history display area
    input/
      QueryInput.tsx          # User input with attachments
      ModeSelector.tsx        # Screenshot mode selector
      ScreenshotChips.tsx     # Screenshot thumbnail chips
      TokenUsagePopup.tsx     # Context window usage indicator
    settings/
      SettingsModels.tsx      # Model toggle UI
      SettingsApiKey.tsx      # API key management (Anthropic/OpenAI/Gemini)
      SettingsConnections.tsx # Google OAuth connection card
      SettingsTools.tsx       # Semantic tool retrieval configuration
  hooks/
    useChatState.ts           # Chat history, streaming, status
    useScreenshots.ts         # Screenshot context management
    useTokenUsage.ts          # Token tracking
  services/
    api.ts                    # REST API client + WS command factory
  types/
    index.ts                  # TypeScript interfaces
  CSS/                        # Component stylesheets
    App.css
    ChatHistory.css
    Settings.css
    SettingsApiKey.css
    SettingsConnections.css
    SettingsModels.css
    SettingsTools.css
```

**State Management Pattern:**
- Custom hooks (`useChatState`, `useScreenshots`, `useTokenUsage`) manage domain-specific state
- `useRef` is used alongside `useState` to avoid stale closures in WebSocket callbacks
- No external state library (Redux, Zustand) -- hooks and context are sufficient

**Communication:**
- Real-time operations (chat, streaming, history) use WebSocket
- Configuration operations (model management, keys, auth) use REST API
- Electron IPC for window management only

### 3. Python Backend (`source/`)

The backend is a FastAPI application serving both WebSocket and REST endpoints:

```
source/
  main.py                     # Entry point: service init, Uvicorn launch
  app.py                      # FastAPI app factory with CORS
  config.py                   # Centralized constants (ports, models, limits)
  database.py                 # SQLite operations (thread-safe)
  ss.py                       # Screenshot capture (hotkey, overlay, DPI)
  api/
    websocket.py              # /ws endpoint, message routing
    http.py                   # /api/* REST endpoints
    handlers.py               # WebSocket message handler logic
  core/
    state.py                  # Global mutable state (AppState)
    connection.py             # WebSocket connection registry
    lifecycle.py              # Graceful shutdown & cleanup
    thread_pool.py            # Async execution helper
  services/
    conversations.py          # Chat flow orchestration
    screenshots.py            # Screenshot lifecycle management
    transcription.py          # Voice-to-text (faster-whisper)
    google_auth.py            # Google OAuth 2.0 flow manager
  llm/
    router.py                 # Routes requests to Ollama or Cloud providers
    ollama_provider.py        # Ollama streaming bridge with tool support
    cloud_provider.py         # Anthropic/OpenAI/Gemini streaming
    key_manager.py            # Encrypted API key storage
  mcp_integration/
    manager.py                # MCP server process management
    retriever.py              # Semantic tool retrieval (Top-K selection)
    handlers.py               # Tool call routing loop
    cloud_tool_handlers.py    # Tool calling for cloud providers
```

**Key Patterns:**
- `AppState` (singleton) holds all mutable state, shared across threads
- `server_loop_holder` stores the asyncio event loop for cross-thread scheduling (hotkey thread -> WebSocket thread)
- `find_available_port()` probes ports 8000-8009 to avoid conflicts
- Thread-safe SQLite with `check_same_thread=False`
- **Hybrid LLM Support**: Routes requests between local Ollama and cloud APIs (Anthropic, OpenAI, Gemini) dynamically based on the selected model.

## Data Flow

### Chat Query Flow

```
User types message
       |
       v
React (App.tsx) --[WS: submit_query]--> Python (websocket.py)
       |                                        |
       |                                        v
       |                              handlers.py: _handle_submit_query
       |                                        |
       |                                        v
       |                              conversations.py: submit_query
       |                                        |
       |                                        v
       |                              router.py: route_chat
       |                               /              \
       |                       (Ollama)                (Cloud: Anthropic/OpenAI/Gemini)
       |                          |                        |
       |                          v                        v
       |                 ollama_provider.py          cloud_provider.py
       |                  + Tool Detection            + Tool Detection
       |                          |                        |
       |                          v                        v
       |                 MCP Manager / Handlers      Cloud Tool Handlers
       |                          |                        |
       |                          v                        v
       |                     Tool Execution           Tool Execution
       |                     (MCP Servers)            (MCP Servers)
       |                          |                        |
       |                          v                        v
       |                   Stream Response          Stream Response
       |                          |                        |
       |                          +-----------+------------+
       |                                      |
       |                                      v
       |                              Save to SQLite
       |                              Clear screenshots
       |                                      |
       v                                      v
React receives WS messages:         Broadcast results
  - thinking_chunk                   - conversation_saved
  - response_chunk                   - tool_calls_summary
  - tool_call / tool_result          - token_update
  - response_complete
```

### Screenshot Flow

```
User presses Alt+. (or UI trigger)
       |
       v
ss.py: ScreenshotService (background thread)
       |
       v
RegionSelector (Tkinter overlay)
  - DPI-aware coordinate transform
  - Click-drag rectangle selection
       |
       v
Capture image, generate thumbnail
       |
       v
screenshots.py: on_screenshot_captured
  - Add to app_state.screenshot_list
  - Schedule WS broadcast via server_loop_holder
       |
       v
React receives: screenshot_added
  - Display thumbnail chip in input area
```

### MCP Tool Call Flow

```
LLM (Ollama or Cloud) returns tool_call
       |
       v
mcp_integration/handlers.py (or cloud_tool_handlers.py)
  - Extract tool name + arguments
  - Broadcast "tool_call" to frontend
       |
       v
mcp_integration/retriever.py
  - Semantically select relevant tools for the next round (if enabled)
       |
       v
mcp_integration/manager.py
  - Route to correct MCP server subprocess (e.g., 'filesystem', 'gmail')
  - Execute via JSON-RPC over stdio
       |
       v
MCP Server (child process)
  - Runs tool function (e.g., read_email, list_files)
  - Returns result
       |
       v
handlers.py
  - Broadcast "tool_result" to frontend
  - Feed result back to LLM
  - Loop continues (up to MAX_MCP_TOOL_ROUNDS)
       |
       v
LLM generates final response
```

## Database Schema

```sql
CREATE TABLE conversations (
    id TEXT PRIMARY KEY,                    -- UUID v4
    title TEXT,                             -- Auto-generated from first message
    created_at REAL,                        -- Unix timestamp
    updated_at REAL,                        -- Updated on each new message
    total_input_tokens INTEGER DEFAULT 0,
    total_output_tokens INTEGER DEFAULT 0
);

CREATE TABLE messages (
    num_messages INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT,                   -- FK to conversations.id
    role TEXT,                              -- 'user' or 'assistant'
    content TEXT,                           -- Message text
    images TEXT,                            -- JSON array of base64 image strings
    model TEXT,                             -- Model used for this message
    created_at REAL                         -- Unix timestamp
);

CREATE TABLE settings (
    key TEXT PRIMARY KEY,                   -- Setting identifier
    value TEXT                              -- JSON-serialized value
);
```

**Key Settings Stored:**
- `enabled_models`: List of active models
- `api_key_anthropic`: Encrypted API key
- `api_key_openai`: Encrypted API key
- `api_key_gemini`: Encrypted API key
- `encryption_salt`: Per-install salt for key encryption
- `tool_always_on`: List of tool names to always include in context
- `tool_retriever_top_k`: Number of semantic matches for tool retrieval

## Technology Stack

| Layer | Technologies |
|-------|-------------|
| **Desktop** | Electron 37+, frameless transparent window |
| **Frontend** | React 19, TypeScript 5.8, Vite 6, React Router 7, react-markdown |
| **Backend** | Python 3.13+, FastAPI, Uvicorn, asyncio |
| **LLM (Local)** | Ollama (default: qwen3-vl:8b-instruct) |
| **LLM (Cloud)** | Anthropic (Claude), OpenAI (GPT/o1), Google (Gemini) |
| **Database** | SQLite3 (thread-safe) |
| **Security** | Fernet encryption (cryptography) for API keys |
| **MCP** | Model Context Protocol SDK, stdio transport |
| **Screenshots** | pynput (hotkeys), Pillow (images), tkinter (overlay) |
| **Transcription** | faster-whisper, pyaudio |
| **Auth** | Google OAuth 2.0 (Gmail/Calendar integration) |
| **Web Search** | DuckDuckGo Search (ddgs), crawl4ai, trafilatura |
| **Build** | PyInstaller (Python), electron-builder (desktop), UV (package manager) |
