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
