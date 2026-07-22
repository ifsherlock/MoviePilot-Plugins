from __future__ import annotations

import ast
import asyncio
import importlib.util
import json
import queue
import re
import sys
import tempfile
import threading
import types
from datetime import datetime, timedelta
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
    translate_package = types.ModuleType(f"{package_name}.translate")
    translate_package.__path__ = [str(package_dir / "translate")]
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
        "app.core.plugin": types.SimpleNamespace(PluginManager=lambda: types.SimpleNamespace(running_plugins={})),
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
        f"{package_name}.translate": translate_package,
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
    plugin._data_path = tempfile.mkdtemp(prefix="autosubv3-test-")
    plugin.get_data_path = lambda: plugin._data_path
    plugin._tasks = {}
    plugin._task_queue = queue.Queue()
    plugin._current_processing_task = None
    plugin._consumer_thread = None
    plugin._running = True
    plugin._enabled = True
    plugin._file_size = 0
    plugin._skip_chinese = False
    plugin._send_notify = False
    plugin._enable_asr = True
    plugin._translate_zh = True
    plugin._subtitle_output_mode = "bilingual"
    plugin._event = module.Event()
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


def test_delete_completed_task_only_removes_record_not_generated_subtitle(tmp_path):
    module = load_plugin_module()
    plugin = make_plugin(module)
    video = tmp_path / "Movie.mkv"
    subtitle = tmp_path / "Movie.chi&eng.ai.srt"
    video.write_bytes(b"video")
    subtitle.write_text("1\n00:00:01,000 --> 00:00:02,000\n你好\nHello\n", encoding="utf-8")
    assert plugin.add_task(str(video), module.TaskSource.SUBTITLE_MANUAL_UPLOAD, force_generate=True) is True
    task = next(iter(plugin._tasks.values()))
    plugin._task_queue.get_nowait()
    task.status = module.TaskStatus.COMPLETED

    result = plugin.delete_tasks(task_ids=[task.task_id])
    payload = plugin.tasks_payload(paths=[str(video)])

    assert len(result["deleted"]) == 1
    assert payload["tasks"] == []
    assert subtitle.exists()


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


def test_translated_subtitle_uses_language_ai_suffixes():
    module = load_plugin_module()

    assert module.AutoSubv3._AutoSubv3__translated_subtitle_path("/media/Movie") == "/media/Movie.chi.ai.srt"
    assert module.AutoSubv3._AutoSubv3__translated_subtitle_path("/media/Movie", "ja") == "/media/Movie.chi&jp.ai.srt"
    assert module.AutoSubv3._AutoSubv3__translated_subtitle_path("/media/Movie", "en") == "/media/Movie.chi&eng.ai.srt"
    assert module.AutoSubv3._AutoSubv3__translated_subtitle_path("/media/Movie", "ko") == "/media/Movie.chi&kr.ai.srt"
    assert module.AutoSubv3._AutoSubv3__translated_subtitle_path("/media/Movie", "zh") == "/media/Movie.chi.ai.srt"
    assert (
        module.AutoSubv3._AutoSubv3__translated_subtitle_path("/media/Movie", "en", "chinese_only")
        == "/media/Movie.chi.ai.srt"
    )


def test_format_translated_content_flattens_bilingual_linebreaks():
    module = load_plugin_module()
    plugin = make_plugin(module)

    plugin._subtitle_output_mode = "bilingual"
    assert (
        plugin._AutoSubv3__format_translated_content("Hello\\Nworld\nagain", "你好\n世界")
        == "你好 世界\nHello world again"
    )

    plugin._subtitle_output_mode = "chinese_only"
    assert plugin._AutoSubv3__format_translated_content("Hello", "你好\n世界") == "你好 世界"


def test_submit_tasks_accepts_source_subtitle_override(tmp_path):
    module = load_plugin_module()
    plugin = make_plugin(module)
    video = tmp_path / "Movie.mkv"
    subtitle = tmp_path / "online.fixed.srt"
    video.write_bytes(b"video")
    subtitle.write_text("1\n00:00:01,000 --> 00:00:02,000\nHello\n", encoding="utf-8")

    result = plugin.submit_tasks(
        [str(video)],
        source=module.TaskSource.SUBTITLE_MANUAL_UPLOAD.value,
        subtitle_overrides={str(video): {"subtitle_path": str(subtitle), "lang": "en"}},
    )
    task = next(iter(plugin._tasks.values()))
    payload = plugin.tasks_payload(paths=[str(video)])

    assert result["added"][0]["source_subtitle_name"] == "online.fixed.srt"
    assert task.source_subtitle_path != str(subtitle)
    assert Path(task.source_subtitle_path).name == "online.fixed.srt"
    assert Path(task.source_subtitle_path).read_text(encoding="utf-8") == subtitle.read_text(encoding="utf-8")
    assert task.source_asset_path == task.source_subtitle_path
    assert task.source_subtitle_lang == "en"
    assert payload["tasks"][0]["source_subtitle_name"] == "online.fixed.srt"
    assert payload["tasks"][0]["source_asset_name"] == "online.fixed.srt"


def test_generate_subtitle_uses_source_subtitle_override(tmp_path):
    module = load_plugin_module()
    plugin = make_plugin(module)
    video = tmp_path / "Movie.mkv"
    subtitle = tmp_path / "online.fixed.srt"
    video.write_bytes(b"video")
    subtitle.write_text("1\n00:00:01,000 --> 00:00:02,000\nHello\n", encoding="utf-8")

    ret, lang, path = plugin._AutoSubv3__generate_subtitle(
        str(video),
        str(tmp_path / "Movie"),
        source_subtitle_path=str(subtitle),
        source_subtitle_lang="en",
    )

    assert ret is True
    assert lang == "en"
    source_path, resolved_source = path
    assert source_path == subtitle
    assert resolved_source == module.ResolvedSource.MATCHED_EXTERNAL.value


def test_source_variant_suffixes_are_single_segment_for_player_compatibility(tmp_path):
    module = load_plugin_module()
    plugin = make_plugin(module)
    base = str(tmp_path / "Levius.S01E01")

    assert (
        module.AutoSubv3._AutoSubv3__translated_subtitle_path_with_variant(base, "ja", "bilingual", "aiasr")
        == f"{base}.chi&jp.aiasr.srt"
    )
    assert (
        module.AutoSubv3._AutoSubv3__translated_subtitle_path_with_variant(base, "en", "bilingual", "aiembedded")
        == f"{base}.chi&eng.aiembedded.srt"
    )
    assert (
        module.AutoSubv3._AutoSubv3__translated_subtitle_path_with_variant(base, "ko", "bilingual", "aimatch")
        == f"{base}.chi&kr.aimatch.srt"
    )

    default_path, default_variant = plugin._prepare_output_path(
        base,
        "ja",
        "bilingual",
        module.ResolvedSource.ASR.value,
        module.OverwritePolicy.SKIP.value,
    )
    variant_path, variant = plugin._prepare_output_path(
        base,
        "ja",
        "bilingual",
        module.ResolvedSource.ASR.value,
        module.OverwritePolicy.NEW_VARIANT.value,
    )

    assert default_path == f"{base}.chi&jp.ai.srt"
    assert default_variant == "ai"
    assert variant_path == f"{base}.chi&jp.aiasr.srt"
    assert variant == "aiasr"


