from __future__ import annotations

import base64
import html
import json
import re
import urllib.error
import urllib.request
from http.cookiejar import Cookie, CookieJar
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import quote, unquote, urlencode, urljoin, urlparse

from app.core.config import settings
from app.log import logger


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
)


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

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
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
        }


@dataclass
class HtmlLink:
    href: str
    text: str


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


class OnlineFetchClient:
    def __init__(self, *, use_proxy: bool = True, timeout: int = 20):
        self.timeout = timeout
        self.cookiejar = CookieJar()
        self.default_headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        self.proxies = getattr(settings, "PROXY", None) if use_proxy else None
        handlers = [urllib.request.HTTPCookieProcessor(self.cookiejar)]
        if self.proxies:
            handlers.append(urllib.request.ProxyHandler(self.proxies))
        self.opener = urllib.request.build_opener(*handlers)

    def get_text(self, url: str, *, referer: str = "") -> Tuple[int, str, str]:
        headers = self._headers(referer)
        request = urllib.request.Request(url, headers=headers)
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                raw = response.read()
                return response.status, self._decode(raw, response.headers.get_content_charset()), response.geturl()
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            return exc.code, self._decode(raw, exc.headers.get_content_charset()), exc.geturl()
        except urllib.error.URLError as exc:
            raise ValueError(_format_network_error(url, exc)) from exc
        except OSError as exc:
            raise ValueError(_format_network_error(url, exc)) from exc

    def get_bytes(self, url: str, *, referer: str = "") -> Tuple[str, bytes, str]:
        headers = self._headers(referer)
        request = urllib.request.Request(url, headers=headers)
        try:
            with self.opener.open(request, timeout=max(self.timeout, 40)) as response:
                content = response.read()
                filename = self._filename_from_response(response.headers, response.geturl() or url)
                return filename, content, response.geturl()
        except urllib.error.HTTPError as exc:
            detail = self._decode(exc.read()[:300], exc.headers.get_content_charset())
            raise ValueError(f"下载失败 HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise ValueError(_format_network_error(url, exc)) from exc
        except OSError as exc:
            raise ValueError(_format_network_error(url, exc)) from exc

    def set_cookie(self, name: str, value: str, domain: str) -> None:
        cookie = Cookie(
            version=0,
            name=name,
            value=value,
            port=None,
            port_specified=False,
            domain=domain,
            domain_specified=True,
            domain_initial_dot=False,
            path="/",
            path_specified=True,
            secure=False,
            expires=None,
            discard=True,
            comment=None,
            comment_url=None,
            rest={},
            rfc2109=False,
        )
        self.cookiejar.set_cookie(cookie)

    def _headers(self, referer: str = "") -> Dict[str, str]:
        headers = dict(self.default_headers)
        if referer:
            headers["Referer"] = referer
        return headers

    @staticmethod
    def _decode(raw: bytes, charset: Optional[str]) -> str:
        if not raw:
            return ""
        candidates = [charset, "utf-8", "gb18030", "big5"]
        for encoding in [item for item in candidates if item]:
            try:
                return raw.decode(encoding)
            except Exception:
                continue
        return raw.decode("utf-8", errors="ignore")

    @staticmethod
    def _filename_from_response(headers: Any, url: str) -> str:
        disposition = headers.get("Content-Disposition", "")
        match = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)', disposition, re.I)
        if match:
            return unquote(match.group(1)).strip() or "subtitle.zip"
        name = Path(url).name
        return name or "subtitle.zip"


class BaseSubtitleProvider:
    provider_id = ""
    display_name = ""
    root_url = ""

    def __init__(self, fetcher: OnlineFetchClient):
        self.fetcher = fetcher

    def status(self) -> Dict[str, Any]:
        return {
            "id": self.provider_id,
            "name": self.display_name,
            "available": True,
            "message": "可用",
            "manual_only": False,
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
            self._host(final_url),
            len(content),
        )
        return filename or self._safe_download_name(result), content

    @staticmethod
    def _looks_like_html(content: bytes, filename: str = "") -> bool:
        suffix = Path(filename or "").suffix.lower()
        if suffix in {".zip", ".rar", ".srt", ".ass", ".ssa", ".sub", ".vtt", ".webvtt", ".sbv"}:
            return False
        head = content[:300].lstrip().lower()
        return head.startswith(b"<!doctype html") or head.startswith(b"<html") or b"<title>" in head

    @staticmethod
    def _host(url: str) -> str:
        return re.sub(r"^https?://([^/]+).*$", r"\1", str(url or ""))

    def _safe_download_name(self, result: Dict[str, Any]) -> str:
        title = re.sub(r"[\\/:*?\"<>|]+", " ", result.get("title") or "subtitle").strip()
        return f"{title or self.provider_id}.zip"


