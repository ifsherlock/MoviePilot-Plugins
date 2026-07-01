from __future__ import annotations

import importlib.util
import importlib
import sys
from pathlib import Path


def load_cache_helpers():
    module_name = "subtitlemanualupload_cache_helpers"
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(
        module_name,
        Path(__file__).with_name("test_subtitlemanualupload_cache.py"),
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def automation_facade(module):
    return importlib.import_module(f"{module.__name__}.automation_facade").SubtitleAutomationFacade


def make_enabled_plugin(tmp_path):
    helpers = load_cache_helpers()
    module, _, _ = helpers.load_plugin_module()
    plugin = helpers.make_plugin(module)
    plugin._enabled = True
    video = tmp_path / "Movie.mkv"
    video.write_text("video", encoding="utf-8")
    entry = {
        "id": "t1",
        "path": str(video),
        "basename": "Movie",
        "filename": "Movie.mkv",
        "target_label": "Movie",
        "storage": "local",
    }
    helpers.remember_targets(plugin, module, [entry])
    return helpers, module, plugin, entry


class FakeAutoTransfer:
    def __init__(self):
        self.written = []

    def auto_transfer_queue_summary(self):
        return {"total": 0, "pending": 0}

    def auto_transfer_queue_snapshot(self, limit=100):
        return {"limit": limit, "tasks": []}

    def auto_search_keywords_for_entry(self, entry, target):
        return [f"{entry['basename']} 2024"]

    def auto_search_and_write_entry(self, entry):
        self.written.append(entry["id"])
        return {"status": "completed", "target": entry["id"]}


class FakeAutosubBridge:
    def __init__(self):
        self.submitted = []

    def autosub_status(self):
        return {"available": True, "enabled": True}

    def autosub_tasks_for_entries(self, entries):
        return {"summary": {"total": 0}, "tasks": [], "task_by_target": {}}

    def submit_autosub_for_entries(self, entries, **kwargs):
        self.submitted.append({"entries": entries, "kwargs": kwargs})
        return {"added": [{"target_id": entry["id"]} for entry in entries], "skipped": [], "failed": []}


class FakeTimelineTasks:
    def tasks_for_entries(self, entries):
        return {"summary": {"total": len(entries)}, "tasks": [], "task_by_target": {}}


def test_automation_facade_reports_disabled_plugin():
    helpers = load_cache_helpers()
    module, _, _ = helpers.load_plugin_module()
    plugin = module.SubtitleManualUpload.__new__(module.SubtitleManualUpload)
    facade = automation_facade(module)(plugin)

    result = facade.query_status()

    assert result == {
        "success": False,
        "message": "SubtitleManualUpload 插件未启用",
        "data": {"enabled": False},
    }


def test_automation_facade_query_status_resolves_targets(tmp_path):
    helpers, module, plugin, _ = make_enabled_plugin(tmp_path)
    auto_transfer = FakeAutoTransfer()
    autosub_bridge = FakeAutosubBridge()
    timeline_tasks = FakeTimelineTasks()
    helpers.override_services(
        plugin,
        auto_transfer=auto_transfer,
        autosub_bridge=autosub_bridge,
        timeline_tasks=timeline_tasks,
    )
    facade = automation_facade(module)(plugin)

    result = facade.query_status(target_ids=["t1"], include_tasks=True)

    assert result["success"] is True
    assert result["data"]["targets"][0]["id"] == "t1"
    assert result["data"]["auto_transfer_queue"] == {"total": 0, "pending": 0}
    assert result["data"]["ai_tasks"]["summary"] == {"total": 0}
    assert result["data"]["timeline_tasks"]["summary"] == {"total": 1}


def test_automation_facade_online_match_precheck_does_not_write(tmp_path):
    helpers, module, plugin, _ = make_enabled_plugin(tmp_path)
    auto_transfer = FakeAutoTransfer()
    helpers.override_services(plugin, auto_transfer=auto_transfer)
    facade = automation_facade(module)(plugin)

    result = facade.online_match(target_ids=["t1"], dry_run=False, confirm_write=False)

    assert result["success"] is True
    assert result["data"]["requires_confirmation"] is True
    assert result["data"]["keywords_by_target"] == {"t1": ["Movie 2024"]}
    assert auto_transfer.written == []


def test_automation_facade_online_match_confirmed_delegates_to_auto_transfer(tmp_path):
    helpers, module, plugin, _ = make_enabled_plugin(tmp_path)
    auto_transfer = FakeAutoTransfer()
    helpers.override_services(plugin, auto_transfer=auto_transfer)
    facade = automation_facade(module)(plugin)

    result = facade.online_match(target_ids=["t1"], dry_run=False, confirm_write=True)

    assert result["success"] is True
    assert result["data"]["results"] == [{"status": "completed", "target": "t1"}]
    assert auto_transfer.written == ["t1"]


def test_automation_facade_ai_generate_requires_confirmation_and_then_submits(tmp_path):
    helpers, module, plugin, _ = make_enabled_plugin(tmp_path)
    autosub_bridge = FakeAutosubBridge()
    helpers.override_services(plugin, autosub_bridge=autosub_bridge)
    facade = automation_facade(module)(plugin)

    preview = facade.ai_generate(target_ids=["t1"], confirm_submit=False)
    submitted = facade.ai_generate(
        target_ids=["t1"],
        source_policy="matched_external",
        overwrite_policy="new_variant",
        confirm_submit=True,
    )

    assert preview["success"] is True
    assert preview["data"]["requires_confirmation"] is True
    assert autosub_bridge.submitted[0]["kwargs"] == {
        "trigger": "workflow",
        "source_policy": "matched_external",
        "overwrite_policy": "new_variant",
    }
    assert submitted["data"]["added"] == [{"target_id": "t1"}]


def test_automation_facade_invalid_target_fails_without_submit(tmp_path):
    helpers, module, plugin, _ = make_enabled_plugin(tmp_path)
    autosub_bridge = FakeAutosubBridge()
    helpers.override_services(plugin, autosub_bridge=autosub_bridge)
    facade = automation_facade(module)(plugin)

    result = facade.ai_generate(target_ids=["missing"], confirm_submit=True)

    assert result["success"] is False
    assert result["message"] == "目标视频已失效，请重新选择资源"
    assert result["data"]["missing_target_ids"] == ["missing"]
    assert autosub_bridge.submitted == []


def test_automation_facade_refresh_index_sync_uses_catalog(tmp_path):
    helpers, module, plugin, entry = make_enabled_plugin(tmp_path)

    class FakeCatalog:
        def __init__(self):
            self.refreshed = False

        def refresh_local_cache(self):
            self.refreshed = True
            return [entry]

        def cache_status(self):
            return {"ready": self.refreshed, "entry_count": 1}

    catalog = FakeCatalog()
    helpers.override_services(plugin, local_media_catalog=catalog)
    facade = automation_facade(module)(plugin)

    result = facade.refresh_index(sync=True)

    assert result["success"] is True
    assert result["data"]["entry_count"] == 1
    assert result["data"]["index"] == {"ready": True, "entry_count": 1}


def test_automation_facade_task_status_without_targets_uses_queue_snapshot(tmp_path):
    helpers, module, plugin, _ = make_enabled_plugin(tmp_path)
    auto_transfer = FakeAutoTransfer()
    autosub_bridge = FakeAutosubBridge()
    helpers.override_services(plugin, auto_transfer=auto_transfer, autosub_bridge=autosub_bridge)
    facade = automation_facade(module)(plugin)

    result = facade.task_status(limit=500)

    assert result["success"] is True
    assert result["data"]["auto_transfer_queue"] == {"limit": 200, "tasks": []}
    assert result["data"]["ai_subtitle"] == {"available": True, "enabled": True}


def test_automation_facade_timeline_fix_precheck_uses_existing_operations(tmp_path):
    helpers, module, plugin, entry = make_enabled_plugin(tmp_path)

    class FakeHistory:
        def existing_timeline_operations(self, items):
            assert items == [{"target_id": "t1"}]
            return ([{"target_entry": entry}], [], [])

    timeline_tasks = FakeTimelineTasks()
    helpers.override_services(plugin, history=FakeHistory(), timeline_tasks=timeline_tasks)
    facade = automation_facade(module)(plugin)

    result = facade.timeline_fix(target_ids=["t1"], confirm_fix=False)

    assert result["success"] is True
    assert result["data"]["requires_confirmation"] is True
    assert result["data"]["preview_count"] == 1
    assert result["data"]["timeline_tasks"]["summary"] == {"total": 1}
