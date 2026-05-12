#!/usr/bin/env bash
# Claude Code Stop hook — delegates to unified service via HTTP
TS=$(date +%s)
curl -sf -X POST http://127.0.0.1:8765/event \
     -H "Content-Type: application/json" \
     -d "{\"type\":\"session_end\",\"ts\":$TS}" \
     > /dev/null 2>&1 || true
echo '{"continue": true, "suppressOutput": true}'
