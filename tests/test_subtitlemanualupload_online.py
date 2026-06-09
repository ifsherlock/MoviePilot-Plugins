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
            return 200, '<a href="/a/abc">Example.Show.S01E02.1080p.chs&eng.ass</a>', url
        if "/a/abc" in url:
            return 200, '<a href="/down/abc">下载字幕文件</a>', url
        return 404, "", url


class SubhdInteractiveDownloadFetcher(FakeFetcher):
    def __init__(self, *, interactive_ok=True):
        self.interactive_ok = interactive_ok
        self.interactive_calls = []

    def get_bytes(self, url, *, referer=""):
        html = "<html><title>验证</title><body>请输入验证码后下载字幕</body></html>".encode()
        return "verify.html", html, url

    def get_bytes_interactive(self, url, *, referer="", captcha_code=""):
        self.interactive_calls.append((url, referer, captcha_code))
        if not self.interactive_ok:
            raise ValueError("ocr failed")
        return "Example.Show.S01E02.zip", b"PK\x03\x04subtitle", url


class ZimukuFakeFetcher:
    def get_text(self, url, *, referer=""):
        return 200, '<a href="/detail/456">Example Show S01E02 简体字幕</a>', url


class ZimukuDirectDownloadFetcher:
    def __init__(self):
        self.direct_calls = []
        self.interactive_calls = []

    def get_bytes(self, url, *, referer=""):
        self.direct_calls.append((url, referer))
        return "example.srt", b"1\r\n00:00:01,000 --> 00:00:02,000\r\nHi", url

    def get_bytes_interactive(self, url, *, referer="", captcha_code=""):
        self.interactive_calls.append((url, referer, captcha_code))
        raise AssertionError("Zimuku direct download should not use interactive flow first")


class ZimukuInteractiveFallbackFetcher(ZimukuDirectDownloadFetcher):
    def get_bytes(self, url, *, referer=""):
        self.direct_calls.append((url, referer))
        return "404.html", b"<html><body>404</body></html>", url

    def get_bytes_interactive(self, url, *, referer="", captcha_code=""):
        self.interactive_calls.append((url, referer, captcha_code))
        return "example.srt", b"1\r\n00:00:01,000 --> 00:00:02,000\r\nHi", "https://s.zimuku.org/download/token"


class ZimukuSecurityFetcher:
    def __init__(self):
        self.verified = False
        self.urls = []
        self.cookies = []

    def get_text(self, url, *, referer=""):
        self.urls.append(url)
        if "security_verify_img=3132333435" in url:
            self.verified = True
            return 200, "", url
        if self.verified:
            return 200, '<a href="/detail/456">Example Show S01E02 简体字幕</a>', url
        html = '<title>网站防火墙</title><img src="data:image/bmp;base64,AAAA">'
        return 404, html, url

    def set_cookie(self, name, value, domain):
        self.cookies.append((name, value, domain))


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


def test_subhd_result_links_keep_longer_duplicate_title():
    module = load_online_module()
    provider = module.SubhdProvider(FakeFetcher())

    links = provider._collect_result_links(
        '<a href="/a/abc">灵魂战车</a>'
        '<a href="/a/abc">Ghost.Rider.2007.Extended.Cut.1080p.BluRay.chseng</a>'
    )

    assert links == [
        ("https://subhd.tv/a/abc", "Ghost.Rider.2007.Extended.Cut.1080p.BluRay.chseng")
    ]


def test_subhd_html_download_response_is_reported_as_verification():
    module = load_online_module()

    html = "<html><title>验证</title><body>请输入验证码后下载字幕</body></html>".encode()
    reason = module.SubhdProvider._html_download_reason(html, "https://subhd.tv/down/abc")

    assert "验证码" in reason
    assert "OCR" in reason


