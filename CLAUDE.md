# CLAUDE.md - Clueless Project Documentation

This file provides guidance to Claude Code (claude.ai/code) when working with this codebase.

## Project Overview

**Clueless** is an AI-powered desktop assistant built with Electron, React, and Python. It provides a floating, always-on-top window that allows users to:
- Chat with an LLM (Ollama) with or without screenshots
- Take region-selective screenshots via hotkey (Ctrl+Shift+Alt+S)
- Stream AI responses in real-time via WebSocket

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Electron Main Process                     │
│  (src/electron/main.ts)                                      │
│  - Creates frameless, transparent, always-on-top window     │
│  - Manages Python server lifecycle                          │
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
- **Ollama** for LLM inference (qwen3-vl for vision, qwen3 for text-only)
- **pynput** for global hotkey detection
- **Pillow** for screenshot capture
- **tkinter** for region selection UI

### Desktop
- **Electron** for cross-platform desktop app
- Frameless, transparent window with always-on-top

## Directory Structure

```
clueless/
├── src/
│   ├── electron/           # Electron main process
│   │   ├── main.ts         # Window creation, Python lifecycle
│   │   ├── pythonApi.ts    # Python server management
│   │   ├── utils.ts        # Dev/prod helpers
│   │   └── preload.js      # IPC bridge (if needed)
│   └── ui/                 # React frontend
│       ├── App.tsx         # Main component, WebSocket logic
│       ├── App.css         # Styles
│       └── main.tsx        # React entry point
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
- Manages screenshot lifecycle and chat history

### `source/ss.py`
- `ScreenshotService`: Global hotkey listener (Ctrl+Shift+Alt+S)
- `RegionSelector`: Full-screen overlay with:
  - Dimmed background
  - Click-and-drag selection
  - Live preview of selected region
  - High-DPI support for Windows
- Handles coordinate transformation for scaled displays

### `src/ui/App.tsx`
- Main React component
- WebSocket connection with auto-reconnect
- Chat history display with markdown rendering
- Collapsible "thinking" section for model reasoning
- Screenshot indicator when image is attached

### `src/electron/main.ts`
- Creates BrowserWindow with frameless, transparent, always-on-top settings
- Starts/stops Python server in production mode
- Handles graceful cleanup on close

## Development Commands

```bash
# Full development mode (all services)
npm run dev

# Individual services
npm run dev:react      # Vite dev server (port 5123)
npm run dev:electron   # Electron app
npm run dev:pyserver   # Python FastAPI server
npm run dev:ollama     # Ollama server

# Build
npm run build          # Full build (Python + React + Electron)
npm run dist:win       # Build Windows installer

# Linting
npm run lint
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
2. Python sends `screenshot_start` → UI hides
3. Region selector overlay appears (tkinter)
4. User drags to select region
5. Screenshot saved to `screenshots/` folder
6. Python sends `screenshot_ready` → UI shows with indicator
7. User types query → sent with screenshot to Ollama
8. Response streamed back via WebSocket

## Model Selection

- **With screenshot**: Uses `qwen3-vl:8b-instruct` (vision-language model)
- **Text-only**: Uses `qwen3:8b` (text model)

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
# In main.py - schedule coroutines from background threads
def safe_schedule(coro):
    loop.call_soon_threadsafe(asyncio.create_task, coro)
```

### Coordinate Transformation
```python
# Screenshot coordinates vs Tkinter coordinates
scale_x = screen_width / tk_width
actual_x = int(tk_x * scale_x)
```

## Configuration

### Python Dependencies (`requirements.txt`)
- fastapi, uvicorn
- ollama
- pillow
- pynput

### Node Dependencies (`package.json`)
- react, react-dom
- react-markdown, react-syntax-highlighter
- electron, electron-builder
- vite, typescript

## Notes for Development

1. **Always run Ollama first**: The app expects Ollama to be running on port 11434
2. **Screenshot folder**: Temporary files stored in `screenshots/`, auto-cleaned
3. **Port handling**: FastAPI auto-finds available port starting from 8000
4. **Graceful shutdown**: Multiple cleanup handlers ensure Python processes terminate

## Common Issues

1. **"Ollama not found"**: Ensure Ollama is installed and `ollama serve` is running
2. **Screenshot coordinates off**: Check DPI scaling, the code handles multiple Windows versions
3. **WebSocket disconnects**: Auto-reconnects after 2 seconds, state preserved
4. **Window not showing**: Check if hidden due to screenshot capture (opacity 0)
