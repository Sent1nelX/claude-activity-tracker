# Claude Code Activity Tracker

![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue?logo=python&logoColor=white)
![License: MIT](https://img.shields.io/badge/license-MIT-green)
![Claude Code](https://img.shields.io/badge/Claude%20Code-plugin-orange?logo=anthropic&logoColor=white)

A lightweight, privacy-respecting plugin for [Claude Code](https://claude.ai/code) that automatically tracks your AI-assisted development activity — sessions, tool calls, files edited, and time spent — and surfaces it through a simple `/activity` command. All data stays on your machine, in a local SQLite database.

---

## Quick Install

```bash
curl -fsSL https://raw.githubusercontent.com/Sent1nelX/claude-activity-tracker/main/install.sh | bash
```

That's it. The installer will:
- Download all plugin files to `~/.claude-activity/`
- Register the MCP server with Claude Code
- Configure hooks (SessionStart, PreToolUse, Stop)
- Start the background service automatically
- Add auto-start to your shell profile

Then **restart Claude Code** and type `/activity`.

> **Requirements:** Python 3.8+, `curl`

---

## Features

- **Automatic session tracking** — hooks into Claude Code start/stop events, no manual logging
- **Tool usage analytics** — see which MCP tools and Claude Code built-ins you reach for most
- **File edit heatmap** — discover which files you iterate on most across sessions
- **GitHub correlation** — compare AI sessions against actual git commits
- **Peak hour analysis** — discover when you're most productive
- **Daily & weekly reports** — instant summaries via the `/activity` skill command
- **MCP-native** — exposes metrics through a local MCP server so Claude can reason about your data
- **Zero cloud dependency** — SQLite on disk, nothing transmitted anywhere
- **Privacy-first** — records file paths and tool names only; never captures prompts or code content

---

## Manual Installation

If you prefer to inspect before running:

```bash
git clone https://github.com/Sent1nelX/claude-activity-tracker.git
cd claude-activity-tracker
./install.sh
```

> **Requirements:** Python 3.8+, Claude Code CLI (`claude`)

---

## Usage

### /activity command

Type `/activity` in any Claude Code session:

```
/activity
```

Claude will fetch today's stats from the local MCP server and display a formatted report:

```
📊 Today's Activity — 2026-05-12

| Metric       | Value    |
|--------------|----------|
| Sessions     | 3        |
| Active time  | 94 min   |
| Tool calls   | 47       |
| Files edited | 12       |

🔧 Top Tools
| Tool    | Calls |
|---------|-------|
| Edit    | 18    |
| Read    | 14    |
| Bash    | 9     |

📁 Top Files
| File              | Edits |
|-------------------|-------|
| src/server.py     | 7     |
| hooks/pre_tool.py | 4     |
```

For a weekly view: `/activity week`

### MCP Tools

The plugin registers an `activity-tracker` MCP server with tools you can call directly or reference in prompts:

| Tool | Description |
|------|-------------|
| `activity_stats` | Today's session summary — duration, tool calls, files edited |
| `activity_session` | Details for a specific session |
| `activity_files` | Most-edited files ranked by edit count |
| `activity_patterns` | Peak hours, day-of-week heatmap, task type breakdown |
| `activity_github` | Correlate AI sessions with git commits (efficiency ratio) |
| `activity_report` | Multi-day report (default: 7 days). Accepts `{ "days": N }` |
| `activity_export` | Export data as JSON or POST to a webhook |

---

## Architecture

```
Claude Code session
       │
       ├── SessionStart hook ─── hooks/session_start.sh ─┐
       │                                                   │  HTTP POST
       ├── PreToolUse hook ───── hooks/pre_tool_use.sh ───► 127.0.0.1:8765
       │                                                   │  (service.py daemon)
       └── Stop hook ─────────── hooks/session_end.sh  ───┘
                                                           │
                                                    SQLite (~/.claude-activity/activity.db)
                                                           │
                                              service.py --mcp (stdio)
                                                           │
                                                     Claude Code
                                              (activity_stats, activity_github, …)
```

A single unified daemon (`service.py`) runs two servers in one process:
- **HTTP :8765** — receives events from lightweight bash hooks via `curl`
- **MCP stdio** — answers tool queries from Claude Code (started via `claude mcp add`)

---

## Data Collected

The tracker records only the minimum needed for productivity metrics:

| What is recorded | Example |
|-----------------|---------|
| Session start/end timestamps | `2026-05-12 09:14:32` |
| Tool name invoked | `Edit`, `Bash`, `Read` |
| File path of edited files | `/home/user/project/src/app.py` |
| Session duration | `47 minutes` |

**What is never recorded:**
- Prompt or message text
- Code content or file contents
- API keys or environment variables
- Terminal output

All data lives in `~/.claude-activity/activity.db` and never leaves your machine.

---

## Service Management

```bash
# Check status
python3 ~/.claude-activity/src/service.py --status

# Stop daemon
python3 ~/.claude-activity/src/service.py --stop

# Restart
python3 ~/.claude-activity/src/service.py --daemon
```

---

## Roadmap

- [ ] **Plane integration** — link sessions to Plane issues and sprints
- [ ] **Web dashboard** — local FastAPI + React view with charts
- [ ] **VSCode extension** — sidebar panel with live metrics
- [ ] **Team aggregation** — opt-in anonymized team stats
- [ ] **Goal tracking** — daily coding time targets with progress bars

---

## Contributing

Pull requests are welcome. For significant changes, please open an issue first.

```bash
# Development setup
git clone https://github.com/Sent1nelX/claude-activity-tracker.git
cd claude-activity-tracker
pip3 install -r requirements.txt
```

---

## License

[MIT](LICENSE) — free to use, modify, and distribute.
