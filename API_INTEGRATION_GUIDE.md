# API Integration Guide

This guide explains how to create APIs, connect Python endpoints to the React frontend, and follow production best practices.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                       React Frontend                                │
│  (src/ui/)                                                          │
│                                                                     │
│  ┌─────────────────┐    ┌─────────────────┐    ┌────────────────┐  │
│  │ Components      │    │ Hooks           │    │ Services       │  │
│  │ (UI rendering)  │ ←→ │ (state logic)   │ ←→ │ (API calls)    │  │
│  └─────────────────┘    └─────────────────┘    └───────┬────────┘  │
│                                                        │           │
└────────────────────────────────────────────────────────│───────────┘
                                                         │
                    ┌────────────────────────────────────┘
                    │
                    ▼ WebSocket (ws://localhost:8000/ws)
                    │ or HTTP REST (http://localhost:8000/api/...)
                    │
┌───────────────────│─────────────────────────────────────────────────┐
│                   │           Python Backend                        │
│                   │           (source/)                             │
│                   │                                                 │
│  ┌────────────────▼─────────────┐    ┌──────────────────────────┐  │
│  │ API Layer (source/api/)      │    │ Services                 │  │
│  │ - websocket.py (real-time)   │ →  │ - conversations.py       │  │
│  │ - http.py (REST endpoints)   │    │ - screenshots.py         │  │
│  └──────────────────────────────┘    └──────────────────────────┘  │
│                                                   │                 │
│  ┌──────────────────────────────┐    ┌───────────▼──────────────┐  │
│  │ LLM (source/llm/)            │    │ Core (source/core/)      │  │
│  │ - ollama.py                  │    │ - state.py               │  │
│  └──────────────────────────────┘    │ - connection.py          │  │
│                                      └──────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

## Two Types of Communication

### 1. WebSocket (Real-time, Bidirectional)

Use WebSocket for:
- Streaming responses (LLM output)
- Real-time events (screenshot captured, tool calls)
- Bidirectional communication (send query, receive stream)
- Chat history updates

### 2. HTTP REST (Request/Response)

Use HTTP for:
- One-time data fetches (get available models)
- Configuration updates
- Health checks
- CRUD operations that don't need streaming

---

## Adding a WebSocket API

### Step 1: Add Handler in Python

Edit `source/api/handlers.py`:

```python
async def _handle_your_action(self, data: Dict[str, Any]):
    """Handle your action."""
    some_param = data.get("some_param")
    
    # Do something
    result = await some_service.do_something(some_param)
    
    # Send response back to client
    await self.websocket.send_text(json.dumps({
        "type": "your_action_result",
        "content": json.dumps(result)
    }))
```

### Step 2: Add to API Service (Frontend)

Edit `src/ui/services/api.ts`:

```typescript
export interface ApiService {
  // ... existing methods
  yourAction: (param: string) => void;
}

export function createApiService(send: (msg: Record<string, unknown>) => void): ApiService {
  return {
    // ... existing methods
    
    yourAction(param: string) {
      send({ type: 'your_action', some_param: param });
    },
  };
}
```

### Step 3: Handle Response (Frontend)

In your component or hook, add a case to the WebSocket message handler:

```typescript
case 'your_action_result': {
  const result = JSON.parse(data.content as string);
  // Do something with result
  break;
}
```

---

## Implemented HTTP REST API

### `source/api/http.py`

The following endpoints are now available:

```python
# ============================================
# Health Check
# ============================================
GET /api/health
Returns: {"status": "healthy"}

# ============================================
# Models API
# ============================================
GET /api/models/ollama
Returns: List of installed models with details:
[
  {
    "name": "qwen3-vl:8b-instruct",
    "size": 123456789,
    "parameter_size": "8.5B",
    "quantization": "Q4_0"
  }
]

GET /api/models/enabled
Returns: List of enabled model names (e.g., ["qwen3-vl:8b-instruct"])

PUT /api/models/enabled
Body: {"models": ["model1", "model2"]}
Returns: {"status": "updated", "models": [...]}
```

### Registering Routes

Routes are registered in `source/app.py`:

```python
app.include_router(http_router)
```

### Step 3: Call from Frontend

Edit `src/ui/services/api.ts`:

```typescript
const HTTP_BASE_URL = 'http://localhost:8000';

export const api = {
  /**
   * Fetch available models.
   */
  async getModels(): Promise<string[]> {
    const response = await fetch(`${HTTP_BASE_URL}/api/models`);
    if (!response.ok) throw new Error('Failed to fetch models');
    return response.json();
  },

  /**
   * Get current settings.
   */
  async getSettings(): Promise<{ capture_mode: string; model: string }> {
    const response = await fetch(`${HTTP_BASE_URL}/api/settings`);
    if (!response.ok) throw new Error('Failed to fetch settings');
    return response.json();
  },

  /**
   * Update settings.
   */
  async updateSettings(settings: { model?: string; capture_mode?: string }): Promise<void> {
    const response = await fetch(`${HTTP_BASE_URL}/api/settings`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(settings),
    });
    if (!response.ok) throw new Error('Failed to update settings');
  },
};
```

### Step 4: Use in Component

```typescript
import { api } from '../services/api';

function SettingsPage() {
  const [models, setModels] = useState<string[]>([]);

  useEffect(() => {
    api.getModels().then(setModels).catch(console.error);
  }, []);

  return (
    <select>
      {models.map(model => (
        <option key={model} value={model}>{model}</option>
      ))}
    </select>
  );
}
```

---

## Best Practices

### Python Backend

1. **Use Services for Business Logic**
   ```python
   # Good: Logic in service
   @router.get("/conversations")
   async def get_conversations():
       return ConversationService.get_conversations()
   
   # Bad: Logic in route
   @router.get("/conversations")
   async def get_conversations():
       return db.execute("SELECT * FROM conversations...")
   ```

2. **Use Pydantic for Request/Response Models**
   ```python
   class CreateConversationRequest(BaseModel):
       title: str
       model: str = "qwen3-vl:8b-instruct"
   
   @router.post("/conversations")
   async def create_conversation(req: CreateConversationRequest):
       return ConversationService.create(req.title, req.model)
   ```

3. **Handle Errors Gracefully**
   ```python
   @router.get("/conversations/{id}")
   async def get_conversation(id: str):
       conv = ConversationService.get(id)
       if not conv:
           raise HTTPException(status_code=404, detail="Conversation not found")
       return conv
   ```

### React Frontend

1. **Use Custom Hooks for State**
   ```typescript
   // Good: State in hook
   const { models, loading, error } = useModels();
   
   // Bad: State scattered in component
   const [models, setModels] = useState([]);
   const [loading, setLoading] = useState(false);
   // etc.
   ```

2. **Centralize API Calls**
   ```typescript
   // Good: Centralized in services/api.ts
   const models = await api.getModels();
   
   // Bad: Fetch calls everywhere
   const response = await fetch('http://localhost:8000/api/models');
   ```

3. **Type Everything**
   ```typescript
   // Good: Typed response
   interface Model {
     name: string;
     size: number;
   }
   const models: Model[] = await api.getModels();
   
   // Bad: Any types
   const models = await api.getModels(); // unknown type
   ```

---

## File Structure Reference

### Python Backend (source/)
```
source/
├── main.py           # Entry point
├── app.py            # FastAPI app factory
├── config.py         # Configuration
├── database.py       # SQLite operations
├── ss.py             # Screenshot service
│
├── api/              # API layer
│   ├── __init__.py
│   ├── websocket.py  # WebSocket endpoint
│   ├── handlers.py   # WebSocket message handlers
│   └── http.py       # HTTP REST endpoints (IMPLEMENTED)
│
├── core/             # Core utilities
│   ├── __init__.py
│   ├── state.py      # Global state
│   ├── connection.py # WebSocket connections
│   └── lifecycle.py  # Startup/shutdown
│
├── services/         # Business logic
│   ├── __init__.py
│   ├── conversations.py
│   └── screenshots.py
│
├── mcp_integration/  # MCP integration
│   ├── __init__.py
│   ├── manager.py
│   └── handlers.py
│
└── llm/              # LLM integration
    ├── __init__.py
    └── ollama.py
```

### React Frontend (`src/ui/`)
```
src/ui/
├── main.tsx          # Entry point
│
├── pages/            # Page components
│   ├── App.tsx       # Main chat - orchestrates hooks
│   ├── Settings.tsx
│   └── ChatHistory.tsx
│
├── components/       # Reusable components
│   ├── chat/
│   │   ├── ChatMessage.tsx
│   │   ├── ResponseArea.tsx
│   │   └── ...
│   ├── input/
│   │   ├── QueryInput.tsx
│   │   ├── ModeSelector.tsx
│   │   └── ...
│   └── Layout.tsx
│
├── hooks/            # Custom hooks
│   ├── useChatState.ts   # Core chat logic
│   ├── useWebSocket.ts   # Connection wrapper
│   ├── useScreenshots.ts # Image management
│   └── useTokenUsage.ts  # Token tracking
│
├── services/         # API layer
│   ├── index.ts
│   └── api.ts        # HTTP API wrappers
│
├── types/            # TypeScript types
│   └── index.ts
│
├── utils/            # Utilities
│   └── clipboard.ts
│
└── CSS/              # Stylesheets
    └── ...
```


---

## Quick Reference: Adding a Feature

### Example: Add "Get Conversation Stats" API

**1. Python Service** (`source/services/conversations.py`):
```python
@staticmethod
def get_stats(conversation_id: str) -> dict:
    """Get statistics for a conversation."""
    from ..database import db
    conv = db.get_conversation(conversation_id)
    return {
        "message_count": len(db.get_messages(conversation_id)),
        "token_count": conv.get("total_tokens", 0),
        "created_at": conv.get("created_at"),
    }
```

**2. HTTP Route** (`source/api/http.py`):
```python
@router.get("/conversations/{id}/stats")
async def get_conversation_stats(id: str):
    from ..services.conversations import ConversationService
    stats = ConversationService.get_stats(id)
    if not stats:
        raise HTTPException(404, "Conversation not found")
    return stats
```

**3. Frontend API** (`src/ui/services/api.ts`):
```typescript
async getConversationStats(id: string): Promise<ConversationStats> {
  const response = await fetch(`${HTTP_BASE_URL}/api/conversations/${id}/stats`);
  if (!response.ok) throw new Error('Failed to fetch stats');
  return response.json();
}
```

**4. Frontend Hook** (`src/ui/hooks/useConversationStats.ts`):
```typescript
export function useConversationStats(id: string) {
  const [stats, setStats] = useState<ConversationStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    api.getConversationStats(id)
      .then(setStats)
      .catch(setError)
      .finally(() => setLoading(false));
  }, [id]);

  return { stats, loading, error };
}
```

**5. Component Usage**:
```typescript
function ConversationDetails({ id }: { id: string }) {
  const { stats, loading, error } = useConversationStats(id);
  
  if (loading) return <Spinner />;
  if (error) return <Error message={error.message} />;
  
  return <StatsDisplay stats={stats} />;
}
```

---

## Summary

| Communication | Use For | Example |
|---------------|---------|---------|
| **WebSocket** | Real-time, streaming, bidirectional | Chat messages, LLM responses, events |
| **HTTP GET** | Fetching data | Get models, get settings |
| **HTTP POST** | Creating resources | Create conversation |
| **HTTP PUT** | Updating resources | Update settings |
| **HTTP DELETE** | Deleting resources | Delete conversation |

Always:
1. Put business logic in **services**
2. Keep API routes thin (just route to services)
3. Use **types** for everything
4. Centralize API calls in **services/api.ts**
5. Use **custom hooks** for state management
