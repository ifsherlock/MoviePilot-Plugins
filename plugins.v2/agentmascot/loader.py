import re
from pathlib import Path

from fastapi.responses import Response

from app.log import logger


LOADER_FILENAME = "agentmascot-loader.js"
JAVASCRIPT_MEDIA_TYPE = "application/javascript; charset=utf-8"
RELATIVE_IMPORT_RE = re.compile(
    r"^import\s+\{(?P<imports>[^}]+)\}\s+from\s+'\.\/(?P<path>[^']+)';\s*",
    flags=re.M,
)
EXPORT_RE = re.compile(r"\n?export\s+\{(?P<exports>[^}]+)\};?\s*$", flags=re.S)


def _parse_export_mappings(spec: str) -> dict[str, str]:
    mappings: dict[str, str] = {}
    for part in spec.split(","):
        item = part.strip()
        if not item:
            continue
        if " as " in item:
            source, target = item.split(" as ", 1)
            mappings[target.strip()] = source.strip()
        else:
            mappings[item] = item
    return mappings


def _parse_import_mappings(spec: str) -> dict[str, str]:
    mappings: dict[str, str] = {}
    for part in spec.split(","):
        item = part.strip()
        if not item:
            continue
        if " as " in item:
            source, target = item.split(" as ", 1)
            mappings[source.strip()] = target.strip()
        else:
            mappings[item] = item
    return mappings


def _inline_imported_chunk(dist_dir: Path, import_match: re.Match) -> str:
    chunk_path = dist_dir / import_match.group("path")
    chunk_code = chunk_path.read_text(encoding="utf-8")
    export_match = EXPORT_RE.search(chunk_code)
    export_mappings = _parse_export_mappings(export_match.group("exports")) if export_match else {}
    chunk_code = EXPORT_RE.sub("", chunk_code)

    aliases: list[str] = []
    for imported_name, local_name in _parse_import_mappings(import_match.group("imports")).items():
        source_name = export_mappings.get(imported_name, imported_name)
        if source_name != local_name:
            aliases.append(f"const {local_name} = {source_name};")

    if aliases:
        return f"{chunk_code}\n{chr(10).join(aliases)}"
    return chunk_code


def build_loader_code(plugin_root: Path) -> str:
    dist_dir = plugin_root / "dist" / "assets"
    loader_path = dist_dir / LOADER_FILENAME
    loader_code = loader_path.read_text(encoding="utf-8")
    import_matches = list(RELATIVE_IMPORT_RE.finditer(loader_code))
    if not import_matches:
        return loader_code

    chunks = [_inline_imported_chunk(dist_dir, match) for match in import_matches]
    loader_code = RELATIVE_IMPORT_RE.sub("", loader_code)
    return f"{chr(10).join(chunks)}\n{loader_code}"


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
