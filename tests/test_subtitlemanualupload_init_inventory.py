from __future__ import annotations

import ast
import importlib.util
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "subtitlemanualupload_init_inventory.py"
PLUGIN_INIT = REPO_ROOT / "plugins.v2" / "subtitlemanualupload" / "__init__.py"
PLUGIN_ROOT = REPO_ROOT / "plugins.v2" / "subtitlemanualupload"


def load_inventory_module():
    spec = importlib.util.spec_from_file_location("subtitlemanualupload_init_inventory", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_inventory_cli_outputs_valid_json_with_core_fields():
    completed = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--details"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    inventory = json.loads(completed.stdout)

    assert inventory["target"] == "plugins.v2/subtitlemanualupload/__init__.py"
    assert inventory["class_name"] == "SubtitleManualUpload"
    assert inventory["line_count"] == len(PLUGIN_INIT.read_text(encoding="utf-8").splitlines())
    assert inventory["method_count"] > 0
    assert "method_groups" in inventory
    assert "source_references" in inventory
    assert "test_references" in inventory


def test_inventory_counts_current_plugin_class_methods():
    inventory_module = load_inventory_module()
    inventory = inventory_module.build_inventory(details=True)
    source = PLUGIN_INIT.read_text(encoding="utf-8")
    tree = ast.parse(source)
    plugin_class = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "SubtitleManualUpload")
    methods = [node for node in plugin_class.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]

    assert inventory["line_count"] == len(source.splitlines())
    assert inventory["method_count"] == len(methods)
    assert {item["name"] for item in inventory["methods"]} == {node.name for node in methods}


def test_inventory_groups_main_entry_responsibilities_and_references():
    inventory_module = load_inventory_module()
    inventory = inventory_module.build_inventory(details=True)
    groups = inventory["method_groups"]

    for group in (
        "moviepilot_hooks",
        "runtime_helpers",
        "service_factories",
        "service_delegates",
        "ai_autosub_facade",
        "config_runtime",
    ):
        assert groups[group]["count"] > 0
        assert groups[group]["methods"]

    assert groups["archive_methods"]["count"] == 0
    assert groups["archive_methods"]["methods"] == []
    assert "init_plugin" in groups["moviepilot_hooks"]["methods"]
    assert "_save_config" in groups["config_runtime"]["methods"]
    assert "_subtitle_writer" in groups["service_factories"]["methods"]
    assert "_set_timeline_task" in groups["service_delegates"]["methods"]
    assert "_submit_online_ai_translate" in groups["ai_autosub_facade"]["methods"]
    assert inventory["source_references"].get("_subtitle_writer")
    assert inventory["test_references"].get("get_api")


def test_inventory_reports_no_compat_layer_files_or_symbols():
    compat_name = "comp" + "at"
    for name in (f"{compat_name}.py", f"{compat_name}_core.py", f"{compat_name}_services.py"):
        assert not (PLUGIN_ROOT / name).exists()

    search_roots = [PLUGIN_ROOT, REPO_ROOT / "tests", REPO_ROOT / "scripts"]
    forbidden = (
        "SubtitleManualUpload" + "CompatMixin",
        "install_" + compat_name + "_",
        f"{compat_name}_core",
        f"{compat_name}_services",
    )
    for root in search_roots:
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            for pattern in forbidden:
                assert pattern not in text, f"{pattern} found in {path.relative_to(REPO_ROOT)}"
