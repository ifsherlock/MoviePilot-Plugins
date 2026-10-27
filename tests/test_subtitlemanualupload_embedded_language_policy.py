from __future__ import annotations

import importlib
import json
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


@pytest.mark.parametrize("tracks,expected", [
    ([track()], True),
    ([track(title="中日双语")], False),
    ([track(title="双语")], False),
    ([track(title="中文字幕"), track(language="eng", title="English")], False),
    ([track(disposition={"forced": 1})], False),
    ([track(disposition={"comment": 1})], False),
    ([track(title="中英双语 歌词")], False),
    ([track(codec="hdmv_pgs_subtitle")], False),
])
def test_strict_existing_track_policy_keeps_usability_filters(embedded_policy, tracks, expected):
    embedded_policy.probe.return_value = types.SimpleNamespace(stdout=json.dumps({"streams": tracks}))
    target = {}

    assert embedded_policy.language.auto_target_has_chinese_subtitle(
        embedded_policy.entry,
        target,
        subtitle_inventory=embedded_policy.inventory,
        language_priority=["chi&eng"],
        strict=True,
    ) is expected
    assert embedded_policy.probe.call_count == 1
    assert embedded_policy.probe.call_args.args[0][0] == "ffprobe"


def test_cached_track_metadata_uses_current_language_selection(embedded_policy):
    embedded_policy.probe.return_value = types.SimpleNamespace(stdout=json.dumps({"streams": [track()]}))
    for priority, expected in [(["chi&eng"], True), (["chi&jp"], False)]:
        assert embedded_policy.language.auto_target_has_chinese_subtitle(
            embedded_policy.entry,
            {},
            subtitle_inventory=embedded_policy.inventory,
            language_priority=priority,
            strict=True,
        ) is expected
    assert embedded_policy.probe.call_count == 1
