"""
OS Path Blocklist for Terminal Security.

Hardcoded blocklist of sensitive OS paths. Commands touching these paths
are rejected before anything else runs. Users never see or configure this —
it silently prevents catastrophic mistakes.

This is the first invisible security layer. Always on, zero configuration.
"""

import os
import re
import platform

# Detect OS once at module level
_IS_WINDOWS = platform.system() == "Windows"
_IS_MAC = platform.system() == "Darwin"


def _get_windows_blocklist() -> list[str]:
    """Return blocked path patterns for Windows."""
    appdata = os.environ.get("APPDATA", "")
    localappdata = os.environ.get("LOCALAPPDATA", "")
    userprofile = os.environ.get("USERPROFILE", "")

    paths = [
        r"C:\Windows\System32",
        r"C:\Windows\SysWOW64",
        r"C:\Windows\Boot",
        r"C:\pagefile.sys",
        r"C:\hiberfil.sys",
    ]

    if appdata:
        paths.append(os.path.join(appdata, "Microsoft", "Credentials"))
    if localappdata:
        paths.append(os.path.join(localappdata, "Microsoft", "Credentials"))
    if userprofile:
        paths.append(os.path.join(userprofile, "NTUSER.DAT"))

    return [p.lower() for p in paths]


def _get_unix_blocklist() -> list[str]:
    """Return blocked path patterns for Unix/macOS."""
    home = os.path.expanduser("~")

    paths = [
        "/etc/passwd",
        "/etc/shadow",
        "/etc/sudoers",
        "/boot",
        "/proc/sys",
        os.path.join(home, ".ssh"),
        os.path.join(home, ".aws", "credentials"),
        os.path.join(home, ".gnupg"),
        "/dev/sd",
    ]

    if _IS_MAC:
        paths.extend(["/System", "/private/etc"])

    return paths


# Build blocklist once at import time
_BLOCKLIST = _get_windows_blocklist() if _IS_WINDOWS else _get_unix_blocklist()

# Dangerous command patterns (OS-independent)
_DANGEROUS_PATTERNS = [
    # Format/destroy disk
    r"\bformat\s+[a-zA-Z]:",
    r"\bmkfs\b",
    r"\bdd\s+.*of=/dev/",
    # Registry destruction (Windows)
    r"\breg\s+delete\s+.*HKLM",
    r"\breg\s+delete\s+.*HKCU",
    # Remove system files
    r"\brm\s+-rf\s+/\s*$",
    r"\brd\s+/s\s+/q\s+[Cc]:\\Windows",
    r"\bdel\s+/[fFsS]\s+[Cc]:\\Windows",
]

_DANGEROUS_RE = [re.compile(p, re.IGNORECASE) for p in _DANGEROUS_PATTERNS]


def check_blocklist(command: str) -> tuple[bool, str]:
    """
    Check if a command touches any blocked OS paths or matches
    dangerous patterns.

    Returns:
        (blocked: bool, reason: str)
        If blocked is True, the command must not be executed.
    """
    cmd_lower = command.lower() if _IS_WINDOWS else command

    # Check path blocklist
    for blocked_path in _BLOCKLIST:
        check_path = blocked_path if _IS_WINDOWS else blocked_path
        if check_path in cmd_lower:
            return True, f"Command touches protected OS path: {blocked_path}"

    # Check dangerous patterns
    for pattern in _DANGEROUS_RE:
        if pattern.search(command):
            return True, f"Command matches dangerous pattern: {pattern.pattern}"

    return False, ""


def check_path_injection(env: dict | None) -> tuple[bool, str]:
    """
    Check if an environment dict tries to override PATH.

    The LLM cannot override env.PATH. On init, the MCP server captures
    the user's login shell PATH and uses that. This prevents a
    prompt-injected command from prepending a malicious binary.

    Returns:
        (injected: bool, reason: str)
    """
    if env is None:
        return False, ""

    if "PATH" in env or "Path" in env or "path" in env:
        return True, "PATH override rejected — cannot modify system PATH"

    return False, ""
