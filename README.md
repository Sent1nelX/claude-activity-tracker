# Claude Code Activity Tracker

![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue?logo=python&logoColor=white)
![License: MIT](https://img.shields.io/badge/license-MIT-green)
![Claude Code](https://img.shields.io/badge/Claude%20Code-plugin-orange?logo=anthropic&logoColor=white)

A lightweight, privacy-respecting plugin for [Claude Code](https://claude.ai/code) that automatically tracks your AI-assisted development activity — sessions, tool calls, files edited, and time spent — and surfaces it through a simple `/activity` command. All data stays on your machine, in a local SQLite database.

---

## Features

- **Automatic session tracking** — hooks into Claude Code start/stop events, no manual logging
- **Tool usage analytics** — see which MCP tools and Claude Code built-ins you reach for most
- **File edit heatmap** — discover which files you iterate on most across sessions
- **Daily & weekly reports** — instant summaries via the `/activity` skill command
- **MCP-native** — exposes metrics through a local MCP server so Claude can reason about your data
- **Zero cloud dependency** — SQLite on disk, nothing transmitted anywhere
- **Privacy-first** — records file paths and tool names only; never captures prompts or code content

---

## Installation

```bash
git clone https://github.com/Sent1nelX/claude-activity-tracker.git
cd claude-activity-tracker
./install.sh
```

Then restart Claude Code. The tracker is active immediately in your next session.

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

The plugin registers an `activity-tracker` MCP server with four tools you can call directly or reference in prompts:

| Tool | Description |
|------|-------------|
| `activity_stats` | Today's session summary — duration, tool calls, files edited |
| `activity_report` | Multi-day report (default: 7 days). Accepts `{ "days": N }` |
| `activity_tools` | Full breakdown of tool call counts for any date range |
| `activity_files` | Most-edited files ranked by edit count |

---

## Architecture

```
Claude Code session
       │
       ├── SessionStart hook
       │       └── hooks/session_start.py  ──┐
       │                                      │
       ├── PreToolUse hook                    ▼
       │       └── hooks/pre_tool_use.py ─► SQLite (~/.claude-activity/activity.db)
       │                                      ▲
       └── Stop hook                          │
               └── hooks/session_end.py  ─────┘
                                              │
                                    src/server.py (MCP)
                                              │
                                        Claude Code
                                    (activity_stats, etc.)
```

Hook scripts write events to SQLite as they happen. The MCP server reads from the same database to answer queries — no network involved.

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

## Roadmap

- [ ] **GitHub integration** — correlate activity with commits and PRs
- [ ] **Plane integration** — link sessions to Plane issues and sprints
- [ ] **Web dashboard** — local FastAPI + React view with charts
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
