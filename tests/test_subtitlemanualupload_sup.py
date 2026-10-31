from __future__ import annotations

import hashlib
import importlib
import io
import sys
import types
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest


ROOT = Path(__file__).resolve().parents[1]
MIB = 1024 * 1024
PGS_HEADER = b"PG" + (90000).to_bytes(4, "big") + bytes(4) + b"\x16\x00\x00"
SUP_CONTENT = PGS_HEADER + bytes(range(256)) * 8
VOBSUB_CONTENT = b"\x00\x00\x01\xba" + bytes(range(256)) * 8
IDX_CONTENT = b"# VobSub index file, v7\nsize: 1920x1080\nid: zh, index: 0\n"
TEXT_FORMAT_SAMPLES = (
    (".smi", b"<SAMI><BODY><SYNC Start=0><P>Hello</BODY></SAMI>"),
    (".sami", b"<SAMI><BODY><SYNC Start=0><P>Hello</BODY></SAMI>"),
    (".ttml", b'<tt xmlns="http://www.w3.org/ns/ttml"><body><p begin="0s" end="1s">Hello</p></body></tt>'),
    (".dfxp", b'<tt xmlns="http://www.w3.org/ns/ttml"><body><p begin="0s" end="1s">Hello</p></body></tt>'),
    (".sub", b"{0}{25}Hello\n{26}{50}World\n"),
)


class StubHttpException(Exception):
    def __init__(self, status_code=500, detail=""):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


@pytest.fixture(params=("plugins.v2", "plugins.v3"))
def sup_modules(request, monkeypatch):
    package_name = f"subtitle_sup_test_{request.param.replace('.', '_')}"
    package = types.ModuleType(package_name)
    package.__path__ = [str(ROOT / request.param / "subtitlemanualupload")]
    monkeypatch.setitem(sys.modules, package_name, package)
    if "fastapi" not in sys.modules:
        fastapi = types.ModuleType("fastapi")
        fastapi.HTTPException = StubHttpException
        monkeypatch.setitem(sys.modules, "fastapi", fastapi)

    settings = types.SimpleNamespace(PROXY=None, PROXY_SERVER=None)
    external_modules = {
        "app": {},
        "app.core": {},
        "app.core.config": {"settings": settings},
        "app.log": {"logger": Mock()},
        "app.sdk": {},
        "app.sdk.config": {"settings": settings},
        "app.sdk.logging": {"logger": Mock()},
        "app.sdk.media": {"build_media_key": Mock(), "resolve_media_identity": Mock()},
        "app.schemas": {},
        "app.schemas.types": {"MediaSource": types.SimpleNamespace(TMDB="tmdb", Douban="douban")},
    }
    for name, attributes in external_modules.items():
        if name not in sys.modules:
            module = types.ModuleType(name)
            monkeypatch.setitem(sys.modules, name, module)
        module = sys.modules[name]
        for attribute, value in attributes.items():
            if not hasattr(module, attribute):
                monkeypatch.setattr(module, attribute, value, raising=False)

    # The facade package imports worker services, which these focused tests do not need.
    auto_package = types.ModuleType(f"{package_name}.auto_transfer")
    auto_package.__path__ = [str(ROOT / request.param / "subtitlemanualupload" / "auto_transfer")]
    monkeypatch.setitem(sys.modules, auto_package.__name__, auto_package)

    def load(name):
        return importlib.import_module(f"{package_name}.{name}")

    try:
        yield types.SimpleNamespace(
            generation=request.param,
            formats=load("matching.subtitle_formats"),
            language=load("matching.subtitle_language"),
            upload=load("upload.upload_session"),
            writer=load("matching.subtitle_writer"),
            timeline=load("timeline.timeline_fixer"),
            load=load,
        )
    finally:
        for name in list(sys.modules):
            if name.startswith(f"{package_name}."):
                sys.modules.pop(name, None)


def make_upload_service(modules, tmp_path):
    return modules.upload.UploadSessionService(
        data_path=tmp_path,
        subtitle_exts=modules.formats.SUBTITLE_EXTS,
        archive_exts={".zip", ".rar", ".7z"},
        rar_exts={".rar"},
        sevenzip_exts={".7z"},
        default_session_hours=24,
        hash_text=lambda value: hashlib.sha256(value.encode()).hexdigest(),
        extract_rar_subtitle_files=Mock(side_effect=AssertionError("unexpected RAR extraction")),
        extract_7z_subtitle_files=Mock(side_effect=AssertionError("unexpected 7Z extraction")),
    )


def zip_content(name, content):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(name, content)
    return output.getvalue()


def make_bitmap_writer(modules, tmp_path):
    timeline_fix = Mock(side_effect=AssertionError("bitmap subtitles must not enter text timeline processing"))
    simplify = Mock(side_effect=AssertionError("bitmap subtitles must not enter text conversion"))
    inventory = types.SimpleNamespace(invalidate_directory=Mock())
    owner = types.SimpleNamespace(
        _traditional_to_simplified=True,
        _emby_refresh_after_subtitle_write=False,
        _subtitle_exts=modules.formats.SUBTITLE_EXTS,
        _stream_exts={".strm"},
        _normalize_text=modules.language.normalize_text,
        _normalize_language_suffix=modules.language.normalize_language_suffix,
        _set_timeline_task=Mock(),
        _run_timeline_fix=timeline_fix,
        _remove_ext_marks=Mock(),
        _target_from_entry=lambda entry: {"label": entry["basename"]},
        _invalidate_match_history_cache=Mock(),
        services=types.SimpleNamespace(subtitle_inventory=lambda: inventory),
    )
    writer = modules.writer.SubtitleWriter(
        owner,
        http_exception=StubHttpException,
        logger=Mock(),
        timeline_result_type=modules.timeline.TimelineFixResult,
        timeline_fix_func=timeline_fix,
        convert_subtitle_file_to_simplified=simplify,
        load_session=Mock(),
        timeline_cache_dir=lambda: tmp_path / "timeline-cache",
    )
    return writer, owner, simplify


