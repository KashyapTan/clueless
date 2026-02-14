"""
Application configuration module.

Centralizes all configuration values and constants.
"""
import os
from pathlib import Path

# Project paths
PROJECT_ROOT = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SOURCE_DIR = Path(os.path.dirname(os.path.abspath(__file__)))

# Screenshot storage
SCREENSHOT_FOLDER = os.path.join('user_data', 'screenshots')
os.makedirs(SCREENSHOT_FOLDER, exist_ok=True)

# Server configuration
DEFAULT_PORT = 8000
MAX_PORT_ATTEMPTS = 10

# Model configuration
DEFAULT_MODEL = 'qwen3-vl:8b-instruct'
MAX_MCP_TOOL_ROUNDS = 30

# Capture modes
class CaptureMode:
    FULLSCREEN = "fullscreen"
    PRECISION = "precision"
    NONE = "none"
