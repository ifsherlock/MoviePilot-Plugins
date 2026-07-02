param(
  [string]$FrontendRoot = "/public"
)

$ErrorActionPreference = "Stop"
$markerStart = "<!-- AgentMascot global loader start -->"
$markerEnd = "<!-- AgentMascot global loader end -->"
$snippetBody = @'
<script type="module">
  let agentMascotLoaderStarted = false;
  const agentMascotLooksLikeJwt = value => typeof value === "string" && /^eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$/.test(value.trim());
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
'@
$snippet = "$markerStart`n$snippetBody`n$markerEnd"

$indexPath = Join-Path $FrontendRoot "index.html"
if (!(Test-Path -LiteralPath $indexPath)) {
  throw "MoviePilot frontend index.html not found: $indexPath"
}

$content = Get-Content -LiteralPath $indexPath -Raw
if ($content.Contains($markerStart)) {
  Write-Host "AgentMascot loader patch already exists: $indexPath"
  exit 0
}

$backupPath = "$indexPath.agentmascot.$(Get-Date -Format 'yyyyMMddHHmmss').bak"
Copy-Item -LiteralPath $indexPath -Destination $backupPath

if ($content -match "</head>") {
  $content = $content -replace "</head>", "$snippet`n</head>"
} elseif ($content -match "</body>") {
  $content = $content -replace "</body>", "$snippet`n</body>"
} else {
  $content = "$content`n$snippet`n"
}

Set-Content -LiteralPath $indexPath -Value $content -Encoding UTF8
Write-Host "AgentMascot loader patch installed: $indexPath"
Write-Host "Backup: $backupPath"