def make_bitmap_operations(modules, tmp_path, writer, *, target_ids=("episode-1",)):
    source = tmp_path / "uploaded.sup"
    source.write_bytes(SUP_CONTENT)
    targets = {target_id: make_target(tmp_path, target_id) for target_id in target_ids}
    operations = writer.build_write_operations(
        [
            {"upload_id": "uploaded", "target_id": target_id, "ext": ".sup", "language_suffix": "eng"}
            for target_id in target_ids
        ],
        {"uploaded": {"upload_id": "uploaded", "stored_path": str(source), "source_name": source.name, "ext": ".sup"}},
        targets,
    )
    return source, targets, operations


def make_target(tmp_path, target_id="episode-1"):
    media_dir = tmp_path / "media"
    media_dir.mkdir(exist_ok=True)
    video = media_dir / f"{target_id}.mkv"
    video.touch()
    return {
        "id": target_id,
        "path": str(video),
        "basename": video.stem,
        "storage": "local",
        "media_type": "tv",
        "title": "Vision Quest",
        "year": "2026",
    }


def make_vobsub_uploads(tmp_path, *, archive_name="subtitles.zip", directory="season-1"):
    uploads = {}
    for extension, content in ((".idx", IDX_CONTENT), (".sub", VOBSUB_CONTENT)):
        upload_id = extension[1:]
        stored_path = tmp_path / f"{upload_id}{extension}"
        stored_path.write_bytes(content)
        source_name = f"VisionQuest.S01E01.chs{extension}"
        uploads[upload_id] = {
            "upload_id": upload_id,
            "stored_path": str(stored_path),
            "source_name": source_name,
            "ext": extension,
            "archive_name": archive_name,
            "archive_member": f"{directory}/{source_name}" if archive_name else "",
        }
    return uploads


def test_sup_direct_upload_preserves_binary(sup_modules, tmp_path):
    service = make_upload_service(sup_modules, tmp_path)
    session = tmp_path / "session"
    session.mkdir()

    uploads = service.extract_subtitle_files("VisionQuest.S01E01.CHS.SUP", SUP_CONTENT, session)

    assert len(uploads) == 1
    assert uploads[0]["ext"] == ".sup"
    assert uploads[0]["source_name"] == "VisionQuest.S01E01.CHS.SUP"
    assert Path(uploads[0]["stored_path"]).read_bytes() == SUP_CONTENT


def test_sup_zip_upload_preserves_binary(sup_modules, tmp_path):
    service = make_upload_service(sup_modules, tmp_path)
    session = tmp_path / "session"
    session.mkdir()

    uploads = service.extract_subtitle_files(
        "VisionQuest.zip", zip_content("subtitles/VisionQuest.S01E01.chs.sup", SUP_CONTENT), session
    )

    assert len(uploads) == 1
    assert uploads[0]["ext"] == ".sup"
    assert uploads[0]["archive_name"] == "VisionQuest.zip"
    assert Path(uploads[0]["stored_path"]).read_bytes() == SUP_CONTENT


@pytest.mark.parametrize(
    ("extension", "content"),
    TEXT_FORMAT_SAMPLES + ((".idx", IDX_CONTENT), (".sub", VOBSUB_CONTENT)),
    ids=("smi", "sami", "ttml", "dfxp", "microdvd", "idx", "vobsub"),
)
@pytest.mark.parametrize("archived", (False, True))
def test_common_subtitle_uploads_preserve_content(sup_modules, tmp_path, extension, content, archived):
    service = make_upload_service(sup_modules, tmp_path)
    session = tmp_path / "session"
    session.mkdir()
    name = f"VisionQuest.S01E01.chs{extension}"
    upload_name = "subtitles.zip" if archived else name
    upload_bytes = zip_content(name, content) if archived else content

    uploads = service.extract_subtitle_files(upload_name, upload_bytes, session)

    assert len(uploads) == 1
    assert uploads[0]["source_name"] == name
    assert uploads[0]["ext"] == extension
    assert Path(uploads[0]["stored_path"]).read_bytes() == content


@pytest.mark.parametrize(
    ("name", "content", "bitmap"),
    (
        ("subtitle.sup", b"", True),
        ("subtitle.IDX", IDX_CONTENT, True),
        ("subtitle.sub", VOBSUB_CONTENT, True),
        ("subtitle.sub", b"\x00\x00\x01\xbd" + bytes(20), True),
        ("subtitle.SUB", b"{0}{25}Hello\n", False),
        ("subtitle.sub", b"", False),
        ("subtitle.srt", VOBSUB_CONTENT, False),
        ("subtitle.exe", VOBSUB_CONTENT, False),
    ),
)
def test_bitmap_classification_uses_format_and_supplied_content(sup_modules, monkeypatch, name, content, bitmap):
    open_file = Mock(side_effect=AssertionError("supplied bytes must avoid file reads"))
    monkeypatch.setattr(Path, "open", open_file)

    assert sup_modules.formats.is_bitmap_subtitle(name, content) is bitmap
    open_file.assert_not_called()


