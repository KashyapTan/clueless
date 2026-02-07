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
    from .ss import take_region_screenshot, start_screenshot_service, take_fullscreen_screenshot, create_thumbnail
except ImportError:
    # Fallback for when run as script
    from ss import take_region_screenshot, start_screenshot_service, take_fullscreen_screenshot, create_thumbnail
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
      response_complete           : Model finished
      error                       : Error message
    """
    await manager.connect(websocket)
    
    # Immediately notify client that server is ready for queries (no screenshot required)
    await websocket.send_text(json.dumps({"type": "ready", "content": "Server ready. You can start chatting or take a screenshot (Ctrl+Shift+Alt+S)."}))
    
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

async def _stream_ollama_chat(user_query: str, image_paths: List[str], chat_history: List[Dict[str, Any]]) -> str:
    """Stream Ollama response without blocking the event loop.

    A background thread iterates the blocking Ollama generator and schedules
    WebSocket broadcasts for each incremental token. Returns the full output
    once streaming completes.
    
    image_paths can be empty list for text-only queries, or contain multiple images.
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
        # Images are stored WITH the message they were sent with, so they persist properly
        messages = []
        for msg in chat_history:
            message_data = {
                'role': msg['role'],
                'content': msg['content'],
            }
            # Include images if they were stored with this message
            if msg.get('images'):
                message_data['images'] = msg['images']
            messages.append(message_data)
        
        # Add current user query - include images if this is a new image submission
        if image_paths:
            messages.append({
                'role': 'user',
                'content': user_query,
                'images': image_paths,
            })
        else:
            messages.append({
                'role': 'user',
                'content': user_query,
            })
        
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
    global _screenshot_list, _chat_history
    
    # Clear all screenshots
    for ss in _screenshot_list:
        if os.path.exists(ss["path"]):
            try:
                os.remove(ss["path"])
            except Exception as e:
                print(f"Error deleting screenshot: {e}")
    
    _screenshot_list = []
    
    # Clear chat history
    _chat_history = []
    print("Context cleared: screenshots and chat history reset")
    
    await broadcast_message("context_cleared", "Context cleared. Ready for new conversation.")

async def handle_submit_query(user_query: str, capture_mode: str = "none"):
    """Handle query submitted from a client. Screenshot is optional."""
    global _screenshot_list, _is_streaming, _chat_history, _screenshot_counter
    
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
            image_path = take_fullscreen_screenshot("screenshots")
            
            if image_path and os.path.exists(image_path):
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

    # Get all image paths for the query
    image_paths = [ss["path"] for ss in _screenshot_list if os.path.exists(ss["path"])]

    # Echo query to clients (outside lock to not block other ops)
    await broadcast_message("query", user_query)

    try:
        # Pass current chat history to the streaming function
        response_text = await _stream_ollama_chat(user_query, image_paths, _chat_history.copy())
        
        # Add this exchange to chat history for future follow-ups
        # Store images WITH the user message so they persist in history
        user_msg = {'role': 'user', 'content': user_query}
        if image_paths:
            user_msg['images'] = image_paths
        _chat_history.append(user_msg)
        _chat_history.append({'role': 'assistant', 'content': response_text})
        print(f"Chat history now has {len(_chat_history)} messages")
        
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