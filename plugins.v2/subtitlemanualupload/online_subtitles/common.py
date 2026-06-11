from __future__ import annotations

import base64
import html
import http.cookiejar
import io
import json
import re
import ssl
import struct
import time
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import quote, unquote, urlencode, urljoin, urlparse, urlunparse

from app.core.config import settings
from app.log import logger


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
)
DEFAULT_ENGINE = "cloakbrowser"
MP_BROWSER_ENGINE = "mp_browser"
ONLINE_ENGINES = {DEFAULT_ENGINE, MP_BROWSER_ENGINE}
DEFAULT_PROVIDER_ROOTS = {
    "subhd": "https://subhd.tv",
    "zimuku": "https://zimuku.org",
    "assrt": "https://2.assrt.net",
    "opensubtitles": "https://www.opensubtitles.com",
}
DEFAULT_ASSRT_API_URL = "https://api.assrt.net"
DEFAULT_OPENSUBTITLES_API_URL = "https://api.opensubtitles.com/api/v1"
OPENSUBTITLES_SEARCH_LANGUAGES = "zh-cn,zh-tw,ze,en,ja,ko"
INTERACTIVE_DOWNLOAD_EVENT_TIMEOUT_MS = 12000
GENERIC_TITLE_ALIAS_WORDS = {
    "arabic",
    "chinese",
    "danish",
    "dutch",
    "english",
    "french",
    "german",
    "italian",
    "italiano",
    "japanese",
    "korean",
    "mandarin",
    "portuguese",
    "russian",
    "spanish",
    "thai",
    "turkish",
    "vietnamese",
    "cantonese",
    "deutsch",
    "espanol",
    "español",
    "francais",
    "français",
    "nederlands",
    "portugues",
    "português",
    "finnish",
    "suomi",
    "turkce",
    "türkçe",
    "中文",
    "国语",
    "國語",
    "普通话",
    "普通話",
    "粤语",
    "粵語",
    "英文",
    "英语",
    "英語",
    "日文",
    "日语",
    "日語",
    "日本語",
    "韩文",
    "韓文",
    "韩语",
    "韓語",
}
GENERIC_TITLE_ALIAS_CODES = {
    "ar",
    "cn",
    "cmn",
    "da",
    "de",
    "en",
    "eng",
    "es",
    "fr",
    "it",
    "ita",
    "ja",
    "jpn",
    "ko",
    "kor",
    "pt",
    "ru",
    "th",
    "vi",
    "yue",
    "zh",
    "zh-cn",
    "zh-hans",
    "zh-hant",
    "zh-tw",
}


@dataclass
class OnlineSubtitleResult:
    provider: str
    result_id: str
    title: str
    page_url: str
    download_url: str = ""
    language: str = ""
    format: str = ""
    season: int = 0
    episode: int = 0
    score: int = 0
    source: str = ""
    note: str = ""
    downloadable: bool = True
    language_category: str = ""
    provider_label: str = ""
    requires_captcha: bool = False
    captcha_hint: str = ""
    download_steps: str = ""
    result_years: Optional[List[int]] = None
    match_year: int = 0
    relevance_status: str = ""
    region_bucket: str = ""
    query_plan: str = ""
    identity_status: str = ""
    reject_reason: str = ""
    match_detail: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "provider_label": self.provider_label or self.source or self.provider,
            "result_id": self.result_id,
            "title": self.title,
            "page_url": self.page_url,
            "download_url": self.download_url,
            "language": self.language,
            "format": self.format,
            "season": self.season,
            "episode": self.episode,
            "score": self.score,
            "source": self.source,
            "note": self.note,
            "downloadable": self.downloadable,
            "language_category": self.language_category or _language_category_from_text(self.language),
            "requires_captcha": self.requires_captcha,
            "captcha_hint": self.captcha_hint,
            "download_steps": self.download_steps,
            "result_years": self.result_years or [],
            "match_year": self.match_year,
            "relevance_status": self.relevance_status,
            "region_bucket": self.region_bucket,
            "query_plan": self.query_plan,
            "identity_status": self.identity_status,
            "reject_reason": self.reject_reason,
            "match_detail": self.match_detail,
        }


@dataclass
class HtmlLink:
    href: str
    text: str


class CaptchaRequiredError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        provider: str = "",
        verify_url: str = "",
        captcha_image: str = "",
        captcha_hint: str = "",
    ):
        super().__init__(message)
        self.provider = provider
        self.verify_url = verify_url
        self.captcha_image = captcha_image
        self.captcha_hint = captcha_hint or message

    def to_payload(self) -> Dict[str, Any]:
        return {
            "captcha_required": True,
            "provider": self.provider,
            "message": str(self),
            "verify_url": self.verify_url,
            "captcha_image": self.captcha_image,
            "captcha_hint": self.captcha_hint,
        }


class LinkExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links: List[HtmlLink] = []
        self._current_href = ""
        self._current_text: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]):
        if tag.lower() != "a" or self._current_href:
            return
        attr_map = {name.lower(): value or "" for name, value in attrs}
        href = attr_map.get("href", "").strip()
        if href:
            self._current_href = href
            self._current_text = []

    def handle_data(self, data: str):
        if self._current_href:
            self._current_text.append(data)

    def handle_endtag(self, tag: str):
        if tag.lower() != "a" or not self._current_href:
            return
        text = re.sub(r"\s+", " ", html.unescape(" ".join(self._current_text))).strip()
        self.links.append(HtmlLink(href=self._current_href, text=text))
        self._current_href = ""
        self._current_text = []


