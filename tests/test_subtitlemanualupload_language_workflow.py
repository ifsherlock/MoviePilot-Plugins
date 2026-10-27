from __future__ import annotations

import hashlib
import io
import types
import zipfile
from collections import OrderedDict
from pathlib import Path
from unittest.mock import Mock

import pytest

from test_subtitlemanualupload_sup import make_bitmap_writer, make_upload_service, sup_modules  # noqa: F401


@pytest.fixture
def workflow(sup_modules, tmp_path):
    modules = sup_modules
    writer, owner, _ = make_bitmap_writer(modules, tmp_path)
    owner._traditional_to_simplified = False
    owner._auto_subtitle_language_strict = True
    owner._auto_subtitle_language_priority = ["chi&eng"]
    owner._auto_subtitle_format_priority = [".ass", ".srt"]
    owner._default_auto_language_priority = modules.language.DEFAULT_AUTO_LANGUAGE_PRIORITY
    owner._default_auto_format_priority = modules.language.DEFAULT_AUTO_FORMAT_PRIORITY
    owner._auto_multi_subtitle_mode = "best"
    owner._auto_transfer_subtitle_strategy = "online_then_ai_source"
    owner._auto_skip_chinese_media_on_transfer = False
    owner._subtitle_exts = modules.formats.SUBTITLE_EXTS
    owner._stream_exts = {".strm"}
    owner._timeline_allow_risky_offset = False
    owner._timeline_max_offset_seconds = 120
    owner._timeline_min_offset_seconds = 0.2
    owner._timeline_vad_mode = "webrtc"
    owner._set_timeline_task = Mock()
    owner._timeline_result_blocks_auto_write = lambda result: False
    owner._timeline_rejection_message = lambda result: ""
    owner._target_from_entry = lambda entry: {"label": entry.get("label", "")}
    owner._remove_ext_marks = Mock()
    owner._invalidate_match_history_cache = Mock()
    owner._subtitle_inventory = lambda: types.SimpleNamespace(invalidate_directory=Mock())
    owner._auto_search_min_score = 20
    owner._auto_season_package_cache = OrderedDict()
    owner._safe_int = lambda value, default=0: int(value or default)
    owner._hash_text = lambda value: hashlib.sha256(value.encode()).hexdigest()
    owner.get_data_path = lambda: tmp_path
    owner._apply_tmdb_detail = Mock()
    owner._extract_episode_hint = modules.load("catalog.target_normalizers").extract_episode_hint
    owner._normalize_auto_transfer_subtitle_strategy = modules.load("config.config_schema").normalize_auto_transfer_subtitle_strategy
    def timeline_fix(*, video_path, subtitle_path, output_path, **kwargs):
        import shutil
        shutil.copyfile(subtitle_path, output_path)
        return modules.timeline.TimelineFixResult(
            enabled=True, applied=False, reason="test timeline unchanged", base="audio", offset_seconds=0, scale_factor=1, score=1,
        )
    owner._run_timeline_fix = timeline_fix
    owner._subtitle_writer = lambda: writer
    upload = make_upload_service(modules, tmp_path)
    owner.services.upload_session = lambda: upload
    ai = Mock(side_effect=AssertionError("strict language policy must not submit AI"))
    language = modules.language
    detect = lambda name, raw: language.detect_language_profile(name, raw, modules.formats.SUBTITLE_EXTS)
    inventory = types.SimpleNamespace(embedded_subtitle_tracks_for_target=lambda entry: [])
    has_subtitle = lambda entry, target: language.auto_target_has_chinese_subtitle(
        entry, target, subtitle_inventory=inventory,
        language_priority=owner._auto_subtitle_language_priority, strict=owner._auto_subtitle_language_strict,
    )
    write_module = modules.load("auto_transfer.auto_transfer_write")
    strategy = write_module.AutoTransferWriteStrategy(owner, collaborators=write_module.AutoTransferWriteCollaborators(
        target_from_entry=lambda entry: entry,
        detect_language_profile=detect,
        write_operations_to_disk=writer.write_operations_to_disk,
        prepare_online_ai_subtitle_overrides=ai,
        submit_autosub_for_entries=ai,
        select_subtitle_items=lambda *args: strategy.select_subtitle_items(*args),
    ))
    online = Mock()
    processor_module = modules.load("auto_transfer.auto_transfer_processor")
    processor = processor_module.AutoTransferProcessor(owner, logger=Mock(), http_exception=ValueError,
        collaborators=processor_module.AutoTransferProcessorCollaborators(
            target_from_entry=lambda entry: entry,
            auto_target_has_chinese_subtitle=has_subtitle,
            chinese_transfer_media_evidence=lambda entry: (False, ""),
            media_for_transfer_entry=lambda entry: entry,
            search_providers=lambda: ["assrt"],
            search_keywords_for_entry=lambda *args: ["Show"],
            check_online_rate_limit=Mock(), wait_online_rate_limit=Mock(),
            online_service=lambda: online, online_download_name=lambda name, *_: name,
            extract_subtitle_files=upload.extract_subtitle_files,
            write_prepared_uploads_for_entries=strategy.write_prepared_uploads_for_entries,
            submit_autosub_for_entries=ai,
            call_search_write_subtitle=lambda *args, **kwargs: processor.search_write_subtitle(*args, **kwargs),
            submit_ai_for_entry=ai,
        ))
    season_module = modules.load("auto_transfer.auto_transfer_season")
    season = season_module.AutoTransferSeasonCache(owner, logger=Mock(),
        collaborators=season_module.AutoTransferSeasonCollaborators(
            target_from_entry=lambda entry: entry,
            auto_target_has_chinese_subtitle=has_subtitle,
            chinese_transfer_media_evidence=lambda entry: (False, ""),
            media_for_transfer_entry=lambda entry: entry,
            task_result_key=lambda entry: entry["id"],
            search_providers=lambda: ["assrt"], wait_online_rate_limit=Mock(),
            online_service=lambda: online, online_download_name=lambda name, *_: name,
            extract_subtitle_files=upload.extract_subtitle_files,
            write_prepared_uploads_for_entries=strategy.write_prepared_uploads_for_entries,
            store_cache=lambda *args: season.store_cache(*args),
            load_cache=lambda *args: season.load_cache(*args),
            write_from_cache=lambda *args: season.write_from_cache(*args),
            search_write_package=lambda *args, **kwargs: season.search_write_package(*args, **kwargs),
            process_entry=processor.process_entry,
        ))
    return types.SimpleNamespace(owner=owner, processor=processor, season=season, upload=upload, online=online, ai=ai, modules=modules)


