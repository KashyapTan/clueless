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
import os
mcp = FastMCP("Filesystem Tools")

# ── YOUR TOOLS GO HERE ─────────────────────────────────────────────────
# @mcp.tool()
# def read_file(path: str) -> str:
#     ...

USERNAME = 'Kashyap Tanuku'
BASE_PATH = f"C:/Users/{USERNAME}"

list_directory_description = f"""
List files/folders in a directory.
CURRENT CONTEXT:
- Username: {USERNAME}
- Base Path: {BASE_PATH}
"""

# 3. Pass the description into the decorator
# This keeps the decorator on top, but feeds it the dynamic text!
@mcp.tool(description=list_directory_description)
def list_directory(path: str) -> list:
    """Lists files for the current user."""
    clean_path = os.path.expanduser(path)

    try:
        return os.listdir(clean_path)
    except FileNotFoundError:
        return [f"Error: Could not find path '{clean_path}'. Check if it exists."]

if __name__ == "__main__":
    mcp.run()
