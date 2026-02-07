# CLAUDE.md - Clueless Project Documentation

This file provides guidance to Claude Code (claude.ai/code) when working with this codebase.

## Project Overview

**Clueless** is an AI-powered desktop assistant built with Electron, React, and Python. It provides a floating, always-on-top window that allows users to:
- Chat with an LLM (Ollama) with or without screenshots
- Take region-selective screenshots via hotkey (Ctrl+Shift+Alt+S)
- Stream AI responses in real-time via WebSocket
- Multi-turn conversations with persistent chat history
- Multiple capture modes (fullscreen, region, meeting recording — UI scaffolded)

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Electron Main Process                     │
│  (src/electron/main.ts)                                      │
│  - Creates frameless, transparent, always-on-top window     │
│  - Manages Python server lifecycle (prod only)              │
│  - Content protection enabled, skips taskbar                │
└────────────────────┬────────────────────────────────────────┘
                     │
         ┌───────────┴───────────┐
         ▼                       ▼
┌─────────────────────┐  ┌─────────────────────────────────────┐
│   React Frontend    │  │         Python Backend               │
│   (src/ui/)         │◄─┤         (source/)                    │
│                     │  │                                      │
│ - App.tsx: Main UI  │  │ - main.py: FastAPI WebSocket server │
│ - WebSocket client  │  │ - ss.py: Screenshot service          │
│ - Markdown render   │  │ - Ollama integration                 │
│ - Nav bar & modes   │  │ - Multi-turn chat history            │
└─────────────────────┘  └─────────────────────────────────────┘
         │                           │
         │    WebSocket (ws://localhost:8000/ws)
         └───────────────────────────┘
```

## Tech Stack

### Frontend
- **React 19** with TypeScript
- **Vite** for bundling
- **react-markdown** + **react-syntax-highlighter** for rendering
- WebSocket for real-time communication

### Backend
- **Python 3.11+** with FastAPI
- **Ollama** for LLM inference (uses `qwen3-vl:8b-instruct` for all queries)
- **pynput** for global hotkey detection
- **Pillow** for screenshot capture
- **tkinter** for region selection UI

### Desktop
- **Electron 37+** for cross-platform desktop app
- Frameless, transparent window with always-on-top (`screen-saver` level)
- Content protection enabled, skips taskbar

## Directory Structure

```
clueless/
├── src/
│   ├── electron/           # Electron main process
│   │   ├── main.ts         # Window creation, Python lifecycle
│   │   ├── pythonApi.ts    # Python server management
│   │   ├── pcResources.ts  # Resource path helpers
│   │   ├── utils.ts        # Dev/prod helpers
│   │   └── tsconfig.json   # Electron-specific TS config
│   └── ui/                 # React frontend
│       ├── App.tsx         # Main component, WebSocket logic
│       ├── App.css         # Styles
│       ├── main.tsx        # React entry point
│       └── assets/         # UI icons and images
│           ├── transparent-clueless-logo.png
│           ├── settings-icon.svg
│           ├── chat-history-icon.svg
│           ├── new-chat-icon.svg
│           ├── plus-icon.svg
│           ├── mic-icon.svg
│           ├── entire-screen-shot-icon.svg
│           ├── region-screen-shot-icon.svg
│           ├── meeting-record-icon.svg
│           └── recorded-meetings-album-icon.svg
├── source/                 # Python backend
│   ├── main.py             # FastAPI server, Ollama streaming
│   └── ss.py               # Screenshot service, region selector
├── dist-electron/          # Compiled Electron code
├── dist-react/             # Built React app
├── dist-python/            # Bundled Python (PyInstaller)
├── screenshots/            # Temporary screenshot storage
├── scripts/                # Build scripts
│   ├── build-python.mjs    # Python bundling
│   └── build-python-exe.py # PyInstaller config
└── package.json            # Node dependencies & scripts
```

## Key Files

### `source/main.py`
- FastAPI WebSocket server on port 8000 (auto-finds available port)
- Handles bidirectional messaging:
  - Client → Server: `submit_query`, `clear_context`
  - Server → Client: `ready`, `screenshot_start`, `screenshot_ready`, `query`, `thinking_chunk`, `thinking_complete`, `response_chunk`, `response_complete`, `error`, `context_cleared`
- Streams Ollama responses token-by-token
- Manages screenshot lifecycle and multi-turn chat history
- Uses a dedicated event loop holder (`_server_loop_holder`) so worker threads can schedule coroutines on the server's asyncio loop
- Graceful cleanup via `atexit`, `SIGINT`, and `SIGTERM` handlers

### `source/ss.py`
- `ScreenshotService`: Global hotkey listener (Ctrl+Shift+Alt+S)
  - Thread-safe capture gating via `_lock` to prevent concurrent captures
  - Supports `callback` (on capture complete) and `start_callback` (on capture begin)
- `RegionSelector`: Full-screen overlay with:
  - Dimmed background
  - Click-and-drag selection
  - Live preview of selected region
  - High-DPI support for Windows
- Handles coordinate transformation for scaled displays

### `src/ui/App.tsx`
- Main React component with full navigation bar:
  - **Left nav**: Settings, Chat History, Recorded Meetings Album buttons
  - **Right nav**: New Chat, Clueless logo
  - **Draggable title bar** (blank space between nav items)
- Multi-turn chat history display with markdown rendering
- Collapsible "thinking" section for model reasoning
- Screenshot indicator with clear context button
- **Mode selection bar** (bottom): Fullscreen SS, Region SS, Meeting Recorder (UI scaffolded, toggle state only)
- **Model selection dropdown** (UI placeholder: GPT-4, GPT-3.5 — not yet wired to backend)
- **Voice input button** (UI placeholder — not yet implemented)
- **Attachments button** (UI placeholder — not yet implemented)
- `electronAPI` bridge for window focus (`window.electronAPI.focusWindow()`)
- Uses refs (`currentQueryRef`, `responseRef`, `thinkingRef`) to capture values correctly during async WebSocket handling

### `src/electron/main.ts`
- Creates BrowserWindow: 400×400, frameless, transparent, always-on-top (`screen-saver` level)
- `setContentProtection(true)` — prevents screen capture of the window
- `skipTaskbar: true` — window hidden from taskbar
- Starts/stops Python server in production mode only (dev uses `dev:pyserver` script)
- Multiple cleanup handlers: `closed`, `close`, `window-all-closed`, `before-quit`, `will-quit`
- No preload script currently configured in `webPreferences`

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
```

## WebSocket Protocol

### Client → Server
```json
{"type": "submit_query", "content": "Your question here"}
{"type": "clear_context"}
```

### Server → Client
```json
{"type": "ready", "content": "Server ready..."}
{"type": "screenshot_start", "content": "..."}
{"type": "screenshot_ready", "content": "Screenshot captured..."}
{"type": "query", "content": "Echo of user query"}
{"type": "thinking_chunk", "content": "...partial thinking..."}
{"type": "thinking_complete", "content": ""}
{"type": "response_chunk", "content": "...partial response..."}
{"type": "response_complete", "content": ""}
{"type": "context_cleared", "content": "Context cleared..."}
{"type": "error", "content": "Error message"}
```

## Screenshot Flow

1. User presses Ctrl+Shift+Alt+S
2. Python sends `screenshot_start` → UI hides (opacity 0)
3. Region selector overlay appears (tkinter)
4. User drags to select region
5. Screenshot saved to `screenshots/` folder
6. Python sends `screenshot_ready` → UI shows with screenshot indicator
7. Chat history is cleared for the new screenshot context
8. User types query → sent with screenshot to Ollama
9. Response streamed back via WebSocket
10. Follow-up questions retain the screenshot and build on chat history

## Multi-Turn Chat

- Chat history is maintained in both frontend (`chatHistory` state) and backend (`_chat_history` list)
- The first message in history includes the screenshot image (if available); follow-ups are text-only
- `clear_context` resets both screenshot and chat history on both sides
- Taking a new screenshot automatically clears previous chat history
- Completed exchanges are added to history on `response_complete`

## Model Selection

- Currently always uses `qwen3-vl:8b-instruct` (vision-language model) for all queries
- The UI has a model selector dropdown (GPT-4 / GPT-3.5) but it is **not yet connected** to the backend

## Important Patterns

### High-DPI Handling (Windows)
```python
# In ss.py - multiple fallback methods for DPI awareness
ctypes.windll.shcore.SetProcessDpiAwarenessContext(-4)  # Best
ctypes.windll.shcore.SetProcessDpiAwareness(2)          # Fallback
ctypes.windll.user32.SetProcessDPIAware()               # Legacy
```

### Thread-Safe WebSocket Broadcasting
```python
# In main.py - schedule coroutines from background threads onto the server loop
_server_loop_holder: Dict[str, Any] = {}

def safe_schedule(coro):
    loop.call_soon_threadsafe(asyncio.create_task, coro)
```

### Coordinate Transformation
```python
# Screenshot coordinates vs Tkinter coordinates
scale_x = screen_width / tk_width
actual_x = int(tk_x * scale_x)
```

### Streaming Lock
```python
# In main.py - prevents concurrent Ollama streams
_stream_lock = asyncio.Lock()
```

## Configuration

### Python Dependencies (`requirements.txt`)
- fastapi, uvicorn, websockets
- ollama
- pillow
- pynput
- python-multipart, requests
- pyinstaller (build tool)

### Node Dependencies (`package.json`)
- react 19, react-dom
- react-markdown, react-syntax-highlighter
- electron 37+, electron-builder
- vite, typescript, cross-env, npm-run-all

## Notes for Development

1. **Always run Ollama first**: The app expects Ollama to be running on port 11434
2. **Screenshot folder**: Temporary files stored in `screenshots/`, auto-cleaned on new capture and shutdown
3. **Port handling**: FastAPI auto-finds available port starting from 8000 (up to 10 attempts)
4. **Graceful shutdown**: Multiple cleanup handlers (atexit, signals, Electron events) ensure Python processes terminate
5. **Virtual environment**: Uses `.venv` — activate before running Python commands
6. **Dev mode**: `npm run dev` starts all 4 services in parallel (React, Electron, Python, Ollama)

## Planned / Scaffolded Features (UI exists, not yet wired)

- **Fullscreen screenshot mode**: Toggle exists in UI
- **Meeting recording mode**: Toggle exists in UI
- **Voice input**: Mic button in input area
- **File attachments**: Plus button in input area
- **Model selection**: Dropdown in input area (GPT-4 / GPT-3.5 options)
- **Settings panel**: Button in nav bar
- **Chat history browser**: Button in nav bar
- **Recorded meetings album**: Button in nav bar
- **New chat**: Button in nav bar (could trigger `clear_context`)

## Common Issues

1. **"Ollama not found"**: Ensure Ollama is installed and `ollama serve` is running
2. **Screenshot coordinates off**: Check DPI scaling, the code handles multiple Windows versions
3. **WebSocket disconnects**: Auto-reconnects after 2 seconds, state preserved
4. **Window not showing**: Check if hidden due to screenshot capture (opacity 0)
5. **electronAPI undefined**: Preload script not currently configured in BrowserWindow; `window.electronAPI` will be undefined
