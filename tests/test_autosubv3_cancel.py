from __future__ import annotations

import importlib.util
import json
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


def test_delete_pending_task_removes_queue_and_record():
    module = load_plugin_module()
    plugin = make_plugin(module)
    with tempfile.NamedTemporaryFile(suffix=".mkv") as video:
        assert plugin.add_task(video.name, module.TaskSource.SUBTITLE_MANUAL_UPLOAD, force_generate=True) is True
        task = next(iter(plugin._tasks.values()))

        result = plugin.delete_tasks(task_ids=[task.task_id])
        payload = plugin.tasks_payload(paths=[video.name])

    assert len(result["deleted"]) == 1
    assert plugin._task_queue.qsize() == 0
    assert payload["tasks"] == []


def test_delete_in_progress_task_is_skipped():
    module = load_plugin_module()
    plugin = make_plugin(module)
    with tempfile.NamedTemporaryFile(suffix=".mkv") as video:
        assert plugin.add_task(video.name, module.TaskSource.SUBTITLE_MANUAL_UPLOAD, force_generate=True) is True
        task = next(iter(plugin._tasks.values()))
        plugin._task_queue.get_nowait()
        task.status = module.TaskStatus.IN_PROGRESS
        plugin._current_processing_task = task

        result = plugin.delete_tasks(task_ids=[task.task_id])
        payload = plugin.tasks_payload(paths=[video.name])

    assert result["deleted"] == []
    assert result["skipped"][0]["reason"] == "任务正在处理，请先取消后再删除"
    assert len(payload["tasks"]) == 1


def test_translated_subtitle_uses_chs_ai_suffix():
    module = load_plugin_module()

    assert (
        module.AutoSubv3._AutoSubv3__translated_subtitle_path("/media/Movie")
        == "/media/Movie.chs.ai.srt"
    )


def test_chs_ai_subtitle_is_detected_as_existing_chinese_subtitle():
    module = load_plugin_module()

    with tempfile.TemporaryDirectory() as tmpdir:
        video_path = Path(tmpdir) / "Movie.mkv"
        subtitle_path = Path(tmpdir) / "Movie.chs.ai.srt"
        video_path.write_bytes(b"video")
        subtitle_path.write_text("1\n00:00:01,000 --> 00:00:02,000\nhello\n", encoding="utf-8")

        exists, lang, filename = module.AutoSubv3._AutoSubv3__external_subtitle_exists(
            str(video_path),
            prefer_langs=["zh", "chs"],
            only_srt=True,
            strict=True,
        )

    assert exists is True
    assert lang == "zh"
    assert filename == "Movie.chs.ai.srt"


def test_settings_form_uses_compatible_native_schema():
    module = load_plugin_module()
    plugin = make_plugin(module)

    form, defaults = plugin.get_form()
    encoded = json.dumps(form, ensure_ascii=False)

    assert defaults["openai_model"] == "inclusionAI/Ling-flash-2.0"
    assert "use_chatgpt_trigger" not in encoded
    assert "VExpansionPanels" not in encoded
    assert "v-show" not in encoded
    assert all(value is not None for value in defaults.values())

    def walk(node):
        if isinstance(node, list):
            for item in node:
                yield from walk(item)
            return
        if not isinstance(node, dict):
            return
        yield node
        yield from walk(node.get("content"))

    for node in walk(form):
        if node.get("component") == "VRow":
            for child in node.get("content") or []:
                assert child.get("component") == "VCol"
        if node.get("component") == "VSelect":
            items = node.get("props", {}).get("items") or []
            assert items
            assert all(isinstance(item, dict) for item in items)
            assert all("title" in item and "value" in item for item in items)


def test_delete_api_is_registered():
    module = load_plugin_module()
    plugin = make_plugin(module)

    apis = {item["path"]: item for item in plugin.get_api()}

    assert "/delete" in apis
    assert apis["/delete"]["methods"] == ["POST"]


def test_translation_high_failure_rate_blocks_subtitle_output():
    module = load_plugin_module()
    plugin = make_plugin(module)
    plugin._skip_chinese = False
    plugin._enable_batch = True
    plugin._subtitle_output_mode = "bilingual"
    subtitles = [types.SimpleNamespace(content=f"line {idx}") for idx in range(10)]

    def fake_translate_parallel(valid_subs):
        plugin._stats.update(
            {
                "translated": 6,
                "failed": 4,
                "batch_success": 0,
                "batch_fail": 1,
                "line_fallback": 6,
            }
        )
        return valid_subs

    plugin._AutoSubv3__load_srt = lambda _path: subtitles
    plugin._AutoSubv3__translate_parallel = fake_translate_parallel
    plugin._AutoSubv3__save_srt = lambda *_args: (_ for _ in ()).throw(
        AssertionError("should not save subtitle when failure rate is too high")
    )

    try:
        plugin._AutoSubv3__translate_zh_subtitle("en", "source.srt", "dest.srt")
    except module.TranslationQualityException as exc:
        assert "40%" in str(exc)
    else:
        raise AssertionError("high translation failure rate should block subtitle output")


def test_translation_failure_rate_at_threshold_allows_subtitle_output():
    module = load_plugin_module()
    plugin = make_plugin(module)
    plugin._skip_chinese = False
    plugin._enable_batch = True
    plugin._subtitle_output_mode = "bilingual"
    subtitles = [types.SimpleNamespace(content=f"line {idx}") for idx in range(10)]
    saved = []

    def fake_translate_parallel(valid_subs):
        plugin._stats.update(
            {
                "translated": 7,
                "failed": 3,
                "batch_success": 1,
                "batch_fail": 1,
                "line_fallback": 7,
            }
        )
        return valid_subs

    plugin._AutoSubv3__load_srt = lambda _path: subtitles
    plugin._AutoSubv3__translate_parallel = fake_translate_parallel
    plugin._AutoSubv3__save_srt = lambda path, items: saved.append((path, items))

    plugin._AutoSubv3__translate_zh_subtitle("en", "source.srt", "dest.srt")

    assert saved == [("dest.srt", subtitles)]


def test_chinese_subtitle_content_forces_chinese_only_output_mode():
    module = load_plugin_module()
    plugin = make_plugin(module)
    plugin._subtitle_output_mode = "bilingual"
    plugin._skip_chinese = False
    plugin._enable_batch = False
    plugin._context_window = 0
    plugin._max_translation_failure_rate = 0.3
    sub = types.SimpleNamespace(content="这是繁體中文字幕內容，應該只輸出潤色後的簡體中文。")
    saved = []

    plugin._AutoSubv3__load_srt = lambda _path: [sub]
    plugin._AutoSubv3__save_srt = lambda _path, items: saved.extend(item.content for item in items)
    plugin._AutoSubv3__translate_to_zh = lambda *_args, **_kwargs: (True, "这是简体中文字幕内容。")
    plugin._AutoSubv3__raise_if_task_cancelled = lambda: None

    plugin._AutoSubv3__translate_zh_subtitle("und", "source.srt", "dest.srt", output_mode="bilingual")

    assert saved == ["这是简体中文字幕内容。"]
    assert plugin._subtitle_output_mode == "bilingual"
