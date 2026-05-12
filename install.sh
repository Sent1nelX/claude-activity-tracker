#!/usr/bin/env bash
# Claude Code Activity Tracker — one-command installer
#
# Quick install (no git clone needed):
#   curl -fsSL https://raw.githubusercontent.com/Sent1nelX/claude-activity-tracker/main/install.sh | bash
#
# Or from a local clone:
#   ./install.sh
set -euo pipefail

REPO="https://github.com/Sent1nelX/claude-activity-tracker"
RAW="https://raw.githubusercontent.com/Sent1nelX/claude-activity-tracker/main"
PLUGIN_DIR="$HOME/.claude-activity"
SETTINGS_FILE="$HOME/.claude/settings.json"
SKILLS_DIR="$HOME/.claude/skills"
PORT="${ACTIVITY_PORT:-8765}"

# ── colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'
info()    { echo -e "${CYAN}[info]${RESET}  $*"; }
ok()      { echo -e "${GREEN}[ok]${RESET}    $*"; }
warn()    { echo -e "${YELLOW}[warn]${RESET}  $*"; }
die()     { echo -e "${RED}[error]${RESET} $*" >&2; exit 1; }

echo -e "${BOLD}"
echo "  ╔═══════════════════════════════════════════╗"
echo "  ║   Claude Code Activity Tracker            ║"
echo "  ║   $REPO  ║"
echo "  ╚═══════════════════════════════════════════╝"
echo -e "${RESET}"

# ── 1. check prerequisites ───────────────────────────────────────────────────
info "Checking prerequisites..."
command -v python3 >/dev/null 2>&1 || die "python3 not found. Install it first."
command -v curl    >/dev/null 2>&1 || die "curl not found. Install it first."
PY_OK=$(python3 -c "import sys; print(sys.version_info[:2] >= (3, 8))")
[ "$PY_OK" = "True" ] || die "Python 3.8+ required (found $(python3 --version))."
ok "Prerequisites OK"

# ── 2. download files ────────────────────────────────────────────────────────
info "Downloading plugin files..."
mkdir -p "$PLUGIN_DIR/src" "$PLUGIN_DIR/hooks"

# Determine source: local clone or remote GitHub
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-install.sh}")" 2>/dev/null && pwd || echo "")"
USE_LOCAL=false
[ -f "$SCRIPT_DIR/src/service.py" ] && USE_LOCAL=true

_get() {
  local dest="$1" src_path="$2"
  if $USE_LOCAL; then
    cp "$SCRIPT_DIR/$src_path" "$dest"
  else
    curl -fsSL "$RAW/$src_path" -o "$dest"
  fi
}

_get "$PLUGIN_DIR/src/service.py"   "src/service.py"
_get "$PLUGIN_DIR/src/server.py"    "src/server.py"
_get "$PLUGIN_DIR/src/db.py"        "src/db.py"
_get "$PLUGIN_DIR/src/dashboard.py" "src/dashboard.py"
_get "$PLUGIN_DIR/hooks/session_start.sh"  "hooks/session_start.sh"
_get "$PLUGIN_DIR/hooks/pre_tool_use.sh"   "hooks/pre_tool_use.sh"
_get "$PLUGIN_DIR/hooks/post_tool_use.sh"  "hooks/post_tool_use.sh"
_get "$PLUGIN_DIR/hooks/session_end.sh"    "hooks/session_end.sh"

chmod +x "$PLUGIN_DIR/hooks/"*.sh
ok "Files downloaded to $PLUGIN_DIR"

# ── 3. install MCP deps (optional — server works without mcp package) ────────
info "Installing mcp package (optional)..."
pip3 install mcp --break-system-packages -q 2>/dev/null \
  || pip3 install mcp -q 2>/dev/null \
  || warn "Could not install mcp via pip — built-in JSON-RPC server will be used instead."

# ── 4. register MCP server with Claude Code ──────────────────────────────────
info "Registering MCP server..."
if command -v claude >/dev/null 2>&1; then
  claude mcp remove activity-tracker --scope user 2>/dev/null || true
  claude mcp add --scope user activity-tracker -- python3 "$PLUGIN_DIR/src/service.py" --mcp 2>/dev/null \
    && ok "MCP server registered: activity-tracker (user scope)" \
    || warn "claude mcp add failed — run manually: claude mcp add --scope user activity-tracker -- python3 $PLUGIN_DIR/src/service.py --mcp"
