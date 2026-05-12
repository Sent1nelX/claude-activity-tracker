# Contributing to claude-activity-tracker

Thanks for wanting to improve claude-activity-tracker! Here's how to get started.

## Quick Start

```bash
git clone https://github.com/Sent1nelX/claude-activity-tracker
cd claude-activity-tracker
python3 -m venv .venv && source .venv/bin/activate
pip install mcp
```

Run locally (foreground mode for debugging):
```bash
python3 src/service.py
```

## Project Structure

```
src/
  service.py     — unified daemon: HTTP hook receiver + MCP entry point
  server.py      — MCP tool implementations + JSON-RPC server
  db.py          — SQLite schema and query helpers
  dashboard.py   — HTML dashboard rendered via /dashboard endpoint
hooks/
  session_start.sh  — reads Claude's session_id from stdin, posts to daemon
  pre_tool_use.sh   — posts tool name + file path to daemon
  post_tool_use.sh  — posts tool completion to daemon
  session_end.sh    — signals session end to daemon
skills/
  activity.md    — /activity Claude Code skill
install.sh       — one-command installer (curl | bash)
```

## Development Workflow

1. Fork the repo and create a branch: `git checkout -b feat/my-feature`
2. Make your changes
3. Test manually with `python3 src/service.py` and a few MCP tool calls
4. Run the installer to validate end-to-end: `./install.sh`
5. Open a PR against `main`

## Adding a New MCP Tool

1. Add `tool_activity_<name>()` function in `src/server.py`
2. Add entry to `TOOLS_SCHEMA` list in `src/server.py`
3. Add entry to `_TOOL_DISPATCH` dict in `src/server.py`
4. Add `@mcp.tool()` wrapper in `_try_fastmcp()` in `src/server.py`
5. Mention it in `README.md` MCP Tools table

## Bug Reports

Open a GitHub issue with:
- OS and Python version
- Steps to reproduce
- What you expected vs what happened
- Relevant output from `python3 src/service.py` (foreground mode)

## Code Style

- Python: standard library only (no extra deps required)
- Bash: `set -euo pipefail`, quote all variables
- Keep files under 500 lines where possible
- No comments that just restate what the code does

## License

By contributing you agree your changes will be licensed under the MIT License.
