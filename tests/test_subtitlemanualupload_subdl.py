from __future__ import annotations

import importlib
import io
import json
import types
import urllib.error
from urllib.parse import parse_qs, urlparse

import pytest

from test_subtitlemanualupload_online import FakeFetcher, load_online_module


def provider(api_key="private-test-key"):
    module = load_online_module()
    package = module.OnlineSubtitleResult.__module__.rsplit(".", 1)[0]
    cls = importlib.import_module(package + ".providers.subdl").SubDLProvider
    return cls(FakeFetcher(), api_key=api_key)


MOVIE = [{"media_type": "movie", "title": "Example Movie", "year": 2020, "imdb_id": "tt1234567", "tmdb_id": "123"}]
TV = [{"media_type": "tv", "title": "Example Show", "season": 2, "episode": 3}]


def payload(rows, media=None):
    return {"status": True, "results": media or [], "subtitles": rows}


def hit(name="Example.Movie.2020.srt", **values):
    return {"name": name, "lang": "EN", "url": "/subtitle/123.zip", **values}


def search_rows(subject, rows, targets=MOVIE, scope="movie", media=None):
    subject._api_json = lambda params: payload(rows, media)
    return subject.search_all([targets[0]["title"]], targets, scope)


def test_key_required_and_status_does_not_claim_health():
    subject = provider("")
    assert not subject.status()["available"]
    with pytest.raises(ValueError, match="未配置"):
        subject.search("Example", MOVIE, "movie")
    assert "尚未检测" in provider().status()["message"]


def test_identity_first_query_plan_and_request_budget():
    plans = provider()._search_plan(["Example Movie", "Other", "Third", "Fourth"], MOVIE, "movie")
    assert len(plans) == 3
    assert plans[0]["imdb_id"] == "tt1234567"
    assert plans[1]["tmdb_id"] == "123"
    assert plans[2]["film_name"] == "Example Movie"
    assert plans[0]["languages"] == "ZH,EN"
    assert plans[0]["subs_per_page"] == 30
    assert plans[0]["releases"] == 1
    assert all("api_key" not in item for item in plans)


def test_tv_request_unpacks_and_does_not_query_episode_title():
    plan = provider()._search_plan(["Example Show S02E03"], TV, "episode")[0]
    assert plan["film_name"] == "Example Show"
    assert plan["type"] == "tv"
    assert plan["unpack"] == 1
    assert plan["season_number"] == 2
    assert plan["episode_number"] == 3


def test_multiple_seasons_fail_explicitly():
    with pytest.raises(ValueError, match="同一季"):
        provider()._search_plan(["Example"], TV + [{"season": 3, "episode": 1}], "season")


def test_movie_languages_and_download_ids_stay_distinct():
    results = search_rows(provider(), [hit(lang="ZH"), hit(url="/subtitle/124.zip"), hit(lang="JA")])
    assert len(results) == 2
    assert {item.language for item in results} == {"英文", "中文"}
    assert len({item.result_id for item in results}) == 2
    assert results[0].download_url == "https://dl.subdl.com/subtitle/123.zip"


@pytest.mark.parametrize("row", [hit(name="Other.Movie.2020.srt"), hit(name="Example.Movie.1999.srt")])
def test_wrong_title_or_year_rejected(row):
    assert search_rows(provider(), [row]) == []


def test_conflicting_returned_media_id_rejected_even_in_title_query():
    assert search_rows(provider(), [hit()], media=[{"imdb_id": "tt9999999"}]) == []


def test_unpacked_files_require_actual_matching_season_and_episode():
    row = hit("Example.Show.S02.zip", season=2, unpack_files=[
        hit("Example.Show.S02E03.srt", season=2, episode=3, url="/subtitle/3.srt"),
        hit("Example.Show.S03E03.srt", season=3, episode=3, url="/subtitle/wrong.srt"),
        hit("Example.Show.S02E04.srt", season=2, episode=4, url="/subtitle/4.srt"),
        hit("Example.Show.S03E03.srt", season=2, episode=3, url="/subtitle/conflict.srt"),
    ])
    results = search_rows(provider(), [row], TV, "episode")
    assert len(results) == 1
    assert (results[0].season, results[0].episode) == (2, 3)
    assert results[0].download_url.endswith("/3.srt")


def test_season_archive_without_single_file_identity_is_not_mislabeled():
    assert search_rows(provider(), [hit("Example.Show.S02.zip", season=2, episode=0)], TV, "episode") == []


