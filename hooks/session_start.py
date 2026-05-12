#!/usr/bin/env python3
"""
Claude Code SessionStart hook.

Reads JSON from stdin (contains 'cwd' for the project path).
Generates a session UUID, persists it to ~/.claude-activity/current_session,
and records the session in the SQLite database.

Always exits with {"continue": true} so Claude Code is never blocked.
"""

import json
import os
import sys
import time
import uuid
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_ACTIVITY_DIR = Path.home() / ".claude-activity"
_SESSION_FILE = _ACTIVITY_DIR / "current_session"
_DEFAULT_DB = _ACTIVITY_DIR / "activity.db"
_DB_PATH = Path(os.environ.get("ACTIVITY_DB_PATH", str(_DEFAULT_DB)))

# Make the db module importable when this hook is run directly.
_HOOKS_DIR = Path(__file__).parent
_SRC_DIR = _HOOKS_DIR.parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

_RESPONSE_OK = json.dumps({"continue": True, "suppressOutput": True})


def _write_ok() -> None:
    sys.stdout.write(_RESPONSE_OK + "\n")
    sys.stdout.flush()


def main() -> None:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:
        payload = {}

    try:
        project = payload.get("cwd", os.getcwd())
        session_id = str(uuid.uuid4())
        ts = int(time.time())

        # Persist session id for downstream hooks.
        _ACTIVITY_DIR.mkdir(parents=True, exist_ok=True)
        _SESSION_FILE.write_text(session_id)

        import db as _db
        _db.start_session(session_id, project=project, ts=ts, db_path=_DB_PATH)
    except Exception:
        # DB failure must not block Claude Code.
        pass

    _write_ok()


if __name__ == "__main__":
    main()
