"""
WebSocket message handlers.

Handles all incoming WebSocket message types and routes them to appropriate services.
"""

import json
from typing import Dict, Any
from fastapi import WebSocket

from ..core.state import app_state
from ..services.conversations import ConversationService
from ..services.screenshots import ScreenshotHandler


class MessageHandler:
    """
    Handles incoming WebSocket messages and routes them to appropriate services.

    Each method handles a specific message type from the client.
    """

    def __init__(self, websocket: WebSocket):
        self.websocket = websocket

    async def handle(self, data: Dict[str, Any]):
        """Route a message to the appropriate handler."""
        msg_type = data.get("type")
        handler = getattr(self, f"_handle_{msg_type}", None)

        if handler:
            await handler(data)
        # Silently ignore unknown types

    async def _handle_submit_query(self, data: Dict[str, Any]):
        """Handle query submission."""
        import asyncio

        query_text = data.get("content", "").strip()
        capture_mode = data.get("capture_mode", "none")
        model = data.get("model", "")

        # Update the selected model in global state so the LLM provider uses it
        if model:
            app_state.selected_model = model

        if not query_text:
            await self.websocket.send_text(
                json.dumps({"type": "error", "content": "Empty query"})
            )
            return

        # Run as background task
        asyncio.create_task(ConversationService.submit_query(query_text, capture_mode))

    async def _handle_clear_context(self, data: Dict[str, Any]):
        """Handle context clearing."""
        await ConversationService.clear_context()

    async def _handle_remove_screenshot(self, data: Dict[str, Any]):
        """Handle screenshot removal."""
        screenshot_id = data.get("id")
        if screenshot_id:
            await ScreenshotHandler.remove_screenshot(screenshot_id)

    async def _handle_set_capture_mode(self, data: Dict[str, Any]):
        """Handle capture mode change."""
        mode = data.get("mode", "fullscreen")
        if mode in ("fullscreen", "precision", "none"):
            app_state.capture_mode = mode
            print(f"Capture mode set to: {mode}")

    async def _handle_stop_streaming(self, data: Dict[str, Any]):
        """Handle stop streaming request."""
        app_state.stop_streaming = True

    async def _handle_get_conversations(self, data: Dict[str, Any]):
        """Handle conversation list request."""
        limit = data.get("limit", 50)
        offset = data.get("offset", 0)
        conversations = ConversationService.get_conversations(
            limit=limit, offset=offset
        )
        await self.websocket.send_text(
            json.dumps(
                {"type": "conversations_list", "content": json.dumps(conversations)}
            )
        )

    async def _handle_load_conversation(self, data: Dict[str, Any]):
        """Handle full conversation load request."""
        conv_id = data.get("conversation_id")
        if conv_id:
            messages = ConversationService.get_full_conversation(conv_id)
            await self.websocket.send_text(
                json.dumps(
                    {
                        "type": "conversation_loaded",
                        "content": json.dumps(
                            {"conversation_id": conv_id, "messages": messages}
                        ),
                    }
                )
            )

    async def _handle_delete_conversation(self, data: Dict[str, Any]):
        """Handle conversation deletion."""
        conv_id = data.get("conversation_id")
        if conv_id:
            ConversationService.delete_conversation(conv_id)
            await self.websocket.send_text(
                json.dumps(
                    {
                        "type": "conversation_deleted",
                        "content": json.dumps({"conversation_id": conv_id}),
                    }
                )
            )

    async def _handle_search_conversations(self, data: Dict[str, Any]):
        """Handle conversation search."""
        search_term = data.get("query", "")
        if search_term:
            results = ConversationService.search_conversations(search_term)
        else:
            results = ConversationService.get_conversations(limit=50)

        await self.websocket.send_text(
            json.dumps({"type": "conversations_list", "content": json.dumps(results)})
        )

    async def _handle_resume_conversation(self, data: Dict[str, Any]):
        """Handle conversation resumption."""
        conv_id = data.get("conversation_id")
        if conv_id:
            await ConversationService.resume_conversation(conv_id)

    async def _handle_start_recording(self, data: Dict[str, Any]):
        """Handle start recording request."""
        if app_state.transcription_service:
            app_state.transcription_service.start_recording()

    async def _handle_stop_recording(self, data: Dict[str, Any]):
        """Handle stop recording request."""
        from ..core.thread_pool import run_in_thread

        if app_state.transcription_service:
            # Run transcription in a separate thread to avoid blocking the event loop
            text = await run_in_thread(
                app_state.transcription_service.stop_recording
            )

            await self.websocket.send_text(
                json.dumps({"type": "transcription_result", "content": text})
            )
