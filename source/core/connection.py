"""
WebSocket connection management.

Handles tracking of active WebSocket connections and message broadcasting.
"""
from typing import List, Dict, Any
from fastapi import WebSocket
import json


class ConnectionManager:
    """
    Manages WebSocket connections for real-time communication.
    
    Handles:
    - Connection tracking
    - Safe message broadcasting
    - Automatic disconnection cleanup
    """
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """Accept and track a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket from tracked connections."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        """
        Broadcast a message to all connected clients.
        
        Automatically removes disconnected clients.
        """
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                disconnected.append(connection)

        # Remove disconnected clients
        for conn in disconnected:
            self.disconnect(conn)
    
    async def broadcast_json(self, message_type: str, content: str):
        """Broadcast a JSON message with type and content fields."""
        message = json.dumps({"type": message_type, "content": content})
        await self.broadcast(message)


# Global connection manager instance
manager = ConnectionManager()


async def broadcast_message(message_type: str, content: str):
    """Helper function to broadcast messages."""
    await manager.broadcast_json(message_type, content)
