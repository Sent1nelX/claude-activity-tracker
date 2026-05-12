#!/usr/bin/env python3
"""
Claude Code PreToolUse hook.

Reads JSON from stdin with fields:
  tool_name   – name of the tool about to be called
  tool_input  – dict of the tool's arguments

Extracts a file path from the tool input (checks common key names),
reads the current session id from ~/.claude-activity/current_session,
and logs the event to the database.

Always exits with {"continue": true} so Claude Code is never blocked.
"""

import json
import os
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_ACTIVITY_DIR = Path.home() / ".claude-activity"
_SESSION_FILE = _ACTIVITY_DIR / "current_session"
_DEFAULT_DB = _ACTIVITY_DIR / "activity.db"
_DB_PATH = Path(os.environ.get("ACTIVITY_DB_PATH", str(_DEFAULT_DB)))

_HOOKS_DIR = Path(__file__).parent
_SRC_DIR = _HOOKS_DIR.parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

_RESPONSE_OK = json.dumps({"continue": True, "suppressOutput": True})

# Keys to inspect (in priority order) when looking for a file path.
_FILE_KEYS = ("file_path", "path", "notebook_path", "output_file")

# Keys whose value may contain a leading filename embedded in a shell command.
_COMMAND_KEYS = ("command",)


def _extract_file_path(tool_input: dict) -> str:
    """Return the best-guess file path from a tool_input dict."""
    if not isinstance(tool_input, dict):
        return ""

    # Direct path keys.
    for key in _FILE_KEYS:
        val = tool_input.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()

    # Try to pull the first token from a shell command (rough heuristic).
    for key in _COMMAND_KEYS:
        val = tool_input.get(key)
        if isinstance(val, str) and val.strip():
            first_token = val.strip().split()[0]
            # Only use it when it looks like a file path (contains / or .).
            if "/" in first_token or "." in first_token:
                return first_token

    return ""


def _read_session_id() -> str | None:
    try:
        text = _SESSION_FILE.read_text().strip()
        return text if text else None
    except Exception:
        return None


def main() -> None:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:
        payload = {}

    try:
        tool_name = payload.get("tool_name", "")
        tool_input = payload.get("tool_input", {})
        file_path = _extract_file_path(tool_input)
        project = os.getcwd()
        ts = int(time.time())

        session_id = _read_session_id()
        if session_id:
            import db as _db
            _db.log_event(
                session_id=session_id,
                ts=ts,
                event_type="PreToolUse",
                tool_name=tool_name,
                file_path=file_path,
                project=project,
                db_path=_DB_PATH,
            )
    except Exception:
        pass

    sys.stdout.write(_RESPONSE_OK + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
