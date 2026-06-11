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
    use_proxy = False

    def get_text(self, url, *, referer=""):
        raise AssertionError("API provider should not use page simulation")

    def get_bytes(self, url, *, referer=""):
        return "example.srt", b"1\n00:00:01,000 --> 00:00:02,000\nHi", url

    def close(self):
        return None


class FakeDirectDownloader:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def get_bytes(self, url, *, referer=""):
        return "example.srt", b"1\n00:00:01,000 --> 00:00:02,000\nHi", url


class FakeWebFetcher:
    use_proxy = False

    def __init__(self, pages=None):
        self.pages = pages or {}
        self.requested = []

    def get_text(self, url, *, referer=""):
        self.requested.append(url)
        for marker, body in self.pages.items():
            if marker in url:
                return 200, body, url
        return 404, "", url

    def get_bytes(self, url, *, referer=""):
        return "subtitle.zip", b"PK\x03\x04" + b"x" * 2048, url

    def post_json(self, url, payload, *, referer=""):
        return {"success": True, "url": "/download/subtitle.zip"}

    def close(self):
        return None


def test_build_search_keywords_prefers_season_package():
    module = load_online_module()
    media = {"media_type": "tv", "title": "Example Show", "year": "2025"}
    targets = [
        {"media_type": "tv", "title": "Example Show", "season": 1, "episode": 1, "basename": "Example.Show.S01E01"},
        {"media_type": "tv", "title": "Example Show", "season": 1, "episode": 2, "basename": "Example.Show.S01E02"},
    ]

    keywords = module.build_search_keywords(media, targets, "season")

    assert keywords[:1] == ["Example Show S01"]
    assert all("第1季" not in keyword for keyword in keywords)


def test_build_search_keywords_episode_ignores_episode_title_suffix():
    module = load_online_module()
    media = {"media_type": "tv", "title": "如积雪般的永寂", "year": "2024"}
    targets = [
        {
            "media_type": "tv",
            "title": "如积雪般的永寂",
            "season": 1,
            "episode": 1,
            "basename": "如积雪般的永寂 - S01E01 - 第 1 集",
            "filename": "如积雪般的永寂 - S01E01 - 第 1 集.mkv",
        },
    ]

    keywords = module.build_search_keywords(media, targets, "episode")

    assert keywords[0] == "如积雪般的永寂 S01E01"
    assert all("第 1 集" not in keyword and "第1集" not in keyword for keyword in keywords)


def test_manual_providers_keep_subhd_zimuku_links_only():
    module = load_online_module()

    service = module.OnlineSubtitleSearchService()
    links = service.manual_links(["Ghost Rider 2007"], providers=["subhd", "zimuku"])
    status = {item["id"]: item for item in service.status()["manual_providers"]}

    assert [item["provider"] for item in links] == ["subhd", "zimuku"]
    assert links[0]["links"][0]["url"] == "https://subhd.tv/search/Ghost%20Rider%202007"
    assert links[1]["links"][0]["url"] == "https://zmk.pw/search?q=Ghost%20Rider%202007&chost=zmk.pw"
    assert status["subhd"]["manual_only"] is False
    assert status["zimuku"]["manual_only"] is False


def test_opensubtitles_search_all_prefers_tmdb_then_title_then_imdb():
    module = load_online_module()
    provider = module.OpenSubtitlesProvider(FakeFetcher(), api_key="test-key")
    calls = []

    def fake_api_json(path, params, *, method="GET"):
        calls.append(dict(params))
        assert path == "/subtitles"
        assert params["languages"] == "zh-cn,zh-tw,ze,en,ja,ko"
        if "query" in params:
            return {
                "data": [
                    {
                        "attributes": {
                            "language": "en",
                            "release": "Example.Show.S01E02.1080p.WEB-DL",
                            "files": [{"file_id": 987, "file_name": "Example.Show.S01E02.srt"}],
                        }
                    }
                ]
            }
        return {"data": []}

    provider._api_json = fake_api_json

    results = provider.search_all(
        ["Example Show S01E02"],
        [
            {
                "media_type": "tv",
                "title": "Example Show",
                "tmdb_id": 12345,
                "imdb_id": "tt7654321",
                "season": 1,
                "episode": 2,
            }
        ],
        "episode",
    )

    assert ["tmdb_id" if "tmdb_id" in item else "query" if "query" in item else "imdb_id" for item in calls] == ["tmdb_id", "query"]
    assert calls[0]["tmdb_id"] == "12345"
    assert calls[1]["query"] == "Example Show S01E02"
    assert len(results) == 1
    assert "英文标题查询" in results[0].query_plan