def test_monitor_mode_accepts_subtitle_fallback_tasks(tmp_path):
    module = load_plugin_module()
    plugin = make_plugin(module)
    plugin._generation_mode = module.GenerationMode.MONITOR.value
    video = tmp_path / "Movie.mkv"
    video.write_bytes(b"video")

    result = plugin.submit_tasks(
        [str(video)],
        source=module.TaskSource.SUBTITLE_MANUAL_UPLOAD.value,
        trigger=module.TriggerType.SUBTITLE_FALLBACK.value,
    )

    assert len(result["added"]) == 1
    assert result["failed"] == []
    assert result["skipped"] == []
    assert len(plugin._tasks) == 1


def test_fallback_mode_accepts_subtitle_fallback_tasks(tmp_path):
    module = load_plugin_module()
    plugin = make_plugin(module)
    plugin._generation_mode = module.GenerationMode.FALLBACK.value
    video = tmp_path / "Movie.mkv"
    video.write_bytes(b"video")

    result = plugin.submit_tasks(
        [str(video)],
        source=module.TaskSource.SUBTITLE_MANUAL_UPLOAD.value,
        trigger=module.TriggerType.SUBTITLE_FALLBACK.value,
    )

    assert len(result["added"]) == 1
    assert len(plugin._tasks) == 1


def test_monitor_service_adds_new_media_task(tmp_path):
    module = load_plugin_module()
    plugin = make_plugin(module)
    plugin._generation_mode = module.GenerationMode.MONITOR.value
    video = tmp_path / "Movie.mkv"
    video.write_bytes(b"video")

    plugin._add_monitor_task(str(video))
    task = next(iter(plugin._tasks.values()))

    assert len(plugin._tasks) == 1
    assert task.video_file == str(video)
    assert task.source == module.TaskSource.EVENT
    assert task.trigger == module.TriggerType.MANUAL.value


def test_monitor_service_skips_new_media_when_subtitlemanualupload_takes_over(tmp_path):
    module = load_plugin_module()
    plugin = make_plugin(module)
    plugin._generation_mode = module.GenerationMode.MONITOR.value
    video = tmp_path / "Movie.mkv"
    video.write_bytes(b"video")

    class FakeSubtitleManualUpload:
        _auto_search_on_transfer = True
        _ai_link_enabled = True
        _auto_transfer_subtitle_strategy = "online_then_ai_source"

        def get_state(self):
            return True

    module.PluginManager = lambda: types.SimpleNamespace(
        running_plugins={"SubtitleManualUpload": FakeSubtitleManualUpload()}
    )

    plugin._add_monitor_task(str(video))

    assert plugin._tasks == {}


def test_run_at_once_adds_supported_media_from_directory(tmp_path):
    module = load_plugin_module()
    plugin = make_plugin(module)
    plugin._generation_mode = module.GenerationMode.MONITOR.value
    video = tmp_path / "Movie.mp4"
    ignored = tmp_path / "Movie.txt"
    video.write_bytes(b"video")
    ignored.write_text("ignored")

    plugin._run_at_once([str(tmp_path)])
    task = next(iter(plugin._tasks.values()))

    assert len(plugin._tasks) == 1
    assert task.video_file == str(video)
    assert task.source == module.TaskSource.MANUAL


def test_independent_monitor_is_blocked_when_subtitlemanualupload_auto_transfer_enabled():
    module = load_plugin_module()
    plugin = make_plugin(module)
    plugin._enabled = True
    plugin._running = True
    plugin._task_queue = queue.Queue()
    plugin._generation_mode = module.GenerationMode.MONITOR.value

    class FakeSubtitleManualUpload:
        _auto_search_on_transfer = True
        _ai_link_enabled = True
        _auto_transfer_subtitle_strategy = "online_then_ai_source"

        def get_state(self):
            return True

    module.PluginManager = lambda: types.SimpleNamespace(
        running_plugins={"SubtitleManualUpload": FakeSubtitleManualUpload()}
    )

    status = plugin._status_payload()

    assert status["independent_monitor_enabled"] is False
    assert status["independent_monitor_blocked_reason"] == "字幕匹配入库自动处理已启用"
    assert "接管" in status["message"]


def test_online_source_only_does_not_block_independent_monitor_when_ai_link_enabled():
    module = load_plugin_module()
    plugin = make_plugin(module)
    plugin._enabled = True
    plugin._running = True
    plugin._task_queue = queue.Queue()
    plugin._generation_mode = module.GenerationMode.MONITOR.value

    class FakeSubtitleManualUpload:
        _auto_search_on_transfer = True
        _ai_link_enabled = True
        _auto_transfer_subtitle_strategy = "online_source_only"

        def get_state(self):
            return True

    module.PluginManager = lambda: types.SimpleNamespace(
        running_plugins={"SubtitleManualUpload": FakeSubtitleManualUpload()}
    )

    status = plugin._status_payload()

    assert status["independent_monitor_enabled"] is True
    assert status["independent_monitor_blocked_reason"] == ""


def test_ai_source_only_blocks_independent_monitor_when_ai_link_enabled():
    module = load_plugin_module()
    plugin = make_plugin(module)
    plugin._enabled = True
    plugin._running = True
    plugin._task_queue = queue.Queue()
    plugin._generation_mode = module.GenerationMode.MONITOR.value

    class FakeSubtitleManualUpload:
        _auto_search_on_transfer = True
        _ai_link_enabled = True
        _auto_transfer_subtitle_strategy = "ai_source_only"

        def get_state(self):
            return True

    module.PluginManager = lambda: types.SimpleNamespace(
        running_plugins={"SubtitleManualUpload": FakeSubtitleManualUpload()}
    )

    status = plugin._status_payload()

    assert status["independent_monitor_enabled"] is False
    assert status["independent_monitor_blocked_reason"] == "字幕匹配入库自动处理已启用"


def test_online_source_only_without_ai_link_does_not_block_independent_monitor():
    module = load_plugin_module()
    plugin = make_plugin(module)
    plugin._enabled = True
    plugin._running = True
    plugin._task_queue = queue.Queue()
    plugin._generation_mode = module.GenerationMode.MONITOR.value

    class FakeSubtitleManualUpload:
        _auto_search_on_transfer = True
        _ai_link_enabled = False
        _auto_transfer_subtitle_strategy = "online_source_only"

        def get_state(self):
            return True

    module.PluginManager = lambda: types.SimpleNamespace(
        running_plugins={"SubtitleManualUpload": FakeSubtitleManualUpload()}
    )

    status = plugin._status_payload()

    assert status["independent_monitor_enabled"] is True
    assert status["independent_monitor_blocked_reason"] == ""


