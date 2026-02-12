"""
Filesystem MCP Server — PLACEHOLDER
=====================================
TODO: Implement these tools yourself!

Suggested tools:
  - read_file(path) -> str           : Read a file's contents
  - write_file(path, content) -> str : Write content to a file
  - move_file(src, dest) -> str      : Move/rename a file
  - list_directory(path) -> list     : List files in a directory
  - delete_file(path) -> str         : Delete a file

Tips:
  - Use Python's built-in `os`, `shutil`, and `pathlib` modules.
  - Add safety checks! Don't let the LLM delete system files.
  - Consider a ALLOWED_DIRECTORIES config to restrict access.

Example:
    @mcp.tool()
    def read_file(path: str) -> str:
        '''Read the contents of a file.'''
        with open(path, 'r') as f:
            return f.read()
"""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Filesystem Tools")

# ── YOUR TOOLS GO HERE ─────────────────────────────────────────────────
# @mcp.tool()
# def read_file(path: str) -> str:
#     ...


if __name__ == "__main__":
    mcp.run()
