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


class AssrtFakeFetcher:
    def get_text(self, url, *, referer=""):
        if "/sub/123" in url:
            return 200, '<a href="/download/123.zip">下载字幕</a>', url
        return 200, '<a href="/sub/123">Example Show S01E02 简体字幕.zip</a>', url


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


def test_assrt_provider_parses_web_results_without_token():
    module = load_online_module()
    provider = module.AssrtProvider(AssrtFakeFetcher())
    targets = [{"season": 1, "episode": 2}]

    results = provider.search("Example Show S01E02", targets, "episode")

    assert len(results) == 1
    assert results[0].provider == "assrt"
    assert results[0].source == "射手网(伪)"
    assert results[0].downloadable is True
    assert results[0].page_url == "https://2.assrt.net/sub/123"


def test_provider_roots_are_normalized_with_fallbacks():
    module = load_online_module()

    roots = module.normalize_provider_roots(
        {
            "subhd": "https://sub.example/",
            "zimuku": "ftp://invalid.example",
            "assrt": "",
        }
    )

    assert roots["subhd"] == "https://sub.example"
    assert roots["zimuku"] == "https://zimuku.org"
    assert roots["assrt"] == "https://2.assrt.net"


def test_socks5h_proxy_is_normalized_for_playwright():
    module = load_online_module()

    proxy = module._playwright_proxy_from_value({"server": "socks5h://user:pass@example.test:1080"})

    assert proxy["server"] == "socks5://example.test:1080"
    assert proxy["username"] == "user"
    assert proxy["password"] == "pass"


def test_online_service_defaults_to_no_proxy():
    module = load_online_module()

    service = module.OnlineSubtitleSearchService()

    assert service.fetcher.use_proxy is False


def test_provider_network_errors_are_compacted():
    module = load_online_module()

    class FailingProvider(module.BaseSubtitleProvider):
        provider_id = "subhd"
        display_name = "SubHD"

        def manual_url(self, keyword):
            return f"https://subhd.tv/search/{keyword}"

        def search(self, keyword, targets, scope):
            raise ValueError("<urlopen error [Errno 104] Connection reset by peer>")

    service = module.OnlineSubtitleSearchService(use_proxy=False)
    service.providers = {"subhd": FailingProvider(None)}
    service.fetcher = types.SimpleNamespace(available=lambda: True, close=lambda: None, engine=module.DEFAULT_ENGINE)

    result = service.search(
        keywords=["Example S01", "Example 第1季", "Example.S01E01"],
        providers=["subhd"],
        targets=[],
        scope="season",
    )

    assert result["results"] == []
    assert len(result["messages"]) == 1
    assert result["messages"][0]["provider"] == "subhd"
    assert "<urlopen" not in result["messages"][0]["message"]
    assert "已尝试 3 个关键词" in result["messages"][0]["message"]