@pytest.mark.parametrize(("content", "bitmap"), ((VOBSUB_CONTENT, True), (b"{0}{25}Hello\n", False)), ids=("vobsub", "microdvd"))
def test_sub_classification_reads_file_when_content_not_supplied(sup_modules, tmp_path, content, bitmap):
    source = tmp_path / "subtitle.sub"
    source.write_bytes(content)

    assert sup_modules.formats.is_bitmap_subtitle(source) is bitmap
    assert sup_modules.formats.is_text_subtitle(source) is not bitmap


def test_sub_classification_does_not_hide_missing_file(sup_modules, tmp_path):
    with pytest.raises(FileNotFoundError):
        sup_modules.formats.is_bitmap_subtitle(tmp_path / "missing.sub")


def test_sub_classification_reads_only_a_small_header(sup_modules, monkeypatch):
    handle = MagicMock()
    handle.__enter__.return_value.read.return_value = VOBSUB_CONTENT[:64]
    monkeypatch.setattr(Path, "open", Mock(return_value=handle))

    assert sup_modules.formats.is_bitmap_subtitle("subtitle.sub") is True
    handle.__enter__.return_value.read.assert_called_once_with(64)


def test_sub_classification_does_not_hide_unreadable_file(sup_modules, monkeypatch):
    monkeypatch.setattr(Path, "open", Mock(side_effect=PermissionError("permission denied")))

    with pytest.raises(PermissionError, match="permission denied"):
        sup_modules.formats.is_bitmap_subtitle("unreadable.sub")


@pytest.mark.parametrize("extension", (".sup", ".idx", ".exe", ".zip"))
def test_text_classification_rejects_bitmap_and_unsupported_formats(sup_modules, extension):
    assert sup_modules.formats.is_text_subtitle(f"subtitle{extension}", SUP_CONTENT) is False


@pytest.mark.parametrize(("extension", "content"), TEXT_FORMAT_SAMPLES, ids=("smi", "sami", "ttml", "dfxp", "microdvd"))
def test_text_classification_accepts_supported_text_formats(sup_modules, extension, content):
    assert sup_modules.formats.is_text_subtitle(f"subtitle{extension}", content) is True


@pytest.mark.parametrize(
    ("extension", "format_name"),
    (
        (".ass", "ass"), (".ssa", "ssa"), (".srt", "srt"), (".vtt", "vtt"),
        (".WEBVTT", "vtt"), (".smi", "sami"), (".sami", "sami"), (".ttml", "ttml"),
        (".dfxp", "ttml"), (".sub", "microdvd"), (".sbv", None), (".sup", None), (".idx", None),
    ),
)
def test_pysubs2_format_maps_supported_text_aliases(sup_modules, extension, format_name):
    assert sup_modules.formats.pysubs2_format(f"subtitle{extension}") == format_name


@pytest.mark.parametrize(
    ("filename", "expected"),
    (("download", "download.sup"), ("subtitle.zip", "subtitle.sup"), ("", "VisionQuest.sup")),
)
def test_online_pgs_content_overrides_missing_or_archive_extension(sup_modules, tmp_path, filename, expected):
    service = make_upload_service(sup_modules, tmp_path)
    service._decode_preview_bytes = Mock(side_effect=AssertionError("PGS must not be decoded as text"))

    assert service.normalize_online_download_name(filename, SUP_CONTENT, {"title": "VisionQuest"}) == expected
    service._decode_preview_bytes.assert_not_called()


@pytest.mark.parametrize(
    ("filename", "suffix"),
    (
        ("VisionQuest.S01E01.chs.sup", "chi"),
        ("VisionQuest.S01E01.cht.sup", "cht"),
        ("VisionQuest.S01E01.eng.sup", "eng"),
        ("VisionQuest.S01E01.chi&eng.SUP", "chi&eng"),
    ),
)
def test_sup_language_uses_filename(sup_modules, monkeypatch, filename, suffix):
    decode = Mock(side_effect=AssertionError("SUP must not be decoded as text"))
    monkeypatch.setattr(sup_modules.language, "decode_preview_bytes", decode)

    profile = sup_modules.language.detect_language_profile(filename, SUP_CONTENT, sup_modules.formats.SUBTITLE_EXTS)

    assert profile["suffix"] == suffix
    decode.assert_not_called()


def test_unmarked_sup_does_not_infer_language_from_binary(sup_modules, monkeypatch):
    decode = Mock(side_effect=AssertionError("SUP must not be decoded as text"))
    monkeypatch.setattr(sup_modules.language, "decode_preview_bytes", decode)
    misleading_content = ("\u4e2d\u6587" * 40 + " English words " * 40).encode("utf-8")

    profile = sup_modules.language.detect_language_profile(
        "VisionQuest.S01E01.sup", PGS_HEADER + misleading_content, sup_modules.formats.SUBTITLE_EXTS
    )

    assert profile["suffix"] == "und"
    decode.assert_not_called()


@pytest.mark.parametrize(("extension", "content"), ((".idx", IDX_CONTENT), (".sub", VOBSUB_CONTENT)), ids=("idx", "vobsub"))
def test_vobsub_language_never_decodes_bitmap_content(sup_modules, monkeypatch, extension, content):
    decode = Mock(side_effect=AssertionError("bitmap subtitles must not be decoded as text"))
    monkeypatch.setattr(sup_modules.language, "decode_preview_bytes", decode)

    profile = sup_modules.language.detect_language_profile(
        f"VisionQuest.S01E01{extension}", content, sup_modules.formats.SUBTITLE_EXTS
    )

    assert profile["suffix"] == "und"
    decode.assert_not_called()


