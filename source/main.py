from ollama import chat
import sys
import os
import socket

# Add current directory to path for imports when run as script
if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)

# Now import ss module
try:
    from .ss import take_region_screenshot, start_screenshot_service
except ImportError:
    # Fallback for when run as script
    from ss import take_region_screenshot, start_screenshot_service
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
      {"type": "submit_query", "content": "<question>"}

    Server -> Client broadcast messages (JSON):
      screenshot_ready            : Screenshot captured, UI should enable query input
      query                       : Echo of submitted query
      response_chunk              : Streaming model token/content fragment
      response_complete           : Model finished
      error                       : Error message
    """
    await manager.connect(websocket)
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
                if not query_text:
                    await websocket.send_text(json.dumps({"type": "error", "content": "Empty query"}))
                    continue
                await handle_submit_query(query_text)
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

async def _stream_ollama_chat(user_query: str, image_path: str) -> str:
    """Stream Ollama response without blocking the event loop.

    A background thread iterates the blocking Ollama generator and schedules
    WebSocket broadcasts for each incremental token. Returns the full output
    once streaming completes.
    """
    loop = asyncio.get_running_loop()
    done_future: asyncio.Future[str] = loop.create_future()

    def safe_schedule(coro):
        try:
            loop.call_soon_threadsafe(asyncio.create_task, coro)
        except RuntimeError:
            pass

    def extract_token(chunk) -> str | None:
        """Attempt to pull an incremental token from a chunk.

        Supports both dict (older client) and object (dataclass) shapes.
        """
        # Dict-based chunk
        if isinstance(chunk, dict):
            msg = chunk.get('message')
            if isinstance(msg, dict):
                tok = msg.get('content')
                if isinstance(tok, str) and tok:
                    return tok
            for key in ('response', 'content', 'delta', 'text', 'token'):
                tok = chunk.get(key)
                if isinstance(tok, str) and tok:
                    return tok
            return None
        # Object-based chunk
        # Common attributes possibly present: response (stream token), message (final), done, created_at
        for attr in ('response', 'content', 'delta', 'token'):
            if hasattr(chunk, attr):
                val = getattr(chunk, attr)
                if isinstance(val, str) and val:
                    return val
        # message may itself be an object with .content
        if hasattr(chunk, 'message'):
            msg = getattr(chunk, 'message')
            if msg is not None and hasattr(msg, 'content'):
                val = getattr(msg, 'content')
                if isinstance(val, str) and val:
                    return val
        return None

    def producer():
        accumulated: list[str] = []
        final_message_content: str | None = None
        try:
            generator = chat(
                model='qwen2.5vl:7b',
                messages=[{
                    'role': 'user',
                    'content': user_query,
                    'images': [image_path],
                }],
                stream=True
            )
            for idx, chunk in enumerate(generator):
                token = extract_token(chunk)
                if token:
                    accumulated.append(token)
                    safe_schedule(broadcast_message("response_chunk", token))
                # Track possible final assembled message (object style)
                if hasattr(chunk, 'done') and getattr(chunk, 'done') and hasattr(chunk, 'message'):
                    msg = getattr(chunk, 'message')
                    if msg is not None and hasattr(msg, 'content'):
                        mc = getattr(msg, 'content')
                        if isinstance(mc, str) and mc:
                            final_message_content = mc
            # Fallback: if no incremental tokens but we have a final message content
            if not accumulated and final_message_content:
                accumulated.append(final_message_content)
                safe_schedule(broadcast_message("response_chunk", final_message_content))
            elif not accumulated:
                # Nothing at all extracted
                safe_schedule(broadcast_message("error", "No content tokens extracted from stream."))
            safe_schedule(broadcast_message("response_complete", ""))
            loop.call_soon_threadsafe(done_future.set_result, ''.join(accumulated))
        except Exception as e:
            err = f"Error streaming from Ollama: {e}"
            print(err)
            safe_schedule(broadcast_message("error", err))
            if not done_future.done():
                loop.call_soon_threadsafe(done_future.set_result, err)

    threading.Thread(target=producer, daemon=True).start()
    return await done_future

#############################################
# Query submission & screenshot lifecycle   #
#############################################

# Track latest screenshot awaiting a query
_latest_screenshot_path: str | None = None
_is_streaming: bool = False
_stream_lock = asyncio.Lock()

async def handle_submit_query(user_query: str):
    """Handle query submitted from a client for the most recent screenshot."""
    global _latest_screenshot_path, _is_streaming
    async with _stream_lock:
        if _is_streaming:
            await broadcast_message("error", "Already streaming a response. Please wait for completion.")
            return
        if not _latest_screenshot_path or not os.path.exists(_latest_screenshot_path):
            await broadcast_message("error", "No screenshot available. Take a screenshot first (Ctrl+Shift+Alt+S).")
            return
        image_path = _latest_screenshot_path
        _is_streaming = True

    # Echo query to clients (outside lock to not block other ops)
    await broadcast_message("query", user_query)

    try:
        await _stream_ollama_chat(user_query, image_path)
    except Exception as e:
        await broadcast_message("error", f"Error processing with AI: {e}")
    finally:
        # Cleanup after completion
        folder_path = os.path.dirname(image_path)
        clear_screenshots_folder(folder_path)
        async with _stream_lock:
            _latest_screenshot_path = None
            _is_streaming = False
        print("Screenshot processed & cleaned up. Ready for next capture.")

async def _on_screenshot_captured(image_path: str):
    """Called when a screenshot is captured; notify clients to ask for query."""
    global _latest_screenshot_path
    _latest_screenshot_path = image_path
    print(f"Screenshot ready for query: {image_path}")
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
    config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="warning", loop="asyncio")
    server = uvicorn.Server(config)
    loop.run_until_complete(server.serve())

def main():
    print("Starting FastAPI WebSocket server...")
    # Start FastAPI server in background
    server_thread = threading.Thread(target=start_fastapi_server, daemon=True)
    server_thread.start()

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
    service_thread = threading.Thread(
        target=start_screenshot_service, 
        args=("screenshots", process_screenshot),
        daemon=True
    )
    service_thread.start()
    
    # Keep the main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nExiting...")
        return

if __name__ == "__main__":
    main()