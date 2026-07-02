import re
from pathlib import Path

from fastapi.responses import Response

from app.log import logger


LOADER_FILENAME = "agentmascot-loader.js"
JAVASCRIPT_MEDIA_TYPE = "application/javascript; charset=utf-8"


def build_loader_code(plugin_root: Path) -> str:
    dist_dir = plugin_root / "dist" / "assets"
    loader_path = dist_dir / LOADER_FILENAME
    loader_code = loader_path.read_text(encoding="utf-8")
    match = re.search(r"^import\s+\{([^}]+)\}\s+from\s+'\.\/([^']+)';\s*", loader_code)
    if not match:
        return loader_code

    provider_path = dist_dir / match.group(2)
    provider_code = provider_path.read_text(encoding="utf-8")
    provider_code = re.sub(r"\n?export\s+\{[^}]+\};?\s*$", "", provider_code, flags=re.S)
    loader_code = loader_code[match.end():]
    return (
        f"{provider_code}\n"
        "const unwrapResponse = u;\n"
        "const DEFAULT_CONFIG = D;\n"
        "const SHIMEJI_ACTIONS = S;\n"
        f"{loader_code}"
    )


def build_loader_response(plugin_root: Path) -> Response:
    try:
        return Response(
            content=build_loader_code(plugin_root),
            media_type=JAVASCRIPT_MEDIA_TYPE,
            headers={"Cache-Control": "no-store"},
        )
    except Exception as err:
        logger.error(f"获取 Agent 桌宠全局入口脚本失败: {err}")
        return Response(
            content=f"console.error('AgentMascot loader failed: {str(err)}');",
            media_type=JAVASCRIPT_MEDIA_TYPE,
            status_code=500,
        )