def test_text_sub_language_can_use_dialogue(sup_modules):
    content = b"{0}{25}These English dialogue words identify this subtitle.\n" * 30

    profile = sup_modules.language.detect_language_profile(
        "VisionQuest.S01E01.sub", content, sup_modules.formats.SUBTITLE_EXTS
    )

    assert profile["suffix"] == "eng"


@pytest.mark.parametrize("size_mib", (21, 28))
def test_sup_zip_members_larger_than_text_limit_are_allowed(sup_modules, tmp_path, size_mib):
    service = make_upload_service(sup_modules, tmp_path)
    session = tmp_path / "session"
    session.mkdir()
    content = PGS_HEADER + bytes(size_mib * MIB - len(PGS_HEADER))

    uploads = service.extract_subtitle_files("large.zip", zip_content("large.chs.sup", content), session)

    assert len(uploads) == 1
    assert Path(uploads[0]["stored_path"]).read_bytes() == content


def test_sup_member_limit_is_50_mib(sup_modules):
    guard = sup_modules.upload.ArchiveResourceGuard("subtitles.zip")

    guard.check_member_size("maximum.SUP", 50 * MIB)
    with pytest.raises(sup_modules.upload.ArchiveResourceLimitError, match="52428801.*52428800"):
        guard.check_member_size("oversized.sup", 50 * MIB + 1)


def test_text_member_limit_remains_20_mib(sup_modules):
    guard = sup_modules.upload.ArchiveResourceGuard("subtitles.zip")

    guard.check_member_size("maximum.srt", 20 * MIB)
    with pytest.raises(sup_modules.upload.ArchiveResourceLimitError, match="20971521.*20971520"):
        guard.check_member_size("oversized.srt", 20 * MIB + 1)


def test_sup_total_extraction_limit_remains_80_mib(sup_modules):
    guard = sup_modules.upload.ArchiveResourceGuard("subtitles.zip")

    guard.accept_subtitle("first.sup", 40 * MIB)
    guard.accept_subtitle("second.sup", 40 * MIB)
    with pytest.raises(sup_modules.upload.ArchiveResourceLimitError, match="83886081.*83886080"):
        guard.accept_subtitle("third.sup", 1)


@pytest.mark.parametrize("language_suffix", ("chi", "cht", "eng", "und"))
def test_sup_write_skips_text_processing_and_preserves_binary(sup_modules, tmp_path, language_suffix):
    source = tmp_path / "uploaded.sup"
    source.write_bytes(SUP_CONTENT)
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    video = media_dir / "VisionQuest.S01E01.mkv"
    video.touch()
    target = {"id": "episode-1", "path": str(video), "basename": video.stem, "storage": "local"}
    writer, owner, simplify = make_bitmap_writer(sup_modules, tmp_path)
    operations = writer.build_write_operations(
        [{"upload_id": "uploaded", "target_id": target["id"], "ext": ".sup", "language_suffix": language_suffix}],
        {"uploaded": {"upload_id": "uploaded", "stored_path": str(source), "source_name": source.name, "ext": ".sup"}},
        {target["id"]: target},
    )

    written, fixed_count, simplified_count = writer.write_operations_to_disk(
        session_dir=tmp_path / "session", operations=operations, fix_timeline=True
    )

    output = media_dir / f"{video.stem}.{language_suffix}.sup"
    assert output.read_bytes() == SUP_CONTENT
    assert source.read_bytes() == SUP_CONTENT
    assert written[0]["output_path"] == str(output)
    assert written[0]["timeline"]["reason"] == "bitmap subtitle skipped"
    assert written[0]["timeline"]["applied"] is False
    assert fixed_count == simplified_count == 0
    assert written[0]["simplified"]["converted"] is False
    if language_suffix in {"chi", "cht"}:
        assert written[0]["simplified"]["reason"] == "bitmap subtitle skipped"
    assert owner._set_timeline_task.call_args.kwargs["status"] == "skipped"
    owner._run_timeline_fix.assert_not_called()
    simplify.assert_not_called()


def test_subtitle_write_does_not_refresh_emby_when_disabled(sup_modules, tmp_path):
    writer, owner, _ = make_bitmap_writer(sup_modules, tmp_path)
    refresh_factory = Mock()
    owner.services.emby_refresh = refresh_factory
    _, _, operations = make_bitmap_operations(sup_modules, tmp_path, writer)

    writer.write_operations_to_disk(session_dir=tmp_path / "session", operations=operations, fix_timeline=True)

    refresh_factory.assert_not_called()


def test_subtitle_write_refreshes_emby_once_for_batch(sup_modules, tmp_path):
    writer, owner, _ = make_bitmap_writer(sup_modules, tmp_path)
    owner._emby_refresh_after_subtitle_write = True
    refresh_service = Mock()
    refresh_factory = Mock(return_value=refresh_service)
    owner.services.emby_refresh = refresh_factory
    _, targets, operations = make_bitmap_operations(
        sup_modules, tmp_path, writer, target_ids=("episode-1", "episode-2")
    )

    written, _, _ = writer.write_operations_to_disk(
        session_dir=tmp_path / "session", operations=operations, fix_timeline=True
    )

    assert len(written) == 2
    refresh_factory.assert_called_once_with()
    refresh_service.refresh_for_videos.assert_called_once()
    refreshed_targets = refresh_service.refresh_for_videos.call_args.args[0]
    assert {target["path"] for target in refreshed_targets} == {target["path"] for target in targets.values()}


