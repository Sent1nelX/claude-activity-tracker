"""
MCP server for Claude Code activity tracker.

Run with:
    python3 src/server.py

Reads DB_PATH from env var ACTIVITY_DB_PATH, defaulting to
~/.claude-activity/activity.db.
"""

import os
import sys
import json
import time
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# DB path resolution
# ---------------------------------------------------------------------------
_DEFAULT_DB = Path.home() / ".claude-activity" / "activity.db"
DB_PATH = Path(os.environ.get("ACTIVITY_DB_PATH", str(_DEFAULT_DB)))

# Add the project src dir to path so `db` is importable when running from any cwd.
_SRC_DIR = Path(__file__).parent
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

import db as _db


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _fmt_ts(ts: int | None) -> str:
    if ts is None:
        return "—"
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _fmt_stats(stats: dict, days: int) -> str:
    lines = [
        f"📊 Activity — last {days} day(s)",
        f"",
        f"🖥️  Sessions      : {stats['total_sessions']}",
        f"🔧 Tool calls    : {stats['total_tools']}",
        f"💬 Requests      : {stats['total_requests']}",
        f"⏱️  Active time   : {stats['active_time_minutes']} min",
        "",
    ]
    if stats["top_tools"]:
        lines.append("🔝 Top tools:")
        for entry in stats["top_tools"]:
            lines.append(f"   {entry['tool']:<30} {entry['count']:>5}x")
        lines.append("")
    if stats["top_files"]:
        lines.append("📁 Top files:")
        for entry in stats["top_files"]:
            lines.append(f"   {entry['file']:<50} {entry['count']:>5}x")
    return "\n".join(lines)


def _fmt_session(info: dict) -> str:
    status = "active" if info["ended_at"] is None else "ended"
    lines = [
        f"🖥️  Session {info['id'][:8]}… [{status}]",
        f"   Project   : {info['project'] or '—'}",
        f"   Started   : {_fmt_ts(info['started_at'])}",
        f"   Ended     : {_fmt_ts(info['ended_at'])}",
        f"   Duration  : {info['duration_minutes']} min",
        f"   Tools     : {info['total_tools']}",
        f"   Requests  : {info['total_requests']}",
    ]
    if info["files_touched"]:
        lines.append(f"   Files ({len(info['files_touched'])}):")
        for f in info["files_touched"][:20]:
            lines.append(f"     • {f}")
    return "\n".join(lines)


def _fmt_files(files: list[dict]) -> str:
    if not files:
        return "No file activity recorded yet."
    lines = ["📁 Recently edited files:", ""]
    for entry in files:
        ts_str = _fmt_ts(entry["last_edited"])
        lines.append(f"  {entry['file']}")
        lines.append(f"    edits: {entry['edit_count']}  last: {ts_str}")
    return "\n".join(lines)


def _fmt_report(stats7: dict, stats1: dict) -> str:
    pct_tools = (
        round(stats1["total_tools"] / stats7["total_tools"] * 100)
        if stats7["total_tools"] else 0
    )
    lines = [
        "📈 Weekly Report",
        "",
        f"Past 7 days:",
        f"  Sessions  : {stats7['total_sessions']}",
        f"  Tool calls: {stats7['total_tools']}",
        f"  Requests  : {stats7['total_requests']}",
        f"  Active    : {stats7['active_time_minutes']} min",
        "",
        f"Past 24 hours (% of week):",
        f"  Tool calls: {stats1['total_tools']} ({pct_tools}% of week)",
        "",
    ]
    if stats7["top_tools"]:
        lines.append("🔝 Most-used tools this week:")
        for entry in stats7["top_tools"][:5]:
            lines.append(f"   {entry['tool']:<30} {entry['count']:>5}x")
        lines.append("")
    if stats7["top_files"]:
        lines.append("📁 Most-touched files this week:")
        for entry in stats7["top_files"][:5]:
            lines.append(f"   {entry['file']}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool implementations (pure functions — easy to test)
# ---------------------------------------------------------------------------

def tool_activity_stats(days: int = 1) -> str:
    stats = _db.get_stats(days=days, db_path=DB_PATH)
    return _fmt_stats(stats, days)


def tool_activity_session(session_id: str) -> str:
    info = _db.get_current_session(session_id, db_path=DB_PATH)
    if info is None:
        return f"Session '{session_id}' not found."
    return _fmt_session(info)


def tool_activity_files(limit: int = 10) -> str:
    files = _db.get_recent_files(limit=limit, db_path=DB_PATH)
    return _fmt_files(files)


def tool_activity_report(days: int = 7) -> str:
    stats_n = _db.get_stats(days=days, db_path=DB_PATH)
    stats_1 = _db.get_stats(days=1, db_path=DB_PATH)
    return _fmt_report(stats_n, stats_1)


# ---------------------------------------------------------------------------
# MCP server — try FastMCP first, fall back to minimal stdio JSON-RPC
# ---------------------------------------------------------------------------

TOOLS_SCHEMA = [
    {
        "name": "activity_stats",
        "description": "Get activity statistics for the last N days.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "Number of days to look back (default 1)", "default": 1}
            },
        },
    },
    {
        "name": "activity_session",
        "description": "Get details for a specific session by ID.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Session UUID"}
            },
            "required": ["session_id"],
        },
    },
    {
        "name": "activity_files",
        "description": "List the most recently edited files.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max files to return (default 10)", "default": 10}
            },
        },
    },
    {
        "name": "activity_report",
        "description": "Weekly activity summary with trends.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "Window in days (default 7)", "default": 7}
            },
        },
    },
]

