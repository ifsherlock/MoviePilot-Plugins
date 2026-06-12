from __future__ import annotations

import asyncio
import importlib.util
import sys
import types
from pathlib import Path


def load_plugin_module():
    root = Path(__file__).resolve().parents[1]
    package_dir = root / "plugins.v2" / "subtitlemanualupload"

    class HTTPException(Exception):
        def __init__(self, status_code=500, detail=""):
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

    class PluginBase:
        def get_data_path(self):
            return root / ".tmp-test-data"

    class FakeTransferHistory:
        calls = 0
        data = []

        @classmethod
        def list_by_page(cls, **kwargs):
            cls.calls += 1
            return list(cls.data)

    class FakeSiteOper:
        data = []

        def list(self):
            return list(self.data)

    async def run_in_threadpool(func, *args, **kwargs):
        return func(*args, **kwargs)

    modules = {
        "fastapi": types.SimpleNamespace(HTTPException=HTTPException, Request=object),
        "starlette": types.ModuleType("starlette"),
        "starlette.concurrency": types.SimpleNamespace(run_in_threadpool=run_in_threadpool),
        "starlette.datastructures": types.SimpleNamespace(UploadFile=object),
        "app": types.ModuleType("app"),
        "app.core": types.ModuleType("app.core"),
        "app.core.config": types.SimpleNamespace(
            settings=types.SimpleNamespace(TMDB_IMAGE_DOMAIN="image.tmdb.org", RMT_MEDIAEXT={".mkv", ".mp4", ".strm"})
        ),
        "app.core.metainfo": types.SimpleNamespace(MetaInfoPath=lambda path: types.SimpleNamespace()),
        "app.db": types.ModuleType("app.db"),
        "app.db.site_oper": types.SimpleNamespace(SiteOper=FakeSiteOper),
        "app.db.models": types.ModuleType("app.db.models"),
        "app.db.models.transferhistory": types.SimpleNamespace(TransferHistory=FakeTransferHistory),
        "app.log": types.SimpleNamespace(
            logger=types.SimpleNamespace(
                info=lambda *args, **kwargs: None,
                warning=lambda *args, **kwargs: None,
                error=lambda *args, **kwargs: None,
            )
        ),
        "app.plugins": types.SimpleNamespace(_PluginBase=PluginBase),
    }
    for name, module in modules.items():
        sys.modules[name] = module

    package_name = "subtitlemanualupload_cache_testpkg"
    for name in list(sys.modules):
        if name == package_name or name.startswith(f"{package_name}."):
            sys.modules.pop(name, None)

    spec = importlib.util.spec_from_file_location(
        package_name,
        package_dir / "__init__.py",
        submodule_search_locations=[str(package_dir)],
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[package_name] = module
    spec.loader.exec_module(module)
    return module, FakeTransferHistory, FakeSiteOper


def make_plugin(module):
    plugin = module.SubtitleManualUpload.__new__(module.SubtitleManualUpload)
    plugin._local_entries_cache = {"loaded_at": None, "entries": [], "media_count": 0, "persisted": False}
    plugin._entry_map = module.OrderedDict()
    plugin._media_index_cache = module.OrderedDict()
    plugin._auto_transfer_tasks = module.OrderedDict()
    plugin._auto_transfer_worker = None
    plugin._auto_season_package_cache = module.OrderedDict()
    plugin._cache_refreshing = False
    plugin._cache_ttl_seconds = 1800
    plugin._cache_max_entries = 10
    plugin._entry_map_max_size = 2
    plugin._media_index_cache_max_keys = 20
    plugin._match_history_cache_ttl_seconds = 86400
    plugin._timeline_task_ttl_seconds = 86400
    plugin._match_history_cache = {"loaded_at": None, "signature": "", "items": [], "entry_count": 0, "persisted": False}
    plugin._timeline_tasks = module.OrderedDict()
    plugin._ai_link_enabled = False
    plugin._auto_skip_chinese_media_on_transfer = True
    plugin._auto_transfer_subtitle_strategy = "search_first"
    plugin._auto_search_min_score = 20
    plugin._online_provider_ids = ["assrt"]
    plugin._online_rate_records = {}
    plugin._online_rate_limit_per_minute = 5
    plugin._transfer_auto_dedupe_seconds = 300
    plugin._transfer_auto_recent = {}
    plugin._transfer_auto_lock = module.threading.Lock()
    plugin._tmdb_detail_cache = {}
    plugin._build_entry_from_history = lambda history: dict(history)
    for cache_file in [plugin._local_cache_file(), plugin._match_history_cache_file()]:
        if cache_file.exists():
            cache_file.unlink()
    return plugin


class FakeRequest:
    def __init__(self, body):
        self._body = body

    async def json(self):
        return self._body


def make_history_entry(tmp_path, entry_id, filename, **extra):
    path = tmp_path / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("video", encoding="utf-8")
    return {
        "id": entry_id,
        "path": str(path),
        "media_key": extra.pop("media_key", f"movie-{entry_id}"),
        **extra,
    }


def test_local_entries_cache_hits_until_forced_refresh(tmp_path):
    module, histories, _ = load_plugin_module()
    plugin = make_plugin(module)
    histories.calls = 0
    histories.data = [make_history_entry(tmp_path, "a", "a.mkv", media_key="movie-a")]

    first = plugin._load_local_entries()
    second = plugin._load_local_entries()
    forced = plugin._load_local_entries(force=True)

    assert first == second == forced
    assert histories.calls == 2
    assert plugin._cache_status()["entry_count"] == 1
    assert plugin._cache_status()["media_count"] == 1


def test_refresh_local_cache_rebuilds_entries(tmp_path):
    module, histories, _ = load_plugin_module()
    plugin = make_plugin(module)
    histories.calls = 0
    histories.data = [make_history_entry(tmp_path, "a", "a.mkv", media_key="movie-a")]
    plugin._load_local_entries()

    histories.data = [make_history_entry(tmp_path, "b", "b.mkv", media_key="movie-b")]
    refreshed = plugin._refresh_local_cache()

    assert [item["id"] for item in refreshed] == ["b"]
    assert list(plugin._entry_map.keys()) == ["b"]


def test_local_entries_cache_persists_between_plugin_instances(tmp_path):
    module, histories, _ = load_plugin_module()
    plugin = make_plugin(module)
    histories.calls = 0
    histories.data = [make_history_entry(tmp_path, "a", "a.mkv", media_key="movie-a")]

    first = plugin._load_local_entries()
    plugin2 = module.SubtitleManualUpload.__new__(module.SubtitleManualUpload)
    plugin2._local_entries_cache = {"loaded_at": None, "entries": [], "media_count": 0, "persisted": False}
    plugin2._entry_map = module.OrderedDict()
    plugin2._media_index_cache = module.OrderedDict()
    plugin2._cache_refreshing = False
    plugin2._cache_ttl_seconds = 1800
    plugin2._cache_max_entries = 10
    plugin2._entry_map_max_size = 2
    plugin2._media_index_cache_max_keys = 20
    plugin2._build_entry_from_history = lambda history: dict(history)

    restored = plugin2._load_local_entries()

    assert restored == first
    assert histories.calls == 1
    assert plugin2._cache_status()["persisted"] is True


def test_stale_persisted_cache_returns_before_background_refresh(tmp_path):
    module, histories, _ = load_plugin_module()
    plugin = make_plugin(module)
    old_time = module.datetime.now() - module.timedelta(seconds=1900)
    stale_path = tmp_path / "stale.mkv"
    stale_path.write_text("video", encoding="utf-8")
    plugin._local_entries_cache = {
        "loaded_at": old_time,
        "entries": [{"id": "stale", "path": str(stale_path), "media_key": "movie-stale"}],
        "media_count": 1,
        "persisted": True,
    }
    started = {"value": False}
    plugin._start_background_cache_refresh = lambda: started.update(value=True)

    entries = plugin._load_local_entries(allow_stale=True)

    assert [item["id"] for item in entries] == ["stale"]
    assert started["value"] is True


def test_transfer_event_entries_can_merge_into_local_cache(tmp_path):
    module, histories, _ = load_plugin_module()
    plugin = make_plugin(module)
    histories.calls = 0
    video = tmp_path / "Example.Show.S01E02.mkv"
    video.write_text("video")
    meta = types.SimpleNamespace(begin_season=1, begin_episode=2, episode_list=[2])
    mediainfo = types.SimpleNamespace(type="电视剧", title="Example Show", year="2024", tmdb_id=123)
    transferinfo = types.SimpleNamespace(file_list_new=[str(video)])

    entries = plugin._entries_from_transfer_event(
        {
            "meta": meta,
            "mediainfo": mediainfo,
            "transferinfo": transferinfo,
        }
    )
    plugin._merge_local_entries_cache(entries)

    assert len(entries) == 1
    assert entries[0]["media_type"] == "tv"
    assert entries[0]["season"] == 1
    assert entries[0]["episode"] == 2
    assert plugin._cache_status()["entry_count"] == 1


def test_entry_map_is_bounded_lru():
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)

    plugin._remember_targets([{"id": "a"}, {"id": "b"}, {"id": "c"}])
    plugin._remember_targets([{"id": "b"}])
    plugin._remember_targets([{"id": "d"}])

    assert list(plugin._entry_map.keys()) == ["b", "d"]


