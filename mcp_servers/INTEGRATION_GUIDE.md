# Connecting MCP Tools to Your Clueless Chat App

## How it Works (Quick Summary)

When you send a message in the chat:

1. **Your message goes to Ollama** — but now with a list of available tools attached
2. **Ollama decides** — if the message needs a tool (e.g., "add 42 and 58"), it returns a `tool_call` instead of text
3. **The backend intercepts** — `_handle_mcp_tool_calls()` catches tool requests, routes them to the correct MCP server
4. **MCP server executes** — the tool runs and returns a result
5. **Results go back to Ollama** — Ollama gets the tool result and generates its final natural-language response
6. **UI shows everything** — tool calls appear in a "Used X tools" card above the response

```
User: "What's 42 + 58?"
    │
    ▼
Ollama (with tools=[add]) → tool_call: add(a=42, b=58)
    │
    ▼
MCP Demo Server → executes add(42, 58) → returns "100.0"
    │
    ▼
Ollama (with tool result) → "42 + 58 equals 100!"
    │
    ▼
Chat UI: [⚙ Used 1 tool: demo > add(a: 42, b: 58) → 100.0]
          "42 + 58 equals 100!"
```

---

## 3-Step Guide: Connecting Any Tool

### Step 1: Create the MCP Server

Create a new file at `mcp_servers/servers/<your_tool>/server.py`:

```python
from mcp.server.fastmcp import FastMCP

# Create a named server
mcp = FastMCP("your_tool_name")

@mcp.tool()
def my_tool(param1: str, param2: int) -> str:
    """Description of what this tool does.
    
    The docstring becomes the tool description that Ollama sees.
    Be specific — it helps the model know WHEN to call your tool.
    """
    # Your logic here
    result = f"Processed {param1} with value {param2}"
    return result

@mcp.tool()
def another_tool(query: str) -> str:
    """Another tool on the same server."""
    return f"Result for: {query}"

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

**Key rules:**
- Use type hints on ALL parameters — Ollama needs the JSON schema
- Write clear docstrings — this is how Ollama decides when to use your tool
- Return strings (or things that convert to strings)
- The `transport="stdio"` is required — the main app communicates via stdin/stdout

### Step 2: Register in `_init_mcp_servers()`

Open `source/main.py` and find the `_init_mcp_servers()` function (search for "HOW TO ADD YOUR OWN MCP TOOL SERVER"). Add:

```python
await _mcp_manager.connect_server(
    "your_tool_name",           # Name shown in UI badge
    sys.executable,             # Uses the project's Python
    [str(PROJECT_ROOT / "mcp_servers" / "servers" / "your_tool" / "server.py")]
)
```

If your server needs environment variables (API keys, etc.):

```python
await _mcp_manager.connect_server(
    "gmail",
    sys.executable,
    [str(PROJECT_ROOT / "mcp_servers" / "servers" / "gmail" / "server.py")],
    env={"GOOGLE_CREDENTIALS_FILE": "/path/to/credentials.json"}
)
```

### Step 3: Restart the App

That's it. Restart `main.py` and your tools will:
- Auto-register with Ollama
- Appear in tool call cards when used
- Show the server name badge in the UI

---

## Example: Building a Web Search Tool

```python
# mcp_servers/servers/websearch/server.py
import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("websearch")

@mcp.tool()
def search_web(query: str, num_results: int = 5) -> str:
    """Search the web for current information.
    
    Use this when the user asks about recent events, current data,
    or anything that requires up-to-date information.
    """
    # Example using a search API
    response = httpx.get(
        "https://api.example.com/search",
        params={"q": query, "limit": num_results}
    )
    results = response.json()
    return "\n".join(f"- {r['title']}: {r['snippet']}" for r in results)

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

Then in `_init_mcp_servers()`:
```python
await _mcp_manager.connect_server(
    "websearch",
    sys.executable,
    [str(PROJECT_ROOT / "mcp_servers" / "servers" / "websearch" / "server.py")]
)
```

---

## How the Code Flow Works (Technical)

### Backend (`source/main.py`)

1. **`McpToolManager`** — manages connections to MCP server subprocesses
   - `connect_server()` — launches a server, does handshake, discovers tools
   - `call_tool()` — routes a call to the right server
   - `get_ollama_tools()` — returns tool schemas in Ollama format

2. **`_init_mcp_servers()`** — called at app startup, connects all servers

3. **`_handle_mcp_tool_calls()`** — the tool-calling loop:
   - Makes a non-streamed Ollama call with `tools=` parameter
   - If Ollama returns `tool_calls`, executes them via `_mcp_manager.call_tool()`
   - Broadcasts `tool_call` WebSocket events to the UI
   - Appends tool results to messages and asks Ollama again
   - Loops until Ollama gives a text response (max 5 rounds)

4. **Inside `_stream_ollama_chat()` → `producer()`**:
   - Before streaming, runs the MCP tool-calling phase
   - The tool results get added to the message context
   - Then the final streamed response has full tool context

### Frontend (`src/ui/pages/App.tsx`)

1. **WebSocket handlers**:
   - `tool_call` message (status: "calling") — updates status bar
   - `tool_call` message (status: "complete") — accumulates into `toolCallsRef`
   - `tool_calls_summary` — backup sync of all tool calls
   - `response_complete` — saves `toolCalls` into chat history

2. **Rendering**: Each assistant message checks for `msg.toolCalls` and renders a "Used N tools" card with server badge, function call, and result.

---

## Debugging Tips

### Check if tools are registered
Look for these lines in the console when the app starts:
```
[MCP] Registered tool: add (from demo)
[MCP] Connected to 'demo' — 1 tool(s)
[MCP] Ready — 1 total tool(s) available
```

### Test a tool independently
```bash
python -m mcp_servers.test_demo
```

### Tool not being called?
- Make sure your docstring clearly describes WHEN to use the tool
- Try being explicit: "Use the add tool to add 42 and 58"
- Check that the model supports tool calling (qwen3 does)

### Server won't connect?
- Run the server directly: `python mcp_servers/servers/your_tool/server.py`
- Check for import errors or missing dependencies
- Make sure `transport="stdio"` is set

---

## File Reference

| File | Purpose |
|------|---------|
| `source/main.py` | `McpToolManager` class, `_init_mcp_servers()`, `_handle_mcp_tool_calls()` |
| `mcp_servers/servers/<name>/server.py` | Each MCP tool server |
| `mcp_servers/client/ollama_bridge.py` | Standalone test bridge (not used by main app) |
| `mcp_servers/test_demo.py` | Quick test script |
| `src/ui/pages/App.tsx` | Frontend tool call handling & rendering |
| `src/ui/CSS/App.css` | Tool call card styling |