class OnlinePageClient:
    def __init__(
        self,
        *,
        engine: str = DEFAULT_ENGINE,
        use_proxy: bool = False,
        timeout: int = 60,
    ):
        self.engine = normalize_online_engine(engine)
        self.use_proxy = use_proxy
        self.timeout = timeout
        self.cookie_jar = http.cookiejar.CookieJar()
        handlers = [urllib.request.HTTPCookieProcessor(self.cookie_jar)]
        proxies = getattr(settings, "PROXY", None) if use_proxy else None
        if proxies:
            handlers.append(urllib.request.ProxyHandler(proxies))
        self.opener = urllib.request.build_opener(*handlers)

    def status(self) -> Dict[str, Any]:
        return {
            "engine": "api",
            "engine_name": "API 自动搜索",
            "available": True,
            "cloakbrowser": False,
            "mp_browser": False,
            "proxy": bool(getattr(settings, "PROXY", None) or getattr(settings, "PROXY_SERVER", None)),
        }

    def available(self) -> bool:
        return True

    def get_text(self, url: str, *, referer: str = "") -> Tuple[int, str, str]:
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        if referer:
            headers["Referer"] = referer
        request = urllib.request.Request(url, headers=headers)
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                raw = response.read()
                charset = response.headers.get_content_charset()
                return response.status, _decode_bytes(raw, charset), response.geturl()
        except urllib.error.HTTPError as exc:
            detail = _decode_bytes(exc.read()[:500], exc.headers.get_content_charset())
            return exc.code, detail, url
        except (urllib.error.URLError, OSError, ssl.SSLError) as exc:
            raise ValueError(_format_network_error(url, exc)) from exc

    def get_bytes(self, url: str, *, referer: str = "") -> Tuple[str, bytes, str]:
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        if referer:
            headers["Referer"] = referer
        request = urllib.request.Request(url, headers=headers)
        last_error: Optional[Exception] = None
        for attempt in range(3):
            try:
                with self.opener.open(request, timeout=self.timeout) as response:
                    content = response.read()
                    filename = OnlineDirectDownloader._filename_from_response(response.headers, response.geturl() or url)
                    logger.info(
                        "[SubtitleManualUpload] 在线字幕下载摘要 host=%s content_type=%s filename=%s magic=%s size=%s",
                        _host(response.geturl() or url),
                        response.headers.get("Content-Type", ""),
                        filename,
                        _content_magic(content),
                        len(content),
                    )
                    return filename, content, response.geturl()
            except urllib.error.HTTPError as exc:
                detail = _decode_bytes(exc.read()[:300], exc.headers.get_content_charset())
                raise ValueError(f"下载失败 HTTP {exc.code}: {detail}") from exc
            except (urllib.error.URLError, OSError, ssl.SSLError) as exc:
                last_error = exc
                if attempt < 2 and _is_retryable_network_error(exc):
                    time.sleep(0.5 * (2 ** attempt))
                    continue
                break
        if last_error:
            raise ValueError(_format_network_error(url, last_error)) from last_error
        raise ValueError(f"下载失败: {_host(url)} 未返回数据")

    def post_json(self, url: str, payload: Dict[str, Any], *, referer: str = "") -> Dict[str, Any]:
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        if referer:
            headers["Referer"] = referer
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            detail = _decode_bytes(exc.read()[:500], exc.headers.get_content_charset())
            raise ValueError(f"请求失败 HTTP {exc.code}: {_compact_error_message(detail)}") from exc
        except (urllib.error.URLError, OSError, ssl.SSLError) as exc:
            raise ValueError(_format_network_error(url, exc)) from exc
        try:
            payload = json.loads(_decode_bytes(raw, None) or "{}")
        except Exception as exc:
            raise ValueError("接口返回内容不是 JSON") from exc
        return payload if isinstance(payload, dict) else {}

    def get_bytes_interactive(self, url: str, *, referer: str = "", captcha_code: str = "") -> Tuple[str, bytes, str]:
        raise CaptchaRequiredError(
            "已移除自动页面仿真下载，请使用右侧手动跳转下载字幕包后上传。",
            verify_url=url,
        )

    def close(self) -> None:
        return None

class OnlineDirectDownloader:
    def __init__(self, *, use_proxy: bool = False, cookies: str = "", timeout: int = 40):
        self.timeout = timeout
        self.cookies = cookies
        handlers = []
        proxies = getattr(settings, "PROXY", None) if use_proxy else None
        if proxies:
            handlers.append(urllib.request.ProxyHandler(proxies))
        self.opener = urllib.request.build_opener(*handlers)

    def get_bytes(self, url: str, *, referer: str = "") -> Tuple[str, bytes, str]:
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        if referer:
            headers["Referer"] = referer
        if self.cookies:
            headers["Cookie"] = self.cookies
        request = urllib.request.Request(url, headers=headers)
        last_error: Optional[Exception] = None
        for attempt in range(3):
            try:
                with self.opener.open(request, timeout=self.timeout) as response:
                    content = response.read()
                    filename = self._filename_from_response(response.headers, response.geturl() or url)
                    logger.info(
                        "[SubtitleManualUpload] 在线字幕下载摘要 host=%s content_type=%s filename=%s magic=%s size=%s",
                        _host(response.geturl() or url),
                        response.headers.get("Content-Type", ""),
                        filename,
                        _content_magic(content),
                        len(content),
                    )
                    return filename, content, response.geturl()
            except urllib.error.HTTPError as exc:
                detail = _decode_bytes(exc.read()[:300], exc.headers.get_content_charset())
                raise ValueError(f"下载失败 HTTP {exc.code}: {detail}") from exc
            except (urllib.error.URLError, OSError, ssl.SSLError) as exc:
                last_error = exc
                if attempt < 2 and _is_retryable_network_error(exc):
                    time.sleep(0.5 * (2 ** attempt))
                    continue
                break
        if last_error:
            raise ValueError(_format_network_error(url, last_error)) from last_error
        raise ValueError(f"下载失败: {_host(url)} 未返回数据")

    @staticmethod
    def _filename_from_response(headers: Any, url: str) -> str:
        disposition = headers.get("Content-Disposition", "")
        match = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)', disposition, re.I)
        if match:
            return unquote(match.group(1)).strip() or "subtitle.zip"
        name = Path(url).name
        return name or "subtitle.zip"


def _looks_like_html_bytes(content: bytes, filename: str = "") -> bool:
    suffix = Path(filename or "").suffix.lower()
    if suffix in {".zip", ".rar", ".srt", ".ass", ".ssa", ".sub", ".vtt", ".webvtt", ".sbv"}:
        return False
    head = (content or b"")[:300].lstrip().lower()
    return head.startswith(b"<!doctype html") or head.startswith(b"<html") or b"<title>" in head


def _content_magic(content: bytes) -> str:
    head = (content or b"")[:16]
    if head.startswith(b"PK\x03\x04"):
        return "zip"
    if head.startswith(b"Rar!\x1a\x07"):
        return "rar"
    text = _decode_bytes(head, None).lstrip().lower()
    if text.startswith("<!do") or text.startswith("<htm"):
        return "html"
    if re.match(r"^\d+\s*", text):
        return "text"
    return head.hex()[:16] or "-"


def build_search_keywords(media: Dict[str, Any], targets: List[Dict[str, Any]], scope: str) -> List[str]:
    title = _clean_keyword(media.get("title") or (targets[0].get("title") if targets else ""))
    year = _clean_keyword(media.get("year") or (targets[0].get("year") if targets else ""))
    media_type = media.get("media_type") or (targets[0].get("media_type") if targets else "")
    search_titles = _search_titles_by_region(media, targets)
    if title and title not in search_titles:
        search_titles.append(title)
    search_titles = _unique_keywords(search_titles)
    keywords: List[str] = []
    if media_type == "tv":
        seasons = sorted({int(target.get("season") or 0) for target in targets if int(target.get("season") or 0)})
        episodes = sorted({int(target.get("episode") or 0) for target in targets if int(target.get("episode") or 0)})
        if search_titles and seasons:
            season = seasons[0]
            if scope in {"season", "batch"} or len(episodes) > 1:
                for item in search_titles[:4]:
                    keywords.append(f"{item} S{season:02d}")
            elif episodes:
                episode = episodes[0]
                for item in search_titles[:4]:
                    keywords.append(f"{item} S{season:02d}E{episode:02d}")
        if not keywords:
            for target in targets[:3]:
                basename = _clean_tv_basename_keyword(target.get("basename") or target.get("filename"))
                if basename:
                    keywords.append(basename)
    elif search_titles:
        if year:
            keywords.extend([f"{item} {year}" for item in search_titles[:5]])
        keywords.extend(search_titles[:5])
    return _unique_keywords([item for item in keywords if item])