def entry_for(tmp_path, episode=1):
    path = tmp_path / f"Show.S01E{episode:02d}.mkv"
    path.touch()
    return {"id": f"e{episode}", "path": str(path), "basename": path.stem, "filename": path.name,
            "label": path.stem, "title": "Show", "year": "2024", "media_key": "show-key",
            "media_type": "tv", "season": 1, "episode": episode, "storage": "local"}


def subtitle_zip(episodes=(1,), languages=("chi.jp", "chi.eng")):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        for episode in episodes:
            for language in languages:
                archive.writestr(f"Show.S01E{episode:02d}.{language}.srt", "1\n00:00:01,000 --> 00:00:02,000\n这是字幕。\nHello there.\n")
    return output.getvalue()


def serve_zip(workflow, content, titles=("Show 双语",)):
    workflow.online.search.return_value = {"results": [
        {"provider": "assrt", "result_id": str(index), "title": title, "score": 95-index, "downloadable": True}
        for index, title in enumerate(titles)
    ]}
    workflow.online.download.side_effect = lambda selected: [{"provider": "assrt", "source_name": "Show.zip", "content": content, "result": selected[0]}]


@pytest.mark.parametrize("mode", ["best", "chinese_all", "all"])
def test_strict_zip_writes_only_selected_pair(workflow, tmp_path, mode):
    workflow.owner._auto_multi_subtitle_mode = mode
    entry = entry_for(tmp_path)
    serve_zip(workflow, subtitle_zip(), ("Show 中日双语", "Show 双语"))
    result = workflow.processor.process_entry(entry)
    assert result["status"] == "written", result
    assert [path.name for path in tmp_path.glob("*.srt")] == ["Show.S01E01.chi&eng.srt"]
    assert "Hello there." in (tmp_path / "Show.S01E01.chi&eng.srt").read_text(encoding="utf-8")
    assert workflow.online.download.call_args.args[0][0]["title"] == "Show 双语"
    workflow.ai.assert_not_called()


