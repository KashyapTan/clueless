# MCP Integration Guide

This guide covers the Model Context Protocol (MCP) integration in Clueless, how to use existing tools, and how to build new ones.

## What is MCP?

The Model Context Protocol is a standardized way to give LLMs access to external tools. Think of it as a "USB port for AI" -- any tool that implements the MCP interface can be plugged into any MCP-compatible LLM application.

**Key concepts:**
- **Transport**: Clueless uses `stdio` (standard input/output) to communicate with MCP servers
- **Protocol**: JSON-RPC 2.0 over the transport layer
- **Tool Discovery**: Servers declare their available tools with JSON Schema definitions
- **Isolation**: Each MCP server runs as an independent child process

## How Tool Calls Work

```
1. User sends query
2. Backend checks for tool-calling opportunities (non-streamed Ollama call)
3. If Ollama returns a tool_call:
   a. Backend routes to the correct MCP server via McpToolManager
   b. Server executes the tool and returns the result
   c. Result is fed back to Ollama
   d. Loop repeats (up to 30 rounds) until Ollama gives a final text response
4. Final response is streamed to the user
```

**Important**: Tool detection is skipped when images are present in the query, as vision models often struggle with simultaneous tool calling and image analysis.

## Active Servers

### Demo Calculator (`demo`)

A reference implementation for testing and learning.

| Tool | Parameters | Description |
|------|-----------|-------------|
| `add` | `a: float, b: float` | Adds two numbers |
| `divide` | `a: float, b: float` | Divides two numbers (50 decimal places) |

### Filesystem Tools (`filesystem`)

File system operations with path-traversal protection.

| Tool | Parameters | Description |
|------|-----------|-------------|
| `list_directory` | `path: str` | Lists files sorted by modification time |
| `read_file` | `path: str` | Reads UTF-8 text file content |
| `write_file` | `path: str, content: str` | Writes or overwrites a file |
| `create_folder` | `path: str, folder_name: str` | Creates a new directory |
| `move_file` | `source_path: str, destination_folder: str` | Moves a file |
| `rename_file` | `source_path: str, new_name: str` | Renames a file in place |

**Security**: All paths are validated against a `BASE_PATH` to prevent directory traversal attacks.

### Web Search (`websearch`)

Internet search and web page reading capabilities.

| Tool | Parameters | Description |
|------|-----------|-------------|
| `search_web_pages` | `query: str` | Searches the web via DuckDuckGo, returns URLs and snippets |
| `read_website` | `url: str` | Reads a web page and extracts clean markdown content |

**Features**:
- Uses DuckDuckGo for privacy-respecting search
- `read_website` uses crawl4ai with stealth mode (rotating User-Agents, noise reduction, randomized timing)
- Falls back to trafilatura for content extraction if crawl4ai fails

### Placeholder Servers (Not Yet Implemented)

These servers have skeleton files but are not yet functional:

- **Gmail** - Email reading/sending via Google OAuth 2.0
- **Calendar** - Google Calendar event management
- **Discord** - Message reading/sending via Bot Token
- **Canvas** - LMS assignment and grade retrieval

## Adding a New MCP Server

### Step 1: Create the Server

Create a new directory under `mcp_servers/servers/` with a `server.py` file:

```python
# mcp_servers/servers/my_tool/server.py
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("My Tool Name")

@mcp.tool()
def my_function(param1: str, param2: int = 10) -> str:
    """Clear description of what this tool does and when the LLM should use it.
    
    This docstring is critical -- it's the only way the LLM knows when
    and how to use your tool. Be specific about:
    - What the tool does
    - When to use it vs. other tools
    - What the parameters mean
    - What the return value contains
    """
    result = do_something(param1, param2)
    return f"Result: {result}"

@mcp.tool()
async def my_async_function(url: str) -> str:
    """Async tools are also supported for I/O-bound operations."""
    data = await fetch_data(url)
    return data

if __name__ == "__main__":
    mcp.run()  # Starts stdio transport
```

**Requirements:**
- Type hints are **mandatory** (used for JSON Schema generation)
- Docstrings become the tool description visible to the LLM
- The `if __name__ == "__main__"` block is required for subprocess execution

### Step 2: Register the Server