def _clean_tv_basename_keyword(value: Any) -> str:
    basename = _clean_keyword(value)
    if not basename:
        return ""
    basename = re.sub(r"\.(mkv|mp4|avi|ts|m2ts|mov|wmv|flv|webm)$", "", basename, flags=re.I)
    episode_match = re.search(r"(?i)(.*?)(S\d{1,2}E\d{1,3})\b", basename)
    if episode_match:
        prefix = re.sub(r"[\s._-]+$", "", episode_match.group(1)).strip()
        code = episode_match.group(2).upper()
        return f"{prefix} {code}".strip() if prefix else code
    season_match = re.search(r"(?i)(.*?)(S\d{1,2})\b", basename)
    if season_match:
        prefix = re.sub(r"[\s._-]+$", "", season_match.group(1)).strip()
        code = season_match.group(2).upper()
        return f"{prefix} {code}".strip() if prefix else code
    return basename


def _query_plan_for_keyword(keyword: str, targets: List[Dict[str, Any]]) -> Dict[str, str]:
    bucket = _region_bucket({}, targets)
    source = _query_source_for_keyword(keyword, targets)
    return {
        "region_bucket": bucket,
        "query_source": source,
        "subtitle_languages": OPENSUBTITLES_SEARCH_LANGUAGES,
        "label": (
            f"{_region_bucket_label(bucket)}区域 · {source} · "
            f"字幕语言 {OPENSUBTITLES_SEARCH_LANGUAGES}"
        ),
    }


def _search_titles_by_region(media: Dict[str, Any], targets: List[Dict[str, Any]]) -> List[str]:
    bucket = _region_bucket(media, targets)
    all_titles = _media_title_aliases(media, targets)
    explicit_english_titles = _explicit_title_values(
        media,
        targets,
        ["en_title", "title_en", "name_en", "english_title"],
    )
    chinese_titles = [item for item in all_titles if _contains_cjk(item)]
    japanese_titles = [item for item in all_titles if _contains_japanese(item)]
    korean_titles = [item for item in all_titles if _contains_korean(item)]
    original_titles = _original_titles(media, targets)

    native_titles = {
        "chinese": chinese_titles,
        "japanese": japanese_titles,
        "korean": korean_titles,
    }.get(bucket, [])
    ordered = [
        *explicit_english_titles,
        *original_titles,
        *native_titles,
        *chinese_titles,
        *japanese_titles,
        *korean_titles,
        *all_titles,
    ]
    return _unique_keywords(ordered)


def _explicit_title_values(media: Dict[str, Any], targets: List[Dict[str, Any]], fields: List[str]) -> List[str]:
    values: List[str] = []
    for source in [media, *(targets or [])]:
        if not isinstance(source, dict):
            continue
        for field in fields:
            value = _clean_title_alias(source.get(field))
            if value:
                values.append(value)
    return _unique_keywords(values)


def _media_title_aliases(media: Dict[str, Any], targets: List[Dict[str, Any]]) -> List[str]:
    values: List[str] = []
    for source in [media, *(targets or [])]:
        if not isinstance(source, dict):
            continue
        for field in ["title", "name", "en_title", "original_title", "original_name", "title_en", "name_en", "english_title"]:
            value = _clean_title_alias(source.get(field))
            if value:
                values.append(value)
        for field in ["aliases", "alternative_titles", "translations", "tmdb_aliases"]:
            values.extend(_alias_values(source.get(field)))
    return _unique_keywords(values)


def _region_bucket(media: Dict[str, Any], targets: List[Dict[str, Any]]) -> str:
    sources = [media, *(targets or [])]
    languages = {_normalize_code(item) for source in sources for item in _as_list(source.get("original_language") if isinstance(source, dict) else "")}
    countries = {
        _normalize_code(item)
        for source in sources
        if isinstance(source, dict)
        for field in ["origin_country", "production_countries", "country", "area", "region"]
        for item in _as_list(source.get(field))
    }
    category_text = " ".join(
        str(source.get(field) or "")
        for source in sources
        if isinstance(source, dict)
        for field in ["category", "media_category", "library_name"]
    )
    if languages & {"zh", "cn", "cmn", "yue"} or countries & {"cn", "hk", "tw", "sg"} or re.search(r"华语|国产|港|台|中国|大陆", category_text):
        return "chinese"
    if languages & {"ja", "jp"} or countries & {"jp"} or re.search(r"日本|日剧|日漫|动画", category_text):
        return "japanese"
    if languages & {"ko", "kr"} or countries & {"kr", "kp"} or re.search(r"韩国|韩剧", category_text):
        return "korean"
    if languages & {"en"} or countries & {"us", "gb", "uk", "ca", "au", "nz", "ie"} or re.search(r"欧美|美剧|英剧", category_text):
        return "western"
    return "other"


def _region_bucket_label(bucket: str) -> str:
    return {
        "chinese": "华语",
        "western": "欧美",
        "japanese": "日本",
        "korean": "韩国",
        "other": "原始",
    }.get(bucket or "", "原始")


def _query_source_for_keyword(keyword: str, targets: List[Dict[str, Any]]) -> str:
    if not _clean_keyword(keyword):
        return "空查询词"
    aliases = _media_title_aliases({}, targets)
    original_titles = _original_titles({}, targets)
    english_titles = [item for item in aliases if _looks_english_title(item)]
    chinese_titles = [
        item
        for item in aliases
        if _contains_cjk(item) and not _contains_japanese(item) and not _contains_korean(item)
    ]
    for title in original_titles:
        if _strong_title_matches(title, keyword):
            return "原名查询"
    for title in english_titles:
        if _strong_title_matches(title, keyword):
            return "英文标题查询"
    for title in chinese_titles:
        if _strong_title_matches(title, keyword):
            return "中文标题查询"
    if _contains_japanese(keyword):
        return "日文查询"
    if _contains_korean(keyword):
        return "韩文查询"
    if _looks_english_title(keyword):
        return "英文弱兜底"
    if _contains_cjk(keyword):
        return "中文弱兜底"
    return "文件名查询"


def _title_aliases(media: Dict[str, Any], targets: List[Dict[str, Any]]) -> List[str]:
    values: List[str] = []
    for source in [media, *(targets or [])]:
        if not isinstance(source, dict):
            continue
        for field in [
            "title",
            "name",
            "en_title",
            "original_title",
            "original_name",
            "title_en",
            "name_en",
            "english_title",
            "filename",
            "basename",
        ]:
            value = _clean_title_alias(source.get(field))
            if value:
                values.append(value)
        for field in ["aliases", "alternative_titles", "translations", "tmdb_aliases"]:
            values.extend(_alias_values(source.get(field)))
    return _unique_keywords(values)


