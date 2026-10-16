from __future__ import annotations

import importlib
import sys
import types
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(params=["plugins.v2", "plugins.v3"])
def subtitle_package(request, monkeypatch):
    package_name = f"subtitle_text_formats_{request.param.replace('.', '_')}"
    package = types.ModuleType(package_name)
    package.__path__ = [str(ROOT / request.param / "subtitlemanualupload")]
    monkeypatch.setitem(sys.modules, package_name, package)
    return package_name


def load_module(package_name, module_name):
    return importlib.import_module(f"{package_name}.{module_name}")


def make_ttml(text="Hello", encoding="utf-8"):
    return (
        f'<?xml version="1.0" encoding="{encoding}"?>'
        '<tt xmlns="http://www.w3.org/ns/ttml"><body><div>'
        f'<p begin="00:00:01.000" end="00:00:02.000">{text}<br/>Next</p>'
        '</div></body></tt>'
    ).encode(encoding)


def make_sami(text="Hello", encoding="utf-8"):
    return (
        '<SAMI><HEAD><META HTTP-EQUIV="Content-Type" '
        f'CONTENT="text/html; charset={encoding}">'
        '<STYLE>.繁體 { Name: 繁體; }</STYLE></HEAD><BODY>'
        f'<SYNC Start=1000><P Class="繁體">{text}<br>Next'
        '<SYNC Start=2000><P Class="繁體">&nbsp;</BODY></SAMI>'
    ).encode(encoding)


@pytest.mark.parametrize("extension,data", [
    (".sup", b"PG\x00\x00\x00\x01"),
    (".idx", b"# VobSub index file, v7\n"),
    (".sub", b"\x00\x00\x01\xba\x00\x01\x02\x03"),
])
def test_low_level_simplification_rejects_bitmap_subtitles(subtitle_package, tmp_path, extension, data):
    tongwen = load_module(subtitle_package, "matching.tongwen")
    source = tmp_path / f"source{extension}"
    output = tmp_path / f"output{extension}"
    source.write_bytes(data)

    with pytest.raises(ValueError, match="图片字幕"):
        tongwen.convert_subtitle_file_to_simplified(source, output)

    assert source.read_bytes() == data
    assert not output.exists()


@pytest.mark.parametrize("extension", [".ttml", ".dfxp"])
def test_ttml_simplification_writes_valid_utf8_and_preserves_cues(subtitle_package, tmp_path, extension):
    pytest.importorskip("pysubs2")
    tongwen = load_module(subtitle_package, "matching.tongwen")
    source = tmp_path / f"source{extension}"
    output = tmp_path / f"output{extension}"
    source.write_bytes(make_ttml("這是一個繁體字幕", encoding="utf-16"))

    assert tongwen.convert_subtitle_file_to_simplified(source, output) is True

    tree = ET.fromstring(output.read_bytes())
    cue = tree.find(".//{http://www.w3.org/ns/ttml}p")
    assert cue.attrib["begin"] == "00:00:01.000"
    assert cue.attrib["end"] == "00:00:02.000"
    assert "这是一个繁体字幕" in "".join(cue.itertext())
    assert cue.find("{http://www.w3.org/ns/ttml}br") is not None


@pytest.mark.parametrize("extension", [".smi", ".sami"])
def test_sami_simplification_keeps_classes_styles_and_encoding_consistent(subtitle_package, tmp_path, extension):
    bs4 = pytest.importorskip("bs4")
    tongwen = load_module(subtitle_package, "matching.tongwen")
    source = tmp_path / f"source{extension}"
    output = tmp_path / f"output{extension}"
    source.write_bytes(make_sami("這是一個繁體字幕", encoding="big5"))

    assert tongwen.convert_subtitle_file_to_simplified(source, output) is True

    document = bs4.BeautifulSoup(output.read_bytes(), "html.parser")
    assert document.find("p").get("class") == ["繁體"]
    assert "繁體" in document.find("style").text
    assert "这是一个繁体字幕" in document.find("p").text
    assert "utf-8" in document.find("meta").get("content")
    assert [element.get("start") for element in document.find_all("sync")] == ["1000", "2000"]


@pytest.mark.parametrize("extension", [".dfxp", ".webvtt", ".smi", ".sami"])
def test_timeline_handles_format_aliases_and_sami(subtitle_package, tmp_path, extension):
    pysubs2 = pytest.importorskip("pysubs2")
    vad = load_module(subtitle_package, "timeline.timeline_vad")
    timeline_io = load_module(subtitle_package, "timeline.timeline_io")
    source = tmp_path / f"source{extension}"
    output = tmp_path / f"output{extension}"
    if extension == ".dfxp":
        source.write_bytes(make_ttml())
    elif extension in {".smi", ".sami"}:
        source.write_bytes(make_sami())
    else:
        source.write_text("WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nHello\n", encoding="utf-8")

    timeline_io.save_adjusted_subtitle(
        pysubs2, source, output, 1.5, 0.5, load_subtitle_file=vad.load_subtitle_file,
    )

    events = vad.load_subtitle_file(pysubs2, output).events
    assert events[0].start == 2000
    if extension not in {".smi", ".sami"}:
        assert events[0].end == 3500
    assert "Hello" in events[0].plaintext