def test_subtitle_write_keeps_result_when_emby_refresh_fails(sup_modules, tmp_path):
    writer, owner, _ = make_bitmap_writer(sup_modules, tmp_path)
    owner._emby_refresh_after_subtitle_write = True
    refresh_service = Mock()
    refresh_service.refresh_for_videos.side_effect = RuntimeError("Emby unavailable")
    owner.services.emby_refresh = Mock(return_value=refresh_service)
    _, _, operations = make_bitmap_operations(sup_modules, tmp_path, writer)

    written, _, _ = writer.write_operations_to_disk(
        session_dir=tmp_path / "session", operations=operations, fix_timeline=True
    )

    assert len(written) == 1
    assert Path(written[0]["output_path"]).is_file()
    assert Path(written[0]["output_path"]).read_bytes() == SUP_CONTENT


def emby_refresh_test_runtime(monkeypatch, generation, *, http_module_name="app.adapters.network.http"):
    server = Mock()
    server._host = "http://emby.local:8096/"
    server._apikey = "test-api-key"
    server.is_inactive.return_value = False
    service_info = types.SimpleNamespace(instance=server)
    helper = Mock()
    helper.get_services.return_value = {"nas-emby": service_info}
    helper_module_name = "app.helper.mediaserver" if generation == "plugins.v2" else "app.application.mediaserver"
    helper_module = types.ModuleType(helper_module_name)
    helper_module.MediaServerHelper = Mock(return_value=helper)
    if helper_module_name == "app.application.mediaserver":
        monkeypatch.setitem(sys.modules, "app.application", types.ModuleType("app.application"))
    else:
        helper_package = types.ModuleType("app.helper")
        helper_package.mediaserver = helper_module
        monkeypatch.setitem(sys.modules, "app.helper", helper_package)
    monkeypatch.setitem(sys.modules, helper_module_name, helper_module)

    response = Mock(status_code=200)
    response.json.return_value = [
        {"Id": "global-library-refresh", "Key": "RefreshLibrary", "Name": "Scan media library", "State": "Idle"},
        {"Id": "external-subtitle-scan", "Key": "ScanExternalTrackTask", "Name": "Scan External Tracks", "State": "Idle"},
    ]
    request_utils = Mock()
    request_utils.get_res.return_value = response
    request_utils.post_res.return_value = Mock(status_code=204)
    http_module = types.ModuleType(http_module_name)
    http_module.RequestUtils = Mock(return_value=request_utils)
    if http_module_name == "app.adapters.network.http":
        monkeypatch.setitem(sys.modules, "app.adapters", types.ModuleType("app.adapters"))
        monkeypatch.setitem(sys.modules, "app.adapters.network", types.ModuleType("app.adapters.network"))
    else:
        monkeypatch.setitem(sys.modules, "app.utils", types.ModuleType("app.utils"))
    monkeypatch.setitem(sys.modules, http_module_name, http_module)
    return server, helper, request_utils


@pytest.mark.parametrize("http_module_name", ("app.adapters.network.http", "app.utils.http"))
def test_emby_refresh_starts_only_external_subtitle_scan_task(sup_modules, monkeypatch, http_module_name):
    server, helper, request_utils = emby_refresh_test_runtime(
        monkeypatch,
        sup_modules.generation,
        http_module_name=http_module_name,
    )
    service = sup_modules.load("integrations.emby_refresh").EmbyRefreshService(Mock())

    assert service.refresh_for_videos([{"path": "/media/movie.mkv", "media_type": "movie"}]) is True

    helper.get_services.assert_called_once_with()
    request_utils.get_res.assert_called_once_with(
        "http://emby.local:8096/emby/ScheduledTasks",
        params={"api_key": "test-api-key"},
        timeout=15,
    )
    request_utils.post_res.assert_called_once_with(
        "http://emby.local:8096/emby/ScheduledTasks/Running/external-subtitle-scan",
        params={"api_key": "test-api-key"},
        timeout=15,
    )
    server.refresh_library_by_items.assert_not_called()
    server.refresh_root_library.assert_not_called()


def test_emby_refresh_does_not_restart_an_active_external_scan(sup_modules, monkeypatch):
    server, _, request_utils = emby_refresh_test_runtime(monkeypatch, sup_modules.generation)
    request_utils.get_res.return_value.json.return_value[1]["State"] = "Running"
    service = sup_modules.load("integrations.emby_refresh").EmbyRefreshService(Mock())

    assert service.refresh_for_videos([{"path": "/media/show.mkv", "media_type": "tv"}]) is True

    request_utils.post_res.assert_not_called()
    server.refresh_root_library.assert_not_called()


def test_emby_refresh_falls_back_to_library_refresh_when_scan_task_is_missing(sup_modules, monkeypatch):
    _, _, request_utils = emby_refresh_test_runtime(monkeypatch, sup_modules.generation)
    request_utils.get_res.return_value.json.return_value = [
        {"Id": "library", "Key": "RefreshLibrary", "Name": "Scan media library", "State": "Idle"}
    ]
    service = sup_modules.load("integrations.emby_refresh").EmbyRefreshService(Mock())

    assert service.refresh_for_videos([{"path": "/media/movie.mkv", "media_type": "movie"}]) is True
    request_utils.post_res.assert_called_once_with(
        "http://emby.local:8096/emby/Library/Refresh",
        params={"api_key": "test-api-key"},
        timeout=15,
    )


