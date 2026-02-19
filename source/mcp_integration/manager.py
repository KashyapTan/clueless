"""
MCP Tool Manager.

Manages MCP server connections and tool routing for the main app.
"""

import os
import sys
from typing import List, Dict, Any

from ..config import PROJECT_ROOT
from .retriever import retriever


class McpToolManager:
    """
    Manages MCP server connections and tool routing.

    This is the in-app version of the bridge. It:
    1. Launches MCP servers as child processes (stdio transport)
    2. Discovers their tools and converts schemas to Ollama format
    3. Routes tool calls from Ollama to the correct MCP server
    4. Returns results back so Ollama can form a final answer

    HOW TO ADD A NEW TOOL SERVER:
    ─────────────────────────────
    1. Create your server in mcp_servers/servers/<name>/server.py
       (use @mcp.tool() decorators — see demo/server.py for example)

    2. In this file's init_mcp_servers() function, add:
       await mcp_manager.connect_server(
           "your_server_name",
           sys.executable,
           [str(PROJECT_ROOT / "mcp_servers" / "servers" / "your_name" / "server.py")]
       )

    3. That's it! The tools will automatically be:
       - Discovered and registered
       - Sent to Ollama with every chat request
       - Routed and executed when Ollama calls them
       - Displayed in the UI response
    """

    def __init__(self):
        self._tool_registry: Dict[str, Any] = {}  # tool_name -> {session, server_name}
        self._connections: Dict[
            str, Any
        ] = {}  # server_name -> {session, stdio_ctx, session_ctx}
        self._ollama_tools: List[Dict] = []  # Ollama-formatted tool definitions
        self._raw_tools: List[
            Dict
        ] = []  # Raw tool schemas (name, description, inputSchema)
        self._initialized = False

    async def connect_server(
        self, server_name: str, command: str, args: list, env: dict = None
    ):
        """Connect to an MCP server by launching it as a subprocess."""
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
        except ImportError as e:
            print(f"[MCP] WARNING: mcp import failed: {e}")
            print(f"[MCP] Run: pip install 'mcp[cli]'")
            print(
                f"[MCP] Skipping server '{server_name}'. Tools will not be available."
            )
            return

        try:
            # Ensure PROJECT_ROOT is in PYTHONPATH so child processes can
            # resolve absolute imports like "from mcp_servers.servers.xxx import ..."
            if env is None:
                env = {**os.environ}
            project_root_str = str(PROJECT_ROOT)
            existing_pypath = env.get("PYTHONPATH", "")
            if existing_pypath:
                if project_root_str not in existing_pypath.split(os.pathsep):
                    env["PYTHONPATH"] = project_root_str + os.pathsep + existing_pypath
            else:
                env["PYTHONPATH"] = project_root_str

            server_params = StdioServerParameters(command=command, args=args, env=env)

            # Launch the MCP server subprocess and connect
            stdio_ctx = stdio_client(server_params)
            read, write = await stdio_ctx.__aenter__()

            session_ctx = ClientSession(read, write)
            session = await session_ctx.__aenter__()
            await session.initialize()

            self._connections[server_name] = {
                "session": session,
                "stdio_ctx": stdio_ctx,
                "session_ctx": session_ctx,
            }

            # Discover tools
            tools_result = await session.list_tools()
            for tool in tools_result.tools:
                self._tool_registry[tool.name] = {
                    "session": session,
                    "server_name": server_name,
                }
                ollama_tool = {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description or "",
                        "parameters": tool.inputSchema
                        if tool.inputSchema
                        else {"type": "object", "properties": {}},
                    },
                }
                self._ollama_tools.append(ollama_tool)

                # Store raw schema for cross-provider conversion
                self._raw_tools.append(
                    {
                        "name": tool.name,
                        "description": tool.description or "",
                        "input_schema": tool.inputSchema
                        if tool.inputSchema
                        else {"type": "object", "properties": {}},
                    }
                )

                print(f"[MCP] Registered tool: {tool.name} (from {server_name})")

            print(
                f"[MCP] Connected to '{server_name}' — {len(tools_result.tools)} tool(s)"
            )
            # Re-embed tools for the retriever
            retriever.embed_tools(self._ollama_tools)
        except Exception as e:
            print(f"[MCP] ERROR connecting to '{server_name}': {e}")
            print(f"[MCP] The server will work without '{server_name}' tools.")

    async def call_tool(self, tool_name: str, arguments: dict) -> str:
        """Route a tool call to the correct MCP server."""
        if tool_name not in self._tool_registry:
            return f"Error: Unknown tool '{tool_name}'"

        entry = self._tool_registry[tool_name]
        session = entry["session"]

        import asyncio
        try:
            result = await asyncio.wait_for(
                session.call_tool(tool_name, arguments=arguments),
                timeout=180.0,  # 3 min safety ceiling
            )
        except asyncio.TimeoutError:
            server = entry.get('server_name', 'unknown')
            return f"Error: Tool '{tool_name}' (server '{server}') timed out after 180s"

        output_parts = []
        for block in result.content:
            if hasattr(block, "text"):
                output_parts.append(block.text)
            else:
                output_parts.append(str(block))

        return "\n".join(output_parts) if output_parts else "Tool returned no output."

    def get_ollama_tools(self) -> List[Dict] | None:
        """Return tool definitions in Ollama format, or None if no tools."""
        return self._ollama_tools if self._ollama_tools else None

    def get_tool_server_name(self, tool_name: str) -> str:
        """Get the server name that owns a tool."""
        entry = self._tool_registry.get(tool_name)
        return entry["server_name"] if entry else "unknown"

    def has_tools(self) -> bool:
        """Check if any tools are registered."""
        return len(self._ollama_tools) > 0

    def get_anthropic_tools(self) -> List[Dict] | None:
        """Return tool definitions in Anthropic format, or None if no tools."""
        if not self._raw_tools:
            return None
        return [
            {
                "name": t["name"],
                "description": t["description"],
                "input_schema": t["input_schema"],
            }
            for t in self._raw_tools
        ]

    def get_openai_tools(self) -> List[Dict] | None:
        """Return tool definitions in OpenAI format, or None if no tools."""
        if not self._raw_tools:
            return None
        tools = []
        for t in self._raw_tools:
            # OpenAI wants parameters without the extra JSON Schema keys
            # that some MCP servers include
            params = dict(t["input_schema"])
            params.pop("additionalProperties", None)
            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": t["name"],
                        "description": t["description"],
                        "parameters": params,
                    },
                }
            )
        return tools

    def get_gemini_tools(self) -> List[Any] | None:
        """Return tool definitions in Gemini format, or None if no tools."""
        if not self._raw_tools:
            return None
        try:
            from google.genai import types

            declarations = []
            for t in self._raw_tools:
                # Clean up the schema for Gemini
                params = dict(t["input_schema"])
                params.pop("additionalProperties", None)

                declarations.append(
                    types.FunctionDeclaration(
                        name=t["name"],
                        description=t["description"],
                        parameters=params,
                    )
                )
            return [types.Tool(function_declarations=declarations)]
        except ImportError:
            print(
                "[MCP] google-genai not installed, cannot convert tools to Gemini format"
            )
            return None

    async def disconnect_server(self, server_name: str):
        """Disconnect a single MCP server by name."""
        conn = self._connections.get(server_name)
        if not conn:
            return

        try:
            await conn["session_ctx"].__aexit__(None, None, None)
            await conn["stdio_ctx"].__aexit__(None, None, None)
            print(f"[MCP] Disconnected from '{server_name}'")
        except Exception as e:
            print(f"[MCP] Error disconnecting from '{server_name}': {e}")

        # Remove from connections
        self._connections.pop(server_name, None)

        # Remove tools belonging to this server
        tools_to_remove = [
            name
            for name, entry in self._tool_registry.items()
            if entry["server_name"] == server_name
        ]
        for tool_name in tools_to_remove:
            self._tool_registry.pop(tool_name, None)

        # Rebuild tool lists without this server's tools
        self._ollama_tools = [
            t
            for t in self._ollama_tools
            if t["function"]["name"] not in tools_to_remove
        ]
        self._raw_tools = [
            t for t in self._raw_tools if t["name"] not in tools_to_remove
        ]

        print(f"[MCP] Removed {len(tools_to_remove)} tool(s) from '{server_name}'")
        # Re-embed tools for the retriever
        retriever.embed_tools(self._ollama_tools)

    def is_server_connected(self, server_name: str) -> bool:
        """Check if a specific MCP server is currently connected."""
        return server_name in self._connections

    async def connect_google_servers(self):
        """Connect Gmail and Calendar MCP servers with Google OAuth env vars."""
        from ..config import GOOGLE_TOKEN_FILE

        import os

        if not os.path.exists(GOOGLE_TOKEN_FILE):
            print("[MCP] Google token not found, skipping Google servers")
            return

        # Build env dict with token path for the child processes
        env = {
            **os.environ,
            "GOOGLE_TOKEN_FILE": str(GOOGLE_TOKEN_FILE),
        }

        # Connect Gmail server
        if not self.is_server_connected("gmail"):
            await self.connect_server(
                "gmail",
                sys.executable,
                [str(PROJECT_ROOT / "mcp_servers" / "servers" / "gmail" / "server.py")],
                env=env,
            )

        # Connect Calendar server
        if not self.is_server_connected("calendar"):
            await self.connect_server(
                "calendar",
                sys.executable,
                [
                    str(
                        PROJECT_ROOT
                        / "mcp_servers"
                        / "servers"
                        / "calendar"
                        / "server.py"
                    )
                ],
                env=env,
            )

        print(
            f"[MCP] Google servers connected — {len(self._ollama_tools)} total tool(s) available"
        )

    async def disconnect_google_servers(self):
        """Disconnect Gmail and Calendar MCP servers."""
        if self.is_server_connected("gmail"):
            await self.disconnect_server("gmail")
        if self.is_server_connected("calendar"):
            await self.disconnect_server("calendar")
        print("[MCP] Google servers disconnected")

    async def cleanup(self):
        """Disconnect from all MCP servers."""
        for name, conn in list(self._connections.items()):
            try:
                await conn["session_ctx"].__aexit__(None, None, None)
                await conn["stdio_ctx"].__aexit__(None, None, None)
                print(f"[MCP] Disconnected from '{name}'")
            except Exception as e:
                print(f"[MCP] Error disconnecting from '{name}': {e}")
        self._connections.clear()
        self._tool_registry.clear()
        self._ollama_tools.clear()
        self._raw_tools.clear()


