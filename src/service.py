#!/usr/bin/env python3
"""
claude-activity-tracker — unified daemon.

Runs two servers in one process:
  1. HTTP on 127.0.0.1:8765  — receives hook events from Claude Code
  2. MCP stdio                — serves metrics to Claude Code as an MCP tool provider

Usage:
    python3 src/service.py          # foreground
    python3 src/service.py --daemon # background (writes PID to ~/.claude-activity/service.pid)

Hook endpoints:
    POST /event   body: {"type": "session_start"|"pre_tool_use"|"post_tool_use"|"session_end"|"user_turn", ...}
    GET  /health  → {"status": "ok", "sessions": N}
    GET  /stats   → JSON stats for today
    GET  /dashboard → HTML dashboard (or JSON stats if dashboard.py absent)

MCP is served on stdin/stdout when --mcp flag is passed (used by claude mcp add).
"""

import argparse
import json
import os
import subprocess
import sys
import time
import threading
import sqlite3
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

# ── paths ─────────────────────────────────────────────────────────────────────
_ACTIVITY_DIR = Path.home() / ".claude-activity"
_DB_PATH = Path(os.environ.get("ACTIVITY_DB_PATH", str(_ACTIVITY_DIR / "activity.db")))
_PID_FILE = _ACTIVITY_DIR / "service.pid"
_SESSION_FILE = _ACTIVITY_DIR / "current_session"
_LAST_TOOL_TS = _ACTIVITY_DIR / "last_tool_ts"
_HTTP_PORT = int(os.environ.get("ACTIVITY_PORT", "8765"))

_SRC_DIR = Path(__file__).parent
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

import db as _db
import server as _mcp_tools  # reuse all tool functions from server.py


# ── HTTP hook receiver ─────────────────────────────────────────────────────────

class HookHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # suppress default access log

    def _send(self, code: int, body: dict):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/health":
            conn = _db.init_db(_DB_PATH)
            n = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
            self._send(200, {"status": "ok", "sessions": n})
        elif self.path.startswith("/stats"):
            stats = _db.get_stats(days=1, db_path=_DB_PATH)
            self._send(200, stats)
        elif self.path == "/dashboard":
            stats = _db.get_stats(days=1, db_path=_DB_PATH)
            try:
                from dashboard import get_dashboard_html
                patterns = _db.get_patterns(days=7, db_path=_DB_PATH)
                daily = _db.get_daily_breakdown(days=7, db_path=_DB_PATH)
                files = _db.get_recent_files(limit=10, db_path=_DB_PATH)
                html = get_dashboard_html(stats, patterns, daily, files)
                data = html.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            except ImportError:
                self._send(200, stats)
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/event":
            self._send(404, {"error": "not found"})
            return

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            payload = json.loads(body)
        except Exception:
            self._send(400, {"error": "invalid JSON"})
            return

        try:
            _handle_event(payload)
            self._send(200, {"ok": True})
        except Exception as e:
            self._send(500, {"error": str(e)})


def _handle_event(payload: dict):
    event_type = payload.get("type", "")
    ts = int(payload.get("ts", time.time()))

    if event_type == "session_start":
        session_id = payload.get("session_id", "")
        project = payload.get("project", "")
        if session_id:
            _db.start_session(session_id, project=project, ts=ts, db_path=_DB_PATH)
            _SESSION_FILE.write_text(session_id)
            # Detect git branch and log it as a separate event
            git_branch = ""
            if project:
                try:
                    result = subprocess.run(
                        ["git", "-C", project, "rev-parse", "--abbrev-ref", "HEAD"],
                        capture_output=True, text=True, timeout=3
                    )
                    git_branch = result.stdout.strip()
                except Exception:
                    git_branch = ""
            if git_branch:
                _db.log_event(session_id, ts, "GitBranch", git_branch, "", project, _DB_PATH)

    elif event_type == "pre_tool_use":
        session_id = _read_session()
        if session_id:
            tool_name = payload.get("tool_name", "")
            file_path = payload.get("file_path", "")
            project = payload.get("project", os.getcwd())
            _db.log_event(session_id, ts, "PreToolUse", tool_name, file_path, project, _DB_PATH)
            # Detect new user request via time gap
            try:
                last_ts = int(_LAST_TOOL_TS.read_text().strip())
            except Exception:
                last_ts = 0
            if ts - last_ts > 30:
                _db.log_event(session_id, ts, "UserTurn", db_path=_DB_PATH)
            _LAST_TOOL_TS.write_text(str(ts))

    elif event_type == "post_tool_use":
        session_id = _read_session()
        if session_id:
            tool_name = payload.get("tool_name", "")
            file_path = payload.get("file_path", "")
            project = payload.get("project", os.getcwd())
            _db.log_event(session_id, ts, "PostToolUse", tool_name, file_path, project, _DB_PATH)

    elif event_type == "session_end":
        session_id = _read_session()
        if session_id:
            _db.end_session(session_id, ts=ts, db_path=_DB_PATH)
            try:
                _SESSION_FILE.unlink()
            except FileNotFoundError:
                pass


def _read_session() -> str | None:
    try:
        v = _SESSION_FILE.read_text().strip()
        return v or None
    except Exception:
        return None


def _run_http():
    server = HTTPServer(("127.0.0.1", _HTTP_PORT), HookHandler)
    server.serve_forever()


# ── MCP stdio server ──────────────────────────────────────────────────────────

def _run_mcp():
    """Serve MCP protocol on stdio (called when --mcp flag passed)."""
    # Reuse the minimal JSON-RPC implementation from server.py
    _mcp_tools._db.init_db(_DB_PATH)
    _mcp_tools._run_minimal_jsonrpc()


# ── daemon mode ───────────────────────────────────────────────────────────────

def _daemonize():
    if os.fork() > 0:
        sys.exit(0)
    os.setsid()
    if os.fork() > 0:
        sys.exit(0)
    sys.stdout.flush()
    sys.stderr.flush()
    with open(os.devnull, "w") as dev_null:
        os.dup2(dev_null.fileno(), sys.stdin.fileno())
        os.dup2(dev_null.fileno(), sys.stdout.fileno())
        os.dup2(dev_null.fileno(), sys.stderr.fileno())
    _PID_FILE.write_text(str(os.getpid()))


# ── entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="claude-activity-tracker service")
    parser.add_argument("--daemon", action="store_true", help="Run in background")
    parser.add_argument("--mcp", action="store_true", help="Serve MCP on stdio (for claude mcp add)")
    parser.add_argument("--stop", action="store_true", help="Stop the running daemon")
    parser.add_argument("--status", action="store_true", help="Show daemon status")
    args = parser.parse_args()

    if args.stop:
        try:
            pid = int(_PID_FILE.read_text().strip())
            os.kill(pid, 15)
            _PID_FILE.unlink(missing_ok=True)
            print(f"Stopped (PID {pid})")
        except Exception as e:
            print(f"Could not stop: {e}")
        return

    if args.status:
        try:
            pid = int(_PID_FILE.read_text().strip())
            os.kill(pid, 0)  # check if alive
            print(f"Running (PID {pid}), HTTP on :{_HTTP_PORT}")
        except Exception:
            print("Not running")
        return

    if args.mcp:
        _run_mcp()
        return

    _ACTIVITY_DIR.mkdir(parents=True, exist_ok=True)
    _db.init_db(_DB_PATH)

    if args.daemon:
        _daemonize()

    print(f"claude-activity-tracker service — HTTP on 127.0.0.1:{_HTTP_PORT}")
    _run_http()


if __name__ == "__main__":
    main()