def test_opensubtitles_search_all_uses_imdb_last():
    module = load_online_module()
    provider = module.OpenSubtitlesProvider(FakeFetcher(), api_key="test-key")
    calls = []

    def fake_api_json(path, params, *, method="GET"):
        calls.append(dict(params))
        if "imdb_id" in params:
            return {
                "data": [
                    {
                        "attributes": {
                            "language": "zh",
                            "release": "Example.Movie.2024.zh",
                            "feature_details": {"year": 2024, "title": "Example Movie", "imdb_id": 7654321},
                            "files": [{"file_id": 55, "file_name": "Example.Movie.2024.zh.srt"}],
                        }
                    }
                ]
            }
        return {"data": []}

    provider._api_json = fake_api_json

    results = provider.search_all(
        ["Example Movie 2024"],
        [{"media_type": "movie", "title": "Example Movie", "year": "2024", "imdb_id": "tt7654321"}],
        "movie",
    )

    assert ["tmdb_id" if "tmdb_id" in item else "query" if "query" in item else "imdb_id" for item in calls] == ["query", "imdb_id"]
    assert calls[-1]["imdb_id"] == "7654321"
    assert [item.result_id for item in results] == ["55"]


def test_subhd_prefers_douban_id_and_parses_subtitle_rows():
    module = load_online_module()
    html = """
    <div class="row">
      <a class="link-dark" href="/a/bqsyNZ">Example Show S01E02 简体中文 ASS</a>
      <span class="fw-bold">简体</span><span class="text-secondary">ASS</span>
    </div>
    """
    fetcher = FakeWebFetcher({"/d/1292052": html})
    provider = module.SubHDProvider(fetcher)

    results = provider.search_all(
        ["Example Show S01E02"],
        [{"media_type": "tv", "title": "Example Show", "douban_id": "1292052", "season": 1, "episode": 2}],
        "episode",
    )

    assert fetcher.requested[0] == "https://subhd.tv/d/1292052"
    assert len(results) == 1
    assert results[0].provider == "subhd"
    assert results[0].result_id == "bqsyNZ"
    assert results[0].language_category == "chinese"
    assert results[0].download_url.startswith("subhd-page:")


def test_subhd_download_uses_api_html_url_fallback():
    module = load_online_module()

    class SubHDFetcher(FakeWebFetcher):
        def get_text(self, url, *, referer=""):
            self.requested.append(url)
            if "/a/abc" in url:
                return 200, '<a href="/down/123">下载字幕</a>', url
            if "/down/123" in url:
                return 200, "<html></html>", url
            return 404, "", url

        def post_json(self, url, payload, *, referer=""):
            return {"success": True, "pass": True, "url": '<a href="/download/from-api.zip">download</a>'}

        def get_bytes(self, url, *, referer=""):
            self.requested.append(url)
            assert url == "https://subhd.tv/download/from-api.zip"
            return "from-api.zip", b"PK\x03\x04" + b"x" * 2048, url

    provider = module.SubHDProvider(SubHDFetcher())

    filename, content = provider.download({"page_url": "https://subhd.tv/a/abc"})

    assert filename == "from-api.zip"
    assert content.startswith(b"PK\x03\x04")


def test_subhd_download_falls_back_to_down_page_href_when_api_url_empty():
    module = load_online_module()

    class SubHDFetcher(FakeWebFetcher):
        def get_text(self, url, *, referer=""):
            self.requested.append(url)
            if "/a/abc" in url:
                return 200, '<a href="/down/123">下载字幕</a>', url
            if "/down/123" in url:
                return 200, '<a href="/download/from-page.zip">备用下载</a>', url
            return 404, "", url

        def post_json(self, url, payload, *, referer=""):
            return {"success": True, "pass": True, "url": "", "msg": "ok"}

        def get_bytes(self, url, *, referer=""):
            self.requested.append(url)
            assert url == "https://subhd.tv/download/from-page.zip"
            return "from-page.zip", b"PK\x03\x04" + b"x" * 2048, url

    provider = module.SubHDProvider(SubHDFetcher())

    filename, content = provider.download({"page_url": "https://subhd.tv/a/abc"})

    assert filename == "from-page.zip"
    assert content.startswith(b"PK\x03\x04")