def _original_titles(media: Dict[str, Any], targets: List[Dict[str, Any]]) -> List[str]:
    values: List[str] = []
    for source in [media, *(targets or [])]:
        if not isinstance(source, dict):
            continue
        for field in ["original_title", "original_name"]:
            value = _clean_title_alias(source.get(field))
            if value:
                values.append(value)
    return _unique_keywords(values)


def _alias_values(value: Any) -> List[str]:
    values: List[str] = []
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except Exception:
            parsed = None
        if parsed is not None:
            return _alias_values(parsed)
        alias = _clean_title_alias(value)
        return [alias] if alias else []
    if isinstance(value, dict):
        if _looks_translation_metadata(value):
            values.extend(_alias_values(value.get("data")))
            for key in ["titles", "results", "translations", "alternative_titles", "aliases"]:
                values.extend(_alias_values(value.get(key)))
            return _unique_keywords(values)
        for key in ["title", "name", "english_name"]:
            values.extend(_alias_values(value.get(key)))
        for key in ["data", "titles", "results", "translations", "alternative_titles", "aliases"]:
            values.extend(_alias_values(value.get(key)))
        return _unique_keywords(values)
    if isinstance(value, list):
        for item in value:
            values.extend(_alias_values(item))
    return _unique_keywords(values)


def extract_title_aliases(value: Any) -> List[str]:
    return _alias_values(value)


def _looks_translation_metadata(value: Dict[str, Any]) -> bool:
    if "data" not in value:
        return False
    language_keys = {"iso_639_1", "iso_3166_1", "english_name"}
    return bool(language_keys & set(value.keys()))


def _as_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple) or isinstance(value, set):
        return list(value)
    if isinstance(value, dict):
        return list(value.values())
    text = str(value or "").strip()
    return [text] if text else []


def _normalize_code(value: Any) -> str:
    return re.sub(r"[^a-z]", "", str(value or "").lower())


def _contains_cjk(value: str) -> bool:
    return bool(re.search(r"[\u3400-\u9fff]", value or ""))


def _contains_japanese(value: str) -> bool:
    return bool(re.search(r"[\u3040-\u30ff]", value or ""))


def _contains_korean(value: str) -> bool:
    return bool(re.search(r"[\uac00-\ud7af]", value or ""))


def _looks_english_title(value: str) -> bool:
    text = value or ""
    return bool(re.search(r"[a-zA-Z]", text)) and not _contains_cjk(text) and not _contains_japanese(text) and not _contains_korean(text)


def normalize_online_engine(value: Any) -> str:
    engine = str(value or "").strip().lower()
    aliases = {
        "cloak": DEFAULT_ENGINE,
        "cloakbrowser": DEFAULT_ENGINE,
        "mp": MP_BROWSER_ENGINE,
        "browser": MP_BROWSER_ENGINE,
        "flaresolverr": MP_BROWSER_ENGINE,
        "mp_browser": MP_BROWSER_ENGINE,
        "moviepilot": MP_BROWSER_ENGINE,
    }
    return aliases.get(engine, DEFAULT_ENGINE)


def normalize_root_url(value: Any, default: str) -> str:
    url = str(value or "").strip().rstrip("/")
    if not re.match(r"^https?://", url, flags=re.I):
        return default
    return url


def normalize_provider_roots(value: Optional[Dict[str, Any]]) -> Dict[str, str]:
    raw = value if isinstance(value, dict) else {}
    return {
        provider_id: normalize_root_url(raw.get(provider_id), default_url)
        for provider_id, default_url in DEFAULT_PROVIDER_ROOTS.items()
    }


def _episode_from_text(value: str) -> Optional[Tuple[int, int]]:
    text = value or ""
    patterns = [
        re.compile(r"(?i)\bS(?P<season>\d{1,2})[\s._-]*E(?P<episode>\d{1,3})\b"),
        re.compile(r"(?i)\b(?P<season>\d{1,2})x(?P<episode>\d{1,3})\b"),
        re.compile(r"第\s*(?P<season>\d{1,2})\s*季.*?第\s*(?P<episode>\d{1,3})\s*[集话話]"),
        re.compile(r"第\s*(?P<episode>\d{1,3})\s*[集话話]"),
    ]
    for pattern in patterns:
        match = pattern.search(text)
        if not match:
            continue
        season = int(match.groupdict().get("season") or 0)
        episode = int(match.groupdict().get("episode") or 0)
        if episode:
            return season, episode
    return None


def _looks_like_mojibake(value: str) -> bool:
    text = str(value or "")
    if not text:
        return False
    if text.count("�") >= 2:
        return True
    cjk_mojibake_leads = sum(text.count(ch) for ch in ("æ", "ç", "è", "å"))
    if cjk_mojibake_leads >= 2:
        return True
    latin1_markers = ("Ã", "Â", "â€", "â€™", "â€œ", "â€")
    marker_count = sum(text.count(marker) for marker in latin1_markers)
    return marker_count >= 2


def _guess_language_label(value: str) -> str:
    text = (value or "").lower()
    if any(key in text for key in ["简英", "中英", "双语", "chs&eng", "chi_eng", "zh&en"]):
        return "简英双语"
    if any(key in text for key in ["繁", "cht", "zh-hant", "zh-tw"]) or re.search(
        r"(^|[\s._\-\[\]()])(?:tw|hk)(?=$|[\s._\-\[\]()])",
        text,
    ):
        return "繁体中文"
    if any(key in text for key in ["简", "chs", "zh-hans", "中文", "chinese"]):
        return "简体中文"
    if any(key in text for key in ["eng", "english"]):
        return "英文"
    if any(key in text for key in ["日文", "日语", "jpn", "japanese"]) or re.search(
        r"(^|[\s._\-\[\]()])ja(?=$|[\s._\-\[\]()])",
        text,
    ):
        return "日文"
    return ""


def _language_category_from_text(value: str) -> str:
    text = (value or "").lower()
    if any(
        key in text
        for key in [
            "中文",
            "简体",
            "繁体",
            "简英",
            "中英",
            "双语",
            "chinese",
            "chs",
            "cht",
            "chi",
            "zho",
            "cmn",
            "zh-cn",
            "zh-tw",
            "zh-ca",
            "zh-hans",
            "zh-hant",
        ]
    ) or re.search(r"(^|[\s._\-\[\]()])(?:zh|ze)(?=$|[\s._\-\[\]()])", text):
        return "chinese"
    if any(key in text for key in ["英文", "english", "eng"]):
        return "english"
    if any(key in text for key in ["日文", "日语", "japanese", "jpn"]):
        return "japanese"
    if any(key in text for key in ["韩文", "韩语", "korean", "kor"]):
        return "other"
    if re.search(r"(^|[\s._\-\[\]()])en(?=$|[\s._\-\[\]()])", text):
        return "english"
    if re.search(r"(^|[\s._\-\[\]()])ja(?=$|[\s._\-\[\]()])", text):
        return "japanese"
    return "other"


def _language_label_from_category(category: str, raw_language: str = "") -> str:
    raw = (raw_language or "").lower()
    if category == "chinese":
        if any(key in raw for key in ["zh-tw", "zh-hant", "cht"]):
            return "繁体中文"
        if raw == "ze":
            return "中英双语"
        return "简体中文"
    if category == "english":
        return "英文"
    if category == "japanese":
        return "日文"
    return raw_language or "其他"


