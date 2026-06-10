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
    plugin._cache_refreshing = False
    plugin._cache_ttl_seconds = 1800
    plugin._cache_max_entries = 10
    plugin._entry_map_max_size = 2
    plugin._media_index_cache_max_keys = 20
    plugin._ai_link_enabled = False
    plugin._auto_skip_chinese_media_on_transfer = True
    plugin._auto_transfer_subtitle_strategy = "search_first"
    plugin._auto_search_min_score = 20
    plugin._online_provider_ids = ["assrt"]
    plugin._tmdb_detail_cache = {}
    plugin._build_entry_from_history = lambda history: dict(history)
    cache_file = plugin._local_cache_file()
    if cache_file.exists():
        cache_file.unlink()
    return plugin


class FakeRequest:
    def __init__(self, body):
        self._body = body

    async def json(self):
        return self._body


def test_local_entries_cache_hits_until_forced_refresh():
    module, histories, _ = load_plugin_module()
    plugin = make_plugin(module)
    histories.calls = 0
    histories.data = [{"id": "a", "path": "/media/a.mkv", "media_key": "movie-a"}]

    first = plugin._load_local_entries()
    second = plugin._load_local_entries()
    forced = plugin._load_local_entries(force=True)

    assert first == second == forced
    assert histories.calls == 2
    assert plugin._cache_status()["entry_count"] == 1
    assert plugin._cache_status()["media_count"] == 1


def test_refresh_local_cache_rebuilds_entries():
    module, histories, _ = load_plugin_module()
    plugin = make_plugin(module)
    histories.calls = 0
    histories.data = [{"id": "a", "path": "/media/a.mkv", "media_key": "movie-a"}]
    plugin._load_local_entries()

    histories.data = [{"id": "b", "path": "/media/b.mkv", "media_key": "movie-b"}]
    refreshed = plugin._refresh_local_cache()

    assert [item["id"] for item in refreshed] == ["b"]
    assert list(plugin._entry_map.keys()) == ["b"]


def test_local_entries_cache_persists_between_plugin_instances():
    module, histories, _ = load_plugin_module()
    plugin = make_plugin(module)
    histories.calls = 0
    histories.data = [{"id": "a", "path": "/media/a.mkv", "media_key": "movie-a"}]

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


def test_stale_persisted_cache_returns_before_background_refresh():
    module, histories, _ = load_plugin_module()
    plugin = make_plugin(module)
    old_time = module.datetime.now() - module.timedelta(seconds=1900)
    plugin._local_entries_cache = {
        "loaded_at": old_time,
        "entries": [{"id": "stale", "path": "/media/stale.mkv", "media_key": "movie-stale"}],
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


def test_search_media_candidates_returns_total_with_page_slice():
    module, histories, _ = load_plugin_module()
    plugin = make_plugin(module)
    histories.data = [
        {"id": "a", "path": "/media/a.mkv", "media_key": "movie-a", "media_type": "movie", "title": "A", "date": "2024-01-01"},
        {"id": "b", "path": "/media/b.mkv", "media_key": "movie-b", "media_type": "movie", "title": "B", "date": "2024-01-02"},
        {"id": "c", "path": "/media/c.mkv", "media_key": "movie-c", "media_type": "movie", "title": "C", "date": "2024-01-03"},
    ]
    plugin._targets_for_media = lambda **kwargs: (_ for _ in ()).throw(
        AssertionError("media list search should not load target details")
    )

    candidates, total = asyncio.run(plugin._search_media_candidates(keyword="", media_type="movie", limit=2, offset=1))

    assert total == 3
    assert [item["title"] for item in candidates] == ["B", "A"]


def test_search_media_candidates_reuses_media_index_cache():
    module, histories, _ = load_plugin_module()
    plugin = make_plugin(module)
    histories.data = [
        {"id": "a", "path": "/media/a.mkv", "media_key": "movie-a", "media_type": "movie", "title": "A", "date": "2024-01-01"},
        {"id": "b", "path": "/media/b.mkv", "media_key": "movie-b", "media_type": "movie", "title": "B", "date": "2024-01-02"},
        {"id": "c", "path": "/media/c.mkv", "media_key": "movie-c", "media_type": "movie", "title": "C", "date": "2024-01-03"},
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


def test_auto_search_providers_excludes_opensubtitles():
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    plugin._online_provider_ids = ["assrt", "opensubtitles"]

    assert plugin._auto_search_providers() == ["assrt"]
