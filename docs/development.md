# Development Guide

This guide covers common development tasks, code patterns, and conventions used in Clueless.

## Development Commands

| Command | Description |
|---------|-------------|
| `npm run dev` | Full dev mode (React + Electron + Python) |
| `npm run dev:react` | Vite dev server on port 5123 |
| `npm run dev:electron` | Electron app (expects React dev server) |
| `npm run dev:pyserver` | Python FastAPI server via UV |
| `npm run build` | Production build (Python exe + React + Electron) |
| `npm run dist:win` | Windows installer via electron-builder |
| `npm run install:python` | Install Python deps via UV |
| `uv sync --group dev` | Install all Python deps including dev tools |
| `uv add <package>` | Add a new Python dependency |

## Code Conventions

### Python Backend

- **Async-first**: All API handlers are async. CPU-bound work uses `asyncio.to_thread()`.
- **State management**: Global state lives in `AppState` (singleton in `source/core/state.py`).
- **Thread safety**: Use `app_state.server_loop_holder` to schedule coroutines from non-async threads.
- **Logging**: Use `print()` with `[MODULE]` prefixes (e.g., `[MCP]`, `[WS]`, `[SS]`).
- **Constants**: All magic numbers and defaults live in `source/config.py`.
- **Security**: Never commit secrets. Use `KeyManager` for sensitive user data.

### React Frontend

- **Hooks over classes**: All components are functional with hooks.
- **Ref pattern**: Use `useRef` alongside `useState` for values accessed in WebSocket callbacks to avoid stale closures.
- **Modular components**: Keep components focused; delegate to sub-components.
- **CSS-per-component**: Each major component has a corresponding CSS file.
- **Type safety**: All interfaces live in `src/ui/types/index.ts`.

### Naming Conventions

| Item | Convention | Example |
|------|-----------|---------|
| Python files | `snake_case.py` | `ollama_provider.py` |
| Python classes | `PascalCase` | `AppState`, `McpToolManager` |
| Python functions | `snake_case` | `submit_query()` |
| React components | `PascalCase.tsx` | `ChatMessage.tsx` |
| React hooks | `use*.ts` | `useChatState.ts` |
| CSS files | `PascalCase.css` | `ChatHistory.css` |
| WebSocket types | `snake_case` | `submit_query`, `response_chunk` |

## Common Tasks

### Adding a New UI Page

1. Create the component in `src/ui/pages/NewPage.tsx`
2. Add the route in `src/ui/main.tsx`:
   ```tsx
   import NewPage from './pages/NewPage'
   // In the router:
   { path: '/new-page', element: <NewPage /> }
   ```
3. Create the stylesheet in `src/ui/CSS/NewPage.css`
4. Add navigation link in `TitleBar.tsx` if needed

### Adding a New WebSocket Message Type

**Backend (Python):**

1. Add the message type handler in `source/api/handlers.py`:
   ```python
   async def _handle_new_message(self, data: dict) -> None:
       # Process the message
       result = await some_operation()
       await self.connection_manager.broadcast_json("new_message_response", result)
   ```

2. Register it in `source/api/websocket.py` in the message routing:
   ```python
   elif msg_type == "new_message":
       await handler._handle_new_message(data)
   ```

**Frontend (React):**

3. Handle the response in `App.tsx`'s WebSocket message handler:
   ```tsx
   case 'new_message_response':
       // Update state
       break;
   ```

### Adding a New REST API Endpoint

1. Add the endpoint in `source/api/http.py`:
   ```python
   @router.get("/api/new-endpoint")
   async def new_endpoint():
       return {"data": "value"}
   ```

2. Add the client method in `src/ui/services/api.ts`:
   ```typescript
   async getNewData(): Promise<any> {
       const response = await fetch(`${this.baseUrl}/api/new-endpoint`);
       return response.json();
   }
   ```

### Adding a New MCP Tool Server

See the dedicated [MCP Guide](./mcp-guide.md) for detailed instructions.

### Modifying the Database Schema

1. Edit `_init_db()` in `source/database.py` to add the new table or column
2. Add a migration for existing databases:
   ```python
   try:
       cursor.execute("ALTER TABLE conversations ADD COLUMN new_field TEXT DEFAULT ''")
   except sqlite3.OperationalError:
       pass  # Column already exists
   ```
3. Update the corresponding read/write methods
4. If the change affects the frontend, update `src/ui/types/index.ts`

### Adding a Cloud Provider

1. Implement streaming logic in `source/llm/cloud_provider.py`
2. Update `source/llm/router.py` to handle the new provider prefix
3. Add API key management support in `source/api/http.py` and `SettingsApiKey.tsx`
4. Register available models in `source/api/http.py`

## Google OAuth Setup

The app uses an embedded OAuth client configuration for Google authentication.
The configuration is loaded from `GOOGLE_CLIENT_CONFIG` in `source/config.py`.

To update the OAuth client:
1. Download `client_secret_*.json` from Google Cloud Console
2. Update the `GOOGLE_CLIENT_CONFIG` dictionary in `source/config.py`
3. Ensure scopes in `GOOGLE_SCOPES` match the required permissions

## Architecture Patterns

### Cross-Thread Communication

The hotkey listener runs in a dedicated thread, but needs to trigger WebSocket broadcasts on the asyncio event loop:

```python
# In the hotkey thread (ss.py):
loop = app_state.server_loop_holder
if loop:
    asyncio.run_coroutine_threadsafe(
        broadcast_screenshot(data),
        loop
    )
```

### Streaming Response Handling

**Ollama (Local):**
Uses a producer-consumer pattern with a background thread reading the synchronous iterator and an asyncio queue for the main loop.

**Cloud Providers:**
Use native async streaming APIs directly in the main event loop (no background threads needed).

### WebSocket Ref Pattern (React)

```tsx
// State for rendering
const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
// Ref for WebSocket callbacks (avoids stale closure)
const chatHistoryRef = useRef(chatHistory);

useEffect(() => {
    chatHistoryRef.current = chatHistory;
}, [chatHistory]);

// In WebSocket handler:
const currentHistory = chatHistoryRef.current; // Always current
```

## Build and Packaging

### PyInstaller Build

The Python backend is bundled into a single executable:

```bash
pyinstaller build-server.spec
```

Output goes to `dist-python/main.exe`, which is included as an extra resource in the Electron package.

### Electron Builder

Configuration in `electron-builder.json`:
- Bundles `dist-electron/` (compiled TypeScript) and `dist-react/` (built frontend)
- Copies `dist-python/` as `python-server/` extra resource
- Targets: NSIS installer and portable for Windows x64