def _language_priority(item: OnlineSubtitleResult) -> int:
    category = item.language_category or _language_category_from_text(f"{item.language} {item.title} {item.note}")
    return {
        "chinese": 40,
        "english": 30,
        "japanese": 20,
        "korean": 20,
        "other": 10,
    }.get(category, 0)


def _guess_subtitle_format(value: str) -> str:
    formats = []
    for ext in [".ass", ".srt", ".ssa", ".vtt", ".sub", ".zip", ".rar"]:
        if ext in (value or "").lower():
            formats.append(ext.removeprefix(".").upper())
    return " / ".join(formats)


def _score_result(title: str, keyword: str, targets: List[Dict[str, Any]]) -> int:
    return int(_assess_result_match(title=title, keyword=keyword, targets=targets)["score"])


def _filter_relevant_results(
    results: Iterable[OnlineSubtitleResult],
    keyword: str,
    targets: List[Dict[str, Any]],
) -> List[OnlineSubtitleResult]:
    return [item for item in results if _has_relevance_signal(item.title, keyword, targets)]


def _has_relevance_signal(title: str, keyword: str, targets: List[Dict[str, Any]]) -> bool:
    return _assess_result_match(title=title, keyword=keyword, targets=targets)["identity_status"] != "failed"


def _provider_priority(item: OnlineSubtitleResult) -> int:
    if item.provider == "subhd":
        return 35
    if item.provider == "assrt":
        return 30
    if item.provider == "zimuku":
        return 25
    if item.provider == "opensubtitles":
        return 20
    return 0


def _identity_priority(item: OnlineSubtitleResult) -> int:
    if item.provider == "assrt" and not item.identity_status:
        return 30
    return {
        "strong": 30,
        "weak": 10,
        "failed": 0,
    }.get(item.identity_status or "", 0)


def _target_year_from_targets(targets: List[Dict[str, Any]]) -> int:
    for target in targets or []:
        for field in ["basename", "filename", "path", "title", "year"]:
            years = _extract_years(str(target.get(field) or ""))
            if years:
                return years[0]
    return 0


def _target_episode_from_targets(targets: List[Dict[str, Any]]) -> int:
    for target in targets or []:
        episode = _safe_int(target.get("episode"), 0)
        if episode:
            return episode
    return 0


def _first_target_value(targets: List[Dict[str, Any]], field: str) -> str:
    for target in targets or []:
        value = str(target.get(field) or "").strip()
        if value and value not in {"0", "None", "null"}:
            return value
    return ""


