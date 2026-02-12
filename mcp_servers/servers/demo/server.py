"""
Demo MCP Server — "Add Two Numbers"
====================================
This is the simplest possible MCP server. It exposes a single tool called
`add` that takes two numbers and returns their sum.

HOW IT WORKS:
1. We import FastMCP from the official MCP Python SDK.
2. We create a server instance with a human-readable name.
3. We decorate a plain Python function with @mcp.tool() to register it
   as a tool that LLMs can call.
4. When this script is run, it starts the server using the "stdio" transport,
   meaning it communicates via standard input/output (stdin/stdout).
   This is how MCP clients (like our Ollama bridge) talk to it.

RUN DIRECTLY (for testing with MCP Inspector):
    python -m mcp_servers.servers.demo.server

Or from the mcp_servers directory:
    python servers/demo/server.py
"""

from mcp.server.fastmcp import FastMCP

# ── Create the MCP server ──────────────────────────────────────────────
# The name is what clients see when they connect.
mcp = FastMCP("Demo Calculator")


# ── Register tools ─────────────────────────────────────────────────────
@mcp.tool()
def add(a: float, b: float) -> float:
    """Add two numbers together and return the result.
    
    Args:
        a: The first number
        b: The second number
    
    Returns:
        The sum of a and b
    """
    return a + b


# ── Entry point ────────────────────────────────────────────────────────
# mcp.run() starts the server. By default it uses "stdio" transport,
# which means it reads JSON-RPC messages from stdin and writes responses
# to stdout. This is the standard way MCP clients launch and talk to
# MCP servers.
if __name__ == "__main__":
    mcp.run()
