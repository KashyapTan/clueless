"""
Global application state management.

Centralizes all mutable global state into a single class for better
maintainability and testability.
"""

from typing import List, Dict, Any, Optional
import threading
from ..ss import ScreenshotService
import asyncio


class AppState:
    """
    Centralized application state container.

    This replaces scattered global variables with a single, well-organized
    state object that can be imported and accessed throughout the application.
    """

    def __init__(self):
        # Screenshot state
        self.screenshot_list: List[Dict[str, Any]] = []
        self.screenshot_counter: int = 0

        # Streaming state
        self.is_streaming: bool = False
        self.stop_streaming: bool = False
        self.stream_lock: asyncio.Lock = asyncio.Lock()

        # Capture mode: 'fullscreen' | 'precision' | 'none'
        self.capture_mode: str = "fullscreen"

        # Currently selected model (updated when user picks from dropdown)
        from ..config import DEFAULT_MODEL

        self.selected_model: str = DEFAULT_MODEL

        # Chat history for multi-turn conversations
        self.chat_history: List[Dict[str, Any]] = []

        # Current conversation ID for database persistence
        self.conversation_id: Optional[str] = None

        # Service references for cleanup
        self.screenshot_service: ScreenshotService | None = None
        self.transcription_service: Any = None
        self.server_thread: threading.Thread | None = None
        self.service_thread: threading.Thread | None = None

        # Event loop holder for cross-thread scheduling
        self.server_loop_holder: Dict[str, Any] = {}

    def reset_conversation(self):
        """Reset state for a new conversation."""
        self.chat_history = []
        self.conversation_id = None
        self.screenshot_list = []

    def add_screenshot(self, screenshot_data: Dict[str, Any]) -> str:
        """Add a screenshot and return its ID."""
        self.screenshot_counter += 1
        ss_id = f"ss_{self.screenshot_counter}"
        screenshot_data["id"] = ss_id
        self.screenshot_list.append(screenshot_data)
        return ss_id

    def remove_screenshot(self, screenshot_id: str) -> bool:
        """Remove a screenshot by ID. Returns True if found and removed."""
        for i, ss in enumerate(self.screenshot_list):
            if ss["id"] == screenshot_id:
                self.screenshot_list.pop(i)
                return True
        return False

    def get_image_paths(self) -> List[str]:
        """Get list of valid image paths from current screenshots."""
        import os

        return [
            os.path.abspath(ss["path"])
            for ss in self.screenshot_list
            if os.path.exists(ss["path"])
        ]


# Global singleton instance
app_state = AppState()
