"""
Source package initialization.

This module sets up the Python path for imports when running as a script.
"""
import os
import sys

# Add current directory to path for imports when run as script
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)