def test_zimuku_searches_candidates_and_filters_episode():
    module = load_online_module()
    search_html = """
    <div class="item"><div class="title"><p class="tt">
      <a href="/subs/456.html">Example Show</a>
    </p></div></div>
    """
    subs_html = """
    <table><tbody>
      <tr><td><a href="/detail/1.html">Example Show S01E01 简体中文</a></td></tr>
      <tr><td><img title="简体中文字幕"><a href="/detail/2.html">Example Show S01E02 ASS</a></td></tr>
    </tbody></table>
    """
    fetcher = FakeWebFetcher({"/search": search_html, "/subs/456.html": subs_html})
    provider = module.ZimukuProvider(fetcher)

    results = provider.search(
        "Example Show S01E02",
        [{"media_type": "tv", "title": "Example Show", "season": 1, "episode": 2}],
        "episode",
    )

    assert [item.result_id for item in results] == ["2"]
    assert "chost=zmk.pw" in fetcher.requested[0]
    assert results[0].provider == "zimuku"
    assert results[0].language_category == "chinese"
    assert results[0].download_url.startswith("zimuku-page:")


def test_zimuku_search_falls_back_when_query_path_404():
    module = load_online_module()
    search_html = """
    <div class="item"><div class="title"><p class="tt">
      <a href="/subs/456.html">Example Show</a>
    </p></div></div>
    """
    subs_html = """
    <table><tbody>
      <tr><td><a href="/detail/2.html">Example Show S01E02 简体中文 ASS</a></td></tr>
    </tbody></table>
    """

    class FallbackFetcher(FakeWebFetcher):
        def get_text(self, url, *, referer=""):
            self.requested.append(url)
            if "/search?q=" in url:
                return 404, "", url
            if "/search/" in url:
                return 200, search_html, url
            if "/subs/456.html" in url:
                return 200, subs_html, url
            return 404, "", url

    fetcher = FallbackFetcher()
    provider = module.ZimukuProvider(fetcher)

    results = provider.search(
        "Example Show S01E02",
        [{"media_type": "tv", "title": "Example Show", "season": 1, "episode": 2}],
        "episode",
    )

    assert [item.result_id for item in results] == ["2"]
    assert any("/search?q=" in url for url in fetcher.requested)
    assert any("/search/" in url and "/search?q=" not in url for url in fetcher.requested)


def test_subhd_download_accepts_nested_api_download_url():
    module = load_online_module()
    page_html = '<a class="down" href="/down/123">下载</a>'

    class NestedSubHDFetcher(FakeWebFetcher):
        def post_json(self, url, payload, *, referer=""):
            assert payload["sid"] == "123"
            return {"success": True, "data": {"download": {"file_url": "/download/subtitle.zip"}}}

    fetcher = NestedSubHDFetcher({"/a/abc": page_html, "/down/123": "download page"})
    provider = module.SubHDProvider(fetcher)

    filename, content = provider.download(
        {
            "provider": "subhd",
            "result_id": "abc",
            "page_url": "https://subhd.tv/a/abc",
            "download_url": "subhd-page:https://subhd.tv/a/abc",
            "title": "Example",
        }
    )

    assert filename == "subtitle.zip"
    assert content.startswith(b"PK\x03\x04")
    assert any("/down/123" in url for url in fetcher.requested)


def test_assrt_provider_requires_api_key_for_auto_search():
    module = load_online_module()
    provider = module.AssrtProvider(FakeFetcher())

    try:
        provider.search("Example Show S01E02", [{"season": 1, "episode": 2}], "episode")
    except ValueError as exc:
        assert "未配置 API Key" in str(exc)
    else:
        raise AssertionError("ASSRT auto search should require API Key")


def test_assrt_provider_uses_official_api_when_key_exists():
    module = load_online_module()
    provider = module.AssrtProvider(FakeFetcher(), api_key="test-key")

    def fake_api_json(path, params):
        assert path == "/v1/sub/search"
        assert params["q"] == "Example Show S01E02"
        return {
            "status": 0,
            "sub": {
                "subs": [
                    {
                        "id": 602333,
                        "native_name": "Example Show S01E02 English subtitles",
                        "subtype": "Subrip(srt)",
                        "lang": "eng",
                    }
                ]
            },
        }

    provider._api_json = fake_api_json

    results = provider.search("Example Show S01E02", [{"season": 1, "episode": 2}], "episode")

    assert len(results) == 1
    assert results[0].result_id == "602333"
    assert results[0].page_url == "https://2.assrt.net/xml/sub/602/602333.xml"
    assert provider._detail_url("652400") == "https://2.assrt.net/xml/sub/652/652400.xml"
    assert results[0].download_url == "assrt-api:602333"
    assert results[0].language == "英文"
    assert results[0].note == "通过 ASSRT 官方 API 搜索"