def test_submit_tasks_treats_reuse_source_policy_as_auto(tmp_path):
    module = load_plugin_module()
    plugin = make_plugin(module)
    video = tmp_path / "Movie.mkv"
    video.write_bytes(b"video")

    result = plugin.submit_tasks([str(video)], source_policy=module.SourcePolicy.REUSE.value)
    task = next(iter(plugin._tasks.values()))

    assert len(result["added"]) == 1
    assert task.source_policy == module.SourcePolicy.AUTO.value


def test_explicit_asr_source_policy_ignores_stale_subtitle_override(tmp_path):
    module = load_plugin_module()
    plugin = make_plugin(module)
    video = tmp_path / "Movie.mkv"
    subtitle = tmp_path / "stale.srt"
    video.write_bytes(b"video")
    subtitle.write_text("1\n00:00:01,000 --> 00:00:02,000\nWrong source\n", encoding="utf-8")

    result = plugin.submit_tasks(
        [str(video)],
        subtitle_overrides={
            str(video): {
                "subtitle_path": str(subtitle),
                "lang": "en",
                "source_policy": "asr",
            }
        },
    )
    task = next(iter(plugin._tasks.values()))

    assert len(result["added"]) == 1
    assert task.source_policy == module.SourcePolicy.ASR.value
    assert task.source_subtitle_path == ""
    assert task.source_asset_path == ""


def test_restart_completed_task_reuses_stable_matched_subtitle_asset(tmp_path):
    module = load_plugin_module()
    plugin = make_plugin(module)
    video = tmp_path / "Movie.mkv"
    subtitle = tmp_path / "online.fixed.srt"
    video.write_bytes(b"video")
    subtitle.write_text("1\n00:00:01,000 --> 00:00:02,000\nHello\n", encoding="utf-8")

    result = plugin.submit_tasks(
        [str(video)],
        source=module.TaskSource.SUBTITLE_MANUAL_UPLOAD.value,
        subtitle_overrides={
            str(video): {
                "subtitle_path": str(subtitle),
                "lang": "en",
                "source_policy": "matched_external",
                "overwrite_policy": "new_variant",
            }
        },
    )
    assert len(result["added"]) == 1
    original = next(iter(plugin._tasks.values()))
    plugin._task_queue.get_nowait()
    original.status = module.TaskStatus.COMPLETED
    original.complete_time = module.datetime.now()
    original.resolved_source = module.ResolvedSource.MATCHED_EXTERNAL.value
    original.source_lang = "en"

    restart = plugin.restart_tasks([original.task_id])
    rerun = [task for task in plugin._tasks.values() if task.rerun_of == original.task_id][0]

    assert len(restart["added"]) == 1
    assert rerun.source_policy == module.SourcePolicy.MATCHED_EXTERNAL.value
    assert Path(rerun.source_subtitle_path).exists()
    assert Path(rerun.source_subtitle_path).read_text(encoding="utf-8") == subtitle.read_text(encoding="utf-8")
    assert rerun.overwrite_policy == module.OverwritePolicy.BACKUP_REPLACE.value
    assert rerun.force_generate is True


def test_restart_reuse_preserves_output_variant_and_forces_generation(tmp_path):
    module = load_plugin_module()
    plugin = make_plugin(module)
    video = tmp_path / "Movie.mkv"
    video.write_bytes(b"video")
    assert plugin.add_task(str(video), module.TaskSource.MANUAL, source_policy=module.SourcePolicy.ASR.value)
    original = next(iter(plugin._tasks.values()))
    plugin._task_queue.get_nowait()
    original.status = module.TaskStatus.COMPLETED
    original.complete_time = module.datetime.now()
    original.output_variant = "aiasr"
    original.output_path = str(tmp_path / "Movie.chi&jp.aiasr.srt")

    result = plugin.restart_tasks([original.task_id])
    rerun = [task for task in plugin._tasks.values() if task.rerun_of == original.task_id][0]

    assert len(result["added"]) == 1
    assert rerun.force_generate is True
    assert rerun.output_variant == "aiasr"
    assert rerun.source_policy == module.SourcePolicy.ASR.value
    assert rerun.reuse_output_path == str(tmp_path / "Movie.chi&jp.aiasr.srt")
    assert rerun.overwrite_policy == module.OverwritePolicy.BACKUP_REPLACE.value


def test_prepare_output_path_uses_inherited_variant_for_backup_replace(tmp_path):
    module = load_plugin_module()
    plugin = make_plugin(module)
    base = str(tmp_path / "Movie")

    path, variant = plugin._prepare_output_path(
        base,
        "en",
        "bilingual",
        module.ResolvedSource.EMBEDDED.value,
        module.OverwritePolicy.BACKUP_REPLACE.value,
        inherited_variant="aimatch",
        inherited_output_path=str(tmp_path / "Movie.chi&jp.aimatch.srt"),
    )

    assert path == str(tmp_path / "Movie.chi&jp.aimatch.srt")
    assert variant == "aimatch"


def test_reuse_backup_replace_writes_original_output_path_even_when_lang_changes(tmp_path):
    module = load_plugin_module()
    plugin = make_plugin(module)
    video = tmp_path / "Movie.mkv"
    source_sub = tmp_path / "Movie.en.srt"
    output = tmp_path / "Movie.chi&jp.aiasr.srt"
    video.write_bytes(b"video")
    source_sub.write_text("1\n00:00:01,000 --> 00:00:02,000\nHello\n", encoding="utf-8")
    output.write_text("old subtitle", encoding="utf-8")

    plugin._AutoSubv3__generate_subtitle = lambda *args, **kwargs: (
        True,
        "en",
        (source_sub, module.ResolvedSource.ASR.value),
    )
    plugin._AutoSubv3__translate_zh_subtitle = lambda _lang, _src, dest, **_kwargs: Path(dest).write_text(
        "new subtitle",
        encoding="utf-8",
    )
    plugin._AutoSubv3__raise_if_task_cancelled = lambda: None
    plugin.is_video_skipped = lambda _path: False
    plugin.is_video_skip_chinese = lambda _path: False
    plugin._current_processing_task = module.TaskItem(
        task_id="rerun",
        video_file=str(video),
        source=module.TaskSource.MANUAL,
        add_time=module.datetime.now(),
    )

    status = plugin._AutoSubv3__process_autosub(
        str(video),
        force_generate=True,
        source_policy=module.SourcePolicy.ASR.value,
        overwrite_policy=module.OverwritePolicy.BACKUP_REPLACE.value,
        output_variant="aiasr",
        reuse_output_path=str(output),
        reuse_source_lang="ja",
    )

    assert status == module.TaskStatus.COMPLETED
    assert output.read_text(encoding="utf-8") == "new subtitle"
    assert Path(f"{output}.mp-ai-bk").read_text(encoding="utf-8") == "old subtitle"
    assert plugin._current_processing_task.output_path == str(output)
    assert plugin._current_processing_task.source_lang == "en"


