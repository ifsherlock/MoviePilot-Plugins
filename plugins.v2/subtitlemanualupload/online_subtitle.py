from __future__ import annotations

import base64
import html
import io
import json
import re
import ssl
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
        raise ValueError("自动在线字幕搜索已移除页面仿真，请使用 API 搜索或右侧手动跳转")

    def get_bytes(self, url: str, *, referer: str = "") -> Tuple[str, bytes, str]:
        return OnlineDirectDownloader(use_proxy=self.use_proxy, timeout=self.timeout).get_bytes(url, referer=referer)

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


class BaseSubtitleProvider:
    provider_id = ""
    display_name = ""
    default_root_url = ""

    def __init__(self, fetcher: OnlinePageClient, root_url: str = ""):
        self.fetcher = fetcher
        self.root_url = normalize_root_url(root_url, self.default_root_url)

    def status(self) -> Dict[str, Any]:
        return {
            "id": self.provider_id,
            "name": self.display_name,
            "available": True,
            "message": "使用 API 自动搜索",
            "manual_only": False,
            "root_url": self.root_url,
            "host": _host(self.root_url),
        }

    def manual_url(self, keyword: str) -> str:
        raise NotImplementedError

    def search(self, keyword: str, targets: List[Dict[str, Any]], scope: str) -> List[OnlineSubtitleResult]:
        raise NotImplementedError

    def download(self, result: Dict[str, Any], captcha_code: str = "") -> Tuple[str, bytes]:
        download_url = result.get("download_url") or result.get("page_url")
        if not download_url:
            raise ValueError("没有可下载链接")
        filename, content, final_url = self.fetcher.get_bytes(download_url, referer=result.get("page_url") or "")
        if self._looks_like_html(content, filename):
            raise ValueError(f"{self.display_name} 返回了网页而不是字幕文件，请尝试手动搜索")
        logger.info(
            "[SubtitleManualUpload] 在线字幕下载完成 provider=%s final_host=%s size=%s",
            self.provider_id,
            _host(final_url),
            len(content),
        )
        return filename or self._safe_download_name(result), content

    @staticmethod
    def _looks_like_html(content: bytes, filename: str = "") -> bool:
        return _looks_like_html_bytes(content, filename)

    def _safe_download_name(self, result: Dict[str, Any]) -> str:
        title = re.sub(r"[\\/:*?\"<>|]+", " ", result.get("title") or "subtitle").strip()
        return f"{title or self.provider_id}.zip"


class ManualSubtitleProvider(BaseSubtitleProvider):
    def __init__(self, fetcher: OnlinePageClient, provider_id: str, display_name: str, root_url: str, url_builder):
        self.provider_id = provider_id
        self.display_name = display_name
        self.default_root_url = root_url
        self._url_builder = url_builder
        super().__init__(fetcher, root_url=root_url)

    def status(self) -> Dict[str, Any]:
        status = super().status()
        status["message"] = "仅保留手动跳转"
        status["manual_only"] = True
        return status

    def manual_url(self, keyword: str) -> str:
        return self._url_builder(self.root_url, keyword)

    def search(self, keyword: str, targets: List[Dict[str, Any]], scope: str) -> List[OnlineSubtitleResult]:
        raise ValueError(f"{self.display_name} 已移除自动搜索，请使用右侧手动跳转")

    def download(self, result: Dict[str, Any], captcha_code: str = "") -> Tuple[str, bytes]:
        raise ValueError(f"{self.display_name} 已移除自动下载，请手动下载字幕包后上传")



def _subhd_manual_url(root_url: str, keyword: str) -> str:
    return f"{root_url}/search/{quote(keyword)}"


def _zimuku_manual_url(root_url: str, keyword: str) -> str:
    return f"{root_url}/search?q={quote(keyword)}"

