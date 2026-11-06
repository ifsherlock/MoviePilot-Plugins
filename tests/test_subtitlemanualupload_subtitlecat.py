from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from test_subtitlemanualupload_online import load_online_module


ROOT = "https://www.subtitlecat.com"
MOVIE = [{"title": "Example Film", "media_type": "movie", "year": 2024}]
SRT = b"1\n00:00:01,000 --> 00:00:02,000\nExample subtitle\n"


def provider_class():
    module = load_online_module()
    package = module.OnlineSubtitleResult.__module__.rsplit(".", 1)[0]
    return importlib.import_module(package + ".providers.subtitlecat").SubtitleCatProvider


def row(title="Example.Film.2024.BluRay", language="English", directory="123"):
    return f'<tr><td><a href="subs/{directory}/{title}.html">{title}</a> (translated from {language})</td><td>9 downloads</td><td>20 languages</td></tr>'


def table(*rows):
    return '<table class="sub-table other-class"><thead><tr><th>Title</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table>"


def detail(title="Example.Film.2024.BluRay", translated=""):
    return f'''<button onclick="translate_from_server_folder('af', '{title}-orig.srt', '/subs/123/')">Translate</button>{translated}'''


class Fetcher:
    use_proxy = False

    def __init__(self, search, details="", content=SRT, status=200):
        self.search = search
        self.details = details
        self.content = content
        self.status = status
        self.requests = []

    def get_text(self, url, *, referer=""):
        self.requests.append(url)
        return self.status, self.search if "index.php?" in url else self.details, url

    def get_bytes(self, url, *, referer=""):
        self.requests.append(url)
        return "test.srt", self.content, url


def test_original_language_is_not_assumed_english_and_translations_are_opt_in():
    fetcher = Fetcher(table(row(language="Portuguese"), row(language="Unknown", directory="124")))
    found = provider_class()(fetcher).search("Example Film", MOVIE, "movie")
    assert [item.language for item in found] == ["Portuguese", "Unknown"]
    assert all(item.translation_source == "original_upload" for item in found)
    assert len(fetcher.requests) == 1
    assert all(item.language_category == "other" for item in found)


def test_unknown_language_ignores_english_in_release_name():
    fetcher = Fetcher(table(row(title="Example.Film.2024.English", language="Unknown")))
    found = provider_class()(fetcher).search("Example Film", MOVIE, "movie")
    assert found[0].language == "Unknown"
    assert found[0].language_category == "other"


def test_explicit_wrong_movie_year_and_partial_title_are_rejected():
    fetcher = Fetcher(table(row(), row("Example.Film.1999"), row("Different.Film.2024")))
    found = provider_class()(fetcher).search("Example Film", MOVIE, "movie")
    assert [item.title for item in found] == ["Example.Film.2024.BluRay"]


def test_wrong_season_episode_and_unproven_season_pack_are_rejected():
    targets = [{"title": "Example Show", "media_type": "tv", "season": 2, "episode": 3}]
    fetcher = Fetcher(table(*(row(title) for title in [
        "Example.Show.S02E03", "Example.Show.S01E03", "Example.Show.S02E04", "Example.Show.S02", "Other.Show.S02E03",
    ])))
    found = provider_class()(fetcher).search("Example Show S02E03", targets, "episode")
    assert [(item.season, item.episode) for item in found] == [(2, 3)]


def test_translated_candidates_preserve_script_and_have_distinct_ids():
    links = '<a href="/subs/124/Example.Film.2024.BluRay-zh-CN.srt" id="download_zh-CN">Download</a><a id="download_zh-TW" href="/subs/125/Example.Film.2024.BluRay-zh-TW.srt">Download</a>'
    fetcher = Fetcher(table(row()), detail(translated=links))
    found = provider_class()(fetcher, include_translations=True).search("Example Film", MOVIE, "movie")
    assert [item.language for item in found] == ["English", "简体中文", "繁体中文"]
    assert len({item.result_id for item in found}) == 3
    assert all(item.translation_source == "site_translation" for item in found[1:])


def test_missing_translation_does_not_trigger_translation_buttons():
    fetcher = Fetcher(table(row()), detail())
    found = provider_class()(fetcher, include_translations=True).search("Example Film", MOVIE, "movie")
    assert len(found) == 1
    assert len(fetcher.requests) == 2
    assert all("translate" not in url for url in fetcher.requests)


@pytest.mark.parametrize("status,body,error", [
    (403, "blocked", "HTTP 403"),
    (200, "<html>challenge</html>", "页面结构"),
    (200, "", "空页面"),
])
def test_failed_search_is_not_reported_as_empty(status, body, error):
    with pytest.raises(ValueError, match=error):
        provider_class()(Fetcher(body, status=status)).search("Example Film", MOVIE, "movie")


def test_empty_table_is_a_legitimate_no_result():
    assert provider_class()(Fetcher(table())).search("Example Film", MOVIE, "movie") == []


