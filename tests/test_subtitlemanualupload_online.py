from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path


def load_online_module():
    root = Path(__file__).resolve().parents[1]
    module_path = root / "plugins.v2" / "subtitlemanualupload" / "online_subtitle.py"

    app_module = types.ModuleType("app")
    core_module = types.ModuleType("app.core")
    config_module = types.ModuleType("app.core.config")
    config_module.settings = types.SimpleNamespace(PROXY=None, PROXY_SERVER=None)
    log_module = types.ModuleType("app.log")
    log_module.logger = types.SimpleNamespace(
        info=lambda *args, **kwargs: None,
        warning=lambda *args, **kwargs: None,
        error=lambda *args, **kwargs: None,
    )
    sys.modules.setdefault("app", app_module)
    sys.modules.setdefault("app.core", core_module)
    sys.modules.setdefault("app.core.config", config_module)
    sys.modules.setdefault("app.log", log_module)

    spec = importlib.util.spec_from_file_location("subtitlemanualupload_online_subtitle", module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeFetcher:
    def get_text(self, url, *, referer=""):
        if "/search/" in url:
            return 200, '<a href="/d/123">Example Show</a>', url
        if "/d/123" in url:
            return 200, '<a href="/a/abc">Example.Show.S01E02.1080p.chs&eng.ass</a>', url
        return 404, "", url


class ZimukuFakeFetcher:
    def get_text(self, url, *, referer=""):
        return 200, '<a href="/detail/456">Example Show S01E02 简体字幕</a>', url


def test_build_search_keywords_prefers_season_package():
    module = load_online_module()
    media = {"media_type": "tv", "title": "Example Show", "year": "2025"}
    targets = [
        {"media_type": "tv", "title": "Example Show", "season": 1, "episode": 1, "basename": "Example.Show.S01E01"},
        {"media_type": "tv", "title": "Example Show", "season": 1, "episode": 2, "basename": "Example.Show.S01E02"},
    ]

    keywords = module.build_search_keywords(media, targets, "season")

    assert keywords[:2] == ["Example Show S01", "Example Show 第1季"]


def test_subhd_provider_parses_detail_subtitle_rows():
    module = load_online_module()
    provider = module.SubhdProvider(FakeFetcher())
    targets = [{"season": 1, "episode": 2}]

    results = provider.search("Example Show S01E02", targets, "episode")

    assert len(results) == 1
    assert results[0].provider == "subhd"
    assert results[0].result_id == "abc"
    assert results[0].download_url == "https://subhd.tv/down/abc"
    assert results[0].season == 1
    assert results[0].episode == 2


def test_zimuku_results_are_marked_manual_only():
    module = load_online_module()
    provider = module.ZimukuProvider(ZimukuFakeFetcher())
    targets = [{"season": 1, "episode": 2}]

    results = provider.search("Example Show S01E02", targets, "episode")

    assert len(results) == 1
    assert results[0].provider == "zimuku"
    assert results[0].downloadable is False
