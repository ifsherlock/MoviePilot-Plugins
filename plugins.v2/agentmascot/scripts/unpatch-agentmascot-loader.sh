#!/bin/sh
set -eu

FRONTEND_ROOT="${1:-/public}"
INDEX_PATH="$FRONTEND_ROOT/index.html"
MARKER_START="<!-- AgentMascot global loader start -->"
MARKER_END="<!-- AgentMascot global loader end -->"

if [ ! -f "$INDEX_PATH" ]; then
  echo "MoviePilot frontend index.html not found: $INDEX_PATH" >&2
  exit 1
fi

if ! grep -q "$MARKER_START" "$INDEX_PATH"; then
  echo "AgentMascot loader patch not found: $INDEX_PATH"
  exit 0
fi

BACKUP_PATH="$INDEX_PATH.agentmascot-unpatch.$(date +%Y%m%d%H%M%S).bak"
cp "$INDEX_PATH" "$BACKUP_PATH"

python3 - "$INDEX_PATH" <<'PY'
from pathlib import Path
import re
import sys

path = Path(sys.argv[1])
content = path.read_text(encoding="utf-8")
pattern = re.compile(
    r"\s*<!-- AgentMascot global loader start -->.*?<!-- AgentMascot global loader end -->\s*",
    re.S,
)
path.write_text(pattern.sub("\n", content, count=1), encoding="utf-8")
PY

echo "AgentMascot loader patch removed: $INDEX_PATH"
echo "Backup: $BACKUP_PATH"
