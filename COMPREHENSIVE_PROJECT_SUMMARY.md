# CLAUDE.md - Clueless Project Documentation

This file provides guidance to Claude Code (claude.ai/code) when working with this codebase.

## Project Overview

**Clueless** is an AI-powered desktop assistant built with Electron, React, and Python. It provides a floating, always-on-top window that allows users to:
- Chat with an LLM (Ollama) with or without screenshots
- Take region-selective screenshots via hotkey (Ctrl+Shift+Alt+S)
- Stream AI responses in real-time via WebSocket
- Multi-turn conversations with **persistent chat history** (SQLite database)
- Multiple capture modes (fullscreen, region, meeting recording)
- **MCP (Model Context Protocol)** integration for extensible tool calling
- **Token usage tracking** with visual indicators
- **Mini mode** - collapsible to a 52×52 logo in the corner
- **Multiple screenshot support** - attach multiple images before querying
- **Chat history browser** - search, load, and delete past conversations
- **Settings page** - model configuration and MCP connections (UI scaffolded)

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Electron Main Process                             │
│  (src/electron/main.ts)                                              │
│  - Creates frameless, transparent, always-on-top window             │
│  - Manages Python server lifecycle (prod only)                      │
│  - Content protection enabled, skips taskbar                        │
│  - Mini mode toggle (52×52 ↔ 450×450)                               │
└────────────────────┬────────────────────────────────────────────────┘
                     │
         ┌───────────┴───────────┐
         ▼                       ▼
