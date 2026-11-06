from __future__ import annotations

import importlib
import json
import shutil
import subprocess
import sys
import types
from collections import OrderedDict
from pathlib import Path
from unittest.mock import Mock

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(params=("plugins.v2", "plugins.v3"))
def embedded_policy(request, tmp_path):
    package_name = f"embedded_language_policy_{request.param.replace('.', '_')}"
    package = types.ModuleType(package_name)
    package.__path__ = [str(ROOT / request.param / "subtitlemanualupload")]
    sys.modules[package_name] = package
    try:
        language = importlib.import_module(f"{package_name}.matching.subtitle_language")
        catalog = importlib.import_module(f"{package_name}.catalog.subtitle_inventory")
        probe = Mock()
        inventory = catalog.SubtitleInventory(
            subtitle_exts={".srt", ".ass"},
            stream_exts={".strm"},
            embedded_text_codecs={"subrip", "ass"},
            embedded_image_codecs={"hdmv_pgs_subtitle"},
            embedded_probe_cache=OrderedDict(),
            embedded_probe_cache_max_size=10,
            trust_transfer_history_paths=False,
            normalize_text=language.normalize_text,
            normalize_language_suffix=language.normalize_language_suffix,
            detect_language_profile=lambda name, raw: language.detect_language_profile(name, raw, {".srt", ".ass"}),
            is_chinese_language_suffix=language.is_chinese_language_suffix,
            safe_int=lambda value, default=0: int(value) if value is not None else default,
            subtitle_backup_path=lambda path: path.with_suffix(".bak"),
            subprocess_module=types.SimpleNamespace(run=probe, PIPE=subprocess.PIPE, TimeoutExpired=subprocess.TimeoutExpired),
            logger_warning=Mock(),
        )
        video = tmp_path / "movie.mkv"
        video.write_bytes(b"video")
        yield types.SimpleNamespace(
            inventory=inventory,
            language=language,
            probe=probe,
            entry={"storage": "local", "path": str(video)},
        )
    finally:
        for name in list(sys.modules):
            if name == package_name or name.startswith(f"{package_name}."):
                sys.modules.pop(name, None)


@pytest.mark.parametrize("language_tag,title,expected", [
    ("chi", "中英双语", "chi&eng"),
    ("eng", "中英双语", "chi&eng"),
    ("und", "中英双语", "chi&eng"),
    ("chi", "中日双语", "chi&jp"),
    ("kor", "中韩双语", "chi&kr"),
    ("cht", "繁英双语", "cht&eng"),
    ("chi", "双语", "chi"),
    ("chi", "中文字幕", "chi"),
    ("eng", "English", "eng"),
])
def test_explicit_embedded_pair_title_refines_primary_language_tag(embedded_policy, language_tag, title, expected):
    assert embedded_policy.inventory.embedded_subtitle_language_suffix(language_tag, title) == expected


def track(language="chi", title="中英双语", *, codec="subrip", disposition=None):
    return {
        "index": 1,
        "codec_name": codec,
        "tags": {"language": language, "title": title},
        "disposition": disposition or {},
    }


@pytest.mark.parametrize("strict", [False, True])
@pytest.mark.parametrize("tracks,expected", [
    ([track()], True),
    ([track(title="中文字幕")], False),
    ([track(title="中日双语")], False),
    ([track(title="双语")], False),
    ([track(title="中文字幕"), track(language="eng", title="English")], False),
    ([track(disposition={"forced": 1})], False),
    ([track(disposition={"comment": 1})], False),
    ([track(title="中英双语 歌词")], False),
    ([track(codec="hdmv_pgs_subtitle")], False),
])
def test_required_pair_keeps_embedded_track_usability_filters(embedded_policy, tracks, expected, strict):
    embedded_policy.probe.return_value = types.SimpleNamespace(stdout=json.dumps({"streams": tracks}))
    target = {}

    assert embedded_policy.language.auto_target_has_chinese_subtitle(
        embedded_policy.entry,
        target,
        subtitle_inventory=embedded_policy.inventory,
        language_priority=["chi&eng", "chi"],
        strict=strict,
    ) is expected
    assert embedded_policy.probe.call_count == 1
    assert embedded_policy.probe.call_args.args[0][0] == "ffprobe"


@pytest.mark.parametrize("strict", [False, True])
def test_cached_track_metadata_uses_current_language_selection(embedded_policy, strict):
    embedded_policy.probe.return_value = types.SimpleNamespace(stdout=json.dumps({"streams": [track()]}))
    for priority, expected in [(["chi&eng"], True), (["chi&jp"], False)]:
        assert embedded_policy.language.auto_target_has_chinese_subtitle(
            embedded_policy.entry,
            {},
            subtitle_inventory=embedded_policy.inventory,
            language_priority=priority,
            strict=strict,
        ) is expected
    assert embedded_policy.probe.call_count == 1


def test_trusting_transfer_history_never_probes_embedded_tracks(embedded_policy):
    embedded_policy.inventory._trust_transfer_history_paths = True

    assert not embedded_policy.language.auto_target_has_chinese_subtitle(
        embedded_policy.entry,
        {},
        subtitle_inventory=embedded_policy.inventory,
        language_priority=["chi&eng"],
        strict=False,
    )
    embedded_policy.probe.assert_not_called()


@pytest.mark.parametrize("disposition,expected", [("0", True), ("forced", False), ("comment", False)])
def test_real_mkv_probe_rejects_forced_and_comment_tracks(embedded_policy, tmp_path, disposition, expected):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("ffmpeg and ffprobe are required to verify real container dispositions")
    subtitle = tmp_path / "track.srt"
    subtitle.write_text("1\n00:00:00,000 --> 00:00:01,000\n这是中文字幕。\nThis is an English subtitle.\n", encoding="utf-8")
    video = Path(embedded_policy.entry["path"])
    subprocess.run(
        [
            "ffmpeg", "-v", "error", "-nostdin", "-y",
            "-f", "lavfi", "-i", "color=c=black:s=16x16:r=1:d=1",
            "-i", str(subtitle), "-map", "0:v:0", "-map", "1:0",
            "-c:v", "ffv1", "-c:s", "srt",
            "-metadata:s:s:0", "language=chi",
            "-metadata:s:s:0", "title=中英双语",
            "-disposition:s:0", disposition, str(video),
        ],
        capture_output=True, check=True, timeout=15,
    )
    # First verify the fixture really carries the container flag under test.
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "s", "-show_streams", "-of", "json", str(video)],
        capture_output=True, text=True, encoding="utf-8", check=True, timeout=10,
    )
    stream = json.loads(probe.stdout)["streams"][0]
    assert stream["disposition"].get(disposition, 0) == (0 if disposition == "0" else 1)
    embedded_policy.inventory._subprocess = subprocess

    assert embedded_policy.language.auto_target_has_chinese_subtitle(
        embedded_policy.entry,
        {},
        subtitle_inventory=embedded_policy.inventory,
        language_priority=["chi&eng"],
        strict=False,
    ) is expected