def test_emby_refresh_recognizes_upstream_scan_task_key(sup_modules, monkeypatch):
    _, _, request_utils = emby_refresh_test_runtime(monkeypatch, sup_modules.generation)
    request_utils.get_res.return_value.json.return_value = [
        {"Id": "upstream-scan", "Key": "ScanExternalSubtitleTask", "State": "Idle"}
    ]
    service = sup_modules.load("integrations.emby_refresh").EmbyRefreshService(Mock())

    assert service.refresh_for_videos([{"path": "/media/movie.mkv", "media_type": "movie"}]) is True
    request_utils.post_res.assert_called_once_with(
        "http://emby.local:8096/emby/ScheduledTasks/Running/upstream-scan",
        params={"api_key": "test-api-key"},
        timeout=15,
    )


def test_emby_refresh_does_not_fallback_when_task_query_fails(sup_modules, monkeypatch):
    _, _, request_utils = emby_refresh_test_runtime(monkeypatch, sup_modules.generation)
    request_utils.get_res.return_value = Mock(status_code=503)
    service = sup_modules.load("integrations.emby_refresh").EmbyRefreshService(Mock())

    assert service.refresh_for_videos([{"path": "/media/movie.mkv", "media_type": "movie"}]) is False
    request_utils.post_res.assert_not_called()


def test_emby_refresh_does_not_fallback_when_dedicated_task_start_fails(sup_modules, monkeypatch):
    _, _, request_utils = emby_refresh_test_runtime(monkeypatch, sup_modules.generation)
    request_utils.post_res.return_value = Mock(status_code=500)
    service = sup_modules.load("integrations.emby_refresh").EmbyRefreshService(Mock())

    assert service.refresh_for_videos([{"path": "/media/movie.mkv", "media_type": "movie"}]) is False
    request_utils.post_res.assert_called_once()
    assert request_utils.post_res.call_args.args[0].endswith(
        "/emby/ScheduledTasks/Running/external-subtitle-scan"
    )


@pytest.mark.parametrize(("extension", "content"), ((".sup", SUP_CONTENT), (".idx", IDX_CONTENT), (".sub", VOBSUB_CONTENT)), ids=("sup", "idx", "vobsub"))
@pytest.mark.parametrize("language_suffix", ("eng", "und"))
def test_auto_organizes_bitmap_subtitles_without_ai(sup_modules, tmp_path, extension, content, language_suffix):
    module = sup_modules.load("auto_transfer.auto_transfer_write")
    source = tmp_path / f"uploaded{extension}"
    source.write_bytes(content)
    entry = {"id": "episode-1", "path": str(tmp_path / "episode.mkv")}
    prepared = {"upload_id": "uploaded", "stored_path": str(source), "source_name": source.name, "ext": extension}
    chosen = {"upload_id": "uploaded", "target_id": entry["id"], "language_suffix": language_suffix, "ext": extension}
    written_item = {"output_path": str(tmp_path / f"episode.{language_suffix}{extension}")}
    writer = types.SimpleNamespace(build_write_operations=Mock(return_value=[{"target_entry": entry}]))
    prepare_ai = Mock(side_effect=AssertionError("bitmap subtitles must not be submitted for AI translation"))
    submit_ai = Mock(side_effect=AssertionError("bitmap subtitles must not be submitted for AI translation"))
    write = Mock(return_value=([written_item], 0, 0))
    owner = types.SimpleNamespace(
        _normalize_text=sup_modules.language.normalize_text,
        _subtitle_writer=lambda: writer,
    )
    collaborators = module.AutoTransferWriteCollaborators(
        target_from_entry=lambda target: target,
        detect_language_profile=Mock(),
        write_operations_to_disk=write,
        prepare_online_ai_subtitle_overrides=prepare_ai,
        submit_autosub_for_entries=submit_ai,
        select_subtitle_items=Mock(return_value=[chosen]),
    )
    strategy = module.AutoTransferWriteStrategy(owner, collaborators=collaborators)

    result = strategy.write_prepared_uploads_for_entries(
        target_entries=[entry], prepared_uploads=[prepared], session_dir=tmp_path / "session"
    )

    assert result["status"] == "written"
    assert result["coverage_complete"] is True
    assert result["written_by_target"] == {entry["id"]: written_item}
    assert result["ai_count"] == 0
    write.assert_called_once()
    prepare_ai.assert_not_called()
    submit_ai.assert_not_called()