def test_assrt_provider_discards_mojibake_results():
    module = load_online_module()
    provider = module.AssrtProvider(FakeFetcher(), api_key="test-key")

    def fake_api_json(path, params):
        return {
            "status": 0,
            "sub": {
                "subs": [
                    {
                        "id": 652400,
                        "native_name": "é­”æˆ’III/æŒ‡çŽ¯çŽ‹III :çŽ‹è€…å½’æ?¥",
                        "subtype": "Subrip(srt)",
                        "lang": "chi",
                    },
                    {
                        "id": 652401,
                        "native_name": "指环王III：王者归来 中文字幕",
                        "subtype": "Subrip(srt)",
                        "lang": "chi",
                    },
                ]
            },
        }

    provider._api_json = fake_api_json

    results = provider.search("指环王3", [{"title": "指环王3", "year": 2003}], "movie")

    assert [item.result_id for item in results] == ["652401"]
    assert results[0].title == "指环王III：王者归来 中文字幕"


def test_opensubtitles_search_returns_multilingual_api_results():
    module = load_online_module()
    provider = module.OpenSubtitlesProvider(FakeFetcher(), api_key="test-key")

    def fake_api_json(path, params, *, method="GET"):
        assert method == "GET"
        assert path == "/subtitles"
        assert params["languages"] == "zh-cn,zh-tw,ze,en,ja,ko"
        return {
            "data": [
                {
                    "attributes": {
                        "language": "en",
                        "url": "https://www.opensubtitles.com/en/subtitles/123",
                        "release": "Example.Show.S01E02.1080p.WEB-DL",
                        "files": [{"file_id": 987, "file_name": "Example.Show.S01E02.srt"}],
                    }
                },
                {
                    "attributes": {
                        "language": "zh",
                        "release": "Example.Show.S01E02.zh",
                        "files": [{"file_id": 988, "file_name": "Example.Show.S01E02.zh.srt"}],
                    }
                },
            ]
        }

    provider._api_json = fake_api_json

    results = provider.search(
        "Example Show S01E02",
        [{"media_type": "tv", "title": "Example Show", "season": 1, "episode": 2}],
        "episode",
    )

    assert len(results) == 2
    assert results[0].provider == "opensubtitles"
    assert results[0].download_url == "opensubtitles-api:987"
    assert results[0].language == "英文"
    assert results[0].language_category == "english"
    assert results[1].download_url == "opensubtitles-api:988"
    assert results[1].language == "简体中文"
    assert results[1].language_category == "chinese"
    assert results[1].note == "通过 OpenSubtitles API 搜索简体中文字幕"


def test_opensubtitles_manual_url_uses_search_all_path():
    module = load_online_module()
    provider = module.OpenSubtitlesProvider(FakeFetcher(), api_key="test-key")

    url = provider.manual_url("指环王")

    assert "search-all/q-" in url
    assert "moviename-" not in url
    assert "%E6%8C%87%E7%8E%AF%E7%8E%8B" in url


def test_opensubtitles_filters_wrong_title_and_year():
    module = load_online_module()
    provider = module.OpenSubtitlesProvider(FakeFetcher(), api_key="test-key")

    def fake_api_json(path, params, *, method="GET"):
        return {
            "data": [
                {
                    "attributes": {
                        "language": "zh",
                        "release": "千王之王.2000.1080p",
                        "upload_date": "2001-01-01T00:00:00Z",
                        "files": [{"file_id": 1, "file_name": "千王之王.2000.srt"}],
                    }
                },
                {
                    "attributes": {
                        "language": "zh",
                        "release": "指环王.2003.1080p",
                        "upload_date": "2003-12-20T00:00:00Z",
                        "files": [{"file_id": 2, "file_name": "指环王.2003.srt"}],
                    }
                },
            ]
        }

    provider._api_json = fake_api_json

    results = provider.search(
        "指环王 2003",
        [{"title": "指环王", "filename": "指环王 (2003) - 1080p.mkv", "year": "2003"}],
        "movie",
    )

    assert len(results) == 1
    assert results[0].result_id == "2"
    assert results[0].match_year == 2003


