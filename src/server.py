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
    lines = [_fmt_report(stats_n, stats_1)]
    try:
        daily = _db.get_daily_breakdown(days=days, db_path=DB_PATH)
        if daily:
            lines.append("📅 Daily breakdown:")
            for d in daily:
                lines.append(f"  {d['date']}  sessions:{d['sessions']}  tools:{d['tools']}  {d['active_minutes']}min")
    except AttributeError:
        pass
    return "\n".join(lines)


def tool_activity_patterns(days: int = 7) -> str:
    """Usage patterns: peak hours, days, task types inferred from tools."""
    patterns = _db.get_patterns(days=days, db_path=DB_PATH)

    lines = [f"🧠 Usage Patterns — last {days} day(s)", ""]

    # Peak hours
    by_hour = patterns["by_hour"]
    if by_hour:
        peak = max(by_hour, key=lambda x: x["count"])
        lines.append(f"⏰ Peak hour: {peak['hour']:02d}:00  ({peak['count']} tool calls)")
        # ASCII mini-chart
        max_cnt = max(h["count"] for h in by_hour)
        lines.append("")
        lines.append("   Hour  Activity")
        for h in by_hour:
            bar = "█" * max(1, round(h["count"] / max_cnt * 20))
            lines.append(f"   {h['hour']:02d}:00  {bar} {h['count']}")
        lines.append("")

    # Day of week
    by_dow = patterns["by_dow"]
    if by_dow:
        peak_day = max(by_dow, key=lambda x: x["count"])
        lines.append(f"📅 Most active day: {peak_day['day']}  ({peak_day['count']} tool calls)")
        for d in by_dow:
            bar = "█" * max(1, round(d["count"] / max(x["count"] for x in by_dow) * 15))
            lines.append(f"   {d['day']}  {bar} {d['count']}")
        lines.append("")

    # Task type inference
    lines.append("🎯 Primary task types detected:")
    for t in patterns["task_types"]:
        lines.append(f"   • {t}")

    return "\n".join(lines)


def tool_activity_github(project_path: str = ".", days: int = 7) -> str:
    """Correlate Claude Code sessions with git commits in the project."""
    import subprocess
    lines = [f"🔗 GitHub Correlation — last {days} days", ""]

    # Claude stats
    stats = _db.get_stats(days=days, db_path=DB_PATH)
    lines.append(f"Claude Code activity:")
    lines.append(f"  Sessions   : {stats['total_sessions']}")
    lines.append(f"  Tool calls : {stats['total_tools']}")
    lines.append(f"  Active time: {stats['active_time_minutes']} min")
    lines.append("")

    # Git commits
    try:
        result = subprocess.run(
            ["git", "-C", project_path, "log",
             f"--since={days} days ago", "--oneline"],
            capture_output=True, text=True, timeout=10
        )
        commits = [l for l in result.stdout.strip().splitlines() if l]
        commit_count = len(commits)

        result2 = subprocess.run(
            ["git", "-C", project_path, "log",
             f"--since={days} days ago",
             "--pretty=format:", "--numstat"],
            capture_output=True, text=True, timeout=10
        )
        lines_added = lines_removed = 0
        for line in result2.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) == 3:
                try:
                    lines_added += int(parts[0])
                    lines_removed += int(parts[1])
                except ValueError:
                    pass

        lines.append(f"Git activity (in {project_path}):")
        lines.append(f"  Commits    : {commit_count}")
        lines.append(f"  Lines added: +{lines_added}")
        lines.append(f"  Lines removed: -{lines_removed}")
        lines.append("")

        if stats["total_sessions"] > 0 and commit_count > 0:
            ratio = round(commit_count / stats["total_sessions"], 2)
            lines.append(f"📊 Efficiency ratio: {ratio} commits per AI session")
            if ratio > 1:
                lines.append("   ✅ High code output relative to AI usage")
            elif ratio > 0.3:
                lines.append("   📈 Moderate output — typical for complex tasks")
            else:
                lines.append("   🔍 Low commit ratio — exploration/research phase?")
        elif commit_count == 0:
            lines.append("ℹ️  No commits found in this period.")
        else:
            lines.append("ℹ️  No Claude sessions recorded yet.")

        if commits:
            lines.append("")
            lines.append("Recent commits:")
            for c in commits[:5]:
                lines.append(f"  • {c}")

    except FileNotFoundError:
        lines.append("⚠️  git not found in PATH.")
    except subprocess.TimeoutExpired:
        lines.append("⚠️  git command timed out.")
    except Exception as e:
        lines.append(f"⚠️  Could not read git log: {e}")

    return "\n".join(lines)


