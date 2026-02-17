# Claude.MD - LLM Development Guide

## Project Overview

Electron + React + Python desktop app for AI chat with screenshot and voice capabilities. Key features:
- Ollama LLM integration (default: qwen3-vl:8b-instruct) with streaming and model selection
- Screenshot capture (Alt+. hotkey, fullscreen + precision modes) with vision model processing
- Voice-to-text transcription via faster-whisper
- WebSocket-based bidirectional communication (FastAPI backend)
- REST API for model management and configuration
- SQLite chat history persistence with search
- MCP (Model Context Protocol) tool integration (demo, filesystem, websearch)
- Web search and page reading via DuckDuckGo + crawl4ai
- Always-on-top frameless window with mini mode (52x52)
- Stop streaming support for interrupting AI responses

## Architecture

```
Electron (main.ts) -> Window mgmt, Python lifecycle, IPC bridge
    |
    +---> React (src/ui/) -> WebSocket client, REST client, UI rendering
    +---> Python (source/main.py) -> FastAPI WS+REST server, Ollama, MCP
              |
              +---> database.py -> SQLite (conversations, messages, settings)
              +---> ss.py -> Screenshot capture (Alt+., tkinter overlay, DPI-aware)
              +---> transcription.py -> Voice-to-text (faster-whisper, pyaudio)
              +---> MCP servers -> stdio child processes (demo, filesystem, websearch)
              +---> ollama_provider.py -> Streaming with thinking/tool support
```

## Tech Stack

**Frontend**: React 19 + TypeScript 5.8 + Vite 6 + React Router 7 + react-markdown
**Backend**: Python 3.13+ + FastAPI + Ollama (qwen3-vl:8b-instruct) + SQLite3 + MCP
**Desktop**: Electron 37+ (frameless, always-on-top, screen-saver level)
**LLM Tools**: MCP SDK, DuckDuckGo Search, crawl4ai, trafilatura
**Voice**: faster-whisper, pyaudio
**Utils**: pynput (hotkeys), Pillow (images), tkinter (overlays), PyInstaller (bundling), UV (package manager)

## Directory Structure (Essential Paths)

```
src/
  electron/               # main.ts, pythonApi.ts, preload.ts, utils.ts
  ui/
    pages/                 # App.tsx, ChatHistory.tsx, Settings.tsx
    components/            # Layout.tsx, TitleBar.tsx, WebSocketContext.tsx
      chat/                # ChatMessage, ThinkingSection, ToolCallsDisplay, CodeBlock
      input/               # QueryInput, ModeSelector, ScreenshotChips, TokenUsagePopup
      settings/            # SettingsModels.tsx
    hooks/                 # useChatState, useScreenshots, useTokenUsage
    services/              # api.ts (REST + WS command factory)
    types/                 # index.ts (TypeScript interfaces)
    CSS/                   # Component stylesheets
source/                    # Python backend
  main.py                  # Entry point (services init, Uvicorn, port discovery)
  app.py                   # FastAPI app factory with CORS
  config.py                # Centralized constants (ports, models, limits)
  database.py              # SQLite ops (conversations, messages, settings)
  ss.py                    # Screenshot service (DPI-aware, multi-monitor)
  api/
    websocket.py           # /ws endpoint, message routing
    http.py                # /api/* REST endpoints (health, models)
    handlers.py            # WebSocket message handler logic (MessageHandler class)
  core/
    state.py               # Global mutable state (AppState singleton)
    connection.py          # WebSocket connection registry (ConnectionManager)
    lifecycle.py           # Graceful shutdown & cleanup
  services/
    conversations.py       # Chat flow orchestration (submit, resume, clear)
    screenshots.py         # Screenshot lifecycle (capture -> broadcast)
    transcription.py       # Voice-to-text via faster-whisper
  llm/
    ollama_provider.py     # Ollama streaming bridge (thinking extraction, tool fallback)
  mcp_integration/
    manager.py             # MCP server process management (McpToolManager)
    handlers.py            # Tool call routing loop (up to 30 rounds)
mcp_servers/
  client/                  # ollama_bridge.py (standalone bridge for testing)
  config/                  # servers.json (server registry)
  servers/
    demo/                  # Calculator (add, divide)
    filesystem/            # File ops (list, read, write, create, move, rename)
    websearch/             # Web search (search_web_pages, read_website)
    gmail/                 # Placeholder
    calendar/              # Placeholder
    discord/               # Placeholder
    canvas/                # Placeholder
docs/                      # Production documentation
  architecture.md          # System architecture overview
  getting-started.md       # Setup and installation guide
  development.md           # Developer guide
  api-reference.md         # WebSocket & REST API reference
  mcp-guide.md             # MCP integration guide
  configuration.md         # Configuration reference
  contributing.md          # Contributing guidelines
dist-electron/             # Compiled TS -> JS
dist-react/                # Built React app
dist-python/               # PyInstaller output (main.exe)
user_data/                 # Persistent app data (DB, screenshots)
```