Add your server to the MCP initialization in `source/main.py`:

```python
async def _init_mcp_servers():
    await _mcp_manager.connect_server(
        "my_tool",                    # Server name (used in routing)
        sys.executable,               # Python interpreter
        [str(PROJECT_ROOT / "mcp_servers" / "servers" / "my_tool" / "server.py")]
    )
```

Also add it to `mcp_servers/config/servers.json`:

```json
{
    "my_tool": {
        "enabled": true,
        "module": "mcp_servers.servers.my_tool.server",
        "description": "Description of what this server provides"
    }
}
```

### Step 3: Test and Restart

Test the server standalone:

```bash
python -m mcp_servers.servers.my_tool.server
```

Then restart the app. Tools are auto-discovered and registered with Ollama.

## Best Practices

### Tool Descriptions

The LLM decides which tools to use based solely on the docstring. Write descriptions that are:

- **Specific**: "Searches the web using DuckDuckGo and returns the top 5 results with titles, URLs, and snippets"
- **Action-oriented**: Start with a verb ("Reads", "Creates", "Searches")
- **Contextual**: Explain when to use this tool vs. others
- **Parameter-aware**: Describe what each parameter expects

### Error Handling

Return errors as strings rather than raising exceptions:

```python
@mcp.tool()
def safe_tool(path: str) -> str:
    """Does something safely."""
    try:
        result = risky_operation(path)
        return f"Success: {result}"
    except FileNotFoundError:
        return f"Error: File not found at {path}"
    except Exception as e:
        return f"Error: {str(e)}"
```

### Descriptions File Pattern

For complex tools, keep docstrings in a separate `descriptions.py` file:

```python
# mcp_servers/servers/my_tool/descriptions.py
MY_FUNCTION_DESC = """
Detailed multi-line description that guides the LLM
on exactly how and when to use this tool.

Mandatory workflow:
1. Always call list_items first
2. Then call process_item with a valid ID
"""

# mcp_servers/servers/my_tool/server.py
from .descriptions import MY_FUNCTION_DESC

@mcp.tool(description=MY_FUNCTION_DESC)
def my_function(item_id: str) -> str:
    ...
```

## Debugging

### Check Server Registration

Look for `[MCP]` log entries on startup:

```
[MCP] Connecting to server: my_tool
[MCP] Server my_tool connected, discovered 2 tools
[MCP] Registered tool: my_function (server: my_tool)
```

### Test Tool Execution

Tool calls appear as cards in the UI:

```
+------------------------------------------+
| TOOL: my_function                        |
| Server: my_tool                          |
| Arguments: {"param1": "test"}            |
| Result: "Success: ..."                   |
+------------------------------------------+
```

### Common Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| Tool not discovered | Missing type hints | Add type annotations to all parameters |
| Tool never called | Poor docstring | Rewrite with clearer description |
| Server crash on startup | Missing dependency | Check `requirements.txt` and install deps |
| "Tool call timeout" | Long-running operation | Add async support or increase timeout |
| Tools not used with images | By design | Tool detection is skipped when images are in context |

## Configuration

Server configuration lives in `mcp_servers/config/servers.json`:

```json
{
    "demo": {
        "enabled": true,
        "module": "mcp_servers.servers.demo.server"
    },
    "filesystem": {
        "enabled": true,
        "module": "mcp_servers.servers.filesystem.server"
    },
    "websearch": {
        "enabled": true,
        "module": "mcp_servers.servers.websearch.server"
    }
}
```

Set `"enabled": false` to disable a server without removing its code.

## Architecture

```
source/mcp_integration/
  manager.py        # McpToolManager: launches servers, discovers tools,
                    #   converts schemas to Ollama format, routes calls
  handlers.py       # Tool call loop: detects tool requests, executes them,
                    #   feeds results back to Ollama (up to 30 rounds)

mcp_servers/
  client/
    ollama_bridge.py  # Standalone bridge (for testing outside the app)
  config/
    servers.json      # Server registration and configuration
  servers/
    demo/             # Reference calculator server
    filesystem/       # File system operations
    websearch/        # Web search + page reading
    gmail/            # Placeholder
    calendar/         # Placeholder
    discord/          # Placeholder
    canvas/           # Placeholder
```