def test_subhd_html_download_uses_interactive_without_user_captcha():
    module = load_online_module()
    fetcher = SubhdInteractiveDownloadFetcher()
    provider = module.SubhdProvider(fetcher)

    filename, content = provider.download({
        "result_id": "abc",
        "page_url": "https://subhd.tv/a/abc",
        "download_url": "https://subhd.tv/down/abc",
        "title": "Example Show S01E02",
    })

    assert filename == "Example.Show.S01E02.zip"
    assert content.startswith(b"PK")
    assert fetcher.interactive_calls == [("https://subhd.tv/down/abc", "https://subhd.tv/a/abc", "")]

    result = provider._parse_subtitle_page(
        "https://subhd.tv/a/abc",
        "Example Show S01E02",
        [{"season": 1, "episode": 2}],
        "Example.Show.S01E02.1080p.chs&eng.ass",
    )
    assert "/api/sub/down" in result.download_steps


def test_subhd_interactive_failure_is_plain_download_error():
    module = load_online_module()
    fetcher = SubhdInteractiveDownloadFetcher(interactive_ok=False)
    provider = module.SubhdProvider(fetcher)

    try:
        provider.download({
            "result_id": "abc",
            "page_url": "https://subhd.tv/a/abc",
            "download_url": "https://subhd.tv/down/abc",
            "title": "Example Show S01E02",
        })
    except ValueError as exc:
        assert "自动仿真下载失败" in str(exc)
    else:
        raise AssertionError("SubHD interactive failure should raise ValueError")


def test_zimuku_results_are_downloadable_and_keep_steps():
    module = load_online_module()
    provider = module.ZimukuProvider(ZimukuFakeFetcher())
    targets = [{"season": 1, "episode": 2}]

    results = provider.search("Example Show S01E02", targets, "episode")

    assert len(results) == 1
    assert results[0].provider == "zimuku"
    assert results[0].downloadable is True
    assert results[0].requires_captcha is True
    assert "/dld" in results[0].download_steps
    assert "/download" in results[0].download_steps
    assert "security_verify_img" in results[0].download_steps


def test_zimuku_security_page_uses_ocr_verify_jump():
    helper_module = types.ModuleType("app.helper")
    ocr_module = types.ModuleType("app.helper.ocr")

    class FakeOcrHelper:
        def get_captcha_text(self, image_b64=None, **kwargs):
            return "12345"

    ocr_module.OcrHelper = FakeOcrHelper
    sys.modules["app.helper"] = helper_module
    sys.modules["app.helper.ocr"] = ocr_module

    module = load_online_module()
    fetcher = ZimukuSecurityFetcher()
    provider = module.ZimukuProvider(fetcher)

    results = provider.search("Example Show S01E02", [{"season": 1, "episode": 2}], "episode")

    assert len(results) == 1
    assert fetcher.verified is True
    assert any("security_verify_img=3132333435" in url for url in fetcher.urls)
    assert fetcher.cookies[0][0] == "srcurl"


def test_zimuku_download_source_tries_direct_file_before_interactive():
    module = load_online_module()
    fetcher = ZimukuDirectDownloadFetcher()
    provider = module.ZimukuProvider(fetcher)

    filename, content = provider._try_download_candidates(
        ["https://zimuku.org/download/token/svr/d0"],
        referer="https://zimuku.org/dld/456.html",
    )

    assert filename == "example.srt"
    assert content.startswith(b"1\r\n")
    assert fetcher.direct_calls == [
        ("https://zimuku.org/download/token/svr/d0", "https://zimuku.org/dld/456.html")
    ]
    assert fetcher.interactive_calls == []


def test_zimuku_download_source_falls_back_to_interactive_navigation_for_html():
    module = load_online_module()
    fetcher = ZimukuInteractiveFallbackFetcher()
    provider = module.ZimukuProvider(fetcher)

    filename, content = provider._try_download_candidates(
        ["https://zimuku.org/download/token/svr/d0"],
        referer="https://zimuku.org/dld/456.html",
    )

    assert filename == "example.srt"
    assert content.startswith(b"1\r\n")
    assert fetcher.direct_calls == [
        ("https://zimuku.org/download/token/svr/d0", "https://zimuku.org/dld/456.html")
    ]
    assert fetcher.interactive_calls == [
        ("https://zimuku.org/download/token/svr/d0", "https://zimuku.org/dld/456.html", "")
    ]


