# Claude.MD - LLM Development Guide

## Project Overview

Electron + React + Python desktop app for AI chat with screenshot capabilities. Key features:
- Ollama LLM integration (qwen3-vl:8b) with streaming
- Screenshot capture (hotkey + fullscreen) with vision model processing
- WebSocket-based bidirectional communication (FastAPI backend)
- SQLite chat history persistence
- MCP (Model Context Protocol) tool integration for extensible LLM capabilities
- Always-on-top frameless window with mini mode (52×52)

## Architecture

```
Electron (main.ts) → Window mgmt, Python lifecycle
    ↓
    ├─→ React (src/ui/) → WebSocket client, UI rendering
    └─→ Python (source/main.py) → FastAPI WS server, Ollama, MCP manager
            ↓
            ├─→ database.py → SQLite (conversations, messages)
            ├─→ ss.py → Screenshot capture (hotkey, tkinter overlay)
            └─→ MCP servers → stdio child processes (demo, filesystem)
```

## Tech Stack

**Frontend**: React 19 + TypeScript + Vite 6 + React Router 7 + react-markdown  
**Backend**: Python 3.11+ + FastAPI + Ollama (qwen3-vl:8b) + SQLite3 + MCP  
**Desktop**: Electron 37+ (frameless, always-on-top, screen-saver level)  
**Utils**: pynput (hotkeys), Pillow (images), tkinter (overlays), PyInstaller (bundling), UV (package manager)

## Directory Structure (Essential Paths)

```
src/
  ├─ electron/          # main.ts, pythonApi.ts, preload.ts, utils.ts
  └─ ui/
      ├─ pages/         # App.tsx, ChatHistory.tsx, Settings.tsx
      ├─ components/    # Layout.tsx, TitleBar.tsx, WebSocketContext.tsx
      └─ CSS/           # Stylesheets
source/              # Python backend
  ├─ main.py          # FastAPI server, Ollama, MCP manager (1195 lines)
  ├─ database.py      # SQLite ops (314 lines)
  ├─ ss.py            # Screenshot service (478 lines)
  └─ user_data/       # clueless_app.db, screenshots/
mcp_servers/
  ├─ client/          # ollama_bridge.py (standalone bridge)
  ├─ config/          # servers.json
  └─ servers/         # demo/, filesystem/, gmail/, etc.
dist-electron/       # Compiled TS → JS
dist-react/          # Built React app
dist-python/         # PyInstaller output (main.exe)
user_data/           # Persistent app data (DB, screenshots)
```

## Key Files & Implementation Details

### `source/main.py` (1195 lines)
**FastAPI WebSocket server, Ollama integration, MCP manager**

Critical components:
- `McpToolManager`: Manages MCP server lifecycle (stdio child processes), discovers tools, routes calls
- `_init_mcp_servers()`: Registers all MCP servers (modify here to add new servers)
- `websocket_endpoint()`: Main WS handler, message type router
- `_handle_mcp_tool_calls()`: Intercepts Ollama tool calls, routes to MCP, returns results
- `_server_loop_holder`: Global asyncio loop reference for scheduling coroutines from worker threads (Windows Proactor requirement)
- `_chat_history`: Multi-turn conversation state (list of message dicts)
- Screenshot lifecycle: `_on_screenshot_start()`, `_on_screenshot_captured()` scheduled on server loop
- Auto-port detection: Falls back from 8000 if busy
- Graceful cleanup: `atexit`, `SIGINT`, `SIGTERM` handlers

**Key patterns**:
- Use `asyncio.run_coroutine_threadsafe(coro, _server_loop_holder.loop)` from non-async threads
- Refs in callbacks capture state; schedule on server loop to access current state
- Tool schemas auto-converted to Ollama format from MCP discovery
- Images preprocessed (max 800x600) before sending to Ollama

### `source/database.py` (314 lines)
**SQLite operations with thread safety**

Critical patterns:
- `check_same_thread=False` enables FastAPI thread pool access
- JSON serialization for image arrays (SQLite has no array type)
- `add_message()` updates parent conversation `updated_at` timestamp
- Migration pattern: Try `ALTER TABLE`, catch `OperationalError` if column exists
- UUIDs for conversation IDs (generated in Python, not DB)

Tables:
- `conversations`: id (TEXT/UUID), title, created_at, updated_at, total_input_tokens, total_output_tokens
- `messages`: num_messages (AUTOINCREMENT), conversation_id (FK), role, content, images (JSON TEXT), created_at

### `source/ss.py` (478 lines)
**Screenshot service with hotkey and overlay**

Components:
1. `ScreenshotService`: Global hotkey listener (Ctrl+Shift+Alt+S)
   - Thread-safe with `_lock` (prevents concurrent captures)
   - Callbacks: `start_callback` (on capture begin), `callback` (on complete)
   - Runs in dedicated background thread
2. `RegionSelector`: Tkinter fullscreen overlay
   - Click-drag rectangle selection
   - DPI-aware coordinate transformation
   - ESC to cancel
3. Helper functions: `take_fullscreen_screenshot()`, `take_region_screenshot()`, `create_thumbnail()`, `copy_image_to_clipboard()`

**Critical**: DPI scaling on Windows requires coordinate transformation for multi-monitor setups

### `src/ui/pages/App.tsx` (892 lines)
**Main React component with WebSocket integration**

**Critical patterns**:
- Uses **refs** for values captured in async WS callbacks: `currentQueryRef`, `responseRef`, `thinkingRef`, `screenshotsRef`, `toolCallsRef`
  - WHY: State updates don't re-register WS handler, callbacks capture stale state
  - SOLUTION: Update both state and ref simultaneously