class SubhdProvider(BaseSubtitleProvider):
    provider_id = "subhd"
    display_name = "SubHD"
    root_url = "https://subhd.tv"

    def manual_url(self, keyword: str) -> str:
        return f"{self.root_url}/search/{quote(keyword)}"

    def search(self, keyword: str, targets: List[Dict[str, Any]], scope: str) -> List[OnlineSubtitleResult]:
        status, text, final_url = self.fetcher.get_text(self.manual_url(keyword))
        if status >= 400 or not text:
            raise ValueError(f"SubHD 搜索失败，HTTP {status}")
        detail_urls = self._collect_detail_urls(text)
        results: List[OnlineSubtitleResult] = []
        for detail_url in detail_urls[:8]:
            try:
                results.extend(self._parse_detail(detail_url, keyword, targets))
            except Exception as exc:
                logger.warning("[SubtitleManualUpload] SubHD 详情解析失败 url=%s error=%s", detail_url, exc)
        if not results:
            logger.info("[SubtitleManualUpload] SubHD 未解析到字幕条目 keyword=%s final=%s", keyword, final_url)
        return results[:40]

    def download(self, result: Dict[str, Any], captcha_code: str = "") -> Tuple[str, bytes]:
        page_url = result.get("page_url") or ""
        sid = result.get("result_id") or ""
        download_url = result.get("download_url") or (f"{self.root_url}/down/{sid}" if sid else "")
        if not download_url:
            raise ValueError("SubHD 没有可下载链接")
        filename, content, final_url = self.fetcher.get_bytes(download_url, referer=page_url)
        if self._looks_like_html(content, filename):
            if b"gzh" in content.lower() or "公众号".encode("utf-8") in content:
                raise ValueError("SubHD 需要公众号验证码，请打开手动搜索链接处理后再上传字幕包")
            raise ValueError("SubHD 返回网页而不是字幕文件，请尝试手动搜索")
        return filename or self._safe_download_name(result), content

    def _collect_detail_urls(self, text: str) -> List[str]:
        urls: List[str] = []
        for link in _extract_links(text):
            href = link.href
            if not href.startswith("/d/"):
                continue
            url = urljoin(self.root_url, href)
            if url not in urls:
                urls.append(url)
        return urls

    def _parse_detail(
        self,
        detail_url: str,
        keyword: str,
        targets: List[Dict[str, Any]],
    ) -> List[OnlineSubtitleResult]:
        status, text, _ = self.fetcher.get_text(detail_url, referer=self.root_url)
        if status >= 400 or not text:
            return []
        results: List[OnlineSubtitleResult] = []
        for link in _extract_links(text):
            if not link.href.startswith("/a/"):
                continue
            page_url = urljoin(self.root_url, link.href)
            sid = Path(page_url).name
            title = self._clean_text(link.text)
            if not sid or not title:
                continue
            season, episode = _episode_from_text(title) or (0, 0)
            results.append(
                OnlineSubtitleResult(
                    provider=self.provider_id,
                    result_id=sid,
                    title=title,
                    page_url=page_url,
                    download_url=f"{self.root_url}/down/{sid}",
                    language=_guess_language_label(title),
                    format=_guess_subtitle_format(title),
                    season=season,
                    episode=episode,
                    score=_score_result(title, keyword, targets),
                    source=self.display_name,
                    note="自动解析自 SubHD 详情页",
                )
            )
        return _dedupe_results(results)

    @staticmethod
    def _clean_text(value: str) -> str:
        return re.sub(r"\s+", " ", html.unescape(value or "")).strip()


