from __future__ import annotations

import asyncio
import io
import importlib.util
import re
import sys
import types
import zipfile
from pathlib import Path

import pytest


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
    plugin._auto_transfer_stopping = False
    plugin._auto_season_package_cache = module.OrderedDict()
    module.SubtitleManualUpload._embedded_subtitle_probe_cache = module.OrderedDict()
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
    plugin._auto_transfer_subtitle_strategy = "online_then_ai_source"
    plugin._auto_multi_subtitle_mode = "best"
    plugin._auto_subtitle_language_priority = ["bilingual", "chi", "cht", "eng"]
    plugin._auto_subtitle_format_priority = [".ass", ".srt", ".ssa", ".vtt", ".webvtt", ".sbv", ".sub"]
    plugin._auto_ass_to_srt_for_ai = True
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


def plugin_submodule(module, name):
    return sys.modules[f"{module.__name__}.{name}"]


class FakeRequest:
    def __init__(self, body=None, query_params=None):
        self._body = {} if body is None else body
        self.query_params = query_params or {}

    async def json(self):
        return self._body


class FakeFormRequest:
    def __init__(self, form):
        self._form = form

    async def form(self):
        return self._form


class FakeForm:
    def __init__(self, values):
        self._values = dict(values)

    def get(self, key, default=None):
        return self._values.get(key, default)

    def getlist(self, key):
        value = self._values.get(key, [])
        return list(value) if isinstance(value, list) else [value]


def test_plugin_api_route_contract_is_stable():
    module, _, _ = load_plugin_module()
    plugin = module.SubtitleManualUpload.__new__(module.SubtitleManualUpload)

    route_contract = [
        (route["path"], tuple(route["methods"]), route.get("auth"), route.get("summary"))
        for route in plugin.get_api()
    ]

    assert route_contract == [
        ("/status", ("GET",), "bear", "获取字幕匹配插件状态"),
        ("/refresh_index", ("POST",), "bear", "兼容旧版刷新索引入口"),
        ("/search", ("GET",), "bear", "搜索 MoviePilot 本地资源候选"),
        ("/targets", ("GET",), "bear", "读取选中媒体的本地文件目标"),
        ("/match_history", ("GET",), "bear", "读取字幕匹配历史"),
        ("/timeline_tasks", ("POST",), "bear", "查询智能调轴任务状态"),
        ("/timeline_fix_existing", ("POST",), "bear", "对匹配历史中的外挂字幕执行智能调轴"),
        ("/auto_transfer_queue", ("GET",), "bear", "查询入库自动字幕处理队列"),
        ("/prepare_upload", ("POST",), "bear", "上传字幕并生成匹配预览"),
        ("/apply_upload", ("POST",), "bear", "应用字幕匹配结果并写入目标目录"),
        ("/clear_subtitles", ("POST",), "bear", "清空选中目标视频的外挂字幕"),
        ("/delete_subtitle", ("POST",), "bear", "删除单个已匹配外挂字幕"),
        ("/restore_subtitle_backup", ("POST",), "bear", "恢复智能调轴前的字幕备份"),
        ("/ai_submit", ("POST",), "bear", "提交 AI 字幕生成任务"),
        ("/ai_tasks", ("POST",), "bear", "查询当前资源的 AI 字幕生成任务状态"),
        ("/ai_cancel", ("POST",), "bear", "取消 AI 字幕生成任务"),
        ("/ai_restart", ("POST",), "bear", "重新生成 AI 字幕任务"),
        ("/online_status", ("GET",), "bear", "获取在线字幕源状态"),
        ("/online_manual_links", ("POST",), "bear", "生成在线字幕站手动搜索链接"),
        ("/online_search", ("POST",), "bear", "搜索在线字幕"),
        ("/online_search_provider", ("POST",), "bear", "搜索单个在线字幕源"),
        ("/online_ai_submit", ("POST",), "bear", "提交在线外语字幕到 AI 翻译状态队列"),
        ("/online_download_preview", ("POST",), "bear", "下载在线字幕并生成匹配预览"),
    ]


class FakeUpload:
    def __init__(self, filename, content):
        self.filename = filename
        self._content = content

    async def read(self):
        return self._content


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


def test_online_download_name_detects_7z_magic():
    module, _, _ = load_plugin_module()
    cls = module.SubtitleManualUpload

    assert cls._normalize_online_download_name(
        "download.bin",
        b"7z\xbc\xaf\x27\x1c" + b"payload",
        {"title": "Jack Reacher"},
    ) == "download.7z"


def test_upload_session_write_and_load_round_trips_payload(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    session_id = f"pytest-{module.SubtitleManualUpload._hash_text(str(tmp_path))[:8]}"
    payload = {
        "target_ids": ["t1"],
        "prepared_uploads": [{"upload_id": "u1", "source_name": "Movie.chi.srt"}],
    }

    plugin._write_session(session_id, payload)
    session_dir, loaded = plugin._load_session(session_id)

    try:
        assert session_dir == plugin._get_session_root() / session_id
        assert loaded == payload
    finally:
        module.shutil.rmtree(session_dir, ignore_errors=True)


def _zip_payload(entries):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, content in entries:
            archive.writestr(name, content)
    return buffer.getvalue()


def _limited_upload_session_service(module, tmp_path, **limit_overrides):
    upload_session = plugin_submodule(module, "upload_session")
    cls = module.SubtitleManualUpload
    limits = upload_session.ArchiveResourceLimits(**limit_overrides)
    return upload_session.UploadSessionService(
        data_path=tmp_path,
        subtitle_exts=cls._subtitle_exts,
        archive_exts=cls._archive_exts,
        rar_exts=cls._rar_exts,
        sevenzip_exts=cls._sevenzip_exts,
        default_session_hours=cls._default_session_hours,
        hash_text=cls._hash_text,
        extract_rar_subtitle_files=lambda *args, **kwargs: [],
        extract_7z_subtitle_files=lambda *args, **kwargs: [],
        resource_limits=limits,
    )


def test_upload_content_size_limit_rejects_single_subtitle(tmp_path):
    module, _, _ = load_plugin_module()
    service = _limited_upload_session_service(module, tmp_path, max_content_bytes=3)

    with pytest.raises(ValueError, match="上传内容大小超过限制"):
        service.extract_subtitle_files("movie.srt", b"1234", tmp_path)


def test_archive_member_count_limit_rejects_zip(tmp_path):
    module, _, _ = load_plugin_module()
    service = _limited_upload_session_service(
        module,
        tmp_path,
        max_content_bytes=1_000_000,
        max_archive_members=2,
    )
    payload = _zip_payload([("a.txt", b""), ("b.txt", b""), ("c.txt", b"")])

    with pytest.raises(ValueError, match="成员数量超过限制"):
        service.extract_subtitle_files("many.zip", payload, tmp_path)


def test_archive_member_size_limit_rejects_zip_subtitle(tmp_path):
    module, _, _ = load_plugin_module()
    service = _limited_upload_session_service(
        module,
        tmp_path,
        max_content_bytes=1_000_000,
        max_archive_member_bytes=3,
    )
    payload = _zip_payload([("movie.srt", b"1234")])

    with pytest.raises(ValueError, match="单文件大小超过限制"):
        service.extract_subtitle_files("sample.zip", payload, tmp_path)


def test_archive_total_size_limit_rejects_zip_subtitles(tmp_path):
    module, _, _ = load_plugin_module()
    service = _limited_upload_session_service(
        module,
        tmp_path,
        max_content_bytes=1_000_000,
        max_archive_member_bytes=100,
        max_archive_total_bytes=5,
    )
    payload = _zip_payload([("a.srt", b"123"), ("b.srt", b"456")])

    with pytest.raises(ValueError, match="总解压大小超过限制"):
        service.extract_subtitle_files("sample.zip", payload, tmp_path)


def test_archive_subtitle_count_limit_rejects_zip_subtitles(tmp_path):
    module, _, _ = load_plugin_module()
    service = _limited_upload_session_service(
        module,
        tmp_path,
        max_content_bytes=1_000_000,
        max_archive_member_bytes=100,
        max_archive_total_bytes=100,
        max_subtitle_files=1,
    )
    payload = _zip_payload([("a.srt", b"1"), ("b.srt", b"2")])

    with pytest.raises(ValueError, match="字幕文件数量超过限制"):
        service.extract_subtitle_files("sample.zip", payload, tmp_path)


def test_rarfile_resource_limit_error_does_not_fallback(tmp_path):
    module, _, _ = load_plugin_module()
    upload_session = plugin_submodule(module, "upload_session")
    fallback_called = False

    class FakeMember:
        filename = "movie.srt"
        file_size = 4

        def isdir(self):
            return False

    class FakeArchive:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def infolist(self):
            return [FakeMember()]

        def read(self, member):
            return b"1234"

    class FakeRarfileModule:
        @staticmethod
        def RarFile(path):
            return FakeArchive()

    def extract_with_rarfile(source_name, archive_path, session_dir, **kwargs):
        return upload_session.extract_rar_subtitle_files_with_rarfile(
            source_name,
            archive_path,
            session_dir,
            rarfile_module_factory=lambda: FakeRarfileModule,
            rar_python_package="rarfile",
            subtitle_exts={".srt"},
            hash_text=module.SubtitleManualUpload._hash_text,
            **kwargs,
        )

    def fallback_extract(*args, **kwargs):
        nonlocal fallback_called
        fallback_called = True
        return []

    limits = upload_session.ArchiveResourceLimits(max_archive_member_bytes=3)

    with pytest.raises(upload_session.ArchiveResourceLimitError, match="单文件大小超过限制"):
        upload_session.extract_rar_subtitle_files(
            "sample.rar",
            tmp_path / "sample.rar",
            tmp_path,
            rar_python_available_func=lambda: True,
            extract_with_rarfile=extract_with_rarfile,
            rar_tool_func=lambda: "7z",
            extract_command_archive_subtitle_files_func=fallback_extract,
            rar_python_package="rarfile",
            resource_limits=limits,
        )

    assert not fallback_called


def test_prepare_upload_uses_upload_session_service(tmp_path):
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
    plugin._extract_subtitle_files = lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("api_prepare_upload should call UploadSessionService directly")
    )
    form = FakeForm(
        {
            "target_ids": module.json.dumps(["m1"]),
            "files": [
                FakeUpload(
                    "Movie.chi.srt",
                    "1\n00:00:01,000 --> 00:00:02,000\n你好\n".encode("utf-8"),
                )
            ],
        }
    )

    prepare_endpoint = next(route["endpoint"] for route in plugin.get_api() if route["path"] == "/prepare_upload")
    response = asyncio.run(prepare_endpoint(FakeFormRequest(form)))

    data = response["data"]
    assert response["success"] is True
    assert data["source"] == "upload"
    assert data["items"][0]["source_name"] == "Movie.chi.srt"
    assert data["items"][0]["target_id"] == "m1"
    session_dir, session_payload = plugin._load_session(data["session_id"])
    assert session_payload["source"] == "upload"
    assert Path(session_payload["uploads"][0]["stored_path"]).is_file()
    module.shutil.rmtree(session_dir, ignore_errors=True)