## Key Files & Implementation Details

### `source/main.py` (188 lines)
**Backend Entry Point**

- `find_available_port(start_port, max_attempts)`: Probes ports 8000-8009
- `start_server()`: Initializes asyncio loop, starts MCP servers, runs Uvicorn
- `start_screenshot_service()`: Starts `ScreenshotService` in daemon thread
- `start_transcription_service()`: Initializes Whisper transcription
- `main()`: Registers signal handlers, starts all threads, keeps process alive
- Stores asyncio loop in `app_state.server_loop_holder` for cross-thread scheduling

### `source/config.py` (30 lines)
**Centralized Configuration**
- `PROJECT_ROOT`: Auto-detected project root
- `SCREENSHOT_FOLDER`: `user_data/screenshots`
- `DEFAULT_PORT`: 8000
- `DEFAULT_MODEL`: `qwen3-vl:8b-instruct`
- `MAX_MCP_TOOL_ROUNDS`: 30
- `CaptureMode` enum: fullscreen, precision, none

### `source/app.py` (45 lines)
**FastAPI App Factory**
- `create_app() -> FastAPI`: Sets up CORS (all origins for dev), mounts `/ws` and `/api` routes

### `source/api/websocket.py` (86 lines)
**WebSocket Endpoint**
- On connect: sends `ready` message + active screenshots
- Routes all incoming message types to `MessageHandler`
- Supported types: `submit_query`, `clear_context`, `remove_screenshot`, `set_capture_mode`, `stop_streaming`, `get_conversations`, `load_conversation`, `delete_conversation`, `search_conversations`, `resume_conversation`, `stop_recording`

### `source/api/handlers.py` (156 lines)
**Message Handler Logic**
- `MessageHandler` class: processes each WebSocket message type
- `_handle_submit_query`: Updates `app_state.selected_model`, launches `ConversationService.submit_query` as background task
- `_handle_stop_recording`: Uses `asyncio.to_thread` for transcription
- All handlers use `ConnectionManager.broadcast_json()` for responses

### `source/api/http.py` (98 lines)
**REST API Endpoints**
- `GET /api/health`: Health check
- `GET /api/models/ollama`: Lists locally installed Ollama models via `ollama.list()`
- `GET /api/models/enabled`: Fetches enabled models from DB settings table
- `PUT /api/models/enabled`: Persists enabled models list to DB

### `source/database.py` (367 lines)
**SQLite Operations with Thread Safety**

Critical patterns:
- `check_same_thread=False` enables FastAPI thread pool access
- JSON serialization for image arrays and settings
- `settings` table for key-value storage (e.g., enabled models)
- `model` column in messages table tracks which model generated each response

Tables:
- `conversations`: id (UUID), title, created_at, updated_at, total_input_tokens, total_output_tokens
- `messages`: num_messages (PK), conversation_id (FK), role, content, images (JSON), model, created_at
- `settings`: key (PK), value

Key functions:
- `start_new_conversation(title)`, `add_message(...)`, `get_recent_conversations(limit, offset)`
- `get_full_conversation(id)`, `add_token_usage(...)`, `get_token_usage(...)`
- `get_enabled_models()`, `set_enabled_models(...)`

