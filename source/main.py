from ollama import chat
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
from typing import List

# FastAPI WebSocket setup
app = FastAPI()

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

@app.get("/")
async def get():
    return HTMLResponse("""
<!DOCTYPE html>
<html>
    <head>
        <title>Ollama Response Stream</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            #messages { max-height: 600px; overflow-y: auto; border: 1px solid #ccc; padding: 10px; }
            .query { background: #e3f2fd; padding: 10px; margin: 5px 0; border-radius: 5px; }
            .response { background: #f5f5f5; padding: 5px; margin: 2px 0; }
            .complete { background: #c8e6c9; padding: 10px; margin: 5px 0; border-radius: 5px; }
            .error { background: #ffcdd2; padding: 10px; margin: 5px 0; border-radius: 5px; }
        </style>
    </head>
    <body>
        <h1>Ollama Response Stream</h1>
        <div id="messages"></div>
        <script>
            var ws = new WebSocket("ws://localhost:8000/ws");
            var responseDiv = null;
            
            ws.onmessage = function(event) {
                var messages = document.getElementById('messages');
                var data = JSON.parse(event.data);
                
                if (data.type === 'query') {
                    var queryDiv = document.createElement('div');
                    queryDiv.className = 'query';
                    queryDiv.innerHTML = '<strong>Query:</strong> ' + data.content;
                    messages.appendChild(queryDiv);
                    
                    // Create response container
                    responseDiv = document.createElement('div');
                    responseDiv.className = 'response';
                    responseDiv.innerHTML = '<strong>Response:</strong> ';
                    messages.appendChild(responseDiv);
                    
                } else if (data.type === 'response_chunk' && responseDiv) {
                    responseDiv.innerHTML += data.content;
                    
                } else if (data.type === 'response_complete') {
                    var completeDiv = document.createElement('div');
                    completeDiv.className = 'complete';
                    completeDiv.innerHTML = '<strong>Response Complete</strong>';
                    messages.appendChild(completeDiv);
                    responseDiv = null;
                    
                } else if (data.type === 'error') {
                    var errorDiv = document.createElement('div');
                    errorDiv.className = 'error';
                    errorDiv.innerHTML = '<strong>Error:</strong> ' + data.content;
                    messages.appendChild(errorDiv);
                }
                
                messages.scrollTop = messages.scrollHeight;
            };
            
            ws.onopen = function(event) {
                console.log("Connected to WebSocket");
            };
            
            ws.onclose = function(event) {
                console.log("Disconnected from WebSocket");
            };
        </script>
    </body>
</html>
    """)

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

async def process_screenshot_async(image_path):
    """Process screenshot with AI and stream to WebSocket"""
    user_query = input("Please enter your query for the screenshot: ")
    print(f"\nProcessing screenshot + Query")
    
    # Send query to WebSocket clients
    await broadcast_message("query", user_query)
    
    try:
        response = chat(
            model='qwen2.5vl:7b',
            messages=[
                {
                    'role': 'user',
                    'content': user_query,
                    'images': [image_path],
                }
            ],
            stream=True
        )

        # Stream the output to WebSocket clients
        output = ""
        for chunk in response:
            if 'message' in chunk and 'content' in chunk['message']:
                content = chunk['message']['content']
                output += content
                # Send each chunk to WebSocket clients
                await broadcast_message("response_chunk", content)
            
        # Send completion message
        await broadcast_message("response_complete", "")
            
    except Exception as e:
        error_msg = f"Error processing with AI: {e}"
        await broadcast_message("error", error_msg)
        output = error_msg
    
    # Clear the screenshots folder after processing
    folder_path = os.path.dirname(image_path)
    clear_screenshots_folder(folder_path)
    print("-" * 50)
    print("Screenshot processed. Check WebSocket clients for response.")
    print("The service continues running for more screenshots...")
    
    return output

def process_screenshot(image_path):
    """Wrapper to run async function in event loop"""
    # Create a new event loop for this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(process_screenshot_async(image_path))
    finally:
        loop.close()

def start_fastapi_server():
    """Start FastAPI server in a separate thread"""
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")

def main():
    print("Starting FastAPI WebSocket server...")
    # Start FastAPI server in background
    server_thread = threading.Thread(target=start_fastapi_server, daemon=True)
    server_thread.start()
    
    # Give server time to start
    time.sleep(3)
    
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