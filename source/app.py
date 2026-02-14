"""
FastAPI application factory.

Creates and configures the FastAPI application instance.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.websocket import websocket_endpoint
from .api.http import router as http_router


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.
    
    Returns:
        Configured FastAPI instance
    """
    app = FastAPI(
        title="Clueless API",
        description="AI Chat Assistant with Screenshot Capabilities",
        version="0.1.0"
    )
    
    # Allow the React dev server (Vite on port 5123) to call HTTP endpoints
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Register WebSocket endpoint
    app.add_websocket_route("/ws", websocket_endpoint)
    
    # Register HTTP REST routes (e.g., /api/models/ollama, /api/models/enabled)
    app.include_router(http_router)
    
    return app


# Create the app instance for uvicorn
app = create_app()