def test_opensubtitles_requires_series_identity_before_episode_score():
    module = load_online_module()
    provider = module.OpenSubtitlesProvider(FakeFetcher(), api_key="test-key")

    def fake_api_json(path, params, *, method="GET"):
        return {
            "data": [
                {
                    "attributes": {
                        "language": "zh",
                        "release": "Youth.Sherlock.S01E07.zh",
                        "files": [{"file_id": 1, "file_name": "Youth.Sherlock.S01E07.zh.srt"}],
                    }
                },
                {
                    "attributes": {
                        "language": "ja",
                        "release": "Haibara-kun.no.Tsuyokute.New.Game.S01E07.zh",
                        "files": [{"file_id": 2, "file_name": "Haibara-kun.no.Tsuyokute.New.Game.S01E07.srt"}],
                    }
                },
            ]
        }

    provider._api_json = fake_api_json

    results = provider.search(
        "灰原同学的第二轮青春游戏 S01E07",
        [
            {
                "media_type": "tv",
                "title": "灰原同学的第二轮青春游戏",
                "en_title": "Haibara-kun's New Game Plus",
                "original_title": "灰原くんの強くて青春ニューゲーム",
                "season": 1,
                "episode": 7,
            }
        ],
        "episode",
    )

    assert len(results) == 1
    assert results[0].result_id == "2"
    assert results[0].identity_status == "strong"
    assert "季集一致" in results[0].match_detail


def test_opensubtitles_rejects_youth_sherlock_for_haibara_sample():
    module = load_online_module()
    provider = module.OpenSubtitlesProvider(FakeFetcher(), api_key="test-key")

    def fake_api_json(path, params, *, method="GET"):
        return {
            "data": [
                {
                    "attributes": {
                        "language": "zh",
                        "release": "Youth.Sherlock.S01E07.zh",
                        "files": [{"file_id": 1, "file_name": "Youth.Sherlock.S01E07.zh.srt"}],
                    }
                }
            ]
        }

    provider._api_json = fake_api_json

    results = provider.search(
        "灰原同学的第二轮青春游戏 S01E07",
        [
            {
                "media_type": "tv",
                "title": "灰原同学的第二轮青春游戏",
                "en_title": "Haibara-kun's New Game Plus",
                "original_title": "灰原くんの強くて青春ニューゲーム",
                "season": 1,
                "episode": 7,
            }
        ],
        "episode",
    )

    assert results == []


def test_opensubtitles_allows_tv_year_conflict_with_series_identity_and_episode():
    module = load_online_module()
    provider = module.OpenSubtitlesProvider(FakeFetcher(), api_key="test-key")

    def fake_api_json(path, params, *, method="GET"):
        return {
            "data": [
                {
                    "attributes": {
                        "language": "zh",
                        "release": "Haibara-kun.no.Tsuyokute.New.Game.S01E07.zh",
                        "feature_details": {
                            "feature_type": "Tvshow",
                            "year": 2024,
                            "title": "Haibara-kun no Tsuyokute New Game",
                        },
                        "upload_date": "2024-12-20T00:00:00Z",
                        "files": [
                            {
                                "file_id": 7,
                                "file_name": "Haibara-kun.no.Tsuyokute.New.Game.S01E07.2024.zh.srt",
                            }
                        ],
                    }
                }
            ]
        }

    provider._api_json = fake_api_json

    results = provider.search(
        "Haibara-kun no Tsuyokute New Game S01E07",
        [
            {
                "media_type": "tv",
                "title": "Haibara-kun no Tsuyokute New Game",
                "en_title": "Haibara-kun no Tsuyokute New Game",
                "season": 1,
                "episode": 7,
                "year": "2025",
            }
        ],
        "episode",
    )

    assert len(results) == 1
    assert results[0].result_id == "7"
    assert results[0].identity_status == "strong"


