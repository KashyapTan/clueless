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
from descriptions import LIST_DIRECTORY_DESCRIPTION, READ_FILE_DESCRIPTION

mcp = FastMCP("Filesystem Tools")

@mcp.tool(description=LIST_DIRECTORY_DESCRIPTION)
def list_directory(path: str) -> list[str]:
    """Lists files for the current user, sorted by most recent modification."""
    # Expand ~ to the full user path
    clean_path = os.path.expanduser(path)

    try:
        # Get all entries in the directory
        entries = os.listdir(clean_path)
        
        # Create full paths so we can check their mtime
        full_paths = [os.path.join(clean_path, entry) for entry in entries]
        
        # Sort by modification time (latest first)
        full_paths.sort(key=os.path.getmtime, reverse=True)
        
        # Convert back to just filenames to match original return signature
        return [os.path.basename(p) for p in full_paths]
    
    except FileNotFoundError:
        return [f"Error: The path '{clean_path}' does not exist."]
    
    except PermissionError:
        return [f"Error: Permission denied. Cannot access '{clean_path}'."]
    
    except NotADirectoryError:
        return [f"Error: '{clean_path}' is a file, not a directory."]
        
    except Exception as e:
        return [f"Error: An unexpected error occurred: {str(e)}"]


@mcp.tool(description=READ_FILE_DESCRIPTION)
def read_file(path: str) -> str:
    """Reads a file's contents."""
    clean_path = os.path.expanduser(path)

    try:
        # 'errors="replace"' ensures the server won't crash on non-text characters
        with open(clean_path, 'r', encoding='utf-8', errors='replace') as f:
            return f.read()
            
    except FileNotFoundError:
        return f"Error: The file '{clean_path}' was not found."
    
    except PermissionError:
        return f"Error: Permission denied. Cannot read '{clean_path}'."
    
    except IsADirectoryError:
        return f"Error: '{clean_path}' is a directory, not a file. Use list_directory instead."
        
    except Exception as e:
        return f"Error: An unexpected error occurred: {str(e)}"

if __name__ == "__main__":
    mcp.run()