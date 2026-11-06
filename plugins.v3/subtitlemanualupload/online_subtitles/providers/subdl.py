from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any, Dict, List
from urllib.parse import urlencode, urljoin, urlparse

from ..clients import USER_AGENT
from ..language import _guess_subtitle_format, _language_category_from_text
from ..matcher import _assess_result_match, _episode_from_text, _extract_years, _normalize_imdb_tt
from ..models import OnlineSubtitleResult
from ..shared import _dedupe_results, _stable_result_id
from .base import BaseSubtitleProvider


class SubDLProvider(BaseSubtitleProvider):
    """SubDL v1 transport/response adapter; matching and file handling stay shared."""

    provider_id = "subdl"
    display_name = "SubDL"
    default_root_url = "https://subdl.com"
    api_url = "https://api.subdl.com/api/v1/subtitles"
    download_root = "https://dl.subdl.com"
    max_queries = 3
    request_timeout = 6

    def __init__(self, fetcher, root_url: str = "", *, api_key: str = ""):
        super().__init__(fetcher, root_url=root_url)
        self.api_key = str(api_key or "").strip()

    def status(self) -> Dict[str, Any]:
        status = super().status()
        status.update(
            available=bool(self.api_key),
            api_configured=bool(self.api_key),
            api_host="api.subdl.com",
            message="已配置 API Key；尚未检测连通性" if self.api_key else "未配置 API Key；不参与自动搜索",
        )
        return status

    def manual_url(self, keyword: str) -> str:
        return f"{self.root_url}/search?{urlencode({'query': keyword})}"

    def search(self, keyword: str, targets: List[Dict[str, Any]], scope: str) -> List[OnlineSubtitleResult]:
        return self.search_all([keyword], targets, scope)

    def search_all(self, keywords: List[str], targets: List[Dict[str, Any]], scope: str) -> List[OnlineSubtitleResult]:
        if not self.api_key:
            raise ValueError("SubDL 未配置 API Key")
        for params in self._search_plan(keywords, targets, scope):
            payload = self._api_json(params)
            found = self._parse_results(payload, params, keywords, targets)
            if found:
                return found
        return []

    def _search_plan(self, keywords, targets, scope):
        is_tv = scope in {"episode", "season"} or any(item.get("media_type") == "tv" for item in targets)
        base = {"type": "tv" if is_tv else "movie", "languages": "ZH,EN", "subs_per_page": 30, "releases": 1}
        if is_tv:
            seasons = {int(item["season"]) for item in targets if item.get("season") is not None and str(item["season"]).isdigit()}
            if len(seasons) > 1:
                raise ValueError("SubDL 单次搜索仅支持同一季，请按季搜索")
            if seasons:
                base["season_number"] = next(iter(seasons))
            episodes = {int(item["episode"]) for item in targets if str(item.get("episode") or "").isdigit()}
            if len(episodes) == 1:
                base["episode_number"] = next(iter(episodes))
            base["unpack"] = 1
        years = {str(item["year"]) for item in targets if re.fullmatch(r"\d{4}", str(item.get("year") or ""))}
        if len(years) == 1:
            base["year"] = next(iter(years))
        identities = []
        for field in ("imdb_id", "tmdb_id"):
            values = [str(item.get(field) or "").strip() for item in targets]
            value = next((value for value in values if value), "")
            if field == "imdb_id":
                value = _normalize_imdb_tt(value)
            elif not value.isdigit():
                value = ""
            if value:
                identities.append({field: value})
        seen = set()
        for keyword in keywords:
            title = re.sub(r"(?i)\s*S\d{1,2}(?:E\d{1,3})?\b.*$", "", str(keyword)).strip()
            if title and title.casefold() not in seen:
                identities.append({"film_name": title})
                seen.add(title.casefold())
        return [{**base, **identity} for identity in identities[:self.max_queries]]

    def _api_json(self, params):
        # v1 puts the key in the query: never pass request URLs or remote bodies to errors/logs.
        request = urllib.request.Request(
            f"{self.api_url}?{urlencode({**params, 'api_key': self.api_key})}",
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        )
        try:
            with self.fetcher.opener.open(request, timeout=self.request_timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            if exc.code in {401, 403}:
                raise ValueError("SubDL API 鉴权失败，请检查密钥及账户权限") from None
            if exc.code == 429:
                raise ValueError("SubDL API 请求限流或额度耗尽") from None
            raise ValueError(f"SubDL API 服务请求失败 HTTP {exc.code}") from None
        except (urllib.error.URLError, OSError):
            raise ValueError("SubDL API 网络请求失败，请检查网络或代理") from None
        try:
            payload = json.loads(raw)
        except (ValueError, UnicodeError):
            raise ValueError("SubDL API 返回内容不是有效 JSON") from None
        self._validate_payload(payload)
        return payload

    @staticmethod
    def _validate_payload(payload):
        if not isinstance(payload, dict):
            raise ValueError("SubDL API 响应结构发生变化")
        if payload.get("status") is not True:
            detail = str(payload.get("error") or payload.get("message") or "").lower()
            if any(word in detail for word in ("api_key", "api key", "apikey", "unauthorized", "not_authorized", "forbidden", "authentication")):
                raise ValueError("SubDL API 鉴权失败，请检查密钥及账户权限")
            if any(word in detail for word in ("limit", "quota", "too many")):
                raise ValueError("SubDL API 请求限流或额度耗尽")
            raise ValueError("SubDL API 返回失败状态；不能视为没有字幕")
        if not isinstance(payload.get("subtitles"), list):
            raise ValueError("SubDL API 缺少字幕列表或响应结构发生变化")

    def _parse_results(self, payload, params, keywords, targets):
        self._validate_payload(payload)
        results = []
        media = payload.get("results")
        # v1 documents that subtitles always belong to results[0].
        metadata = media[0] if isinstance(media, list) and media and isinstance(media[0], dict) else {}
        if metadata.get("type") and metadata["type"] != params["type"]:
            return []
        for field in ("imdb_id", "tmdb_id"):
            expected = {str(target[field]) for target in targets if target.get(field)}
            if metadata.get(field) and expected and str(metadata[field]) not in expected:
                return []
        for row in payload["subtitles"]:
            if not isinstance(row, dict):
                raise ValueError("SubDL API 字幕条目结构发生变化")
            unpacked = row.get("unpack_files")
            if unpacked is not None and not isinstance(unpacked, list):
                raise ValueError("SubDL API 单集文件列表结构发生变化")
            season_pack = row.get("full_season") or row.get("episode_from") != row.get("episode_end")
            if params["type"] == "tv" and not unpacked and season_pack:
                continue
            entries = unpacked if params["type"] == "tv" and isinstance(unpacked, list) and unpacked else [row]
            for entry in entries:
                if not isinstance(entry, dict):
                    raise ValueError("SubDL API 单集文件结构发生变化")
                candidate = self._candidate(row, entry, metadata, params, keywords, targets)
                if candidate:
                    results.append(candidate)
        return _dedupe_results(results)[:80]

    def _candidate(self, row, entry, metadata, params, keywords, targets):
        releases = entry.get("releases")
        release = next((item for item in releases if isinstance(item, str) and item), "") if isinstance(releases, list) else ""
        title = str(entry.get("release_name") or release or entry.get("name") or "").strip()
        download_url = self._download_url(entry.get("url"))
        if not title or not download_url:
            return None
        language = str(entry.get("lang") or entry.get("language") or row.get("lang") or row.get("language") or "").strip()
        category = _language_category_from_text(language)
        if category not in {"chinese", "english"}:
            return None
        season, episode = self._season_episode(entry, title)
        if season is None or episode is None:
            return None
        if params["type"] == "tv":
            # Never label a season archive or ambiguous filename with the requested episode.
            if not episode or not any(
                int(target.get("season") or 0) == season
                and (not target.get("episode") or int(target["episode"]) == episode)
                for target in targets
            ):
                return None
            if entry is not row and row.get("season") is not None and str(row["season"]) != str(season):
                return None
        match_title = title
        if params["type"] == "tv" and not _episode_from_text(title):
            match_title += f" S{season:02d}E{episode:02d}"
        assessment = _assess_result_match(
            title=match_title,
            keyword="",
            targets=targets or [{"title": keyword} for keyword in keywords],
            attrs={**{key: metadata[key] for key in ("imdb_id", "tmdb_id") if metadata.get(key)}, "movie_name": metadata.get("name")},
            result_years=_extract_years(str(metadata.get("year") or "")) or _extract_years(title),
        )
        if assessment["identity_status"] == "failed":
            return None
        label = {"en": "英文", "english": "英文", "zh": "中文", "chinese": "中文"}.get(language.lower(), language)
        page_url = urljoin(self.root_url + "/", str(row.get("subtitlePage") or ""))
        return OnlineSubtitleResult(
            provider=self.provider_id, provider_label=self.display_name,
            result_id=_stable_result_id(self.provider_id, download_url + "|" + language),
            title=title, page_url=page_url, download_url=download_url,
            language=label, language_category=category, format=str(entry.get("format") or _guess_subtitle_format(title + " " + download_url)),
            season=season, episode=episode, score=assessment["score"], source=self.display_name,
            note="SubDL 官方接口；语言由来源声明，未验证翻译质量" + ("；含听障说明" if entry.get("hi") else ""),
            identity_status=assessment["identity_status"], relevance_status=assessment["relevance_status"],
            match_detail=assessment["match_detail"], query_plan="SubDL v1",
        )

    @staticmethod
    def _season_episode(entry, title):
        season = entry.get("season")
        episode = entry.get("episode")
        if season is not None and not str(season).isdigit():
            return None, None
        if episode is not None and not str(episode).isdigit():
            return None, None
        parsed = _episode_from_text(title)
        file_episode = _episode_from_text(str(entry.get("name") or ""))
        if parsed and file_episode and parsed != file_episode:
            return None, None
        parsed = file_episode or parsed
        if parsed:
            if season is not None and parsed[0] and int(season) != parsed[0]:
                return None, None
            if episode is not None and int(episode) != parsed[1]:
                return None, None
        return int(season) if season is not None else (parsed[0] if parsed else 0), int(episode) if episode is not None else (parsed[1] if parsed else 0)

    def _download_url(self, value):
        url = urljoin(self.download_root + "/", str(value or "")) if value else ""
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname != "dl.subdl.com" or parsed.username or parsed.password or parsed.port not in {None, 443}:
            return ""
        return url

    def download(self, result, captcha_code=""):
        url = self._download_url(result.get("download_url"))
        if not url:
            raise ValueError("SubDL 缺少有效的官方字幕下载地址")
        return super().download({**result, "download_url": url}, captcha_code=captcha_code)