def test_opensubtitles_filters_filename_year_and_upload_year_conflicts():
    module = load_online_module()
    provider = module.OpenSubtitlesProvider(FakeFetcher(), api_key="test-key")

    def fake_api_json(path, params, *, method="GET"):
        return {
            "data": [
                {
                    "attributes": {
                        "language": "en",
                        "release": "Spider-Man.Into.the.Spider-Verse.2018.1080p",
                        "upload_date": "2018-12-20T00:00:00Z",
                        "files": [{"file_id": 1, "file_name": "Spider-Man.Into.the.Spider-Verse.2017.srt"}],
                    }
                },
                {
                    "attributes": {
                        "language": "en",
                        "release": "Spider-Man.Into.the.Spider-Verse.2018.1080p",
                        "upload_date": "2017-12-20T00:00:00Z",
                        "files": [{"file_id": 2, "file_name": "Spider-Man.Into.the.Spider-Verse.2018.srt"}],
                    }
                },
                {
                    "attributes": {
                        "language": "en",
                        "release": "Spider-Man.Into.the.Spider-Verse.2018.1080p",
                        "upload_date": "2018-12-20T00:00:00Z",
                        "files": [{"file_id": 3, "file_name": "Spider-Man.Into.the.Spider-Verse.2018.srt"}],
                    }
                },
            ]
        }

    provider._api_json = fake_api_json

    results = provider.search(
        "Spider-Man Into the Spider-Verse 2018",
        [
            {
                "media_type": "movie",
                "title": "蜘蛛侠：平行宇宙",
                "en_title": "Spider-Man: Into the Spider-Verse",
                "filename": "蜘蛛侠：平行宇宙 (2018) - 1080p.mkv",
                "year": "2018",
            }
        ],
        "movie",
    )

    assert [item.result_id for item in results] == ["3"]


def test_build_search_keywords_uses_region_aware_tmdb_titles():
    module = load_online_module()
    media = {
        "media_type": "tv",
        "title": "九龙大众浪漫",
        "original_title": "九龍ジェネリックロマンス",
        "en_title": "Kowloon Generic Romance",
        "original_language": "ja",
        "origin_country": ["JP"],
        "year": "2025",
    }
    targets = [
        {
            **media,
            "season": 1,
            "episode": 4,
            "basename": "九龙大众浪漫 - S01E04 - 第 4 集",
        }
    ]

    keywords = module.build_search_keywords(media, targets, "episode")

    assert keywords[0] == "Kowloon Generic Romance S01E04"
    assert "九龍ジェネリックロマンス S01E04" in keywords


def test_build_search_keywords_filters_language_name_aliases():
    module = load_online_module()
    movie_media = {
        "media_type": "movie",
        "title": "勇敢的心",
        "year": "1995",
        "en_title": "English",
        "original_title": "Braveheart",
        "original_language": "en",
        "origin_country": ["US"],
        "translations": [
            {
                "name": "English",
                "english_name": "English",
                "data": {"title": "Braveheart"},
            }
        ],
    }

    movie_keywords = module.build_search_keywords(movie_media, [movie_media], "movie")

    assert "English 1995" not in movie_keywords
    assert movie_keywords[0] == "Braveheart 1995"

    tv_media = {
        "media_type": "tv",
        "title": "企鹅人",
        "en_title": "English",
        "original_title": "The Penguin",
        "original_language": "en",
        "origin_country": ["US"],
        "year": "2024",
    }
    tv_target = {**tv_media, "season": 1, "episode": 8, "basename": "企鹅人 - S01E08 - 第 8 集"}

    tv_keywords = module.build_search_keywords(tv_media, [tv_target], "episode")

    assert "English S01E08" not in tv_keywords
    assert tv_keywords[0] == "The Penguin S01E08"


def test_build_search_keywords_filters_plot_summary_aliases():
    module = load_online_module()
    media = {
        "media_type": "movie",
        "title": "熔炉",
        "year": "2011",
        "original_title": "도가니",
        "original_language": "ko",
        "origin_country": ["KR"],
        "translations": [
            {
                "name": "Chinese",
                "data": {
                    "title": "本片取材于2005年光州一所聋哑障碍人学校的真实事件，改编自韩国作家孔枝泳的同名小说。来自首尔的哑语美术老师来到雾津。",
                },
            }
        ],
    }

    keywords = module.build_search_keywords(media, [media], "movie")

    assert all("真实事件" not in item for item in keywords)
    assert keywords[0] == "도가니 2011"