def test_force_generate_retries_video_marked_no_audio(tmp_path):
    module = load_plugin_module()
    plugin = make_plugin(module)
    video = tmp_path / "Movie.mkv"
    source_sub = tmp_path / "Movie.asr.srt"
    video.write_bytes(b"video")
    source_sub.write_text("1\n00:00:01,000 --> 00:00:02,000\nHello\n", encoding="utf-8")
    plugin.add_skipped_video(str(video))
    called = {"generate": False}

    def fake_generate(*args, **kwargs):
        called["generate"] = True
        return True, "en", (source_sub, module.ResolvedSource.ASR.value)

    plugin._AutoSubv3__generate_subtitle = fake_generate
    plugin._AutoSubv3__translate_zh_subtitle = lambda _lang, _src, dest, **_kwargs: Path(dest).write_text(
        "new subtitle",
        encoding="utf-8",
    )
    plugin._AutoSubv3__raise_if_task_cancelled = lambda: None
    plugin.is_video_skip_chinese = lambda _path: False

    status = plugin._AutoSubv3__process_autosub(
        str(video),
        force_generate=True,
        source_policy=module.SourcePolicy.ASR.value,
        overwrite_policy=module.OverwritePolicy.NEW_VARIANT.value,
    )

    assert status == module.TaskStatus.COMPLETED
    assert called["generate"] is True
    assert (tmp_path / "Movie.chi&eng.aiasr.srt").exists()


def test_generation_pipeline_keeps_source_failure_reason_on_task(tmp_path):
    module = load_plugin_module()
    plugin = make_plugin(module)
    video = tmp_path / "Movie.mkv"
    video.write_bytes(b"video")
    plugin._current_processing_task = module.TaskItem(
        task_id="source-failure",
        video_file=str(video),
        source=module.TaskSource.MANUAL,
        add_time=module.datetime.now(),
    )
    plugin.is_video_skipped = lambda _path: False
    plugin.is_video_skip_chinese = lambda _path: False
    plugin._AutoSubv3__generate_subtitle = lambda *args, **kwargs: (False, "", None)

    status = plugin._AutoSubv3__process_autosub(str(video), force_generate=True)

    assert status == module.TaskStatus.FAILED
    assert "字幕源生成失败" in plugin._current_processing_task.error_message
    assert "Whisper 配置" in plugin._current_processing_task.error_message


def test_generation_pipeline_keeps_exception_type_and_message_on_task(tmp_path):
    module = load_plugin_module()
    plugin = make_plugin(module)
    video = tmp_path / "Movie.mkv"
    video.write_bytes(b"video")
    plugin._current_processing_task = module.TaskItem(
        task_id="api-failure",
        video_file=str(video),
        source=module.TaskSource.MANUAL,
        add_time=module.datetime.now(),
    )
    plugin.is_video_skipped = lambda _path: False
    plugin.is_video_skip_chinese = lambda _path: False

    def fail_generation(*args, **kwargs):
        raise RuntimeError("HTTP 401 invalid key")

    plugin._AutoSubv3__generate_subtitle = fail_generation

    status = plugin._AutoSubv3__process_autosub(str(video), force_generate=True)

    assert status == module.TaskStatus.FAILED
    assert plugin._current_processing_task.error_message == "RuntimeError: HTTP 401 invalid key"


def test_prefer_audio_keeps_first_audio_when_no_default_or_language_match():
    module = load_plugin_module()

    ok, audio_index, audio_lang = module.AutoSubv3._AutoSubv3__get_video_prefer_audio(
        {
            "streams": [
                {"codec_type": "audio", "tags": {"language": "ja"}, "disposition": {}},
                {"codec_type": "audio", "tags": {"language": "en"}, "disposition": {}},
            ]
        },
        prefer_lang=["fr"],
    )

    assert ok is True
    assert audio_index == 0
    assert audio_lang == "ja"


def test_prefer_audio_uses_requested_language_over_default():
    module = load_plugin_module()

    ok, audio_index, audio_lang = module.AutoSubv3._AutoSubv3__get_video_prefer_audio(
        {
            "streams": [
                {"codec_type": "audio", "tags": {"language": "ja"}, "disposition": {"default": 1}},
                {"codec_type": "audio", "tags": {"language": "en"}, "disposition": {}},
            ]
        },
        prefer_lang=["en", "eng"],
    )

    assert ok is True
    assert audio_index == 1
    assert audio_lang == "en"


