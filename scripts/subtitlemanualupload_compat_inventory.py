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
COMPAT_CORE_PATH = ROOT / "plugins.v2" / "subtitlemanualupload" / "compat_core.py"
COMPAT_SERVICES_PATH = ROOT / "plugins.v2" / "subtitlemanualupload" / "compat_services.py"
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
        if "__pycache__" not in path.parts
    ]


def call_sites(name: str, files: list[Path], *, exclude_paths: set[Path] | None = None) -> list[str]:
    exclude_paths = {path.resolve() for path in (exclude_paths or set())}
    pattern = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])")
    definition_pattern = re.compile(rf"^\s*(async\s+def|def)\s+{re.escape(name)}\s*\(")
    hits: list[str] = []
    for path in files:
        if path.resolve() in exclude_paths:
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        for line_no, line in enumerate(lines, 1):
            if path == COMPAT_PATH and definition_pattern.search(line):
                continue
            if pattern.search(line):
                hits.append(f"{path.relative_to(ROOT).as_posix()}:{line_no}")
    return hits


def _string_node_value(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _assignment_target_name(target: ast.AST, installer_arg: str) -> str | None:
    if (
        isinstance(target, ast.Attribute)
        and isinstance(target.value, ast.Name)
        and target.value.id == installer_arg
        and target.attr.startswith("_")
    ):
        return target.attr
    return None


def dynamic_install_methods_from_file(path: Path) -> list[dict[str, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    rel_path = path.relative_to(ROOT).as_posix()
    installs: list[dict[str, str]] = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name.startswith("install_"):
            installer_arg = node.args.args[0].arg if node.args.args else "cls"
            for child in ast.walk(node):
                if isinstance(child, ast.Assign):
                    for target in child.targets:
                        name = _assignment_target_name(target, installer_arg)
                        if name:
                            installs.append(
                                {
                                    "name": name,
                                    "installer": node.name,
                                    "kind": "attribute-assignment",
                                    "source": f"{rel_path}:{child.lineno}",
                                }
                            )
                elif isinstance(child, ast.Call) and isinstance(child.func, ast.Name) and child.func.id == "setattr":
                    if len(child.args) >= 2:
                        first = child.args[0]
                        second = child.args[1]
                        if isinstance(first, ast.Name) and first.id == installer_arg:
                            name = _string_node_value(second)
                            if name and name.startswith("_"):
                                installs.append(
                                    {
                                        "name": name,
                                        "installer": node.name,
                                        "kind": "setattr",
                                        "source": f"{rel_path}:{child.lineno}",
                                    }
                                )
    return installs


def legacy_delegate_methods_from_file(path: Path) -> list[dict[str, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    rel_path = path.relative_to(ROOT).as_posix()
    installs: list[dict[str, str]] = []
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == "LEGACY_INSTANCE_SERVICE_DELEGATES" for target in node.targets):
            continue
        if not isinstance(node.value, (ast.Tuple, ast.List)):
            continue
        for item in node.value.elts:
            if not isinstance(item, (ast.Tuple, ast.List)) or not item.elts:
                continue
            name = _string_node_value(item.elts[0])
            if name and name.startswith("_"):
                installs.append(
                    {
                        "name": name,
                        "installer": "LEGACY_INSTANCE_SERVICE_DELEGATES",
                        "kind": "legacy-service-delegate",
                        "source": f"{rel_path}:{getattr(item, 'lineno', node.lineno)}",
                    }
                )
    return installs


def dynamic_install_methods() -> list[dict[str, str]]:
    installs: list[dict[str, str]] = []
    for path in (COMPAT_CORE_PATH, COMPAT_SERVICES_PATH):
        if not path.exists():
            continue
        installs.extend(dynamic_install_methods_from_file(path))
    if COMPAT_SERVICES_PATH.exists():
        installs.extend(legacy_delegate_methods_from_file(COMPAT_SERVICES_PATH))
    return sorted(installs, key=lambda item: (item["name"], item["source"]))


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
        source_hits = call_sites(node.name, source_files, exclude_paths={COMPAT_PATH})
        test_hits = call_sites(node.name, test_files)
        line_count = (node.end_lineno or node.lineno) - node.lineno + 1
        classification = classify_method(node, source_hits, test_hits)
        delete_blockers = []
        if source_hits:
            delete_blockers.append("runtime-refs")
        if test_hits:
            delete_blockers.append("test-refs")
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
                "delete_blockers": delete_blockers,
                "classification": classification,
            }
        )
    dynamic_installs = dynamic_install_methods()
    runtime_refs = {item["name"]: item["source_call_sites"] for item in methods if item["source_call_sites"]}
    test_refs = {item["name"]: item["test_call_sites"] for item in methods if item["test_call_sites"]}
    dynamic_install_names = sorted({item["name"] for item in dynamic_installs})
    delete_blockers = {
        "explicit_methods": sorted({*runtime_refs.keys(), *test_refs.keys()}),
        "dynamic_installs": dynamic_install_names,
    }
    return {
        "compat_path": COMPAT_PATH.relative_to(ROOT).as_posix(),
        "line_count": len(source_text.splitlines()),
        "method_count": len(methods),
        "classification_counts": dict(Counter(item["classification"] for item in methods)),
        "delegate_only_count": sum(1 for item in methods if item["delegate_only"]),
        "source_referenced_count": sum(1 for item in methods if item["source_call_sites"]),
        "test_referenced_count": sum(1 for item in methods if item["test_call_sites"]),
        "runtime_refs": runtime_refs,
        "test_refs": test_refs,
        "dynamic_installs": dynamic_installs,
        "dynamic_install_count": len(dynamic_installs),
        "dynamic_install_method_count": len(dynamic_install_names),
        "delete_blockers": delete_blockers,
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