def tool_activity_vscode(days: int = 7) -> str:
    """Correlate Claude Code sessions with VSCode activity."""
    # Call _db.get_vscode_correlation() if it exists, otherwise return helpful message
    try:
        result = _db.get_vscode_correlation(days=days, db_path=DB_PATH)
    except AttributeError:
        return "VSCode correlation not yet available. Update to latest version."

    lines = [f"💻 VSCode Correlation — last {days} days", ""]
    if not result.get("vscode_installed"):
        lines.append("VSCode/VSCodium not detected on this system.")
        return "\n".join(lines)

    shared = result.get("shared_projects", [])
    vsc = result.get("vscode_projects", [])

    lines.append(f"VSCode projects open: {len(vsc)}")
    lines.append(f"Projects active in both Claude + VSCode: {len(shared)}")
    if shared:
        lines.append("")
        lines.append("Shared projects:")
        for p in shared[:10]:
            lines.append(f"  • {p}")
    if vsc and not shared:
        lines.append("")
        lines.append("VSCode projects (no Claude overlap):")
        for p in vsc[:5]:
            lines.append(f"  • {p}")
    return "\n".join(lines)


def tool_activity_plane(workspace_url: str = "", api_key: str = "") -> str:
    """Show Plane integration status and instructions, or fetch issues if configured."""
    config_file = Path.home() / ".claude-activity" / "config.json"

    # Try to load config if no args provided
    if not workspace_url or not api_key:
        try:
            import json as _json
            cfg = _json.loads(config_file.read_text())
            workspace_url = cfg.get("plane_workspace_url", "")
            api_key = cfg.get("plane_api_key", "")
        except Exception:
            pass

    if not workspace_url or not api_key:
        return (
            "Plane integration not configured.\n\n"
            "To set up:\n"
            "1. Get your API key from Plane → Settings → API Tokens\n"
            "2. Run this to save config:\n\n"
            "   python3 -c \"\n"
            "   import json; from pathlib import Path\n"
            "   cfg = {'plane_workspace_url': 'https://app.plane.so/YOUR_WORKSPACE', 'plane_api_key': 'YOUR_KEY'}\n"
            "   (Path.home()/'.claude-activity'/'config.json').write_text(json.dumps(cfg))\n"
            "   \"\n\n"
            "3. Then call: activity_plane()"
        )

    # Fetch projects then issues from Plane API
    import urllib.request, urllib.error, json as _json

    def _plane_get(path: str) -> dict:
        req = urllib.request.Request(
            f"https://api.plane.so/api/v1{path}",
            headers={"X-Api-Key": api_key, "Accept": "application/json",
                     "User-Agent": "claude-activity-tracker/2.0"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return _json.loads(resp.read())

    try:
        workspace_slug = workspace_url.rstrip("/").split("/")[-1]
        projects = _plane_get(f"/workspaces/{workspace_slug}/projects/")
        project_list = projects.get("results", projects) if isinstance(projects, dict) else projects

        lines = [f"✈️  Plane — {workspace_slug}", f"Projects: {len(project_list)}", ""]
        for proj in project_list[:5]:
            pid = proj.get("id", "")
            pname = proj.get("name", "?")
            try:
                issues_data = _plane_get(f"/workspaces/{workspace_slug}/projects/{pid}/issues/?per_page=10")
                issues = issues_data.get("results", [])
                total = issues_data.get("total_count", len(issues))
                lines.append(f"📁 {pname} ({total} issues)")
                for issue in issues[:10]:
                    state = issue.get("state_detail", {}).get("name", "—")
                    lines.append(f"   [{state}] {issue.get('name', 'Untitled')}")
                lines.append("")
            except Exception:
                lines.append(f"📁 {pname}")
        return "\n".join(lines)
    except Exception as e:
        return f"Plane API error: {e}\nCheck your workspace URL and API key."


def tool_activity_export(webhook_url: str = "", days: int = 7) -> str:
    """Export activity data as JSON, optionally POST to a webhook URL."""
    import json as _json

    stats = _db.get_stats(days=days, db_path=DB_PATH)
    patterns = _db.get_patterns(days=days, db_path=DB_PATH)
    files = _db.get_recent_files(limit=20, db_path=DB_PATH)

    payload = {
        "source": "claude-activity-tracker",
        "exported_at": int(time.time()),
        "period_days": days,
        "stats": stats,
        "patterns": {
            "task_types": patterns["task_types"],
            "peak_hour": max(patterns["by_hour"], key=lambda x: x["count"])["hour"] if patterns["by_hour"] else None,
            "peak_day": max(patterns["by_dow"], key=lambda x: x["count"])["day"] if patterns["by_dow"] else None,
        },
        "top_files": files[:10],
    }

    if webhook_url:
        import urllib.request
        import urllib.error
        body = _json.dumps(payload).encode()
        req = urllib.request.Request(
            webhook_url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return f"✅ Data exported to {webhook_url}\nHTTP {resp.status}\n\nPayload:\n{_json.dumps(payload, indent=2)}"
        except urllib.error.URLError as e:
            return f"❌ Export failed: {e}\n\nPayload (not sent):\n{_json.dumps(payload, indent=2)}"
    else:
        return f"📤 Export payload (add webhook_url to POST):\n\n{_json.dumps(payload, indent=2)}"


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
    {
        "name": "activity_patterns",
        "description": "Analyse usage patterns: peak hours, days, inferred task types.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "Window in days (default 7)", "default": 7}
            },
        },
    },
    {
        "name": "activity_github",
        "description": "Correlate Claude Code sessions with git commits — AI sessions vs code output ratio.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_path": {"type": "string", "description": "Path to git repo (default '.')", "default": "."},
                "days": {"type": "integer", "description": "Window in days (default 7)", "default": 7}
            },
        },
    },
    {
        "name": "activity_export",
        "description": "Export activity data as JSON or POST to a webhook URL (Plane, custom tracker, etc).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "webhook_url": {"type": "string", "description": "URL to POST data to (optional)"},
                "days": {"type": "integer", "description": "Window in days (default 7)", "default": 7}
            },
        },
    },
    {
        "name": "activity_vscode",
        "description": "Correlate Claude Code sessions with VSCode activity — shared projects and overlap.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "Window in days (default 7)", "default": 7}
            },
        },
    },
    {
        "name": "activity_plane",
        "description": "Show Plane integration status and instructions, or fetch open issues if configured.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workspace_url": {"type": "string", "description": "Plane workspace URL (optional if saved in config)"},
                "api_key": {"type": "string", "description": "Plane API key (optional if saved in config)"}
            },
        },
    },
]

