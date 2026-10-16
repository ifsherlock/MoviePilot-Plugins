from __future__ import annotations

import sys
import threading
import types
from unittest.mock import Mock

import pytest

from test_autosubv3_cancel import load_plugin_module, make_plugin


@pytest.fixture(params=["v2", "v3"])
def event_plugin(request, monkeypatch, tmp_path):
    module = load_plugin_module(monkeypatch, request.param)
    plugin = make_plugin(module)
    plugin.get_data_path = lambda: tmp_path
    plugin._listen_transfer_event = True
    plugin._generation_mode = module.GenerationMode.MONITOR.value
    plugin._subtitlemanualupload_auto_transfer_enabled = lambda: False
    return module, plugin


def transfer_event(paths, *, as_dict=True, object_data=False):
    transfer = {"file_list_new": paths} if as_dict else types.SimpleNamespace(file_list_new=paths)
    data = types.SimpleNamespace(transferinfo=transfer) if object_data else {"transferinfo": transfer}
    return types.SimpleNamespace(event_data=data)


@pytest.mark.parametrize("as_dict", [True, False])
@pytest.mark.parametrize("object_data", [True, False])
def test_event_enqueues_video_once_and_persists_event_source(event_plugin, tmp_path, as_dict, object_data):
    module, plugin = event_plugin
    path = tmp_path / "episode.MKV"
    path.touch()
    subtitle = tmp_path / "episode.ass"
    subtitle.touch()
    event = transfer_event([str(path), str(path), path, str(subtitle), None, 4, str(tmp_path / "missing.mp4")], as_dict=as_dict, object_data=object_data)
    plugin.listen_transfer_complete(event)
    plugin.listen_transfer_complete(event)
    assert plugin._task_queue.qsize() == 1
    task = next(iter(plugin._tasks.values()))
    assert task.video_file == str(path)
    assert task.source == module.TaskSource.EVENT
    assert task.trigger == "event"
    restored = plugin.load_tasks()[task.task_id]
    assert restored.trigger == "event" and restored.source == module.TaskSource.EVENT
    assert plugin._normalize_trigger("event") == "event"
    assert plugin._normalize_trigger(module.TriggerType.EVENT) == "event"
    assert plugin._normalize_trigger("manual") == "manual"
    assert plugin._normalize_trigger("subtitle_fallback") == "subtitle_fallback"


@pytest.mark.parametrize("blocked_by", ["disabled", "listener", "fallback", "takeover"])
def test_disabled_or_delegated_events_do_not_submit_or_restart_monitor(event_plugin, tmp_path, blocked_by):
    module, plugin = event_plugin
    path = tmp_path / "episode.mkv"
    path.touch()
    plugin._start_file_monitor = Mock(side_effect=AssertionError("event must not restart directory monitoring"))
    if blocked_by == "disabled":
        plugin._enabled = False
    elif blocked_by == "listener":
        plugin._listen_transfer_event = False
    elif blocked_by == "fallback":
        plugin._generation_mode = module.GenerationMode.FALLBACK.value
    else:
        plugin._subtitlemanualupload_auto_transfer_enabled = lambda: True
    plugin.listen_transfer_complete(transfer_event([str(path)]))
    assert plugin._tasks == {}
    assert plugin._task_queue.qsize() == 0
    plugin._start_file_monitor.assert_not_called()


@pytest.mark.parametrize("paths", [None, "a.mkv", {"file": "a.mkv"}, 1, []])
def test_malformed_event_file_list_does_not_create_tasks(event_plugin, paths):
    _, plugin = event_plugin
    plugin.listen_transfer_complete(transfer_event(paths))
    plugin.listen_transfer_complete(types.SimpleNamespace(event_data=None))
    assert plugin._tasks == {}


def test_parallel_transfer_events_do_not_duplicate_pending_task(event_plugin, tmp_path):
    _, plugin = event_plugin
    path = tmp_path / "episode.mkv"
    path.touch()
    event = transfer_event([str(path)])
    failures = []

    def handle():
        try:
            plugin.listen_transfer_complete(event)
        except Exception as exc:
            failures.append(exc)

    threads = [threading.Thread(target=handle) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)
        assert not thread.is_alive()
    assert failures == []
    assert len(plugin._tasks) == plugin._task_queue.qsize() == 1


def test_initialization_and_reload_start_monitor_without_registering_it_as_event(event_plugin, tmp_path, monkeypatch):
    module, plugin = event_plugin
    monitor = Mock()
    plugin._get_monitor_service = lambda: monitor
    plugin.update_config = Mock()
    monkeypatch.setattr(module.tempfile, "gettempdir", lambda: str(tmp_path))
    config = {"enabled": True, "enable_asr": False, "translate_zh": False, "listen_transfer_event": True}
    plugin.init_plugin(dict(config))
    plugin.init_plugin(dict(config))
    assert monitor.start_file_monitor.call_count == 2
    assert "listen_transfer_complete" in module.eventmanager.registered
    assert "_start_file_monitor" not in module.eventmanager.registered
    path = tmp_path / "episode.mkv"
    path.touch()
    plugin.listen_transfer_complete(transfer_event([str(path)]))
    assert len(plugin._tasks) == 1
    assert monitor.start_file_monitor.call_count == 2


def test_directory_monitor_uses_same_event_trigger_as_transfer_listener(event_plugin, tmp_path):
    module, plugin = event_plugin
    monitor_module = sys.modules[f"{module.__name__}.monitoring.monitor_service"]
    monitor = monitor_module.MonitorService(plugin, {".mkv"}, module.logger, lambda: None)
    path = tmp_path / "episode.mkv"
    path.touch()
    monitor.add_monitor_task(str(path))
    task = next(iter(plugin._tasks.values()))
    assert task.source == module.TaskSource.EVENT
    assert task.trigger == "event"