def test_loaded_subtitle_page_without_extension_is_read_as_srt():
    module = load_online_module()

    class BodyLocator:
        def inner_text(self, timeout=0):
            return "1\n00:00:01,000 --> 00:00:02,000\nHi"

    class Page:
        url = "https://s.zimuku.org/download/encoded-token"

        def locator(self, selector):
            assert selector == "body"
            return BodyLocator()

    filename, content, final_url = module.OnlinePageClient._read_loaded_subtitle_page(
        Page(),
        "https://zimuku.org/download/token/svr/d0",
    )

    assert filename == "zimuku-subtitle.srt"
    assert b"00:00:01,000 --> 00:00:02,000" in content
    assert final_url == "https://s.zimuku.org/download/encoded-token"


def test_assrt_provider_parses_web_results_without_api_key():
    module = load_online_module()
    provider = module.AssrtProvider(AssrtFakeFetcher())
    targets = [{"season": 1, "episode": 2}]

    results = provider.search("Example Show S01E02", targets, "episode")

    assert len(results) == 1
    assert results[0].provider == "assrt"
    assert results[0].source == "射手网(伪)"
    assert results[0].downloadable is True
    assert results[0].page_url == "https://2.assrt.net/sub/123"


def test_assrt_provider_uses_official_api_when_key_exists():
    module = load_online_module()
    provider = module.AssrtProvider(AssrtFakeFetcher(), api_key="test-key")

    def fake_api_json(path, params):
        assert path == "/v1/sub/search"
        assert params["q"] == "Example Show S01E02"
        return {
            "status": 0,
            "sub": {
                "subs": [
                    {
                        "id": 602333,
                        "native_name": "Example Show S01E02 简体字幕",
                        "subtype": "Subrip(srt)",
                    }
                ]
            },
        }

    provider._api_json = fake_api_json

    results = provider.search("Example Show S01E02", [{"season": 1, "episode": 2}], "episode")

    assert len(results) == 1
    assert results[0].result_id == "602333"
    assert results[0].download_url == "assrt-api:602333"
    assert results[0].note == "通过 ASSRT 官方 API 搜索"


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


def test_site_cookie_headers_are_normalized_without_plain_status_leak():
    module = load_online_module()

    service = module.OnlineSubtitleSearchService(
        site_cookies={
            "subhd.tv": "foo=bar; session=abc",
            "zimuku.org": "zid=xyz",
        }
    )

    assert service.fetcher._configured_cookie_header("https://subhd.tv/search/demo") == "foo=bar; session=abc"
    assert service.fetcher._configured_cookie_header("https://www.zimuku.org/search?q=demo") == "zid=xyz"
    status = service.status()
    assert status["site_cookie_hosts"] == ["subhd.tv", "zimuku.org"]
    assert "foo=bar" not in str(status)


def test_cookie_headers_are_merged_by_name():
    module = load_online_module()

    merged = module._merge_cookie_headers("a=1; b=2", "b=3; c=4")

    assert merged == "a=1; b=3; c=4"


def test_manual_links_respect_empty_provider_selection():
    module = load_online_module()

    service = module.OnlineSubtitleSearchService()

    assert service.manual_links(["Example"], providers=[]) == []


def test_online_search_respects_empty_provider_selection():
    module = load_online_module()

    service = module.OnlineSubtitleSearchService()

    result = service.search(keywords=["Example"], providers=[], targets=[], scope="movie")

    assert result["results"] == []
    assert result["messages"][0]["provider"] == "providers"


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
