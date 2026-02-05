from ollama import chat
import sys
import os
import socket
import signal
import atexit

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

# Global variables for cleanup
_screenshot_service = None
_server_thread = None
_service_thread = None

def cleanup_resources():
    """Clean up all resources when shutting down."""
    global _screenshot_service, _server_thread, _service_thread
    print("Cleaning up resources...")
    
    # Stop screenshot service
    if _screenshot_service:
        try:
            _screenshot_service.stop_listener()
            print("Screenshot service stopped")
        except Exception as e:
            print(f"Error stopping screenshot service: {e}")
    
    # Clean up screenshot folder
    try:
        if os.path.exists("screenshots"):
            clear_screenshots_folder("screenshots")
            print("Screenshots folder cleaned")
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

async def _stream_ollama_chat(user_query: str, image_path: str, chat_history: List[Dict[str, Any]]) -> str:
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
        
        # Build messages list from chat history
        # First message includes the image, follow-ups are text-only
        messages = []
        for i, msg in enumerate(chat_history):
            if i == 0:
                # First user message includes the image
                messages.append({
                    'role': msg['role'],
                    'content': msg['content'],
                    'images': [image_path],
                })
            else:
                messages.append({
                    'role': msg['role'],
                    'content': msg['content'],
                })
        
        # Add current user query
        if len(messages) == 0:
            # First message - include image
            messages.append({
                'role': 'user',
                'content': user_query,
                'images': [image_path],
            })
        else:
            # Follow-up message - no image needed
            messages.append({
                'role': 'user',
                'content': user_query,
            })
        
        try:
            generator = chat(
                model='qwen3-vl:8b-instruct',
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
                    
                # Track final message from done chunk
                if hasattr(chunk, 'done') and getattr(chunk, 'done') and hasattr(chunk, 'message'):
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

# Chat history for multi-turn conversations (cleared on new screenshot)
_chat_history: List[Dict[str, Any]] = []

async def handle_submit_query(user_query: str):
    """Handle query submitted from a client for the most recent screenshot."""
    global _latest_screenshot_path, _is_streaming, _chat_history
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
        # Pass current chat history to the streaming function
        response_text = await _stream_ollama_chat(user_query, image_path, _chat_history.copy())
        
        # Add this exchange to chat history for future follow-ups
        _chat_history.append({'role': 'user', 'content': user_query})
        _chat_history.append({'role': 'assistant', 'content': response_text})
        print(f"Chat history now has {len(_chat_history)} messages")
        
    except Exception as e:
        await broadcast_message("error", f"Error processing with AI: {e}")
    finally:
        async with _stream_lock:
            _is_streaming = False
        # Note: We no longer clear the screenshot here to allow follow-up questions

async def _on_screenshot_start():
    """Called when screenshot capture starts; notify clients to hide window."""
    global _latest_screenshot_path
    print("Screenshot capture starting - hiding window")
    
    # Clear old screenshot BEFORE new one is taken (so we don't delete the new one)
    if _latest_screenshot_path:
        old_folder = os.path.dirname(_latest_screenshot_path)
        if old_folder:
            clear_screenshots_folder(old_folder)
        _latest_screenshot_path = None  # Clear the path since we deleted it
    
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
    """Called when a screenshot is captured; notify clients to ask for query."""
    global _latest_screenshot_path, _chat_history
    
    # Clear chat history for new conversation
    _chat_history = []
    print("Chat history cleared for new screenshot")
    
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
            args=("screenshots",),
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