### `source/core/state.py` (90 lines)
**Global Mutable State**
- `AppState` class (singleton):
  - `screenshot_list`: Active screenshots in context
  - `is_streaming` / `stop_streaming`: LLM response control flags
  - `capture_mode`: Current screenshot behavior (CaptureMode enum)
  - `chat_history`: In-memory multi-turn conversation history
  - `server_loop_holder`: Stores main asyncio loop for thread-safe scheduling
  - `selected_model`: Currently selected Ollama model

### `source/core/connection.py` (64 lines)
**WebSocket Connection Registry**
- `ConnectionManager` class: tracks active WebSocket connections
- `broadcast(message)`, `broadcast_json(type, content)`: Send to all clients

### `source/core/lifecycle.py` (97 lines)
**Shutdown & Cleanup**
- Cleans up MCP server subprocesses
- Stops screenshot hotkey listener
- Clears temporary screenshot folder

### `source/ss.py` (484 lines)
**Screenshot Service with Hotkey and Overlay**

Components:
1. `ScreenshotService`: Global hotkey listener (Alt+.)
   - Thread-safe with `_lock` (prevents concurrent captures)
   - Callbacks: `start_callback` (on capture begin), `callback` (on complete)
   - Runs in dedicated background thread
2. `RegionSelector`: Tkinter fullscreen overlay
   - Click-drag rectangle selection
   - DPI-aware coordinate transformation (Windows ctypes)
   - ESC to cancel
3. Helper functions: `take_fullscreen_screenshot()`, `take_region_screenshot()`, `create_thumbnail()`, `copy_image_to_clipboard()`

**Critical**: DPI scaling on Windows requires coordinate transformation for multi-monitor setups. Extensive Windows ctypes code handles DPI awareness.

### `source/services/conversations.py` (190 lines)
**Conversation Logic**
- `submit_query`: Handles user input, image processing, auto-screenshot (fullscreen mode), Ollama streaming, persistence, token tracking
- `resume_conversation`: Reconstructs chat state from DB, regenerates thumbnails, restores token counts
- `clear_context`: Resets state for new chat, clears screenshots
- Post-response: broadcasts `conversation_saved`, `tool_calls_summary`, clears used screenshots

### `source/services/transcription.py` (136 lines)
**Voice-to-Text Service**
- `TranscriptionService` class: uses `faster-whisper` with `base.en` model
- Records 16kHz mono audio via `pyaudio` into a queue
- Transcribes on stop, broadcasts result via WebSocket

### `source/llm/ollama_provider.py` (333 lines)
**Ollama Streaming Bridge**
- Producer-consumer pattern: background thread runs Ollama generator, main thread consumes via asyncio queue
- Separates `thinking` tokens from `content` tokens (Qwen-style reasoning support)
- Fallback: if stream is empty (tool-calling edge case), performs non-streamed `chat` call
- Handles "unexpected" tool calls that appear mid-text-stream
- Broadcasts `thinking_chunk`, `response_chunk`, and completion messages

### `source/mcp_integration/manager.py` (192 lines)
**MCP Server Manager**
- `McpToolManager`: Launches MCP servers as subprocesses via stdio transport
- Discovers tools via JSON-RPC handshake
- Converts JSON Schema to Ollama function-calling format
- Routes tool calls to correct server process
- Active servers on startup: demo, filesystem, websearch

### `source/mcp_integration/handlers.py` (155 lines)
**Tool Call Routing Loop**
- Non-streamed initial call to detect tool requests
- Executes tools via `McpToolManager`, feeds results back to Ollama
- Loops up to `MAX_MCP_TOOL_ROUNDS` (30) or until final text response
- **Skips tool detection when images are present** (vision models struggle with simultaneous tool calling)
- Broadcasts `tool_call` and `tool_result` messages to frontend

### `src/electron/main.ts` (148 lines)
**Electron Main Process**

Window config:
- 450x450 normal, 52x52 mini
- `frame: false`, `transparent: true`, `alwaysOnTop: true`, `level: 'screen-saver'`
- `skipTaskbar: true`, `setContentProtection(true)`

IPC handlers:
- `set-mini-mode`: Resizes window, repositions to top-right of previous bounds
- `focus-window`: Brings to foreground

