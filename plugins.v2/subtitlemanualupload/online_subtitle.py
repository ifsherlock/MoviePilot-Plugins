from __future__ import annotations

import base64
import html
import io
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
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


class OnlinePageClient:
    def __init__(self, *, engine: str = DEFAULT_ENGINE, use_proxy: bool = False, timeout: int = 60):
        self.engine = normalize_online_engine(engine)
        self.use_proxy = use_proxy
        self.timeout = timeout
        self._context = None
        self._playwright_helper = None

    def status(self) -> Dict[str, Any]:
        return {
            "engine": self.engine,
            "engine_name": "CloakBrowser" if self.engine == DEFAULT_ENGINE else "MoviePilot 浏览器仿真/FlareSolverr",
            "available": self.available(),
            "cloakbrowser": _can_import("cloakbrowser"),
            "mp_browser": _can_import("app.helper.browser"),
            "proxy": bool(getattr(settings, "PROXY", None) or getattr(settings, "PROXY_SERVER", None)),
        }

    def available(self) -> bool:
        if self.engine == DEFAULT_ENGINE:
            return _can_import("cloakbrowser")
        return _mp_browser_looks_configured()

    def get_text(self, url: str, *, referer: str = "") -> Tuple[int, str, str]:
        if self.engine == DEFAULT_ENGINE:
            return self._get_text_with_cloakbrowser(url, referer=referer)
        return self._get_text_with_mp_browser(url, referer=referer)

    def get_bytes(self, url: str, *, referer: str = "") -> Tuple[str, bytes, str]:
        if self.engine == DEFAULT_ENGINE and referer:
            try:
                self.get_text(referer)
            except Exception as exc:
                logger.warning(
                    "[SubtitleManualUpload] 在线字幕下载前预热详情页失败 host=%s error=%s",
                    _host(referer),
                    exc,
                )
        return OnlineDirectDownloader(use_proxy=self.use_proxy, cookies=self._cookie_header(url)).get_bytes(
            url,
            referer=referer,
        )

    def set_cookie(self, name: str, value: str, domain: str) -> None:
        if self.engine != DEFAULT_ENGINE:
            return
        context = self._ensure_context()
        try:
            context.add_cookies(
                [
                    {
                        "name": name,
                        "value": value,
                        "domain": domain,
                        "path": "/",
                        "httpOnly": False,
                        "secure": False,
                    }
                ]
            )
        except Exception as exc:
            logger.warning("[SubtitleManualUpload] 设置浏览器 Cookie 失败 domain=%s error=%s", domain, exc)

    def close(self) -> None:
        if not self._context:
            return
        try:
            self._context.close()
        except Exception:
            pass
        finally:
            self._context = None

    def _get_text_with_cloakbrowser(self, url: str, *, referer: str = "") -> Tuple[int, str, str]:
        if not _can_import("cloakbrowser"):
            raise ValueError("CloakBrowser 不可用，请确认 MoviePilot 已准备浏览器运行环境")
        context = self._ensure_context()
        page = None
        try:
            page = context.new_page()
            headers = {"User-Agent": USER_AGENT}
            if referer:
                headers["Referer"] = referer
            page.set_extra_http_headers(headers)
            response = page.goto(url, wait_until="domcontentloaded", timeout=self.timeout * 1000)
            try:
                page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass
            status = int(getattr(response, "status", 200) or 200)
            return status, page.content() or "", getattr(page, "url", url) or url
        except Exception as exc:
            raise ValueError(_format_browser_error(url, exc, engine="CloakBrowser")) from exc
        finally:
            if page:
                try:
                    page.close()
                except Exception:
                    pass

    def _get_text_with_mp_browser(self, url: str, *, referer: str = "") -> Tuple[int, str, str]:
        try:
            from app.helper.browser import PlaywrightHelper
        except Exception as exc:
            raise ValueError("MoviePilot 浏览器仿真不可用，请先在系统设置中配置 Playwright/FlareSolverr") from exc
        try:
            if not self._playwright_helper:
                self._playwright_helper = PlaywrightHelper()
            text = self._playwright_helper.get_page_source(
                url=url,
                cookies=None,
                proxies=getattr(settings, "PROXY_SERVER", None) if self.use_proxy else None,
                timeout=self.timeout,
            )
            if not text:
                raise ValueError("未获取到页面内容")
            return 200, text, url
        except Exception as exc:
            raise ValueError(_format_browser_error(url, exc, engine="MoviePilot 浏览器仿真")) from exc

    def _ensure_context(self):
        if self._context:
            return self._context
        from cloakbrowser import launch_context

        self._context = launch_context(headless=True, proxy=_browser_proxy(self.use_proxy))
        return self._context

    def _cookie_header(self, url: str) -> str:
        if self.engine != DEFAULT_ENGINE or not self._context:
            return ""
        try:
            cookies = self._context.cookies([url])
        except Exception:
            return ""
        pairs = []
        for item in cookies or []:
            name = str(item.get("name") or "").strip()
            value = str(item.get("value") or "")
            if name:
                pairs.append(f"{name}={value}")
        return "; ".join(pairs)


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
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                content = response.read()
                filename = self._filename_from_response(response.headers, response.geturl() or url)
                return filename, content, response.geturl()
        except urllib.error.HTTPError as exc:
            detail = _decode_bytes(exc.read()[:300], exc.headers.get_content_charset())
            raise ValueError(f"下载失败 HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise ValueError(_format_network_error(url, exc)) from exc
        except OSError as exc:
            raise ValueError(_format_network_error(url, exc)) from exc

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
    default_root_url = ""

    def __init__(self, fetcher: OnlinePageClient, root_url: str = ""):
        self.fetcher = fetcher
        self.root_url = normalize_root_url(root_url, self.default_root_url)

    def status(self) -> Dict[str, Any]:
        return {
            "id": self.provider_id,
            "name": self.display_name,
            "available": True,
            "message": "使用浏览器仿真搜索",
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
        suffix = Path(filename or "").suffix.lower()
        if suffix in {".zip", ".rar", ".srt", ".ass", ".ssa", ".sub", ".vtt", ".webvtt", ".sbv"}:
            return False
        head = content[:300].lstrip().lower()
        return head.startswith(b"<!doctype html") or head.startswith(b"<html") or b"<title>" in head

    def _safe_download_name(self, result: Dict[str, Any]) -> str:
        title = re.sub(r"[\\/:*?\"<>|]+", " ", result.get("title") or "subtitle").strip()
        return f"{title or self.provider_id}.zip"


class SubhdProvider(BaseSubtitleProvider):
    provider_id = "subhd"
    display_name = "SubHD"
    default_root_url = DEFAULT_PROVIDER_ROOTS["subhd"]

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
                logger.warning(
                    "[SubtitleManualUpload] SubHD 详情解析失败 host=%s error=%s",
                    _host(detail_url),
                    exc,
                )
        if not results:
            logger.info("[SubtitleManualUpload] SubHD 未解析到字幕条目 final_host=%s", _host(final_url))
        return results[:40]

    def download(self, result: Dict[str, Any], captcha_code: str = "") -> Tuple[str, bytes]:
        page_url = result.get("page_url") or ""
        sid = result.get("result_id") or ""
        download_url = result.get("download_url") or (f"{self.root_url}/down/{sid}" if sid else "")
        if not download_url:
            raise ValueError("SubHD 没有可下载链接")
        filename, content, final_url = self.fetcher.get_bytes(download_url, referer=page_url)
        if self._looks_like_html(content, filename):
            lowered = content.lower()
            if b"gzh" in lowered or "公众号".encode("utf-8") in content:
                raise ValueError("SubHD 需要公众号验证码，请打开手动搜索链接处理后再上传字幕包")
            raise ValueError("SubHD 返回网页而不是字幕文件，请尝试手动搜索")
        logger.info(
            "[SubtitleManualUpload] SubHD 在线字幕下载完成 final_host=%s size=%s",
            _host(final_url),
            len(content),
        )
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
    default_root_url = DEFAULT_PROVIDER_ROOTS["zimuku"]

    def status(self) -> Dict[str, Any]:
        status = super().status()
        status["message"] = "使用浏览器仿真搜索；遇到网站防火墙会尝试 MoviePilot OCR"
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
        current_text = text
        current_url = final_url or self.root_url
        domain = urlparse(self.root_url).hostname or "zimuku.org"
        last_error = "OCR 未返回结果"
        for attempt in range(1, 4):
            captcha = self._recognize_security_captcha(current_text)
            if not captcha:
                last_error = "OCR 未返回结果"
                logger.warning(
                    "[SubtitleManualUpload] Zimuku 防火墙验证码 OCR 未返回结果 host=%s attempt=%s",
                    _host(self.root_url),
                    attempt,
                )
            else:
                logger.info(
                    "[SubtitleManualUpload] Zimuku 防火墙验证码 OCR 完成 host=%s attempt=%s length=%s",
                    _host(self.root_url),
                    attempt,
                    len(captcha),
                )
                self.fetcher.set_cookie("srcurl", _string_to_hex(current_url), domain=domain)
                verify_url = urljoin(self.root_url, f"/?security_verify_img={_string_to_hex(captcha)}")
                status, _, verify_final_url = self.fetcher.get_text(verify_url, referer=current_url)
                status, solved, _ = self.fetcher.get_text(current_url, referer=verify_final_url or verify_url)
                if not _is_zimuku_security_page(solved):
                    return solved
                last_error = f"验证码未通过，HTTP {status}"
                logger.warning(
                    "[SubtitleManualUpload] Zimuku 防火墙验证码未通过 host=%s attempt=%s http=%s",
                    _host(self.root_url),
                    attempt,
                    status,
                )
            status, current_text, current_url = self.fetcher.get_text(current_url or self.root_url)
            if not _is_zimuku_security_page(current_text):
                return current_text
        raise ValueError(f"Zimuku 防火墙验证码验证失败: {last_error}")

    @staticmethod
    def _recognize_security_captcha(text: str) -> str:
        match = re.search(r"data:image/[a-zA-Z0-9.+-]+;base64,([^\"']+)", text)
        if not match:
            raise ValueError("Zimuku 触发防火墙，但未找到验证码图片")
        image_b64 = match.group(1)
        try:
            from app.helper.ocr import OcrHelper

            helper = OcrHelper()
            candidates = [image_b64]
            candidates.extend(_preprocess_zimuku_captcha(image_b64))
            for candidate in candidates:
                captcha = _clean_captcha_text(helper.get_captcha_text(image_b64=candidate))
                if len(captcha) >= 4:
                    return captcha
            return ""
        except Exception as exc:
            raise ValueError(f"Zimuku 防火墙验证码 OCR 失败: {exc}") from exc


class AssrtProvider(BaseSubtitleProvider):
    provider_id = "assrt"
    display_name = "射手网(伪)"
    default_root_url = DEFAULT_PROVIDER_ROOTS["assrt"]

    def status(self) -> Dict[str, Any]:
        status = super().status()
        status["message"] = "使用浏览器仿真搜索网页站"
        return status

    def manual_url(self, keyword: str) -> str:
        return f"{self.root_url}/sub/?{urlencode({'searchword': keyword})}"

    def search(self, keyword: str, targets: List[Dict[str, Any]], scope: str) -> List[OnlineSubtitleResult]:
        status, text, final_url = self.fetcher.get_text(self.manual_url(keyword))
        if status >= 400 or not text:
            raise ValueError(f"射手网(伪) 搜索失败，HTTP {status}")
        results: List[OnlineSubtitleResult] = []
        for link in _extract_links(text):
            href = (link.href or "").strip()
            title = re.sub(r"\s+", " ", html.unescape(link.text or "")).strip()
            if not self._is_result_link(href, title):
                continue
            page_url = urljoin(self.root_url, href)
            season, episode = _episode_from_text(title) or (0, 0)
            direct_download = self._looks_like_download_href(href)
            results.append(
                OnlineSubtitleResult(
                    provider=self.provider_id,
                    result_id=_stable_result_id(self.provider_id, page_url),
                    title=title or Path(urlparse(page_url).path).name or "射手网(伪) 字幕",
                    page_url=page_url,
                    download_url=page_url if direct_download else "",
                    language=_guess_language_label(title),
                    format=_guess_subtitle_format(title),
                    season=season,
                    episode=episode,
                    score=_score_result(title, keyword, targets),
                    source=self.display_name,
                    note="浏览器仿真解析自射手网(伪)",
                    downloadable=True,
                )
            )
        if not results:
            logger.info("[SubtitleManualUpload] 射手网(伪) 未解析到字幕条目 final_host=%s", _host(final_url))
        return _dedupe_results(results)[:30]

    def download(self, result: Dict[str, Any], captcha_code: str = "") -> Tuple[str, bytes]:
        page_url = result.get("page_url") or ""
        download_url = result.get("download_url") or self._extract_download_url(page_url)
        if not download_url:
            raise ValueError("射手网(伪) 未找到可下载链接，请使用手动搜索")
        return super().download({**result, "download_url": download_url, "page_url": page_url}, captcha_code=captcha_code)

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


class OnlineSubtitleSearchService:
    def __init__(
        self,
        *,
        engine: str = DEFAULT_ENGINE,
        use_proxy: bool = False,
        provider_roots: Optional[Dict[str, str]] = None,
    ):
        self.fetcher = OnlinePageClient(engine=engine, use_proxy=use_proxy)
        roots = normalize_provider_roots(provider_roots)
        self.providers: Dict[str, BaseSubtitleProvider] = {
            "subhd": SubhdProvider(self.fetcher, root_url=roots["subhd"]),
            "zimuku": ZimukuProvider(self.fetcher, root_url=roots["zimuku"]),
            "assrt": AssrtProvider(self.fetcher, root_url=roots["assrt"]),
        }

    def status(self) -> Dict[str, Any]:
        browser_status = self.fetcher.status()
        return {
            "engine": browser_status["engine"],
            "engine_name": browser_status["engine_name"],
            "providers": [provider.status() for provider in self.providers.values()],
            "capabilities": {
                "ocr": _can_import("app.helper.ocr"),
                "cloakbrowser": browser_status["cloakbrowser"],
                "mp_browser": browser_status["mp_browser"],
                "flaresolverr": _mp_browser_looks_configured(),
                "proxy": browser_status["proxy"],
            },
            "engine_available": browser_status["available"],
        }

    def manual_links(self, keywords: List[str]) -> List[Dict[str, Any]]:
        links: List[Dict[str, Any]] = []
        for provider in self.providers.values():
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
        if not self.fetcher.available():
            engine_name = "CloakBrowser" if self.fetcher.engine == DEFAULT_ENGINE else "MoviePilot 浏览器仿真/FlareSolverr"
            return {
                "results": [],
                "messages": [
                    {
                        "provider": "engine",
                        "level": "warning",
                        "message": f"{engine_name} 不可用，请检查 MoviePilot 浏览器环境或改用手动搜索链接",
                    }
                ],
            }
        provider_ids = [item for item in providers if item in self.providers] or list(self.providers.keys())
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
        results.sort(key=lambda item: (item.score, item.provider != "subhd", item.title), reverse=True)
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
                        f"{title} 第{season}季第{episode}集",
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


def _format_network_error(url: str, exc: BaseException) -> str:
    host = _host(url) or "字幕站"
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