def test_online_download_name_prefers_archive_magic_over_filename_suffix():
    module, _, _ = load_plugin_module()
    cls = module.SubtitleManualUpload

    rar_named_zip = cls._normalize_online_download_name(
        "Spider-Man.Into.the.Spider-Verse.2018.1080p.WEB-DL.DD5.1.H264-FGT.zip",
        b"Rar!\x1a\x07\x00subtitle-data",
        {"title": "Spider-Man Into the Spider-Verse"},
    )
    zip_named_unknown = cls._normalize_online_download_name(
        "subtitle.bin",
        b"PK\x03\x04subtitle-data",
        {"title": "Spider-Man Into the Spider-Verse"},
    )

    assert rar_named_zip == "Spider-Man.Into.the.Spider-Verse.2018.1080p.WEB-DL.DD5.1.H264-FGT.rar"
    assert zip_named_unknown == "subtitle.zip"


def test_language_suffix_supports_bilingual_codes():
    module, _, _ = load_plugin_module()
    cls = module.SubtitleManualUpload

    assert cls._normalize_language_suffix("chi&eng") == "chi&eng"
    assert cls._normalize_language_suffix("zh/en") == "chi&eng"
    assert cls._normalize_language_suffix("chi+jpn") == "chi&jp"
    assert cls._normalize_language_suffix("chi,kor") == "chi&kr"
    assert cls._is_chinese_language_suffix("chi&eng") is True


def test_detect_language_profile_marks_bilingual_subtitles():
    module, _, _ = load_plugin_module()
    cls = module.SubtitleManualUpload

    chinese = "这是中文字幕文本" * 30
    english = " This is an English subtitle line" * 30
    japanese = "これは日本語字幕です" * 30
    korean = "이것은 한국어 자막입니다" * 30

    assert cls._detect_language_profile("movie.zh.en.srt", f"{chinese}{english}".encode())["suffix"] == "chi&eng"
    assert cls._detect_language_profile("movie.srt", f"{chinese}{japanese}".encode())["suffix"] == "chi&jp"
    assert cls._detect_language_profile("movie.srt", f"{chinese}{korean}".encode())["suffix"] == "chi&kr"


def test_detect_language_profile_prefers_suffix_token_before_subtitle_extension():
    module, _, _ = load_plugin_module()
    cls = module.SubtitleManualUpload

    name = "Jack.Reacher.Never.Go.Back.2016.1080p.KORSUB.HDRip.x264.AAC2.0-STUTTERSHIT.eng.srt"
    assert cls._detect_language_profile(name, b"")["suffix"] == "eng"
    assert cls._detect_language_profile("Example.Movie.2024.zh.en.ass", b"")["suffix"] == "chi&eng"


