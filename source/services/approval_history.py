"""
Approval History Manager.

Manages the exec-approvals.json file for the "on-miss" ask level.
When a user clicks "Allow & Remember", the command signature is saved
so it auto-approves next time.

File location: user_data/exec-approvals.json
"""

import json
import hashlib
import os
import time


_APPROVALS_FILE = os.path.join("user_data", "exec-approvals.json")


def _load_approvals() -> dict:
    """Load the approvals file, creating it if it doesn't exist."""
    if not os.path.exists(_APPROVALS_FILE):
        return {"approvals": []}

    try:
        with open(_APPROVALS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "approvals" not in data:
                data["approvals"] = []
            return data
    except (json.JSONDecodeError, IOError):
        return {"approvals": []}


def _save_approvals(data: dict):
    """Save the approvals file."""
    os.makedirs(os.path.dirname(_APPROVALS_FILE), exist_ok=True)
    with open(_APPROVALS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _compute_hash(command_signature: str) -> str:
    """Compute a stable hash for a command signature."""
    return hashlib.sha256(command_signature.encode("utf-8")).hexdigest()[:16]


def _normalize_command(command: str) -> str:
    """
    Normalize a command to a signature for approval matching.

    Strips arguments that are likely to change between invocations
    (file paths, URLs, etc.) while keeping the base command.
    For simplicity, we use the first token (the executable/command name).
    """
    parts = command.strip().split()
    if not parts:
        return command
    # Use first 1-2 tokens as the signature
    # e.g., "npm install", "git status", "python script.py" -> "npm install", "git status", "python"
    if len(parts) >= 2 and parts[0] in ("npm", "npx", "pip", "git", "docker", "cargo", "uv"):
        return f"{parts[0]} {parts[1]}"
    return parts[0]


def is_command_approved(command: str) -> bool:
    """
    Check if a command (or its normalized signature) has been
    previously approved and remembered.
    """
    data = _load_approvals()
    signature = _normalize_command(command)
    sig_hash = _compute_hash(signature)

    return any(a["hash"] == sig_hash for a in data["approvals"])


def remember_approval(command: str):
    """
    Save a command's approval so future identical commands auto-approve.
    Called when user clicks "Allow & Remember".
    """
    data = _load_approvals()
    signature = _normalize_command(command)
    sig_hash = _compute_hash(signature)

    # Don't duplicate
    if any(a["hash"] == sig_hash for a in data["approvals"]):
        return

    data["approvals"].append({
        "hash": sig_hash,
        "command_signature": signature,
        "approved_at": time.time(),
    })

    _save_approvals(data)


def get_approval_count() -> int:
    """Return the number of remembered approvals."""
    data = _load_approvals()
    return len(data["approvals"])


def clear_approvals():
    """Clear all remembered approvals."""
    _save_approvals({"approvals": []})