def test_changed_table_cells_are_not_reported_as_no_results():
    changed = table('<tr><td>Example Film</td><td><a href="subs/123/movie.html">Details</a></td></tr>')
    with pytest.raises(ValueError, match="表格结构变化"):
        provider_class()(Fetcher(changed)).search("Example Film", MOVIE, "movie")


def test_original_download_requires_detail_filename_confirmation():
    fetcher = Fetcher(table(row()), detail())
    provider = provider_class()(fetcher)
    result = provider.search("Example Film", MOVIE, "movie")[0].to_dict()
    assert provider.download(result) == ("test.srt", SRT)
    assert fetcher.requests[-1] == ROOT + "/subs/123/Example.Film.2024.BluRay-orig.srt"
    fetcher.details = detail(title="Another.Movie")
    with pytest.raises(ValueError, match="未确认原字幕"):
        provider.download(result)


def test_translation_download_uses_actual_href_across_directory_and_respects_disable():
    links = '<a id="download_zh-TW" href="/subs/456/Example.Film.2024.BluRay-zh-TW.srt">Download</a>'
    fetcher = Fetcher(table(row()), detail(translated=links))
    provider = provider_class()(fetcher, include_translations=True)
    result = provider.search("Example Film", MOVIE, "movie")[-1].to_dict()
    assert provider.download(result) == ("test.srt", SRT)
    assert "/subs/456/" in fetcher.requests[-1]
    provider.include_translations = False
    with pytest.raises(ValueError, match="已停用"):
        provider.download(result)


def test_translation_link_cannot_silently_select_a_different_movie():
    links = '<a id="download_zh-CN" href="/subs/456/Other.Film-zh-CN.srt">Download</a>'
    fetcher = Fetcher(table(row()), detail(translated=links))
    with pytest.raises(ValueError, match="文件名与详情页不一致"):
        provider_class()(fetcher, include_translations=True).search("Example Film", MOVIE, "movie")


def test_original_download_handles_spaces_and_encoded_filenames():
    title = "Example Film (2024)"
    fetcher = Fetcher(table(row(title)), detail(title))
    provider = provider_class()(fetcher)
    result = provider.search("Example Film", MOVIE, "movie")[0].to_dict()
    provider.download(result)
    assert fetcher.requests[-1].endswith("Example%20Film%20%282024%29-orig.srt")


@pytest.mark.parametrize("url", [
    "https://outside.invalid/subs/123/Example.Film.html",
    ROOT + "/subs/123/../../Example.Film.html",
    ROOT + "/subs/123/Example.Film.html?redirect=anything",
    ROOT + "/subs/123/%2e%2e%2fsecret.html",
    "file:///subs/123/Example.Film.html",
])
def test_untrusted_download_page_urls_are_rejected_before_request(url):
    fetcher = Fetcher(table())
    with pytest.raises(ValueError, match="不受支持"):
        provider_class()(fetcher).download({"page_url": url, "download_url": "subtitlecat-original:" + url})
    assert fetcher.requests == []


def test_download_rejects_html_even_when_named_srt():
    fetcher = Fetcher(table(row()), detail(), content=b"<!DOCTYPE html><html><title>Blocked</title></html>")
    provider = provider_class()(fetcher)
    result = provider.search("Example Film", MOVIE, "movie")[0].to_dict()
    with pytest.raises(ValueError):
        provider.download(result)


def test_search_limits_detail_request_budget_and_keyword_budget():
    fetcher = Fetcher(table(*(row(directory=str(i)) for i in range(25))), detail())
    found = provider_class()(fetcher, include_translations=True).search("Example Film", MOVIE, "movie")
    assert len(found) == 20
    assert len(fetcher.requests) == 5
    empty = Fetcher(table())
    provider_class()(empty).search_all([f"Missing Film {i}" for i in range(10)], MOVIE, "movie")
    assert len(empty.requests) == 3


def test_v2_v3_subtitlecat_modules_are_identical():
    root = Path(__file__).resolve().parents[1]
    relative = "subtitlemanualupload/online_subtitles/providers/subtitlecat.py"
    assert (root / "plugins.v2" / relative).read_bytes() == (root / "plugins.v3" / relative).read_bytes()


def test_search_deadline_caps_network_timeout_and_is_restored(monkeypatch):
    cls = provider_class()
    module = importlib.import_module(cls.__module__)
    now = [0]
    monkeypatch.setattr(module.time, "monotonic", lambda: now[0])

    class SlowFetcher(Fetcher):
        timeout = 10

        def get_text(self, url, *, referer=""):
            assert self.timeout <= 10
            now[0] += 11
            return super().get_text(url, referer=referer)

    fetcher = SlowFetcher(table())
    with pytest.raises(ValueError, match="时间预算"):
        cls(fetcher).search_all(["Missing one", "Missing two", "Missing three"], MOVIE, "movie")
    assert len(fetcher.requests) == 2
    assert fetcher.timeout == 10