def test_build_search_keywords_filters_native_language_name_aliases():
    module = load_online_module()
    media = {
        "media_type": "movie",
        "title": "恶灵骑士",
        "year": "2007",
        "en_title": "Ghost Rider",
        "original_title": "Ghost Rider",
        "original_language": "en",
        "origin_country": ["US"],
        "translations": [
            {"iso_639_1": "fr", "name": "French", "english_name": "French", "data": {"title": "Français"}},
            {"iso_639_1": "de", "name": "German", "english_name": "German", "data": {"title": "Deutsch"}},
            {"iso_639_1": "nl", "name": "Dutch", "english_name": "Dutch", "data": {"title": "Nederlands"}},
            {"iso_639_1": "tr", "name": "Turkish", "english_name": "Turkish", "data": {"title": "Hayalet Sürücü"}},
            {"iso_639_1": "fi", "name": "suomi", "english_name": "Finnish", "data": {"title": ""}},
        ],
    }

    keywords = module.build_search_keywords(media, [media], "movie")

    assert keywords[0] == "Ghost Rider 2007"
    assert all(
        item not in keywords
        for item in [
            "Français 2007",
            "Deutsch 2007",
            "Nederlands 2007",
            "Türkçe 2007",
            "Turkish 2007",
            "Finnish 2007",
            "suomi 2007",
        ]
    )
    assert "Hayalet Sürücü 2007" in keywords


def test_build_search_keywords_prioritizes_explicit_english_title_over_latin_translations():
    module = load_online_module()
    media = {
        "media_type": "movie",
        "title": "指环王3：王者无敌",
        "year": "2003",
        "en_title": "The Lord of the Rings: The Return of the King",
        "original_title": "The Lord of the Rings: The Return of the King",
        "original_language": "en",
        "origin_country": ["US"],
        "tmdb_aliases": [
            "Der Herr der Ringe - Die Rueckkehr des Koenigs",
            "Pán prstenu: Návrat krále",
            "The Lord of the Rings: The Return of the King",
        ],
    }

    keywords = module.build_search_keywords(media, [media], "movie")

    assert keywords[0] == "The Lord of the Rings: The Return of the King 2003"
    assert keywords.index("The Lord of the Rings: The Return of the King 2003") < keywords.index(
        "Der Herr der Ringe - Die Rueckkehr des Koenigs 2003"
    )


def test_opensubtitles_rejects_generic_english_query_match():
    module = load_online_module()
    provider = module.OpenSubtitlesProvider(FakeFetcher(), api_key="test-key")

    def fake_api_json(path, params, *, method="GET"):
        return {
            "data": [
                {
                    "attributes": {
                        "language": "en",
                        "release": "I Dont Speak English.1995.English",
                        "feature_details": {
                            "feature_type": "Movie",
                            "year": 1995,
                            "title": "I Dont Speak English",
                            "tmdb_id": 12345,
                        },
                        "upload_date": "1996-01-01T00:00:00Z",
                        "files": [{"file_id": 1, "file_name": "I Dont Speak English.1995.English.srt"}],
                    }
                }
            ]
        }

    provider._api_json = fake_api_json

    results = provider.search(
        "English 1995",
        [
            {
                "media_type": "movie",
                "title": "勇敢的心",
                "en_title": "English",
                "original_title": "Braveheart",
                "filename": "勇敢的心 (1995) - 480p.strm",
                "year": "1995",
                "tmdb_id": 197,
            }
        ],
        "movie",
    )

    assert results == []


def test_query_plan_records_region_and_query_source():
    module = load_online_module()

    plan = module._query_plan_for_keyword(
        "九龍ジェネリックロマンス S01E04",
        [
            {
                "media_type": "tv",
                "title": "九龙大众浪漫",
                "original_title": "九龍ジェネリックロマンス",
                "en_title": "Kowloon Generic Romance",
                "original_language": "ja",
                "origin_country": ["JP"],
                "season": 1,
                "episode": 4,
            }
        ],
    )

    assert plan["region_bucket"] == "japanese"
    assert plan["query_source"] == "原名查询"


def test_opensubtitles_download_uses_download_api_link():
    module = load_online_module()
    provider = module.OpenSubtitlesProvider(FakeFetcher(), api_key="test-key", username="demo", password="secret")
    provider.download.__globals__["OnlineDirectDownloader"] = FakeDirectDownloader
    provider._session_token = "jwt-token"

    def fake_api_json(path, params, *, method="GET", token="", allow_without_token=False):
        assert path == "/download"
        assert method == "POST"
        assert params["file_id"] == "987"
        assert token == "jwt-token"
        return {"link": "https://download.example/subtitle.srt", "file_name": "subtitle.srt"}

    provider._api_json = fake_api_json

    filename, content = provider.download({"download_url": "opensubtitles-api:987"})

    assert filename == "subtitle.srt"
    assert b"00:00:01,000" in content