def test_timeline_loader_rejects_bitmap_before_calling_parser(subtitle_package, tmp_path):
    vad = load_module(subtitle_package, "timeline.timeline_vad")
    source = tmp_path / "source.sub"
    source.write_bytes(b"\x00\x00\x01\xba\x00\x01")
    parser = types.SimpleNamespace(load=lambda *args, **kwargs: pytest.fail("bitmap reached text parser"))

    with pytest.raises(ValueError, match="图片字幕"):
        vad.load_subtitle_file(parser, source)


def test_sami_loader_honors_declared_big5_encoding(subtitle_package, tmp_path):
    pysubs2 = pytest.importorskip("pysubs2")
    pytest.importorskip("bs4")
    vad = load_module(subtitle_package, "timeline.timeline_vad")
    source = tmp_path / "source.smi"
    source.write_bytes(make_sami("這是一個繁體字幕", encoding="big5"))

    assert "這是一個繁體字幕" in vad.load_subtitle_file(pysubs2, source).events[0].plaintext


def make_online_ai_service(package_name, monkeypatch):
    api_module = types.ModuleType(f"{package_name}.api.online_api")
    api_module.download_online_results_to_uploads = lambda *args, **kwargs: None
    monkeypatch.setitem(sys.modules, api_module.__name__, api_module)
    online_module = types.ModuleType(f"{package_name}.online.online_subtitle")
    online_module.CaptchaRequiredError = type("CaptchaRequiredError", (Exception,), {})
    monkeypatch.setitem(sys.modules, online_module.__name__, online_module)
    target_module = types.ModuleType(f"{package_name}.catalog.target_resolver")
    target_module.auto_fill_missing_targets = lambda *args, **kwargs: None
    target_module.suggest_target = lambda *args, **kwargs: "target"
    monkeypatch.setitem(sys.modules, target_module.__name__, target_module)
    module = load_module(package_name, "online.online_ai")
    owner = types.SimpleNamespace(
        _normalize_text=lambda value: str(value or "").strip(),
        _auto_ass_to_srt_for_ai=False,
        _detect_language_profile=lambda name, data: {"suffix": "eng", "label": "English"},
    )
    logger = types.SimpleNamespace(info=lambda *args, **kwargs: None, warning=lambda *args, **kwargs: None)
    return module.OnlineAiService(owner, http_exception=Exception, logger=logger, check_timeline_fixer_dependencies=None)


@pytest.mark.parametrize("extension", [".smi", ".sami", ".ttml", ".dfxp", ".vtt", ".webvtt"])
def test_foreign_text_formats_convert_to_ai_srt_with_ass_switch_disabled(subtitle_package, monkeypatch, tmp_path, extension):
    pysubs2 = pytest.importorskip("pysubs2")
    service = make_online_ai_service(subtitle_package, monkeypatch)
    source = tmp_path / f"source.eng{extension}"
    if extension in {".smi", ".sami"}:
        source.write_bytes(make_sami())
    elif extension in {".ttml", ".dfxp"}:
        source.write_bytes(make_ttml())
    else:
        source.write_text("WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nHello\n", encoding="utf-8")

    result = service.ai_ready_prepared_uploads(session_dir=tmp_path, prepared_uploads=[{
        "upload_id": "foreign", "source_name": source.name, "stored_path": str(source), "ext": extension,
    }])

    assert len(result) == 1
    assert result[0]["ext"] == ".srt"
    assert result[0]["converted_from_ext"] == extension
    assert "Hello" in pysubs2.load(result[0]["stored_path"]).events[0].plaintext


def test_bitmap_and_disabled_ass_never_reach_ai_parser(subtitle_package, monkeypatch, tmp_path):
    service = make_online_ai_service(subtitle_package, monkeypatch)
    service.load_pysubs2_file = lambda path: pytest.fail("ineligible subtitle reached AI parser")
    uploads = []
    for extension, data in [(".sup", b"PG\x00"), (".idx", b"# VobSub"), (".sub", b"\x00\x00\x01\xba"), (".ass", b"[Script Info]")]:
        source = tmp_path / f"source{extension}"
        source.write_bytes(data)
        uploads.append({"upload_id": extension, "source_name": source.name, "stored_path": str(source), "ext": extension})

    assert service.ai_ready_prepared_uploads(session_dir=tmp_path, prepared_uploads=uploads) == []


def test_new_text_format_parse_error_is_reported(subtitle_package, monkeypatch, tmp_path):
    pytest.importorskip("pysubs2")
    service = make_online_ai_service(subtitle_package, monkeypatch)
    source = tmp_path / "source.dfxp"
    source.write_text("<invalid", encoding="utf-8")

    with pytest.raises(RuntimeError, match="source.dfxp"):
        service.ai_ready_prepared_uploads(session_dir=tmp_path, prepared_uploads=[{
            "upload_id": "bad", "source_name": source.name, "stored_path": str(source), "ext": ".dfxp",
        }])
