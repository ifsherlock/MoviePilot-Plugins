from __future__ import annotations

import importlib
import re
import sys
import types
from pathlib import Path

import pytest

from test_subtitlemanualupload_online import load_online_module


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(params=("plugins.v2", "plugins.v3"))
def plugin_modules(request):
    version = request.param
    plugin_path = ROOT / version / "subtitlemanualupload"
    package_name = f"strm_skip_test_{version.replace('.', '_')}"
    package = types.ModuleType(package_name)
    package.__path__ = [str(plugin_path)]
    sys.modules[package_name] = package
    for sub in ("catalog", "matching", "online_subtitles", "online_subtitles.providers"):
        sub_pkg = types.ModuleType(f"{package_name}.{sub}")
        sub_pkg.__path__ = [str(plugin_path / sub.replace(".", "/"))]
        sys.modules[f"{package_name}.{sub}"] = sub_pkg
    load_online_module()
    if version == "plugins.v3":
        sdk_mod = types.ModuleType("app.sdk")
        sdk_cfg = types.ModuleType("app.sdk.config")
        sdk_cfg.settings = sys.modules["app.core.config"].settings
        sdk_log = types.ModuleType("app.sdk.logging")
        sdk_log.logger = sys.modules["app.log"].logger
        sys.modules.setdefault("app.sdk", sdk_mod)
        sys.modules.setdefault("app.sdk.config", sdk_cfg)
        sys.modules.setdefault("app.sdk.logging", sdk_log)
    try:
        yield types.SimpleNamespace(
            media_metadata=importlib.import_module(f"{package_name}.catalog.media_metadata"),
            language=importlib.import_module(f"{package_name}.matching.subtitle_language"),
            subdl=importlib.import_module(f"{package_name}.online_subtitles.providers.subdl").SubDLProvider,
        )
    finally:
        for name in list(sys.modules):
            if name == package_name or name.startswith(f"{package_name}."):
                sys.modules.pop(name, None)


def test_is_chinese_transfer_media_skips_filename_with_chinese_sub_tags(plugin_modules):
    mm = plugin_modules.media_metadata
    cat_pat = re.compile(r"国产|华语")
    common_kwargs = {
        "auto_media_for_entry_func": lambda entry: {"tmdb_id": 94404, "original_language": "ja", "origin_country": ["JP"]},
        "normalize_text": lambda v: str(v or "").strip(),
        "chinese_language_codes": {"zh", "zh-hans"},
        "chinese_country_codes": {"cn", "tw", "hk"},
        "chinese_region_names": {"china"},
        "chinese_category_pattern": cat_pat,
    }

    for path in (
        "/strm/Anime/Show S02E01 1080p.WEB-DL.AAC.CHS-CHT-LINETV@UBWEB.strm",
        "/strm/Anime/Show S01E11 1080p.BluRay.x265.FLAC.CHS-ADE.strm",
        "/strm/Anime/Show S01E01.zh-hans.mkv",
        "/strm/Anime/Show S01E01.简繁内封.strm",
    ):
        matched, reason = mm.is_chinese_transfer_media({"path": path}, **common_kwargs)
        assert matched is True, path
        assert "文件名包含中文字幕标识" in reason

    for path in (
        "/strm/Anime/Show S01E47 1080p.H265.FLAC 2.0.JA.strm",
        "/strm/Anime/Show S01E01 1080p.x265.FLAC 2.0-VCB-Studio.strm",
        "/strm/Movies/Example.Movie.2024.1080p.WEB-DL.mkv",
    ):
        matched, _ = mm.is_chinese_transfer_media({"path": path}, **common_kwargs)
        assert matched is False, path


def test_detect_language_profile_does_not_match_ascii_substring_in_words(plugin_modules):
    language = plugin_modules.language
    english_srt = (
        b"1\n00:00:01,000 --> 00:00:03,500\n"
        b"I will declare it here and now. Never experienced a truly fulfilling summer in this world.\n"
    ) * 4

    profile = language.detect_language_profile(
        "The.Tatami.Time.Machine.Blues.S01E01.WEBRip.x264-ION10.srt",
        english_srt,
        {".srt", ".ass"},
    )
    assert profile["suffix"] == "eng", profile

    assert language.detect_language_profile("Show.chs.S01E01.srt", english_srt, {".srt"})["suffix"] == "chi&eng"
    assert language.detect_language_profile("Show.S01E01.zh-cn.srt", b"", {".srt"})["suffix"] == "chi"


def test_subdl_429_trips_quota_cooldown_and_short_circuits(plugin_modules):
    SubDLProvider = plugin_modules.subdl
    SubDLProvider._quota_cooldown_until = 0.0

    class _FakeFetcher:
        def __init__(self):
            self.calls = 0

        def get_bytes(self, url, referer=""):
            self.calls += 1
            raise ValueError('下载失败 HTTP 429: {"error":"api_download_limit_exceeded","retryAfterSeconds":1200}')

    fetcher = _FakeFetcher()
    provider = SubDLProvider(fetcher, api_key="test-key")
    try:
        with pytest.raises(ValueError, match="429"):
            provider.download({"download_url": "/subtitle/123.zip"})
        assert fetcher.calls == 1
        assert SubDLProvider._in_quota_cooldown() is True
        assert provider.search_all(["Example"], [{"media_type": "movie"}], "movie") == []
        with pytest.raises(ValueError, match="配额已达上限"):
            provider.download({"download_url": "/subtitle/124.zip"})
        assert fetcher.calls == 1
    finally:
        SubDLProvider._quota_cooldown_until = 0.0