@pytest.mark.parametrize("strategy", ["online_then_ai_source", "online_source_only", "ai_source_only"])
def test_strict_no_match_never_writes_or_submits_ai(workflow, tmp_path, strategy):
    workflow.owner._auto_transfer_subtitle_strategy = strategy
    serve_zip(workflow, subtitle_zip(languages=("chi.jp",)))
    result = workflow.processor.process_entry(entry_for(tmp_path))
    assert result["status"] == "skipped"
    assert list(tmp_path.glob("*.srt")) == []
    workflow.ai.assert_not_called()
    if strategy == "ai_source_only":
        workflow.online.search.assert_not_called()
    else:
        assert result["reason"] == "未找到符合语言要求的字幕"


def test_existing_other_pair_does_not_skip_selected_pair(workflow, tmp_path):
    entry = entry_for(tmp_path)
    entry["subtitles"] = [{"language_suffix": "chi&jp"}]
    serve_zip(workflow, subtitle_zip())
    assert workflow.processor.process_entry(entry)["status"] == "written"
    workflow.online.search.assert_called_once()
    entry["subtitles"].append({"language_suffix": "chi&eng"})
    assert workflow.processor.process_entry(entry)["reason"] == "目标已有所选语言字幕"
    workflow.online.search.assert_called_once()


def test_season_cache_rechecks_language_after_restart_and_preference_change(workflow, tmp_path):
    entries = [entry_for(tmp_path, 1), entry_for(tmp_path, 2)]
    serve_zip(workflow, subtitle_zip(episodes=(1, 2)))
    workflow.owner._auto_subtitle_language_priority = ["chi&jp"]
    initial = workflow.season.search_write_package(entries)
    assert initial["status"] == "written", initial
    assert initial["coverage_complete"] is True
    assert len(list(tmp_path.glob("*.chi&jp.srt"))) == 2
    workflow.owner._auto_season_package_cache.clear()
    workflow.owner._auto_subtitle_language_priority = ["chi&eng"]
    cached = workflow.season.write_from_cache(entries)
    assert cached["from_cache"] is True
    assert len(list(tmp_path.glob("*.chi&eng.srt"))) == 2
    workflow.owner._auto_subtitle_language_priority = ["chi&kr"]
    unmatched = workflow.season.write_from_cache(entries)
    assert unmatched["status"] == "skipped"
    assert list(tmp_path.glob("*.chi&kr.srt")) == []
    workflow.online.download.assert_called_once()
    workflow.ai.assert_not_called()


def test_language_config_round_trip_and_empty_validation(sup_modules):
    schema = sup_modules.load("config.config_schema")
    runtime = sup_modules.load("config.config_runtime")
    for priority in (["bilingual", "chi", "cht", "eng"], ["chi&eng"], ["jpn"], ["kor"]):
        config = schema.normalize_plugin_config({"auto_subtitle_language_priority": priority, "auto_subtitle_language_strict": True})
        owner = types.SimpleNamespace()
        runtime.apply_runtime_config(owner, config)
        saved = runtime.build_save_config_payload(owner)
        reloaded = schema.normalize_plugin_config(saved)
        assert reloaded["auto_subtitle_language_priority"] == config["auto_subtitle_language_priority"]
        assert reloaded["auto_subtitle_language_strict"] is True
    with pytest.raises(ValueError, match="至少选择一种语言"):
        schema.normalize_plugin_config({"auto_subtitle_language_priority": [], "auto_subtitle_language_strict": True})


def test_embedded_track_pair_title_is_exact_and_requires_explicit_pair_name(sup_modules):
    module = sup_modules.load("catalog.subtitle_inventory")
    language = sup_modules.language
    inventory = module.SubtitleInventory(
        subtitle_exts={".srt"}, stream_exts={".strm"}, embedded_text_codecs={"ass"},
        embedded_image_codecs={"pgs"}, embedded_probe_cache=OrderedDict(), embedded_probe_cache_max_size=5,
        trust_transfer_history_paths=False, normalize_text=language.normalize_text,
        normalize_language_suffix=language.normalize_language_suffix,
        detect_language_profile=lambda name, raw: language.detect_language_profile(name, raw, {".srt"}),
        is_chinese_language_suffix=language.is_chinese_language_suffix, safe_int=lambda value, default=0: default,
        subtitle_backup_path=lambda path: path, subprocess_module=types.SimpleNamespace(),
        logger_warning=lambda *args, **kwargs: None,
    )
    assert inventory.embedded_subtitle_language_suffix("chi", "中英双语") == "chi&eng"
    assert inventory.embedded_subtitle_language_suffix("eng", "English subtitles for Chinese dialogue") == "eng"
