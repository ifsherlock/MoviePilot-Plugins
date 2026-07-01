#!/usr/bin/env python3
"""Validate release plugin versions before packaging.

The release workflow builds tags and assets from package.json/package.v2.json.
This check prevents publishing an asset whose market index version differs
from the plugin class-level plugin_version.
"""

from __future__ import annotations

import ast
import json
import sys
import warnings
from pathlib import Path
from typing import Any

warnings.filterwarnings("ignore", category=SyntaxWarning)


def _load_package(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as file_obj:
        return json.load(file_obj)


def _candidate_dirs(package_file: Path, plugin_id: str) -> list[Path]:
    plugin_id_lc = plugin_id.lower()
    roots = [Path("plugins.v2"), Path("plugins")]
    if package_file.name == "package.json":
        roots = [Path("plugins"), Path("plugins.v2")]
    return [package_file.parent / root / plugin_id_lc for root in roots]


def _plugin_dir(package_file: Path, plugin_id: str) -> Path | None:
    for candidate in _candidate_dirs(package_file, plugin_id):
        if candidate.is_dir():
            return candidate
    return None


def _plugin_version(init_file: Path) -> str | None:
    tree = ast.parse(init_file.read_text(encoding="utf-8"), filename=str(init_file))
    for class_node in (node for node in tree.body if isinstance(node, ast.ClassDef)):
        for node in class_node.body:
            value_node = None
            if isinstance(node, ast.Assign):
                if any(
                    isinstance(target, ast.Name) and target.id == "plugin_version"
                    for target in node.targets
                ):
                    value_node = node.value
            elif (
                isinstance(node, ast.AnnAssign)
                and isinstance(node.target, ast.Name)
                and node.target.id == "plugin_version"
            ):
                value_node = node.value
            if isinstance(value_node, ast.Constant) and isinstance(value_node.value, str):
                return value_node.value
    return None


def check_package(path: Path) -> list[str]:
    errors: list[str] = []
    package = _load_package(path)
    for plugin_id, meta in package.items():
        if not isinstance(meta, dict) or meta.get("release") is not True:
            continue

        package_version = str(meta.get("version") or "").strip()
        history_key = f"v{package_version}"
        if not package_version:
            errors.append(f"{path}: {plugin_id} release=true but version is empty")
        if history_key not in (meta.get("history") or {}):
            errors.append(f"{path}: {plugin_id} missing history entry {history_key}")

        plugin_dir = _plugin_dir(path, plugin_id)
        if not plugin_dir:
            expected = ", ".join(str(candidate) for candidate in _candidate_dirs(path, plugin_id))
            errors.append(f"{path}: {plugin_id} missing plugin directory; checked {expected}")
            continue

        init_file = plugin_dir / "__init__.py"
        if not init_file.exists():
            errors.append(f"{path}: {plugin_id} missing {init_file}")
            continue

        source_version = _plugin_version(init_file)
        if not source_version:
            errors.append(f"{path}: {plugin_id} missing class-level plugin_version in {init_file}")
            continue
        if package_version != source_version:
            errors.append(
                f"{path}: {plugin_id} version mismatch, "
                f"package={package_version}, plugin_version={source_version} ({init_file})"
            )

        plugin_package = plugin_dir / "package.json"
        if plugin_package.exists():
            plugin_package_version = str(_load_package(plugin_package).get("version") or "").strip()
            if plugin_package_version and plugin_package_version != package_version:
                errors.append(
                    f"{path}: {plugin_id} package version mismatch, "
                    f"index={package_version}, plugin_package={plugin_package_version} ({plugin_package})"
                )
    return errors


def main() -> int:
    package_files = [Path(arg) for arg in sys.argv[1:]] or [Path("package.json"), Path("package.v2.json")]
    errors: list[str] = []
    for package_file in package_files:
        errors.extend(check_package(package_file))
    if errors:
        print("Plugin release version gate failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Plugin release version gate passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
