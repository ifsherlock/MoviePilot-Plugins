from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "subtitlemanualupload_style_ownership.py"
FRONTEND_INVENTORY_PATH = REPO_ROOT / "scripts" / "subtitlemanualupload_frontend_inventory.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_style_ownership_cli_outputs_valid_selector_map():
    completed = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--summary"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    summary = json.loads(completed.stdout)

    assert summary["target"] == "plugins.v2/subtitlemanualupload/src/components/AppPage.vue"
    assert summary["selector_count"] > 100
    assert summary["unmapped_selectors"] == []
    assert summary["app_page_unused_selectors"] == []
    assert ".subtitle-upload-page" in summary["stay_in_app_page_selectors"]
    assert ".media-card" in summary["move_with_component_selectors"]


def test_style_ownership_covers_frontend_inventory_selectors():
    ownership_module = load_module(SCRIPT_PATH, "subtitlemanualupload_style_ownership")
    inventory_module = load_module(FRONTEND_INVENTORY_PATH, "subtitlemanualupload_frontend_inventory")

    ownership = ownership_module.build_style_ownership()
    inventory = inventory_module.build_inventory(details=True)

    ownership_selectors = {item["selector"].lstrip(".") for item in ownership["selectors"]}
    inventory_selectors = set(inventory["css_class_inventory"]["style_class_selectors"])

    assert ownership_selectors == inventory_selectors
    assert ownership["unmapped_selectors"] == []

    by_selector = {item["selector"]: item for item in ownership["selectors"]}
    assert by_selector[".root-tabs"]["migration"] == "stay-in-app-page"
    assert by_selector[".online-dialog"]["migration"] == "move-in-3.3"
    assert by_selector[".ai-task-dialog"]["owner"] == "AiTaskDialog"
    assert by_selector[".upload-dialog"]["owner"] == "UploadDialog"
    assert by_selector[".auto-queue-card"]["migration"] == "move-in-3.4"
    assert by_selector[".auto-queue-card"]["owner"] == "AutoTransferQueueDialog"
    assert by_selector[".global-history-card"]["owner"] == "MatchHistoryPanel"
    assert ".detail-tabs" not in by_selector
    assert ownership["legacy_orphan_cleanup_selectors"] == []
    assert ownership["app_page_unused_selectors"] == []
