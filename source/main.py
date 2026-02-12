from ollama import chat
import sys
import os
import socket
import signal
import atexit
from pathlib import Path

# Add current directory to path for imports when run as script
if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)

# Now import ss module
try:
    from .ss import take_region_screenshot, start_screenshot_service, take_fullscreen_screenshot, create_thumbnail
    from .database import DatabaseManager
except ImportError:
    # Fallback for when run as script
    from ss import take_region_screenshot, start_screenshot_service, take_fullscreen_screenshot, create_thumbnail
    from database import DatabaseManager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import threading
import time
import os
import glob
import shutil
import asyncio
import uvicorn
import json
from typing import List, Dict, Any
from concurrent.futures import Future

# FastAPI WebSocket setup
app = FastAPI()

# Database manager for chat history persistence
db = DatabaseManager()

# Persistent screenshot folder (inside user_data so images survive across sessions)
SCREENSHOT_FOLDER = os.path.join('user_data', 'screenshots')
os.makedirs(SCREENSHOT_FOLDER, exist_ok=True)

# Global variables for cleanup
_screenshot_service = None
_server_thread = None
_service_thread = None

#############################################
# MCP (Model Context Protocol) Integration  #
#############################################

class McpToolManager:
    """
    Manages MCP server connections and tool routing for the main app.
    
    This is the in-app version of the bridge. It:
    1. Launches MCP servers as child processes (stdio transport)
    2. Discovers their tools and converts schemas to Ollama format
    3. Routes tool calls from Ollama to the correct MCP server
    4. Returns results back so Ollama can form a final answer
    
    HOW TO ADD A NEW TOOL SERVER:
    ─────────────────────────────
    1. Create your server in mcp_servers/servers/<name>/server.py
       (use @mcp.tool() decorators — see demo/server.py for example)
    
    2. In this file's _init_mcp_servers() function, add:
       await _mcp_manager.connect_server(
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
        self._tool_registry: Dict[str, Any] = {}   # tool_name -> {session, server_name}
        self._connections: Dict[str, Any] = {}      # server_name -> {session, stdio_ctx, session_ctx}
        self._ollama_tools: List[Dict] = []          # Ollama-formatted tool definitions
        self._initialized = False
    
    async def connect_server(self, server_name: str, command: str, args: list, env: dict = None):
        """Connect to an MCP server by launching it as a subprocess."""
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
        except ImportError:
            print(f"[MCP] WARNING: mcp package not installed. Run: pip install 'mcp[cli]'")
            print(f"[MCP] Skipping server '{server_name}'. Tools will not be available.")
            return
        
        try:
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
                        "parameters": tool.inputSchema if tool.inputSchema else {"type": "object", "properties": {}},
                    },
                }
                self._ollama_tools.append(ollama_tool)
                print(f"[MCP] Registered tool: {tool.name} (from {server_name})")
            
            print(f"[MCP] Connected to '{server_name}' — {len(tools_result.tools)} tool(s)")
        except Exception as e:
            print(f"[MCP] ERROR connecting to '{server_name}': {e}")
            print(f"[MCP] The server will work without '{server_name}' tools.")
    
    async def call_tool(self, tool_name: str, arguments: dict) -> str:
        """Route a tool call to the correct MCP server."""
        if tool_name not in self._tool_registry:
            return f"Error: Unknown tool '{tool_name}'"
        
        entry = self._tool_registry[tool_name]
        session = entry["session"]
        
        result = await session.call_tool(tool_name, arguments=arguments)
        
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
        return len(self._ollama_tools) > 0
    
    async def cleanup(self):
        """Disconnect from all MCP servers."""
        for name, conn in self._connections.items():
            try:
                await conn["session_ctx"].__aexit__(None, None, None)
                await conn["stdio_ctx"].__aexit__(None, None, None)
                print(f"[MCP] Disconnected from '{name}'")
            except Exception as e:
                print(f"[MCP] Error disconnecting from '{name}': {e}")
        self._connections.clear()
        self._tool_registry.clear()
        self._ollama_tools.clear()

# Global MCP tool manager
_mcp_manager = McpToolManager()

# Project root (for resolving MCP server paths)
PROJECT_ROOT = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def _init_mcp_servers():
    """
    Connect to all enabled MCP servers.
    
    ╔══════════════════════════════════════════════════════════════════╗
    ║  HOW TO ADD YOUR OWN MCP TOOL SERVER:                          ║
    ║                                                                 ║
    ║  1. Create mcp_servers/servers/<name>/server.py                 ║
    ║  2. Add @mcp.tool() functions in it                            ║
    ║  3. Add a connect_server() call below                          ║
    ║  4. Restart the app — your tools are now available!             ║
    ╚══════════════════════════════════════════════════════════════════╝
    """
    global _mcp_manager
    
    # ── Demo server (add two numbers) ──────────────────────────────
    await _mcp_manager.connect_server(
        "demo",
        sys.executable,
        [str(PROJECT_ROOT / "mcp_servers" / "servers" / "demo" / "server.py")]
    )
    
    # ── Add more servers here as you implement them ────────────────
    # Example:
    # await _mcp_manager.connect_server(
    #     "filesystem",
    #     sys.executable,
    #     [str(PROJECT_ROOT / "mcp_servers" / "servers" / "filesystem" / "server.py")]
    # )
    #
    # await _mcp_manager.connect_server(
    #     "gmail",
    #     sys.executable,
    #     [str(PROJECT_ROOT / "mcp_servers" / "servers" / "gmail" / "server.py")],
    #     env={"GOOGLE_CREDENTIALS_FILE": "path/to/creds.json"}
    # )
    
    _mcp_manager._initialized = True
    print(f"[MCP] Ready — {len(_mcp_manager._ollama_tools)} total tool(s) available")

def cleanup_resources():
    """Clean up all resources when shutting down."""
    global _screenshot_service, _server_thread, _service_thread
    print("Cleaning up resources...")
    
    # Clean up MCP servers
    try:
        loop = _server_loop_holder.get("loop")
        if loop and loop.is_running():
            import concurrent.futures
            fut = concurrent.futures.Future()
            async def _do_cleanup():
                try:
                    await _mcp_manager.cleanup()
                    fut.set_result(True)
                except Exception as e:
                    fut.set_result(False)
                    print(f"MCP cleanup error: {e}")
            loop.call_soon_threadsafe(asyncio.ensure_future, _do_cleanup())
            try:
                fut.result(timeout=5)
            except Exception:
                pass
        print("MCP servers cleaned up")
    except Exception as e:
        print(f"Error cleaning up MCP: {e}")
    
    # Stop screenshot service
    if _screenshot_service:
        try:
            _screenshot_service.stop_listener()
            print("Screenshot service stopped")
        except Exception as e:
            print(f"Error stopping screenshot service: {e}")
    
    # Clean up temporary screenshot folder (not the persistent user_data/screenshots)
    try:
        if os.path.exists("screenshots") and os.path.abspath("screenshots") != os.path.abspath(SCREENSHOT_FOLDER):
            clear_screenshots_folder("screenshots")
            print("Temp screenshots folder cleaned")
    except Exception as e:
        print(f"Error cleaning screenshots folder: {e}")
    
    print("Cleanup completed")

def signal_handler(signum, frame):
    """Handle shutdown signals."""
    print(f"Received signal {signum}, shutting down...")
    cleanup_resources()
    sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Register cleanup function to run at exit
atexit.register(cleanup_resources)

# Holder for the running uvicorn event loop so worker threads can schedule
# coroutine work (websocket broadcasts) onto the SAME loop instead of creating
# their own loops. Creating separate loops then touching loop-bound objects
# (WebSocket transports) causes assertion errors on Windows' Proactor.
_server_loop_holder: Dict[str, Any] = {}

def find_available_port(start_port: int = 8000, max_attempts: int = 10) -> int:
    """Find an available port starting from start_port."""
    for port in range(start_port, start_port + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('', port))
                return port
        except OSError:
            continue
    raise RuntimeError(f"Could not find an available port in range {start_port}-{start_port + max_attempts - 1}")

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                disconnected.append(connection)

        # Remove disconnected clients
        for conn in disconnected:
            self.disconnect(conn)

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Bidirectional websocket.

    Client -> Server messages (JSON):
      {"type": "submit_query", "content": "<question>", "capture_mode": "fullscreen"|"precision"|"none"}
      {"type": "clear_context"}  - Clear screenshots and chat history
      {"type": "remove_screenshot", "id": "<screenshot_id>"}  - Remove specific screenshot
      {"type": "set_capture_mode", "mode": "fullscreen"|"precision"|"none"}  - Set capture mode

    Server -> Client broadcast messages (JSON):
      ready                       : Server is ready, UI can accept input immediately
      screenshot_start            : Screenshot capture starting, UI should hide
      screenshot_ready            : Screenshot captured, attached to context (legacy)
      screenshot_added            : Screenshot added to context with preview data
      screenshot_removed          : Screenshot removed from context
      screenshots_cleared         : All screenshots cleared
      query                       : Echo of submitted query
      response_chunk              : Streaming model token/content fragment
      tool_call                   : MCP tool call event (calling / complete)
      response_complete           : Model finished
      error                       : Error message
    """
    await manager.connect(websocket)
    
    # Immediately notify client that server is ready for queries (no screenshot required)
    await websocket.send_text(json.dumps({"type": "ready", "content": "Server ready. You can start chatting or take a screenshot (Alt+.)"}))
    
    # Send any existing screenshots to the newly connected client
    for ss in _screenshot_list:
        await websocket.send_text(json.dumps({
            "type": "screenshot_added",
            "content": {
                "id": ss["id"],
                "name": ss["name"],
                "thumbnail": ss["thumbnail"]
            }
        }))
    
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except Exception:
                continue  # Ignore malformed client messages
            msg_type = data.get("type")
            if msg_type == "submit_query":
                query_text = data.get("content", "").strip()
                capture_mode = data.get("capture_mode", "none")  # fullscreen, precision, or none
                if not query_text:
                    await websocket.send_text(json.dumps({"type": "error", "content": "Empty query"}))
                    continue
                await handle_submit_query(query_text, capture_mode)
            elif msg_type == "clear_context":
                # Clear screenshots and chat history for fresh start
                await handle_clear_context()
            elif msg_type == "remove_screenshot":
                # Remove a specific screenshot
                screenshot_id = data.get("id")
                if screenshot_id:
                    await handle_remove_screenshot(screenshot_id)
            elif msg_type == "set_capture_mode":
                # Update the capture mode for hotkey behavior
                mode = data.get("mode", "fullscreen")
                await handle_set_capture_mode(mode)
            elif msg_type == "get_conversations":
                # Fetch conversation list for chat history page
                limit = data.get("limit", 50)
                offset = data.get("offset", 0)
                conversations = db.get_recent_conversations(limit=limit, offset=offset)
                await websocket.send_text(json.dumps({
                    "type": "conversations_list",
                    "content": json.dumps(conversations)
                }))
            elif msg_type == "load_conversation":
                # Load a specific conversation's messages
                conv_id = data.get("conversation_id")
                if conv_id:
                    messages = db.get_full_conversation(conv_id)
                    await websocket.send_text(json.dumps({
                        "type": "conversation_loaded",
                        "content": json.dumps({
                            "conversation_id": conv_id,
                            "messages": messages
                        })
                    }))
            elif msg_type == "delete_conversation":
                # Delete a conversation from the database
                conv_id = data.get("conversation_id")
                if conv_id:
                    db.delete_conversation(conv_id)
                    await websocket.send_text(json.dumps({
                        "type": "conversation_deleted",
                        "content": json.dumps({"conversation_id": conv_id})
                    }))
            elif msg_type == "search_conversations":
                # Search conversations by text
                search_term = data.get("query", "")
                if search_term:
                    results = db.search_conversations(search_term)
                    await websocket.send_text(json.dumps({
                        "type": "conversations_list",
                        "content": json.dumps(results)
                    }))
                else:
                    # If empty search, return all recent conversations
                    conversations = db.get_recent_conversations(limit=50)
                    await websocket.send_text(json.dumps({
                        "type": "conversations_list",
                        "content": json.dumps(conversations)
                    }))
            elif msg_type == "resume_conversation":
                # Resume a previous conversation (load into active chat)
                conv_id = data.get("conversation_id")
                if conv_id:
                    await handle_resume_conversation(conv_id)
            # else: silently ignore unknown types (could extend later)
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# Function to broadcast messages
async def broadcast_message(message_type: str, content: str):
    message = json.dumps({"type": message_type, "content": content})
    await manager.broadcast(message)