class AssrtProvider(BaseSubtitleProvider):
    provider_id = "assrt"
    display_name = "射手网(伪)"
    default_root_url = DEFAULT_PROVIDER_ROOTS["assrt"]

    def __init__(
        self,
        fetcher: OnlinePageClient,
        root_url: str = "",
        *,
        api_key: str = "",
        api_url: str = DEFAULT_ASSRT_API_URL,
    ):
        super().__init__(fetcher, root_url=root_url)
        self.api_key = str(api_key or "").strip()
        self.api_url = normalize_root_url(api_url, DEFAULT_ASSRT_API_URL)

    def status(self) -> Dict[str, Any]:
        status = super().status()
        status["api_configured"] = bool(self.api_key)
        status["api_host"] = _host(self.api_url)
        status["message"] = "已配置 API Key，使用官方 API 搜索" if self.api_key else "未配置 API Key；不参与自动搜索"
        return status

    def manual_url(self, keyword: str) -> str:
        return f"{self.root_url}/sub/?{urlencode({'searchword': keyword})}"

    def search(self, keyword: str, targets: List[Dict[str, Any]], scope: str) -> List[OnlineSubtitleResult]:
        if self.api_key:
            return self._search_api(keyword, targets)
        raise ValueError("射手网(伪) 未配置 API Key，已跳过自动搜索")

    def download(self, result: Dict[str, Any], captcha_code: str = "") -> Tuple[str, bytes]:
        result_id = str(result.get("result_id") or "").strip()
        download_url = str(result.get("download_url") or "").strip()
        if self.api_key and (result_id.isdigit() or download_url.startswith("assrt-api:")):
            return self._download_api(result_id or download_url.replace("assrt-api:", "", 1))
        page_url = result.get("page_url") or ""
        download_url = download_url or self._extract_download_url(page_url)
        if not download_url:
            raise ValueError("射手网(伪) 未找到可下载链接，请使用手动搜索")
        return super().download({**result, "download_url": download_url, "page_url": page_url}, captcha_code=captcha_code)

    def _search_api(self, keyword: str, targets: List[Dict[str, Any]]) -> List[OnlineSubtitleResult]:
        payload = self._api_json(
            "/v1/sub/search",
            {
                "q": keyword,
                "cnt": "15",
                "pos": "0",
                "is_file": "1",
                "no_muxer": "1",
                "filelist": "1",
            },
        )
        subs = self._extract_subs(payload)
        results: List[OnlineSubtitleResult] = []
        for item in subs:
            sid = str(item.get("id") or "").strip()
            if not sid:
                continue
            title = self._api_subtitle_title(item)
            if _looks_like_mojibake(
                " ".join(
                    str(item.get(key) or "")
                    for key in ("native_name", "title", "videoname", "filename", "desc")
                )
                or title
            ):
                logger.info("[SubtitleManualUpload] 丢弃 ASSRT 乱码字幕结果 id=%s", sid)
                continue
            language_text = " ".join([title, str(item.get("lang") or ""), str(item.get("desc") or "")])
            language_label = _guess_language_label(language_text)
            season, episode = _episode_from_text(title) or (0, 0)
            results.append(
                OnlineSubtitleResult(
                    provider=self.provider_id,
                    provider_label=self.display_name,
                    result_id=sid,
                    title=title,
                    page_url=self._detail_url(sid),
                    download_url=f"assrt-api:{sid}",
                    language=language_label,
                    language_category=_language_category_from_text(language_text or language_label),
                    format=_guess_subtitle_format(" ".join([title, str(item.get("subtype") or ""), str(item.get("filename") or "")])),
                    season=season,
                    episode=episode,
                    score=_score_result(title, keyword, targets) + 8,
                    source=self.display_name,
                    note="通过 ASSRT 官方 API 搜索",
                    downloadable=True,
                )
            )
        return _dedupe_results(results)[:30]

    def _detail_url(self, subtitle_id: str) -> str:
        sid = str(subtitle_id or "").strip()
        if sid.isdigit():
            return f"{self.root_url}/xml/sub/{int(sid) // 1000}/{sid}.xml"
        return f"{self.root_url}/sub/{quote(sid)}"

    def _download_api(self, subtitle_id: str) -> Tuple[str, bytes]:
        if not subtitle_id:
            raise ValueError("射手网(伪) API 缺少字幕 ID")
        payload = self._api_json("/v1/sub/detail", {"id": subtitle_id})
        subs = self._extract_subs(payload)
        detail = subs[0] if subs else {}
        download_url = str(detail.get("url") or "").strip()
        filename = str(detail.get("filename") or "").strip()
        filelist = detail.get("filelist") or []
        if isinstance(filelist, dict):
            filelist = [filelist]
        if not download_url and isinstance(filelist, list):
            for item in filelist:
                if not isinstance(item, dict):
                    continue
                download_url = str(item.get("url") or "").strip()
                filename = filename or str(item.get("f") or "").strip()
                if download_url:
                    break
        if not download_url:
            raise ValueError("射手网(伪) API 未返回可下载链接")
        name, content, final_url = OnlineDirectDownloader(use_proxy=self.fetcher.use_proxy).get_bytes(download_url)
        logger.info(
            "[SubtitleManualUpload] 射手网(伪) API 字幕下载完成 host=%s size=%s",
            _host(final_url),
            len(content),
        )
        return filename or name or f"assrt-{subtitle_id}.zip", content

    def _api_json(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        query = urlencode({key: value for key, value in params.items() if value not in {None, ""}})
        url = f"{self.api_url}{path}?{query}"
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        handlers = []
        proxies = getattr(settings, "PROXY", None) if self.fetcher.use_proxy else None
        if proxies:
            handlers.append(urllib.request.ProxyHandler(proxies))
        opener = urllib.request.build_opener(*handlers)
        try:
            request = urllib.request.Request(url, headers=headers)
            with opener.open(request, timeout=40) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            detail = _decode_bytes(exc.read()[:500], exc.headers.get_content_charset())
            raise ValueError(f"射手网(伪) API 请求失败 HTTP {exc.code}: {_compact_error_message(detail)}") from exc
        except urllib.error.URLError as exc:
            raise ValueError(_format_network_error(self.api_url, exc)) from exc
        except OSError as exc:
            raise ValueError(_format_network_error(self.api_url, exc)) from exc
        try:
            payload = json.loads(_decode_bytes(raw, None) or "{}")
        except Exception as exc:
            raise ValueError("射手网(伪) API 返回内容不是 JSON") from exc
        error = self._api_error_message(payload)
        if error:
            raise ValueError(error)
        return payload

    @staticmethod
    def _api_error_message(payload: Dict[str, Any]) -> str:
        status = payload.get("status")
        if status in {0, "0", None}:
            return ""
        message = (
            payload.get("message")
            or payload.get("msg")
            or payload.get("error")
            or payload.get("err")
            or payload.get("result")
            or "API 返回错误"
        )
        text = str(message)
        lowered = text.lower()
        if "invalid token" in lowered:
            return "射手网(伪) API Key 无效，请在插件设置中检查。"
        if "quota" in lowered or "limit" in lowered:
            return "射手网(伪) API 配额不足或请求过于频繁，请稍后再试。"
        return f"射手网(伪) API 返回错误: {text}"

    @staticmethod
    def _extract_subs(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        containers = [
            payload.get("sub") if isinstance(payload, dict) else None,
            payload,
        ]
        for container in containers:
            if not isinstance(container, dict):
                continue
            subs = container.get("subs") or container.get("sub")
            if isinstance(subs, list):
                return [item for item in subs if isinstance(item, dict)]
            if isinstance(subs, dict):
                return [subs]
        return []

    @staticmethod
    def _api_subtitle_title(item: Dict[str, Any]) -> str:
        for key in ("native_name", "title", "videoname", "filename"):
            value = re.sub(r"\s+", " ", html.unescape(str(item.get(key) or ""))).strip()
            if value:
                return value
        return f"射手网(伪) 字幕 {item.get('id') or ''}".strip()

    def _extract_download_url(self, page_url: str) -> str:
        if not page_url:
            return ""
        if self._looks_like_download_href(page_url):
            return page_url
        status, text, _ = self.fetcher.get_text(page_url, referer=self.root_url)
        if status >= 400 or not text:
            return ""
        candidates = []
        for link in _extract_links(text):
            href = (link.href or "").strip()
            if self._looks_like_download_href(href) or re.search(r"下载|download", link.text or "", re.I):
                candidates.append(urljoin(self.root_url, href))
        return candidates[0] if candidates else ""

    @staticmethod
    def _is_result_link(href: str, title: str) -> bool:
        if not href or href.startswith("#") or href.lower().startswith("javascript:"):
            return False
        if not title or len(title) < 3:
            return False
        lowered = href.lower()
        if "searchword=" in lowered:
            return False
        return "/sub/" in lowered or "/download" in lowered or "/down" in lowered

    @staticmethod
    def _looks_like_download_href(href: str) -> bool:
        lowered = (href or "").lower()
        return bool(
            re.search(r"\.(zip|rar|srt|ass|ssa|sub|vtt|webvtt)(?:$|[?#])", lowered)
            or "/download" in lowered
            or "/down" in lowered
        )


class OpenSubtitlesProvider(BaseSubtitleProvider):
    provider_id = "opensubtitles"
    display_name = "OpenSubtitles"
    default_root_url = DEFAULT_PROVIDER_ROOTS["opensubtitles"]

    def __init__(
        self,
        fetcher: OnlinePageClient,
        root_url: str = "",
        *,
        api_key: str = "",
        api_url: str = DEFAULT_OPENSUBTITLES_API_URL,
        username: str = "",
        password: str = "",
    ):
        super().__init__(fetcher, root_url=root_url)
        self.api_key = str(api_key or "").strip()
        self.api_url = normalize_root_url(api_url, DEFAULT_OPENSUBTITLES_API_URL)
        self.username = str(username or "").strip()
        self.password = str(password or "").strip()
        self._session_token = ""

    def status(self) -> Dict[str, Any]:
        status = super().status()
        status["api_configured"] = bool(self.api_key)
        status["api_host"] = _host(self.api_url)
        status["download_configured"] = bool(self.username and self.password)
        if self.api_key and status["download_configured"]:
            status["message"] = "已配置 API Key 和账号密码，可搜索并下载多语言字幕"
        elif self.api_key:
            status["message"] = "已配置 API Key，可搜索；下载需 OpenSubtitles 账号密码"
        else:
            status["message"] = "未配置 API Key；不参与自动搜索"
        return status

    def manual_url(self, keyword: str) -> str:
        return (
            f"{self.root_url}/en/en,zh-CN/search-all/q-{quote(keyword)}"
            "/hearing_impaired-include/machine_translated-/trusted_sources-"
        )

    def search(self, keyword: str, targets: List[Dict[str, Any]], scope: str) -> List[OnlineSubtitleResult]:
        if not self.api_key:
            raise ValueError("OpenSubtitles 未配置 API Key，已跳过自动搜索")
        target_year = _target_year_from_targets(targets)
        target_media_type = next((str(target.get("media_type") or "") for target in targets or [] if target.get("media_type")), "")
        strict_year_filter = target_media_type != "tv"
        query_plan = _query_plan_for_keyword(keyword, targets)
        payload = self._api_json(
            "/subtitles",
            {
                "query": keyword,
                "languages": OPENSUBTITLES_SEARCH_LANGUAGES,
                "order_by": "download_count",
                "order_direction": "desc",
            },
        )
        rows = payload.get("data") if isinstance(payload, dict) else []
        if not isinstance(rows, list):
            rows = []
        results: List[OnlineSubtitleResult] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            attrs = row.get("attributes") if isinstance(row.get("attributes"), dict) else {}
            files = attrs.get("files") if isinstance(attrs.get("files"), list) else []
            file_info = next((item for item in files if isinstance(item, dict) and item.get("file_id")), None)
            if not file_info:
                continue
            title = self._subtitle_title(attrs, file_info)
            language_code = str(attrs.get("language") or attrs.get("languages") or "").strip()
            language_text = " ".join(
                [
                    language_code,
                    str(attrs.get("language_name") or ""),
                    title,
                    str(file_info.get("file_name") or ""),
                ]
            )
            language_category = _language_category_from_text(language_text)
            language_label = _language_label_from_category(language_category, language_code)
            season, episode = _episode_from_text(title) or (0, 0)
            file_id = str(file_info.get("file_id") or "").strip()
            result_years = _years_from_opensubtitles_attrs(attrs, file_info, title)
            file_years = _years_from_file_info(file_info)
            if strict_year_filter and target_year and result_years and target_year not in result_years:
                continue
            if strict_year_filter and target_year and file_years and target_year not in file_years:
                continue
            upload_year = _year_from_upload_date(attrs.get("upload_date") or attrs.get("uploaded_at"))
            if strict_year_filter and target_year and upload_year and upload_year < target_year:
                continue
            assessment = _assess_result_match(
                title=title,
                keyword=keyword,
                targets=targets,
                result_years=result_years,
                attrs=attrs,
                file_info=file_info,
            )
            if assessment["identity_status"] == "failed":
                continue
            results.append(
                OnlineSubtitleResult(
                    provider=self.provider_id,
                    provider_label=self.display_name,
                    result_id=file_id,
                    title=title,
                    page_url=str(attrs.get("url") or self.manual_url(keyword)),
                    download_url=f"opensubtitles-api:{file_id}",
                    language=language_label,
                    language_category=language_category,
                    format=_guess_subtitle_format(" ".join([title, str(file_info.get("file_name") or "")])),
                    season=season or _safe_int(attrs.get("season_number"), 0),
                    episode=episode or _safe_int(attrs.get("episode_number"), 0),
                    score=assessment["score"] + 6 + (12 if target_year and target_year in result_years else 0),
                    source=self.display_name,
                    note=f"通过 OpenSubtitles API 搜索{language_label}字幕",
                    downloadable=True,
                    result_years=result_years,
                    match_year=target_year if target_year and target_year in result_years else 0,
                    relevance_status=assessment["relevance_status"],
                    region_bucket=query_plan["region_bucket"],
                    query_plan=query_plan["label"],
                    identity_status=assessment["identity_status"],
                    reject_reason=assessment["reject_reason"],
                    match_detail=assessment["match_detail"],
                )
            )
        return _dedupe_results(results)[:30]

    def download(self, result: Dict[str, Any], captcha_code: str = "") -> Tuple[str, bytes]:
        result_id = str(result.get("result_id") or "").strip()
        download_url = str(result.get("download_url") or "").strip()
        if download_url.startswith("opensubtitles-api:"):
            result_id = download_url.replace("opensubtitles-api:", "", 1)
        if not result_id:
            raise ValueError("OpenSubtitles 缺少 file_id")
        token = self._auth_token()
        payload = self._api_json("/download", {"file_id": result_id}, method="POST", token=token)
        file_url = str(payload.get("link") or "").strip()
        filename = str(payload.get("file_name") or payload.get("filename") or "").strip()
        if not file_url:
            raise ValueError("OpenSubtitles API 未返回下载链接")
        name, content, final_url = OnlineDirectDownloader(use_proxy=self.fetcher.use_proxy).get_bytes(file_url)
        logger.info(
            "[SubtitleManualUpload] OpenSubtitles API 字幕下载完成 host=%s size=%s",
            _host(final_url),
            len(content),
        )
        return filename or name or f"opensubtitles-{result_id}.srt", content

    def _auth_token(self) -> str:
        if self._session_token:
            return self._session_token
        if not self.username or not self.password:
            raise ValueError("OpenSubtitles 下载需要在插件设置中填写 OpenSubtitles 用户名和密码")
        payload = self._api_json(
            "/login",
            {"username": self.username, "password": self.password},
            method="POST",
            allow_without_token=True,
        )
        token = str(payload.get("token") or "").strip()
        if not token:
            raise ValueError("OpenSubtitles 登录未返回 token")
        self._session_token = token
        return token

    def _api_json(
        self,
        path: str,
        params: Dict[str, Any],
        *,
        method: str = "GET",
        token: str = "",
        allow_without_token: bool = False,
    ) -> Dict[str, Any]:
        url = f"{self.api_url}{path}"
        data = None
        headers = {
            "Api-Key": self.api_key,
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        elif method.upper() == "POST" and not allow_without_token and path != "/login":
            raise ValueError("OpenSubtitles 下载接口缺少登录认证 token")
        if method.upper() == "GET":
            query = urlencode({key: value for key, value in params.items() if value not in {None, ""}})
            if query:
                url = f"{url}?{query}"
        else:
            data = json.dumps({key: value for key, value in params.items() if value not in {None, ""}}).encode("utf-8")
        handlers = []
        proxies = getattr(settings, "PROXY", None) if self.fetcher.use_proxy else None
        if proxies:
            handlers.append(urllib.request.ProxyHandler(proxies))
        opener = urllib.request.build_opener(*handlers)
        last_error: Optional[Exception] = None
        raw = b""
        for attempt in range(3):
            try:
                request = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
                with opener.open(request, timeout=40) as response:
                    raw = response.read()
                break
            except urllib.error.HTTPError as exc:
                detail = _decode_bytes(exc.read()[:500], exc.headers.get_content_charset())
                raise ValueError(f"OpenSubtitles API 请求失败 HTTP {exc.code}: {_compact_error_message(detail)}") from exc
            except (urllib.error.URLError, OSError, ssl.SSLError) as exc:
                last_error = exc
                if attempt < 2 and _is_retryable_network_error(exc):
                    time.sleep(0.5 * (2 ** attempt))
                    continue
                break
        if not raw and last_error:
            raise ValueError(_format_network_error(self.api_url, last_error)) from last_error
        try:
            payload = json.loads(_decode_bytes(raw, None) or "{}")
        except Exception as exc:
            raise ValueError("OpenSubtitles API 返回内容不是 JSON") from exc
        if isinstance(payload, dict) and payload.get("message") and payload.get("status") not in {200, "200", None}:
            raise ValueError(f"OpenSubtitles API 返回错误: {payload.get('message')}")
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _subtitle_title(attrs: Dict[str, Any], file_info: Dict[str, Any]) -> str:
        for key in ("release", "feature_details", "url"):
            value = attrs.get(key)
            if isinstance(value, dict):
                for subkey in ("title", "movie_name", "name"):
                    text = re.sub(r"\s+", " ", html.unescape(str(value.get(subkey) or ""))).strip()
                    if text:
                        return text
            else:
                text = re.sub(r"\s+", " ", html.unescape(str(value or ""))).strip()
                if text and not text.startswith("http"):
                    return text
        for key in ("file_name", "cd_number"):
            text = re.sub(r"\s+", " ", html.unescape(str(file_info.get(key) or ""))).strip()
            if text:
                return text
        return "OpenSubtitles Subtitle"


class OnlineSubtitleSearchService:
    def __init__(
        self,
        *,
        engine: str = DEFAULT_ENGINE,
        use_proxy: bool = False,
        provider_roots: Optional[Dict[str, str]] = None,
        assrt_api_key: str = "",
        assrt_api_url: str = DEFAULT_ASSRT_API_URL,
        opensubtitles_api_key: str = "",
        opensubtitles_api_url: str = DEFAULT_OPENSUBTITLES_API_URL,
        opensubtitles_username: str = "",
        opensubtitles_password: str = "",
    ):
        self.fetcher = OnlinePageClient(engine=engine, use_proxy=use_proxy)
        roots = normalize_provider_roots(provider_roots)
        self.providers: Dict[str, BaseSubtitleProvider] = {
            "assrt": AssrtProvider(
                self.fetcher,
                root_url=roots["assrt"],
                api_key=assrt_api_key,
                api_url=assrt_api_url,
            ),
            "opensubtitles": OpenSubtitlesProvider(
                self.fetcher,
                root_url=roots["opensubtitles"],
                api_key=opensubtitles_api_key,
                api_url=opensubtitles_api_url,
                username=opensubtitles_username,
                password=opensubtitles_password,
            ),
        }
        self.manual_providers: Dict[str, BaseSubtitleProvider] = {
            "subhd": ManualSubtitleProvider(self.fetcher, "subhd", "SubHD", roots["subhd"], _subhd_manual_url),
            "zimuku": ManualSubtitleProvider(self.fetcher, "zimuku", "Zimuku", roots["zimuku"], _zimuku_manual_url),
            "assrt": self.providers["assrt"],
            "opensubtitles": self.providers["opensubtitles"],
        }

    def status(self) -> Dict[str, Any]:
        browser_status = self.fetcher.status()
        return {
            "engine": browser_status["engine"],
            "engine_name": browser_status["engine_name"],
            "providers": [provider.status() for provider in self.providers.values()],
            "manual_providers": [provider.status() for provider in self.manual_providers.values()],
            "capabilities": {
                "ocr": _can_import("app.helper.ocr"),
                "cloakbrowser": browser_status["cloakbrowser"],
                "mp_browser": browser_status["mp_browser"],
                "flaresolverr": _mp_browser_looks_configured(),
                "proxy": browser_status["proxy"],
            },
            "engine_available": browser_status["available"],
        }

    def manual_links(self, keywords: List[str], providers: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        links: List[Dict[str, Any]] = []
        provider_ids = list(self.manual_providers.keys()) if providers is None else [item for item in providers if item in self.manual_providers]
        for provider_id in provider_ids:
            provider = self.manual_providers[provider_id]
            links.append(
                {
                    "provider": provider.provider_id,
                    "name": provider.display_name,
                    "root_url": provider.root_url,
                    "host": _host(provider.root_url),
                    "links": [
                        {
                            "keyword": keyword,
                            "url": provider.manual_url(keyword),
                        }
                        for keyword in keywords
                    ],
                }
            )
        return links

    def search(
        self,
        *,
        keywords: List[str],
        providers: List[str],
        targets: List[Dict[str, Any]],
        scope: str,
    ) -> Dict[str, Any]:
        provider_ids = [item for item in providers if item in self.providers]
        if not provider_ids:
            return {
                "results": [],
                "messages": [
                    {
                        "provider": "providers",
                        "level": "info",
                        "message": "未启用在线字幕源，请至少选择一个来源或使用手动上传。",
                    }
                ],
            }
        results: List[OnlineSubtitleResult] = []
        provider_messages: List[Dict[str, str]] = []
        try:
            for provider_id in provider_ids:
                provider = self.providers[provider_id]
                provider_count = 0
                provider_errors: List[str] = []
                for keyword in keywords:
                    try:
                        found = provider.search(keyword, targets, scope)
                        provider_count += len(found)
                        results.extend(found)
                        if found:
                            break
                    except Exception as exc:
                        message = _compact_error_message(str(exc))
                        if message not in provider_errors:
                            provider_errors.append(message)
                        logger.warning(
                            "[SubtitleManualUpload] 在线字幕搜索失败 provider=%s keyword_count=%s host=%s error=%s",
                            provider_id,
                            len(keywords),
                            _host(provider.root_url),
                            exc,
                        )
                logger.info(
                    "[SubtitleManualUpload] 在线字幕源搜索完成 provider=%s host=%s keywords=%s results=%s",
                    provider_id,
                    _host(provider.root_url),
                    len(keywords),
                    provider_count,
                )
                if provider_count == 0 and provider_errors:
                    provider_messages.append(
                        {
                            "provider": provider_id,
                            "level": "warning",
                            "message": _provider_error_summary(provider_errors, len(keywords)),
                        }
                    )
        finally:
            self.fetcher.close()
        results = _dedupe_results(results)
        results.sort(
            key=lambda item: (
                _provider_priority(item),
                _identity_priority(item),
                _language_priority(item),
                item.score,
                item.title,
            ),
            reverse=True,
        )
        return {
            "results": [item.to_dict() for item in results[:80]],
            "messages": provider_messages,
        }

    def download(self, results: Iterable[Dict[str, Any]], captcha_code: str = "") -> List[Dict[str, Any]]:
        downloaded: List[Dict[str, Any]] = []
        try:
            for result in results:
                provider_id = result.get("provider")
                provider = self.providers.get(provider_id)
                if not provider:
                    raise ValueError(f"未知字幕源 {provider_id}")
                filename, content = provider.download(result, captcha_code=captcha_code)
                downloaded.append(
                    {
                        "provider": provider_id,
                        "source_name": filename,
                        "content": content,
                        "result": result,
                    }
                )
        finally:
            self.fetcher.close()
        return downloaded


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
            primary_title = search_titles[0]
            if scope in {"season", "batch"} or len(episodes) > 1:
                for item in search_titles[:4]:
                    keywords.append(f"{item} S{season:02d}")
                keywords.append(f"{primary_title} 第{season}季")
            elif episodes:
                episode = episodes[0]
                for item in search_titles[:4]:
                    keywords.append(f"{item} S{season:02d}E{episode:02d}")
                keywords.append(f"{primary_title} 第{season}季第{episode}集")
        for target in targets[:3]:
            basename = _clean_keyword(target.get("basename") or target.get("filename"))
            if basename:
                keywords.append(basename)
    elif search_titles:
        if year:
            keywords.extend([f"{item} {year}" for item in search_titles[:5]])
        keywords.extend(search_titles[:5])
    return _unique_keywords([item for item in keywords if item])


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
    if item.provider == "assrt":
        return 30
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
