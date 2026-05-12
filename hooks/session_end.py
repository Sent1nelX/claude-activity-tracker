#!/usr/bin/env python3
"""
Claude Code Stop hook.

Reads the current session id from ~/.claude-activity/current_session and
marks the session as ended in the SQLite database.

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


def _read_session_id() -> str | None:
    try:
        text = _SESSION_FILE.read_text().strip()
        return text if text else None
    except Exception:
        return None


def main() -> None:
    try:
        # Consume stdin even if we don't need it (keeps the hook contract clean).
        sys.stdin.read()
    except Exception:
        pass

    try:
        session_id = _read_session_id()
        if session_id:
            import db as _db
            _db.end_session(session_id, ts=int(time.time()), db_path=_DB_PATH)

            # Remove the session file so stale ids don't leak into the next session.
            try:
                _SESSION_FILE.unlink(missing_ok=True)
            except Exception:
                pass
    except Exception:
        pass

    sys.stdout.write(_RESPONSE_OK + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