def _normalize_imdb_tt(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    match = re.search(r"tt\d{5,}", text)
    if match:
        return match.group(0)
    digits = re.sub(r"\D+", "", text)
    return f"tt{digits}" if digits else ""


def _normalize_imdb_for_opensubtitles(value: Any) -> str:
    imdb = _normalize_imdb_tt(value)
    return imdb[2:].lstrip("0") or "" if imdb else ""


def _strip_tags(value: str) -> str:
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", value or "", flags=re.I | re.S)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _extract_unique_matches(pattern: str, text: str) -> List[str]:
    result: List[str] = []
    seen = set()
    for match in re.finditer(pattern, text or "", flags=re.I | re.S):
        value = str(match.group(1) or "").strip()
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _episode_include_for_title(title: str, target_episode: int) -> Tuple[bool, bool]:
    if not target_episode:
        return True, False
    text = title or ""
    tag_re = re.compile(r"(?i)(S\d{1,2}\s*(?:E|EP)\d{1,3})|(\bEP?\d{1,3}\b)|(第\s*\d+\s*[集话話])")
    has_tag = bool(tag_re.search(text))
    tokens = [
        rf"(?i)\bS\d{{1,2}}\s*E0?{target_episode}\b",
        rf"(?i)\bE0?{target_episode}\b",
        rf"(?i)\bEP0?{target_episode}\b",
        rf"第\s*{target_episode}\s*[集话話]",
    ]
    matches = any(re.search(pattern, text) for pattern in tokens)
    return (not has_tag or matches), not has_tag


def _extract_download_hrefs(text: str) -> List[str]:
    hrefs: List[str] = []
    for link in _extract_links(text):
        href = html.unescape((link.href or "").strip())
        label = link.text or ""
        if not href or href.startswith("#") or href.lower().startswith("javascript:"):
            continue
        lowered = href.lower()
        if re.search(r"\.(zip|rar|7z|srt|ass|ssa|sub|vtt)(?:$|[?#])", lowered) or re.search(r"下载|download|电信|联通|移动", label, re.I):
            hrefs.append(href)
    return _unique_keywords(hrefs)


def _search_douban_subject(keyword: str, year: int, fetcher: OnlinePageClient) -> Dict[str, str]:
    query = re.sub(r"\bS\d{1,2}(?:E\d{1,3})?\b", "", keyword or "", flags=re.I).strip()
    if not query:
        return {}
    url = "https://search.douban.com/movie/subject_search?" + urlencode({"search_text": query, "cat": "1002"})
    try:
        status, text, _ = fetcher.get_text(url, referer="https://movie.douban.com/")
    except Exception as exc:
        logger.warning("[SubtitleManualUpload] 豆瓣兜底搜索失败 keyword=%s error=%s", query, exc)
        return {}
    if status >= 400 or not text:
        return {}
    candidates: List[Dict[str, str]] = []
    match = re.search(r"window\.__DATA__\s*=\s*({.+?});", text, re.S)
    if match:
        try:
            payload = json.loads(match.group(1))
            for item in payload.get("items") or []:
                if not isinstance(item, dict) or item.get("tpl_name") != "search_subject":
                    continue
                sid = str(item.get("id") or "").strip()
                title = _strip_tags(str(item.get("title") or ""))
                raw = " ".join(str(item.get(key) or "") for key in ("title", "abstract", "abstract_2"))
                years = _extract_years(raw)
                if sid:
                    candidates.append({"douban_id": sid, "title": title, "year": str(years[0]) if years else ""})
        except Exception:
            candidates = []
    if not candidates:
        for sid in _extract_unique_matches(r"movie\.douban\.com/subject/(\d+)", text):
            candidates.append({"douban_id": sid, "title": "", "year": ""})
    if year:
        for candidate in candidates:
            if str(year) == str(candidate.get("year") or ""):
                return candidate
    return candidates[0] if candidates else {}


def _fetch_douban_imdb_id(douban_id: str, fetcher: OnlinePageClient) -> str:
    douban_id = str(douban_id or "").strip()
    if not douban_id:
        return ""
    url = f"https://movie.douban.com/subject/{quote(douban_id)}/"
    try:
        status, text, _ = fetcher.get_text(url, referer="https://movie.douban.com/")
    except Exception as exc:
        logger.warning("[SubtitleManualUpload] 豆瓣 IMDb 解析失败 douban=%s error=%s", douban_id, exc)
        return ""
    if status >= 400 or not text:
        return ""
    match = re.search(r"IMDb:</span>\s*([^<\s]+)", text, re.I)
    return _normalize_imdb_tt(match.group(1)) if match else ""


def _years_from_opensubtitles_attrs(attrs: Dict[str, Any], file_info: Dict[str, Any], title: str) -> List[int]:
    values = [
        title,
        attrs.get("release"),
        attrs.get("movie_name"),
        attrs.get("feature_details"),
        file_info.get("file_name"),
    ]
    years: List[int] = []
    for value in values:
        if isinstance(value, dict):
            for key in ["year", "release_year"]:
                year = _safe_int(value.get(key), 0)
                if year:
                    years.append(year)
            value = " ".join(str(item or "") for item in value.values())
        years.extend(_extract_years(str(value or "")))
    return sorted(set(years))


def _years_from_file_info(file_info: Dict[str, Any]) -> List[int]:
    values = [
        file_info.get("file_name"),
        file_info.get("moviehash_match"),
        file_info.get("release"),
    ]
    years: List[int] = []
    for value in values:
        years.extend(_extract_years(str(value or "")))
    return sorted(set(years))


def _extract_years(value: str) -> List[int]:
    current_year = datetime.now().year + 1
    years = []
    for match in re.finditer(r"(?<!\d)(19\d{2}|20\d{2})(?!\d)", value or ""):
        year = int(match.group(1))
        if 1900 <= year <= current_year:
            years.append(year)
    return sorted(set(years))


def _year_from_upload_date(value: Any) -> int:
    match = re.match(r"\s*(19\d{2}|20\d{2})", str(value or ""))
    return int(match.group(1)) if match else 0


def _relevance_status(title: str, keyword: str, targets: List[Dict[str, Any]]) -> str:
    return _assess_result_match(title=title, keyword=keyword, targets=targets)["relevance_status"]


def _assess_result_match(
    *,
    title: str,
    keyword: str,
    targets: List[Dict[str, Any]],
    result_years: Optional[List[int]] = None,
    attrs: Optional[Dict[str, Any]] = None,
    file_info: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    attrs = attrs or {}
    file_info = file_info or {}
    haystack = " ".join(
        str(item or "")
        for item in [
            title,
            attrs.get("movie_name"),
            attrs.get("feature_details"),
            attrs.get("release"),
            file_info.get("file_name"),
        ]
    )
    score = 0
    reasons: List[str] = []
    reject_reason = ""
    year_reject_reason = ""
    title_matched = False
    metadata_matched = False
    file_title_matched = False

    target_aliases = _title_aliases({}, targets)
    keyword_parts = _keyword_match_parts(keyword)
    series_aliases = _series_title_aliases(targets)
    for alias in target_aliases:
        if _strong_title_matches(alias, haystack):
            title_matched = True
            score += 34
            reasons.append("标题别名命中")
            break
    if not title_matched:
        for part in keyword_parts:
            if _is_episode_only_keyword_part(part, keyword, targets):
                continue
            if _strong_title_matches(part, haystack):
                title_matched = True
                score += 18
                reasons.append("搜索词命中")
                break
    series_matched = any(_strong_title_matches(alias, haystack) for alias in series_aliases)
    file_name = str(file_info.get("file_name") or "")
    if file_name:
        file_title_matched = any(_strong_title_matches(alias, file_name) for alias in target_aliases)
        if file_title_matched and not title_matched:
            score += 28
            reasons.append("文件名标题命中")

    for target in targets or []:
        target_tmdb = str(target.get("tmdb_id") or "").strip()
        target_imdb = str(target.get("imdb_id") or "").strip().lower()
        text_values = json.dumps(attrs, ensure_ascii=False, default=str).lower()
        if target_imdb and target_imdb in text_values:
            metadata_matched = True
            score += 40
            reasons.append("IMDb 证据命中")
            break
        if target_tmdb and re.search(rf"(?<!\d){re.escape(target_tmdb)}(?!\d)", text_values):
            metadata_matched = True
            score += 40
            reasons.append("TMDB 证据命中")
            break

    target_year = _target_year_from_targets(targets)
    result_years = result_years if result_years is not None else _extract_years(haystack)
    if target_year and result_years:
        if target_year in result_years:
            score += 18
            reasons.append("年份一致")
        else:
            year_reject_reason = "年份冲突"
            reject_reason = year_reject_reason
    upload_year = _year_from_upload_date(attrs.get("upload_date") or attrs.get("uploaded_at"))
    if target_year and upload_year:
        if upload_year < target_year:
            year_reject_reason = year_reject_reason or "字幕上传时间早于资源年份"
            reject_reason = reject_reason or year_reject_reason
        else:
            reasons.append("上传年份可用")

    episode_ok = False
    episode_required = any(int(target.get("episode") or 0) for target in targets or [])
    hint = _episode_from_text(haystack)
    if hint:
        season, episode = hint
        for target in targets or []:
            target_season = int(target.get("season") or 0)
            target_episode = int(target.get("episode") or 0)
            if episode == target_episode and (not season or not target_season or season == target_season):
                episode_ok = True
                score += 22
                reasons.append("季集一致")
                break
    elif _season_matches_text(haystack, targets):
        episode_ok = True
        score += 10
        reasons.append("季一致")
    elif not episode_required:
        episode_ok = True

    media_type = next((str(target.get("media_type") or "") for target in targets or [] if target.get("media_type")), "")
    tv_identity_with_episode = (
        media_type == "tv"
        and episode_ok
        and (series_matched or title_matched or metadata_matched or file_title_matched)
    )
    if tv_identity_with_episode and reject_reason and reject_reason == year_reject_reason:
        reject_reason = ""
    if media_type == "tv" and not series_matched and not metadata_matched:
        title_matched = False
        reject_reason = reject_reason or "剧名身份不匹配"
    if media_type == "tv" and episode_required and not episode_ok:
        reject_reason = reject_reason or "季集不匹配"

    if _guess_language_label(title):
        score += 6

    identity_ok = title_matched or metadata_matched or file_title_matched
    if not identity_ok:
        reject_reason = reject_reason or "无标题或媒体身份信号"
    year_ok_for_strong = (
        not target_year
        or not result_years
        or target_year in result_years
        or tv_identity_with_episode
    )
    if reject_reason:
        identity_status = "failed"
    elif metadata_matched or (
        (title_matched or file_title_matched)
        and year_ok_for_strong
        and episode_ok
    ):
        identity_status = "strong"
    else:
        identity_status = "weak"
    return {
        "score": score,
        "identity_status": identity_status,
        "relevance_status": "matched" if identity_status == "strong" else ("weak" if identity_status == "weak" else "failed"),
        "reject_reason": reject_reason,
        "match_detail": " / ".join(_unique_keywords(reasons)) or reject_reason,
    }


def _is_cjk_text(value: str) -> bool:
    return bool(re.search(r"[\u3400-\u9fff]", value or ""))


def _series_title_aliases(targets: List[Dict[str, Any]]) -> List[str]:
    values: List[str] = []
    for target in targets or []:
        for field in ["title", "en_title", "original_title", "original_name", "title_en", "name_en", "english_title"]:
            value = _clean_title_alias(target.get(field))
            if value:
                values.append(value)
        for field in ["aliases", "alternative_titles", "translations", "tmdb_aliases"]:
            values.extend(_alias_values(target.get(field)))
    return _unique_keywords(values)


def _is_episode_only_keyword_part(part: str, keyword: str, targets: List[Dict[str, Any]]) -> bool:
    if re.fullmatch(r"(?i)s\d{1,2}e\d{1,3}|e\d{1,3}", part or ""):
        return True
    series_aliases = _series_title_aliases(targets)
    if any(_strong_title_matches(alias, part) for alias in series_aliases):
        return False
    return _is_cjk_text(part) and len(part) >= 3 and part in _normalize_title_for_match(keyword) and len(targets or []) == 1


def _season_matches_text(value: str, targets: List[Dict[str, Any]]) -> bool:
    seasons = {int(target.get("season") or 0) for target in targets or [] if int(target.get("season") or 0)}
    if not seasons:
        return False
    text = value or ""
    for season in seasons:
        if re.search(rf"(?i)\bS{season:02d}\b|\bS{season}\b|第\s*{season}\s*季", text):
            return True
    return False


def _keyword_match_parts(value: str) -> List[str]:
    stopwords = {"a", "an", "and", "of", "the", "to", "in", "on", "for", "with", "part"}
    parts: List[str] = []
    for raw in re.split(r"[\s._\-:：,，]+", (value or "").lower()):
        part = raw.strip()
        if not part:
            continue
        if _is_generic_language_alias(part):
            continue
        if re.fullmatch(r"(19\d{2}|20\d{2})", part):
            continue
        if _is_cjk_text(part):
            if len(part) >= 3:
                parts.append(part)
        elif len(part) >= 3 and part not in stopwords:
            parts.append(part)
    return parts


def _title_matches(needle: str, haystack: str) -> bool:
    clean_needle = _normalize_title_for_match(needle)
    clean_haystack = _normalize_title_for_match(haystack)
    if not clean_needle or not clean_haystack:
        return False
    if _is_cjk_text(clean_needle):
        if len(clean_needle) < 3:
            return False
        return clean_needle in clean_haystack or clean_haystack in clean_needle
    parts = [part for part in re.split(r"\s+", clean_needle.lower()) if len(part) >= 2]
    if not parts:
        return False
    haystack_lower = clean_haystack.lower()
    return all(part in haystack_lower for part in parts)


def _strong_title_matches(needle: str, haystack: str) -> bool:
    clean_needle = _normalize_title_for_match(needle)
    clean_haystack = _normalize_title_for_match(haystack)
    if not clean_needle or not clean_haystack:
        return False
    if _is_cjk_text(clean_needle):
        if len(clean_needle) < 3:
            return False
        return clean_needle in clean_haystack
    parts = [
        part
        for part in re.split(r"\s+", clean_needle.lower())
        if len(part) >= 3 and not re.fullmatch(r"(?:19\d{2}|20\d{2}|s\d{1,2}e\d{1,3}|s\d{1,2})", part)
    ]
    if not parts:
        return False
    matched = sum(1 for part in parts if re.search(rf"(?<![a-z0-9]){re.escape(part)}(?![a-z0-9])", clean_haystack.lower()))
    return matched == len(parts) if len(parts) <= 2 else matched >= max(2, len(parts) - 1)


def _normalize_title_for_match(value: Any) -> str:
    text = str(value or "").lower()
    text = re.sub(r"[\[\]【】()（）{}<>《》:：,，.!！?？'\"“”‘’._\-]+", " ", text)
    text = re.sub(r"\b(?:1080p|2160p|720p|bluray|web-dl|webrip|hdr|x264|x265|h264|h265)\b", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _dedupe_results(results: Iterable[OnlineSubtitleResult]) -> List[OnlineSubtitleResult]:
    deduped: List[OnlineSubtitleResult] = []
    seen = set()
    for item in results:
        key = (item.provider, item.result_id or item.page_url or item.title)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _extract_links(text: str) -> List[HtmlLink]:
    parser = LinkExtractor()
    try:
        parser.feed(text or "")
    except Exception:
        return []
    return parser.links


def _stable_result_id(provider: str, value: str) -> str:
    digest = base64.urlsafe_b64encode(value.encode("utf-8"))[:18].decode("ascii")
    return f"{provider}-{digest}"


def _clean_keyword(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace(".", " ")).strip()


def _clean_title_alias(value: Any) -> str:
    alias = _clean_keyword(value)
    if not alias or _is_generic_language_alias(alias):
        return ""
    if len(alias) > 80:
        return ""
    if re.search(r"https?://|www\.|。|！|？|；|……", alias, flags=re.IGNORECASE):
        return ""
    if _looks_english_title(alias):
        words = [
            item
            for item in re.split(r"\s+", _normalize_title_for_match(alias))
            if item and not re.fullmatch(r"(?:19\d{2}|20\d{2}|s\d{1,2}e\d{1,3}|s\d{1,2})", item)
        ]
        if len(words) == 1 and len(words[0]) < 2:
            return ""
    return alias


def _is_generic_language_alias(value: Any) -> bool:
    alias = _clean_keyword(value).lower()
    if not alias:
        return True
    normalized = _normalize_title_for_match(alias)
    if not normalized:
        return True
    if alias in GENERIC_TITLE_ALIAS_WORDS or alias in GENERIC_TITLE_ALIAS_CODES:
        return True
    tokens = [item for item in re.split(r"\s+", normalized) if item]
    if not tokens:
        return True
    generic_tokens = GENERIC_TITLE_ALIAS_WORDS | GENERIC_TITLE_ALIAS_CODES | {
        "audio",
        "dub",
        "dubbed",
        "forced",
        "hi",
        "sdh",
        "sub",
        "subs",
        "subtitle",
        "subtitles",
    }
    if all(item in generic_tokens for item in tokens):
        return True
    return len(tokens) == 1 and tokens[0].isalpha() and len(tokens[0]) < 2


def _unique_keywords(values: Iterable[str]) -> List[str]:
    result: List[str] = []
    seen = set()
    for value in values:
        normalized = value.strip()
        key = normalized.lower()
        if not normalized or key in seen:
            continue
        seen.add(key)
        result.append(normalized)
    return result[:8]


def _english_search_titles(media: Dict[str, Any], targets: List[Dict[str, Any]]) -> List[str]:
    values: List[str] = []
    for source in [media, *(targets or [])]:
        if not isinstance(source, dict):
            continue
        for field in ["en_title", "original_title", "original_name", "title_en", "name_en"]:
            value = _clean_title_alias(source.get(field))
            if value and not _is_cjk_text(value):
                values.append(value)
    return _unique_keywords(values)


def _can_import(module_name: str) -> bool:
    try:
        __import__(module_name)
        return True
    except Exception:
        return False


def _mp_browser_looks_configured() -> bool:
    if not _can_import("app.helper.browser"):
        return False
    return bool(getattr(settings, "BROWSER_EMULATION", None) or getattr(settings, "FLARESOLVERR_URL", None))


def _browser_proxy(use_proxy: bool) -> Optional[Any]:
    if not use_proxy:
        return None
    proxy_server = getattr(settings, "PROXY_SERVER", None)
    proxy = _playwright_proxy_from_value(proxy_server)
    if proxy:
        return proxy
    proxy_config = getattr(settings, "PROXY", None)
    proxy = _playwright_proxy_from_value(proxy_config)
    if proxy:
        return proxy
    return None


def _playwright_proxy_from_value(value: Any) -> Optional[Dict[str, str]]:
    if isinstance(value, dict):
        raw_server = value.get("server") or value.get("http") or value.get("https")
    else:
        raw_server = value
    server = str(raw_server or "").strip()
    if not server:
        return None
    parsed = urlparse(server)
    scheme = parsed.scheme.lower()
    if scheme == "socks5h":
        parsed = parsed._replace(scheme="socks5")
    normalized_server = urlunparse(parsed) if parsed.scheme else server
    if parsed.scheme and parsed.hostname:
        host = parsed.hostname
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"
        netloc = f"{host}:{parsed.port}" if parsed.port else host
        normalized_server = urlunparse((parsed.scheme, netloc, "", "", "", ""))
    proxy: Dict[str, str] = {"server": normalized_server}
    if parsed.username:
        proxy["username"] = unquote(parsed.username)
    if parsed.password:
        proxy["password"] = unquote(parsed.password)
    return proxy


def _host(url: str) -> str:
    return urlparse(str(url or "")).netloc or str(url or "")


def _decode_bytes(raw: bytes, charset: Optional[str]) -> str:
    if not raw:
        return ""
    candidates = [charset, "utf-8", "gb18030", "big5"]
    for encoding in [item for item in candidates if item]:
        try:
            return raw.decode(encoding)
        except Exception:
            continue
    return raw.decode("utf-8", errors="ignore")


def _looks_like_html_content(content: bytes, filename: str = "") -> bool:
    if Path(filename or "").suffix.lower() in {".zip", ".rar", ".7z", ".srt", ".ass", ".ssa", ".vtt", ".sub"}:
        return False
    head = _decode_bytes((content or b"")[:500], None).lstrip().lower()
    return head.startswith("<!doctype html") or head.startswith("<html") or "<body" in head


def _looks_like_captcha_page(text: str) -> bool:
    lowered = (text or "").lower()
    return any(token in lowered for token in ["captcha", "verify", "verification"]) or "验证码" in (text or "") or "验证" in (text or "")


def _first_nonempty_link_text(text: str, href_prefix: str = "") -> str:
    for link in _extract_links(text):
        if href_prefix and not (link.href or "").startswith(href_prefix):
            continue
        if link.text:
            return link.text
    return ""


def _format_network_error(url: str, exc: BaseException) -> str:
    host = _host(url) or "字幕站"
    reason = getattr(exc, "reason", exc)
    reason_text = str(reason or exc)
    lowered = reason_text.lower()
    if "unexpected_eof_while_reading" in lowered or "eof occurred in violation of protocol" in lowered:
        return f"{host} TLS 连接被提前断开，已重试仍失败；请检查代理、NAS 出口网络或稍后再试"
    if "connection reset" in lowered or "errno 104" in lowered or "远程主机强迫关闭" in reason_text:
        return f"{host} 连接被重置，可能是源站拦截、代理异常或容器网络出口受限"
    if "timed out" in lowered or "timeout" in lowered:
        return f"{host} 连接超时，请稍后重试或检查代理"
    if "name or service not known" in lowered or "nodename nor servname" in lowered:
        return f"{host} DNS 解析失败，请检查容器网络"
    return f"{host} 网络请求失败：{reason_text}"


def _is_retryable_network_error(exc: BaseException) -> bool:
    reason = getattr(exc, "reason", exc)
    text = str(reason or exc).lower()
    return any(
        token in text
        for token in [
            "unexpected_eof_while_reading",
            "eof occurred in violation of protocol",
            "connection reset",
            "timed out",
            "timeout",
            "temporarily unavailable",
        ]
    )


def _format_browser_error(url: str, exc: BaseException, *, engine: str) -> str:
    text = str(exc or "").strip()
    host = _host(url) or "字幕站"
    lowered = text.lower()
    if "net::err_connection_reset" in lowered or "connection reset" in lowered or "errno 104" in lowered:
        return f"{host} 浏览器访问被重置，可能是源站反爬、代理异常或网络出口受限"
    if "timeout" in lowered:
        return f"{host} 浏览器访问超时，请稍后重试或检查代理"
    return f"{engine} 访问 {host} 失败：{text[:120] or '未知错误'}"


def _compact_error_message(message: str) -> str:
    text = re.sub(r"\s+", " ", str(message or "")).strip()
    text = re.sub(r"^<urlopen error \[Errno 104\] Connection reset by peer>$", "连接被重置", text, flags=re.I)
    text = re.sub(r"^<urlopen error ([^>]+)>$", r"\1", text, flags=re.I)
    return text[:160] or "在线请求失败"


def _provider_error_summary(errors: List[str], keyword_count: int) -> str:
    summary = errors[0]
    if len(errors) > 1:
        summary += f"；另有 {len(errors) - 1} 类错误"
    if keyword_count > 1:
        summary += f"（已尝试 {keyword_count} 个关键词）"
    return summary


def _is_zimuku_security_page(text: str) -> bool:
    return "security_verify" in (text or "") or "网站防火墙" in (text or "")


def _clean_captcha_text(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z]", "", value or "")


def _preprocess_zimuku_captcha(image_b64: str) -> List[str]:
    try:
        from PIL import Image, ImageFilter

        image = Image.open(io.BytesIO(base64.b64decode(image_b64))).convert("RGB")
        scaled = image.resize((image.width * 3, image.height * 3), Image.Resampling.LANCZOS)
        mask = Image.new("L", scaled.size, 255)
        source = scaled.load()
        output = mask.load()
        for y in range(scaled.height):
            for x in range(scaled.width):
                r, g, b = source[x, y]
                # Zimuku's Yunsuo captcha uses green glyphs on a pale background.
                output[x, y] = 0 if (g > r + 20 and g > b + 20 and g < 190) else 255
        mask = mask.filter(ImageFilter.MedianFilter(3))
        buffer = io.BytesIO()
        mask.convert("RGB").save(buffer, format="PNG")
        return [base64.b64encode(buffer.getvalue()).decode()]
    except Exception as exc:
        logger.warning("[SubtitleManualUpload] Zimuku 验证码图片预处理失败：%s", exc)
        return []


def _string_to_hex(value: str) -> str:
    return "".join(f"{ord(char):x}" for char in value)


def _append_raw_query_param(url: str, key: str, value: str) -> str:
    separator = "&" if "?" in (url or "") else "?"
    return f"{url}{separator}{quote(str(key))}={quote(str(value))}"

# Keep internal helpers available to split provider modules.
__all__ = [name for name in globals() if not name.startswith("__")]
