"""
Dashboard HTML generator for claude-activity-tracker.

Usage:
    from dashboard import get_dashboard_html
    html = get_dashboard_html(stats, patterns, daily, files)
"""

import json

_CHART_JS_CDN = "https://cdn.jsdelivr.net/npm/chart.js"

_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  background: #0d1117;
  color: #c9d1d9;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
  font-size: 14px;
  padding: 24px;
}
h1 { font-size: 20px; color: #f0f6fc; margin-bottom: 4px; }
.subtitle { color: #8b949e; margin-bottom: 24px; font-size: 13px; }
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}
.card {
  background: #161b22;
  border: 1px solid #30363d;
  border-radius: 8px;
  padding: 16px;
}
.card h2 { font-size: 12px; color: #8b949e; text-transform: uppercase; letter-spacing: .5px; margin-bottom: 8px; }
.stat-value { font-size: 32px; font-weight: 600; color: #f0f6fc; }
.stat-label { font-size: 12px; color: #8b949e; margin-top: 4px; }
.charts-row {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 16px;
  margin-bottom: 24px;
}
.chart-card {
  background: #161b22;
  border: 1px solid #30363d;
  border-radius: 8px;
  padding: 16px;
}
.chart-card h2 { font-size: 13px; color: #8b949e; margin-bottom: 12px; }
.chart-wrap { position: relative; height: 220px; }
.hourly-card {
  background: #161b22;
  border: 1px solid #30363d;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 24px;
}
.hourly-card h2 { font-size: 13px; color: #8b949e; margin-bottom: 12px; }
.hourly-wrap { position: relative; height: 160px; }
.files-card {
  background: #161b22;
  border: 1px solid #30363d;
  border-radius: 8px;
  padding: 16px;
}
.files-card h2 { font-size: 13px; color: #8b949e; margin-bottom: 12px; }
.file-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 0;
  border-bottom: 1px solid #21262d;
  font-size: 12px;
}
.file-row:last-child { border-bottom: none; }
.file-name { color: #58a6ff; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 75%; }
.file-count { color: #8b949e; flex-shrink: 0; }
.task-tags { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 4px; }
.tag {
  background: #1f6feb33;
  border: 1px solid #1f6feb66;
  color: #58a6ff;
  border-radius: 12px;
  padding: 2px 10px;
  font-size: 11px;
}
"""

_CHART_DEFAULTS = """
Chart.defaults.color = '#8b949e';
Chart.defaults.borderColor = '#21262d';
Chart.defaults.font.family = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif";
Chart.defaults.font.size = 11;
"""


def _safe_json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)


def get_dashboard_html(
    stats: dict,
    patterns: dict,
    daily: list,
    files: list,
) -> str:
    """
    Build and return a complete dark-themed HTML dashboard page.

    Args:
        stats:    output of db.get_stats()
        patterns: output of db.get_patterns()
        daily:    output of db.get_daily_breakdown()
        files:    output of db.get_recent_files()
    """
    # ── stat cards ────────────────────────────────────────────────────────────
    stat_cards_html = "".join([
        f'<div class="card"><h2>Sessions</h2>'
        f'<div class="stat-value">{stats.get("total_sessions", 0)}</div>'
        f'<div class="stat-label">today</div></div>',

        f'<div class="card"><h2>Tool Calls</h2>'
        f'<div class="stat-value">{stats.get("total_tools", 0)}</div>'
        f'<div class="stat-label">today</div></div>',

        f'<div class="card"><h2>Requests</h2>'
        f'<div class="stat-value">{stats.get("total_requests", 0)}</div>'
        f'<div class="stat-label">today</div></div>',

        f'<div class="card"><h2>Active Time</h2>'
        f'<div class="stat-value">{stats.get("active_time_minutes", 0)}</div>'
        f'<div class="stat-label">minutes today</div></div>',
    ])

    # ── task type tags ────────────────────────────────────────────────────────
    task_types = patterns.get("task_types", [])
    tags_html = "".join(f'<span class="tag">{t}</span>' for t in task_types)

    # ── recent files table ────────────────────────────────────────────────────
    file_rows_html = ""
    for f in files[:10]:
        name = f.get("file", "")
        short = name.split("/")[-1] if "/" in name else name
        count = f.get("edit_count", 0)
        file_rows_html += (
            f'<div class="file-row">'
            f'<span class="file-name" title="{name}">{short}</span>'
            f'<span class="file-count">{count} edits</span>'
            f'</div>'
        )
    if not file_rows_html:
        file_rows_html = '<div class="file-row"><span style="color:#8b949e">No files yet</span></div>'

    # ── JS data ───────────────────────────────────────────────────────────────
    daily_labels = _safe_json([d.get("date", "") for d in daily])
    daily_sessions = _safe_json([d.get("sessions", 0) for d in daily])
    daily_tools = _safe_json([d.get("tools", 0) for d in daily])
    daily_requests = _safe_json([d.get("requests", 0) for d in daily])

    top_tools = stats.get("top_tools", [])
    tool_labels = _safe_json([t.get("tool", "") for t in top_tools[:8]])
    tool_counts = _safe_json([t.get("count", 0) for t in top_tools[:8]])

    hour_data_raw = {h["hour"]: h["count"] for h in patterns.get("by_hour", [])}
    hour_labels = _safe_json(list(range(24)))
    hour_counts = _safe_json([hour_data_raw.get(h, 0) for h in range(24)])

    js = f"""
{_CHART_DEFAULTS}

// Daily activity bar chart
(function() {{
  const ctx = document.getElementById('dailyChart').getContext('2d');
  new Chart(ctx, {{
    type: 'bar',
    data: {{
      labels: {daily_labels},
      datasets: [
        {{
          label: 'Sessions',
          data: {daily_sessions},
          backgroundColor: '#1f6feb',
          borderRadius: 3,
        }},
        {{
          label: 'Tools',
          data: {daily_tools},
          backgroundColor: '#238636',
          borderRadius: 3,
        }},
        {{
          label: 'Requests',
          data: {daily_requests},
          backgroundColor: '#9e6a03',
          borderRadius: 3,
        }},
      ]
    }},
    options: {{
      responsive: true,
      maintainAspectRatio: false,
      plugins: {{ legend: {{ labels: {{ boxWidth: 10, padding: 12 }} }} }},
      scales: {{
        x: {{ grid: {{ display: false }} }},
        y: {{ beginAtZero: true, grid: {{ color: '#21262d' }} }}
      }}
    }}
  }});
}})();

// Tool usage doughnut
(function() {{
  const ctx = document.getElementById('toolChart').getContext('2d');
  const palette = [
    '#1f6feb','#238636','#9e6a03','#da3633','#8957e5',
    '#2f81f7','#3fb950','#d29922','#f85149','#bc8cff'
  ];
  new Chart(ctx, {{
    type: 'doughnut',
    data: {{
      labels: {tool_labels},
      datasets: [{{
        data: {tool_counts},
        backgroundColor: palette,
        borderWidth: 0,
        hoverOffset: 4,
      }}]
    }},
    options: {{
      responsive: true,
      maintainAspectRatio: false,
      plugins: {{
        legend: {{
          position: 'right',
          labels: {{ boxWidth: 10, padding: 8, font: {{ size: 11 }} }}
        }}
      }}
    }}
  }});
}})();

// Hourly activity line chart
(function() {{
  const ctx = document.getElementById('hourlyChart').getContext('2d');
  new Chart(ctx, {{
    type: 'line',
    data: {{
      labels: {hour_labels},
      datasets: [{{
        label: 'Events',
        data: {hour_counts},
        borderColor: '#58a6ff',
        backgroundColor: 'rgba(88,166,255,0.1)',
        fill: true,
        tension: 0.4,
        pointRadius: 2,
        pointHoverRadius: 4,
      }}]
    }},
    options: {{
      responsive: true,
      maintainAspectRatio: false,
      plugins: {{ legend: {{ display: false }} }},
      scales: {{
        x: {{ grid: {{ display: false }} }},
        y: {{ beginAtZero: true, grid: {{ color: '#21262d' }} }}
      }}
    }}
  }});
}})();
"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Claude Activity Dashboard</title>
<script src="{_CHART_JS_CDN}"></script>
<style>{_CSS}</style>
</head>
<body>
<h1>Claude Activity Dashboard</h1>
<p class="subtitle">Real-time view of your Claude Code activity</p>

<div class="grid">
{stat_cards_html}
</div>

<div class="grid" style="grid-template-columns: 1fr; margin-bottom: 16px;">
  <div class="card">
    <h2>Task Types</h2>
    <div class="task-tags">{tags_html if tags_html else '<span style="color:#8b949e">No data yet</span>'}</div>
  </div>
</div>

<div class="charts-row">
  <div class="chart-card">
    <h2>Daily Activity (last 7 days)</h2>
    <div class="chart-wrap"><canvas id="dailyChart"></canvas></div>
  </div>
  <div class="chart-card">
    <h2>Top Tools</h2>
    <div class="chart-wrap"><canvas id="toolChart"></canvas></div>
  </div>
</div>

<div class="hourly-card">
  <h2>Activity by Hour of Day</h2>
  <div class="hourly-wrap"><canvas id="hourlyChart"></canvas></div>
</div>

<div class="files-card">
  <h2>Recently Edited Files</h2>
  {file_rows_html}
</div>

<script>
{js}
</script>
</body>
</html>"""

    return html