def test_opensubtitles_download_can_login_for_token():
    module = load_online_module()
    provider = module.OpenSubtitlesProvider(
        FakeFetcher(),
        api_key="test-key",
        username="demo",
        password="secret",
    )
    provider.download.__globals__["OnlineDirectDownloader"] = FakeDirectDownloader
    calls = []

    def fake_api_json(path, params, *, method="GET", token="", allow_without_token=False):
        calls.append((path, params, method, token, allow_without_token))
        if path == "/login":
            assert method == "POST"
            assert allow_without_token is True
            assert params == {"username": "demo", "password": "secret"}
            return {"token": "login-token"}
        if path == "/download":
            assert method == "POST"
            assert token == "login-token"
            return {"link": "https://download.example/subtitle.srt", "file_name": "subtitle.srt"}
        raise AssertionError(path)

    provider._api_json = fake_api_json

    filename, _ = provider.download({"result_id": "987"})

    assert filename == "subtitle.srt"
    assert calls[0][0] == "/login"
    assert calls[1][0] == "/download"


def test_provider_roots_are_normalized_with_fallbacks():
    module = load_online_module()

    roots = module.normalize_provider_roots(
        {
            "subhd": "https://sub.example/",
            "zimuku": "ftp://invalid.example",
            "assrt": "",
            "opensubtitles": "https://www.opensubtitles.org/",
        }
    )

    assert roots["subhd"] == "https://sub.example"
    assert roots["zimuku"] == "https://zmk.pw"
    assert roots["assrt"] == "https://2.assrt.net"
    assert roots["opensubtitles"] == "https://www.opensubtitles.org"


def test_online_service_defaults_to_no_proxy():
    module = load_online_module()

    service = module.OnlineSubtitleSearchService()

    assert service.fetcher.use_proxy is False
    assert service.status()["engine_name"] == "API 自动搜索"


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


def test_online_service_orders_assrt_before_opensubtitles():
    module = load_online_module()

    class StaticProvider(module.BaseSubtitleProvider):
        def __init__(self, provider_id, score, language_category, identity_status=""):
            self.provider_id = provider_id
            self.display_name = provider_id
            super().__init__(FakeFetcher())
            self.score = score
            self.language_category = language_category
            self.identity_status = identity_status

        def manual_url(self, keyword):
            return f"https://example.invalid/{self.provider_id}/{keyword}"

        def search(self, keyword, targets, scope):
            return [
                module.OnlineSubtitleResult(
                    provider=self.provider_id,
                    result_id=self.provider_id,
                    title=self.provider_id,
                    page_url=self.manual_url(keyword),
                    score=self.score,
                    language_category=self.language_category,
                    identity_status=self.identity_status,
                )
            ]

    service = module.OnlineSubtitleSearchService()
    service.providers = {
        "assrt": StaticProvider("assrt", 8, "english"),
        "opensubtitles": StaticProvider("opensubtitles", 53, "chinese", "weak"),
    }
    service.fetcher = types.SimpleNamespace(close=lambda: None)

    result = service.search(keywords=["Example"], providers=["opensubtitles", "assrt"], targets=[], scope="movie")

    assert [item["provider"] for item in result["results"]] == ["assrt", "opensubtitles"]


def test_provider_network_errors_are_compacted():
    module = load_online_module()

    class FailingProvider(module.BaseSubtitleProvider):
        provider_id = "assrt"
        display_name = "射手网(伪)"

        def manual_url(self, keyword):
            return f"https://2.assrt.net/sub/?searchword={keyword}"

        def search(self, keyword, targets, scope):
            raise ValueError("<urlopen error [Errno 104] Connection reset by peer>")

    service = module.OnlineSubtitleSearchService(use_proxy=False)
    service.providers = {"assrt": FailingProvider(FakeFetcher())}
    service.fetcher = types.SimpleNamespace(close=lambda: None)

    result = service.search(
        keywords=["Example S01", "Example 第1季", "Example.S01E01"],
        providers=["assrt"],
        targets=[],
        scope="season",
    )

    assert result["results"] == []
    assert len(result["messages"]) == 1
    assert result["messages"][0]["provider"] == "assrt"
    assert "<urlopen" not in result["messages"][0]["message"]
    assert "已尝试 3 个关键词" in result["messages"][0]["message"]
