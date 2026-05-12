"""
SQLite database layer for Claude Code activity tracker.
DB path: ~/.claude-activity/activity.db
"""

import sqlite3
import time
from pathlib import Path

DEFAULT_DB_PATH = Path.home() / ".claude-activity" / "activity.db"


def _connect(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Create tables if they don't exist. Returns an open connection."""
    conn = _connect(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            id               TEXT    PRIMARY KEY,
            started_at       INTEGER NOT NULL,
            ended_at         INTEGER,
            project          TEXT    NOT NULL DEFAULT '',
            total_tools      INTEGER NOT NULL DEFAULT 0,
            total_requests   INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id  TEXT    NOT NULL REFERENCES sessions(id),
            ts          INTEGER NOT NULL,
            type        TEXT    NOT NULL,
            tool_name   TEXT    NOT NULL DEFAULT '',
            file_path   TEXT    NOT NULL DEFAULT '',
            project     TEXT    NOT NULL DEFAULT ''
        );

        CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id);
        CREATE INDEX IF NOT EXISTS idx_events_ts      ON events(ts);
        CREATE INDEX IF NOT EXISTS idx_events_type    ON events(type);
        CREATE INDEX IF NOT EXISTS idx_events_file    ON events(file_path);
    """)
    conn.commit()
    return conn


def start_session(session_id: str, project: str, ts: int | None = None,
                  db_path: str | Path = DEFAULT_DB_PATH) -> None:
    """Insert a new session row."""
    ts = ts or int(time.time())
    conn = init_db(db_path)
    with conn:
        conn.execute(
            "INSERT OR IGNORE INTO sessions (id, started_at, project) VALUES (?, ?, ?)",
            (session_id, ts, project),
        )


def end_session(session_id: str, ts: int | None = None,
                db_path: str | Path = DEFAULT_DB_PATH) -> None:
    """Set ended_at on a session."""
    ts = ts or int(time.time())
    conn = init_db(db_path)
    with conn:
        conn.execute(
            "UPDATE sessions SET ended_at = ? WHERE id = ?",
            (ts, session_id),
        )


def log_event(
    session_id: str,
    ts: int | None = None,
    event_type: str = "",
    tool_name: str = "",
    file_path: str = "",
    project: str = "",
    db_path: str | Path = DEFAULT_DB_PATH,
) -> None:
    """Insert an event and increment the appropriate session counter."""
    ts = ts or int(time.time())
    conn = init_db(db_path)
    with conn:
        conn.execute(
            """INSERT INTO events (session_id, ts, type, tool_name, file_path, project)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (session_id, ts, event_type, tool_name, file_path, project),
        )
        # Increment tool count for any tool event; request count for user turns.
        if event_type in ("PreToolUse", "PostToolUse"):
            conn.execute(
                "UPDATE sessions SET total_tools = total_tools + 1 WHERE id = ?",
                (session_id,),
            )
        elif event_type == "UserTurn":
            conn.execute(
                "UPDATE sessions SET total_requests = total_requests + 1 WHERE id = ?",
                (session_id,),
            )
        # Ensure the session row exists (belt-and-suspenders for hook ordering issues).
        conn.execute(
            "INSERT OR IGNORE INTO sessions (id, started_at, project) VALUES (?, ?, ?)",
            (session_id, ts, project),
        )


def get_stats(days: int = 1, db_path: str | Path = DEFAULT_DB_PATH) -> dict:
    """
    Return aggregate stats for the last `days` days.

    Keys:
        total_sessions, total_tools, total_requests,
        top_files     [{file, count}, ...],
        top_tools     [{tool, count}, ...],
        active_time_minutes
    """
    since = int(time.time()) - days * 86_400
    conn = init_db(db_path)

    row = conn.execute(
        """SELECT
               COUNT(DISTINCT id)            AS total_sessions,
               SUM(total_tools)              AS total_tools,
               SUM(total_requests)           AS total_requests,
               SUM(COALESCE(ended_at, strftime('%s','now')) - started_at) AS raw_seconds
           FROM sessions
           WHERE started_at >= ?""",
        (since,),
    ).fetchone()

    total_sessions = row["total_sessions"] or 0
    total_tools = row["total_tools"] or 0
    total_requests = row["total_requests"] or 0
    active_time_minutes = round((row["raw_seconds"] or 0) / 60, 1)

    top_files = [
        {"file": r["file_path"], "count": r["cnt"]}
        for r in conn.execute(
            """SELECT file_path, COUNT(*) AS cnt
               FROM events
               WHERE ts >= ? AND file_path != ''
               GROUP BY file_path
               ORDER BY cnt DESC
               LIMIT 10""",
            (since,),
        ).fetchall()
    ]

    top_tools = [
        {"tool": r["tool_name"], "count": r["cnt"]}
        for r in conn.execute(
            """SELECT tool_name, COUNT(*) AS cnt
               FROM events
               WHERE ts >= ? AND tool_name != ''
               GROUP BY tool_name
               ORDER BY cnt DESC
               LIMIT 10""",
            (since,),
        ).fetchall()
    ]

    return {
        "total_sessions": total_sessions,
        "total_tools": total_tools,
        "total_requests": total_requests,
        "top_files": top_files,
        "top_tools": top_tools,
        "active_time_minutes": active_time_minutes,
    }


def get_current_session(session_id: str,
                        db_path: str | Path = DEFAULT_DB_PATH) -> dict | None:
    """Return a dict with session info, or None if not found."""
    conn = init_db(db_path)
    row = conn.execute(
        "SELECT * FROM sessions WHERE id = ?", (session_id,)
    ).fetchone()
    if row is None:
        return None

    now = int(time.time())
    ended_at = row["ended_at"] or now
    duration_minutes = round((ended_at - row["started_at"]) / 60, 1)

    # Files touched this session
    files = [
        r["file_path"]
        for r in conn.execute(
            """SELECT DISTINCT file_path FROM events
               WHERE session_id = ? AND file_path != ''
               ORDER BY ts DESC""",
            (session_id,),
        ).fetchall()
    ]

    return {
        "id": row["id"],
        "project": row["project"],
        "started_at": row["started_at"],
        "ended_at": row["ended_at"],
        "duration_minutes": duration_minutes,
        "total_tools": row["total_tools"],
        "total_requests": row["total_requests"],
        "files_touched": files,
    }


def get_recent_files(limit: int = 10,
                     db_path: str | Path = DEFAULT_DB_PATH) -> list[dict]:
    """Return recently edited files with edit counts, most recent first."""
    conn = init_db(db_path)
    rows = conn.execute(
        """SELECT file_path, COUNT(*) AS edit_count, MAX(ts) AS last_edited
           FROM events
           WHERE file_path != ''
           GROUP BY file_path
           ORDER BY last_edited DESC
           LIMIT ?""",
        (limit,),
    ).fetchall()
    return [
        {"file": r["file_path"], "edit_count": r["edit_count"], "last_edited": r["last_edited"]}
        for r in rows
    ]
