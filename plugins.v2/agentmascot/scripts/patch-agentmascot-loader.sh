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

if grep -q "$MARKER_START" "$INDEX_PATH"; then
  echo "AgentMascot loader patch already exists: $INDEX_PATH"
  exit 0
fi

BACKUP_PATH="$INDEX_PATH.agentmascot.$(date +%Y%m%d%H%M%S).bak"
cp "$INDEX_PATH" "$BACKUP_PATH"

python3 - "$INDEX_PATH" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
content = path.read_text(encoding="utf-8")
snippet = """<!-- AgentMascot global loader start -->
<script type="module">
  let agentMascotLoaderStarted = false;
  const agentMascotLooksLikeJwt = value => typeof value === "string" && /^eyJ[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]+$/.test(value.trim());
  const agentMascotPickToken = (value, depth = 0) => {
    if (!value || depth > 5) return "";
    if (agentMascotLooksLikeJwt(value)) return value.trim();
    if (typeof value === "string") {
      try { return agentMascotPickToken(JSON.parse(value), depth + 1); } catch { return ""; }
    }
    if (Array.isArray(value)) {
      for (const item of value) {
        const token = agentMascotPickToken(item, depth + 1);
        if (token) return token;
      }
      return "";
    }
    if (typeof value !== "object") return "";
    for (const key of ["access_token", "accessToken", "token", "jwt", "id_token"]) {
      const token = agentMascotPickToken(value[key], depth + 1);
      if (token) return token;
    }
    for (const key of ["state", "user", "auth", "data"]) {
      const token = agentMascotPickToken(value[key], depth + 1);
      if (token) return token;
    }
    for (const item of Object.values(value)) {
      const token = agentMascotPickToken(item, depth + 1);
      if (token) return token;
    }
    return "";
  };
  const agentMascotReadStorageToken = area => {
    try {
      if (!area) return "";
      for (const key of ["auth", "user", "userStore", "authStore", "moviepilot-auth"]) {
        const token = agentMascotPickToken(area.getItem(key));
        if (token) return token;
      }
      for (let index = 0; index < area.length; index += 1) {
        const token = agentMascotPickToken(area.getItem(area.key(index)));
        if (token) return token;
      }
    } catch {}
    return "";
  };
  const agentMascotToken = () => agentMascotReadStorageToken(window.localStorage) || agentMascotReadStorageToken(window.sessionStorage);
  const agentMascotImportCode = code => {
    const blobUrl = URL.createObjectURL(new Blob([String(code)], { type: "application/javascript" }));
    return import(blobUrl).finally(() => URL.revokeObjectURL(blobUrl));
  };
  const startAgentMascotLoader = async () => {
    if (agentMascotLoaderStarted) return;
    agentMascotLoaderStarted = true;
    try {
      const token = agentMascotToken();
      if (token) {
        window.__AgentMascotAccessToken = token;
        try {
          const response = await fetch("/api/v1/plugin/AgentMascot/loader", {
            headers: { Authorization: `Bearer ${token}` },
            credentials: "same-origin",
            cache: "no-store",
          });
          if (!response.ok) throw new Error(`loader api ${response.status}`);
          await agentMascotImportCode(await response.text());
          return;
        } catch (apiError) {
          console.debug("[AgentMascot] loader api failed, trying static file", apiError);
        }
      }
      await import("/api/v1/plugin/file/agentmascot/dist/assets/agentmascot-loader.js?agentmascot=0.1.10");
    } catch (error) {
      agentMascotLoaderStarted = false;
      console.debug("[AgentMascot] loader skipped", error);
    }
  };
  const agentMascotLoaderTimer = window.setInterval(() => {
    startAgentMascotLoader();
    if (agentMascotLoaderStarted) window.clearInterval(agentMascotLoaderTimer);
  }, 1000);
  window.setTimeout(() => window.clearInterval(agentMascotLoaderTimer), 30000);
  startAgentMascotLoader();
</script>
<!-- AgentMascot global loader end -->"""

if "</head>" in content:
    content = content.replace("</head>", snippet + "\n</head>", 1)
elif "</body>" in content:
    content = content.replace("</body>", snippet + "\n</body>", 1)
else:
    content = content + "\n" + snippet + "\n"

path.write_text(content, encoding="utf-8")
PY

echo "AgentMascot loader patch installed: $INDEX_PATH"
echo "Backup: $BACKUP_PATH"