**Python lifecycle** (prod only):
- Starts Python server on `app.whenReady()`
- Stops on `app.quit()`
- Dev mode skips (dev:pyserver script handles it)

### `src/electron/pythonApi.ts` (341 lines)
**Python Process Management**
- `startPythonServer()`: Finds available port, spawns Python/exe
- `stopPythonServer()`: Kills process and orphans
- `getServerPort()`: Returns discovered port
- Aggressive cleanup of stale processes on target ports
- Startup verification via stdout monitoring + health check

### `src/ui/pages/App.tsx` (588 lines)
**Main Chat Interface**
- **Architecture**: Modular composition using custom hooks and components
- **State**: `useChatState` (chat logic), `useScreenshots` (images), `useTokenUsage` (stats)
- **Local state**: `selectedModel`, `enabledModels`, `isRecording`
- **WebSocket handling**: thinking_chunk, response_chunk, tool_call, tool_result, conversation_resumed, screenshot_start/ready, transcription_result
- **Rendering**: Delegates to `ResponseArea` (chat history) and `QueryInput` (user interaction)

### `src/ui/pages/ChatHistory.tsx` (202 lines)
**Conversation Browser**
- WebSocket-based conversation fetching (`get_conversations`)
- Debounced search (`search_conversations`)
- Groups chats by "Today", "Yesterday", or specific dates
- Resume conversation on click

### `src/ui/pages/Settings.tsx` (85 lines)
**Tabbed Settings Interface**
- Currently implements "Models" tab
- Extensible for future settings categories

### `src/ui/components/settings/SettingsModels.tsx` (166 lines)
**Model Management UI**
- Fetches installed models via `GET /api/models/ollama`
- Fetches enabled models via `GET /api/models/enabled`
- Toggle switches to enable/disable models via `PUT /api/models/enabled`

### `src/ui/hooks/`
- **`useChatState.ts`**: Core chat logic. Manages `chatHistory` array, streaming buffers (thinking, response), `toolCalls`, status, and refs.
- **`useScreenshots.ts`**: Manages screenshot carousel, `captureMode`, and `screenshotsRef`.
- **`useTokenUsage.ts`**: Tracks cumulative token usage (input, output, total, limit).

### `src/ui/services/api.ts` (191 lines)
**API Client**
- Singleton `api` object with REST fetch wrappers (`getOllamaModels`, `getEnabledModels`, `setEnabledModels`)
- `createApiService()`: Factory for WS-based commands (`submitQuery`, `clearContext`, etc.)

### `src/ui/types/index.ts` (134 lines)
**TypeScript Interfaces**
- `ChatMessage`, `ToolCall`, `Screenshot`, `TokenUsage`, `WebSocketMessage`
- Global `Window` interface for `electronAPI`

### `src/ui/components/chat/`
- **`ChatMessage.tsx`**: Individual message rendering with markdown
- **`ThinkingSection.tsx`**: Collapsible reasoning display
- **`ToolCallsDisplay.tsx`**: MCP tool execution cards with human-readable labels and collapsible results
- **`CodeBlock.tsx`**: Syntax-highlighted code blocks

### `src/ui/components/input/`
- **`QueryInput.tsx`**: User input with screenshot attachments
- **`ModeSelector.tsx`**: Screenshot capture mode selector
- **`ScreenshotChips.tsx`**: Screenshot thumbnail chips with remove
- **`TokenUsagePopup.tsx`**: Context window usage indicator

### MCP Servers

#### `mcp_servers/servers/demo/server.py` (67 lines)
**Reference implementation**: `add(a, b)`, `divide(a, b)`

#### `mcp_servers/servers/filesystem/server.py` (255 lines)
**File system tools** with path-traversal protection:
- `list_directory`, `read_file`, `write_file`, `create_folder`, `move_file`, `rename_file`
- `_get_safe_path()`: Validates paths against `BASE_PATH`

#### `mcp_servers/servers/websearch/server.py` (145 lines)
**Web search + page reading**:
- `search_web_pages(query)`: DuckDuckGo search returning URLs + snippets
- `read_website(url)`: Async crawl4ai with stealth mode (rotating UAs, noise reduction, randomized timing)
- Falls back to trafilatura for content extraction

