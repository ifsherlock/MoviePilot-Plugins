from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "subtitlemanualupload_backend_inventory.py"


def load_inventory_module():
    spec = importlib.util.spec_from_file_location("subtitlemanualupload_backend_inventory", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_backend_inventory_cli_outputs_valid_json_for_big_modules():
    completed = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--details"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    inventory = json.loads(completed.stdout)

    assert inventory["module_count"] == 4
    for key in ("auto_transfer", "online_subtitles.common", "target_resolver", "timeline_fixer"):
        module = inventory["modules"][key]
        assert module["line_count"] > 0
        assert module["total_class_function_count"] > 0
        assert module["public_exports"]
        assert module["facade_symbols_to_preserve"]
        assert "path" in module


def test_backend_inventory_records_facade_symbols_to_preserve():
    inventory_module = load_inventory_module()
    inventory = inventory_module.build_inventory(details=True)

    auto_transfer = inventory["modules"]["auto_transfer"]
    assert {"AutoTransferService", "AutoTransferCollaborators"} <= set(auto_transfer["facade_symbols_to_preserve"])
    assert auto_transfer["import_reference_count"] > 0

    common = inventory["modules"]["online_subtitles.common"]
    assert {"OnlineSubtitleResult", "OnlinePageClient", "build_search_keywords"} <= set(common["facade_symbols_to_preserve"])

    target_resolver = inventory["modules"]["target_resolver"]
    assert {"MediaTargetResolver", "LocalMediaCatalog", "SubtitleInventory"} <= set(target_resolver["facade_symbols_to_preserve"])

    timeline_fixer = inventory["modules"]["timeline_fixer"]
    assert {"TimelineFixResult", "check_timeline_fixer_dependencies", "fix_subtitle_timeline"} <= set(
        timeline_fixer["facade_symbols_to_preserve"]
    )
