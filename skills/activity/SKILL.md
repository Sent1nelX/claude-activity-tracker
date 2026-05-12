---
name: activity
description: Show Claude Code activity stats — sessions, tools used, files edited, and productivity metrics.
triggers:
  - /activity
  - show my activity
  - show my stats
  - coding stats
  - activity report
  - how much have I coded
  - what did I work on today
  - session summary
  - tool usage stats
  - what files did I edit
  - vscode correlation
  - compare with vscode
  - plane issues
---

# Activity Tracker Skill

Use this skill when the user types `/activity` or asks about their Claude Code usage, coding stats, session summaries, or productivity metrics.

## Instructions

### Step 1 — Fetch today's stats

Call the `activity_stats` MCP tool (server: `activity-tracker`):

```
tool: activity_stats
arguments: {}
```

This returns a JSON object with:
- `date` — today's date
- `session_count` — number of sessions started
- `total_duration_minutes` — total active time
- `tool_calls` — total MCP/tool invocations
- `files_edited` — number of unique files touched
- `top_files` — list of `{path, edits}` objects (up to 10)
- `top_tools` — list of `{tool, calls}` objects (up to 10)

### Step 2 — Format the output

Present results as a clean markdown summary. Use the template below, substituting real values:

```
## 📊 Today's Activity — {date}

| Metric | Value |
|--------|-------|
| Sessions | {session_count} |
| Active time | {total_duration_minutes} min |
| Tool calls | {tool_calls} |
| Files edited | {files_edited} |

### 🔧 Top Tools
| Tool | Calls |
|------|-------|
| {tool} | {calls} |
... (repeat for each entry)

### 📁 Top Files
| File | Edits |
|------|-------|
| {path} | {edits} |
... (repeat for each entry)
```

Shorten file paths to the last 2-3 path segments for readability (e.g. `src/server.py` instead of `/home/user/projects/foo/src/server.py`).

### Step 3 — Offer weekly view (optional)

After showing today's stats, offer: _"Type /activity week for a 7-day report."_

If the user asked for weekly stats (e.g. said "weekly", "this week", "7 days"), call `activity_report` instead:

```
tool: activity_report
arguments: { "days": 7 }
```

Format the weekly report similarly, but add a daily breakdown table:

```
### 📅 Daily Breakdown
| Date | Sessions | Duration | Tools |
|------|----------|----------|-------|
| {date} | {sessions} | {minutes} min | {tools} |
```

### Step 4 — Insight (optional, 1 sentence)

If any single tool accounts for more than 40% of calls, note it:
_"You relied heavily on **{tool}** today — it accounted for {pct}% of all tool calls."_

If total active time exceeds 120 minutes, note:
_"Solid session — over 2 hours of focused work."_

### Step 5 — VSCode correlation (when requested)

If the user asks about VSCode activity, shared projects, or "compare with vscode", call `activity_vscode`:

```
tool: activity_vscode
arguments: { "days": 7 }
```

This returns:
- `vscode_installed` — whether VSCode/VSCodium was detected
- `vscode_projects` — list of recently open VSCode projects
- `shared_projects` — projects active in both Claude Code and VSCode

Present results as a short summary:

```
## 💻 VSCode Correlation — last 7 days

VSCode projects open: {count}
Projects active in both Claude + VSCode: {count}

Shared projects:
  • {project}
```

If VSCode is not detected, note that it was not found on the system.

### Step 6 — Plane issues (when requested)

If the user asks about Plane issues, tasks, or sprints, call `activity_plane`:

```
tool: activity_plane
arguments: {}
```

Optionally pass `workspace_url` and `api_key` if the user provides them explicitly.

The tool returns either:
- Setup instructions (if Plane is not configured) — display them as-is so the user can follow the steps
- A list of open issues with their states — present as a simple list:

```
## ✈️ Plane Issues — {workspace}

Open issues: {total}

  [In Progress] Fix login redirect bug
  [Backlog] Add dark mode
  ...
```

## Error Handling

If the MCP tool returns an error or the database is empty:
- Say: _"No activity recorded yet. The tracker starts collecting data from your next Claude Code session."_
- Do not fabricate numbers.

## Notes

- Data is stored locally in `~/.claude-activity/activity.db` — nothing leaves the machine.
- The tracker records tool names, file paths, and session timestamps. It never records prompt text or code content.