def test_api_apply_upload_uses_subtitle_writer_and_forwards_risky_offset(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    video = tmp_path / "Movie.mkv"
    source = tmp_path / "Upload.srt"
    destination = tmp_path / "Movie.chi.srt"
    video.write_text("video", encoding="utf-8")
    source.write_text("1\n00:00:01,000 --> 00:00:02,000\n你好\n", encoding="utf-8")
    target = {
        "id": "m1",
        "path": str(video),
        "basename": "Movie",
        "filename": "Movie.mkv",
        "target_label": "Movie",
        "storage": "local",
    }
    plugin._write_session(
        "apply-writer",
        {
            "uploads": [
                {
                    "upload_id": "u1",
                    "source_name": source.name,
                    "archive_name": "",
                    "stored_path": str(source),
                    "ext": ".srt",
                }
            ],
            "targets": [target],
        },
    )
    plugin._write_operations_to_disk = lambda **kwargs: (_ for _ in ()).throw(
        AssertionError("api_apply_upload should call SubtitleWriter directly")
    )
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
            score=0.9,
            confidence="high",
        )

    module.fix_subtitle_timeline = fake_fix

    apply_endpoint = next(route["endpoint"] for route in plugin.get_api() if route["path"] == "/apply_upload")
    response = asyncio.run(
        apply_endpoint(
            FakeRequest(
                {
                    "session_id": "apply-writer",
                    "items": [
                        {
                            "upload_id": "u1",
                            "target_id": "m1",
                            "ext": ".srt",
                            "language_suffix": "chi",
                        }
                    ],
                    "fix_timeline": True,
                    "allow_risky_offset": True,
                }
            )
        )
    )

    assert response["success"] is True
    assert response["data"]["count"] == 1
    assert destination.exists()
    assert "智能调轴 1 个" in response["message"]
    assert captured["kwargs"]["allow_risky_offset"] is True


def test_online_download_preview_uses_upload_session_service(tmp_path):
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
    plugin._extract_subtitle_files = lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("api_online_download_preview should call UploadSessionService directly")
    )

    class FakeOnlineService:
        def download(self, selected):
            return [
                {
                    "provider": selected[0]["provider"],
                    "source_name": "Movie.eng.srt",
                    "content": b"1\n00:00:01,000 --> 00:00:02,000\nHello\n",
                    "result": selected[0],
                }
            ]

    plugin._online_service = lambda: FakeOnlineService()

    response = asyncio.run(
        plugin.api_online_download_preview(
            FakeRequest(
                {
                    "target_ids": ["m1"],
                    "results": [
                        {
                            "provider": "opensubtitles",
                            "result_id": "r1",
                            "title": "Movie English",
                        }
                    ],
                }
            )
        )
    )

    data = response["data"]
    assert response["success"] is True
    assert data["source"] == "online"
    assert data["items"][0]["source_name"] == "Movie.eng.srt"
    assert data["items"][0]["online_source"] == "opensubtitles"
    session_dir, session_payload = plugin._load_session(data["session_id"])
    assert session_payload["source"] == "online"
    assert Path(session_payload["uploads"][0]["stored_path"]).is_file()
    module.shutil.rmtree(session_dir, ignore_errors=True)


def test_extract_7z_subtitle_files_with_external_tool(tmp_path):
    module, _, _ = load_plugin_module()
    cls = module.SubtitleManualUpload
    original_sevenzip_tool = cls._sevenzip_tool
    original_run_archive_command = cls._run_archive_command
    cls._sevenzip_tool = classmethod(lambda inner_cls: "7z")

    def fake_run_archive_command(inner_cls, args, timeout=120):
        command = args[1]
        if command == "l":
            return (
                "Path = sample.7z\n"
                "Path = 说明.txt\n"
                "Path = Jack.Reacher.2012.chs&eng.ass\n"
                "Path = Jack.Reacher.2012.eng.ass\n"
            ).encode()
        if command == "x":
            member = args[-1]
            return f"[Script Info]\n; {member}\nDialogue: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,,你好".encode()
        raise AssertionError(args)

    cls._run_archive_command = classmethod(fake_run_archive_command)

    try:
        extracted = cls._extract_subtitle_files("sample.7z", b"7z\xbc\xaf\x27\x1c" + b"payload", tmp_path)
    finally:
        cls._sevenzip_tool = original_sevenzip_tool
        cls._run_archive_command = original_run_archive_command

    assert [item["source_name"] for item in extracted] == [
        "Jack.Reacher.2012.chs&eng.ass",
        "Jack.Reacher.2012.eng.ass",
    ]
    assert all(Path(item["stored_path"]).exists() for item in extracted)
    assert all(item["archive_name"] == "sample.7z" for item in extracted)


def test_language_suffix_supports_bilingual_codes():
    module, _, _ = load_plugin_module()
    language = plugin_submodule(module, "subtitle_language")
    cls = module.SubtitleManualUpload

    assert language.normalize_language_suffix("chi&eng") == "chi&eng"
    assert language.normalize_language_suffix("zh/en") == "chi&eng"
    assert language.normalize_language_suffix("chi+jpn") == "chi&jp"
    assert language.normalize_language_suffix("chi,kor") == "chi&kr"
    assert language.is_chinese_language_suffix("chi&eng") is True
    assert cls._normalize_language_suffix("zh/en") == "chi&eng"
    assert cls._is_chinese_language_suffix("chi&eng") is True


def test_detect_language_profile_marks_bilingual_subtitles():
    module, _, _ = load_plugin_module()
    language = plugin_submodule(module, "subtitle_language")
    cls = module.SubtitleManualUpload

    chinese = "这是中文字幕文本" * 30
    english = " This is an English subtitle line" * 30
    japanese = "これは日本語字幕です" * 30
    korean = "이것은 한국어 자막입니다" * 30

    assert language.detect_language_profile("movie.zh.en.srt", f"{chinese}{english}".encode(), cls._subtitle_exts)["suffix"] == "chi&eng"
    assert language.detect_language_profile("movie.srt", f"{chinese}{japanese}".encode(), cls._subtitle_exts)["suffix"] == "chi&jp"
    assert language.detect_language_profile("movie.srt", f"{chinese}{korean}".encode(), cls._subtitle_exts)["suffix"] == "chi&kr"
    assert cls._detect_language_profile("movie.zh.en.srt", f"{chinese}{english}".encode())["suffix"] == "chi&eng"


def test_detect_language_profile_prefers_suffix_token_before_subtitle_extension():
    module, _, _ = load_plugin_module()
    language = plugin_submodule(module, "subtitle_language")
    cls = module.SubtitleManualUpload

    name = "Jack.Reacher.Never.Go.Back.2016.1080p.KORSUB.HDRip.x264.AAC2.0-STUTTERSHIT.eng.srt"
    assert language.detect_language_profile(name, b"", cls._subtitle_exts)["suffix"] == "eng"
    assert language.detect_language_profile("Example.Movie.2024.zh.en.ass", b"", cls._subtitle_exts)["suffix"] == "chi&eng"
    assert cls._detect_language_profile(name, b"")["suffix"] == "eng"


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