def test_strm_target_skips_timeline_fixing(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    session_dir = tmp_path / "session"
    session_dir.mkdir()
    video = tmp_path / "Movie.strm"
    video.write_text("http://example.invalid/movie.mkv", encoding="utf-8")
    source = tmp_path / "subtitle.srt"
    source.write_text("1\n00:00:01,000 --> 00:00:02,000\nHello\n", encoding="utf-8")
    destination = tmp_path / "Movie.chi.srt"

    results, fixed_count, _ = plugin._write_operations_to_disk(
        session_dir=session_dir,
        operations=[
            {
                "upload_info": {"upload_id": "u1", "source_name": "subtitle.srt", "archive_name": ""},
                "target_entry": {"id": "t1", "path": str(video), "basename": "Movie", "storage": "local"},
                "video_path": video,
                "source_path": source,
                "language_suffix": "chi",
                "destination_name": destination.name,
                "destination_path": destination,
            }
        ],
        fix_timeline=True,
    )

    assert destination.read_text(encoding="utf-8") == source.read_text(encoding="utf-8")
    assert fixed_count == 0
    assert results[0]["timeline"]["enabled"] is True
    assert results[0]["timeline"]["applied"] is False
    assert results[0]["timeline"]["base"] == "strm"
    task = plugin._timeline_task_for_target_id("t1")
    assert task["status"] == "skipped"
    assert task["timeline"]["base"] == "strm"
    assert plugin._timeline_tasks_for_entries([{"id": "t1"}])["summary"]["skipped"] == 1


def test_write_operations_passes_allow_risky_offset_to_timeline_fixer(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    session_dir = tmp_path / "session"
    session_dir.mkdir()
    video = tmp_path / "Movie.mkv"
    source = tmp_path / "subtitle.srt"
    destination = tmp_path / "Movie.chi.srt"
    video.write_text("video", encoding="utf-8")
    source.write_text("1\n00:00:01,000 --> 00:00:02,000\nHello\n", encoding="utf-8")
    captured = {}

    def fake_fix(video_path, subtitle_path, output_path, **kwargs):
        captured["kwargs"] = kwargs
        output_path.write_bytes(subtitle_path.read_bytes())
        return module.TimelineFixResult(
            enabled=True,
            applied=True,
            reason="timeline adjusted",
            base="audio:webrtc",
            offset_seconds=121.0,
            scale_factor=1.0,
            score=0.8,
        )

    module.fix_subtitle_timeline = fake_fix

    results, fixed_count, _ = plugin._write_operations_to_disk(
        session_dir=session_dir,
        operations=[
            {
                "upload_info": {"upload_id": "u1", "source_name": "subtitle.srt", "archive_name": ""},
                "target_entry": {"id": "t1", "path": str(video), "basename": "Movie", "storage": "local"},
                "video_path": video,
                "source_path": source,
                "language_suffix": "chi",
                "destination_name": destination.name,
                "destination_path": destination,
            }
        ],
        fix_timeline=True,
        allow_risky_offset=True,
    )

    assert destination.exists()
    assert fixed_count == 1
    assert results[0]["timeline"]["offset_seconds"] == 121.0
    assert captured["kwargs"]["allow_risky_offset"] is True


def test_target_payload_marks_strm_resources(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    video = tmp_path / "Movie.strm"
    video.write_text("http://example.invalid/movie.mkv", encoding="utf-8")

    target = plugin._target_from_entry(
        {"id": "t1", "path": str(video), "basename": "Movie", "target_label": "Movie", "storage": "local"}
    )

    assert target["path"] == str(video)
    assert target["is_stream"] is True


def test_ai_submit_skips_strm_without_requiring_autosub_plugin(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    video = tmp_path / "Movie.strm"
    video.write_text("http://example.invalid/movie.mkv", encoding="utf-8")

    result = plugin._submit_autosub_for_entries(
        [{"id": "t1", "path": str(video), "basename": "Movie", "target_label": "Movie", "storage": "local"}]
    )

    assert result["added"] == []
    assert result["failed"] == []
    assert result["skipped"][0]["reason"] == "STRM 资源暂不支持 AI 生成字幕"


def test_ai_restart_with_selected_external_subtitle_submits_matched_override(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    video = tmp_path / "Movie.mkv"
    subtitle = tmp_path / "Movie.eng.srt"
    video.write_text("video", encoding="utf-8")
    subtitle.write_text("1\n00:00:01,000 --> 00:00:02,000\nHello\n", encoding="utf-8")
    entry = {"id": "t1", "path": str(video), "basename": "Movie", "target_label": "Movie", "storage": "local"}
    captured = {}

    plugin._autosub_plugin = lambda: (types.SimpleNamespace(restart_tasks=lambda **kwargs: None), "")

    def fake_submit(entries, subtitle_overrides=None, **kwargs):
        captured["entries"] = entries
        captured["overrides"] = subtitle_overrides
        captured["submit_kwargs"] = kwargs
        return {"added": [{"path": entries[0]["path"]}], "skipped": [], "failed": [], "targets": [], "tasks": {}}

    plugin._submit_autosub_for_entries = fake_submit

    result = plugin._restart_autosub_for_entries(
        [entry],
        source_policy="matched_external",
        overwrite_policy="new_variant",
        source_subtitle_path=str(subtitle),
    )

    override = captured["overrides"][str(video)]
    assert result["added"]
    assert captured["entries"] == [entry]
    assert override["subtitle_path"] == str(subtitle)
    assert override["lang"] == "en"
    assert override["source_policy"] == "matched_external"
    assert override["source_name"] == subtitle.name
    assert captured["submit_kwargs"]["trigger"] == "manual"
    assert captured["submit_kwargs"]["source_policy"] == "matched_external"
    assert captured["submit_kwargs"]["overwrite_policy"] == "new_variant"


def test_ai_restart_rejects_external_subtitle_outside_current_target(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    video = tmp_path / "Movie.mkv"
    subtitle = tmp_path / "Other.eng.srt"
    video.write_text("video", encoding="utf-8")
    subtitle.write_text("1\n00:00:01,000 --> 00:00:02,000\nHello\n", encoding="utf-8")
    entry = {"id": "t1", "path": str(video), "basename": "Movie", "target_label": "Movie", "storage": "local"}

    try:
        plugin._restart_subtitle_override_for_entries([entry], source_subtitle_path=str(subtitle))
    except module.HTTPException as exc:
        assert exc.status_code == 400
        assert "当前集" in exc.detail
    else:
        raise AssertionError("should reject unrelated subtitle path")


def test_delete_single_subtitle_only_allows_target_subtitles(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    video = tmp_path / "Movie.mkv"
    subtitle = tmp_path / "Movie.chi.srt"
    unrelated = tmp_path / "Other.chi.srt"
    video.write_text("video", encoding="utf-8")
    subtitle.write_text("subtitle", encoding="utf-8")
    unrelated.write_text("other", encoding="utf-8")
    entry = {"id": "t1", "path": str(video), "basename": "Movie", "target_label": "Movie", "storage": "local"}
    plugin._remember_targets([entry])

    response = asyncio.run(
        plugin.api_delete_subtitle(FakeRequest({"target_id": "t1", "subtitle_path": str(subtitle)}))
    )

    assert response["success"] is True
    assert not subtitle.exists()
    assert unrelated.exists()


def test_delete_single_subtitle_rejects_locked_target(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    video = tmp_path / "Movie.mkv"
    subtitle = tmp_path / "Movie.chi.srt"
    video.write_text("video", encoding="utf-8")
    subtitle.write_text("subtitle", encoding="utf-8")
    entry = {"id": "t1", "path": str(video), "basename": "Movie", "target_label": "Movie", "storage": "local"}
    plugin._remember_targets([entry])

    try:
        asyncio.run(
            plugin.api_delete_subtitle(
                FakeRequest({"target_id": "t1", "subtitle_path": str(subtitle), "locked_target_ids": ["t1"]})
            )
        )
    except module.HTTPException as exc:
        assert exc.status_code == 423
        assert "锁定" in exc.detail
    else:
        raise AssertionError("locked target should reject subtitle deletion")

    assert subtitle.exists()


def test_search_media_candidates_returns_total_with_page_slice(tmp_path):
    module, histories, _ = load_plugin_module()
    plugin = make_plugin(module)
    histories.data = [
        make_history_entry(tmp_path, "a", "a.mkv", media_key="movie-a", media_type="movie", title="A", date="2024-01-01"),
        make_history_entry(tmp_path, "b", "b.mkv", media_key="movie-b", media_type="movie", title="B", date="2024-01-02"),
        make_history_entry(tmp_path, "c", "c.mkv", media_key="movie-c", media_type="movie", title="C", date="2024-01-03"),
    ]
    plugin._targets_for_media = lambda **kwargs: (_ for _ in ()).throw(
        AssertionError("media list search should not load target details")
    )

    candidates, total = asyncio.run(plugin._search_media_candidates(keyword="", media_type="movie", limit=2, offset=1))

    assert total == 3
    assert [item["title"] for item in candidates] == ["B", "A"]


def test_group_entries_exposes_thumbnail_poster_url():
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    entries = [
        {
            "id": "a",
            "path": "/media/a.mkv",
            "media_key": "movie-a",
            "media_type": "movie",
            "title": "A",
            "date": "2024-01-01",
            "poster_url": "https://image.tmdb.org/t/p/w500/poster.jpg",
        }
    ]

    groups = plugin._group_entries_as_media(entries, 0)

    assert groups[0]["poster_url"] == "https://image.tmdb.org/t/p/w500/poster.jpg"
    assert groups[0]["poster_thumb_url"] == "https://image.tmdb.org/t/p/w185/poster.jpg"


def test_search_media_candidates_reuses_media_index_cache(tmp_path):
    module, histories, _ = load_plugin_module()
    plugin = make_plugin(module)
    histories.data = [
        make_history_entry(tmp_path, "a", "a.mkv", media_key="movie-a", media_type="movie", title="A", date="2024-01-01"),
        make_history_entry(tmp_path, "b", "b.mkv", media_key="movie-b", media_type="movie", title="B", date="2024-01-02"),
        make_history_entry(tmp_path, "c", "c.mkv", media_key="movie-c", media_type="movie", title="C", date="2024-01-03"),
    ]
    calls = {"count": 0}
    original_group = plugin._group_entries_as_media

    def counted_group(entries, limit):
        calls["count"] += 1
        return original_group(entries, limit)

    plugin._group_entries_as_media = counted_group

    first, first_total = asyncio.run(plugin._search_media_candidates(keyword="", media_type="movie", limit=2, offset=0))
    second, second_total = asyncio.run(plugin._search_media_candidates(keyword="", media_type="movie", limit=2, offset=2))

    assert first_total == second_total == 3
    assert [item["title"] for item in first] == ["C", "B"]
    assert [item["title"] for item in second] == ["A"]
    assert calls["count"] == 1


def test_match_history_groups_targets_with_subtitles(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    video1 = tmp_path / "Show.S01E01.mkv"
    video2 = tmp_path / "Show.S01E02.mkv"
    sub1 = tmp_path / "Show.S01E01.chi.srt"
    sub2 = tmp_path / "Show.S01E02.eng.srt"
    for path in [video1, video2, sub1, sub2]:
        path.write_text("data", encoding="utf-8")
    plugin._local_entries_cache = {
        "loaded_at": module.datetime.now(),
        "entries": [
            {
                "id": "e1",
                "media_key": "tv-show",
                "media_type": "tv",
                "title": "Show",
                "path": str(video1),
                "basename": "Show.S01E01",
                "season": 1,
                "episode": 1,
                "target_label": "S01E01",
                "storage": "local",
            },
            {
                "id": "e2",
                "media_key": "tv-show",
                "media_type": "tv",
                "title": "Show",
                "path": str(video2),
                "basename": "Show.S01E02",
                "season": 1,
                "episode": 2,
                "target_label": "S01E02",
                "storage": "local",
            },
        ],
        "media_count": 1,
        "persisted": False,
    }

    items = plugin._match_history_items(keyword="", media_type="tv")

    assert len(items) == 1
    assert items[0]["subtitle_count"] == 2
    assert [target["episode"] for target in items[0]["targets"]] == [1, 2]


def test_match_history_cache_reuses_scanned_items_until_invalidated(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    video = tmp_path / "Movie.mkv"
    subtitle = tmp_path / "Movie.chi.srt"
    video.write_text("video", encoding="utf-8")
    subtitle.write_text("subtitle", encoding="utf-8")
    plugin._local_entries_cache = {
        "loaded_at": module.datetime.now(),
        "entries": [
            {
                "id": "m1",
                "media_key": "movie",
                "media_type": "movie",
                "title": "Movie",
                "path": str(video),
                "basename": "Movie",
                "target_label": "Movie",
                "storage": "local",
            }
        ],
        "media_count": 1,
        "persisted": False,
    }
    calls = {"count": 0}
    original = plugin._subtitle_files_for_target

    def counted_subtitles(entry):
        calls["count"] += 1
        return original(entry)

    plugin._subtitle_files_for_target = counted_subtitles

    first = plugin._match_history_items()
    second = plugin._match_history_items()
    plugin._invalidate_match_history_cache()
    third = plugin._match_history_items()

    assert first == second == third
    assert calls["count"] == 2


def test_match_history_filters_deleted_local_targets(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    video = tmp_path / "Movie.mkv"
    subtitle = tmp_path / "Movie.chi.srt"
    video.write_text("video", encoding="utf-8")
    subtitle.write_text("subtitle", encoding="utf-8")
    entry = {
        "id": "m1",
        "media_key": "movie",
        "media_type": "movie",
        "title": "Movie",
        "path": str(video),
        "basename": "Movie",
        "target_label": "Movie",
        "storage": "local",
    }
    plugin._local_entries_cache = {
        "loaded_at": module.datetime.now(),
        "entries": [entry],
        "media_count": 1,
        "persisted": False,
    }
    plugin._remember_targets([entry])

    assert len(plugin._match_history_items()) == 1

    video.unlink()
    assert plugin._match_history_items() == []
    assert plugin._cache_status()["entry_count"] == 0


def test_match_history_cache_invalidates_when_external_subtitle_changes(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    video = tmp_path / "Movie.mkv"
    video.write_text("video", encoding="utf-8")
    plugin._local_entries_cache = {
        "loaded_at": module.datetime.now(),
        "entries": [
            {
                "id": "m1",
                "media_key": "movie",
                "media_type": "movie",
                "title": "Movie",
                "path": str(video),
                "basename": "Movie",
                "target_label": "Movie",
                "storage": "local",
            }
        ],
        "media_count": 1,
        "persisted": False,
    }

    assert plugin._match_history_items() == []

    (tmp_path / "Movie.chi.srt").write_text("subtitle", encoding="utf-8")
    future = module.time.time() + 10
    module.os.utime(tmp_path, (future, future))

    items = plugin._match_history_items()
    assert len(items) == 1
    assert items[0]["subtitle_count"] == 1


def test_transfer_auto_dedupe_key_changes_when_same_path_is_reimported(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    entry = make_auto_entry(tmp_path)

    claimed, skipped = plugin._claim_transfer_auto_entries([entry])
    assert len(claimed) == 1
    assert skipped == 0

    claimed, skipped = plugin._claim_transfer_auto_entries([entry])
    assert claimed == []
    assert skipped == 1

    Path(entry["path"]).write_text("video reimported with different size", encoding="utf-8")
    claimed, skipped = plugin._claim_transfer_auto_entries([entry])
    assert len(claimed) == 1
    assert skipped == 0


def test_timeline_fix_existing_accepts_all_subtitles_for_target(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    video = tmp_path / "Movie.mkv"
    chi = tmp_path / "Movie.chi.srt"
    eng = tmp_path / "Movie.eng.srt"
    video.write_text("video", encoding="utf-8")
    chi.write_text("1\n00:00:01,000 --> 00:00:02,000\n你好\n", encoding="utf-8")
    eng.write_text("1\n00:00:01,000 --> 00:00:02,000\nHello\n", encoding="utf-8")
    entry = {
        "id": "m1",
        "media_key": "movie",
        "media_type": "movie",
        "title": "Movie",
        "path": str(video),
        "basename": "Movie",
        "target_label": "Movie",
        "storage": "local",
    }
    plugin._local_entries_cache = {
        "loaded_at": module.datetime.now(),
        "entries": [entry],
        "media_count": 1,
        "persisted": False,
    }
    plugin._remember_targets([entry])
    module.check_timeline_fixer_dependencies = lambda: {
        "available": True,
        "ffmpeg": True,
        "ffprobe": True,
        "modules": {},
    }

    class NoopThread:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        def start(self):
            return None

    original_thread = module.threading.Thread
    module.threading.Thread = NoopThread
    try:
        response = asyncio.run(plugin.api_timeline_fix_existing(FakeRequest({"items": [{"target_id": "m1"}]})))
    finally:
        module.threading.Thread = original_thread

    assert response["success"] is True
    assert response["data"]["accepted"] == 2
    assert response["data"]["summary"]["pending"] == 2
    assert response["data"]["task_by_target"]["m1"]["status"] == "pending"


def setup_online_ai_translate(plugin, module, tmp_path):
    video = tmp_path / "Movie.mkv"
    video.write_text("video", encoding="utf-8")
    entry = {
        "id": "m1",
        "path": str(video),
        "basename": "Movie",
        "filename": "Movie.mkv",
        "target_label": "Movie",
        "storage": "local",
    }
    plugin._remember_targets([entry])

    class FakeOnlineService:
        def download(self, results):
            return [
                {
                    "provider": "opensubtitles",
                    "source_name": "Movie.eng.srt",
                    "content": b"1\n00:00:01,000 --> 00:00:02,000\nHello\n",
                    "result": results[0],
                }
            ]

    captured = {}

    def fake_submit(entries, subtitle_overrides=None, **kwargs):
        captured["overrides"] = subtitle_overrides or {}
        captured["submit_kwargs"] = kwargs
        return {
            "added": [{"path": entries[0]["path"]}],
            "skipped": [],
            "failed": [],
            "targets": [plugin._target_from_entry(entries[0])],
            "tasks": {
                "status": {"available": True},
                "summary": {"total": 1, "active": 1, "pending": 1},
                "tasks": [{"target_id": "m1", "status": "pending"}],
                "task_by_target": {"m1": {"target_id": "m1", "status": "pending"}},
            },
        }

    def fake_fix(video_path, subtitle_path, output_path, **kwargs):
        captured["fix_kwargs"] = kwargs
        output_path.write_bytes(subtitle_path.read_bytes())
        return module.TimelineFixResult(
            enabled=True,
            applied=True,
            reason="test",
            base="audio",
            offset_seconds=1.0,
            scale_factor=1.0,
            score=0.95,
        )

    plugin._online_service = lambda: FakeOnlineService()
    plugin._submit_autosub_for_entries = fake_submit
    module.check_timeline_fixer_dependencies = lambda: {
        "available": True,
        "ffmpeg": "ffmpeg",
        "ffprobe": "ffprobe",
        "modules": {"pysubs2": True, "numpy": True},
    }
    module.fix_subtitle_timeline = fake_fix
    return entry, captured


def test_online_ai_translate_downloads_fixes_and_does_not_create_preview(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    entry, captured = setup_online_ai_translate(plugin, module, tmp_path)

    response = asyncio.run(
        plugin.api_online_download_preview(
            FakeRequest(
                {
                    "target_ids": ["m1"],
                    "submit_ai_translate": True,
                    "results": [
                        {
                            "provider": "opensubtitles",
                            "result_id": "r1",
                            "language_category": "english",
                            "title": "Movie English",
                        }
                    ],
                }
            )
        )
    )

    data = response["data"]
    assert response["success"] is True
    assert "session_id" not in data
    assert "items" not in data
    assert data["ai_translate"]["added"]
    assert data["tasks"]["task_by_target"]["m1"]["status"] == "pending"
    assert data["timeline_tasks"]["task_by_target"]["m1"]["status"] == "completed"
    assert data["fixed_subtitles"][0]["timeline"]["applied"] is True
    override = captured["overrides"][entry["path"]]
    assert Path(override["subtitle_path"]).exists()
    assert override["lang"] == "en"
    assert override["source_policy"] == "matched_external"
    assert override["timeline_fixed"] is True
    assert captured["submit_kwargs"]["trigger"] == "manual"
    assert captured["submit_kwargs"]["source_policy"] == "matched_external"
    assert captured["submit_kwargs"]["overwrite_policy"] == "new_variant"


def test_online_ai_submit_endpoint_downloads_fixes_and_does_not_create_preview(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    entry, captured = setup_online_ai_translate(plugin, module, tmp_path)

    response = asyncio.run(
        plugin.api_online_ai_submit(
            FakeRequest(
                {
                    "target_ids": ["m1"],
                    "results": [
                        {
                            "provider": "opensubtitles",
                            "result_id": "r1",
                            "language_category": "english",
                            "title": "Movie English",
                        }
                    ],
                }
            )
        )
    )

    data = response["data"]
    assert response["success"] is True
    assert "session_id" not in data
    assert "items" not in data
    assert data["ai_translate"]["added"]
    assert data["tasks"]["task_by_target"]["m1"]["status"] == "pending"
    assert data["timeline_tasks"]["task_by_target"]["m1"]["status"] == "completed"
    assert Path(captured["overrides"][entry["path"]]["subtitle_path"]).exists()
    assert captured["submit_kwargs"]["source_policy"] == "matched_external"


def test_online_ai_submit_can_allow_risky_offset_after_manual_confirm(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    _, captured = setup_online_ai_translate(plugin, module, tmp_path)

    response = asyncio.run(
        plugin.api_online_ai_submit(
            FakeRequest(
                {
                    "target_ids": ["m1"],
                    "allow_risky_offset": True,
                    "results": [
                        {
                            "provider": "opensubtitles",
                            "result_id": "r1",
                            "language_category": "english",
                            "title": "Movie English",
                        }
                    ],
                }
            )
        )
    )

    assert response["success"] is True
    assert captured["fix_kwargs"]["allow_risky_offset"] is True


def test_online_ai_submit_requires_timeline_fixer_before_download(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    video = tmp_path / "Movie.mkv"
    video.write_text("video", encoding="utf-8")
    plugin._remember_targets(
        [
            {
                "id": "m1",
                "path": str(video),
                "basename": "Movie",
                "filename": "Movie.mkv",
                "target_label": "Movie",
                "storage": "local",
            }
        ]
    )
    plugin._online_service = lambda: (_ for _ in ()).throw(AssertionError("timeline check should run before download"))
    module.check_timeline_fixer_dependencies = lambda: {
        "available": False,
        "ffmpeg": "",
        "ffprobe": "ffprobe",
        "modules": {"pysubs2": True},
    }

    try:
        asyncio.run(
            plugin.api_online_ai_submit(
                FakeRequest(
                    {
                        "target_ids": ["m1"],
                        "results": [
                            {
                                "provider": "opensubtitles",
                                "result_id": "r1",
                                "language_category": "english",
                                "title": "Movie English",
                            }
                        ],
                    }
                )
            )
        )
    except module.HTTPException as exc:
        assert exc.status_code == 409
        assert "智能调轴不可用" in exc.detail
    else:
        raise AssertionError("timeline dependency failure should block online AI submit")


def test_tmdb_aliases_reuse_online_title_cleaner():
    module, _, _ = load_plugin_module()

    aliases = module.SubtitleManualUpload._tmdb_aliases(
        [
            {"iso_639_1": "tr", "name": "Turkish", "english_name": "Turkish", "data": {"title": "Hayalet Sürücü"}},
            {"iso_639_1": "fi", "name": "suomi", "english_name": "Finnish", "data": {"title": ""}},
            {"iso_639_1": "en", "name": "English", "english_name": "English", "data": {"title": "Ghost Rider"}},
        ]
    )

    assert "Hayalet Sürücü" in aliases
    assert "Ghost Rider" in aliases
    assert "Turkish" not in aliases
    assert "suomi" not in aliases
    assert "Finnish" not in aliases


def test_tmdb_detail_payload_prefers_real_english_translation_title():
    module, _, _ = load_plugin_module()

    payload = module.SubtitleManualUpload._tmdb_detail_payload(
        {
            "original_language": "en",
            "origin_country": ["US"],
            "original_title": "The Lord of the Rings: The Return of the King",
            "translations": [
                {
                    "iso_639_1": "de",
                    "name": "Deutsch",
                    "english_name": "German",
                    "data": {"title": "Der Herr der Ringe - Die Rueckkehr des Koenigs"},
                },
                {
                    "iso_639_1": "en",
                    "name": "English",
                    "english_name": "English",
                    "data": {"title": "The Lord of the Rings: The Return of the King"},
                },
            ],
        }
    )

    assert payload["en_title"] == "The Lord of the Rings: The Return of the King"
    assert "Der Herr der Ringe - Die Rueckkehr des Koenigs" in payload["tmdb_aliases"]


def make_auto_entry(tmp_path, filename="Movie.mkv", **overrides):
    video = tmp_path / filename
    video.write_text("video", encoding="utf-8")
    entry = {
        "id": filename,
        "media_key": "movie-key",
        "media_type": "movie",
        "title": "Movie",
        "year": "2024",
        "tmdb_id": 123,
        "douban_id": "",
        "path": str(video),
        "basename": video.stem,
        "filename": video.name,
        "storage": "local",
        "library_name": "MoviePilot 入库事件",
        "target_label": video.name,
    }
    entry.update(overrides)
    return entry


def test_auto_transfer_queue_enqueues_tv_season_tasks_without_starting_immediately(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    plugin._ensure_transfer_auto_worker = lambda: None
    entries = [
        make_auto_entry(
            tmp_path,
            filename="Show.S01E01.mkv",
            media_key="tv-key",
            media_type="tv",
            title="Show",
            season=1,
            episode=1,
        ),
        make_auto_entry(
            tmp_path,
            filename="Show.S01E02.mkv",
            media_key="tv-key",
            media_type="tv",
            title="Show",
            season=1,
            episode=2,
        ),
    ]

    queued, skipped = plugin._enqueue_transfer_auto_entries(entries)
    snapshot = plugin._auto_transfer_queue_snapshot()

    assert queued == 2
    assert skipped == 0
    assert snapshot["summary"]["pending"] == 2
    assert len({task["group_key"] for task in snapshot["tasks"]}) == 1


def test_auto_transfer_group_prefers_season_package_then_single_episode(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    plugin._auto_skip_chinese_media_on_transfer = False
    entries = [
        make_auto_entry(
            tmp_path,
            filename="Show.S01E01.mkv",
            id="e1",
            media_key="tv-key",
            media_type="tv",
            title="Show",
            season=1,
            episode=1,
        ),
        make_auto_entry(
            tmp_path,
            filename="Show.S01E02.mkv",
            id="e2",
            media_key="tv-key",
            media_type="tv",
            title="Show",
            season=1,
            episode=2,
        ),
    ]
    calls = []
    plugin._auto_write_from_season_cache = lambda items: {"status": "skipped", "written_by_target": {}}

    def fake_season(items, task_ids=None):
        calls.append(("season", [item["id"] for item in items], list(task_ids or [])))
        return {
            "status": "written",
            "result": "Show S01 pack",
            "written_by_target": {"e1": {"path": "Show.S01E01.chi.srt"}},
            "candidate_count": 1,
            "search_results": 1,
        }

    def fake_single(entry, target, **kwargs):
        calls.append(("single", entry["id"], kwargs.get("queue_rate_limited")))
        return {"status": "written", "target": target.get("label"), "result": "single episode"}

    plugin._auto_search_write_season_package = fake_season
    plugin._auto_search_write_subtitle = fake_single

    results = plugin._auto_process_transfer_group(entries, task_ids=["t1", "t2"])

    assert calls == [("season", ["e1", "e2"], ["t1", "t2"]), ("single", "e2", True)]
    assert results["e1"]["season_package"] is True
    assert results["e2"]["result"] == "single episode"


def test_auto_transfer_group_accepts_season_ai_by_target(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    plugin._auto_skip_chinese_media_on_transfer = False
    entries = [
        make_auto_entry(tmp_path, filename="Show.S01E01.mkv", id="e1", media_key="tv-key", media_type="tv", title="Show", season=1, episode=1),
        make_auto_entry(tmp_path, filename="Show.S01E02.mkv", id="e2", media_key="tv-key", media_type="tv", title="Show", season=1, episode=2),
    ]
    calls = []
    plugin._auto_write_from_season_cache = lambda items: {"status": "skipped", "written_by_target": {}}
    plugin._auto_search_write_season_package = lambda items, task_ids=None: {
        "status": "written",
        "result": "Show S01 English pack",
        "written_by_target": {},
        "ai_by_target": {
            "e1": {"target_id": "e1", "subtitle_path": "Show.S01E01.fixed.srt"},
            "e2": {"target_id": "e2", "subtitle_path": "Show.S01E02.fixed.srt"},
        },
        "ai_translate": {"added": [{"path": entries[0]["path"]}, {"path": entries[1]["path"]}]},
        "candidate_count": 1,
        "search_results": 1,
    }

    def fake_single(entry, target, **kwargs):
        calls.append(entry["id"])
        return {"status": "written"}

    plugin._auto_search_write_subtitle = fake_single

    results = plugin._auto_process_transfer_group(entries, task_ids=["t1", "t2"])

    assert calls == []
    assert results["e1"]["status"] == "ai_submitted"
    assert results["e2"]["status"] == "ai_submitted"
    assert results["e1"]["fixed_subtitles"][0]["subtitle_path"].endswith("S01E01.fixed.srt")


def test_auto_season_package_tries_next_candidate_when_coverage_incomplete(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    plugin._online_provider_ids = ["opensubtitles"]
    entries = [
        make_auto_entry(tmp_path, filename="Show.S01E01.mkv", id="e1", media_key="tv-key", media_type="tv", title="Show", season=1, episode=1),
        make_auto_entry(tmp_path, filename="Show.S01E02.mkv", id="e2", media_key="tv-key", media_type="tv", title="Show", season=1, episode=2),
    ]

    class FakeSeasonService:
        def __init__(self):
            self.downloaded = []

        def search(self, **kwargs):
            return {
                "results": [
                    {"provider": "opensubtitles", "result_id": "partial", "title": "partial pack", "score": 90, "downloadable": True},
                    {"provider": "opensubtitles", "result_id": "full", "title": "full pack", "score": 89, "downloadable": True},
                ]
            }

        def download(self, selected):
            self.downloaded.append(selected[0]["result_id"])
            return [{"provider": "opensubtitles", "source_name": f"{selected[0]['result_id']}.zip", "content": b"zip", "result": selected[0]}]

    service = FakeSeasonService()
    plugin._online_service = lambda: service
    plugin._auto_wait_online_rate_limit = lambda *args, **kwargs: None
    plugin._auto_media_for_entry = lambda entry: {"media_type": "tv", "title": "Show", "year": "2024"}
    plugin._apply_tmdb_detail = lambda target, media: None
    plugin._extract_subtitle_files = lambda source_name, content, session_dir: [
        {"upload_id": source_name, "source_name": source_name, "stored_path": str(tmp_path / source_name), "ext": ".srt"}
    ]
    plugin._store_auto_season_package_cache = lambda *args, **kwargs: None

    def fake_write(**kwargs):
        selected_title = kwargs["selected_result"]["title"]
        if selected_title == "partial pack":
            return {
                "status": "written",
                "result": selected_title,
                "written_by_target": {"e1": {"path": "Show.S01E01.chi.srt"}},
                "completed_count": 1,
                "missing_target_ids": ["e2"],
                "coverage_complete": False,
            }
        return {
            "status": "written",
            "result": selected_title,
            "written_by_target": {
                "e1": {"path": "Show.S01E01.chi.srt"},
                "e2": {"path": "Show.S01E02.chi.srt"},
            },
            "completed_count": 2,
            "missing_target_ids": [],
            "coverage_complete": True,
        }

    plugin._auto_write_prepared_uploads_for_entries = fake_write

    result = plugin._auto_search_write_season_package(entries)

    assert service.downloaded == ["partial", "full"]
    assert result["result"] == "full pack"
    assert result["coverage_complete"] is True


def test_levius_season_package_requires_all_twelve_episodes(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    plugin._online_provider_ids = ["opensubtitles"]
    entries = [
        make_auto_entry(
            tmp_path,
            filename=f"Levius.S01E{episode:02d}.mkv",
            id=f"e{episode}",
            media_key="levius-tv-key",
            media_type="tv",
            title="Levius",
            season=1,
            episode=episode,
        )
        for episode in range(1, 13)
    ]

    class FakeSeasonService:
        def __init__(self):
            self.downloaded = []

        def search(self, **kwargs):
            return {
                "results": [
                    {"provider": "opensubtitles", "result_id": "levius-11", "title": "Levius pack 11 episodes", "score": 96, "downloadable": True},
                    {"provider": "opensubtitles", "result_id": "levius-12", "title": "Levius pack 12 episodes", "score": 95, "downloadable": True},
                ]
            }

        def download(self, selected):
            self.downloaded.append(selected[0]["result_id"])
            return [{"provider": "opensubtitles", "source_name": f"{selected[0]['result_id']}.zip", "content": b"zip", "result": selected[0]}]

    service = FakeSeasonService()
    plugin._online_service = lambda: service
    plugin._auto_wait_online_rate_limit = lambda *args, **kwargs: None
    plugin._auto_media_for_entry = lambda entry: {"media_type": "tv", "title": "Levius", "year": "2019"}
    plugin._apply_tmdb_detail = lambda target, media: None
    plugin._extract_subtitle_files = lambda source_name, content, session_dir: [
        {"upload_id": source_name, "source_name": source_name, "stored_path": str(tmp_path / source_name), "ext": ".srt"}
    ]
    plugin._store_auto_season_package_cache = lambda *args, **kwargs: None

    def fake_write(**kwargs):
        selected_title = kwargs["selected_result"]["title"]
        if "11 episodes" in selected_title:
            return {
                "status": "written",
                "result": selected_title,
                "written_by_target": {f"e{episode}": {"path": f"Levius.S01E{episode:02d}.chi.srt"} for episode in range(1, 12)},
                "completed_count": 11,
                "missing_target_ids": ["e12"],
                "coverage_complete": False,
            }
        return {
            "status": "written",
            "result": selected_title,
            "written_by_target": {
                f"e{episode}": {"path": f"Levius.S01E{episode:02d}.chi.srt"} for episode in range(1, 13)
            },
            "completed_count": 12,
            "missing_target_ids": [],
            "coverage_complete": True,
        }

    plugin._auto_write_prepared_uploads_for_entries = fake_write

    result = plugin._auto_search_write_season_package(entries)

    assert service.downloaded == ["levius-11", "levius-12"]
    assert result["result"] == "Levius pack 12 episodes"
    assert result["completed_count"] == 12
    assert result["coverage_complete"] is True
    assert set(result["written_by_target"]) == {f"e{episode}" for episode in range(1, 13)}


def test_auto_season_foreign_srt_submits_ai_as_subtitle_fallback(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    entries = [
        make_auto_entry(tmp_path, filename="Show.S01E01.mkv", id="e1", media_key="tv-key", media_type="tv", title="Show", season=1, episode=1),
        make_auto_entry(tmp_path, filename="Show.S01E02.mkv", id="e2", media_key="tv-key", media_type="tv", title="Show", season=1, episode=2),
    ]
    prepared_uploads = []
    for entry in entries:
        subtitle = tmp_path / f"{entry['basename']}.eng.srt"
        subtitle.write_text("1\n00:00:01,000 --> 00:00:02,000\nHello\n", encoding="utf-8")
        prepared_uploads.append(
            {
                "upload_id": entry["id"],
                "source_name": subtitle.name,
                "stored_path": str(subtitle),
                "ext": ".srt",
                "target_id": entry["id"],
            }
        )

    captured = {}
    plugin._auto_prepared_items_for_targets = lambda uploads, targets: [
        {
            "upload_id": item["upload_id"],
            "source_name": item["source_name"],
            "ext": ".srt",
            "target_id": item["target_id"],
            "language_suffix": "eng",
        }
        for item in uploads
    ]
    plugin._prepare_online_ai_subtitle_overrides = lambda **kwargs: (
        {entry["path"]: {"subtitle_path": str(tmp_path / f"{entry['basename']}.fixed.srt"), "lang": "en"} for entry in kwargs["target_entries"]},
        [{"target_id": entry["id"], "subtitle_path": str(tmp_path / f"{entry['basename']}.fixed.srt"), "autosub_lang": "en"} for entry in kwargs["target_entries"]],
    )

    def fake_submit(entries_arg, subtitle_overrides=None, **kwargs):
        captured["entries"] = entries_arg
        captured["overrides"] = subtitle_overrides
        captured["submit_kwargs"] = kwargs
        return {
            "added": [{"path": entry["path"]} for entry in entries_arg],
            "skipped": [],
            "failed": [],
        }

    plugin._submit_autosub_for_entries = fake_submit
    plugin._write_operations_to_disk = lambda **kwargs: (_ for _ in ()).throw(
        AssertionError("Foreign season package should be submitted to AI instead of written")
    )

    result = plugin._auto_write_prepared_uploads_for_entries(
        target_entries=entries,
        prepared_uploads=prepared_uploads,
        session_dir=tmp_path,
        selected_result={"provider": "opensubtitles", "title": "Show English pack"},
    )

    assert result["status"] == "written"
    assert result["ai_count"] == 2
    assert result["coverage_complete"] is True
    assert [entry["id"] for entry in captured["entries"]] == ["e1", "e2"]
    assert set(captured["overrides"]) == {entry["path"] for entry in entries}
    assert captured["submit_kwargs"]["trigger"] == "subtitle_fallback"
    assert captured["submit_kwargs"]["source_policy"] == "matched_external"
    assert captured["submit_kwargs"]["overwrite_policy"] == "new_variant"


def test_auto_transfer_rate_limit_is_tracked_per_provider(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    plugin._online_provider_ids = ["assrt", "opensubtitles"]
    plugin._auto_transfer_tasks["t1"] = {
        "id": "t1",
        "status": "in_progress",
        "active": True,
        "next_run_ts": 0,
        "message": "",
    }
    now = {"value": 1000.0}
    observed = {}
    original_time = module.time.time
    original_sleep = module.time.sleep
    module.time.time = lambda: now["value"]

    def fake_sleep(seconds):
        observed["next_run_ts"] = plugin._auto_transfer_tasks["t1"]["next_run_ts"]
        observed["message"] = plugin._auto_transfer_tasks["t1"]["message"]
        now["value"] += seconds

    module.time.sleep = fake_sleep
    try:
        plugin._online_rate_records = {"assrt": [941.0, 950.0, 960.0, 970.0, 980.0]}
        plugin._auto_wait_online_rate_limit(["assrt"], task_ids=["t1"])
    finally:
        module.time.time = original_time
        module.time.sleep = original_sleep

    assert observed["next_run_ts"] == 1001.0
    assert "assrt" in observed["message"]
    assert len(plugin._online_rate_records["assrt"]) == 5
    assert plugin._auto_transfer_tasks["t1"]["next_run_ts"] == 0


def test_auto_transfer_skips_chinese_media_by_tmdb_language(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    entry = make_auto_entry(tmp_path, title="流浪地球")
    plugin._tmdb_detail_for_media = lambda media: {"original_language": "zh", "origin_country": ["CN"]}
    plugin._auto_search_write_subtitle = lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("Chinese media should skip search")
    )
    plugin._auto_submit_ai_for_entry = lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("Chinese media should skip AI")
    )

    result = plugin._auto_process_transfer_entry(entry)

    assert result["status"] == "skipped"
    assert "中文资源自动跳过" in result["reason"]


def test_auto_transfer_chinese_title_is_not_skip_evidence_without_tmdb_match(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    entry = make_auto_entry(tmp_path, title="灰原同学的第二轮青春游戏", media_type="tv", season=1, episode=7)
    plugin._tmdb_detail_for_media = lambda media: {"original_language": "ja", "origin_country": ["JP"]}
    plugin._auto_search_write_subtitle = lambda item, target: {
        "status": "written",
        "target": target.get("label"),
        "result": "Haigakura S01E07",
    }
    plugin._auto_submit_ai_for_entry = lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("Written result should not trigger fallback AI")
    )

    result = plugin._auto_process_transfer_entry(entry)

    assert result["status"] == "written"
    assert result["result"] == "Haigakura S01E07"


def test_auto_transfer_search_first_falls_back_to_ai_when_search_is_uncertain(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    entry = make_auto_entry(tmp_path)
    plugin._auto_skip_chinese_media_on_transfer = False
    plugin._auto_search_write_subtitle = lambda item, target: {
        "status": "skipped",
        "target": target.get("label"),
        "reason": "高置信可下载结果数量为 0",
        "search_results": 0,
    }
    plugin._auto_submit_ai_for_entry = lambda item, target, reason: {
        "status": "ai_submitted",
        "target": target.get("label"),
        "reason": reason,
    }

    result = plugin._auto_process_transfer_entry(entry)

    assert result["status"] == "ai_submitted"
    assert result["search"]["search_results"] == 0


def test_auto_transfer_search_only_never_submits_ai(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    entry = make_auto_entry(tmp_path)
    plugin._auto_skip_chinese_media_on_transfer = False
    plugin._auto_transfer_subtitle_strategy = "search_only"
    plugin._auto_search_write_subtitle = lambda item, target: {
        "status": "skipped",
        "target": target.get("label"),
        "reason": "高置信可下载结果数量为 0",
    }
    plugin._auto_submit_ai_for_entry = lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("search_only should not submit AI")
    )

    result = plugin._auto_process_transfer_entry(entry)

    assert result["status"] == "skipped"
    assert result["strategy"] == "search_only"


def test_auto_transfer_ai_only_never_searches(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    entry = make_auto_entry(tmp_path)
    plugin._auto_skip_chinese_media_on_transfer = False
    plugin._auto_transfer_subtitle_strategy = "ai_only"
    plugin._auto_search_write_subtitle = lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("ai_only should not search")
    )
    plugin._auto_submit_ai_for_entry = lambda item, target, reason: {
        "status": "ai_submitted",
        "target": target.get("label"),
        "reason": reason,
    }

    result = plugin._auto_process_transfer_entry(entry)

    assert result["status"] == "ai_submitted"
    assert result["strategy"] == "ai_only"


def test_auto_transfer_ai_first_falls_back_to_search_only_when_ai_fails(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    entry = make_auto_entry(tmp_path)
    plugin._auto_skip_chinese_media_on_transfer = False
    plugin._auto_transfer_subtitle_strategy = "ai_first"
    plugin._auto_submit_ai_for_entry = lambda item, target, reason: {
        "status": "failed",
        "target": target.get("label"),
        "reason": "AI 插件不可用",
    }
    plugin._auto_search_write_subtitle = lambda item, target: {
        "status": "written",
        "target": target.get("label"),
        "result": "ASSRT subtitle",
    }

    result = plugin._auto_process_transfer_entry(entry)

    assert result["status"] == "written"
    assert result["ai"]["status"] == "failed"


def test_auto_transfer_existing_subtitle_skips_all_strategies(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    entry = make_auto_entry(tmp_path, filename="Movie.mkv")
    (tmp_path / "Movie.chi.srt").write_text("subtitle", encoding="utf-8")
    plugin._auto_search_write_subtitle = lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("existing subtitle should skip search")
    )
    plugin._auto_submit_ai_for_entry = lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("existing subtitle should skip AI")
    )

    result = plugin._auto_process_transfer_entry(entry)

    assert result["status"] == "skipped"
    assert result["reason"] == "目标已有外挂字幕"


def test_auto_search_write_uses_best_api_candidate_when_multiple_results(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    plugin._online_provider_ids = ["assrt", "opensubtitles"]
    entry = make_auto_entry(tmp_path, filename="Movie.mkv")
    subtitle = tmp_path / "Movie.chi.srt"
    subtitle.write_text("1\n00:00:01,000 --> 00:00:02,000\n你好\n", encoding="utf-8")

    class FakeAutoService:
        def __init__(self):
            self.downloaded = []

        def search(self, **kwargs):
            return {
                "results": [
                    {
                        "provider": "opensubtitles",
                        "result_id": "os-1",
                        "title": "Movie 2024 Chinese",
                        "score": 70,
                        "downloadable": True,
                        "language_category": "chinese",
                    },
                    {
                        "provider": "assrt",
                        "result_id": "assrt-1",
                        "title": "Movie 2024 English",
                        "score": 65,
                        "downloadable": True,
                        "language_category": "english",
                    },
                ]
            }

        def download(self, selected):
            self.downloaded = selected
            return [
                {
                    "provider": selected[0]["provider"],
                    "source_name": "Movie.chi.srt",
                    "content": subtitle.read_bytes(),
                    "result": selected[0],
                }
            ]

    service = FakeAutoService()
    plugin._online_service = lambda: service
    plugin._auto_search_keywords_for_entry = lambda item, target: ["Movie 2024"]
    plugin._extract_subtitle_files = lambda source_name, content, session_dir: [
        {
            "upload_id": "u1",
            "source_name": source_name,
            "stored_path": str(subtitle),
            "ext": ".srt",
        }
    ]
    plugin._build_write_operations = lambda *args, **kwargs: [{"ok": True}]
    plugin._write_operations_to_disk = lambda **kwargs: ([{"output_name": "Movie.chi.srt"}], 0, 0)
    plugin._auto_submit_ai_for_entry = lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("Chinese subtitle should not trigger AI")
    )

    result = plugin._auto_search_write_subtitle(entry)

    assert result["status"] == "written"
    assert result["candidate_count"] == 2
    assert service.downloaded[0]["result_id"] == "os-1"


def test_auto_search_write_chinese_subtitle_enables_timeline_fix(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    entry = make_auto_entry(tmp_path, filename="Movie.mkv")
    subtitle = tmp_path / "Movie.chi.srt"
    subtitle.write_text("1\n00:00:01,000 --> 00:00:02,000\n你好\n", encoding="utf-8")

    class FakeAutoService:
        def search(self, **kwargs):
            return {
                "results": [
                    {
                        "provider": "opensubtitles",
                        "result_id": "os-1",
                        "title": "Movie Chinese",
                        "score": 90,
                        "downloadable": True,
                        "language_category": "chinese",
                    }
                ]
            }

        def download(self, selected):
            return [
                {
                    "provider": selected[0]["provider"],
                    "source_name": "Movie.chi.srt",
                    "content": subtitle.read_bytes(),
                    "result": selected[0],
                }
            ]

    observed = {}
    plugin._online_service = lambda: FakeAutoService()
    plugin._auto_search_keywords_for_entry = lambda item, target: ["Movie 2024"]
    plugin._extract_subtitle_files = lambda source_name, content, session_dir: [
        {
            "upload_id": "u1",
            "source_name": source_name,
            "stored_path": str(subtitle),
            "ext": ".srt",
        }
    ]
    plugin._build_write_operations = lambda *args, **kwargs: [{"ok": True}]

    def fake_write(**kwargs):
        observed["fix_timeline"] = kwargs.get("fix_timeline")
        return [{"output_name": "Movie.chi.srt"}], 1, 0

    plugin._write_operations_to_disk = fake_write
    plugin._submit_autosub_for_entries = lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("Chinese subtitle should not trigger AI")
    )

    result = plugin._auto_search_write_subtitle(entry)

    assert result["status"] == "written"
    assert observed["fix_timeline"] is True


def test_auto_search_write_foreign_srt_submits_ai_without_writing(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    entry = make_auto_entry(tmp_path, filename="Movie.mkv")
    subtitle = tmp_path / "Movie.eng.srt"
    subtitle.write_text("1\n00:00:01,000 --> 00:00:02,000\nHello\n", encoding="utf-8")

    class FakeAutoService:
        def search(self, **kwargs):
            return {
                "results": [
                    {
                        "provider": "opensubtitles",
                        "result_id": "os-1",
                        "title": "Movie English",
                        "score": 90,
                        "downloadable": True,
                        "language_category": "english",
                    }
                ]
            }

        def download(self, selected):
            return [
                {
                    "provider": selected[0]["provider"],
                    "source_name": "Movie.eng.srt",
                    "content": subtitle.read_bytes(),
                    "result": selected[0],
                }
            ]

    captured = {}
    plugin._online_service = lambda: FakeAutoService()
    plugin._auto_search_keywords_for_entry = lambda item, target: ["Movie 2024"]
    plugin._extract_subtitle_files = lambda source_name, content, session_dir: [
        {
            "upload_id": "u1",
            "source_name": source_name,
            "stored_path": str(subtitle),
            "ext": ".srt",
        }
    ]
    plugin._write_operations_to_disk = lambda **kwargs: (_ for _ in ()).throw(
        AssertionError("Foreign SRT should be submitted to AI instead of written")
    )
    plugin._prepare_online_ai_subtitle_overrides = lambda **kwargs: (
        {entry["path"]: {"subtitle_path": str(subtitle), "lang": "en"}},
        [{"target_id": entry["id"], "subtitle_path": str(subtitle), "autosub_lang": "en"}],
    )

    def fake_submit(entries, subtitle_overrides=None, **kwargs):
        captured["overrides"] = subtitle_overrides
        captured["submit_kwargs"] = kwargs
        return {
            "added": [{"path": entries[0]["path"]}],
            "skipped": [],
            "failed": [],
            "tasks": {"task_by_target": {"e1": {"status": "pending"}}},
        }

    plugin._submit_autosub_for_entries = fake_submit

    result = plugin._auto_search_write_subtitle(entry)

    assert result["status"] == "ai_submitted"
    assert captured["overrides"][entry["path"]]["lang"] == "en"
    assert captured["submit_kwargs"]["trigger"] == "subtitle_fallback"
    assert captured["submit_kwargs"]["source_policy"] == "matched_external"
    assert captured["submit_kwargs"]["overwrite_policy"] == "new_variant"
    assert result["fixed_subtitles"][0]["autosub_lang"] == "en"


def test_auto_search_providers_use_only_unattended_api_sources():
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    plugin._online_provider_ids = ["subhd", "zimuku", "assrt", "opensubtitles"]

    assert plugin._auto_search_providers() == ["assrt", "opensubtitles"]


def test_transfer_auto_claim_dedupes_same_video_path(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    first = make_auto_entry(tmp_path, filename="Movie.mkv")
    duplicate = {**first}
    other = make_auto_entry(tmp_path, filename="Other.mkv")

    claimed, skipped = plugin._claim_transfer_auto_entries([first, duplicate, other])
    claimed_again, skipped_again = plugin._claim_transfer_auto_entries([first])

    assert [item["filename"] for item in claimed] == ["Movie.mkv", "Other.mkv"]
    assert skipped == 1
    assert claimed_again == []
    assert skipped_again == 1
