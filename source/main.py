from ollama import chat
from .ss import take_region_screenshot, start_screenshot_service
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
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
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

async def process_screenshot_async(image_path):
    """Process screenshot with AI and stream to WebSocket (non-blocking)."""
    user_query = await asyncio.to_thread(input, "Please enter your query for the screenshot: ")
    print("\nProcessing screenshot + Query")

    await broadcast_message("query", user_query)

    try:
        output = await _stream_ollama_chat(user_query, image_path)
    except Exception as e:
        error_msg = f"Error processing with AI: {e}"
        await broadcast_message("error", error_msg)
        output = error_msg

    # Cleanup & logging
    folder_path = os.path.dirname(image_path)
    clear_screenshots_folder(folder_path)
    print("-" * 50)
    print("Screenshot processed. Check WebSocket clients for response.")
    print("The service continues running for more screenshots...")
    return output

def process_screenshot(image_path):
    """Public sync hook invoked by screenshot service thread.

    Instead of creating a NEW event loop (which then attempts to use
    websocket objects bound to the uvicorn loop and crashes with
    _ProactorBaseWritePipeTransport assertion errors on Windows), we submit
    the coroutine to the existing server loop thread-safely.
    """
    server_loop = _server_loop_holder.get("loop")
    if server_loop is None:
        print("Server loop not ready yet. Skipping screenshot processing.")
        return None
    future: Future = asyncio.run_coroutine_threadsafe(
        process_screenshot_async(image_path), server_loop
    )
    try:
        return future.result()
    except Exception as e:
        print(f"Error awaiting screenshot processing: {e}")
        return None

def start_fastapi_server():
    """Start FastAPI server in a dedicated thread & store its loop."""
    loop = asyncio.new_event_loop()
    _server_loop_holder["loop"] = loop
    asyncio.set_event_loop(loop)
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="warning", loop="asyncio")
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
    
    print("Starting screenshot service in background...")
    print("Press Ctrl+Shift+Alt+S anytime to take a screenshot")
    print("Screenshots will be processed and streamed via WebSocket")
    print("Visit http://localhost:8000 to see responses in real-time")
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