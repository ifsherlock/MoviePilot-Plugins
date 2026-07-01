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
    remaining_root_modules = inventory["migration"]["remaining_root_modules"]
    assert inventory["remaining_root_module_count"] == len(remaining_root_modules)
    assert inventory["migration"]["root_module_count"] == len(remaining_root_modules)
    assert inventory["migration"]["remaining_root_module_count"] == len(remaining_root_modules)
    assert inventory["migration"]["unmapped_root_modules"] == []
    assert "config_runtime" not in remaining_root_modules
    assert "config_schema" not in remaining_root_modules
    assert "subtitle_history" not in remaining_root_modules
    assert "subtitle_language" not in remaining_root_modules
    assert "subtitle_writer" not in remaining_root_modules
    assert "tongwen" not in remaining_root_modules
    assert "timeline_alignment" not in remaining_root_modules
    assert "timeline_cache" not in remaining_root_modules
    assert "timeline_dependencies" not in remaining_root_modules
    assert "timeline_fixer" not in remaining_root_modules
    assert "timeline_io" not in remaining_root_modules
    assert "timeline_tasks" not in remaining_root_modules
    assert "timeline_vad" not in remaining_root_modules
    assert "local_media_catalog" not in remaining_root_modules
    assert "media_metadata" not in remaining_root_modules
    assert "media_target_resolver" not in remaining_root_modules
    assert "subtitle_inventory" not in remaining_root_modules
    assert "target_normalizers" not in remaining_root_modules
    assert "target_resolver" not in remaining_root_modules
    assert "online_ai" not in remaining_root_modules
    assert "online_subtitle" not in remaining_root_modules
    assert "upload_session" not in remaining_root_modules

    target_packages = {item["name"]: item for item in inventory["target_subpackages"]}
    for name in (
        "automation",
        "auto_transfer",
        "catalog",
        "config",
        "integrations",
        "matching",
        "online",
        "runtime",
        "timeline",
        "upload",
        "utils",
    ):
        assert target_packages[name]["exists"] is True
        if name == "config":
            assert target_packages[name]["contains_only_init"] is False
            assert target_packages[name]["python_files"] == ["__init__.py", "config_runtime.py", "config_schema.py"]
        elif name == "catalog":
            assert target_packages[name]["contains_only_init"] is False
            assert target_packages[name]["python_files"] == [
                "__init__.py",
                "local_media_catalog.py",
                "media_metadata.py",
                "media_target_resolver.py",
                "subtitle_inventory.py",
                "target_normalizers.py",
                "target_resolver.py",
            ]
        elif name == "matching":
            assert target_packages[name]["contains_only_init"] is False
            assert target_packages[name]["python_files"] == [
                "__init__.py",
                "subtitle_history.py",
                "subtitle_language.py",
                "subtitle_writer.py",
                "tongwen.py",
            ]
        elif name == "timeline":
            assert target_packages[name]["contains_only_init"] is False
            assert target_packages[name]["python_files"] == [
                "__init__.py",
                "timeline_alignment.py",
                "timeline_cache.py",
                "timeline_dependencies.py",
                "timeline_fixer.py",
                "timeline_io.py",
                "timeline_tasks.py",
                "timeline_vad.py",
            ]
        elif name == "online":
            assert target_packages[name]["contains_only_init"] is False
            assert target_packages[name]["python_files"] == ["__init__.py", "online_ai.py", "online_subtitle.py"]
        elif name == "upload":
            assert target_packages[name]["contains_only_init"] is False
            assert target_packages[name]["python_files"] == ["__init__.py", "upload_session.py"]
        else:
            assert target_packages[name]["contains_only_init"] is True

    migration_targets = {item["module"]: item for item in inventory["migration"]["migration_targets"]}
    assert migration_targets["workflow_actions"]["target_subpackage"] == "automation"
    assert migration_targets["auto_transfer"]["target_subpackage"] == "auto_transfer"
    assert migration_targets["config_runtime"]["migrated"] is True
    assert migration_targets["config_schema"]["migrated"] is True
    assert migration_targets["subtitle_history"]["migrated"] is True
    assert migration_targets["subtitle_language"]["migrated"] is True
    assert migration_targets["subtitle_writer"]["migrated"] is True
    assert migration_targets["tongwen"]["migrated"] is True
    assert migration_targets["timeline_alignment"]["migrated"] is True
    assert migration_targets["timeline_cache"]["migrated"] is True
    assert migration_targets["timeline_dependencies"]["migrated"] is True
    assert migration_targets["timeline_fixer"]["migrated"] is True
    assert migration_targets["timeline_io"]["migrated"] is True
    assert migration_targets["timeline_tasks"]["migrated"] is True
    assert migration_targets["timeline_vad"]["migrated"] is True
    assert migration_targets["local_media_catalog"]["migrated"] is True
    assert migration_targets["media_metadata"]["migrated"] is True
    assert migration_targets["media_target_resolver"]["migrated"] is True
    assert migration_targets["subtitle_inventory"]["migrated"] is True
    assert migration_targets["target_normalizers"]["migrated"] is True
    assert migration_targets["target_resolver"]["migrated"] is True
    assert migration_targets["online_ai"]["migrated"] is True
    assert migration_targets["online_subtitle"]["migrated"] is True
    assert migration_targets["upload_session"]["migrated"] is True
    assert migration_targets["target_resolver"]["target_subpackage"] == "catalog"
    assert migration_targets["timeline_fixer"]["target_subpackage"] == "timeline"

    for key in ("auto_transfer", "online_subtitles.common", "target_resolver", "timeline_fixer"):
        module = inventory["modules"][key]
        assert module["line_count"] > 0
        if key != "online_subtitles.common":
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