else
  warn "'claude' CLI not in PATH — skipping MCP registration. Run this after installing Claude Code:"
  warn "  claude mcp add activity-tracker -- python3 $PLUGIN_DIR/src/service.py --mcp"
fi

# ── 5. update Claude Code settings.json (hooks) ──────────────────────────────
info "Configuring hooks in settings.json..."
mkdir -p "$(dirname "$SETTINGS_FILE")"

python3 - <<PYEOF
import json, os

sf   = os.path.expanduser("~/.claude/settings.json")
hdir = os.path.expanduser("~/.claude-activity/hooks")

settings = {}
if os.path.exists(sf):
    try:
        with open(sf) as f:
            settings = json.load(f)
    except Exception:
        pass

hooks = settings.setdefault("hooks", {})

def set_hook(event, cmd):
    entry = {"matcher": "", "hooks": [{"type": "command", "command": cmd}]}
    existing = hooks.get(event, [])
    # replace any previous activity-tracker hook for this event
    cleaned = [e for e in existing if "claude-activity" not in json.dumps(e)]
    cleaned.append(entry)
    hooks[event] = cleaned

set_hook("SessionStart", f"bash {hdir}/session_start.sh")
set_hook("PreToolUse",   f"bash {hdir}/pre_tool_use.sh")
set_hook("PostToolUse",  f"bash {hdir}/post_tool_use.sh")
set_hook("Stop",         f"bash {hdir}/session_end.sh")

with open(sf, "w") as f:
    json.dump(settings, f, indent=2)
print(f"  settings.json updated")
PYEOF
ok "Hooks configured"

# ── 6. install /activity skill ────────────────────────────────────────────────
mkdir -p "$SKILLS_DIR"
if $USE_LOCAL && [ -f "$SCRIPT_DIR/skills/activity.md" ]; then
  cp "$SCRIPT_DIR/skills/activity.md" "$SKILLS_DIR/activity.md"
elif ! $USE_LOCAL; then
  curl -fsSL "$RAW/skills/activity.md" -o "$SKILLS_DIR/activity.md" 2>/dev/null || true
fi
[ -f "$SKILLS_DIR/activity.md" ] && ok "Skill /activity installed" || warn "Skill not installed"

# ── 7. start the background service ──────────────────────────────────────────
info "Starting background service on port $PORT..."
pkill -f "service.py" 2>/dev/null || true
sleep 0.3
ACTIVITY_PORT=$PORT python3 "$PLUGIN_DIR/src/service.py" --daemon
sleep 0.8

if curl -sf "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then
  ok "Service running on http://127.0.0.1:$PORT"
else
  warn "Service did not start — run manually: python3 $PLUGIN_DIR/src/service.py --daemon"
fi

# ── 8. auto-start on shell login ─────────────────────────────────────────────
AUTOSTART_LINE="python3 \$HOME/.claude-activity/src/service.py --daemon 2>/dev/null &"
for RC in "$HOME/.bashrc" "$HOME/.zshrc" "$HOME/.profile"; do
  if [ -f "$RC" ] && ! grep -q "claude-activity" "$RC" 2>/dev/null; then
    echo "" >> "$RC"
    echo "# claude-activity-tracker — auto-start" >> "$RC"
    echo "$AUTOSTART_LINE" >> "$RC"
    ok "Auto-start added to $RC"
    break
  fi
done

# ── done ─────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}  ✅ Installation complete!${RESET}"
echo ""
echo -e "  ${BOLD}Quick start:${RESET}"
echo -e "    Restart Claude Code, then type ${CYAN}/activity${RESET}"
echo ""
echo -e "  ${BOLD}MCP tools available:${RESET}"
echo -e "    ${CYAN}activity_stats${RESET}    — today's summary"
echo -e "    ${CYAN}activity_patterns${RESET} — peak hours & task types"
echo -e "    ${CYAN}activity_github${RESET}   — AI sessions vs git commits"
echo -e "    ${CYAN}activity_report${RESET}   — weekly report"
echo -e "    ${CYAN}activity_export${RESET}   — JSON/webhook export"
echo ""
echo -e "  ${BOLD}Service management:${RESET}"
echo -e "    python3 ~/.claude-activity/src/service.py --status"
echo -e "    python3 ~/.claude-activity/src/service.py --stop"
echo ""
echo -e "  ${BOLD}One-line install for next time:${RESET}"
echo -e "    ${CYAN}curl -fsSL $RAW/install.sh | bash${RESET}"
echo ""