- WebSocket message router in `ws.onmessage` event handler
- Screenshot thumbnails stored as base64 data URIs
- Tool calls displayed as cards: `⚙ Used X tools: server > tool(args) → result`
- `electronAPI.focusWindow()` and `electronAPI.setMiniMode()` for IPC

**State management**:
- `messages`: Chat history array
- `screenshots`: Current screenshot carousel (cleared after query completes)
- `captureMode`: 'fullscreen' | 'precision' | 'none'
- `currentConversationId`: UUID or null

### `src/electron/main.ts` (148 lines)
**Electron main process**

Window config:
- 450×450 normal, 52×52 mini
- `frame: false`, `transparent: true`, `alwaysOnTop: true`, `level: 'screen-saver'`
- `skipTaskbar: true`, `setContentProtection(true)`

IPC handlers:
- `set-mini-mode`: Resizes window, repositions to top-right
- `focus-window`: Brings to foreground

**Python lifecycle** (prod only):
- Starts Python server on `app.whenReady()`
- Stops on `app.quit()`
- Dev mode skips (dev:pyserver script handles it)

### `mcp_servers/servers/demo/server.py` (63 lines)
**Reference MCP server implementation**

Pattern for adding tools:
```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("ServerName")

@mcp.tool()
def function_name(param: type) -> return_type:
    """Description visible to LLM (critical for tool discovery)"""
    return result

if __name__ == "__main__":
    mcp.run()  # stdio transport
```

**Requirements**: Type hints mandatory (schema generation), docstrings become tool descriptions

## Development Commands

```bash
npm run dev                # Full dev mode (all services)
npm run dev:react          # Vite dev server (port 5123)
npm run dev:electron       # Electron app
npm run dev:pyserver       # Python FastAPI (via uv run)
npm run build              # Full build (Python exe + React + Electron)
npm run dist:win           # Windows installer
uv sync --group dev        # Install all Python deps (fast!)
uv add <package>           # Add a new Python dependency
```

## MCP (Model Context Protocol) Integration

**Purpose**: Give LLM access to external tools via stdio child processes (JSON-RPC).

### How Tool Calls Work
1. User query → Ollama receives tools array (all registered MCP tools)
2. Ollama returns `tool_call` if needed
3. Backend intercepts in `_handle_mcp_tool_calls()`
4. McpToolManager routes to correct server
5. Result goes back to Ollama for final response

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

**Step 2**: Register in `source/main.py` → `_init_mcp_servers()`
```python
await _mcp_manager.connect_server(
    "tool_name",
    sys.executable,
    [str(PROJECT_ROOT / "mcp_servers" / "servers" / "tool_name" / "server.py")]
)
```

**Step 3**: Restart app — tools auto-register!

### Current Servers
- ✅ **demo**: add, divide
- ✅ **filesystem**: list_directory (partial)
- 📝 Placeholders: gmail, calendar, discord, canvas, websearch

### Debugging
- Check `[MCP]` logs in console
- Test standalone: `python -m mcp_servers.servers.demo.server`
- Tool calls show as cards in UI: `⚙ Used 1 tool: demo > add(a: 42, b: 58) → 100.0`

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

## Database Schema

```sql
CREATE TABLE conversations (
    id TEXT PRIMARY KEY,              -- UUID
    title TEXT,                       -- Auto-generated from first message
    created_at REAL,
    updated_at REAL,                  -- Updated on every new message
    total_input_tokens INTEGER DEFAULT 0,
    total_output_tokens INTEGER DEFAULT 0
)

CREATE TABLE messages (
    num_messages INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT,             -- FK to conversations.id
    role TEXT,                        -- 'user' or 'assistant'
    content TEXT,
    images TEXT,                      -- JSON array: ["path1.png", "path2.png"]
    created_at REAL,
    FOREIGN KEY(conversation_id) REFERENCES conversations(id)
)
```

**Critical**: `check_same_thread=False` for FastAPI thread pool access, JSON serialization for image arrays

## Common Development Tasks

### Add New UI Page
1. Create `src/ui/pages/<PageName>.tsx`
2. Add route in `src/ui/main.tsx`: `<Route path="/path" element={<Page />} />`
3. Add CSS in `src/ui/CSS/<PageName>.css`

### Add New WebSocket Message Type
1. Backend: Add case in `websocket_endpoint()`, use `await broadcast_message("type", content)`
2. Frontend: Add case in `ws.onmessage` switch in App.tsx

### Add New MCP Tool
See MCP section above.

### Modify Database Schema
1. Edit `_init_db()` in database.py
2. Add migration: `try: cursor.execute("ALTER TABLE...") except sqlite3.OperationalError: pass`
3. Update read/write methods

### Change Ollama Model
1. `ollama pull model-name`
2. Search/replace `qwen3-vl:8b-instruct` in main.py
3. Update context limit (token tracking code: `limit: 128000`)
4. Verify tool support (not all models support function calling)

## Architecture Decisions (Critical for LLMs)

**Why `check_same_thread=False` in SQLite?**  
FastAPI uses thread pools; SQLite needs multi-thread access.

**Why refs in App.tsx?**  
WebSocket callbacks capture stale state; refs ensure current values in async operations.

**Why `_server_loop_holder`?**  
Windows Proactor loop can't be accessed from other threads; we schedule coroutines instead.

**Why stdio transport for MCP?**  
Standard MCP protocol; enables child process isolation.

**Why PyInstaller?**  
Bundles Python + deps into single exe for production.

**Why Electron `screen-saver` level?**  
Ensures always-on-top even above full-screen apps.

**Why DPI scaling in ss.py?**  
Windows multi-monitor setups require coordinate transformation for accurate region selection.

---

*Last updated: February 12 2026 | Version: 0.0.0 (pre-release)*