class ZimukuProvider(BaseSubtitleProvider):
    provider_id = "zimuku"
    display_name = "Zimuku"
    root_url = "https://zimuku.org"

    def status(self) -> Dict[str, Any]:
        status = super().status()
        status["message"] = "可搜索；遇到网站防火墙会尝试 MoviePilot OCR"
        return status

    def manual_url(self, keyword: str) -> str:
        return f"{self.root_url}/search?q={quote(keyword)}"

    def search(self, keyword: str, targets: List[Dict[str, Any]], scope: str) -> List[OnlineSubtitleResult]:
        status, text, final_url = self.fetcher.get_text(self.manual_url(keyword))
        if _is_zimuku_security_page(text):
            text = self._solve_security_page(text, final_url)
        if status >= 400 and not text:
            raise ValueError(f"Zimuku 搜索失败，HTTP {status}")
        results = []
        for link in _extract_links(text):
            href = link.href
            if not any(pattern in href for pattern in ["/detail/", "/d/", "/sub/"]):
                continue
            title = re.sub(r"\s+", " ", link.text).strip()
            if not title or len(title) < 4:
                continue
            page_url = urljoin(self.root_url, href)
            season, episode = _episode_from_text(title) or (0, 0)
            result_id = _stable_result_id(self.provider_id, page_url)
            results.append(
                OnlineSubtitleResult(
                    provider=self.provider_id,
                    result_id=result_id,
                    title=title,
                    page_url=page_url,
                    download_url=page_url,
                    language=_guess_language_label(title),
                    format=_guess_subtitle_format(title),
                    season=season,
                    episode=episode,
                    score=_score_result(title, keyword, targets),
                    source=self.display_name,
                    note="Zimuku 搜索结果，下载失败时请使用手动搜索",
                    downloadable=False,
                )
            )
        return _dedupe_results(results)[:30]

    def download(self, result: Dict[str, Any], captcha_code: str = "") -> Tuple[str, bytes]:
        raise ValueError("Zimuku 下载入口存在动态校验，当前请使用手动搜索下载后再上传")

    def _solve_security_page(self, text: str, final_url: str) -> str:
        match = re.search(r"data:image/[a-zA-Z0-9.+-]+;base64,([^\"']+)", text)
        if not match:
            raise ValueError("Zimuku 触发防火墙，但未找到验证码图片")
        try:
            from app.helper.ocr import OcrHelper

            captcha = OcrHelper().get_captcha_text(image_b64=match.group(1))
        except Exception as exc:
            raise ValueError(f"Zimuku 防火墙验证码 OCR 失败: {exc}") from exc
        captcha = re.sub(r"\s+", "", captcha or "")
        if not captcha:
            raise ValueError("Zimuku 防火墙验证码 OCR 未返回结果")
        verify_value = _string_to_hex(captcha)
        self.fetcher.set_cookie("security_verify_img", verify_value, domain="zimuku.org")
        status, solved, _ = self.fetcher.get_text(final_url or self.root_url)
        if _is_zimuku_security_page(solved):
            raise ValueError(f"Zimuku 防火墙验证未通过，HTTP {status}")
        return solved