_TOOL_DISPATCH = {
    "activity_stats": lambda args: tool_activity_stats(days=int(args.get("days", 1))),
    "activity_session": lambda args: tool_activity_session(session_id=args["session_id"]),
    "activity_files": lambda args: tool_activity_files(limit=int(args.get("limit", 10))),
    "activity_report": lambda args: tool_activity_report(days=int(args.get("days", 7))),
}


def _try_fastmcp() -> bool:
    """Attempt to start the server with FastMCP. Returns True if successful."""
    try:
        from mcp.server.fastmcp import FastMCP  # type: ignore
    except ImportError:
        return False

    mcp = FastMCP("claude-activity-tracker")

    @mcp.tool()
    def activity_stats(days: int = 1) -> str:
        """Get activity statistics for the last N days."""
        return tool_activity_stats(days=days)

    @mcp.tool()
    def activity_session(session_id: str) -> str:
        """Get details for a specific session by ID."""
        return tool_activity_session(session_id=session_id)

    @mcp.tool()
    def activity_files(limit: int = 10) -> str:
        """List the most recently edited files."""
        return tool_activity_files(limit=limit)

    @mcp.tool()
    def activity_report(days: int = 7) -> str:
        """Weekly activity summary with trends."""
        return tool_activity_report(days=days)

    mcp.run()
    return True  # unreachable after mcp.run() blocks, but satisfies type checker


def _run_minimal_jsonrpc() -> None:
    """
    Minimal stdio JSON-RPC 2.0 server implementing the MCP protocol
    (initialize, tools/list, tools/call).
    """

    def _send(obj: dict) -> None:
        line = json.dumps(obj)
        sys.stdout.write(line + "\n")
        sys.stdout.flush()

    def _error(req_id, code: int, message: str) -> dict:
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}

    for raw_line in sys.stdin:
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        try:
            req = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            _send(_error(None, -32700, f"Parse error: {exc}"))
            continue

        req_id = req.get("id")
        method = req.get("method", "")
        params = req.get("params") or {}

        if method == "initialize":
            _send({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "claude-activity-tracker", "version": "1.0.0"},
                },
            })

        elif method == "notifications/initialized":
            # No response needed for notifications.
            pass

        elif method == "tools/list":
            _send({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"tools": TOOLS_SCHEMA},
            })

        elif method == "tools/call":
            tool_name = params.get("name", "")
            tool_args = params.get("arguments") or {}
            handler = _TOOL_DISPATCH.get(tool_name)
            if handler is None:
                _send(_error(req_id, -32601, f"Unknown tool: {tool_name}"))
            else:
                try:
                    result_text = handler(tool_args)
                    _send({
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "content": [{"type": "text", "text": result_text}],
                            "isError": False,
                        },
                    })
                except Exception as exc:  # noqa: BLE001
                    _send({
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "content": [{"type": "text", "text": f"Error: {exc}"}],
                            "isError": True,
                        },
                    })

        else:
            # Unknown method — send method-not-found only for requests (have id).
            if req_id is not None:
                _send(_error(req_id, -32601, f"Method not found: {method}"))


if __name__ == "__main__":
    # Ensure the DB is initialised before accepting connections.
    _db.init_db(DB_PATH)

    if not _try_fastmcp():
        # FastMCP not available — use the built-in minimal server.
        _run_minimal_jsonrpc()
