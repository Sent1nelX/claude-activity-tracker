#!/usr/bin/env bash
# Claude Code SessionStart hook — delegates to unified service via HTTP
SESSION_ID=$(python3 -c "import uuid; print(uuid.uuid4())")
PROJECT=$(pwd)
TS=$(date +%s)
curl -sf -X POST http://127.0.0.1:8765/event \
     -H "Content-Type: application/json" \
     -d "{\"type\":\"session_start\",\"session_id\":\"$SESSION_ID\",\"project\":\"$PROJECT\",\"ts\":$TS}" \
     > /dev/null 2>&1 || true
echo '{"continue": true, "suppressOutput": true}'