class AssrtProvider(BaseSubtitleProvider):
    provider_id = "assrt"
    display_name = "ASSRT"
    root_url = "https://2.assrt.net"
    api_root = "https://api.assrt.net/v1"

    def __init__(self, fetcher: OnlineFetchClient, token: str = ""):
        super().__init__(fetcher)
        self.token = (token or "").strip()

    def status(self) -> Dict[str, Any]:
        status = super().status()
        if self.token:
            status["message"] = "已配置 Token，将优先尝试 ASSRT API"
            status["manual_only"] = False
        else:
            status["message"] = "未配置 Token，匿名网页通常返回 402，将提供手动搜索链接"
            status["manual_only"] = True
        return status

    def manual_url(self, keyword: str) -> str:
        return f"{self.root_url}/sub/?searchword={quote(keyword)}"

    def search(self, keyword: str, targets: List[Dict[str, Any]], scope: str) -> List[OnlineSubtitleResult]:
        if self.token:
            return self._search_api(keyword, targets)
        status, text, _ = self.fetcher.get_text(self.manual_url(keyword))
        if status == 402:
            raise ValueError("ASSRT 匿名网页返回 402，已提供手动搜索链接；如需自动搜索可在设置中配置 ASSRT Token")
        if status >= 400:
            raise ValueError(f"ASSRT 搜索失败，HTTP {status}")
        results: List[OnlineSubtitleResult] = []
        for link in _extract_links(text):
            href = link.href
            title = re.sub(r"\s+", " ", link.text).strip()
            if not title or "sub" not in href.lower():
                continue
            page_url = urljoin(self.root_url, href)
            season, episode = _episode_from_text(title) or (0, 0)
            results.append(
                OnlineSubtitleResult(
                    provider=self.provider_id,
                    result_id=_stable_result_id(self.provider_id, page_url),
                    title=title,
                    page_url=page_url,
                    download_url=page_url,
                    language=_guess_language_label(title),
                    format=_guess_subtitle_format(title),
                    season=season,
                    episode=episode,
                    score=_score_result(title, keyword, targets),
                    source=self.display_name,
                    note="ASSRT 网页结果",
                    downloadable=False,
                )
            )
        return _dedupe_results(results)[:30]

    def download(self, result: Dict[str, Any], captcha_code: str = "") -> Tuple[str, bytes]:
        if not result.get("download_url"):
            raise ValueError("ASSRT 当前结果没有可下载链接，请使用手动搜索")
        return super().download(result, captcha_code=captcha_code)

    def _search_api(self, keyword: str, targets: List[Dict[str, Any]]) -> List[OnlineSubtitleResult]:
        query = urlencode({"q": keyword, "token": self.token})
        status, text, _ = self.fetcher.get_text(f"{self.api_root}/sub/search?{query}")
        if status >= 400:
            raise ValueError(f"ASSRT API 搜索失败，HTTP {status}")
        payload = json.loads(text or "{}")
        if payload.get("status") not in {0, "0", 200, "200", None} and payload.get("errmsg"):
            raise ValueError(payload.get("errmsg"))
        results: List[OnlineSubtitleResult] = []
        for item in payload.get("sub", {}).get("subs", []) or payload.get("subs", []) or []:
            title = item.get("videoname") or item.get("native_name") or item.get("filename") or "ASSRT 字幕"
            detail_url = item.get("url") or item.get("detail_url") or self.manual_url(keyword)
            download_url = item.get("download_url") or item.get("file_url") or ""
            season, episode = _episode_from_text(title) or (0, 0)
            results.append(
                OnlineSubtitleResult(
                    provider=self.provider_id,
                    result_id=str(item.get("id") or _stable_result_id(self.provider_id, detail_url + title)),
                    title=title,
                    page_url=detail_url,
                    download_url=download_url,
                    language=_guess_language_label(str(item) + title),
                    format=_guess_subtitle_format(str(item) + title),
                    season=season,
                    episode=episode,
                    score=_score_result(title, keyword, targets),
                    source=self.display_name,
                    note="ASSRT API 结果",
                )
            )
        return _dedupe_results(results)[:30]