@pytest.mark.parametrize(("extension", "content"), ((".sup", SUP_CONTENT), (".idx", IDX_CONTENT), (".sub", VOBSUB_CONTENT)), ids=("sup", "idx", "vobsub"))
def test_history_timeline_skips_bitmap_subtitles(sup_modules, tmp_path, extension, content):
    module = sup_modules.load("matching.subtitle_history")
    source = tmp_path / f"episode.chi{extension}"
    source.write_bytes(content)
    entry = {"id": "episode-1", "path": str(tmp_path / "episode.mkv")}
    target = {**entry, "subtitles": [{"path": str(source), "ext": extension}]}
    writer = types.SimpleNamespace(build_write_operations=Mock(side_effect=AssertionError("bitmap subtitle must be skipped")))
    detect_language = Mock(side_effect=AssertionError("skipped subtitle must not be decoded"))
    services = types.SimpleNamespace(
        local_media_catalog=lambda: types.SimpleNamespace(resolve_targets=lambda target_ids: {entry["id"]: entry}),
        target_resolver=lambda: types.SimpleNamespace(target_from_entry=lambda target_entry: target),
        writer=lambda: writer,
    )
    owner = types.SimpleNamespace(
        services=services,
        _normalize_text=sup_modules.language.normalize_text,
        _detect_language_profile=detect_language,
    )
    history = module.SubtitleHistory(owner, http_exception=StubHttpException, logger=Mock(), target_entry_cache=Mock())

    operations, skipped, failed = history.existing_timeline_operations(
        [{"target_id": entry["id"], "subtitle_path": str(source)}]
    )

    assert operations == []
    assert failed == []
    assert len(skipped) == 1
    assert skipped[0]["subtitle_path"] == str(source)
    writer.build_write_operations.assert_not_called()
    detect_language.assert_not_called()


@pytest.mark.parametrize("selected_extension", (".idx", ".sub"))
@pytest.mark.parametrize("archived", (False, True))
def test_selecting_either_vobsub_file_writes_complete_pair(sup_modules, tmp_path, selected_extension, archived):
    service = make_upload_service(sup_modules, tmp_path)
    session = tmp_path / "session"
    session.mkdir()
    if archived:
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("season-1/VisionQuest.S01E01.chs.idx", IDX_CONTENT)
            archive.writestr("season-1/VisionQuest.S01E01.chs.sub", VOBSUB_CONTENT)
        prepared = service.extract_subtitle_files("subtitles.zip", output.getvalue(), session)
        assert {item["archive_member"] for item in prepared} == {
            "season-1/VisionQuest.S01E01.chs.idx", "season-1/VisionQuest.S01E01.chs.sub"
        }
    else:
        prepared = []
        for extension, content in ((".idx", IDX_CONTENT), (".sub", VOBSUB_CONTENT)):
            prepared.extend(service.extract_subtitle_files(f"VisionQuest.S01E01.chs{extension}", content, session))
    uploads = {item["upload_id"]: item for item in prepared}
    selected = next(item for item in prepared if item["ext"] == selected_extension)
    target = make_target(tmp_path)
    writer, owner, simplify = make_bitmap_writer(sup_modules, tmp_path)

    operations = writer.build_write_operations(
        [{"upload_id": selected["upload_id"], "target_id": target["id"], "ext": selected_extension, "language_suffix": "chi"}],
        uploads,
        {target["id"]: target},
    )
    written, fixed_count, simplified_count = writer.write_operations_to_disk(
        session_dir=session, operations=operations, fix_timeline=True
    )

    assert len(operations) == len(written) == 2
    media_dir = Path(target["path"]).parent
    assert (media_dir / f"{target['basename']}.chi.idx").read_bytes() == IDX_CONTENT
    assert (media_dir / f"{target['basename']}.chi.sub").read_bytes() == VOBSUB_CONTENT
    assert all(item["timeline"]["reason"] == "bitmap subtitle skipped" for item in written)
    assert all(item["simplified"]["converted"] is False for item in written)
    assert fixed_count == simplified_count == 0
    owner._run_timeline_fix.assert_not_called()
    simplify.assert_not_called()


def test_explicit_vobsub_pair_is_not_duplicated_and_normalizes_language(sup_modules, tmp_path):
    uploads = make_vobsub_uploads(tmp_path)
    target = make_target(tmp_path)
    writer, _, _ = make_bitmap_writer(sup_modules, tmp_path)

    operations = writer.build_write_operations(
        [
            {"upload_id": "idx", "target_id": target["id"], "language_suffix": "chs", "ext": ".idx"},
            {"upload_id": "sub", "target_id": target["id"], "language_suffix": "chi", "ext": ".sub"},
        ],
        uploads,
        {target["id"]: target},
    )

    assert len(operations) == 2
    assert {item["destination_name"] for item in operations} == {"episode-1.chi.idx", "episode-1.chi.sub"}


@pytest.mark.parametrize("selected_id", ("idx", "sub"))
def test_vobsub_missing_companion_is_rejected(sup_modules, tmp_path, selected_id):
    uploads = make_vobsub_uploads(tmp_path)
    target = make_target(tmp_path)
    writer, _, _ = make_bitmap_writer(sup_modules, tmp_path)

    with pytest.raises(StubHttpException, match="VobSub") as error:
        writer.build_write_operations(
            [{"upload_id": selected_id, "target_id": target["id"], "language_suffix": "chi"}],
            {selected_id: uploads[selected_id]},
            {target["id"]: target},
        )

    assert error.value.status_code == 400


@pytest.mark.parametrize("conflict", ("target", "language"))
def test_vobsub_pair_conflicting_explicit_mapping_is_rejected(sup_modules, tmp_path, conflict):
    uploads = make_vobsub_uploads(tmp_path)
    first = make_target(tmp_path)
    second = make_target(tmp_path, "episode-2")
    writer, _, _ = make_bitmap_writer(sup_modules, tmp_path)
    sub_item = {"upload_id": "sub", "target_id": first["id"], "language_suffix": "chi"}
    sub_item["target_id" if conflict == "target" else "language_suffix"] = second["id"] if conflict == "target" else "eng"

    with pytest.raises(StubHttpException, match="VobSub") as error:
        writer.build_write_operations(
            [{"upload_id": "idx", "target_id": first["id"], "language_suffix": "chi"}, sub_item],
            uploads,
            {first["id"]: first, second["id"]: second},
        )

    assert error.value.status_code == 400


