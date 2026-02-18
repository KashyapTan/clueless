# Configuration Reference

This document covers all configurable aspects of Clueless.

## Python Backend Configuration

### Constants (`source/config.py`)

| Constant | Default | Description |
|----------|---------|-------------|
| `PROJECT_ROOT` | Auto-detected | Root directory of the project |
| `SCREENSHOT_FOLDER` | `user_data/screenshots` | Where screenshots are stored |
| `DEFAULT_PORT` | `8000` | Starting port for the FastAPI server |
| `DEFAULT_MODEL` | `qwen3-vl:8b-instruct` | Default Ollama model |
| `MAX_MCP_TOOL_ROUNDS` | `30` | Maximum tool call iterations per query |
| `GOOGLE_TOKEN_FILE` | `user_data/google/token.json` | Stored OAuth credentials |

### Capture Modes (`CaptureMode` enum)

| Mode | Description |
|------|-------------|
| `fullscreen` | Captures the entire screen automatically |
| `precision` | Opens a region selector overlay for manual selection |
| `none` | No automatic screenshot capture |

### Port Auto-Discovery

The server probes ports starting from `DEFAULT_PORT` (8000) up to 8009. The first available port is used. This prevents conflicts when multiple instances run or when a stale process holds a port.

### CORS Configuration (`source/app.py`)

By default, CORS allows all origins for development:

```python
allow_origins=["*"]
allow_methods=["*"]
allow_headers=["*"]
```

Restrict this in production deployments if needed.

## Electron Configuration

### Window Settings (`src/electron/main.ts`)

| Setting | Value | Purpose |
|---------|-------|---------|
| `width` / `height` | 450 x 450 | Normal mode dimensions |
| Mini mode | 52 x 52 | Minimized dimensions |
| `frame` | `false` | Frameless window |
| `transparent` | `true` | Transparent background |
| `alwaysOnTop` | `true` | Stays on top of other windows |
| `level` | `screen-saver` | On top of even full-screen apps |
| `skipTaskbar` | `true` | Hidden from taskbar |
| `contentProtection` | `true` | Prevents screen recording |

## MCP Server Configuration

### Server Registry (`mcp_servers/config/servers.json`)

Each server entry:

```json
{
    "server_name": {
        "enabled": true,
        "module": "mcp_servers.servers.server_name.server",
        "env": {
            "ENV_VAR": "value"
        }
    }
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `enabled` | Yes | Whether the server is active |
| `module` | Yes | Python module path |
| `env` | No | Environment variables passed to the server process |

### Currently Registered Servers

| Server | Enabled | Tools |
|--------|---------|-------|
| `demo` | Yes | `add`, `divide` |
| `filesystem` | Yes | `list_directory`, `read_file`, `write_file`, `create_folder`, `move_file`, `rename_file` |
| `websearch` | Yes | `search_web_pages`, `read_website` |
| `gmail` | Dynamic | Search, read, send, reply, draft, trash, labels, unread count |
| `calendar` | Dynamic | List events, search, create, update, delete, quick add, free/busy |
| `discord` | No | Placeholder |
| `canvas` | No | Placeholder |

> **Note:** Gmail and Calendar servers are started dynamically only after the user connects their Google account in Settings.

## Frontend Configuration

### Vite Dev Server (`vite.config.ts`)

| Setting | Value |
|---------|-------|
| Port | 5123 |
| Base path | `./` (relative, for Electron) |
| Output directory | `dist-react` |
| Plugin | `@vitejs/plugin-react` |

### Router (`src/ui/main.tsx`)

Uses `createHashRouter` (required for Electron, which uses `file://` protocol):

| Route | Component | Description |
|-------|-----------|-------------|
| `/` | `App` | Main chat interface |
| `/settings` | `Settings` | Application settings (Models, Connections) |
| `/history` | `ChatHistory` | Conversation browser |
| `/album` | Album | Screenshot album |

## Build Configuration

### Electron Builder (`electron-builder.json`)

| Setting | Value |
|---------|-------|
| App ID | `com.kashyap-tanuku.clueless` |
| Product Name | `Clueless` |
| Windows targets | `nsis` (installer), `portable` |
| Architecture | `x64` |
| Extra resources | `dist-python` -> `python-server` |

### PyInstaller (`build-server.spec`)

Bundles the Python backend into a single executable at `dist-python/main.exe`. Includes all Python dependencies and the MCP server files.

## Database Configuration

### SQLite Settings

| Setting | Value | Reason |
|---------|-------|--------|
| `check_same_thread` | `False` | FastAPI uses thread pools |
| Location | `user_data/clueless_app.db` | Persistent across sessions |
| WAL mode | Not enabled | Single-writer is sufficient |

### Settings Table

Application settings are stored as key-value pairs in the `settings` table:

| Key | Value Type | Description |
|-----|-----------|-------------|
| `enabled_models` | JSON array | List of enabled model names |
| `api_key_anthropic` | Encrypted string | Anthropic API key |
| `api_key_openai` | Encrypted string | OpenAI API key |
| `api_key_gemini` | Encrypted string | Google Gemini API key |
| `encryption_salt` | Hex string | Salt for Fernet encryption |

## Environment Variables

| Variable | Used By | Description |
|----------|---------|-------------|
| `GOOGLE_TOKEN_FILE` | Gmail/Calendar MCP | Path to stored OAuth token JSON |
| `GOOGLE_CREDENTIALS_PATH` | Google Auth | Path to OAuth client config (embedded in app) |
| `DISCORD_BOT_TOKEN` | Discord MCP | Discord bot authentication token (Placeholder) |
| `CANVAS_API_TOKEN` | Canvas MCP | Canvas LMS API token (Placeholder) |
| `CANVAS_BASE_URL` | Canvas MCP | Canvas instance URL (Placeholder) |