┌─────────────────────┐  ┌──────────────────────────────────────────┐
│   React Frontend    │  │         Python Backend                    │
│   (src/ui/)         │◄─┤         (source/)                         │
│                     │  │                                           │
│ - App.tsx          │  │ - main.py: FastAPI WebSocket server       │
│ - ChatHistory.tsx   │  │ - database.py: SQLite chat persistence    │
│ - Settings.tsx      │  │ - ss.py: Screenshot service               │
│ - MeetingAlbum.tsx  │  │ - Ollama integration (qwen3-vl:8b)        │
│ - Token indicators  │  │ - Multi-turn chat history                 │
│ - WebSocket client  │  │ - MCP tool manager (stdio transport)      │
└─────────────────────┘  └───────────────┬───────────────────────────┘
         │                               │
         │    WebSocket (ws://localhost:8000/ws)
         └───────────────────────────────┘
                                         │
                    ┌────────────────────┴────────────────────┐
                    ▼                                         ▼
         ┌───────────────────────┐              ┌────────────────────────┐
         │  MCP Server Processes │              │  SQLite Database       │
         │  (mcp_servers/)       │              │  (user_data/)          │
         │                       │              │                        │
         │  - demo (add/divide)  │              │  - conversations       │
         │  - filesystem         │              │  - messages            │
         │  - gmail (placeholder)│              │  - screenshots         │
         │  - discord (...)      │              │  - token counts        │
         │  - websearch (...)    │              └────────────────────────┘
         │  - canvas (...)       │
         │  - calendar (...)     │
         └───────────────────────┘
```

## Tech Stack

### Frontend
- **React 19** with TypeScript
- **React Router DOM 7** for page navigation (App, Settings, ChatHistory, MeetingAlbum)
- **Vite 6** for bundling
- **react-markdown** + **react-syntax-highlighter** for rendering AI responses
- WebSocket for real-time bidirectional communication

### Backend
- **Python 3.11+** with FastAPI
- **Ollama** for LLM inference (uses `qwen3-vl:8b-instruct` for vision + text)
- **SQLite3** for persistent chat history and conversation management
- **MCP (Model Context Protocol)** for extensible tool calling
- **pynput** for global hotkey detection (Ctrl+Shift+Alt+S)
- **Pillow** (PIL) for screenshot capture and thumbnail generation
- **tkinter** for region selection overlay UI
- **PyInstaller** for packaging Python code into standalone executable

### Desktop
- **Electron 37+** for cross-platform desktop app
- Frameless, transparent window with always-on-top (`screen-saver` level)
- Content protection enabled (prevents screen capture of the window itself)
- Skips taskbar for non-intrusive operation
- IPC bridge for mini mode and window focus control

## Directory Structure

```
clueless/
├── src/
│   ├── electron/           # Electron main process
│   │   ├── main.ts         # Window creation, Python lifecycle, IPC handlers
│   │   ├── pythonApi.ts    # Python server management
│   │   ├── pcResources.ts  # Resource path helpers (dev/prod)
│   │   ├── preload.ts      # Electron preload script (IPC bridge)
│   │   ├── utils.ts        # Dev/prod detection helpers
│   │   └── tsconfig.json   # Electron-specific TS config
│   └── ui/                 # React frontend
│       ├── main.tsx        # React entry point
│       ├── vite-env.d.ts   # Vite type definitions
│       ├── pages/          # React Router pages
│       │   ├── App.tsx     # Main chat interface
│       │   ├── ChatHistory.tsx  # Conversation browser with search
│       │   ├── Settings.tsx     # Model & MCP settings (UI scaffolded)
│       │   └── MeetingAlbum.tsx # Recorded meetings (placeholder)
│       ├── components/
│       │   ├── Layout.tsx       # Root layout with mini mode logic
│       │   ├── TitleBar.tsx     # Navigation bar (draggable)
│       │   ├── SettingsModels.tsx  # Model selector component
│       │   └── WebSocketContext.tsx # WebSocket context provider
│       ├── CSS/            # Stylesheets
│       │   ├── App.css
│       │   ├── ChatHistory.css
│       │   ├── Settings.css
│       │   ├── SettingsModels.css
│       │   └── TitleBar.css
│       └── assets/         # UI icons and images
│           ├── transparent-clueless-logo.png
│           ├── settings-icon.svg
│           ├── chat-history-icon.svg
│           ├── new-chat-icon.svg
│           ├── mic-icon.svg
│           ├── entire-screen-shot-icon.svg
│           ├── region-screen-shot-icon.svg
│           ├── meeting-record-icon.svg
│           ├── recorded-meetings-album-icon.svg
│           ├── context-window-icon.svg
│           ├── scroll-down-icon.svg
│           ├── models.svg
│           ├── mcp.svg
│           ├── ollama.svg
│           ├── anthropic.svg
│           ├── gemini.svg
│           └── openai.svg
├── source/                 # Python backend
│   ├── main.py             # FastAPI server entry point
│   ├── app.py              # FastAPI app factory
│   ├── config.py           # Configuration constants
│   ├── database.py         # SQLite chat history persistence
│   ├── ss.py               # Screenshot service, region selector
│   ├── api/                # API layer
│   │   ├── websocket.py    # WebSocket endpoint
│   │   ├── http.py         # HTTP REST endpoints
│   │   └── handlers.py     # Message handlers
│   ├── core/               # Core utilities
│   │   ├── state.py        # Global state
│   │   ├── connection.py   # WebSocket manager
│   │   └── lifecycle.py    # Startup/shutdown logic
│   ├── services/           # Business logic
│   │   ├── conversations.py
│   │   └── screenshots.py
│   ├── llm/                # LLM integration
│   │   └── ollama.py
│   ├── mcp_integration/    # MCP tool management
│   │   ├── manager.py
│   │   └── handlers.py
│   └── user_data/          # Persistent user data
│       ├── clueless_app.db # SQLite database
│       └── screenshots/    # Persistent screenshot storage
├── mcp_servers/            # MCP (Model Context Protocol) tools
│   ├── __init__.py
│   ├── README.md           # Comprehensive MCP guide
│   ├── INTEGRATION_GUIDE.md # 3-step tool integration guide
│   ├── requirements.txt    # MCP dependencies
│   ├── test_demo.py        # Test script for demo server
│   ├── client/
│   │   ├── __init__.py
│   │   └── ollama_bridge.py # Standalone bridge for external use
│   ├── config/
│   │   └── servers.json    # Server configuration (for bridge)
│   └── servers/            # Each subfolder = one MCP server
│       ├── __init__.py
│       ├── demo/           # ✅ IMPLEMENTED — add/divide tools
│       │   ├── __init__.py
│       │   └── server.py
│       ├── filesystem/     # ✅ PARTIALLY IMPLEMENTED — list_directory
│       │   ├── __init__.py
│       │   └── server.py
│       ├── gmail/          # 📝 PLACEHOLDER
│       ├── calendar/       # 📝 PLACEHOLDER
│       ├── discord/        # 📝 PLACEHOLDER
│       ├── canvas/         # 📝 PLACEHOLDER
│       └── websearch/      # 📝 PLACEHOLDER
├── dist-electron/          # Compiled Electron code (TypeScript → JS)
│   ├── main.js
│   ├── pythonApi.js
│   ├── pcResources.js
│   ├── preload.js
│   └── utils.js
├── dist-react/             # Built React app (Vite output)
│   ├── index.html
│   └── assets/
│       ├── index-[hash].js
│       └── index-[hash].css
├── dist-python/            # Bundled Python (PyInstaller output)
│   └── main.exe            # Standalone Python server executable
├── user_data/              # Persistent application data
│   ├── clueless_app.db     # SQLite database (conversations, messages)
│   └── screenshots/        # User screenshots
├── screenshots/            # Temporary screenshot storage (legacy)
├── scripts/                # Build automation
│   ├── build-python.mjs    # Python bundling script (legacy)
│   └── build-python-exe.py # PyInstaller build configuration
├── package.json            # Node dependencies & build scripts
├── requirements.txt        # Python dependencies
├── pyproject.toml          # Python project configuration
├── tsconfig.json           # Root TypeScript config
├── tsconfig.app.json       # App-specific TS config
├── tsconfig.node.json      # Node-specific TS config
├── vite.config.ts          # Vite bundler configuration
├── eslint.config.js        # ESLint configuration
├── electron-builder.json   # Electron Builder config (installers)
├── build-server.spec       # PyInstaller spec file
├── README.md               # User-facing documentation
├── CLAUDE.md               # This file (AI assistant guide)
├── PYINSTALLER_GUIDE.md    # PyInstaller documentation
└── plan.MD                 # Development roadmap
```

## Key Files

### `source/main.py` (162 lines)
Entry point for the backend. It initializes services, starts the screenshot listener, and launches the FastAPI server (uvicorn) with the correct asyncio loop configuration. It delegates the actual app creation to `app.py` and logic to `services/`, `api/`, and `core/` modules.

### `source/api/http.py` (98 lines)
New HTTP REST API for non-streaming operations:
- **GET /api/health**: Server health check
- **GET /api/models/ollama**: Lists installed Ollama models with details (size, quantization)
- **GET /api/models/enabled**: Returns models enabled in settings (from DB)
- **PUT /api/models/enabled**: Updates the list of enabled models
- **Architecture**: Separates one-time fetches from the WebSocket real-time stream.

### `source/database.py` (367 lines)
SQLite database manager with thread-safe operations:
- **Schema**:
  - `conversations`: id, title, timestamps, token counts
  - `messages`: content, role, images, model (new column)
  - `settings`: key-value store for preferences (e.g., enabled models)
- **New Features**:
  - `get/set_enabled_models()`: Persists user model selection
  - `model` column in messages: Tracks which model generated a response
  - `settings` table: Generic key-value storage
- **Write operations**:
  - `start_new_conversation(title)` → creates new chat session
  - `add_message(conversation_id, role, content, images)` → saves message and updates parent timestamp
- **Read operations**:
  - `get_recent_conversations(limit, offset)` → lazy loading for sidebar
  - `get_full_conversation(conversation_id)` → loads all messages
  - `search_conversations(query)` → full-text search in titles and content
- **Update operations**:
  - `update_conversation_title(conversation_id, title)` → auto-generated titles from first message
  - `update_token_counts(conversation_id, input_tokens, output_tokens)` → cumulative tracking
- **Delete operations**:
  - `delete_conversation(conversation_id)` → cascade delete messages
- **Key concept**: `check_same_thread=False` to allow FastAPI thread pool access
- **JSON serialization** for image arrays (SQLite doesn't have native array type)
- **Migration support** for adding columns to existing databases

### `source/ss.py` (478 lines)
Screenshot service with two main components:
1. **`ScreenshotService`**: Global hotkey listener
   - Monitors Ctrl+Shift+Alt+S
   - Thread-safe capture gating via `_lock` (prevents concurrent captures)
   - Callback system: `start_callback` (on capture begin), `callback` (on capture complete)
   - Runs in dedicated background thread
   - Clipboard copy support with DPI awareness
2. **`RegionSelector`**: Full-screen overlay (tkinter)
   - Dimmed background with semi-transparent selection
   - Click-and-drag rectangle selection
   - Live preview of selected region
   - High-DPI support for Windows (multi-monitor aware)
   - Coordinate transformation for scaled displays
   - ESC to cancel
3. **Helper functions**:
   - `take_fullscreen_screenshot()` → captures entire primary display
   - `take_region_screenshot()` → launches RegionSelector overlay
   - `create_thumbnail(image_path, max_size=100)` → base64-encoded thumbnail for UI
   - `copy_image_to_clipboard(image, dpi_scale)` → robust clipboard support (64-bit handles)
   - `get_dpi_scale()` → detects monitor DPI scaling factor

### `src/ui/pages/App.tsx` (554 lines)
Main Chat Application Component (Refactored):
- **Architecture**:
  - State management via custom hooks: `useChatState`, `useScreenshots`, `useTokenUsage`
  - WebSocket communication via `useWebSocket` hook
  - API abstraction via `src/ui/services/api.ts`
- **Features**:
  - **Navigation**: TitleBar with Settings, History, Album links
  - **Chat Interface**: `ResponseArea` (messages), `QueryInput` (text area)
  - **Input Options**: `ScreenshotChips` (previews), `ModeSelector` (capture modes), `TokenUsagePopup`
  - **Model Selector**: Dropdown populated from `api.getEnabledModels()`
- **Key Hooks**:
  - `useChatState`: Handles message history, thinking state, tool calls
  - `useScreenshots`: Handles capture mode, image list, thumbnail generation
  - `useTokenUsage`: Tracks input/output tokens
- **WebSocket Integration**:
  - Handles all server messages (`ready`, `query`, `response_chunk`, `tool_call`, etc.)
  - Auto-reconnection logic
- **IPC**: Uses `window.electronAPI` for focus and mini-mode toggling

### `src/ui/pages/ChatHistory.tsx` (202 lines)
Conversation browser with advanced features:
- **WebSocket-based conversation fetching**
- **Debounced search** (300ms delay) with full-text search
- **Lazy loading** support (limit/offset pagination)
- **Conversation list**:
  - Title and relative timestamp (e.g., "2 hours ago")
  - Click to resume conversation
  - Delete button (confirmation dialog)
- **Real-time updates**:
  - New conversations appear automatically
  - Deleted conversations remove from list
- **Navigation integration** with React Router state passing

### `src/ui/pages/Settings.tsx` (85 lines)
Settings page with tabbed navigation:
- **Tabs**: Models, Connections, Ollama, Anthropic, Gemini, OpenAI
- **Implemented**: 
  - **Models**: Uses `SettingsModels` component to toggle local Ollama models.
- **Placeholders**: Other tabs show a "coming soon" message.
- **Sidebar**: Vertical navigation with icons.

### `src/ui/components/Layout.tsx` (41 lines)
Root layout component with mini mode logic:
- **Mini mode state management**
- **Container structure**:
  - `mini-container` — 52×52 logo (visible in mini mode)
  - `container` — main app (visible in normal mode)
- **Opacity toggle** for screenshot capture (hides UI when screenshot starts)
- **Outlet context** provides `setMini`, `setIsHidden`, `isHidden` to child routes
- **electronAPI integration** for IPC communication

### `src/ui/components/TitleBar.tsx` (53 lines)
Navigation bar component:
- **Left navigation buttons**:
  - Settings → navigates to `/settings`
  - Chat History → navigates to `/history`
  - Recorded Meetings Album → navigates to `/album`
- **Draggable blank space** (center) for window movement
- **Right navigation**:
  - New Chat button → clears context and navigates to `/` with `newChat: true` state
  - Clueless logo → enters mini mode on click
- **Tooltip support** on all buttons

### `src/electron/main.ts` (148 lines)
Electron main process:
- **Window configuration**:
  - 450×450 (normal) / 52×52 (mini)
  - Frameless, transparent, resizable
  - Always-on-top (`screen-saver` level)
  - No minimize/maximize buttons
  - Skips taskbar
  - Content protection enabled
- **Python server lifecycle** (production only):
  - Starts Python server on app ready
  - Stops server on app quit
  - Dev mode skips this (dev:pyserver script handles it)
- **IPC handlers**:
  - `set-mini-mode` → resizes window and repositions to top-right
  - `focus-window` → brings window to foreground
- **Multi-cleanup handlers**:
  - `closed`, `close`, `window-all-closed`, `before-quit`, `will-quit`
- **Preload script** for secure IPC bridge

### `mcp_servers/servers/demo/server.py` (63 lines)
Reference implementation of an MCP server:
- **Two tools**: `add(a, b)` and `divide(a, b)`
- **FastMCP framework** (official MCP Python SDK)
- **@mcp.tool() decorator** for tool registration
- **Type hints** required for schema generation
- **Docstrings** become tool descriptions (visible to LLM)
- **stdio transport** (communicates via stdin/stdout)
- **Can run standalone** for testing with MCP Inspector

### `mcp_servers/README.md` (332 lines)
Comprehensive MCP integration guide:
- **Quick start instructions** for dependencies and testing
- **Architecture explanation** with diagrams
- **How MCP works** — "USB port for AI" analogy
- **Tool discovery and routing** mechanisms
- **Folder structure** explanation
- **Adding new servers** step-by-step guide
- **Debugging tips** and troubleshooting
- **Placeholder server descriptions** with suggested tools

## Development Commands

```bash
# Full development mode (all services)
npm run dev

# Individual services
npm run dev:react      # Vite dev server (port 5123)
npm run dev:electron   # Electron app
npm run dev:pyserver   # Python FastAPI server (.venv activated)
npm run dev:ollama     # Ollama server (auto-detects if already running)

# Build
npm run build          # Full build (Python exe + React + Electron transpile)
npm run build:react    # Vite build only
npm run build:python-exe  # PyInstaller build only
npm run dist:win       # Build Windows installer
npm run dist:mac       # Build macOS installer
npm run dist:linux     # Build Linux installer

# Other
npm run lint           # ESLint
npm run install:python # Install Python deps in .venv
npm run test:ollama    # Check if Ollama is running
npm run transpile:electron  # Compile TypeScript to JavaScript
npm run preview        # Preview production build
```

## MCP (Model Context Protocol) Integration

### Overview
Clueless has **built-in MCP support** that allows you to give the LLM access to external tools (file operations, Gmail, Discord, web search, etc.). MCP servers run as child processes and communicate via stdio (JSON-RPC).

### Architecture
```
┌───────────────────┐           ┌────────────────────┐
│   Ollama Model    │           │  MCP Tool Manager  │
│  (qwen3-vl:8b)    │◄─────────►│    (main.py)       │
│                   │  tools=[]  │                    │
│ Returns tool_call │           │ Routes tool calls  │
└───────────────────┘           └─────────┬──────────┘
                                          │
                        ┌─────────────────┴─────────────────┐
                        ▼                                   ▼
                ┌────────────────┐                ┌────────────────┐
                │  demo server   │                │ filesystem srv │
                │  (add, divide) │                │ (list_dir)     │
                │  stdio process │                │ stdio process  │
                └────────────────┘                └────────────────┘
```

### How Tool Calls Work
1. User sends query: "What's 42 + 58?"
2. Ollama receives request WITH tools array containing all registered MCP tools
3. Ollama detects it needs a tool and returns: `tool_call: add(a=42, b=58)`
4. Backend intercepts tool call in `_handle_mcp_tool_calls()`
5. McpToolManager routes to correct server: `demo.add(42, 58)`
6. MCP server executes and returns: `"100.0"`
7. Result goes back to Ollama as tool result
8. Ollama generates final response: "42 + 58 equals 100!"
9. UI displays both tool call card and final response

### Adding New MCP Tools (3 Steps)

**Step 1**: Create server at `mcp_servers/servers/<name>/server.py`
```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("My Tool")

@mcp.tool()
def my_function(param: str) -> str:
    """Clear description for the LLM to understand when to call this."""
    return f"Result: {param}"

if __name__ == "__main__":
    mcp.run()
```

**Step 2**: Register in `source/main.py` → `_init_mcp_servers()` function
```python
await _mcp_manager.connect_server(
    "my_tool",
    sys.executable,
    [str(PROJECT_ROOT / "mcp_servers" / "servers" / "my_tool" / "server.py")]
)
```

**Step 3**: Restart the app — tools auto-register!

### Current MCP Servers
- ✅ **demo** — `add(a, b)`, `divide(a, b)` — basic calculator tools
- ✅ **filesystem** — `list_directory(path)` — file system operations (partial)
- 📝 **gmail** — placeholder for Gmail integration
- 📝 **calendar** — placeholder for Google Calendar
- 📝 **discord** — placeholder for Discord bot
- 📝 **canvas** — placeholder for Canvas LMS
- 📝 **websearch** — placeholder for web search/scrape

### MCP Debugging
- Check console for `[MCP]` prefixed logs
- Verify tool registration: "Registered tool: add (from demo)"
- Test standalone: `python -m mcp_servers.servers.demo.server`
- Use MCP Inspector for interactive testing
- Tool calls appear in UI as cards: `⚙ Used 1 tool: demo > add(a: 42, b: 58) → 100.0`

### MCP Resources
- **Official docs**: https://modelcontextprotocol.io
- **Python SDK**: `pip install "mcp[cli]"`
- **Project guide**: `mcp_servers/README.md`
- **Integration guide**: `mcp_servers/INTEGRATION_GUIDE.md`

## WebSocket Protocol

The WebSocket connection at `ws://localhost:8000/ws` uses JSON messages with `type` and `content` fields.

### Client → Server Messages

```json
// Submit a query (with or without images)
{"type": "submit_query", "content": "Your question here"}

// Clear conversation context (start new chat)
{"type": "clear_context"}

// Set capture mode
{"type": "set_capture_mode", "mode": "fullscreen" | "precision" | "none"}

// Resume a previous conversation
{"type": "resume_conversation", "conversation_id": "uuid-string"}

// Get list of conversations (for ChatHistory page)
{"type": "get_conversations", "limit": 50, "offset": 0}

// Search conversations
{"type": "search_conversations", "query": "search terms"}

// Delete a conversation
{"type": "delete_conversation", "conversation_id": "uuid-string"}

// Remove a screenshot from context
{"type": "remove_screenshot", "screenshot_id": "ss_1"}
```

### Server → Client Messages

```json
// Server ready to receive queries
{"type": "ready", "content": "Server ready..."}

// Screenshot capture starting (UI should hide)
{"type": "screenshot_start", "content": "Screenshot capture starting"}

// Screenshot added to context (with thumbnail)
{"type": "screenshot_added", "content": "{\"id\": \"ss_1\", \"name\": \"screenshot.png\", \"thumbnail\": \"data:image/png;base64,...\"}"}

// Screenshot removed from context
{"type": "screenshot_removed", "content": "{\"id\": \"ss_1\"}"}

// All screenshots cleared from context
{"type": "screenshots_cleared", "content": ""}

// Legacy screenshot ready message
{"type": "screenshot_ready", "content": "Screenshot captured..."}

// Echo of user query
{"type": "query", "content": "User's question"}

// Streaming thinking/reasoning chunks
{"type": "thinking_chunk", "content": "...partial thinking..."}
{"type": "thinking_complete", "content": ""}

// Streaming response chunks
{"type": "response_chunk", "content": "...partial response..."}
{"type": "response_complete", "content": ""}

// MCP tool call initiated
{"type": "tool_call", "content": "{\"name\": \"add\", \"arguments\": {\"a\": 42, \"b\": 58}, \"server\": \"demo\"}"}

// MCP tool call result
{"type": "tool_result", "content": "{\"name\": \"add\", \"result\": \"100.0\", \"server\": \"demo\"}"}

// Context cleared confirmation
{"type": "context_cleared", "content": "Context cleared..."}

// Conversation saved to database
{"type": "conversation_saved", "content": "{\"conversation_id\": \"uuid-string\"}"}

// List of conversations (response to get_conversations)
{"type": "conversations_list", "content": "[{\"id\": \"uuid\", \"title\": \"...\", \"date\": 1234567890}, ...]"}

// Conversation loaded (response to resume_conversation)
{"type": "conversation_loaded", "content": "{\"conversation_id\": \"uuid\", \"messages\": [...]}"}

// Conversation deleted confirmation
{"type": "conversation_deleted", "content": "{\"conversation_id\": \"uuid\"}"}

// Token usage update (sent after each response)
{"type": "token_update", "content": "{\"input\": 123, \"output\": 456, \"total\": 579}"}

// Error message
{"type": "error", "content": "Error message"}
```

## Screenshot Flow

### Precision Mode (Hotkey Capture)
1. User presses **Ctrl+Shift+Alt+S** (or **Alt+.**)
2. Screenshot service calls `start_callback` → schedules `_on_screenshot_start()` on server loop
3. Backend sends `screenshot_start` → UI sets opacity to 0 (hides window)
4. RegionSelector overlay appears (full-screen tkinter window)
5. User drags to select region (or ESC to cancel)
6. Screenshot captured and saved to `user_data/screenshots/`
7. Screenshot service calls `callback` with image path → schedules `_on_screenshot_captured()`
8. Backend generates thumbnail (max 100x100, base64-encoded)
9. Backend sends `screenshot_added` with id, name, thumbnail
10. UI displays thumbnail in screenshot carousel
11. UI sends `screenshot_ready` (legacy) → UI opacity back to 1
12. User can attach multiple screenshots before querying
13. User submits query → all screenshots sent to Ollama
14. After response completes, screenshots embedded in chat history message
15. Screenshots cleared from carousel (but preserved in message)

### Fullscreen Mode
1. User selects "Fullscreen" capture mode at bottom of window
2. User submits query (or clicks screenshot button)
3. Backend captures entire primary display via `ImageGrab.grab()`
4. Screenshot saved and processed (no overlay, instant capture)
5. Image immediately sent to Ollama with query
6. After response, screenshot cleared from context (fullscreen mode is one-shot)

### Meeting Recording Mode
- UI scaffolded but not yet implemented
- Intended for continuous screen recording during meetings
- Will save frames to `user_data/screenshots/` with timestamps

## Database Schema

### `conversations` Table
```sql
CREATE TABLE conversations (
    id TEXT PRIMARY KEY,              -- UUID (e.g., "550e8400-...")
    title TEXT,                       -- Auto-generated from first message
    created_at REAL,                  -- Unix timestamp
    updated_at REAL,                  -- Updated on every new message
    total_input_tokens INTEGER DEFAULT 0,   -- Cumulative input tokens
    total_output_tokens INTEGER DEFAULT 0   -- Cumulative output tokens
)
```

### `messages` Table
```sql
CREATE TABLE messages (
    num_messages INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT,             -- FK to conversations.id
    role TEXT,                        -- 'user' or 'assistant'
    content TEXT,                     -- Message content
    images TEXT,                      -- JSON array: ["path1.png", "path2.png"]
    model TEXT,                       -- Model name used for this message
    created_at REAL,
    FOREIGN KEY(conversation_id) REFERENCES conversations(id)
)

CREATE TABLE settings (
    key TEXT PRIMARY KEY,             -- e.g., "enabled_models"
    value TEXT                        -- e.g., JSON string of model names
)
```

### Key Concepts
- **Thread-safe**: `check_same_thread=False` allows FastAPI thread pool access
- **JSON serialization**: Image arrays stored as JSON strings (SQLite has no array type)
- **Lazy loading**: ChatHistory loads metadata only, messages loaded on demand
- **Full-text search**: Searches in both title and content fields
- **Cascade delete**: Deleting conversation also deletes all messages
- **Token tracking**: Cumulative input/output tokens per conversation
- **Migration support**: `ALTER TABLE` statements for adding columns to existing DBs

## Capture Modes

Clueless has three capture modes (toggle buttons at bottom of window):

### 1. Fullscreen Mode (Default)
- **Icon**: Monitor/screen icon
- **Behavior**: Captures entire primary display on query submission
- **Use case**: Quick screenshots without region selection
- **Screenshot lifecycle**: One-shot (cleared after response)
- **Hotkey**: Not applicable (UI button only)

### 2. Precision Mode (Region Selection)
- **Icon**: Crosshair/region icon
- **Behavior**: User manually triggers hotkey to capture selected region
- **Hotkey**: Ctrl+Shift+Alt+S
- **Use case**: Selective screenshots, multiple images before query
- **Screenshot lifecycle**: Persistent (stays in carousel until cleared or query completes)
- **Multiple screenshots**: Supported

### 3. Meeting Recording Mode
- **Icon**: Video camera icon
- **Status**: UI scaffolded, not yet implemented
- **Intended behavior**: Continuous screen recording with frame extraction
- **Use case**: Recording meetings, lectures, or long sessions
- **Planned features**: 
  - Start/stop recording button
  - Frame extraction at intervals
  - Gallery of recorded frames
  - Playback interface

## Chat History & Conversation Management

### Features
- **Persistent storage**: All conversations saved to SQLite database
- **Lazy loading**: Sidebar loads metadata only (id, title, timestamp)
- **Search**: Full-text search across titles and message content
- **Resume conversations**: Click to load all messages and continue chatting
- **Delete conversations**: Swipe or click delete button (cascade deletes messages)
- **Auto-titling**: First user message becomes conversation title (truncated)
- **Timestamps**: "2 hours ago", "Yesterday", "Last week" relative formatting
- **Token tracking**: Total tokens per conversation displayed in UI

### Workflow
1. User starts chatting → backend auto-creates conversation with UUID
2. Each message saved immediately → `updated_at` timestamp refreshed
3. Conversation appears in ChatHistory sidebar
4. User can navigate away and resume later → all context preserved
5. Token counts accumulate per conversation
6. User can delete old conversations → cascade delete from database

### Database Operations
- **Write**: `add_message()` called after every `response_complete`
- **Read**: `get_recent_conversations()` for sidebar, `get_full_conversation()` for resume
- **Search**: `search_conversations(query)` for full-text search
- **Delete**: `delete_conversation(id)` with cascade to messages
- **Update**: `update_conversation_title()` auto-generates title from first message

## Token Usage Tracking

### Features
- **Real-time tracking**: Token counts updated after every response
- **Visual indicator**: "1,234 / 128,000" display with color coding
- **Breakdown popup**: Click to see input vs output tokens
- **Per-conversation totals**: Cumulative tracking in database
- **Color coding**:
  - 🟢 Green: < 50% of limit (safe)
  - 🟡 Yellow: 50-80% of limit (caution)
  - 🔴 Red: > 80% of limit (approaching limit)
- **Context window limit**: Currently hardcoded to 128,000 tokens (qwen3-vl:8b context limit)

### Implementation
1. Ollama returns token counts in response metadata
2. Backend parses `prompt_eval_count` (input) and `eval_count` (output)
3. Backend sends `token_update` message to UI
4. UI updates state and displays indicator
5. Database stores cumulative totals per conversation
6. On conversation resume, previous token counts loaded

### Token Calculation
- **Input tokens**: User message + chat history + system prompt + tool schemas + images
- **Output tokens**: Assistant response (thinking + final response)
- **Images**: Each image ~1000-2000 tokens depending on resolution (Ollama estimate)

## Mini Mode

### Overview
Mini mode collapses the window to a **52×52 pixel logo** in the top-right corner, allowing the app to stay accessible without covering screen space.

### Features
- **Toggle**: Click Clueless logo in title bar → enters mini mode
- **Restore**: Click mini logo → restores to previous size/position
- **Position**: Top-right corner of previous window location
- **Size**: 52×52 pixels (just the logo)
- **Window properties**:
  - Still always-on-top
  - Still frameless and transparent
  - Still skips taskbar
  - Maintains content protection
- **State preservation**: Returns to exact previous size and position

### Implementation
- **Frontend**: `Layout.tsx` manages `mini` state and container visibility
- **IPC**: `window.electronAPI.setMiniMode(boolean)` calls Electron main process
- **Backend**: `main.ts` handles `set-mini-mode` IPC, resizes BrowserWindow
- **CSS**: `.mini-mode` and `.normal-mode` classes toggle container visibility
- **Position calculation**: `newX = normalBounds.x + normalBounds.width - 52`

### Use Cases
- Keep Clueless accessible while working full-screen
- Reduce visual clutter during meetings
- Quick access to screenshot hotkey without visible window
- Preserve screen real estate for main tasks

## Ollama Integration

### Current Model
- **Model**: `qwen3-vl:8b-instruct`
- **Type**: Vision-language model (multimodal)
- **Purpose**: Processes both text and images
- **Context window**: 128,000 tokens
- **Tool calling**: ✅ Supported (for MCP integration)
- **Streaming**: ✅ Token-by-token response delivery
- **Local**: Runs entirely on user's machine (privacy-preserving)

### Chat API Usage
```python
from ollama import chat

response = chat(
    model='qwen3-vl:8b-instruct',
    messages=_chat_history,  # Multi-turn conversation
    tools=_mcp_manager.get_ollama_tools(),  # MCP tools (if available)
    stream=True,  # Token-by-token streaming
    options={
        'temperature': 0.7,
        # Other Ollama options...
    }
)

# Process streaming response
for chunk in response:
    if 'message' in chunk:
        if 'tool_calls' in chunk['message']:
            # Handle MCP tool calls
            pass
        elif 'content' in chunk['message']:
            # Stream text content
            pass
```

### Image Handling
- **Format**: Base64-encoded PNG/JPEG
- **Preprocessing**: Images resized if > 800x600 (reduces token usage)
- **Embedding**: Images stored as `{"type": "image", "data": "base64..."}` in chat history
- **Multiple images**: Supported (all images in one message)
- **Thumbnails**: Generated for UI display (100x100 max)

### Response Structure
- **Thinking**: Optional reasoning/chain-of-thought (collapsible in UI)
- **Tool calls**: MCP tool invocations (displayed as cards)
- **Final response**: Markdown-formatted answer (with syntax highlighting)
- **Token counts**: `prompt_eval_count` (input) and `eval_count` (output)

## Build Process

### Development Build
```bash
npm run dev
```
Starts four concurrent processes:
1. **Vite dev server** (React) on port 5123
2. **Electron** in dev mode (loads from Vite)
3. **Python server** (FastAPI) on port 8000
4. **Ollama server** (auto-starts if not running)

### Production Build
```bash
npm run build
```
1. **Install Python deps** → `pip install -r requirements.txt`
2. **Build Python exe** → PyInstaller creates `dist-python/main.exe`
3. **Transpile Electron** → TypeScript → JavaScript (`dist-electron/`)
4. **Build React** → Vite bundles to `dist-react/`

### Installer Build
```bash
npm run dist:win   # Windows (.exe installer)
npm run dist:mac   # macOS (.dmg, .app)
npm run dist:linux # Linux (.AppImage, .deb)
```
Uses **electron-builder** to create platform-specific installers:
- **Windows**: NSIS installer with auto-update support
- **macOS**: DMG and .app bundle (requires code signing)
- **Linux**: AppImage, Debian package

### Build Artifacts
```
dist/                       # electron-builder output
├── win-unpacked/           # Unpacked Windows build
│   ├── Clueless.exe        # Main executable
│   ├── resources/
│   │   ├── app.asar        # Packaged Electron app
│   │   └── dist-python/    # Bundled Python server
│   └── ...
├── CluelessSetup.exe       # Windows installer
├── Clueless.dmg            # macOS disk image
└── Clueless.AppImage       # Linux portable

dist-electron/              # Compiled TypeScript (JS)
dist-react/                 # Compiled React (HTML/CSS/JS)
dist-python/                # PyInstaller executable
    └── main.exe            # Standalone Python server
```

### PyInstaller Configuration
- **Spec file**: `build-server.spec`
- **Entry point**: `source/main.py`
- **One-file mode**: All dependencies bundled into single exe
- **Hidden imports**: `mcp`, `ollama`, `PIL`, `tkinter`, `pynput`
- **Data files**: MCP servers copied to bundle
- **Console**: Hidden (no console window)

## Common Development Tasks

### Adding a New UI Page
1. Create component in `src/ui/pages/<PageName>.tsx`
2. Add route in `src/ui/main.tsx`:
   ```tsx
   <Route path="/your-path" element={<YourPage />} />
   ```
3. Add navigation button in `TitleBar.tsx` (if needed)
4. Add CSS file in `src/ui/CSS/<PageName>.css`

### Adding a New WebSocket Message Type
1. **Backend** (`source/main.py`):
   - Add case in `websocket_endpoint()` for client → server
   - Use `await broadcast_message("your_type", content)` for server → client
2. **Frontend** (`src/ui/pages/App.tsx`):
   - Add case in `ws.onmessage` switch statement
   - Update state based on message content

### Adding a New MCP Tool
See "MCP Integration" section above for 3-step process.

### Modifying the Database Schema
1. Edit `_init_db()` in `source/database.py`
2. Add migration code:
   ```python
   try:
       cursor.execute("ALTER TABLE table_name ADD COLUMN new_col TYPE")
   except sqlite3.OperationalError:
       pass  # Column already exists
   ```
3. Update read/write methods to handle new column
4. Test with existing database to ensure migration works

### Changing the Ollama Model
1. **Pull new model**: `ollama pull model-name`
2. **Update code**: Search for `qwen3-vl:8b-instruct` in `source/main.py`
3. **Replace** all instances with new model name
4. **Verify tool support**: Not all models support function calling
5. **Update context limit**: Change `limit: 128000` in token tracking code
6. **Rebuild**: `npm run build` to update bundled code

### Debugging WebSocket Issues
1. **Check browser console**: Look for connection errors
2. **Check Python console**: Look for `[MCP]` and WebSocket logs
3. **Verify port**: Ensure 8000 is not blocked by firewall
4. **Test connection**: `curl http://localhost:8000` should return HTML
5. **WebSocket test**: Use browser devtools Network tab → WS filter
6. **Add logging**: Insert `console.log()` in `App.tsx` and `print()` in `main.py`

### Common Errors

#### "Cannot find module 'electron'"
- **Cause**: Node modules not installed
- **Fix**: `npm install`

#### "Python server not starting"
- **Cause**: Virtual environment not activated or deps not installed
- **Fix**: `.venv\Scripts\activate` then `pip install -r requirements.txt`

#### "Ollama connection refused"
- **Cause**: Ollama not running
- **Fix**: `ollama serve` or `npm run dev:ollama`

#### "Screenshot not captured"
- **Cause**: Hotkey conflict or pynput permissions
- **Fix**: Check system hotkeys, run as admin, verify pynput installed

#### "MCP tools not appearing"
- **Cause**: MCP package not installed or server registration failed
- **Fix**: `pip install "mcp[cli]"`, check console for `[MCP]` errors

#### "Database locked"
- **Cause**: Multiple processes accessing SQLite simultaneously
- **Fix**: Ensure `check_same_thread=False` in connection, close old connections

#### "Token count incorrect"
- **Cause**: Ollama response missing token metadata
- **Fix**: Check Ollama version, ensure model supports token reporting

## Configuration Files

### `package.json`
- Node dependencies (React, Electron, Vite, TypeScript)
- Build scripts (`dev`, `build`, `dist`)
- Electron main entry point: `dist-electron/main.js`

### `pyproject.toml`
- Python project metadata
- Dependencies (FastAPI, Ollama, Pillow, pynput, etc.)
- Requires Python >= 3.13

### `requirements.txt`
- Python dependencies with version constraints
- Used by `npm run install:python`
- Includes PyInstaller for bundling

### `vite.config.ts`
- Vite bundler configuration
- React plugin
- Build output to `dist-react/`
- Dev server on port 5123

### `tsconfig.json`
- Root TypeScript configuration
- Extends `tsconfig.app.json` and `tsconfig.node.json`

### `electron-builder.json`
- Electron Builder configuration
- App ID, product name, copyright
- Platform-specific build settings
- File patterns to include/exclude
- Installer options (NSIS, DMG, etc.)

### `build-server.spec`
- PyInstaller specification file
- Entry point: `source/main.py`
- Hidden imports for dependencies
- Data files (MCP servers)
- One-file bundle configuration

## Important Notes for AI Assistants

### When Editing Code
- **Always use absolute paths** for file operations
- **Preserve refs** in React components (critical for async WebSocket handling)
- **Include 3+ lines of context** when using replace_string_in_file
- **Test WebSocket messages** end-to-end (backend → frontend → UI)
- **Verify MCP registration** when adding new tool servers
- **Check database migrations** when modifying schema

### Architecture Decisions
- **Why check_same_thread=False?** FastAPI uses thread pools; SQLite needs multi-thread access
- **Why refs in App.tsx?** WebSocket callbacks capture stale state; refs ensure current values
- **Why event loop holder?** Windows Proactor loop can't be touched from other threads; we schedule work instead
- **Why stdio transport for MCP?** Standard MCP protocol; enables child process isolation
- **Why PyInstaller?** Bundles Python + deps into single exe for production distribution
- **Why Electron screen-saver level?** Ensures always-on-top even above full-screen apps

### Testing Checklist
- [ ] WebSocket connection established on app start
- [ ] Screenshot captures (both fullscreen and region)
- [ ] Multi-turn conversations preserved
- [ ] Chat history loads and resumes correctly
- [ ] MCP tools register and execute
- [ ] Token counts update after each response
- [ ] Mini mode toggles and restores
- [ ] Database migrations work on existing DB
- [ ] Build process completes without errors
- [ ] Installer runs and app launches

## Future Roadmap

### Planned Features
- **Model selector UI** → Currently hardcoded to qwen3-vl:8b
- **Multiple LLM providers** → OpenAI, Anthropic, Gemini APIs
- **Voice input** → Speech-to-text for queries
- **Meeting recording** → Continuous screen capture with frame extraction
- **MCP server management UI** → Enable/disable servers, configure credentials
- **Custom hotkeys** → User-configurable screenshot hotkey
- **OCR integration** → Extract text from screenshots
- **Export conversations** → Markdown, PDF, or JSON export
- **Sync across devices** → Cloud backup for conversations
- **Plugin system** → Third-party MCP server marketplace
- **Themes** → Light/dark mode, custom color schemes
- **Accessibility** → Screen reader support, keyboard navigation

### Known Issues
- **macOS compatibility** → Not yet tested/supported (Windows-only currently)
- **Linux compatibility** → Partial support, needs testing
- **High DPI scaling** → Some UI elements may not scale correctly on 4K displays
- **Screenshot performance** → Large images can slow down response time
- **Token limit warnings** → Currently hardcoded, should be model-specific
- **Database backups** → No automatic backup system yet
- **Error recovery** → Some error states require app restart

## Resources

### Documentation
- **README.md** → User-facing setup and usage guide
- **CLAUDE.md** → This file (AI assistant reference)
- **mcp_servers/README.md** → MCP integration guide
- **mcp_servers/INTEGRATION_GUIDE.md** → 3-step tool integration
- **PYINSTALLER_GUIDE.md** → PyInstaller bundling guide
- **plan.MD** → Development roadmap

### External Links
- **Ollama**: https://ollama.com
- **Model Context Protocol**: https://modelcontextprotocol.io
- **Electron**: https://www.electronjs.org
- **Vite**: https://vitejs.dev
- **FastAPI**: https://fastapi.tiangolo.com
- **React**: https://react.dev

---

*Last updated: February 12 2026*
*Project version: 0.0.0 (pre-release)*
*For the latest updates, see the project repository.*