def clear_screenshots_folder(folder_path="screenshots"):
    """Clear all files in the screenshots folder"""
    try:
        if os.path.exists(folder_path):
            for file_path in glob.glob(os.path.join(folder_path, "*")):
                os.remove(file_path)
            print(f"Cleared screenshots folder: {folder_path}")
    except Exception as e:
        print(f"Error clearing folder: {e}")

async def _handle_mcp_tool_calls(messages: List[Dict[str, Any]], image_paths: List[str]) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Do a non-streamed Ollama call to check for tool calls.
    
    If Ollama wants to call MCP tools, this function:
    1. Makes the tool calls via MCP servers
    2. Broadcasts tool_call events to the UI so users see what happened
    3. Appends tool call + result messages to the conversation
    4. Repeats until Ollama stops requesting tools
    
    Returns:
        (updated_messages, tool_calls_made)
        - updated_messages: the messages list with tool exchanges appended
        - tool_calls_made: list of {name, args, result, server} for UI display
    """
    tool_calls_made = []
    
    if not _mcp_manager.has_tools():
        return messages, tool_calls_made
    
    # Only do tool detection for text-only queries (no images)
    # Vision models + tool calling don't always mix well
    has_images = any(msg.get('images') for msg in messages) or bool(image_paths)
    if has_images:
        return messages, tool_calls_made
    
    # Non-streamed call to detect tool requests
    try:
        response = chat(
            model='qwen3-vl:8b-instruct',
            messages=messages,
            tools=_mcp_manager.get_ollama_tools(),
        )
    except Exception as e:
        print(f"[MCP] Error in tool detection call: {e}")
        return messages, tool_calls_made
    
    # Loop: keep calling tools until Ollama gives a final text answer
    max_rounds = 5  # Safety limit to prevent infinite loops
    rounds = 0
    while response.message.tool_calls and rounds < max_rounds:
        rounds += 1
        for tool_call in response.message.tool_calls:
            fn_name = tool_call.function.name
            fn_args = tool_call.function.arguments
            server_name = _mcp_manager.get_tool_server_name(fn_name)
            
            print(f"[MCP] Tool call: {fn_name}({fn_args}) from server '{server_name}'")
            
            # Broadcast to UI so users see the tool being called
            await broadcast_message("tool_call", json.dumps({
                "name": fn_name,
                "args": fn_args,
                "server": server_name,
                "status": "calling"
            }))
            
            # Execute the tool via MCP
            try:
                result = await _mcp_manager.call_tool(fn_name, fn_args)
            except Exception as e:
                result = f"Error executing tool: {e}"
            
            print(f"[MCP] Tool result: {result}")
            
            # Broadcast result to UI
            await broadcast_message("tool_call", json.dumps({
                "name": fn_name,
                "args": fn_args,
                "result": str(result),
                "server": server_name,
                "status": "complete"
            }))
            
            tool_calls_made.append({
                "name": fn_name,
                "args": fn_args,
                "result": str(result),
                "server": server_name,
            })
            
            # Add tool exchange to messages for context
            messages.append(response.message.model_dump())
            messages.append({
                "role": "tool",
                "content": str(result),
            })
        
        # Ask Ollama again with tool results
        try:
            response = chat(
                model='qwen3-vl:8b-instruct',
                messages=messages,
                tools=_mcp_manager.get_ollama_tools(),
            )
        except Exception as e:
            print(f"[MCP] Error in follow-up call: {e}")
            break
    
    # If we got a final text response from the tool-calling loop (non-streamed),
    # we DON'T add it to messages here — the streaming call will generate the 
    # final response so we get token-by-token streaming in the UI.
    # But we DO need to keep the messages updated with tool exchanges.
    
    return messages, tool_calls_made


async def _stream_ollama_chat(user_query: str, image_paths: List[str], chat_history: List[Dict[str, Any]]) -> tuple[str, Dict[str, int], List[Dict[str, Any]]]:
    """Stream Ollama response without blocking the event loop.

    A background thread iterates the blocking Ollama generator and schedules
    WebSocket broadcasts for each incremental token. Returns a tuple of
    (full_output_text, token_stats_dict, tool_calls_list) once streaming completes.
    
    image_paths can be empty list for text-only queries, or contain multiple images.
    """
    loop = asyncio.get_running_loop()
    done_future: asyncio.Future[tuple[str, Dict[str, int], List[Dict[str, Any]]]] = loop.create_future()

    def safe_schedule(coro):
        try:
            loop.call_soon_threadsafe(asyncio.create_task, coro)
        except RuntimeError:
            pass

    def extract_token(chunk) -> tuple[str | None, str | None]:
        """Attempt to pull content and thinking tokens from a chunk.

        Supports both dict (older client) and object (dataclass) shapes.
        Returns (content_token, thinking_token).
        """
        content_token = None
        thinking_token = None
        
        # Dict-based chunk
        if isinstance(chunk, dict):
            msg = chunk.get('message')
            if isinstance(msg, dict):
                content_token = msg.get('content') if isinstance(msg.get('content'), str) and msg.get('content') else None
                thinking_token = msg.get('thinking') if isinstance(msg.get('thinking'), str) and msg.get('thinking') else None
            if not content_token:
                for key in ('response', 'content', 'delta', 'text', 'token'):
                    tok = chunk.get(key)
                    if isinstance(tok, str) and tok:
                        content_token = tok
                        break
            return (content_token, thinking_token)
        
        # Object-based chunk - check for message.thinking first
        if hasattr(chunk, 'message'):
            msg = getattr(chunk, 'message')
            if msg is not None:
                if hasattr(msg, 'thinking'):
                    val = getattr(msg, 'thinking')
                    if isinstance(val, str) and val:
                        thinking_token = val
                if hasattr(msg, 'content'):
                    val = getattr(msg, 'content')
                    if isinstance(val, str) and val:
                        content_token = val
        
        # Fallback for content if not found in message
        if not content_token:
            for attr in ('response', 'content', 'delta', 'token'):
                if hasattr(chunk, attr):
                    val = getattr(chunk, attr)
                    if isinstance(val, str) and val:
                        content_token = val
                        break
        
        return (content_token, thinking_token)

    def producer():
        accumulated: list[str] = []
        thinking_tokens: list[str] = []
        final_message_content: str | None = None
        collected_token_stats: Dict[str, int] = {"prompt_eval_count": 0, "eval_count": 0}
        
        # Build messages list from chat history
        # Images are stored WITH the message they were sent with, so they persist properly
        messages = []
        for msg in chat_history:
            message_data = {
                'role': msg['role'],
                'content': msg['content'],
            }
            # Include images only if they still exist on disk
            if msg.get('images'):
                existing_images = [p for p in msg['images'] if os.path.exists(p)]
                if existing_images:
                    message_data['images'] = existing_images
            messages.append(message_data)
        
        # Add current user query - include images if this is a new image submission
        # Only include images that actually exist on disk
        existing_image_paths = [p for p in image_paths if os.path.exists(p)]
        if existing_image_paths:
            messages.append({
                'role': 'user',
                'content': user_query,
                'images': existing_image_paths,
            })
        else:
            messages.append({
                'role': 'user',
                'content': user_query,
            })
        
        # ── MCP Tool Calling Phase ─────────────────────────────────
        # Before streaming, check if Ollama wants to call any MCP tools.
        # This is done synchronously (non-streamed) because tool calls
        # need the full response to detect tool_calls in the message.
        # The tool results get appended to `messages` so the streamed
        # response below already has tool context.
        tool_calls_list = []
        if _mcp_manager.has_tools():
            # We need to run the async MCP calls from inside this thread.
            # Schedule onto the server's event loop and wait for the result.
            import concurrent.futures
            future = concurrent.futures.Future()
            
            async def _do_tool_calls():
                try:
                    updated, calls = await _handle_mcp_tool_calls(messages.copy(), image_paths)
                    future.set_result((updated, calls))
                except Exception as e:
                    future.set_exception(e)
            
            try:
                loop.call_soon_threadsafe(asyncio.ensure_future, _do_tool_calls())
                # Wait for the tool calls to complete (with timeout)
                updated_messages, tool_calls_list = future.result(timeout=60)
                # Replace messages with the updated version that includes tool exchanges
                messages = updated_messages
            except Exception as e:
                print(f"[MCP] Tool calling phase failed: {e}")
                # Continue without tools — the model will respond normally
        
        try:
            # Use vision model if we have an image, otherwise use text model
            model_name = 'qwen3-vl:8b-instruct'
            generator = chat(
                model=model_name,
                messages=messages,
                stream=True,
            )
            for idx, chunk in enumerate(generator):
                content_token, thinking_token = extract_token(chunk)
                
                # Handle thinking tokens - they come one at a time
                if thinking_token:
                    thinking_tokens.append(thinking_token)
                    safe_schedule(broadcast_message("thinking_chunk", thinking_token))
                
                # Handle regular content - when we start getting content, thinking is done
                if content_token:
                    # If this is first content and we had thinking, send thinking_complete
                    if thinking_tokens and not accumulated:
                        safe_schedule(broadcast_message("thinking_complete", ""))
                    accumulated.append(content_token)
                    safe_schedule(broadcast_message("response_chunk", content_token))
                    
                # Track final message from done chunk and collect token stats
                if hasattr(chunk, 'done') and getattr(chunk, 'done'):
                    token_stats = {
                        "prompt_eval_count": getattr(chunk, 'prompt_eval_count', 0),
                        "eval_count": getattr(chunk, 'eval_count', 0),
                    }
                    collected_token_stats["prompt_eval_count"] = token_stats["prompt_eval_count"] or 0
                    collected_token_stats["eval_count"] = token_stats["eval_count"] or 0
                    safe_schedule(broadcast_message("token_usage", json.dumps(token_stats)))
                    
                    if hasattr(chunk, 'message'):
                        msg = getattr(chunk, 'message')
                        if msg is not None:
                            if hasattr(msg, 'content'):
                                mc = getattr(msg, 'content')
                                if isinstance(mc, str) and mc:
                                    final_message_content = mc
            
            # If we had thinking but never sent complete (e.g., no content followed)
            if thinking_tokens and not accumulated:
                safe_schedule(broadcast_message("thinking_complete", ""))
            
            # Fallback: if no incremental tokens but we have a final message content
            if not accumulated and final_message_content:
                accumulated.append(final_message_content)
                safe_schedule(broadcast_message("response_chunk", final_message_content))
            elif not accumulated:
                # Nothing at all extracted
                safe_schedule(broadcast_message("error", "No content tokens extracted from stream."))
            safe_schedule(broadcast_message("response_complete", ""))
            loop.call_soon_threadsafe(done_future.set_result, (''.join(accumulated), collected_token_stats, tool_calls_list))
        except Exception as e:
            err = f"Error streaming from Ollama: {e}"
            print(err)
            safe_schedule(broadcast_message("error", err))
            if not done_future.done():
                loop.call_soon_threadsafe(done_future.set_result, (err, collected_token_stats, tool_calls_list))

    threading.Thread(target=producer, daemon=True).start()
    return await done_future

#############################################
# Query submission & screenshot lifecycle   #
#############################################

# Track multiple screenshots (list of dicts with id, path, name, thumbnail)
_screenshot_list: List[Dict[str, Any]] = []
_screenshot_counter = 0  # For generating unique IDs
_is_streaming: bool = False
_stream_lock = asyncio.Lock()

# Current capture mode: 'fullscreen' | 'precision' | 'none'
# - fullscreen: auto-capture on submit, hotkey disabled
# - precision: hotkey captures regions, adds to context
# - none: no screenshots (text-only mode)
_current_capture_mode: str = "fullscreen"

# Chat history for multi-turn conversations (cleared on new screenshot)
_chat_history: List[Dict[str, Any]] = []

# Current conversation ID for database persistence
_current_conversation_id: str | None = None

async def handle_set_capture_mode(mode: str):
    """Update the capture mode."""
    global _current_capture_mode
    if mode in ("fullscreen", "precision", "none"):
        _current_capture_mode = mode
        print(f"Capture mode set to: {mode}")
    else:
        print(f"Invalid capture mode: {mode}")

async def handle_remove_screenshot(screenshot_id: str):
    """Remove a specific screenshot from context."""
    global _screenshot_list
    
    # Find and remove the screenshot
    for i, ss in enumerate(_screenshot_list):
        if ss["id"] == screenshot_id:
            # Delete the file
            if os.path.exists(ss["path"]):
                try:
                    os.remove(ss["path"])
                except Exception as e:
                    print(f"Error deleting screenshot file: {e}")
            
            # Remove from list
            _screenshot_list.pop(i)
            print(f"Screenshot removed: {screenshot_id}")
            
            # Notify clients
            await broadcast_message("screenshot_removed", json.dumps({"id": screenshot_id}))
            return
    
    print(f"Screenshot not found: {screenshot_id}")

async def handle_clear_context():
    """Clear screenshots and chat history for a fresh start."""
    global _screenshot_list, _chat_history, _current_conversation_id
    
    # Clear all screenshots
    for ss in _screenshot_list:
        if os.path.exists(ss["path"]):
            try:
                os.remove(ss["path"])
            except Exception as e:
                print(f"Error deleting screenshot: {e}")
    
    _screenshot_list = []
    
    # Clear chat history and reset conversation ID
    _chat_history = []
    _current_conversation_id = None
    print("Context cleared: screenshots and chat history reset")
    
    await broadcast_message("context_cleared", "Context cleared. Ready for new conversation.")

async def handle_resume_conversation(conversation_id: str):
    """Resume a previously saved conversation by loading it into the active chat."""
    global _chat_history, _current_conversation_id, _screenshot_list
    
    # Clear current state
    _chat_history = []
    for ss in _screenshot_list:
        if os.path.exists(ss["path"]):
            try:
                os.remove(ss["path"])
            except Exception as e:
                print(f"Error deleting screenshot: {e}")
    _screenshot_list = []
    
    # Load conversation from database
    messages = db.get_full_conversation(conversation_id)
    _current_conversation_id = conversation_id
    
    # Rebuild in-memory chat history from database
    # Also generate thumbnails for any images so the frontend can display them
    for msg in messages:
        entry = {'role': msg['role'], 'content': msg['content']}
        if msg.get('images'):
            entry['images'] = msg['images']
            # Generate thumbnails for frontend display
            thumbnails = []
            for img_path in msg['images']:
                if os.path.exists(img_path):
                    thumb = create_thumbnail(img_path)
                    thumbnails.append({'name': os.path.basename(img_path), 'thumbnail': thumb})
                else:
                    thumbnails.append({'name': os.path.basename(img_path), 'thumbnail': None})
            msg['images'] = thumbnails  # Replace file paths with thumbnail data for frontend
        _chat_history.append(entry)
    
    print(f"Resumed conversation {conversation_id} with {len(_chat_history)} messages")
    
    # Notify client that conversation is loaded
    token_usage = db.get_token_usage(conversation_id)
    await broadcast_message("conversation_resumed", json.dumps({
        "conversation_id": conversation_id,
        "messages": messages,
        "token_usage": token_usage
    }))

async def handle_submit_query(user_query: str, capture_mode: str = "none"):
    """Handle query submitted from a client. Screenshot is optional."""
    global _screenshot_list, _is_streaming, _chat_history, _screenshot_counter, _current_conversation_id
    
    print(f"[DEBUG] handle_submit_query called: capture_mode={capture_mode}, screenshots={len(_screenshot_list)}, history={len(_chat_history)}")
    
    async with _stream_lock:
        if _is_streaming:
            await broadcast_message("error", "Already streaming a response. Please wait for completion.")
            return
        _is_streaming = True

    # Handle fullscreen mode - auto-capture ONLY on first message of a new conversation
    # (no screenshots AND no chat history means this is a fresh start)
    # Follow-up questions rely on the LLM's conversation memory
    if capture_mode == "fullscreen" and len(_screenshot_list) == 0 and len(_chat_history) == 0:
        print(f"[DEBUG] Taking fullscreen screenshot (new conversation)")
        try:
            # Notify about screenshot capture start
            await broadcast_message("screenshot_start", "Taking fullscreen screenshot...")
            
            # Give the UI time to hide (WebSocket message + React re-render)
            await asyncio.sleep(0.4)
            
            # Take fullscreen screenshot
            image_path = take_fullscreen_screenshot(SCREENSHOT_FOLDER)
            
            if image_path and os.path.exists(image_path):
                # Convert to absolute path for reliable DB storage
                image_path = os.path.abspath(image_path)
                # Generate ID and thumbnail
                _screenshot_counter += 1
                ss_id = f"ss_{_screenshot_counter}"
                thumbnail = create_thumbnail(image_path)
                name = os.path.basename(image_path)
                
                # Add to list
                ss_data = {
                    "id": ss_id,
                    "path": image_path,
                    "name": name,
                    "thumbnail": thumbnail
                }
                _screenshot_list.append(ss_data)
                
                # Notify clients
                await broadcast_message("screenshot_added", json.dumps({
                    "id": ss_id,
                    "name": name,
                    "thumbnail": thumbnail
                }))
                
                print(f"Fullscreen screenshot captured: {ss_id}")
        except Exception as e:
            print(f"Error taking fullscreen screenshot: {e}")

    # Get all image paths for the query (use absolute paths)
    image_paths = [os.path.abspath(ss["path"]) for ss in _screenshot_list if os.path.exists(ss["path"])]

    # Echo query to clients (outside lock to not block other ops)
    await broadcast_message("query", user_query)

    try:
        # Pass current chat history to the streaming function
        response_text, token_stats, tool_calls = await _stream_ollama_chat(user_query, image_paths, _chat_history.copy())
        
        # Create conversation in DB on the first message (lazy creation)
        if _current_conversation_id is None:
            # Use the first ~50 chars of the user's query as the title
            title = user_query[:50] + ('...' if len(user_query) > 50 else '')
            _current_conversation_id = db.start_new_conversation(title)
            print(f"Created new conversation: {_current_conversation_id}")
        
        # Persist token usage to database (now that conversation ID is guaranteed)
        input_tokens = token_stats.get("prompt_eval_count", 0)
        output_tokens = token_stats.get("eval_count", 0)
        if input_tokens or output_tokens:
            try:
                db.add_token_usage(_current_conversation_id, input_tokens, output_tokens)
            except Exception as e:
                print(f"Error saving token usage: {e}")
        
        # Broadcast tool calls summary so the frontend can display them
        if tool_calls:
            await broadcast_message("tool_calls_summary", json.dumps(tool_calls))
        
        # Add this exchange to chat history for future follow-ups
        # Store images WITH the user message so they persist in history
        user_msg = {'role': 'user', 'content': user_query}
        if image_paths:
            user_msg['images'] = image_paths
        _chat_history.append(user_msg)
        assistant_msg: Dict[str, Any] = {'role': 'assistant', 'content': response_text}
        if tool_calls:
            assistant_msg['tool_calls'] = tool_calls
        _chat_history.append(assistant_msg)
        
        # Persist to database
        db.add_message(_current_conversation_id, 'user', user_query, image_paths if image_paths else None)
        db.add_message(_current_conversation_id, 'assistant', response_text)
        
        # Broadcast the conversation_id to the frontend so it knows the active chat
        await broadcast_message("conversation_saved", json.dumps({
            "conversation_id": _current_conversation_id
        }))
        
        print(f"Chat history now has {len(_chat_history)} messages (conversation: {_current_conversation_id})")
        
        # Clear screenshots from UI after they've been embedded in chat history
        # The images are now stored in _chat_history, so we can clear the screenshot list
        if image_paths and len(_screenshot_list) > 0:
            _screenshot_list.clear()
            await broadcast_message("screenshots_cleared", "")
            print("Screenshots cleared from UI - images now embedded in chat history")
        
    except Exception as e:
        await broadcast_message("error", f"Error processing with AI: {e}")
    finally:
        async with _stream_lock:
            _is_streaming = False

async def _on_screenshot_start():
    """Called when screenshot capture starts; notify clients to hide window."""
    global _current_capture_mode
    
    # Only process hotkey captures in precision mode
    if _current_capture_mode != "precision":
        print(f"Hotkey capture ignored - not in precision mode (current: {_current_capture_mode})")
        return
    
    print("Screenshot capture starting - hiding window")
    await broadcast_message("screenshot_start", "Screenshot capture starting")

def process_screenshot_start():
    """Hook invoked by screenshot service thread when screenshot capture starts.
    
    Schedules a coroutine on the running server loop to broadcast that
    screenshot capture is starting so the UI can hide the window.
    """
    server_loop = _server_loop_holder.get("loop")
    if server_loop is None:
        print("Server loop not ready yet. Skipping screenshot start processing.")
        return None

    def schedule():
        asyncio.create_task(_on_screenshot_start())

    try:
        server_loop.call_soon_threadsafe(schedule)
    except Exception as e:
        print(f"Failed to schedule screenshot start handling: {e}")
    return None

async def _on_screenshot_captured(image_path: str):
    """Called when a screenshot is captured via hotkey; add to screenshot list."""
    global _screenshot_list, _screenshot_counter, _current_capture_mode
    
    # Only process hotkey captures in precision mode
    if _current_capture_mode != "precision":
        print(f"Hotkey capture ignored - not in precision mode (current: {_current_capture_mode})")
        # Delete the captured file since we're not using it
        if os.path.exists(image_path):
            try:
                os.remove(image_path)
            except Exception as e:
                print(f"Error deleting unused screenshot: {e}")
        return
    
    # Generate ID and thumbnail
    _screenshot_counter += 1
    ss_id = f"ss_{_screenshot_counter}"
    abs_image_path = os.path.abspath(image_path)
    thumbnail = create_thumbnail(abs_image_path)
    name = os.path.basename(abs_image_path)
    
    # Add to list (use absolute path for reliable DB storage)
    ss_data = {
        "id": ss_id,
        "path": abs_image_path,
        "name": name,
        "thumbnail": thumbnail
    }
    _screenshot_list.append(ss_data)
    
    print(f"Screenshot added to context: {ss_id} - {name}")
    
    # Notify clients with the new screenshot data
    await broadcast_message("screenshot_added", json.dumps({
        "id": ss_id,
        "name": name,
        "thumbnail": thumbnail
    }))
    
    # Also send legacy screenshot_ready for backwards compatibility
    await broadcast_message("screenshot_ready", "Screenshot captured. Enter your query and press Enter.")

def process_screenshot(image_path):
    """Hook invoked by screenshot service thread when a screenshot is taken.

    Schedules a coroutine on the running server loop to broadcast that a
    screenshot is ready and store its path. Does NOT ask for terminal input.
    """
    server_loop = _server_loop_holder.get("loop")
    if server_loop is None:
        print("Server loop not ready yet. Skipping screenshot processing.")
        return None

    def schedule():
        asyncio.create_task(_on_screenshot_captured(image_path))

    try:
        server_loop.call_soon_threadsafe(schedule)
    except Exception as e:
        print(f"Failed to schedule screenshot handling: {e}")
    return None

def start_fastapi_server():
    """Start FastAPI server in a dedicated thread & store its loop."""
    # Find an available port
    try:
        port = find_available_port(8000)
        print(f"Starting server on port {port}")
    except RuntimeError as e:
        print(f"Error finding available port: {e}")
        return
    
    loop = asyncio.new_event_loop()
    _server_loop_holder["loop"] = loop
    _server_loop_holder["port"] = port  # Store the port for reference
    asyncio.set_event_loop(loop)
    
    # Initialize MCP tool servers on this event loop before serving
    try:
        loop.run_until_complete(_init_mcp_servers())
    except Exception as e:
        print(f"[MCP] Failed to initialize servers (non-fatal): {e}")
    
    config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="warning", loop="asyncio")
    server = uvicorn.Server(config)
    loop.run_until_complete(server.serve())

def main():
    global _screenshot_service, _server_thread, _service_thread
    
    print("Starting FastAPI WebSocket server...")
    # Start FastAPI server in background
    _server_thread = threading.Thread(target=start_fastapi_server, daemon=True)
    _server_thread.start()

    # Wait until loop is available (startup barrier)
    for _ in range(50):  # up to ~5 seconds
        if _server_loop_holder.get("loop") is not None:
            break
        time.sleep(0.1)
    else:
        print("Warning: server loop not initialized; continuing anyway.")
    
    # Get the actual port being used
    port = _server_loop_holder.get("port", 8000)
    
    print("Starting screenshot service in background...")
    print("Press Ctrl+Shift+Alt+S anytime to take a screenshot")
    print("Screenshots will be processed and streamed via WebSocket")
    print(f"Visit http://localhost:{port} to see responses in real-time")
    print("The service will run until you close this program")
    
    # Start the service in a separate thread with AI callback
    # Import and create the screenshot service
    try:
        from ss import ScreenshotService
        _screenshot_service = ScreenshotService(process_screenshot, process_screenshot_start)
        _service_thread = threading.Thread(
            target=_screenshot_service.start_listener, 
            args=(SCREENSHOT_FOLDER,),
            daemon=True
        )
        _service_thread.start()
    except Exception as e:
        print(f"Error starting screenshot service: {e}")
    
    # Keep the main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nExiting...")
        cleanup_resources()
        return

if __name__ == "__main__":
    main()