@pytest.mark.parametrize("mismatch", ("directory", "archive", "stem"))
def test_vobsub_companion_must_come_from_same_archive_directory_and_name(sup_modules, tmp_path, mismatch):
    uploads = make_vobsub_uploads(tmp_path)
    if mismatch == "directory":
        uploads["sub"]["archive_member"] = "season-2/VisionQuest.S01E01.chs.sub"
    elif mismatch == "archive":
        uploads["sub"]["archive_name"] = "another.zip"
    else:
        uploads["sub"]["archive_member"] = "season-1/VisionQuest.S01E02.chs.sub"
    target = make_target(tmp_path)
    writer, _, _ = make_bitmap_writer(sup_modules, tmp_path)

    with pytest.raises(StubHttpException, match="VobSub"):
        writer.build_write_operations(
            [{"upload_id": "idx", "target_id": target["id"], "language_suffix": "chi"}],
            uploads,
            {target["id"]: target},
        )


def test_vobsub_ambiguous_companion_is_rejected(sup_modules, tmp_path):
    uploads = make_vobsub_uploads(tmp_path)
    duplicate = tmp_path / "duplicate.sub"
    duplicate.write_bytes(VOBSUB_CONTENT)
    uploads["duplicate"] = {**uploads["sub"], "upload_id": "duplicate", "stored_path": str(duplicate)}
    target = make_target(tmp_path)
    writer, _, _ = make_bitmap_writer(sup_modules, tmp_path)

    with pytest.raises(StubHttpException, match="VobSub"):
        writer.build_write_operations(
            [{"upload_id": "idx", "target_id": target["id"], "language_suffix": "chi"}],
            uploads,
            {target["id"]: target},
        )


def test_vobsub_idx_cannot_pair_with_text_sub(sup_modules, tmp_path):
    uploads = make_vobsub_uploads(tmp_path)
    Path(uploads["sub"]["stored_path"]).write_bytes(b"{0}{25}Hello\n")
    target = make_target(tmp_path)
    writer, _, _ = make_bitmap_writer(sup_modules, tmp_path)

    with pytest.raises(StubHttpException, match="VobSub"):
        writer.build_write_operations(
            [{"upload_id": "idx", "target_id": target["id"], "language_suffix": "chi"}],
            uploads,
            {target["id"]: target},
        )


def test_text_sub_needs_no_idx_companion(sup_modules, tmp_path):
    source = tmp_path / "subtitle.sub"
    source.write_bytes(b"{0}{25}Hello\n")
    target = make_target(tmp_path)
    writer, _, _ = make_bitmap_writer(sup_modules, tmp_path)

    operations = writer.build_write_operations(
        [{"upload_id": "text", "target_id": target["id"], "language_suffix": "eng", "ext": ".sub"}],
        {"text": {"upload_id": "text", "source_name": source.name, "stored_path": str(source), "ext": ".sub"}},
        {target["id"]: target},
    )

    assert len(operations) == 1
    assert operations[0]["destination_name"] == "episode-1.eng.sub"


@pytest.mark.parametrize(("extension", "content"), ((".idx", IDX_CONTENT), (".sub", VOBSUB_CONTENT)), ids=("idx", "vobsub"))
@pytest.mark.parametrize("download_name", ("", "subtitle.zip"))
def test_online_vobsub_magic_overrides_download_extension(sup_modules, tmp_path, extension, content, download_name):
    service = make_upload_service(sup_modules, tmp_path)
    service._decode_preview_bytes = Mock(side_effect=AssertionError("VobSub must not enter text detection"))

    filename = service.normalize_online_download_name(download_name, content, {"title": "VisionQuest"})

    assert filename == f"{'subtitle' if download_name else 'VisionQuest'}{extension}"
    service._decode_preview_bytes.assert_not_called()


def test_text_sub_member_limit_is_20_mib_after_content_detection(sup_modules):
    guard = sup_modules.upload.ArchiveResourceGuard("subtitles.zip")
    text_head = b"{0}{25}Hello\n"

    guard.check_member_size("subtitle.sub", 20 * MIB, raw_bytes=text_head)
    with pytest.raises(sup_modules.upload.ArchiveResourceLimitError, match="20971521.*20971520"):
        guard.check_member_size("subtitle.sub", 20 * MIB + 1, raw_bytes=text_head)


@pytest.mark.parametrize("bitmap", (False, True), ids=("microdvd", "vobsub"))
def test_sub_zip_size_limit_depends_on_content(sup_modules, tmp_path, bitmap):
    service = make_upload_service(sup_modules, tmp_path)
    session = tmp_path / "session"
    session.mkdir()
    header = VOBSUB_CONTENT[:64] if bitmap else b"{0}{25}Hello\n"
    content = header + bytes(21 * MIB - len(header))
    archive = zip_content("subtitle.sub", content)

    if not bitmap:
        with pytest.raises(sup_modules.upload.ArchiveResourceLimitError):
            service.extract_subtitle_files("subtitle.zip", archive, session)
        return
    uploads = service.extract_subtitle_files("subtitle.zip", archive, session)

    assert len(uploads) == 1
    assert Path(uploads[0]["stored_path"]).read_bytes() == content
