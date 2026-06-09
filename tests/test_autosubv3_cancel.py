from __future__ import annotations

import importlib.util
import queue
import sys
import tempfile
import types
from pathlib import Path


def load_plugin_module():
    root = Path(__file__).resolve().parents[1]
    package_dir = root / "plugins.v2" / "autosubv3"

    class HTTPException(Exception):
        def __init__(self, status_code=500, detail=""):
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

    class PluginBase:
        def get_data(self, key):
            return getattr(self, "_data", {}).get(key)

        def save_data(self, key, value):
            self._data[key] = value

    class FakeEventManager:
        @staticmethod
        def register(_event_type):
            def decorator(func):
                return func

            return decorator

    logger = types.SimpleNamespace(
        info=lambda *args, **kwargs: None,
        warning=lambda *args, **kwargs: None,
        error=lambda *args, **kwargs: None,
        debug=lambda *args, **kwargs: None,
    )

    package_name = "autosubv3_cancel_testpkg"
    modules = {
        "fastapi": types.SimpleNamespace(HTTPException=HTTPException, Request=object),
        "watchdog": types.ModuleType("watchdog"),
        "watchdog.events": types.SimpleNamespace(FileSystemEventHandler=object),
        "watchdog.observers": types.SimpleNamespace(Observer=object),
        "iso639": types.ModuleType("iso639"),
        "psutil": types.ModuleType("psutil"),
        "srt": types.SimpleNamespace(Subtitle=object),
        "lxml": types.ModuleType("lxml"),
        "lxml.etree": types.ModuleType("lxml.etree"),
        "app": types.ModuleType("app"),
        "app.core": types.ModuleType("app.core"),
        "app.core.config": types.SimpleNamespace(settings=types.SimpleNamespace(RMT_MEDIAEXT={".mkv", ".mp4"})),
        "app.core.context": types.SimpleNamespace(MediaInfo=object),
        "app.core.event": types.SimpleNamespace(eventmanager=FakeEventManager(), Event=object),
        "app.schemas": types.SimpleNamespace(TransferInfo=object),
        "app.schemas.types": types.SimpleNamespace(
            NotificationType=types.SimpleNamespace(Manual="Manual"),
            EventType=types.SimpleNamespace(TransferComplete="TransferComplete"),
        ),
        "app.log": types.SimpleNamespace(logger=logger),
        "app.plugins": types.SimpleNamespace(_PluginBase=PluginBase),
        "app.utils": types.ModuleType("app.utils"),
        "app.utils.system": types.SimpleNamespace(SystemUtils=object),
        f"{package_name}.ffmpeg": types.SimpleNamespace(Ffmpeg=object),
        f"{package_name}.translate": types.ModuleType(f"{package_name}.translate"),
        f"{package_name}.translate.openai_translate": types.SimpleNamespace(OpenAi=object),
    }
    for name, module in modules.items():
        sys.modules[name] = module

    for name in list(sys.modules):
        if name == package_name or name.startswith(f"{package_name}."):
            sys.modules.pop(name, None)
    sys.modules[f"{package_name}.ffmpeg"] = modules[f"{package_name}.ffmpeg"]
    sys.modules[f"{package_name}.translate"] = modules[f"{package_name}.translate"]
    sys.modules[f"{package_name}.translate.openai_translate"] = modules[f"{package_name}.translate.openai_translate"]

    spec = importlib.util.spec_from_file_location(
        package_name,
        package_dir / "__init__.py",
        submodule_search_locations=[str(package_dir)],
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[package_name] = module
    spec.loader.exec_module(module)
    return module


def make_plugin(module):
    plugin = module.AutoSubv3.__new__(module.AutoSubv3)
    plugin._data = {}
    plugin._tasks = {}
    plugin._task_queue = queue.Queue()
    plugin._current_processing_task = None
    plugin._consumer_thread = None
    plugin._running = True
    plugin._enabled = True
    return plugin


def test_cancel_pending_task_by_path_marks_inactive():
    module = load_plugin_module()
    plugin = make_plugin(module)
    with tempfile.NamedTemporaryFile(suffix=".mkv") as video:
        assert plugin.add_task(video.name, module.TaskSource.SUBTITLE_MANUAL_UPLOAD, force_generate=True) is True

        result = plugin.cancel_tasks(paths=[video.name])
        payload = plugin.tasks_payload(paths=[video.name])

    assert len(result["cancelled"]) == 1
    assert plugin._task_queue.qsize() == 0
    assert payload["tasks"][0]["status"] == "cancelled"
    assert payload["tasks"][0]["active"] is False
    assert payload["tasks"][0]["cancel_requested"] is True


def test_cancel_in_progress_task_sets_cancel_requested():
    module = load_plugin_module()
    plugin = make_plugin(module)
    with tempfile.NamedTemporaryFile(suffix=".mkv") as video:
        assert plugin.add_task(video.name, module.TaskSource.SUBTITLE_MANUAL_UPLOAD, force_generate=True) is True
        task = next(iter(plugin._tasks.values()))
        plugin._task_queue.get_nowait()
        task.status = module.TaskStatus.IN_PROGRESS
        plugin._current_processing_task = task

        result = plugin.cancel_tasks(paths=[video.name])
        payload = plugin.tasks_payload(paths=[video.name])

    assert len(result["cancelled"]) == 1
    assert task.cancel_requested is True
    assert payload["tasks"][0]["status"] == "cancelled"
    assert payload["tasks"][0]["active"] is False


def test_cancelled_current_task_interrupts_next_translate_call():
    module = load_plugin_module()
    plugin = make_plugin(module)
    with tempfile.NamedTemporaryFile(suffix=".mkv") as video:
        assert plugin.add_task(video.name, module.TaskSource.SUBTITLE_MANUAL_UPLOAD, force_generate=True) is True
        task = next(iter(plugin._tasks.values()))
        plugin._task_queue.get_nowait()
        task.status = module.TaskStatus.IN_PROGRESS
        plugin._current_processing_task = task
        plugin.cancel_tasks(paths=[video.name])

        plugin._max_retries = 1
        plugin._openai = types.SimpleNamespace(
            translate_to_zh=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("should not call OpenAI"))
        )

        try:
            plugin._AutoSubv3__translate_to_zh("hello")
        except module.UserInterruptException:
            pass
        else:
            raise AssertionError("cancelled current task should interrupt translation")
