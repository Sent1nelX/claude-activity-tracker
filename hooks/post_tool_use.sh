#!/usr/bin/env bash
# Claude Code PostToolUse hook — delegates to unified service via HTTP
INPUT=$(cat)
TOOL=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_name',''))" 2>/dev/null || echo "")
FILE=$(echo "$INPUT" | python3 -c "
import sys,json
d=json.load(sys.stdin)
inp=d.get('tool_input',{})
print(inp.get('file_path') or inp.get('path') or inp.get('notebook_path',''))
" 2>/dev/null || echo "")
TS=$(date +%s)
curl -sf -X POST http://127.0.0.1:8765/event \
     -H "Content-Type: application/json" \
     -d "{\"type\":\"post_tool_use\",\"tool_name\":\"$TOOL\",\"file_path\":\"$FILE\",\"project\":\"$(pwd)\",\"ts\":$TS}" \
     > /dev/null 2>&1 || true
echo '{"continue": true, "suppressOutput": true}'