def test_ffmpeg_extract_wav_maps_audio_stream_zero(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    module_path = root / "plugins.v2" / "autosubv3" / "ffmpeg" / "__init__.py"
    module_name = "autosubv3_ffmpeg_testpkg"
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    captured = {}

    class Result:
        returncode = 0

    def fake_run(command):
        captured["command"] = command
        return Result()

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    assert module.Ffmpeg.extract_wav_from_video("Movie.mkv", "Movie.wav", audio_index=0) is True
    assert "-map" in captured["command"]
    assert "0:a:0" in captured["command"]


def test_restart_reports_missing_matched_subtitle_source(tmp_path):
    module = load_plugin_module()
    plugin = make_plugin(module)
    video = tmp_path / "Movie.mkv"
    subtitle = tmp_path / "online.fixed.srt"
    video.write_bytes(b"video")
    subtitle.write_text("1\n00:00:01,000 --> 00:00:02,000\nHello\n", encoding="utf-8")
    assert plugin.add_task(
        str(video),
        module.TaskSource.SUBTITLE_MANUAL_UPLOAD,
        force_generate=True,
        source_subtitle_path=str(subtitle),
        source_subtitle_lang="en",
        source_policy=module.SourcePolicy.MATCHED_EXTERNAL.value,
    )
    task = next(iter(plugin._tasks.values()))
    plugin._task_queue.get_nowait()
    task.status = module.TaskStatus.COMPLETED
    task.complete_time = module.datetime.now()
    Path(task.source_asset_path).unlink()

    result = plugin.restart_tasks([task.task_id])

    assert result["added"] == []
    assert "原字幕匹配外挂源已不存在" in result["failed"][0]["reason"]


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


def test_bilingual_ai_subtitle_suffix_is_detected_as_existing_chinese_subtitle():
    module = load_plugin_module()

    with tempfile.TemporaryDirectory() as tmpdir:
        video_path = Path(tmpdir) / "Movie.mkv"
        subtitle_path = Path(tmpdir) / "Movie.chi&jp.ai.srt"
        video_path.write_bytes(b"video")
        subtitle_path.write_text("1\n00:00:01,000 --> 00:00:02,000\n你好\nこんにちは\n", encoding="utf-8")

        exists, lang, filename = module.AutoSubv3._AutoSubv3__external_subtitle_exists(
            str(video_path),
            prefer_langs=["zh", "chs"],
            only_srt=True,
            strict=True,
        )

    assert exists is True
    assert lang == "zh"
    assert filename == "Movie.chi&jp.ai.srt"


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


def test_config_vue_default_fields_match_backend_defaults():
    module = load_plugin_module()
    _, defaults = module.AutoSubv3().get_form()
    root = Path(__file__).resolve().parents[1]
    config_vue = (root / "plugins.v2" / "autosubv3" / "src" / "components" / "Config.vue").read_text(encoding="utf-8")
    match = re.search(r"const defaultConfig = \{(?P<body>.*?)\n\}", config_vue, re.S)
    assert match
    frontend_fields = set(re.findall(r"^\s{2}([A-Za-z_][A-Za-z0-9_]*)\s*:", match.group("body"), re.M))

    assert frontend_fields == set(defaults)


def test_task_store_loads_legacy_records_and_skips_bad_records():
    module = load_plugin_module()
    plugin = make_plugin(module)
    plugin._data["tasks"] = {
        "ok": {
            "task_id": "ok",
            "video_file": "/media/Movie.mkv",
            "source": module.TaskSource.MANUAL.value,
            "add_time": "2026-07-02T00:00:00",
            "status": module.TaskStatus.PENDING.value,
        },
        "bad": {
            "task_id": "bad",
            "video_file": "/media/Broken.mkv",
        },
    }

    tasks = plugin.load_tasks()

    assert set(tasks) == {"ok"}
    task = tasks["ok"]
    assert task.trigger == module.TriggerType.MANUAL.value
    assert task.source_policy == module.SourcePolicy.AUTO.value
    assert task.overwrite_policy == module.OverwritePolicy.SKIP.value
    assert task.cancel_requested is False


def test_task_store_keeps_skip_record_keys():
    module = load_plugin_module()
    plugin = make_plugin(module)

    plugin.add_skipped_video("/media/no-audio.mkv")
    plugin.add_skip_chinese_video("/media/chinese.mkv")

    assert "/media/no-audio.mkv" in plugin._data["skipped_videos"]
    assert plugin._data["skipped_videos"]["/media/no-audio.mkv"]["reason"] == "no_audio"
    assert "/media/chinese.mkv" in plugin._data["skip_chinese_videos"]
    assert plugin._data["skip_chinese_videos"]["/media/chinese.mkv"]["reason"] == "chinese"


def test_autosubv3_task_apis_are_registered():
    module = load_plugin_module()
    plugin = make_plugin(module)

    apis = {item["path"]: item for item in plugin.get_api()}

    assert {
        path: {
            "methods": apis[path]["methods"],
            "auth": apis[path]["auth"],
            "summary": apis[path]["summary"],
        }
        for path in apis
    } == {
        "/status": {
            "methods": ["GET"],
            "auth": "bear",
            "summary": "获取 AI 字幕生成联动状态",
        },
        "/submit": {
            "methods": ["POST"],
            "auth": "bear",
            "summary": "提交 AI 字幕生成任务",
        },
        "/tasks": {
            "methods": ["GET"],
            "auth": "bear",
            "summary": "获取 AI 字幕生成任务状态",
        },
        "/cancel": {
            "methods": ["POST"],
            "auth": "bear",
            "summary": "取消 AI 字幕生成任务",
        },
        "/delete": {
            "methods": ["POST"],
            "auth": "bear",
            "summary": "删除 AI 字幕任务记录",
        },
        "/restart": {
            "methods": ["POST"],
            "auth": "bear",
            "summary": "重新生成 AI 字幕任务",
        },
        "/models": {
            "methods": ["POST"],
            "auth": "bear",
            "summary": "获取 OpenAI 兼容接口模型列表",
        },
        "/test_model": {
            "methods": ["POST"],
            "auth": "bear",
            "summary": "测试 OpenAI 兼容模型是否可用",
        },
    }


def test_openai_model_config_apis_use_form_payload():
    module = load_plugin_module()
    plugin = make_plugin(module)
    api_module = sys.modules[f"{module.__name__}.tasks.api"]
    created = []

    class FakeRequest:
        def __init__(self, body):
            self._body = body

        async def json(self):
            return self._body

    class FakeOpenAi:
        def __init__(self, **kwargs):
            created.append(kwargs)
            self.model = kwargs.get("model") or "default-model"

        def list_models(self):
            return ["z-model", "a-model", "a-model"]

        def test_model(self):
            return "OK"

    api_module.OpenAi = FakeOpenAi
    api_module.settings = types.SimpleNamespace(PROXY={"https": "http://proxy.local:7890"})

    api = plugin._get_task_api()
    body = {
        "openai_url": "https://api.example.com/",
        "openai_key": "sk-test",
        "openai_model": "model-a",
        "openai_proxy": True,
        "compatible": True,
    }

    models = asyncio.run(api.api_models(FakeRequest(body)))
    test = asyncio.run(api.api_test_model(FakeRequest(body)))

    assert models["data"]["models"] == [
        {"title": "a-model", "value": "a-model"},
        {"title": "z-model", "value": "z-model"},
    ]
    assert models["data"]["count"] == 2
    assert test["data"] == {
        "model": "model-a",
        "reply": "OK",
        "endpoint_id": "",
        "endpoint_name": "",
    }
    assert created[0] == {
        "api_key": "sk-test",
        "api_url": "https://api.example.com",
        "proxy": {"https": "http://proxy.local:7890"},
        "model": None,
        "compatible": True,
    }
    assert created[1] == {
        "api_key": "sk-test",
        "api_url": "https://api.example.com",
        "proxy": {"https": "http://proxy.local:7890"},
        "model": "model-a",
        "compatible": True,
    }


def test_openai_model_test_requires_model_name():
    module = load_plugin_module()
    plugin = make_plugin(module)
    api_module = sys.modules[f"{module.__name__}.tasks.api"]

    class FakeRequest:
        async def json(self):
            return {
                "openai_url": "https://api.example.com",
                "openai_key": "sk-test",
                "openai_model": "",
            }

    try:
        asyncio.run(plugin._get_task_api().api_test_model(FakeRequest()))
    except api_module.HTTPException as exc:
        assert exc.status_code == 400
        assert exc.detail == "请先填写或选择模型"
    else:
        raise AssertionError("api_test_model should reject empty model")


def test_openai_model_config_apis_accept_endpoint_payload():
    module = load_plugin_module()
    plugin = make_plugin(module)
    api_module = sys.modules[f"{module.__name__}.tasks.api"]
    created = []

    class FakeRequest:
        async def json(self):
            return {
                "endpoint": {
                    "id": "backup",
                "name": "备用线路",
                "api_url": "https://backup.example.com/v1",
                "api_key": "sk-backup",
                "model": {"title": "backup-model", "value": "backup-model"},
                "use_proxy": False,
                "compatible": True,
                }
            }

    class FakeOpenAi:
        def __init__(self, **kwargs):
            created.append(kwargs)
            self.model = kwargs.get("model") or ""

        def list_models(self):
            return ["backup-model"]

        def test_model(self):
            return "OK"

    api_module.OpenAi = FakeOpenAi
    api = plugin._get_task_api()

    models = asyncio.run(api.api_models(FakeRequest()))
    tested = asyncio.run(api.api_test_model(FakeRequest()))

    assert models["data"]["endpoint_id"] == "backup"
    assert models["data"]["endpoint_name"] == "备用线路"
    assert tested["data"]["endpoint_id"] == "backup"
    assert tested["data"]["model"] == "backup-model"
    assert created[0]["api_url"] == "https://backup.example.com/v1"
    assert created[0]["model"] is None
    assert created[1]["model"] == "backup-model"
    assert created[1]["compatible"] is True


def test_openai_model_api_reports_sanitized_client_creation_error():
    module = load_plugin_module()
    plugin = make_plugin(module)
    api_module = sys.modules[f"{module.__name__}.tasks.api"]

    class FakeRequest:
        async def json(self):
            return {
                "endpoint": {
                    "api_url": "https://user:password@example.com/v1?token=sk-private",
                    "api_key": "sk-private",
                    "model": "model-a",
                }
            }

    class BrokenOpenAi:
        def __init__(self, **kwargs):
            raise ValueError(f"invalid endpoint {kwargs['api_url']} with {kwargs['api_key']}")

    api_module.OpenAi = BrokenOpenAi
    api = plugin._get_task_api()

    try:
        asyncio.run(api.api_models(FakeRequest()))
    except Exception as exc:
        assert exc.status_code == 502
        assert "sk-private" not in exc.detail
        assert "user:password" not in exc.detail
        assert "***" in exc.detail
    else:
        raise AssertionError("api_models should report client creation errors")


def test_openai_endpoint_config_migrates_legacy_fields_and_keeps_compatibility_mirror():
    module = load_plugin_module()
    endpoint_module = sys.modules[f"{module.__name__}.translate.openai_endpoints"]
    config = {
        "openai_url": "https://legacy.example.com",
        "openai_key": "sk-legacy",
        "openai_model": "legacy-model",
        "openai_proxy": True,
        "compatible": True,
    }

    endpoints, active_id, fallback_enabled = endpoint_module.normalize_openai_endpoints(config)
    changed = endpoint_module.apply_openai_endpoint_compatibility_fields(
        config,
        endpoints,
        active_id,
        fallback_enabled,
    )

    assert changed is True
    assert active_id == "default"
    assert fallback_enabled is True
    assert endpoints == [
        {
            "id": "default",
            "name": "默认线路",
            "api_url": "https://legacy.example.com",
            "api_key": "sk-legacy",
            "model": "legacy-model",
            "use_proxy": True,
            "compatible": True,
            "enabled": True,
        }
    ]
    assert config["openai_endpoints"] == endpoints
    assert config["openai_key"] == "sk-legacy"


def test_openai_endpoint_config_repairs_object_model_values():
    module = load_plugin_module()
    endpoint_module = sys.modules[f"{module.__name__}.translate.openai_endpoints"]
    config = {
        "openai_endpoints": [
            {
                "id": "grok",
                "name": "grok",
                "api_url": "https://gateway.example.com/v1",
                "api_key": "sk-test",
                "model": "{'title': 'grok-4.5', 'value': 'grok-4.5'}",
                "compatible": True,
                "enabled": True,
            }
        ],
        "openai_active_endpoint": "grok",
    }

    endpoints, active_id, fallback_enabled = endpoint_module.normalize_openai_endpoints(config)
    endpoint_module.apply_openai_endpoint_compatibility_fields(config, endpoints, active_id, fallback_enabled)

    assert endpoint_module.normalize_openai_model({"title": "LongCat-2.0", "value": "LongCat-2.0"}) == "LongCat-2.0"
    assert endpoint_module.normalize_openai_model("{'title': 'grok-4.5', 'value': 'grok-4.5'}") == "grok-4.5"
    assert endpoint_module.normalize_openai_model('[{"id": "model-a"}]') == "model-a"
    assert endpoint_module.normalize_openai_model("[object Object]") == ""
    assert endpoints[0]["model"] == "grok-4.5"
    assert config["openai_model"] == "grok-4.5"
    assert config["openai_endpoints"][0]["model"] == "grok-4.5"


def test_openai_endpoint_pool_falls_back_and_cools_failed_primary():
    module = load_plugin_module()
    endpoint_module = sys.modules[f"{module.__name__}.translate.openai_endpoints"]
    calls = []
    clock = [100.0]

    class FakeLogger:
        def warning(self, *args):
            pass

        def error(self, *args):
            pass

        def info(self, *args):
            pass

    class FakeClient:
        def __init__(self, **kwargs):
            self.name = kwargs["endpoint_name"]
            self.last_error = ""

        def translate_to_zh(self, text, context=None, max_retries=3):
            calls.append(self.name)
            if self.name == "主线路":
                self.last_error = "HTTP 401 invalid api key"
                return False, self.last_error
            return True, "翻译成功"

        def translate_batch_to_zh(self, texts, max_retries=3):
            return True, ["成功"] * len(texts)

    endpoints = [
        {"id": "primary", "name": "主线路", "api_url": "https://primary.example.com", "api_key": "k1", "model": "m1", "enabled": True},
        {"id": "backup", "name": "备用线路", "api_url": "https://backup.example.com", "api_key": "k2", "model": "m2", "enabled": True},
    ]
    pool = endpoint_module.OpenAiEndpointPool(
        endpoints,
        active_id="primary",
        fallback_enabled=True,
        proxy=None,
        logger=FakeLogger(),
        client_factory=FakeClient,
        time_func=lambda: clock[0],
    )

    first = pool.translate_to_zh("hello")
    second = pool.translate_to_zh("again")

    assert first == (True, "翻译成功")
    assert second == (True, "翻译成功")
    assert calls == ["主线路", "备用线路", "备用线路"]
    assert pool.last_error == ""


def test_openai_endpoint_pool_skips_client_that_failed_to_initialize():
    module = load_plugin_module()
    endpoint_module = sys.modules[f"{module.__name__}.translate.openai_endpoints"]
    calls = []

    class FakeLogger:
        def warning(self, *args):
            pass

        def error(self, *args):
            pass

        def debug(self, *args):
            pass

    class FakeClient:
        def __init__(self, **kwargs):
            self.name = kwargs["endpoint_name"]
            self.last_error = ""
            if self.name == "损坏线路":
                raise ValueError(f"bad endpoint {kwargs['api_url']} {kwargs['api_key']}")

        def translate_to_zh(self, text, context=None, max_retries=3):
            calls.append(self.name)
            return True, "备用成功"

        def translate_batch_to_zh(self, texts, max_retries=3):
            return True, ["备用成功"] * len(texts)

    endpoints = [
        {
            "id": "broken",
            "name": "损坏线路",
            "api_url": "https://bad.example.com?token=sk-bad",
            "api_key": "sk-bad",
            "model": "m1",
            "enabled": True,
        },
        {
            "id": "backup",
            "name": "备用线路",
            "api_url": "https://backup.example.com",
            "api_key": "sk-backup",
            "model": "m2",
            "enabled": True,
        },
    ]
    pool = endpoint_module.OpenAiEndpointPool(
        endpoints,
        active_id="broken",
        fallback_enabled=True,
        proxy=None,
        logger=FakeLogger(),
        client_factory=FakeClient,
    )

    assert pool.translate_to_zh("hello") == (True, "备用成功")
    assert calls == ["备用线路"]


def test_openai_endpoint_diagnostics_hide_url_credentials_and_api_key():
    module = load_plugin_module()
    endpoint_module = sys.modules[f"{module.__name__}.translate.openai_endpoints"]
    diagnostics_module = sys.modules[f"{module.__name__}.translate.api_diagnostics"]
    warnings = []

    class FakeLogger:
        def warning(self, *args):
            warnings.append(args)

        def error(self, *args):
            pass

        def debug(self, *args):
            pass

    class FakeClient:
        def __init__(self, **kwargs):
            self.last_error = ""

        def translate_to_zh(self, text, context=None, max_retries=3):
            self.last_error = "request rejected for sk-secret"
            return False, self.last_error

        def translate_batch_to_zh(self, texts, max_retries=3):
            return False, [None] * len(texts)

    endpoint = {
        "id": "primary",
        "name": "主线路",
        "api_url": "https://user:password@example.com/v1?api_key=sk-secret#debug",
        "api_key": "sk-secret",
        "model": "model-a",
        "enabled": True,
    }
    pool = endpoint_module.OpenAiEndpointPool(
        [endpoint],
        active_id="primary",
        fallback_enabled=True,
        proxy=None,
        logger=FakeLogger(),
        client_factory=FakeClient,
    )

    success, error = pool.translate_to_zh("hello")

    assert success is False
    assert "sk-secret" not in error
    assert "***" in error
    assert diagnostics_module.safe_api_url(endpoint["api_url"]) == "https://example.com/v1"
    assert diagnostics_module.safe_api_url("https://user:pass@example.com:bad/v1?secret=yes") == "https://example.com:bad/v1"
    rendered_warning = " ".join(str(item) for item in warnings[0])
    assert "user:password" not in rendered_warning
    assert "api_key=" not in rendered_warning


def test_queue_worker_preserves_specific_failure_message():
    module = load_plugin_module()
    queue_module = sys.modules[f"{module.__name__}.tasks.queue_worker"]
    event = threading.Event()
    task = module.TaskItem(
        task_id="task-error",
        video_file="/media/Movie.mkv",
        source=module.TaskSource.MANUAL,
        add_time=datetime.now(),
    )
    tasks = {task.task_id: task}

    def process_task(*args, **kwargs):
        worker.current_task.error_message = "备用线路：HTTP 429 rate limit"
        return module.TaskStatus.FAILED

    def save_tasks():
        if tasks[task.task_id].status == module.TaskStatus.FAILED:
            event.set()

    worker = queue_module.QueueWorker(
        event,
        lambda: tasks,
        save_tasks,
        process_task,
        lambda status: "字幕生成失败，请查看日志",
        types.SimpleNamespace(info=lambda *args: None, warning=lambda *args: None, error=lambda *args: None),
        task_queue=queue.Queue(),
    )
    worker.task_queue.put(task)

    worker.consume()

    assert task.status == module.TaskStatus.FAILED
    assert task.error_message == "备用线路：HTTP 429 rate limit"


def test_autosub_config_uses_parallel_basic_and_api_tabs():
    root = Path(__file__).resolve().parents[1]
    config_source = (root / "plugins.v2" / "autosubv3" / "src" / "components" / "Config.vue").read_text(encoding="utf-8")
    endpoint_source = (
        root / "plugins.v2" / "autosubv3" / "src" / "components" / "config" / "ApiEndpointSettings.vue"
    ).read_text(encoding="utf-8")
    task_table_source = (
        root / "plugins.v2" / "autosubv3" / "src" / "components" / "tasks" / "TaskTable.vue"
    ).read_text(encoding="utf-8")

    assert '<VTab value="basic"' in config_source
    assert '<VTab value="api"' in config_source
    assert "ApiEndpointSettings" in config_source
    assert "openai_endpoints" in config_source
    assert "openai_active_endpoint" in config_source
    assert "自动 fallback" in endpoint_source
    assert "添加线路" in endpoint_source
    assert "获取模型" in endpoint_source
    assert "测试 API" in endpoint_source
    assert "moveEndpoint" in endpoint_source
    assert "toggleEndpoint" in endpoint_source
    assert "normalizeModelValue" in endpoint_source
    assert "map(normalizeModelValue)" in endpoint_source
    assert 'item-title="title"' not in endpoint_source
    assert "至少保留一条启用线路" in endpoint_source
    assert "task-message-error" in task_table_source
    assert "VTooltip" in task_table_source


def test_autosub_release_metadata_versions_match():
    root = Path(__file__).resolve().parents[1]
    module = load_plugin_module()
    package = json.loads((root / "package.json").read_text(encoding="utf-8"))
    package_v2 = json.loads((root / "package.v2.json").read_text(encoding="utf-8"))
    plugin_package = json.loads(
        (root / "plugins.v2" / "autosubv3" / "package.json").read_text(encoding="utf-8")
    )
    readme = (root / "plugins.v2" / "autosubv3" / "README.md").read_text(encoding="utf-8")
    version = module.AutoSubv3.plugin_version

    assert version == "3.5.59"
    assert package["AutoSubv3"]["version"] == version
    assert package_v2["AutoSubv3"]["version"] == version
    assert plugin_package["version"] == version
    assert f"v{version}" in package["AutoSubv3"]["history"]
    assert f"v{version}" in package_v2["AutoSubv3"]["history"]
    assert f"## v{version} 更新" in readme


def test_task_api_payload_keeps_frontend_contract(tmp_path):
    module = load_plugin_module()
    plugin = make_plugin(module)
    video = tmp_path / "Movie.mkv"
    subtitle = tmp_path / "online.fixed.srt"
    output = tmp_path / "Movie.chi.ai.srt"
    video.write_bytes(b"video")
    subtitle.write_text("1\n00:00:01,000 --> 00:00:02,000\nHello\n", encoding="utf-8")

    result = plugin.submit_tasks(
        [str(video)],
        source=module.TaskSource.SUBTITLE_MANUAL_UPLOAD.value,
        subtitle_overrides={
            str(video): {
                "subtitle_path": str(subtitle),
                "lang": "en",
                "source_policy": "matched_external",
            }
        },
    )
    assert len(result["added"]) == 1
    plugin._task_queue.get_nowait()
    task = next(iter(plugin._tasks.values()))
    task.status = module.TaskStatus.COMPLETED
    task.complete_time = module.datetime.now()
    task.resolved_source = module.ResolvedSource.MATCHED_EXTERNAL.value
    task.source_lang = "en"
    task.output_path = str(output)
    task.output_variant = "ai"

    payload = plugin.tasks_payload(paths=[str(video)], limit=10)
    api_task = payload["tasks"][0]

    assert {
        "task_id",
        "video_file",
        "video_name",
        "source",
        "source_label",
        "force_generate",
        "source_subtitle_path",
        "source_subtitle_name",
        "source_subtitle_lang",
        "trigger",
        "source_policy",
        "source_policy_label",
        "resolved_source",
        "resolved_source_label",
        "source_asset_path",
        "source_asset_name",
        "source_lang",
        "output_path",
        "output_name",
        "output_variant",
        "reuse_output_path",
        "reuse_source_lang",
        "overwrite_policy",
        "rerun_of",
        "status",
        "status_label",
        "message",
        "queue_position",
        "add_time",
        "complete_time",
        "cancel_requested",
        "active",
    } <= set(api_task)
    assert {"status", "tasks"} <= set(payload)
    assert {
        "available",
        "enabled",
        "running",
        "queue_ready",
        "counts",
        "message",
        "updated_at",
    } <= set(payload["status"])
    assert api_task["video_name"] == "Movie.mkv"
    assert api_task["source_subtitle_name"] == "online.fixed.srt"
    assert api_task["source_asset_name"] == "online.fixed.srt"
    assert api_task["output_name"] == "Movie.chi.ai.srt"
    assert api_task["status"] == "completed"
    assert api_task["active"] is False
    assert api_task["cancel_requested"] is False


def test_autosubv3_layered_inventory_keeps_plugin_root_small():
    root = Path(__file__).resolve().parents[1]
    plugin_dir = root / "plugins.v2" / "autosubv3"

    assert {path.name for path in plugin_dir.glob("*.py")} == {"__init__.py"}
    for relative in {
        "core/models.py",
        "core/config_schema.py",
        "core/legacy_views.py",
        "core/compat_methods.py",
        "storage/task_store.py",
        "tasks/queue_worker.py",
        "tasks/task_service.py",
        "tasks/api.py",
        "pipeline/subtitle_output.py",
        "pipeline/source_resolver.py",
        "pipeline/asr_service.py",
        "pipeline/translation_service.py",
        "pipeline/generation_pipeline.py",
        "monitoring/monitor_service.py",
    }:
        assert (plugin_dir / relative).is_file()


def test_autosubv3_shell_stays_below_size_budget():
    root = Path(__file__).resolve().parents[1]
    init_path = root / "plugins.v2" / "autosubv3" / "__init__.py"
    source = init_path.read_text(encoding="utf-8-sig")
    tree = ast.parse(source)
    plugin_class = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "AutoSubv3"
    )
    direct_methods = {
        node.name
        for node in plugin_class.body
        if isinstance(node, ast.FunctionDef)
    }

    assert len(source.splitlines()) < 800
    assert len(direct_methods) <= 30
    assert {
        "__process_autosub",
        "__translate_zh_subtitle",
        "__do_speech_recognition",
        "_consume_tasks",
    }.isdisjoint(direct_methods)


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
                "last_error": "主线路：HTTP 429 rate limit",
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
        assert "HTTP 429 rate limit" in str(exc)
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