class OnlineSubtitleSearchService:
    def __init__(self, *, assrt_token: str = "", use_proxy: bool = True):
        fetcher = OnlineFetchClient(use_proxy=use_proxy)
        self.providers: Dict[str, BaseSubtitleProvider] = {
            "subhd": SubhdProvider(fetcher),
            "zimuku": ZimukuProvider(fetcher),
            "assrt": AssrtProvider(fetcher, token=assrt_token),
        }

    def status(self) -> Dict[str, Any]:
        return {
            "providers": [provider.status() for provider in self.providers.values()],
            "capabilities": {
                "ocr": _can_import("app.helper.ocr"),
                "cloakbrowser": _can_import("cloakbrowser"),
                "proxy": bool(getattr(settings, "PROXY", None) or getattr(settings, "PROXY_SERVER", None)),
            },
        }

    def manual_links(self, keywords: List[str]) -> List[Dict[str, Any]]:
        links: List[Dict[str, Any]] = []
        for provider in self.providers.values():
            links.append(
                {
                    "provider": provider.provider_id,
                    "name": provider.display_name,
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
        provider_ids = [item for item in providers if item in self.providers] or list(self.providers.keys())
        results: List[OnlineSubtitleResult] = []
        provider_messages: List[Dict[str, str]] = []
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
                        "[SubtitleManualUpload] 在线字幕搜索失败 provider=%s keyword=%s error=%s",
                        provider_id,
                        keyword,
                        exc,
                    )
            logger.info(
                "[SubtitleManualUpload] 在线字幕源搜索完成 provider=%s keywords=%s results=%s",
                provider_id,
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
        results = _dedupe_results(results)
        results.sort(key=lambda item: (item.score, item.provider != "subhd", item.title), reverse=True)
        return {
            "results": [item.to_dict() for item in results[:80]],
            "messages": provider_messages,
        }

    def download(self, results: Iterable[Dict[str, Any]], captcha_code: str = "") -> List[Dict[str, Any]]:
        downloaded: List[Dict[str, Any]] = []
        for result in results:
            provider_id = result.get("provider")
            provider = self.providers.get(provider_id)
            if not provider:
                raise ValueError(f"未知字幕源: {provider_id}")
            filename, content = provider.download(result, captcha_code=captcha_code)
            downloaded.append(
                {
                    "provider": provider_id,
                    "source_name": filename,
                    "content": content,
                    "result": result,
                }
            )
        return downloaded


def build_search_keywords(media: Dict[str, Any], targets: List[Dict[str, Any]], scope: str) -> List[str]:
    title = _clean_keyword(media.get("title") or (targets[0].get("title") if targets else ""))
    year = _clean_keyword(media.get("year") or (targets[0].get("year") if targets else ""))
    media_type = media.get("media_type") or (targets[0].get("media_type") if targets else "")
    keywords: List[str] = []
    if media_type == "tv":
        seasons = sorted({int(target.get("season") or 0) for target in targets if int(target.get("season") or 0)})
        episodes = sorted({int(target.get("episode") or 0) for target in targets if int(target.get("episode") or 0)})
        if title and seasons:
            season = seasons[0]
            if scope in {"season", "batch"} or len(episodes) > 1:
                keywords.extend([f"{title} S{season:02d}", f"{title} 第{season}季"])
            elif episodes:
                episode = episodes[0]
                keywords.extend(
                    [
                        f"{title} S{season:02d}E{episode:02d}",
                        f"{title} 第{season}季 第{episode}集",
                    ]
                )
        for target in targets[:3]:
            basename = _clean_keyword(target.get("basename") or target.get("filename"))
            if basename:
                keywords.append(basename)
    elif title:
        if year:
            keywords.append(f"{title} {year}")
        keywords.append(title)
    return _unique_keywords([item for item in keywords if item])


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


def _guess_language_label(value: str) -> str:
    text = (value or "").lower()
    if any(key in text for key in ["简英", "中英", "双语", "chs&eng", "chi_eng", "zh&en"]):
        return "简英双语"
    if any(key in text for key in ["繁", "cht", "zh-hant"]):
        return "繁体中文"
    if any(key in text for key in ["简", "chs", "zh-hans", "中文", "chinese"]):
        return "简体中文"
    if any(key in text for key in ["eng", "english"]):
        return "英文"
    return ""


def _guess_subtitle_format(value: str) -> str:
    formats = []
    for ext in [".ass", ".srt", ".ssa", ".vtt", ".sub", ".zip", ".rar"]:
        if ext in (value or "").lower():
            formats.append(ext.removeprefix(".").upper())
    return " / ".join(formats)


def _score_result(title: str, keyword: str, targets: List[Dict[str, Any]]) -> int:
    haystack = (title or "").lower()
    score = 0
    for part in re.split(r"[\s._-]+", (keyword or "").lower()):
        if len(part) >= 2 and part in haystack:
            score += 5
    hint = _episode_from_text(title)
    if hint:
        season, episode = hint
        for target in targets:
            target_season = int(target.get("season") or 0)
            target_episode = int(target.get("episode") or 0)
            if episode == target_episode and (not season or not target_season or season == target_season):
                score += 30
                break
    if _guess_language_label(title):
        score += 10
    return score


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


def _can_import(module_name: str) -> bool:
    try:
        __import__(module_name)
        return True
    except Exception:
        return False


def _format_network_error(url: str, exc: BaseException) -> str:
    host = urlparse(url or "").netloc or "字幕站"
    reason = getattr(exc, "reason", exc)
    reason_text = str(reason or exc)
    lowered = reason_text.lower()
    if "connection reset" in lowered or "errno 104" in lowered or "远程主机强迫关闭" in reason_text:
        return f"{host} 连接被重置，可能是源站拦截、代理异常或容器网络出口受限"
    if "timed out" in lowered or "timeout" in lowered:
        return f"{host} 连接超时，请稍后重试或检查代理"
    if "name or service not known" in lowered or "nodename nor servname" in lowered:
        return f"{host} DNS 解析失败，请检查容器网络"
    return f"{host} 网络请求失败：{reason_text}"


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


def _string_to_hex(value: str) -> str:
    return "".join(f"{ord(char):x}" for char in value)