# Global MCP tool manager singleton
mcp_manager = McpToolManager()


async def init_mcp_servers():
    """
    Connect to all enabled MCP servers.

    ╔══════════════════════════════════════════════════════════════════╗
    ║  HOW TO ADD YOUR OWN MCP TOOL SERVER:                           ║
    ║                                                                  ║
    ║  1. Create mcp_servers/servers/<name>/server.py                  ║
    ║  2. Add @mcp.tool() functions in it                             ║
    ║  3. Add a connect_server() call below                           ║
    ║  4. Restart the app — your tools are now available!              ║
    ╚══════════════════════════════════════════════════════════════════╝
    """
    # ── Demo server (add two numbers) ──────────────────────────────
    # await mcp_manager.connect_server(
    #     "demo",
    #     sys.executable,
    #     [str(PROJECT_ROOT / "mcp_servers" / "servers" / "demo" / "server.py")],
    # )

    # ── Filesystem server ──────────────────────────────────────────
    await mcp_manager.connect_server(
        "filesystem",
        sys.executable,
        [str(PROJECT_ROOT / "mcp_servers" / "servers" / "filesystem" / "server.py")],
    )

    await mcp_manager.connect_server(
        "websearch",
        sys.executable,
        [str(PROJECT_ROOT / "mcp_servers" / "servers" / "websearch" / "server.py")],
    )

    # ── Terminal server ────────────────────────────────────────────
    await mcp_manager.connect_server(
        "terminal",
        sys.executable,
        [str(PROJECT_ROOT / "mcp_servers" / "servers" / "terminal" / "server.py")],
    )

    # ── Add more servers here as you implement them ────────────────
    # Example:
    # await mcp_manager.connect_server(
    #     "my_server",
    #     sys.executable,
    #     [str(PROJECT_ROOT / "mcp_servers" / "servers" / "my_server" / "server.py")],
    # )

    mcp_manager._initialized = True
    print(f"[MCP] Ready — {len(mcp_manager._ollama_tools)} total tool(s) available")