def test_write_operations_rejects_low_confidence_timeline_result(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    session_dir = tmp_path / "session"
    session_dir.mkdir()
    video = tmp_path / "Movie.mkv"
    source = tmp_path / "subtitle.srt"
    destination = tmp_path / "Movie.chi.srt"
    video.write_text("video", encoding="utf-8")
    source.write_text("1\n00:00:01,000 --> 00:00:02,000\nHello\n", encoding="utf-8")

    def fake_fix(video_path, subtitle_path, output_path, **kwargs):
        output_path.write_bytes(subtitle_path.read_bytes())
        return module.TimelineFixResult(
            enabled=True,
            applied=False,
            reason="timeline alignment rejected",
            base="audio:rms",
            offset_seconds=-30.0,
            scale_factor=1.0,
            score=0.2,
            confidence="low",
            score_margin=0.0,
            risk_flags=["rms_low_precision"],
        )

    module.fix_subtitle_timeline = fake_fix

    try:
        plugin._write_operations_to_disk(
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
    except module.HTTPException as exc:
        assert exc.status_code == 409
        assert "智能调轴低可信" in exc.detail
    else:
        raise AssertionError("low confidence timeline result should block write")
    assert not destination.exists()
    assert plugin._timeline_task_for_target_id("t1")["status"] == "failed"


def test_low_confidence_timeline_result_blocks_auto_write():
    module, _, _ = load_plugin_module()

    result = module.TimelineFixResult(
        enabled=True,
        applied=False,
        reason="timeline alignment rejected",
        base="audio:rms",
        offset_seconds=-119.99,
        scale_factor=1.0,
        score=0.2,
        confidence="low",
        score_margin=0.0,
        risk_flags=["weak_score_margin", "rms_low_precision"],
    )

    assert module.SubtitleManualUpload._timeline_result_blocks_auto_write(result) is True


def test_offset_below_threshold_with_blocking_risk_still_blocks_auto_write():
    module, _, _ = load_plugin_module()

    result = module.TimelineFixResult(
        enabled=True,
        applied=False,
        reason="offset below threshold",
        base="audio:webrtc",
        offset_seconds=0.1,
        scale_factor=1.0,
        score=0.2,
        confidence="rejected",
        score_margin=0.0,
        risk_flags=["local_alignment_unstable"],
    )

    assert module.SubtitleManualUpload._timeline_result_blocks_auto_write(result) is True


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


def test_ai_submit_with_selected_external_subtitle_submits_matched_override(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    video = tmp_path / "Movie.mkv"
    subtitle = tmp_path / "Movie.eng.srt"
    video.write_text("video", encoding="utf-8")
    subtitle.write_text("1\n00:00:01,000 --> 00:00:02,000\nHello\n", encoding="utf-8")
    entry = {"id": "t1", "path": str(video), "basename": "Movie", "target_label": "Movie", "storage": "local"}
    plugin._remember_targets([entry])
    captured = {}

    class FakeBridge:
        def selected_external_subtitle_override_for_entries(self, entries, **kwargs):
            captured["selected_kwargs"] = kwargs
            return {
                entries[0]["path"]: {
                    "subtitle_path": kwargs["source_subtitle_path"],
                    "lang": "en",
                    "source_policy": "matched_external",
                    "source_name": Path(kwargs["source_subtitle_path"]).name,
                    "timeline_fixed": False,
                    "overwrite_policy": kwargs["overwrite_policy"],
                }
            }

        def submit_autosub_for_entries(self, entries, subtitle_overrides=None, **kwargs):
            captured["entries"] = entries
            captured["overrides"] = subtitle_overrides
            captured["submit_kwargs"] = kwargs
            return {"added": [{"path": entries[0]["path"]}], "skipped": [], "failed": [], "targets": [], "tasks": {}}

    plugin._submit_autosub_for_entries = lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("api_ai_submit should call AutoSubBridge directly")
    )
    plugin._autosub_bridge = lambda: FakeBridge()

    response = asyncio.run(
        plugin.api_ai_submit(
            FakeRequest(
                {
                    "target_ids": ["t1"],
                    "source_policy": "matched_external",
                    "source_subtitle_path": str(subtitle),
                    "overwrite_policy": "new_variant",
                }
            )
        )
    )

    override = captured["overrides"][str(video)]
    assert response["success"] is True
    assert captured["entries"] == [entry]
    assert override["subtitle_path"] == str(subtitle)
    assert override["lang"] == "en"
    assert override["source_policy"] == "matched_external"
    assert captured["selected_kwargs"]["source_subtitle_path"] == str(subtitle)
    assert captured["submit_kwargs"]["trigger"] == "manual"
    assert captured["submit_kwargs"]["source_policy"] == "matched_external"
    assert captured["submit_kwargs"]["overwrite_policy"] == "new_variant"


def test_ai_submit_with_asr_source_policy_forwards_source_choice(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    video = tmp_path / "Movie.mkv"
    video.write_text("video", encoding="utf-8")
    entry = {"id": "t1", "path": str(video), "basename": "Movie", "target_label": "Movie", "storage": "local"}
    plugin._remember_targets([entry])
    captured = {}

    class FakeBridge:
        def submit_autosub_for_entries(self, entries, subtitle_overrides=None, **kwargs):
            captured["entries"] = entries
            captured["overrides"] = subtitle_overrides
            captured["submit_kwargs"] = kwargs
            return {"added": [{"path": entries[0]["path"]}], "skipped": [], "failed": [], "targets": [], "tasks": {}}

    plugin._submit_autosub_for_entries = lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("api_ai_submit should call AutoSubBridge directly")
    )
    plugin._autosub_bridge = lambda: FakeBridge()

    response = asyncio.run(
        plugin.api_ai_submit(
            FakeRequest(
                {
                    "target_ids": ["t1"],
                    "source_policy": "asr",
                    "overwrite_policy": "new_variant",
                }
            )
        )
    )

    assert response["success"] is True
    assert captured["overrides"] is None
    assert captured["submit_kwargs"]["trigger"] == "manual"
    assert captured["submit_kwargs"]["source_policy"] == "asr"
    assert captured["submit_kwargs"]["overwrite_policy"] == "new_variant"


def test_autosub_tasks_for_entries_returns_all_tasks_by_target(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    video = tmp_path / "Movie.mkv"
    video.write_text("video", encoding="utf-8")
    entry = {"id": "t1", "path": str(video), "basename": "Movie", "target_label": "Movie", "storage": "local"}
    tasks = [
        {"task_id": "new-asr", "video_file": str(video), "status": "completed", "output_variant": "aiasr"},
        {"task_id": "old-match", "video_file": str(video), "status": "completed", "output_variant": "aimatch"},
        {"task_id": "old-embedded", "video_file": str(video), "status": "failed", "output_variant": "aiembedded"},
    ]
    fake_plugin = types.SimpleNamespace(
        _status_payload=lambda: {"available": True, "enabled": True},
        tasks_payload=lambda **kwargs: {"status": {"available": True}, "tasks": tasks},
    )
    plugin._ai_link_enabled = True
    plugin._autosub_plugin = lambda: (fake_plugin, "")

    result = plugin._autosub_tasks_for_entries([entry])

    assert [task["task_id"] for task in result["tasks"]] == ["new-asr", "old-match", "old-embedded"]
    assert result["task_by_target"]["t1"]["task_id"] == "new-asr"
    assert [task["task_id"] for task in result["tasks_by_target"]["t1"]] == ["new-asr", "old-match", "old-embedded"]
    assert result["summary"]["total"] == 3


def test_ai_restart_forwards_selected_task_ids_without_using_latest(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    video = tmp_path / "Movie.mkv"
    video.write_text("video", encoding="utf-8")
    entry = {"id": "t1", "path": str(video), "basename": "Movie", "target_label": "Movie", "storage": "local"}
    captured = {}

    class FakeAutoSub:
        def _status_payload(self):
            return {"available": True, "enabled": True}

        def tasks_payload(self, **kwargs):
            return {
                "status": {"available": True},
                "tasks": [
                    {"task_id": "latest-asr", "video_file": str(video), "status": "completed", "active": False},
                    {"task_id": "old-match", "video_file": str(video), "status": "completed", "active": False},
                ],
            }

        def restart_tasks(self, **kwargs):
            captured.update(kwargs)
            return {"added": [{"task_id": "old-match"}], "skipped": [], "failed": []}

    plugin._ai_link_enabled = True
    plugin._autosub_plugin = lambda: (FakeAutoSub(), "")

    result = plugin._restart_autosub_for_entries([entry], task_ids=["old-match"])

    assert captured["task_ids"] == ["old-match"]
    assert result["added"] == [{"task_id": "old-match"}]


def test_api_ai_restart_accepts_task_ids_without_target_ids(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    video = tmp_path / "Movie.mkv"
    video.write_text("video", encoding="utf-8")
    entry = {"id": "t1", "path": str(video), "basename": "Movie", "target_label": "Movie", "storage": "local"}
    plugin._remember_targets([entry])
    captured = {}

    def fake_restart(entries, **kwargs):
        captured["entries"] = entries
        captured["kwargs"] = kwargs
        return {"added": [{"task_id": "old-match"}], "skipped": [], "failed": [], "tasks": {}}

    class FakeBridge:
        def restart_autosub_for_entries(self, entries, **kwargs):
            return fake_restart(entries, **kwargs)

    plugin._restart_autosub_for_entries = lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("api_ai_restart should call AutoSubBridge directly")
    )
    plugin._autosub_bridge = lambda: FakeBridge()

    response = asyncio.run(plugin.api_ai_restart(FakeRequest({"task_ids": ["old-match"]})))

    assert response["success"] is True
    assert captured["entries"] == [entry]
    assert captured["kwargs"]["task_ids"] == ["old-match"]


def test_ai_restart_filters_task_ids_outside_current_target(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    video1 = tmp_path / "Episode1.mkv"
    video2 = tmp_path / "Episode2.mkv"
    video1.write_text("video", encoding="utf-8")
    video2.write_text("video", encoding="utf-8")
    entry1 = {"id": "e1", "path": str(video1), "basename": "Episode1", "target_label": "E01", "storage": "local"}
    entry2 = {"id": "e2", "path": str(video2), "basename": "Episode2", "target_label": "E02", "storage": "local"}
    captured = {}

    class FakeAutoSub:
        def _status_payload(self):
            return {"available": True, "enabled": True}

        def tasks_payload(self, **kwargs):
            return {
                "status": {"available": True},
                "tasks": [
                    {"task_id": "task-e1", "video_file": str(video1), "status": "completed", "active": False},
                    {"task_id": "task-e2", "video_file": str(video2), "status": "completed", "active": False},
                ],
            }

        def restart_tasks(self, **kwargs):
            captured.update(kwargs)
            return {"added": [{"task_id": "task-e1"}], "skipped": [], "failed": []}

    plugin._ai_link_enabled = True
    plugin._autosub_plugin = lambda: (FakeAutoSub(), "")

    result = plugin._restart_autosub_for_entries([entry1], task_ids=["task-e1", "task-e2"])

    assert captured["task_ids"] == ["task-e1"]
    assert result["skipped"][0]["task_id"] == "task-e2"
    assert "不属于当前可操作目标" in result["skipped"][0]["reason"]


def test_ai_restart_task_ids_for_locked_target_are_skipped(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    video = tmp_path / "Locked.mkv"
    video.write_text("video", encoding="utf-8")
    locked_entry = {"id": "locked", "path": str(video), "basename": "Locked", "target_label": "Locked", "storage": "local"}
    plugin._remember_targets([locked_entry])
    called = {"restart": False}

    class FakeAutoSub:
        def _status_payload(self):
            return {"available": True, "enabled": True}

        def tasks_payload(self, **kwargs):
            return {"status": {"available": True}, "tasks": []}

        def restart_tasks(self, **kwargs):
            called["restart"] = True
            return {"added": [], "skipped": [], "failed": []}

    plugin._ai_link_enabled = True
    plugin._autosub_plugin = lambda: (FakeAutoSub(), "")

    response = asyncio.run(
        plugin.api_ai_restart(
            FakeRequest({"task_ids": ["locked-task"], "locked_target_ids": ["locked"]})
        )
    )

    assert response["success"] is True
    assert called["restart"] is False
    assert response["data"]["skipped"][0]["task_id"] == "locked-task"


def test_ai_restart_explicit_task_ids_filtered_empty_does_not_fallback(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    video1 = tmp_path / "Episode1.mkv"
    video2 = tmp_path / "Episode2.mkv"
    video1.write_text("video", encoding="utf-8")
    video2.write_text("video", encoding="utf-8")
    entry1 = {"id": "e1", "path": str(video1), "basename": "Episode1", "target_label": "E01", "storage": "local"}
    called = {"restart": False}

    class FakeAutoSub:
        def _status_payload(self):
            return {"available": True, "enabled": True}

        def tasks_payload(self, **kwargs):
            return {
                "status": {"available": True},
                "tasks": [
                    {"task_id": "task-e1", "video_file": str(video1), "status": "completed", "active": False},
                    {"task_id": "task-e2", "video_file": str(video2), "status": "completed", "active": False},
                ],
            }

        def restart_tasks(self, **kwargs):
            called["restart"] = True
            return {"added": [], "skipped": [], "failed": []}

    plugin._ai_link_enabled = True
    plugin._autosub_plugin = lambda: (FakeAutoSub(), "")

    result = plugin._restart_autosub_for_entries([entry1], task_ids=["task-e2"])

    assert called["restart"] is False
    assert result["added"] == []
    assert result["skipped"][0]["task_id"] == "task-e2"
    assert "不属于当前可操作目标" in result["skipped"][0]["reason"]


def test_api_ai_restart_task_ids_with_empty_target_cache_does_not_query_global_tasks(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    called = {"tasks_payload": False, "restart": False}

    class FakeAutoSub:
        def _status_payload(self):
            return {"available": True, "enabled": True}

        def tasks_payload(self, **kwargs):
            called["tasks_payload"] = True
            return {"status": {"available": True}, "tasks": [{"task_id": "global-task", "video_file": str(tmp_path / "Locked.mkv")}]}

        def restart_tasks(self, **kwargs):
            called["restart"] = True
            return {"added": [], "skipped": [], "failed": []}

    plugin._ai_link_enabled = True
    plugin._entry_map.clear()
    plugin._autosub_plugin = lambda: (FakeAutoSub(), "")

    response = asyncio.run(plugin.api_ai_restart(FakeRequest({"task_ids": ["global-task"]})))

    assert response["success"] is True
    assert called["tasks_payload"] is False
    assert called["restart"] is False
    assert response["data"]["skipped"][0]["task_id"] == "global-task"


def test_api_ai_restart_all_requested_targets_locked_with_task_ids_does_not_fallback(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    video1 = tmp_path / "Episode1.mkv"
    video2 = tmp_path / "Episode2.mkv"
    video1.write_text("video", encoding="utf-8")
    video2.write_text("video", encoding="utf-8")
    plugin._remember_targets(
        [
            {"id": "e1", "path": str(video1), "basename": "Episode1", "target_label": "E01", "storage": "local"},
            {"id": "e2", "path": str(video2), "basename": "Episode2", "target_label": "E02", "storage": "local"},
        ]
    )
    called = {"restart": False}

    def fake_restart(entries, **kwargs):
        called["restart"] = True
        return {"added": [], "skipped": [], "failed": [], "tasks": {}}

    plugin._restart_autosub_for_entries = fake_restart

    response = asyncio.run(
        plugin.api_ai_restart(
            FakeRequest({"target_ids": ["e1"], "task_ids": ["task-e1"], "locked_target_ids": ["e1"]})
        )
    )

    assert response["success"] is True
    assert called["restart"] is False
    skipped = response["data"]["skipped"]
    assert any(item.get("target_id") == "e1" for item in skipped)
    assert any(item.get("task_id") == "task-e1" for item in skipped)


def test_api_ai_restart_mixed_unlocked_and_locked_task_ids(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    video1 = tmp_path / "Episode1.mkv"
    video2 = tmp_path / "Episode2.mkv"
    video1.write_text("video", encoding="utf-8")
    video2.write_text("video", encoding="utf-8")
    entry1 = {"id": "e1", "path": str(video1), "basename": "Episode1", "target_label": "E01", "storage": "local"}
    entry2 = {"id": "e2", "path": str(video2), "basename": "Episode2", "target_label": "E02", "storage": "local"}
    plugin._remember_targets([entry1, entry2])
    captured = {}

    class FakeAutoSub:
        def _status_payload(self):
            return {"available": True, "enabled": True}

        def tasks_payload(self, **kwargs):
            return {
                "status": {"available": True},
                "tasks": [
                    {"task_id": "task-e1", "video_file": str(video1), "status": "completed", "active": False},
                    {"task_id": "task-e2", "video_file": str(video2), "status": "completed", "active": False},
                ],
            }

        def restart_tasks(self, **kwargs):
            captured.update(kwargs)
            return {"added": [{"task_id": "task-e1"}], "skipped": [], "failed": []}

    plugin._ai_link_enabled = True
    plugin._autosub_plugin = lambda: (FakeAutoSub(), "")

    response = asyncio.run(
        plugin.api_ai_restart(
            FakeRequest(
                {
                    "target_ids": ["e1", "e2"],
                    "task_ids": ["task-e1", "task-e2"],
                    "locked_target_ids": ["e2"],
                }
            )
        )
    )

    assert response["success"] is True
    assert captured["task_ids"] == ["task-e1"]
    skipped = response["data"]["skipped"]
    assert any(item.get("target_id") == "e2" for item in skipped)
    assert any(item.get("task_id") == "task-e2" for item in skipped)


def test_api_ai_restart_stale_target_ids_with_task_ids_returns_400(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    video = tmp_path / "Movie.mkv"
    video.write_text("video", encoding="utf-8")
    plugin._remember_targets([{"id": "valid", "path": str(video), "basename": "Movie", "target_label": "Movie", "storage": "local"}])

    try:
        asyncio.run(plugin.api_ai_restart(FakeRequest({"target_ids": ["missing"], "task_ids": ["task-1"]})))
    except module.HTTPException as exc:
        assert exc.status_code == 400
        assert "目标视频已失效" in exc.detail
    else:
        raise AssertionError("stale target should be rejected even when task_ids are provided")


def test_api_ai_restart_mixed_stale_target_ids_returns_400(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    video = tmp_path / "Movie.mkv"
    video.write_text("video", encoding="utf-8")
    plugin._remember_targets([{"id": "valid", "path": str(video), "basename": "Movie", "target_label": "Movie", "storage": "local"}])

    try:
        asyncio.run(plugin.api_ai_restart(FakeRequest({"target_ids": ["valid", "missing"], "task_ids": ["task-1"]})))
    except module.HTTPException as exc:
        assert exc.status_code == 400
        assert "目标视频已失效" in exc.detail
    else:
        raise AssertionError("mixed stale target should be rejected")


def test_ai_restart_rejects_external_subtitle_outside_current_target(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    video = tmp_path / "Movie.mkv"
    subtitle = tmp_path / "Other.eng.srt"
    video.write_text("video", encoding="utf-8")
    subtitle.write_text("1\n00:00:01,000 --> 00:00:02,000\nHello\n", encoding="utf-8")
    entry = {"id": "t1", "path": str(video), "basename": "Movie", "target_label": "Movie", "storage": "local"}

    try:
        plugin._selected_external_subtitle_override_for_entries([entry], source_subtitle_path=str(subtitle))
    except module.HTTPException as exc:
        assert exc.status_code == 400
        assert "当前集" in exc.detail
    else:
        raise AssertionError("should reject unrelated subtitle path")


def test_ai_restart_matched_external_filters_explicit_task_ids_before_submit(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    video1 = tmp_path / "Episode1.mkv"
    video2 = tmp_path / "Episode2.mkv"
    subtitle = tmp_path / "Episode1.eng.srt"
    video1.write_text("video", encoding="utf-8")
    video2.write_text("video", encoding="utf-8")
    subtitle.write_text("1\n00:00:01,000 --> 00:00:02,000\nHello\n", encoding="utf-8")
    entry1 = {"id": "e1", "path": str(video1), "basename": "Episode1", "target_label": "E01", "storage": "local"}
    called = {"submit": False}

    class FakeAutoSub:
        def _status_payload(self):
            return {"available": True, "enabled": True}

        def tasks_payload(self, **kwargs):
            return {
                "status": {"available": True},
                "tasks": [
                    {"task_id": "task-e1", "video_file": str(video1), "status": "completed", "active": False},
                    {"task_id": "task-e2", "video_file": str(video2), "status": "completed", "active": False},
                ],
            }

        def restart_tasks(self, **kwargs):
            raise AssertionError("matched external path should submit, not restart")

    def fake_submit(*args, **kwargs):
        called["submit"] = True
        return {"added": [], "skipped": [], "failed": [], "targets": [], "tasks": {}}

    plugin._ai_link_enabled = True
    plugin._autosub_plugin = lambda: (FakeAutoSub(), "")
    plugin._submit_autosub_for_entries = fake_submit

    result = plugin._restart_autosub_for_entries(
        [entry1],
        source_policy="matched_external",
        source_subtitle_path=str(subtitle),
        task_ids=["task-e2"],
    )

    assert called["submit"] is False
    assert result["added"] == []
    assert result["skipped"][0]["task_id"] == "task-e2"


def test_ai_restart_matched_external_backup_replace_becomes_new_variant(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    video = tmp_path / "Episode1.mkv"
    subtitle = tmp_path / "Episode1.eng.srt"
    video.write_text("video", encoding="utf-8")
    subtitle.write_text("1\n00:00:01,000 --> 00:00:02,000\nHello\n", encoding="utf-8")
    entry = {"id": "e1", "path": str(video), "basename": "Episode1", "target_label": "E01", "storage": "local"}
    captured = {}

    class FakeAutoSub:
        def _status_payload(self):
            return {"available": True, "enabled": True}

        def tasks_payload(self, **kwargs):
            return {
                "status": {"available": True},
                "tasks": [{"task_id": "task-e1", "video_file": str(video), "status": "completed", "active": False}],
            }

        def restart_tasks(self, **kwargs):
            raise AssertionError("matched external path should submit, not restart")

    def fake_submit(*args, **kwargs):
        captured["submit_kwargs"] = kwargs
        return {"added": [{"task_id": "new-task"}], "skipped": [], "failed": [], "targets": [], "tasks": {}}

    plugin._ai_link_enabled = True
    plugin._autosub_plugin = lambda: (FakeAutoSub(), "")
    plugin._submit_autosub_for_entries = fake_submit

    result = plugin._restart_autosub_for_entries(
        [entry],
        source_policy="matched_external",
        overwrite_policy="backup_replace",
        source_subtitle_path=str(subtitle),
        source_subtitle_lang="eng",
        task_ids=["task-e1"],
    )

    assert result["added"][0]["task_id"] == "new-task"
    override = captured["submit_kwargs"]["subtitle_overrides"][str(video)]
    assert override["overwrite_policy"] == "new_variant"
    assert captured["submit_kwargs"]["overwrite_policy"] == "new_variant"


def test_ai_tasks_empty_request_includes_tasks_by_target():
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)

    response = asyncio.run(plugin.api_ai_tasks(FakeRequest({})))

    assert response["success"] is True
    assert response["data"]["tasks_by_target"] == {}


def test_api_delete_subtitle_only_allows_target_subtitles(tmp_path):
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


def test_api_delete_subtitle_rejects_locked_target(tmp_path):
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


def test_clear_subtitles_skips_locked_targets_and_uses_enumerated_subtitles(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    video1 = tmp_path / "Movie1.mkv"
    video2 = tmp_path / "Movie2.mkv"
    sub1 = tmp_path / "Movie1.chi.srt"
    sub2 = tmp_path / "Movie2.chi.srt"
    unrelated = tmp_path / "Other.chi.srt"
    for path in [video1, video2, sub1, sub2, unrelated]:
        path.write_text("data", encoding="utf-8")
    entries = [
        {"id": "t1", "path": str(video1), "basename": "Movie1", "target_label": "Movie1", "storage": "local"},
        {"id": "t2", "path": str(video2), "basename": "Movie2", "target_label": "Movie2", "storage": "local"},
    ]
    plugin._remember_targets(entries)

    response = asyncio.run(
        plugin.api_clear_subtitles(FakeRequest({"target_ids": ["t1", "t2"], "locked_target_ids": ["t2"]}))
    )

    assert response["success"] is True
    assert response["data"]["count"] == 1
    assert not sub1.exists()
    assert sub2.exists()
    assert unrelated.exists()
    assert response["data"]["failed"][0]["target_id"] == "t2"


def test_restore_subtitle_backup_missing_returns_404(tmp_path):
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
            plugin.api_restore_subtitle_backup(
                FakeRequest({"target_id": "t1", "subtitle_path": str(subtitle)})
            )
        )
    except module.HTTPException as exc:
        assert exc.status_code == 404
        assert "没有找到调轴前备份" in exc.detail
    else:
        raise AssertionError("missing subtitle backup should return 404")


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


def test_api_search_uses_local_media_catalog_service(tmp_path):
    module, histories, _ = load_plugin_module()
    plugin = make_plugin(module)
    histories.data = [
        make_history_entry(tmp_path, "a", "a.mkv", media_key="movie-a", media_type="movie", title="A", date="2024-01-01"),
    ]
    plugin._search_media_candidates = lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("api_search should call LocalMediaCatalog directly")
    )

    search_endpoint = next(route["endpoint"] for route in plugin.get_api() if route["path"] == "/search")
    response = asyncio.run(
        search_endpoint(FakeRequest(query_params={"media_type": "movie", "page_size": "10"}))
    )

    assert response["data"]["total"] == 1
    assert response["data"]["medias"][0]["title"] == "A"


def test_api_targets_uses_media_target_resolver_directly(tmp_path):
    module, histories, _ = load_plugin_module()
    plugin = make_plugin(module)
    histories.data = [
        make_history_entry(
            tmp_path,
            "m1",
            "Movie.mkv",
            media_key="movie",
            media_type="movie",
            title="Movie",
            year="2024",
            basename="Movie",
            target_label="Movie.mkv",
        )
    ]
    plugin._targets_for_media = lambda **kwargs: (_ for _ in ()).throw(
        AssertionError("api_targets should call MediaTargetResolver directly")
    )

    targets_endpoint = next(route["endpoint"] for route in plugin.get_api() if route["path"] == "/targets")
    response = targets_endpoint(
        FakeRequest(query_params={"media_type": "movie", "title": "Movie", "year": "2024"})
    )

    assert response["data"]["target_count"] == 1
    assert response["data"]["targets"][0]["basename"] == "Movie"


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


def test_subtitle_history_service_persists_and_restores_cache(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    history_module = plugin_submodule(module, "subtitle_history")
    history = history_module.SubtitleHistory(plugin, http_exception=module.HTTPException, logger=module.logger)
    video = tmp_path / "Movie.mkv"
    video.write_text("video", encoding="utf-8")
    target = {
        "id": "m1",
        "path": str(video),
        "basename": "Movie",
        "target_label": "Movie",
        "storage": "local",
    }
    plugin._match_history_cache = {
        "loaded_at": module.datetime.now(),
        "signature": "sig",
        "items": [{"id": "movie", "targets": [target]}],
        "entry_count": 1,
        "persisted": False,
    }

    history.persist_match_history_cache()
    plugin._match_history_cache = {"loaded_at": None, "signature": "", "items": [], "entry_count": 0, "persisted": False}
    plugin._entry_map.clear()

    assert history.restore_persisted_match_history_cache() is True
    assert plugin._match_history_cache["persisted"] is True
    assert plugin._match_history_cache["items"][0]["targets"][0]["id"] == "m1"
    assert plugin._entry_map["m1"]["path"] == str(video)


def test_api_match_history_builds_targets_with_media_target_resolver(tmp_path):
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
    plugin._target_from_entry = lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("match history should build targets through MediaTargetResolver")
    )

    match_history_endpoint = next(
        route["endpoint"] for route in plugin.get_api() if route["path"] == "/match_history"
    )
    response = match_history_endpoint(FakeRequest(query_params={"media_type": "movie"}))

    assert response["data"]["total"] == 1
    assert response["data"]["items"][0]["targets"][0]["basename"] == "Movie"


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
    routes = plugin.get_api()
    timeline_api_module = plugin_submodule(module, "api.timeline_api")
    timeline_api_module.check_timeline_fixer_dependencies = lambda: {
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

    original_thread = timeline_api_module.threading.Thread
    timeline_api_module.threading.Thread = NoopThread
    try:
        timeline_endpoint = next(route["endpoint"] for route in routes if route["path"] == "/timeline_fix_existing")
        response = asyncio.run(timeline_endpoint(FakeRequest({"items": [{"target_id": "m1"}]})))
    finally:
        timeline_api_module.threading.Thread = original_thread

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


def test_online_ai_translate_rejects_low_confidence_timeline_before_submit(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    setup_online_ai_translate(plugin, module, tmp_path)
    called = {"submit": False}

    def fake_submit(*args, **kwargs):
        called["submit"] = True
        return {}

    def fake_fix(video_path, subtitle_path, output_path, **kwargs):
        output_path.write_bytes(subtitle_path.read_bytes())
        return module.TimelineFixResult(
            enabled=True,
            applied=False,
            reason="timeline alignment rejected",
            base="audio:webrtc",
            offset_seconds=10.0,
            scale_factor=1.0,
            score=0.2,
            confidence="rejected",
            score_margin=0.0,
            risk_flags=["local_alignment_unstable"],
        )

    plugin._submit_autosub_for_entries = fake_submit
    module.fix_subtitle_timeline = fake_fix

    try:
        asyncio.run(
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
    except module.HTTPException as exc:
        assert exc.status_code == 409
        assert "智能调轴低可信" in exc.detail
    else:
        raise AssertionError("low confidence timeline result should block AI submit")
    assert called["submit"] is False


def test_online_download_preview_submit_ai_rejects_mixed_stale_targets(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    setup_online_ai_translate(plugin, module, tmp_path)
    called = {"submit": False}

    def fake_submit(*args, **kwargs):
        called["submit"] = True
        return {}

    plugin._submit_online_ai_translate = fake_submit

    try:
        asyncio.run(
            plugin.api_online_download_preview(
                FakeRequest(
                    {
                        "target_ids": ["m1", "missing"],
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
    except module.HTTPException as exc:
        assert exc.status_code == 400
        assert "目标视频已失效" in exc.detail
    else:
        raise AssertionError("mixed stale target should be rejected")
    assert called["submit"] is False


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


def test_online_ai_submit_endpoint_uses_online_ai_service(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
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
    captured = {}

    class FakeOnlineAiService:
        def submit_online_ai_translate(self, entries, selected_results, allow_risky_offset=False):
            captured["entries"] = entries
            captured["selected_results"] = selected_results
            captured["allow_risky_offset"] = allow_risky_offset
            return plugin._ok({"ai_translate": {"added": [{"path": entries[0]["path"]}]}, "tasks": {}})

    plugin._submit_online_ai_translate = lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("api_online_ai_submit should call OnlineAiService directly")
    )
    plugin._online_ai_service = lambda: FakeOnlineAiService()

    response = asyncio.run(
        plugin.api_online_ai_submit(
            FakeRequest(
                {
                    "target_ids": ["m1"],
                    "allow_risky_offset": True,
                    "results": [{"provider": "opensubtitles", "result_id": "r1", "language_category": "english"}],
                }
            )
        )
    )

    assert response["success"] is True
    assert captured["entries"] == [entry]
    assert captured["selected_results"][0]["result_id"] == "r1"
    assert captured["allow_risky_offset"] is True


def test_online_download_preview_submit_ai_uses_online_ai_service(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
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
    captured = {}

    class FakeOnlineAiService:
        def submit_online_ai_translate(self, entries, selected_results, allow_risky_offset=False):
            captured["entries"] = entries
            captured["selected_results"] = selected_results
            captured["allow_risky_offset"] = allow_risky_offset
            return plugin._ok({"ai_translate": {"added": [{"path": entries[0]["path"]}]}, "tasks": {}})

    plugin._submit_online_ai_translate = lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("api_online_download_preview should call OnlineAiService directly for submit_ai_translate")
    )
    plugin._online_ai_service = lambda: FakeOnlineAiService()

    response = asyncio.run(
        plugin.api_online_download_preview(
            FakeRequest(
                {
                    "target_ids": ["m1"],
                    "submit_ai_translate": True,
                    "results": [{"provider": "opensubtitles", "result_id": "r1", "language_category": "english"}],
                }
            )
        )
    )

    assert response["success"] is True
    assert captured["entries"] == [entry]
    assert captured["selected_results"][0]["result_id"] == "r1"
    assert captured["allow_risky_offset"] is False


def test_online_ai_submit_stale_target_returns_400_without_name_error():
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)

    try:
        asyncio.run(
            plugin.api_online_ai_submit(
                FakeRequest(
                    {
                        "target_ids": ["missing"],
                        "results": [{"provider": "opensubtitles", "result_id": "r1"}],
                    }
                )
            )
        )
    except module.HTTPException as exc:
        assert exc.status_code == 400
        assert "目标视频已失效" in exc.detail
    else:
        raise AssertionError("stale target should be rejected")


def test_online_ai_submit_mixed_stale_target_returns_400(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    video = tmp_path / "Movie.mkv"
    video.write_text("video", encoding="utf-8")
    plugin._remember_targets(
        [{"id": "m1", "path": str(video), "basename": "Movie", "target_label": "Movie", "storage": "local"}]
    )

    try:
        asyncio.run(
            plugin.api_online_ai_submit(
                FakeRequest(
                    {
                        "target_ids": ["m1", "missing"],
                        "results": [{"provider": "opensubtitles", "result_id": "r1"}],
                    }
                )
            )
        )
    except module.HTTPException as exc:
        assert exc.status_code == 400
        assert "目标视频已失效" in exc.detail
    else:
        raise AssertionError("mixed stale target should be rejected")


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


def test_auto_transfer_queue_stop_service_marks_pending_queue_stopped(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    plugin._ensure_transfer_auto_worker = lambda: None
    entry = make_auto_entry(tmp_path, filename="Movie.mkv")

    queued, skipped = plugin._enqueue_transfer_auto_entries([entry])
    assert queued == 1
    assert skipped == 0

    plugin.stop_service()
    snapshot = plugin._auto_transfer_queue_snapshot()

    assert plugin._auto_transfer_stopping is True
    assert snapshot["summary"]["pending"] == 0
    assert snapshot["summary"]["skipped"] == 1
    assert snapshot["summary"]["active"] == 0
    assert "服务已停止" in snapshot["tasks"][0]["message"]

    queued, skipped = plugin._enqueue_transfer_auto_entries([make_auto_entry(tmp_path, filename="Other.mkv")])
    assert queued == 0
    assert skipped == 1


def test_listen_transfer_complete_uses_auto_transfer_service_directly(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    plugin._enabled = True
    plugin._auto_search_on_transfer = True
    entry = make_auto_entry(tmp_path, filename="Movie.mkv")
    merged = {}
    captured = {}

    class FakeAutoTransferService:
        def enqueue_transfer_auto_entries(self, entries):
            captured["entries"] = entries
            return 1, 0

    plugin._entries_from_transfer_event = lambda event_data: [entry]
    plugin._merge_local_entries_cache = lambda entries: merged.setdefault("entries", entries)
    plugin._enqueue_transfer_auto_entries = lambda entries: (_ for _ in ()).throw(
        AssertionError("listen_transfer_complete should call AutoTransferService directly")
    )
    plugin._auto_transfer_service = lambda: FakeAutoTransferService()

    plugin.listen_transfer_complete(types.SimpleNamespace(event_data={"path": str(tmp_path / "Movie.mkv")}))

    assert merged["entries"] == [entry]
    assert captured["entries"] == [entry]


def test_api_auto_transfer_queue_uses_auto_transfer_service_directly():
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    captured = {}

    class FakeAutoTransferService:
        def auto_transfer_queue_snapshot(self, limit=100):
            captured["limit"] = limit
            return {"summary": {"total": 0}, "tasks": []}

    plugin._auto_transfer_queue_snapshot = lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("api_auto_transfer_queue should call AutoTransferService directly")
    )
    plugin._auto_transfer_service = lambda: FakeAutoTransferService()

    queue_endpoint = next(route["endpoint"] for route in plugin.get_api() if route["path"] == "/auto_transfer_queue")
    response = queue_endpoint(FakeRequest(query_params={"limit": "500"}))

    assert response["success"] is True
    assert captured["limit"] == 200
    assert response["data"]["summary"]["total"] == 0


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


def test_auto_transfer_skips_before_search_when_video_has_embedded_chinese_subtitle(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    entry = make_auto_entry(tmp_path, title="Anime", media_type="tv", season=4, episode=14)
    plugin._auto_skip_chinese_media_on_transfer = False
    original_run = module.subprocess.run
    module.subprocess.run = lambda *args, **kwargs: types.SimpleNamespace(
        stdout='{"streams":[{"index":2,"codec_name":"subrip","tags":{"language":"chi","title":"Chinese Simplified"}}]}'
    )
    plugin._auto_search_write_subtitle = lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("Embedded Chinese subtitle should skip online search")
    )
    plugin._auto_submit_ai_for_entry = lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("Embedded Chinese subtitle should skip AI")
    )

    try:
        result = plugin._auto_process_transfer_entry(entry)
    finally:
        module.subprocess.run = original_run

    assert result["status"] == "skipped"
    assert result["reason"] == "目标已有中文字幕"


def test_auto_transfer_ai_source_only_skips_embedded_chinese_before_ai(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    entry = make_auto_entry(tmp_path, title="Anime", media_type="tv", season=4, episode=14)
    plugin._auto_skip_chinese_media_on_transfer = False
    plugin._auto_transfer_subtitle_strategy = "ai_source_only"
    original_run = module.subprocess.run
    module.subprocess.run = lambda *args, **kwargs: types.SimpleNamespace(
        stdout='{"streams":[{"index":2,"codec_name":"subrip","tags":{"language":"zho"}}]}'
    )
    plugin._auto_submit_ai_for_entry = lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("Embedded Chinese subtitle should skip ai_source_only")
    )

    try:
        result = plugin._auto_process_transfer_entry(entry)
    finally:
        module.subprocess.run = original_run

    assert result["status"] == "skipped"
    assert result["reason"] == "目标已有中文字幕"


def test_auto_transfer_samples_unknown_embedded_text_subtitle_content(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    entry = make_auto_entry(tmp_path, title="Anime", media_type="tv", season=4, episode=14)
    plugin._auto_skip_chinese_media_on_transfer = False
    original_run = module.subprocess.run

    def fake_run(args, *run_args, **run_kwargs):
        if args[0] == "ffprobe":
            return types.SimpleNamespace(
                stdout='{"streams":[{"index":2,"codec_name":"subrip","tags":{"language":"und"}}]}'
            )
        return types.SimpleNamespace(
            stdout=("1\n00:00:01,000 --> 00:00:02,000\n这是一段中文字幕内容，用来确认未知语言内嵌字幕不会漏判。\n" * 25).encode()
        )

    module.subprocess.run = fake_run
    plugin._auto_search_write_subtitle = lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("Sampled Chinese subtitle should skip online search")
    )
    plugin._auto_submit_ai_for_entry = lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("Sampled Chinese subtitle should skip AI")
    )

    try:
        result = plugin._auto_process_transfer_entry(entry)
    finally:
        module.subprocess.run = original_run

    assert result["status"] == "skipped"
    assert result["reason"] == "目标已有中文字幕"


def test_auto_transfer_embedded_english_subtitle_still_searches(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    entry = make_auto_entry(tmp_path, title="Anime", media_type="tv", season=4, episode=14)
    plugin._auto_skip_chinese_media_on_transfer = False
    original_run = module.subprocess.run
    module.subprocess.run = lambda *args, **kwargs: types.SimpleNamespace(
        stdout='{"streams":[{"index":4,"codec_name":"ass","tags":{"language":"eng","title":"English subtitles for Chinese dialogue"}}]}'
    )
    plugin._auto_search_write_subtitle = lambda item, target, **kwargs: {
        "status": "written",
        "target": target.get("label"),
        "result": "online chinese subtitle",
    }
    plugin._auto_submit_ai_for_entry = lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("Written online subtitle should not trigger AI")
    )

    try:
        result = plugin._auto_process_transfer_entry(entry)
    finally:
        module.subprocess.run = original_run

    assert result["status"] == "written"
    assert result["result"] == "online chinese subtitle"


def test_auto_transfer_embedded_regional_chinese_language_tag_skips(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    entry = make_auto_entry(tmp_path, title="Anime", media_type="tv", season=4, episode=14)
    plugin._auto_skip_chinese_media_on_transfer = False
    original_run = module.subprocess.run
    module.subprocess.run = lambda *args, **kwargs: types.SimpleNamespace(
        stdout='{"streams":[{"index":2,"codec_name":"ass","tags":{"language":"zh-Hans-CN"}}]}'
    )
    plugin._auto_search_write_subtitle = lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("Regional Chinese language tag should skip online search")
    )

    try:
        result = plugin._auto_process_transfer_entry(entry)
    finally:
        module.subprocess.run = original_run

    assert result["status"] == "skipped"
    assert result["reason"] == "目标已有中文字幕"


def test_auto_transfer_embedded_chinese_pgs_does_not_skip_online_search(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    entry = make_auto_entry(tmp_path, title="Anime", media_type="tv", season=4, episode=14)
    plugin._auto_skip_chinese_media_on_transfer = False
    original_run = module.subprocess.run
    module.subprocess.run = lambda *args, **kwargs: types.SimpleNamespace(
        stdout='{"streams":[{"index":5,"codec_name":"hdmv_pgs_subtitle","tags":{"language":"chi","title":"Chinese"}}]}'
    )
    plugin._auto_search_write_subtitle = lambda item, target, **kwargs: {
        "status": "written",
        "target": target.get("label"),
        "result": "online chinese subtitle",
    }

    try:
        result = plugin._auto_process_transfer_entry(entry)
    finally:
        module.subprocess.run = original_run

    assert result["status"] == "written"
    assert result["result"] == "online chinese subtitle"


def test_auto_transfer_embedded_chinese_signs_does_not_skip_online_search(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    entry = make_auto_entry(tmp_path, title="Anime", media_type="tv", season=4, episode=14)
    plugin._auto_skip_chinese_media_on_transfer = False
    original_run = module.subprocess.run
    module.subprocess.run = lambda *args, **kwargs: types.SimpleNamespace(
        stdout='{"streams":[{"index":2,"codec_name":"ass","tags":{"language":"chi","title":"Chinese Signs/Songs"}}]}'
    )
    plugin._auto_search_write_subtitle = lambda item, target, **kwargs: {
        "status": "written",
        "target": target.get("label"),
        "result": "online chinese subtitle",
    }

    try:
        result = plugin._auto_process_transfer_entry(entry)
    finally:
        module.subprocess.run = original_run

    assert result["status"] == "written"
    assert result["result"] == "online chinese subtitle"


def test_auto_transfer_group_skips_embedded_chinese_target_before_season_search(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    plugin._auto_skip_chinese_media_on_transfer = False
    entries = [
        make_auto_entry(tmp_path, filename="Show.S01E01.mkv", id="e1", media_key="tv-key", media_type="tv", title="Show", season=1, episode=1),
        make_auto_entry(tmp_path, filename="Show.S01E02.mkv", id="e2", media_key="tv-key", media_type="tv", title="Show", season=1, episode=2),
    ]
    original_run = module.subprocess.run

    def fake_run(args, *run_args, **run_kwargs):
        video_path = str(args[-1])
        if video_path.endswith("Show.S01E01.mkv"):
            return types.SimpleNamespace(
                stdout='{"streams":[{"index":2,"codec_name":"subrip","tags":{"language":"zho","title":"Chinese Simplified"}}]}'
            )
        return types.SimpleNamespace(stdout='{"streams":[]}')

    module.subprocess.run = fake_run
    cache_ids = []
    season_ids = []

    def fake_cache(items):
        cache_ids.extend(item["id"] for item in items)
        return {"status": "skipped", "written_by_target": {}}

    def fake_season(items, task_ids=None):
        season_ids.extend(item["id"] for item in items)
        return {
            "status": "skipped",
            "written_by_target": {},
            "ai_by_target": {},
        }

    plugin._auto_write_from_season_cache = fake_cache
    plugin._auto_search_write_season_package = fake_season
    searched = []
    plugin._auto_search_write_subtitle = lambda entry, target, **kwargs: searched.append(entry["id"]) or {"status": "skipped", "target": target.get("label")}

    try:
        results = plugin._auto_process_transfer_group(entries, task_ids=["t1", "t2"])
    finally:
        module.subprocess.run = original_run

    assert results["e1"]["status"] == "skipped"
    assert results["e1"]["reason"] == "目标已有中文字幕"
    assert cache_ids == ["e2"]
    assert season_ids == ["e2"]
    assert searched == ["e2"]


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


def test_auto_transfer_online_then_ai_source_falls_back_to_ai_when_search_is_uncertain(tmp_path):
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
    assert result["strategy"] == "online_then_ai_source"


def test_auto_transfer_online_source_only_never_submits_ai_source_fallback(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    entry = make_auto_entry(tmp_path)
    plugin._auto_skip_chinese_media_on_transfer = False
    plugin._auto_transfer_subtitle_strategy = "online_source_only"
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
    assert result["strategy"] == "online_source_only"


def test_auto_transfer_ai_source_only_never_searches(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    entry = make_auto_entry(tmp_path)
    plugin._auto_skip_chinese_media_on_transfer = False
    plugin._auto_transfer_subtitle_strategy = "ai_source_only"
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
    assert result["strategy"] == "ai_source_only"


def test_auto_transfer_legacy_ai_first_maps_to_ai_source_only(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    entry = make_auto_entry(tmp_path)
    plugin._auto_skip_chinese_media_on_transfer = False
    plugin._auto_transfer_subtitle_strategy = "ai_first"
    plugin._auto_search_write_subtitle = lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("ai_first legacy value should migrate to ai_source_only and never search")
    )
    plugin._auto_submit_ai_for_entry = lambda item, target, reason: {
        "status": "ai_submitted",
        "target": target.get("label"),
        "reason": reason,
    }

    result = plugin._auto_process_transfer_entry(entry)

    assert result["status"] == "ai_submitted"
    assert result["strategy"] == "ai_source_only"


def test_auto_transfer_legacy_strategy_aliases_are_migrated():
    module, _, _ = load_plugin_module()
    config_schema = plugin_submodule(module, "config_schema")
    aliases = {
        "search_first": "online_then_ai_source",
        "search_only": "online_source_only",
        "ai_only": "ai_source_only",
        "ai_first": "ai_source_only",
    }

    for legacy, expected in aliases.items():
        assert config_schema.normalize_auto_transfer_subtitle_strategy(legacy) == expected
    assert module.SubtitleManualUpload._normalize_auto_transfer_subtitle_strategy("ai_first") == "ai_source_only"


def test_auto_subtitle_preference_config_normalizes_legacy_strings(tmp_path):
    module, _, _ = load_plugin_module()
    config_schema = plugin_submodule(module, "config_schema")
    plugin = make_plugin(module)
    plugin.update_config = lambda config: None
    raw_config = {
        "auto_multi_subtitle_mode": "chinese",
        "auto_subtitle_language_priority": "英文,双语,坏值",
        "auto_subtitle_format_priority": "srt,ass,xxx",
        "auto_ass_to_srt_for_ai": False,
    }

    normalized = config_schema.normalize_plugin_config(raw_config, subtitle_exts=module.SubtitleManualUpload._subtitle_exts)
    assert normalized["auto_multi_subtitle_mode"] == "chinese_all"
    assert normalized["auto_subtitle_language_priority"][:4] == ["eng", "bilingual", "chi", "cht"]
    assert normalized["auto_subtitle_format_priority"][:4] == [".srt", ".ass", ".ssa", ".vtt"]
    assert ".sbv" in normalized["auto_subtitle_format_priority"]
    assert normalized["auto_ass_to_srt_for_ai"] is False

    plugin.init_plugin(raw_config)

    assert plugin._auto_multi_subtitle_mode == "chinese_all"
    assert plugin._auto_subtitle_language_priority[:4] == ["eng", "bilingual", "chi", "cht"]
    assert plugin._auto_subtitle_format_priority[:4] == [".srt", ".ass", ".ssa", ".vtt"]
    assert ".sbv" in plugin._auto_subtitle_format_priority
    assert plugin._auto_ass_to_srt_for_ai is False


def test_config_schema_default_config_covers_config_vue_bound_fields():
    module, _, _ = load_plugin_module()
    config_schema = plugin_submodule(module, "config_schema")
    plugin = module.SubtitleManualUpload.__new__(module.SubtitleManualUpload)
    _, default_config = plugin.get_form()
    vue_text = (Path(module.__file__).parent / "src" / "components" / "Config.vue").read_text(encoding="utf-8")
    bound_fields = sorted(set(re.findall(r"localConfig\.(?!value\b)([A-Za-z0-9_]+)", vue_text)))

    assert bound_fields
    assert not [field for field in bound_fields if field not in config_schema.DEFAULT_CONFIG]
    assert not [field for field in bound_fields if field not in default_config]
    for field in bound_fields:
        assert default_config[field] == config_schema.DEFAULT_CONFIG[field]

    assert "online_providers: ['assrt', 'opensubtitles']" in vue_text
    assert "auto_subtitle_language_priority: ['bilingual', 'chi', 'cht', 'eng']" in vue_text
    assert "auto_subtitle_format_priority: ['.ass', '.srt', '.ssa', '.vtt']" in vue_text
    assert "timeline_max_offset_seconds: 120" in vue_text
    assert "rar_dependency_mode: 'none'" in vue_text
    assert "opensubtitles_api_url: 'https://api.opensubtitles.com/api/v1'" in vue_text


def test_auto_transfer_existing_chinese_subtitle_skips_all_strategies(tmp_path):
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
    assert result["reason"] == "目标已有中文字幕"


def test_auto_transfer_existing_non_chinese_subtitle_still_searches(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    entry = make_auto_entry(tmp_path, filename="Movie.mkv")
    (tmp_path / "Movie.eng.srt").write_text("1\n00:00:01,000 --> 00:00:02,000\nHello\n", encoding="utf-8")
    plugin._auto_skip_chinese_media_on_transfer = False
    original_run = module.subprocess.run
    module.subprocess.run = lambda *args, **kwargs: types.SimpleNamespace(stdout='{"streams":[]}')
    plugin._auto_search_write_subtitle = lambda item, target, **kwargs: {
        "status": "written",
        "target": target.get("label"),
        "result": "online chinese subtitle",
    }
    plugin._auto_submit_ai_for_entry = lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("Written online subtitle should not trigger AI")
    )

    try:
        result = plugin._auto_process_transfer_entry(entry)
    finally:
        module.subprocess.run = original_run

    assert result["status"] == "written"
    assert result["result"] == "online chinese subtitle"


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
    plugin._write_operations_to_disk = lambda **kwargs: ([{"output_name": "Movie.chi.srt"}], 0, 0)
    plugin._auto_submit_ai_for_entry = lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("Chinese subtitle should not trigger AI")
    )

    result = plugin._auto_search_write_subtitle(entry)

    assert result["status"] == "written"
    assert result["candidate_count"] == 2
    assert service.downloaded[0]["result_id"] == "os-1"


def test_auto_search_write_falls_back_when_best_download_has_no_subtitle(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    plugin._online_provider_ids = ["assrt", "opensubtitles"]
    entry = make_auto_entry(tmp_path, filename="Movie.mkv")
    subtitle = tmp_path / "Movie.chi.srt"
    subtitle.write_text("1\n00:00:01,000 --> 00:00:02,000\n你好\n", encoding="utf-8")

    class FakeAutoService:
        def __init__(self):
            self.downloaded_ids = []

        def search(self, **kwargs):
            return {
                "results": [
                    {
                        "provider": "opensubtitles",
                        "result_id": "os-link",
                        "title": "Movie Netdisk Link",
                        "score": 95,
                        "downloadable": True,
                        "language_category": "chinese",
                    },
                    {
                        "provider": "assrt",
                        "result_id": "assrt-sub",
                        "title": "Movie Chinese Subtitle",
                        "score": 90,
                        "downloadable": True,
                        "language_category": "chinese",
                    },
                ]
            }

        def download(self, selected):
            result = selected[0]
            self.downloaded_ids.append(result["result_id"])
            if result["result_id"] == "os-link":
                return [
                    {
                        "provider": result["provider"],
                        "source_name": "download-url.txt",
                        "content": b"https://example.invalid/pan-link",
                        "result": result,
                    }
                ]
            return [
                {
                    "provider": result["provider"],
                    "source_name": "Movie.chi.srt",
                    "content": subtitle.read_bytes(),
                    "result": result,
                }
            ]

    service = FakeAutoService()
    plugin._online_service = lambda: service
    plugin._auto_search_keywords_for_entry = lambda item, target: ["Movie 2024"]

    def fake_extract(source_name, content, session_dir):
        if source_name.endswith(".txt"):
            return []
        return [
            {
                "upload_id": "u1",
                "source_name": source_name,
                "stored_path": str(subtitle),
                "ext": ".srt",
            }
        ]

    plugin._extract_subtitle_files = fake_extract
    plugin._write_operations_to_disk = lambda **kwargs: ([{"output_name": "Movie.chi.srt"}], 0, 0)

    result = plugin._auto_search_write_subtitle(entry)

    assert result["status"] == "written"
    assert result["result"] == "Movie Chinese Subtitle"
    assert service.downloaded_ids == ["os-link", "assrt-sub"]


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


def test_auto_search_write_prefers_chinese_ass_from_multi_subtitle_package(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    entry = make_auto_entry(tmp_path, filename="Movie.mkv")
    files = {}
    for name, text in {
        "Movie.chi.srt": "1\n00:00:01,000 --> 00:00:02,000\n你好\n",
        "Movie.chi.ass": "[Script Info]\n[V4+ Styles]\n[Events]\nDialogue: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,,你好\n",
        "Movie.eng.srt": "1\n00:00:01,000 --> 00:00:02,000\nHello\n",
    }.items():
        path = tmp_path / name
        path.write_text(text, encoding="utf-8")
        files[name] = path

    class FakeAutoService:
        def search(self, **kwargs):
            return {"results": [{"provider": "opensubtitles", "result_id": "os-1", "title": "Movie pack", "score": 90, "downloadable": True}]}

        def download(self, selected):
            return [{"provider": "opensubtitles", "source_name": "Movie.zip", "content": b"zip", "result": selected[0]}]

    plugin._online_service = lambda: FakeAutoService()
    plugin._auto_search_keywords_for_entry = lambda item, target: ["Movie 2024"]
    plugin._extract_subtitle_files = lambda source_name, content, session_dir: [
        {"upload_id": name, "source_name": name, "stored_path": str(path), "ext": path.suffix.lower()}
        for name, path in files.items()
    ]
    captured = {}

    def fake_write(**kwargs):
        captured["operations"] = kwargs["operations"]
        return [{"output_name": operation["destination_name"]} for operation in kwargs["operations"]], 1, 0

    plugin._write_operations_to_disk = fake_write
    plugin._submit_autosub_for_entries = lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("Chinese best match should not trigger AI")
    )

    result = plugin._auto_search_write_subtitle(entry)

    assert result["status"] == "written"
    assert [operation["upload_info"]["source_name"] for operation in captured["operations"]] == ["Movie.chi.ass"]
    assert result["written"][0]["output_name"] == "Movie.chi.ass"


def test_auto_write_chinese_all_keeps_chinese_and_bilingual_variants(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    plugin._auto_multi_subtitle_mode = "chinese_all"
    entry = make_auto_entry(tmp_path, filename="Movie.mkv")
    prepared_uploads = []
    for name, text in {
        "Movie.chi.ass": "[Script Info]\n[V4+ Styles]\n[Events]\nDialogue: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,,你好\n",
        "Movie.cht.srt": "1\n00:00:01,000 --> 00:00:02,000\n你好\n",
        "Movie.chi.eng.srt": "1\n00:00:01,000 --> 00:00:02,000\n你好\nHello\n",
        "Movie.eng.srt": "1\n00:00:01,000 --> 00:00:02,000\nHello\n",
    }.items():
        path = tmp_path / name
        path.write_text(text, encoding="utf-8")
        prepared_uploads.append({"upload_id": name, "source_name": name, "stored_path": str(path), "ext": path.suffix.lower()})

    captured = {}

    def fake_write(**kwargs):
        captured["operations"] = kwargs["operations"]
        return [{"output_name": operation["destination_name"]} for operation in kwargs["operations"]], 1, 0

    plugin._write_operations_to_disk = fake_write
    plugin._submit_autosub_for_entries = lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("Chinese-all mode should ignore foreign-only subtitles when Chinese variants exist")
    )

    result = plugin._auto_write_prepared_uploads_for_entries(
        target_entries=[entry],
        prepared_uploads=prepared_uploads,
        session_dir=tmp_path,
        selected_result={"provider": "opensubtitles", "title": "Movie pack"},
    )

    assert result["status"] == "written"
    assert [operation["upload_info"]["source_name"] for operation in captured["operations"]] == [
        "Movie.chi.eng.srt",
        "Movie.chi.ass",
        "Movie.cht.srt",
    ]


def test_auto_select_all_keeps_all_language_and_format_variants(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    plugin._auto_multi_subtitle_mode = "all"
    entry = make_auto_entry(tmp_path, filename="Movie.mkv")
    prepared_uploads = []
    for name, text in {
        "Movie.chi.ass": "[Script Info]\n[V4+ Styles]\n[Events]\nDialogue: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,,你好\n",
        "Movie.cht.srt": "1\n00:00:01,000 --> 00:00:02,000\n你好\n",
        "Movie.eng.ass": "[Script Info]\n[V4+ Styles]\n[Events]\nDialogue: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,,Hello\n",
        "Movie.eng.srt": "1\n00:00:01,000 --> 00:00:02,000\nHello\n",
    }.items():
        path = tmp_path / name
        path.write_text(text, encoding="utf-8")
        prepared_uploads.append({"upload_id": name, "source_name": name, "stored_path": str(path), "ext": path.suffix.lower()})

    selected = plugin._select_auto_subtitle_items(prepared_uploads, [plugin._target_from_entry(entry)])

    assert [item["source_name"] for item in selected] == [
        "Movie.chi.ass",
        "Movie.cht.srt",
        "Movie.eng.ass",
        "Movie.eng.srt",
    ]


def test_online_ai_converts_foreign_ass_to_temporary_srt(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    entry = make_auto_entry(tmp_path, filename="Movie.mkv")
    source = tmp_path / "Movie.eng.ass"
    source.write_text("[Script Info]\n[V4+ Styles]\n[Events]\nDialogue: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,,Hello\n", encoding="utf-8")

    class FakeSubs:
        def save(self, output_path, format_=""):
            assert format_ == "srt"
            Path(output_path).write_text("1\n00:00:01,000 --> 00:00:02,000\nHello\n", encoding="utf-8")

    plugin._load_pysubs2_file = lambda path: FakeSubs()

    def fake_timeline(video_path, subtitle_path, output_path, allow_risky_offset=False):
        assert Path(subtitle_path).suffix.lower() == ".srt"
        Path(output_path).write_text(Path(subtitle_path).read_text(encoding="utf-8"), encoding="utf-8")
        return module.TimelineFixResult(
            enabled=True,
            applied=False,
            reason="offset below threshold",
            base="test",
            offset_seconds=0.0,
            scale_factor=1.0,
            score=1.0,
        )

    plugin._run_timeline_fix = fake_timeline

    overrides, fixed = plugin._prepare_online_ai_subtitle_overrides(
        session_dir=tmp_path,
        target_entries=[entry],
        prepared_uploads=[{"upload_id": "u1", "source_name": source.name, "stored_path": str(source), "ext": ".ass"}],
    )

    assert set(overrides) == {entry["path"]}
    assert overrides[entry["path"]]["subtitle_path"].endswith(".srt")
    assert fixed[0]["source_name"].endswith(".srt")
    assert fixed[0]["autosub_lang"] == "en"


def test_auto_write_foreign_ai_skip_is_not_counted_as_completed(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    entry = make_auto_entry(tmp_path, filename="Movie.mkv")
    subtitle = tmp_path / "Movie.eng.srt"
    subtitle.write_text("1\n00:00:01,000 --> 00:00:02,000\nHello\n", encoding="utf-8")
    prepared_uploads = [
        {
            "upload_id": "u1",
            "source_name": subtitle.name,
            "stored_path": str(subtitle),
            "ext": ".srt",
        }
    ]
    plugin._prepare_online_ai_subtitle_overrides = lambda **kwargs: (
        {entry["path"]: {"subtitle_path": str(subtitle), "lang": "en"}},
        [{"target_id": entry["id"], "subtitle_path": str(subtitle), "autosub_lang": "en"}],
    )
    plugin._submit_autosub_for_entries = lambda *args, **kwargs: {
        "added": [],
        "skipped": [{"path": entry["path"], "reason": "任务已存在"}],
        "failed": [],
        "tasks": {"task_by_target": {}},
    }

    result = plugin._auto_write_prepared_uploads_for_entries(
        target_entries=[entry],
        prepared_uploads=prepared_uploads,
        session_dir=tmp_path,
        selected_result={"provider": "opensubtitles", "title": "Movie English"},
    )

    assert result["status"] == "skipped"
    assert result["ai_count"] == 0
    assert result["completed_count"] == 0
    assert result["ai_by_target"] == {}
    assert "AI 字幕任务未新增" in result["reason"]


def test_online_ai_falls_back_to_srt_when_foreign_ass_conversion_fails(tmp_path):
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)
    entry = make_auto_entry(tmp_path, filename="Movie.mkv")
    ass_source = tmp_path / "Movie.eng.ass"
    srt_source = tmp_path / "Movie.eng.srt"
    ass_source.write_text("[Script Info]\n[V4+ Styles]\n[Events]\nDialogue: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,,Hello\n", encoding="utf-8")
    srt_source.write_text("1\n00:00:01,000 --> 00:00:02,000\nHello\n", encoding="utf-8")
    plugin._load_pysubs2_file = lambda path: (_ for _ in ()).throw(RuntimeError("bad ass"))
    observed = {}

    def fake_timeline(video_path, subtitle_path, output_path, allow_risky_offset=False):
        observed["subtitle_path"] = subtitle_path
        Path(output_path).write_text(Path(subtitle_path).read_text(encoding="utf-8"), encoding="utf-8")
        return module.TimelineFixResult(
            enabled=True,
            applied=False,
            reason="offset below threshold",
            base="test",
            offset_seconds=0.0,
            scale_factor=1.0,
            score=1.0,
        )

    plugin._run_timeline_fix = fake_timeline

    overrides, fixed = plugin._prepare_online_ai_subtitle_overrides(
        session_dir=tmp_path,
        target_entries=[entry],
        prepared_uploads=[
            {"upload_id": "ass", "source_name": ass_source.name, "stored_path": str(ass_source), "ext": ".ass"},
            {"upload_id": "srt", "source_name": srt_source.name, "stored_path": str(srt_source), "ext": ".srt"},
        ],
    )

    assert Path(observed["subtitle_path"]) == srt_source
    assert set(overrides) == {entry["path"]}
    assert fixed[0]["source_name"] == "Movie.eng.srt"


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
