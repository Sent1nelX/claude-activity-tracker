#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# Claude Code Activity Tracker — Installer
# https://github.com/Sent1nelX/claude-activity-tracker
# ============================================================

PLUGIN_DIR="$HOME/.claude-activity"
SETTINGS_FILE="$HOME/.claude/settings.json"
SKILLS_DIR="$HOME/.claude/skills"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

info()    { echo -e "${CYAN}[info]${RESET}  $*"; }
success() { echo -e "${GREEN}[ok]${RESET}    $*"; }
warn()    { echo -e "${YELLOW}[warn]${RESET}  $*"; }
error()   { echo -e "${RED}[error]${RESET} $*" >&2; exit 1; }

echo -e "${BOLD}"
echo "  ╔══════════════════════════════════════════╗"
echo "  ║   Claude Code Activity Tracker           ║"
echo "  ║   github.com/Sent1nelX/claude-activity-tracker ║"
echo "  ╚══════════════════════════════════════════╝"
echo -e "${RESET}"

# ── 1. Prerequisites ────────────────────────────────────────
info "Checking prerequisites..."

command -v python3 >/dev/null 2>&1 || error "python3 is required but not found."
command -v claude  >/dev/null 2>&1 || error "'claude' CLI is required. Install Claude Code first."

PYTHON_VER=$(python3 -c "import sys; print(sys.version_info[:2] >= (3, 8))")
[ "$PYTHON_VER" = "True" ] || error "Python 3.8+ required."

success "Prerequisites OK"

# ── 2. Create plugin directory ───────────────────────────────
info "Creating plugin directory at $PLUGIN_DIR ..."
mkdir -p "$PLUGIN_DIR/hooks" "$PLUGIN_DIR/src"

# ── 3. Copy files ────────────────────────────────────────────
info "Copying plugin files..."

if [ -d "$SCRIPT_DIR/hooks" ]; then
    cp -r "$SCRIPT_DIR/hooks/." "$PLUGIN_DIR/hooks/"
    success "Copied hooks/"
else
    warn "hooks/ directory not found in $SCRIPT_DIR — skipping"
fi

if [ -d "$SCRIPT_DIR/src" ]; then
    cp -r "$SCRIPT_DIR/src/." "$PLUGIN_DIR/src/"
    success "Copied src/"
else
    warn "src/ directory not found in $SCRIPT_DIR — skipping"
fi

# ── 4. Make hook scripts executable ─────────────────────────
info "Setting executable permissions on hook scripts..."
find "$PLUGIN_DIR/hooks" -name "*.py" -exec chmod +x {} \;
success "Hook scripts are executable"

# ── 5. Install Python dependencies ──────────────────────────
info "Installing Python dependencies (mcp)..."

if pip3 install mcp --break-system-packages --quiet 2>/dev/null; then
    success "mcp installed (--break-system-packages)"
elif pip3 install mcp --quiet 2>/dev/null; then
    success "mcp installed"
else
    warn "pip3 install failed. Trying pip..."
    if pip install mcp --break-system-packages --quiet 2>/dev/null || pip install mcp --quiet 2>/dev/null; then
        success "mcp installed via pip"
    else
        warn "Could not install mcp automatically. Run: pip3 install mcp"
    fi
fi

# ── 6. Register MCP server ───────────────────────────────────
info "Registering MCP server with Claude Code..."
if claude mcp add activity-tracker -- python3 "$PLUGIN_DIR/src/server.py" 2>/dev/null; then
    success "MCP server registered: activity-tracker"
else
    warn "MCP server may already be registered, or 'claude mcp add' failed."
    warn "If needed, run manually:"
    warn "  claude mcp add activity-tracker -- python3 $PLUGIN_DIR/src/server.py"
fi

# ── 7. Update settings.json ──────────────────────────────────
info "Updating Claude Code settings.json ..."

mkdir -p "$(dirname "$SETTINGS_FILE")"

python3 - <<PYEOF
import json, os, sys

settings_file = os.path.expanduser("~/.claude/settings.json")
plugin_dir    = os.path.expanduser("~/.claude-activity")

# Load existing settings (or start fresh)
if os.path.exists(settings_file):
    try:
        with open(settings_file, "r") as f:
            settings = json.load(f)
    except json.JSONDecodeError:
        print("[warn]  settings.json was not valid JSON — creating a fresh one")
        settings = {}
else:
    settings = {}

hooks = settings.setdefault("hooks", {})

def ensure_hook(event, command):
    """Add command to hook list if not already present."""
    existing = hooks.get(event, [])
    # Hooks can be stored as a list of commands or a list of hook objects
    cmd_str = json.dumps(command)
    for entry in existing:
        if isinstance(entry, dict) and json.dumps(entry.get("command")) == cmd_str:
            return  # already registered
        if isinstance(entry, list) and json.dumps(entry) == cmd_str:
            return  # already registered
    existing.append({"command": command})
    hooks[event] = existing

ensure_hook("SessionStart", ["python3", f"{plugin_dir}/hooks/session_start.py"])
ensure_hook("PreToolUse",   ["python3", f"{plugin_dir}/hooks/pre_tool_use.py"])
ensure_hook("Stop",         ["python3", f"{plugin_dir}/hooks/session_end.py"])

with open(settings_file, "w") as f:
    json.dump(settings, f, indent=2)

print(f"[ok]    settings.json updated: {settings_file}")
PYEOF

# ── 8. Install skill file ────────────────────────────────────
info "Installing skill file..."

mkdir -p "$SKILLS_DIR"

if [ -f "$SCRIPT_DIR/skills/activity.md" ]; then
    cp "$SCRIPT_DIR/skills/activity.md" "$SKILLS_DIR/activity.md"
    success "Skill installed: $SKILLS_DIR/activity.md"
else
    warn "skills/activity.md not found — skipping skill installation"
fi

# ── Done ─────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}  Installation complete!${RESET}"
echo ""
echo -e "  ${BOLD}Usage:${RESET}"
echo -e "    Type ${CYAN}/activity${RESET} in any Claude Code session to see your stats"
echo ""
echo -e "  ${BOLD}Available MCP tools:${RESET}"
echo -e "    ${CYAN}activity_stats${RESET}   — today's session summary"
echo -e "    ${CYAN}activity_report${RESET}  — weekly activity report"
echo -e "    ${CYAN}activity_tools${RESET}   — most-used tools breakdown"
echo -e "    ${CYAN}activity_files${RESET}   — most-edited files"
echo ""
echo -e "  ${BOLD}Data location:${RESET} $PLUGIN_DIR/activity.db"
echo ""
echo -e "  Restart Claude Code for hooks to take effect."
echo ""
