# MCP Servers for Clueless

This directory contains your custom **Model Context Protocol (MCP)** servers — modular tool packs that give your LLM (Ollama, Claude, GPT, Gemini) the ability to interact with the real world (files, email, calendar, Discord, etc.).

---

## 📁 Folder Structure

```
mcp_servers/
├── __init__.py
├── requirements.txt            # Python dependencies for MCP
├── test_demo.py                # Test script — run this first!
│
├── client/                     # The "bridge" that connects MCP ↔ Ollama
│   ├── __init__.py
│   └── ollama_bridge.py        # Core bridge: discovers tools, routes calls
│
├── config/
│   └── servers.json            # Configuration: which servers to enable, credentials
│
└── servers/                    # Each subfolder = one independent MCP server
    ├── __init__.py
    ├── demo/                   # ✅ IMPLEMENTED — add two numbers
    │   ├── __init__.py
    │   └── server.py           # The actual MCP server code
    ├── filesystem/             # 📝 PLACEHOLDER — file read/write/move tools
    │   ├── __init__.py
    │   └── server.py
    ├── gmail/                  # 📝 PLACEHOLDER — Gmail tools
    │   ├── __init__.py
    │   └── server.py
    ├── calendar/               # 📝 PLACEHOLDER — Google Calendar tools
    │   ├── __init__.py
    │   └── server.py
    ├── discord/                # 📝 PLACEHOLDER — Discord tools
    │   ├── __init__.py
    │   └── server.py
    ├── canvas/                 # 📝 PLACEHOLDER — Canvas LMS tools
    │   ├── __init__.py
    │   └── server.py
    └── websearch/              # 📝 PLACEHOLDER — Web search/scrape tools
        ├── __init__.py
        └── server.py
```

### What each part does:

| Folder | Purpose |
|---|---|
| `servers/<name>/server.py` | An independent MCP server. Each one defines tools using `@mcp.tool()`. Runs as its own process. |
| `client/ollama_bridge.py` | The bridge that launches MCP servers, discovers their tools, converts them to Ollama format, and routes tool calls. |
| `config/servers.json` | Declares which servers exist, whether they're enabled, and any credentials they need. |
| `test_demo.py` | A runnable test that connects the demo server to Ollama and asks "What is 42 + 58?" |

---

## 🚀 Quick Start

### 1. Install dependencies

```bash
pip install "mcp[cli]" ollama
```

### 2. Make sure Ollama is running with a tool-capable model

```bash
# Pull a model that supports tool calling
ollama pull qwen3:8b    # or llama3.1, mistral, etc.

# IMPORTANT: Your current model (qwen3-vl:8b-instruct) is a VISION model.
# Vision models typically do NOT support tool/function calling.
# You need a regular text model for tools.
```

### 3. Run the demo test

```bash
cd c:\Users\Kashyap Tanuku\Desktop\Github\clueless
python -m mcp_servers.test_demo
```

You should see Ollama call the `add` tool and return the result.

---

## 🧠 How MCP Works — The Complete Guide

### What is MCP?

**Model Context Protocol** is a standardized way for LLMs to use external tools. Think of it as a **USB port for AI** — any tool that speaks MCP can plug into any LLM that understands MCP.

```
┌─────────────┐     MCP Protocol     ┌──────────────────┐
│  LLM Client │ ◄──────────────────► │   MCP Server     │
│  (Ollama,   │   (JSON-RPC over     │  (your tools)    │
│   Claude,   │    stdin/stdout)     │                  │
│   GPT...)   │                      │  @mcp.tool()     │
└─────────────┘                      │  def add(a, b)   │
                                     │  def send_email()│
                                     └──────────────────┘
```

### The 3 MCP Primitives

| Primitive | Who Controls It | What It Does | Example |
|---|---|---|---|
| **Tools** | The LLM decides when to call them | Functions the LLM can execute | `add(5, 3)`, `send_email(...)` |
| **Resources** | The app/client controls them | Data the LLM can read | File contents, DB records |
| **Prompts** | The user triggers them | Reusable interaction templates | "Review this code", "Summarize" |

**For your use case, you mainly need Tools.**

### How the Communication Works

MCP uses **JSON-RPC 2.0** over a transport layer. The most common transport is **stdio** (standard input/output):

```
┌──────────────────┐     stdin      ┌──────────────────┐
│  Bridge/Client   │ ──────────────>│   MCP Server     │
│  (your app)      │                │  (child process)  │
│                  │<───────────────│                   │
│                  │     stdout     │                   │
└──────────────────┘                └──────────────────┘
```

1. The **client** (bridge) spawns the server as a **child process**
2. Client sends JSON-RPC requests via the server's **stdin**
3. Server sends JSON-RPC responses via its **stdout**
4. This is all handled automatically by the MCP SDK

### The Tool-Calling Flow (Step by Step)

