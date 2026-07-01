from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPO_ROOT / "plugins.v2" / "subtitlemanualupload"
SEARCH_ROOTS = (
    PLUGIN_ROOT,
    REPO_ROOT / "tests",
)
TARGET_MODULES = {
    "auto_transfer": PLUGIN_ROOT / "auto_transfer.py",
    "online_subtitles.common": PLUGIN_ROOT / "online_subtitles" / "common.py",
    "target_resolver": PLUGIN_ROOT / "target_resolver.py",
    "timeline_fixer": PLUGIN_ROOT / "timeline_fixer.py",
}


def _relative(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT).as_posix()


def _iter_python_files() -> list[Path]:
    files: list[Path] = []
    for root in SEARCH_ROOTS:
        if not root.exists():
            continue
        files.extend(path for path in root.rglob("*.py") if path.is_file())
    return sorted(files)


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(errors="ignore")


def _statement_at(lines: list[str], lineno: int) -> str:
    if lineno <= 0 or lineno > len(lines):
        return ""
    return lines[lineno - 1].strip()


def _target_match_names(module_key: str) -> set[str]:
    parts = module_key.split(".")
    names = {module_key, parts[-1], f"subtitlemanualupload.{module_key}"}
    names.add(f"plugins.v2.subtitlemanualupload.{module_key}")
    if len(parts) > 1:
        names.add(".".join(parts[-2:]))
    return names


def _import_matches_target(node: ast.ImportFrom, module_key: str) -> bool:
    module = node.module or ""
    match_names = _target_match_names(module_key)
    if module in match_names:
        return True
    if module.endswith(f".{module_key}"):
        return True
    if node.level > 0 and module == module_key.split(".")[-1]:
        return True
    return False


def _direct_import_matches_target(name: str, module_key: str) -> bool:
    match_names = _target_match_names(module_key)
    return name in match_names or name.endswith(f".{module_key}")


def _imports_for(module_key: str) -> dict[str, Any]:
    references: list[dict[str, Any]] = []
    imported_symbols: set[str] = set()
    for path in _iter_python_files():
        source = _read_text(path)
        lines = source.splitlines()
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and _import_matches_target(node, module_key):
                symbols = [alias.name for alias in node.names]
                imported_symbols.update(symbols)
                references.append(
                    {
                        "path": _relative(path),
                        "line": node.lineno,
                        "kind": "from_import",
                        "module": "." * node.level + (node.module or ""),
                        "symbols": symbols,
                        "statement": _statement_at(lines, node.lineno),
                    }
                )
            elif isinstance(node, ast.Import):
                matched = [alias.name for alias in node.names if _direct_import_matches_target(alias.name, module_key)]
                if not matched:
                    continue
                references.append(
                    {
                        "path": _relative(path),
                        "line": node.lineno,
                        "kind": "import",
                        "module": "",
                        "symbols": matched,
                        "statement": _statement_at(lines, node.lineno),
                    }
                )
    return {
        "references": references,
        "imported_symbols": sorted(imported_symbols),
    }


def _top_level_symbols(tree: ast.Module) -> list[dict[str, Any]]:
    symbols: list[dict[str, Any]] = []
    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            symbols.append(
                {
                    "name": node.name,
                    "kind": "class" if isinstance(node, ast.ClassDef) else "function",
                    "line_start": node.lineno,
                    "line_end": node.end_lineno,
                    "line_count": (node.end_lineno or node.lineno) - node.lineno + 1,
                    "public": not node.name.startswith("_"),
                }
            )
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            names: list[str] = []
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name) and target.id.isupper() and not target.id.startswith("_"):
                    names.append(target.id)
            for name in names:
                symbols.append(
                    {
                        "name": name,
                        "kind": "constant",
                        "line_start": node.lineno,
                        "line_end": node.end_lineno,
                        "line_count": (node.end_lineno or node.lineno) - node.lineno + 1,
                        "public": True,
                    }
                )
    return symbols


def _count_defs(tree: ast.Module) -> dict[str, int]:
    classes = [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
    functions = [node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    top_classes = [node for node in tree.body if isinstance(node, ast.ClassDef)]
    top_functions = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    return {
        "top_level_class_count": len(top_classes),
        "top_level_function_count": len(top_functions),
        "total_class_count": len(classes),
        "total_function_count": len(functions),
        "total_class_function_count": len(classes) + len(functions),
    }


def _module_inventory(module_key: str, path: Path, *, details: bool) -> dict[str, Any]:
    source = _read_text(path)
    tree = ast.parse(source)
    lines = source.splitlines()
    symbols = _top_level_symbols(tree)
    imports = _imports_for(module_key)
    public_exports = sorted(symbol["name"] for symbol in symbols if symbol["public"])
    imported_symbols = [symbol for symbol in imports["imported_symbols"] if symbol != "*"]
    facade_symbols = sorted(set(public_exports) | set(imported_symbols))
    known_symbols = {symbol["name"] for symbol in symbols}
    inventory: dict[str, Any] = {
        "module": module_key,
        "path": _relative(path),
        "line_count": len(lines),
        **_count_defs(tree),
        "top_level_symbol_count": len(symbols),
        "public_exports": public_exports,
        "imported_symbols": imported_symbols,
        "facade_symbols_to_preserve": facade_symbols,
        "imported_symbols_missing_from_module": sorted(set(imported_symbols) - known_symbols),
        "import_reference_count": len(imports["references"]),
    }
    if details:
        inventory["top_level_symbols"] = symbols
        inventory["import_references"] = imports["references"]
    return inventory


def build_inventory(*, details: bool = False) -> dict[str, Any]:
    modules = {
        key: _module_inventory(key, path, details=details)
        for key, path in TARGET_MODULES.items()
    }
    return {
        "target": "plugins.v2/subtitlemanualupload backend big modules",
        "module_count": len(modules),
        "modules": modules,
        "summary": {
            key: {
                "path": value["path"],
                "line_count": value["line_count"],
                "total_class_function_count": value["total_class_function_count"],
                "public_export_count": len(value["public_exports"]),
                "facade_symbol_count": len(value["facade_symbols_to_preserve"]),
                "import_reference_count": value["import_reference_count"],
            }
            for key, value in modules.items()
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Inventory SubtitleManualUpload backend big modules.")
    parser.add_argument("--details", action="store_true", help="include top-level symbol and import reference details")
    args = parser.parse_args()
    print(json.dumps(build_inventory(details=args.details), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
