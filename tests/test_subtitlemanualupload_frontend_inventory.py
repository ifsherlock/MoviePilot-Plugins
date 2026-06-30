from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "subtitlemanualupload_frontend_inventory.py"
APP_PAGE = REPO_ROOT / "plugins.v2" / "subtitlemanualupload" / "src" / "components" / "AppPage.vue"


def load_inventory_module():
    spec = importlib.util.spec_from_file_location("subtitlemanualupload_frontend_inventory", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_frontend_inventory_cli_outputs_valid_json_with_core_fields():
    completed = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--details"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    inventory = json.loads(completed.stdout)

    assert inventory["target"] == "plugins.v2/subtitlemanualupload/src/components/AppPage.vue"
    assert inventory["line_count"] == len(APP_PAGE.read_text(encoding="utf-8").splitlines())
    assert inventory["sections"]["template"]["sha256"]
    assert inventory["sections"]["style_scoped"]["sha256"]
    assert inventory["sections"]["script"]["attrs"] == "setup"
    assert inventory["sections"]["style_scoped"]["attrs"] == "scoped"
    component_paths = {item["path"] for item in inventory["component_templates"]}
    assert "plugins.v2/subtitlemanualupload/src/components/MediaGrid.vue" in component_paths
    assert "plugins.v2/subtitlemanualupload/src/components/TargetDetailPanel.vue" in component_paths
    assert "plugins.v2/subtitlemanualupload/src/components/AiTaskDialog.vue" in component_paths
    assert "plugins.v2/subtitlemanualupload/src/components/OnlineSubtitleDialog.vue" in component_paths
    assert "plugins.v2/subtitlemanualupload/src/components/UploadDialog.vue" in component_paths
    component_style_paths = {item["path"] for item in inventory["component_styles"]}
    assert "plugins.v2/subtitlemanualupload/src/components/MediaSearchPanel.vue" in component_style_paths
    assert "plugins.v2/subtitlemanualupload/src/components/TargetDetailPanel.vue" in component_style_paths
    assert "plugins.v2/subtitlemanualupload/src/components/AiTaskDialog.vue" in component_style_paths
    assert "plugins.v2/subtitlemanualupload/src/components/OnlineSubtitleDialog.vue" in component_style_paths
    assert "plugins.v2/subtitlemanualupload/src/components/UploadDialog.vue" in component_style_paths


def test_frontend_inventory_reports_app_page_contract_surfaces():
    inventory_module = load_inventory_module()
    inventory = inventory_module.build_inventory(details=True)

    expose_keys = set(inventory["define_expose_keys"])
    assert {"loadStatus", "refreshIndex", "runSearch", "onlineSearching"} <= expose_keys

    endpoints = {(item["method"], item["endpoint"]) for item in inventory["endpoints"]}
    assert ("GET", "/status") in endpoints
    assert ("POST", "/ai_tasks") in endpoints
    assert ("POST", "/online_search_provider") in endpoints
    assert any(endpoint.startswith("/targets?") for _, endpoint in endpoints)

    classes = inventory["css_class_inventory"]
    assert "subtitle-upload-page" in classes["template_classes"]
    assert "subtitle-upload-page" in classes["style_class_selectors"]
    assert "hero-card" in classes["template_classes"]
    assert "media-card" in classes["template_classes"]
    assert "ai-status-strip" in classes["template_classes"]

    texts = inventory["visible_text_inventory"]["all_static_texts"]
    assert "字幕匹配" in texts
    assert "匹配历史" in texts
    assert "搜索此集在线字幕" in texts