```
You: "What is 42 + 58?"

Step 1: Bridge sends to Ollama:
{
  messages: [{ role: "user", content: "What is 42 + 58?" }],
  tools: [{
    type: "function",
    function: { name: "add", description: "Add two numbers", parameters: {...} }
  }]
}

Step 2: Ollama responds with a tool call (instead of text):
{
  message: {
    tool_calls: [{ function: { name: "add", arguments: { a: 42, b: 58 } } }]
  }
}

Step 3: Bridge routes "add(42, 58)" to the demo MCP server
        Server computes 42 + 58 = 100 and returns it

Step 4: Bridge sends the result back to Ollama:
{
  messages: [
    { role: "user", content: "What is 42 + 58?" },
    { role: "assistant", tool_calls: [...] },
    { role: "tool", content: "100" }            ← tool result
  ]
}

Step 5: Ollama now responds with natural language:
"42 + 58 = 100"
```

---

## 🔧 How to Add Your Own Tools

### Step 1: Pick a server folder (or create a new one)

Each server folder has a `server.py` file. Open it and add tools.

### Step 2: Write a tool function

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("My Server Name")

@mcp.tool()
def my_tool(param1: str, param2: int = 10) -> str:
    """Description of what this tool does (the LLM reads this!)."""
    # Your logic here
    return f"Result: {param1} x {param2}"

if __name__ == "__main__":
    mcp.run()
```

**Key rules:**
- **Type hints are REQUIRED** (`param: str`, `-> str`). MCP uses them to generate the JSON schema that tells the LLM what parameters the tool accepts.
- **The docstring IS the tool description.** Write it clearly — the LLM reads it to decide when/how to use the tool.
- **Return a string** (or a type the LLM can understand).

### Step 3: Connect it to the bridge

In your code (or in `test_demo.py`), add:

```python
await bridge.connect_server(
    server_name="my_server",
    command=sys.executable,
    args=["mcp_servers/servers/my_server/server.py"],
)
```

### Step 4: Enable it in `config/servers.json`

```json
{
    "my_server": {
        "enabled": true,
        "module": "mcp_servers.servers.my_server.server"
    }
}
```

---

## 🔑 Authentication — How Users Connect Their Accounts

Different services use different auth methods. Here's a breakdown:

### Google (Gmail, Calendar, Drive)
**Method: OAuth 2.0** (the most complex but most secure)

```
First time setup:
1. Create a Google Cloud project at console.cloud.google.com
2. Enable the API (Gmail API, Calendar API, etc.)
3. Create OAuth 2.0 credentials (Desktop app type)
4. Download credentials.json
5. First run → opens a browser → user logs in & grants permission
6. Your app receives tokens (access_token + refresh_token)
7. Store tokens in token.json for future use
8. Refresh tokens automatically when they expire

Subsequent runs:
- Load token.json → use refresh_token to get new access_token → make API calls
```

**Packages:** `pip install google-auth google-auth-oauthlib google-api-python-client`

### Discord
**Method: Bot Token** (simple!)

```
1. Go to discord.com/developers/applications
2. Create app → Add Bot
3. Copy the bot token
4. Store it in config/servers.json or an environment variable
5. Use the token in HTTP headers: "Authorization: Bot <token>"
```

**For personal use**, a bot token is perfect. For a public app, you'd use OAuth 2.0.

### Canvas LMS
**Method: API Access Token** (simplest!)

```
1. Log into Canvas → Account → Settings
2. "New Access Token" → copy it
3. Use in HTTP headers: "Authorization: Bearer <token>"
```

### Web Search
- **DuckDuckGo**: No API key needed! Use `duckduckgo-search` package.
- **Google Custom Search**: Free API key, 100 queries/day
- **Brave Search**: Free tier, 2000 queries/month

### Where to Store Credentials

**Option A: Environment variables** (recommended for secrets)
```bash
export DISCORD_BOT_TOKEN="abc123..."
```

**Option B: config/servers.json** (convenient for development)
```json
{
    "discord": {
        "env": { "DISCORD_BOT_TOKEN": "abc123..." }
    }
}
```

**Option C: Separate credential files** (for OAuth tokens)
```
mcp_servers/config/google_credentials.json
mcp_servers/config/google_token.json
```

⚠️ **IMPORTANT:** Add credential files to `.gitignore` so they don't get committed!

---

## 🔮 Future: Connecting to Claude, GPT, Gemini

The beauty of MCP is that your servers are **transport-agnostic**. The same server that works with Ollama can work with:

- **Claude Desktop**: Native MCP support. Just point it at your server.
- **Claude API**: Use the MCP client SDK to bridge (similar to our Ollama bridge).
- **OpenAI/GPT**: Convert MCP tools to OpenAI function-calling format (very similar to what the bridge already does).
- **Gemini**: Convert to Gemini's function-calling format.

The `ollama_bridge.py` pattern can be adapted for any LLM that supports function/tool calling. The MCP server side stays exactly the same.

---

## 🧪 Testing Individual Servers

You can test any server independently using the MCP Inspector:

```bash
# Install the inspector
npx -y @modelcontextprotocol/inspector

# Run your server
python mcp_servers/servers/demo/server.py

# Or use the MCP dev mode
pip install "mcp[cli]"
mcp dev mcp_servers/servers/demo/server.py
```

The Inspector gives you a web UI to call tools manually and see the JSON-RPC messages.