#### Placeholder servers: `gmail/`, `calendar/`, `discord/`, `canvas/` (skeleton files)

## Development Commands

```bash
npm run dev                # Full dev mode (all services in parallel)
npm run dev:react          # Vite dev server (port 5123)
npm run dev:electron       # Electron app
npm run dev:pyserver       # Python FastAPI (via uv run)
npm run build              # Full build (Python exe + React + Electron)
npm run dist:win           # Windows installer (NSIS + portable)
npm run install:python     # Install Python deps via UV
uv sync --group dev        # Install all Python deps (fast!)
uv add <package>           # Add a new Python dependency
```

## MCP (Model Context Protocol) Integration

**Purpose**: Give LLM access to external tools via stdio child processes (JSON-RPC).

### How Tool Calls Work
1. User query -> Backend performs non-streamed Ollama call to detect tool requests
2. Ollama returns `tool_call` if needed
3. Backend routes via `McpToolManager` to correct server subprocess
4. Server executes tool, returns result via JSON-RPC
5. Result fed back to Ollama -> loop continues (up to 30 rounds)
6. Final text response is streamed to user
7. Tool detection is skipped when images are present

### Adding New MCP Tools (3 Steps)

**Step 1**: Create `mcp_servers/servers/<name>/server.py`
```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("ToolName")

@mcp.tool()
def function_name(param: str) -> str:
    """LLM-visible description of when to use this tool."""
    return f"Result: {param}"

if __name__ == "__main__":
    mcp.run()
```

**Step 2**: Register in `source/main.py` -> `_init_mcp_servers()`
```python
await _mcp_manager.connect_server(
    "tool_name",
    sys.executable,
    [str(PROJECT_ROOT / "mcp_servers" / "servers" / "tool_name" / "server.py")]
)
```

**Step 3**: Add to `mcp_servers/config/servers.json` and restart app

### Current Servers
- **demo**: add, divide (reference implementation)
- **filesystem**: list_directory, read_file, write_file, create_folder, move_file, rename_file
- **websearch**: search_web_pages, read_website
- Placeholders: gmail, calendar, discord, canvas

### Debugging
- Check `[MCP]` logs in console for server registration
- Test standalone: `python -m mcp_servers.servers.demo.server`
- Tool calls show as cards in UI with arguments, results, and server name

## WebSocket Protocol

The WebSocket connection at `ws://localhost:8000/ws` uses JSON messages with `type` and `content` fields.

### Client -> Server Messages

```json
{"type": "submit_query", "content": "Your question", "model": "qwen3-vl:8b-instruct"}
{"type": "clear_context"}
{"type": "stop_streaming"}
{"type": "set_capture_mode", "mode": "fullscreen | precision | none"}
{"type": "remove_screenshot", "screenshot_id": "ss_1"}
{"type": "get_conversations", "limit": 50, "offset": 0}
{"type": "load_conversation", "conversation_id": "uuid-string"}
{"type": "resume_conversation", "conversation_id": "uuid-string"}
{"type": "search_conversations", "query": "search terms"}
{"type": "delete_conversation", "conversation_id": "uuid-string"}
{"type": "stop_recording"}
```

### Server -> Client Messages

```json
{"type": "ready", "content": "Server ready..."}
{"type": "screenshot_start", "content": "Screenshot capture starting"}
{"type": "screenshot_added", "content": "{\"id\": \"ss_1\", \"name\": \"...\", \"thumbnail\": \"data:image/png;base64,...\"}"}
{"type": "screenshot_removed", "content": "{\"id\": \"ss_1\"}"}
{"type": "screenshots_cleared", "content": ""}
{"type": "query", "content": "User's question"}
{"type": "thinking_chunk", "content": "...partial thinking..."}
{"type": "thinking_complete", "content": ""}
{"type": "response_chunk", "content": "...partial response..."}
{"type": "response_complete", "content": ""}
{"type": "tool_call", "content": "{\"name\": \"...\", \"arguments\": {...}, \"server\": \"...\"}"}
{"type": "tool_result", "content": "{\"name\": \"...\", \"result\": \"...\", \"server\": \"...\"}"}
{"type": "tool_calls_summary", "content": "[...]"}
{"type": "context_cleared", "content": "Context cleared..."}
{"type": "conversation_saved", "content": "{\"conversation_id\": \"uuid\"}"}
{"type": "conversations_list", "content": "[...]"}
{"type": "conversation_loaded", "content": "{...}"}
{"type": "conversation_resumed", "content": "{...}"}
{"type": "conversation_deleted", "content": "{\"conversation_id\": \"uuid\"}"}
{"type": "token_update", "content": "{\"input\": 123, \"output\": 456, \"total\": 579}"}
{"type": "transcription_result", "content": "Transcribed text"}
{"type": "error", "content": "Error message"}
```