def test_asr_merge_splits_long_word_segments_by_duration_and_punctuation():
    module = load_plugin_module()
    plugin = make_plugin(module)
    plugin._max_segment_duration = 4
    plugin._max_segment_chars = 80
    module.etree.HTML = lambda _content: None

    words = [
        types.SimpleNamespace(index=1, start=timedelta(seconds=0), end=timedelta(seconds=0.6), content="Good"),
        types.SimpleNamespace(index=2, start=timedelta(seconds=0.6), end=timedelta(seconds=1.1), content="evening"),
        types.SimpleNamespace(index=3, start=timedelta(seconds=1.1), end=timedelta(seconds=1.5), content="and"),
        types.SimpleNamespace(index=4, start=timedelta(seconds=1.5), end=timedelta(seconds=2.2), content="welcome"),
        types.SimpleNamespace(index=5, start=timedelta(seconds=2.2), end=timedelta(seconds=2.7), content="to"),
        types.SimpleNamespace(index=6, start=timedelta(seconds=2.7), end=timedelta(seconds=3.5), content="GC-1"),
        types.SimpleNamespace(index=7, start=timedelta(seconds=3.5), end=timedelta(seconds=4.2), content="News"),
        types.SimpleNamespace(index=8, start=timedelta(seconds=4.2), end=timedelta(seconds=4.8), content="live"),
        types.SimpleNamespace(index=9, start=timedelta(seconds=4.8), end=timedelta(seconds=5.3), content="at"),
        types.SimpleNamespace(index=10, start=timedelta(seconds=5.3), end=timedelta(seconds=5.8), content="8:00."),
        types.SimpleNamespace(index=11, start=timedelta(seconds=5.8), end=timedelta(seconds=6.4), content="Our"),
        types.SimpleNamespace(index=12, start=timedelta(seconds=6.4), end=timedelta(seconds=7.1), content="top"),
        types.SimpleNamespace(index=13, start=timedelta(seconds=7.1), end=timedelta(seconds=7.8), content="story"),
        types.SimpleNamespace(index=14, start=timedelta(seconds=7.8), end=timedelta(seconds=8.4), content="tonight,"),
        types.SimpleNamespace(index=15, start=timedelta(seconds=8.4), end=timedelta(seconds=9.1), content="just-released"),
    ]

    merged = plugin._AutoSubv3__merge_srt(words)

    assert [item.index for item in merged] == list(range(1, len(merged) + 1))
    assert len(merged) >= 3
    assert all((item.end - item.start).total_seconds() <= 4.7 for item in merged)
    assert merged[0].content.endswith("GC-1")
    assert merged[1].content == "News live at 8:00."