def test_actual_metadata_can_supply_missing_filename_episode():
    results = search_rows(provider(), [hit("Example.Show.srt", season=2, episode=3)], TV, "episode")
    assert len(results) == 1
    assert (results[0].season, results[0].episode) == (2, 3)


def test_payload_errors_do_not_become_empty_results():
    subject = provider()
    with pytest.raises(ValueError, match="鉴权"):
        subject._validate_payload({"status": False, "error": "Invalid API key private-test-key"})
    with pytest.raises(ValueError, match="限流"):
        subject._validate_payload({"status": False, "error": "Daily quota exceeded"})
    with pytest.raises(ValueError, match="失败状态"):
        subject._validate_payload({"status": False, "error": "No subtitles found"})
    with pytest.raises(ValueError, match="字幕列表"):
        subject._validate_payload({"status": True, "results": [hit()]})
    subject._validate_payload(payload([]))


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def test_api_injects_secret_only_at_request_boundary():
    subject = provider()
    seen = []

    def open_request(request, timeout):
        seen.append((request, timeout))
        return Response(json.dumps(payload([])).encode())

    subject.fetcher.opener = types.SimpleNamespace(open=open_request)
    assert subject._api_json({"film_name": "Example"})["subtitles"] == []
    assert parse_qs(urlparse(seen[0][0].full_url).query)["api_key"] == ["private-test-key"]
    assert seen[0][1] == 6


@pytest.mark.parametrize("status,message", [(401, "鉴权"), (403, "鉴权"), (429, "限流"), (503, "HTTP 503")])
def test_http_failure_redacts_url_body_and_exception_chain(status, message):
    subject = provider()

    def fail(request, timeout):
        raise urllib.error.HTTPError(request.full_url, status, "private-test-key", {}, io.BytesIO(b"private-test-key"))

    subject.fetcher.opener = types.SimpleNamespace(open=fail)
    with pytest.raises(ValueError, match=message) as error:
        subject._api_json({"film_name": "Example"})
    assert "private-test-key" not in str(error.value)
    assert error.value.__suppress_context__


def test_network_failure_and_invalid_json_have_safe_errors():
    subject = provider()

    def fail(request, timeout):
        raise urllib.error.URLError(request.full_url)

    subject.fetcher.opener = types.SimpleNamespace(open=fail)
    with pytest.raises(ValueError, match="网络") as error:
        subject._api_json({"film_name": "Example"})
    assert "private-test-key" not in str(error.value)
    subject.fetcher.opener.open = lambda request, timeout: Response(b"<html>private-test-key</html>")
    with pytest.raises(ValueError, match="JSON"):
        subject._api_json({"film_name": "Example"})


@pytest.mark.parametrize("url", ["http://dl.subdl.com/subtitle/1.zip", "https://evil.example/file.srt", "https://dl.subdl.com@evil.example/file.srt", "file:///tmp/file", "//evil.example/file"])
def test_download_rejects_non_official_destinations(url):
    with pytest.raises(ValueError, match="下载地址"):
        provider().download({"download_url": url})


def test_download_uses_existing_downloader():
    name, content = provider().download({"download_url": "/subtitle/123.zip"})
    assert name == "example.srt"
    assert b"-->" in content


def test_first_media_result_owns_subtitles_and_conflicting_identity_is_rejected():
    assert search_rows(provider(), [hit()], media=[{"imdb_id": "tt9999999"}, {"imdb_id": "tt1234567"}]) == []


def test_documented_media_identity_supplies_title_and_year():
    rows = [hit("Episode.One.srt", release_name="Episode One", season=2, episode=3, format="srt", language="EN", url="/subtitle/parent/file1")]
    results = search_rows(provider(), rows, TV, "episode", [{"type": "tv", "name": "Example Show"}])
    assert len(results) == 1
    assert results[0].format == "srt"
    assert search_rows(provider(), [hit()], media=[{"year": 1999}]) == []


def test_full_season_cannot_become_first_episode_without_unpack_files():
    assert search_rows(provider(), [hit("Example.Show.S02E03.zip", season=2, episode=3, full_season=True)], TV, "episode") == []


def test_release_title_cannot_hide_conflicting_filename_episode():
    assert search_rows(provider(), [hit("Example.Show.S03E03.srt", release_name="Example.Show.S02E03", season=2, episode=3)], TV, "episode") == []