_TOOL_DISPATCH = {
    "activity_stats":    lambda args: tool_activity_stats(days=int(args.get("days", 1))),
    "activity_session":  lambda args: tool_activity_session(session_id=args["session_id"]),
    "activity_files":    lambda args: tool_activity_files(limit=int(args.get("limit", 10))),
    "activity_report":   lambda args: tool_activity_report(days=int(args.get("days", 7))),
    "activity_patterns": lambda args: tool_activity_patterns(days=int(args.get("days", 7))),
    "activity_github":   lambda args: tool_activity_github(
        project_path=args.get("project_path", "."),
        days=int(args.get("days", 7)),
    ),
    "activity_export":   lambda args: tool_activity_export(
        webhook_url=args.get("webhook_url", ""),
        days=int(args.get("days", 7)),
    ),
    "activity_vscode":   lambda args: tool_activity_vscode(days=int(args.get("days", 7))),
    "activity_plane":    lambda args: tool_activity_plane(
        workspace_url=args.get("workspace_url", ""),
        api_key=args.get("api_key", ""),
    ),
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

    @mcp.tool()
    def activity_patterns(days: int = 7) -> str:
        """Analyse usage patterns: peak hours, days, inferred task types."""
        return tool_activity_patterns(days=days)

    @mcp.tool()
    def activity_github(project_path: str = ".", days: int = 7) -> str:
        """Correlate Claude Code sessions with git commits."""
        return tool_activity_github(project_path=project_path, days=days)

    @mcp.tool()
    def activity_export(webhook_url: str = "", days: int = 7) -> str:
        """Export activity data as JSON or POST to a webhook URL."""
        return tool_activity_export(webhook_url=webhook_url, days=days)

    @mcp.tool()
    def activity_vscode(days: int = 7) -> str:
        """Correlate Claude Code sessions with VSCode activity."""
        return tool_activity_vscode(days=days)

    @mcp.tool()
    def activity_plane(workspace_url: str = "", api_key: str = "") -> str:
        """Show Plane integration status and instructions, or fetch issues if configured."""
        return tool_activity_plane(workspace_url=workspace_url, api_key=api_key)

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
