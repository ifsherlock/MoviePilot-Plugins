from __future__ import annotations

import argparse
import ast
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
COMPAT_PATH = ROOT / "plugins.v2" / "subtitlemanualupload" / "compat.py"
SOURCE_ROOT = ROOT / "plugins.v2" / "subtitlemanualupload"
TEST_ROOT = ROOT / "tests"


def method_nodes(tree: ast.Module) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "SubtitleManualUploadCompatMixin":
            return [item for item in node.body if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))]
    raise RuntimeError("SubtitleManualUploadCompatMixin not found")


def iter_python_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return [
        path
        for path in root.rglob("*.py")
        if "__pycache__" not in path.parts and path != COMPAT_PATH
    ]


def call_sites(name: str, files: list[Path]) -> list[str]:
    pattern = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(name)}\s*\(")
    hits: list[str] = []
    for path in files:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        for line_no, line in enumerate(lines, 1):
            if pattern.search(line):
                hits.append(f"{path.relative_to(ROOT).as_posix()}:{line_no}")
    return hits


def is_one_line_delegate(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    body = [item for item in node.body if not isinstance(item, ast.Pass)]
    if len(body) != 1:
        return False
    item = body[0]
    value: ast.AST | None = None
    if isinstance(item, ast.Return):
        value = item.value
    elif isinstance(item, ast.Expr):
        value = item.value
    return isinstance(value, ast.Call)


def classify_method(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    source_hits: list[str],
    test_hits: list[str],
) -> str:
    line_count = (node.end_lineno or node.lineno) - node.lineno + 1
    delegate = is_one_line_delegate(node)
    name = node.name
    if source_hits:
        return "required-runtime"
    if test_hits:
        return "required-test"
    if delegate:
        return "delete-now"
    if name.startswith(
        (
            "_normalize_",
            "_language_",
            "_detect_language",
            "_archive_",
            "_extract_",
            "_build_",
            "_tmdb_",
            "_timeline_",
            "_auto_",
        )
    ):
        return "move-to-service"
    if line_count <= 3:
        return "delete-now"
    return "move-to-service"


def build_inventory() -> dict[str, Any]:
    source_text = COMPAT_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source_text)
    source_files = iter_python_files(SOURCE_ROOT)
    test_files = iter_python_files(TEST_ROOT)
    methods = []
    for node in method_nodes(tree):
        source_hits = call_sites(node.name, source_files)
        test_hits = call_sites(node.name, test_files)
        line_count = (node.end_lineno or node.lineno) - node.lineno + 1
        classification = classify_method(node, source_hits, test_hits)
        methods.append(
            {
                "name": node.name,
                "kind": "async" if isinstance(node, ast.AsyncFunctionDef) else "sync",
                "line_start": node.lineno,
                "line_end": node.end_lineno,
                "line_count": line_count,
                "delegate_only": is_one_line_delegate(node),
                "source_call_sites": source_hits,
                "test_call_sites": test_hits,
                "classification": classification,
            }
        )
    return {
        "compat_path": COMPAT_PATH.relative_to(ROOT).as_posix(),
        "line_count": len(source_text.splitlines()),
        "method_count": len(methods),
        "classification_counts": dict(Counter(item["classification"] for item in methods)),
        "delegate_only_count": sum(1 for item in methods if item["delegate_only"]),
        "source_referenced_count": sum(1 for item in methods if item["source_call_sites"]),
        "test_referenced_count": sum(1 for item in methods if item["test_call_sites"]),
        "delete_now": [item["name"] for item in methods if item["classification"] == "delete-now"],
        "methods": methods,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Inventory SubtitleManualUpload compat.py methods.")
    parser.add_argument("--details", action="store_true", help="Print full method inventory.")
    args = parser.parse_args()
    inventory = build_inventory()
    if not args.details:
        inventory = {key: value for key, value in inventory.items() if key != "methods"}
    print(json.dumps(inventory, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