## Database Schema

```sql
CREATE TABLE conversations (
    id TEXT PRIMARY KEY,              -- UUID
    title TEXT,                       -- Auto-generated from first message
    created_at REAL,
    updated_at REAL,                  -- Updated on every new message
    total_input_tokens INTEGER DEFAULT 0,
    total_output_tokens INTEGER DEFAULT 0
);

CREATE TABLE messages (
    num_messages INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT,             -- FK to conversations.id
    role TEXT,                        -- 'user' or 'assistant'
    content TEXT,                     -- Message text
    images TEXT,                      -- JSON array of base64 strings
    model TEXT,                       -- Model used for this response
    created_at REAL
);

CREATE TABLE settings (
    key TEXT PRIMARY KEY,
    value TEXT                        -- JSON-serialized value
);
```

## Common Development Tasks

### Add New UI Page
1. Create `src/ui/pages/<PageName>.tsx`
2. Add route in `src/ui/main.tsx` using `createHashRouter`
3. Add CSS in `src/ui/CSS/<PageName>.css`

### Add New WebSocket Message Type
1. Backend: Add handler method in `source/api/handlers.py` (MessageHandler class)
2. Backend: Add routing case in `source/api/websocket.py`
3. Frontend: Add case in `App.tsx` WebSocket message handler

### Add New REST Endpoint
1. Backend: Add route in `source/api/http.py`
2. Frontend: Add client method in `src/ui/services/api.ts`

### Add New MCP Tool
See MCP section above and `docs/mcp-guide.md`.

### Modify Database Schema
1. Edit `_init_db()` in database.py
2. Add migration: `try: cursor.execute("ALTER TABLE...") except sqlite3.OperationalError: pass`
3. Update read/write methods
4. Update `src/ui/types/index.ts` if frontend is affected

### Change Ollama Model
1. `ollama pull model-name`
2. Update `DEFAULT_MODEL` in `source/config.py`
3. Verify tool support (not all models support function calling)
4. Test with images if using a vision model

## Architecture Decisions (Critical for LLMs)

**Why `check_same_thread=False` in SQLite?**
FastAPI uses thread pools; SQLite needs multi-thread access.

**Why refs in React hooks?**
WebSocket callbacks capture stale state; refs ensure current values in async operations.

**Why `server_loop_holder`?**
Windows Proactor loop can't be accessed from other threads; we schedule coroutines via `asyncio.run_coroutine_threadsafe()`.

**Why stdio transport for MCP?**
Standard MCP protocol; enables child process isolation and language-agnostic servers.

**Why PyInstaller?**
Bundles Python + deps into single exe for production distribution.

**Why Electron `screen-saver` level?**
Ensures always-on-top even above full-screen apps.

**Why DPI scaling in ss.py?**
Windows multi-monitor setups require coordinate transformation via ctypes for accurate region selection.

**Why skip tool detection with images?**
Vision models often struggle with simultaneous tool calling and image analysis; separating concerns improves reliability.

**Why producer-consumer pattern in ollama_provider.py?**
Ollama's synchronous generator runs in a background thread; the main async thread consumes chunks via an asyncio queue for non-blocking streaming.

**Why non-streamed initial call for tool detection?**
Streaming responses can't reliably indicate tool calls; a quick non-streamed check determines if tools are needed before switching to streamed mode.

---

*Last updated: February 17 2026 | Version: 0.1.0*
