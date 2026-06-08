from __future__ import annotations

import base64
import html
import io
import json
import re
import tempfile
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
DEFAULT_ASSRT_API_URL = "https://api.assrt.net"


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
    provider_label: str = ""
    requires_captcha: bool = False
    captcha_hint: str = ""
    download_steps: str = ""

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
            "requires_captcha": self.requires_captcha,
            "captcha_hint": self.captcha_hint,
            "download_steps": self.download_steps,
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
        site_cookies: Optional[Dict[str, str]] = None,
    ):
        self.engine = normalize_online_engine(engine)
        self.use_proxy = use_proxy
        self.timeout = timeout
        self.site_cookies = _normalize_site_cookies(site_cookies)
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
        self._prepare_cookie_for_url(url)
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

    def get_bytes_interactive(self, url: str, *, referer: str = "", captcha_code: str = "") -> Tuple[str, bytes, str]:
        if self.engine != DEFAULT_ENGINE:
            raise CaptchaRequiredError(
                "当前在线搜索引擎不支持交互式验证码下载，请切换到 CloakBrowser 或手动下载后上传。",
                verify_url=url,
            )
        context = self._ensure_context()
        self._prepare_cookie_for_url(url)
        if referer:
            self._prepare_cookie_for_url(referer)
        page = None
        try:
            page = context.new_page()
            page.set_extra_http_headers({"User-Agent": USER_AGENT, **({"Referer": referer} if referer else {})})
            if referer:
                page.goto(referer, wait_until="domcontentloaded", timeout=self.timeout * 1000)
            try:
                with page.expect_download(timeout=self.timeout * 1000) as download_info:
                    page.goto(url, wait_until="domcontentloaded", timeout=self.timeout * 1000)
                return self._read_playwright_download(download_info.value, url)
            except Exception:
                page.goto(url, wait_until="domcontentloaded", timeout=self.timeout * 1000)
            captcha = captcha_code or self._recognize_page_captcha(page)
            if captcha:
                inputs = page.locator("input[type='text'], input:not([type]), textarea")
                if inputs.count():
                    inputs.first.fill(captcha)
                    try:
                        with page.expect_download(timeout=self.timeout * 1000) as download_info:
                            self._click_first_download_submit(page)
                        logger.info("[SubtitleManualUpload] 下载页验证码提交完成 host=%s source=%s", _host(page.url or url), "user" if captcha_code else "ocr")
                        return self._read_playwright_download(download_info.value, page.url or url)
                    except Exception as exc:
                        logger.warning("[SubtitleManualUpload] 下载页验证码提交后未捕获下载 host=%s source=%s error=%s", _host(page.url or url), "user" if captcha_code else "ocr", exc)
            raise CaptchaRequiredError(
                "下载页需要验证码或站点验证；请输入验证码后重试，或打开验证页手动下载后上传。",
                verify_url=page.url or url,
                captcha_hint="浏览器仿真已打开下载页，但未自动识别或提交验证码。",
            )
        finally:
            if page:
                try:
                    page.close()
                except Exception:
                    pass

    @staticmethod
    def _click_first_download_submit(page: Any) -> None:
        for selector in [
            "button[type='submit']",
            "input[type='submit']",
            "button:has-text('下载')",
            "button:has-text('提交')",
            "a:has-text('下载')",
        ]:
            locator = page.locator(selector)
            if locator.count():
                locator.first.click()
                return
        page.keyboard.press("Enter")

    @staticmethod
    def _recognize_page_captcha(page: Any) -> str:
        try:
            from app.helper.ocr import OcrHelper
        except Exception as exc:
            logger.info("[SubtitleManualUpload] MoviePilot OCR 不可用，跳过下载页验证码自动识别 error=%s", exc)
            return ""
        candidates = []
        try:
            image_sources = page.locator("img").evaluate_all(
                """imgs => imgs.map(img => ({
                    src: img.currentSrc || img.src || '',
                    alt: img.alt || '',
                    title: img.title || '',
                    width: img.naturalWidth || img.width || 0,
                    height: img.naturalHeight || img.height || 0
                }))"""
            )
        except Exception:
            image_sources = []
        for item in image_sources or []:
            src = str(item.get("src") or "")
            label = f"{item.get('alt') or ''} {item.get('title') or ''}".lower()
            width = int(item.get("width") or 0)
            height = int(item.get("height") or 0)
            looks_like_captcha = (
                "captcha" in src.lower()
                or "verify" in src.lower()
                or "验证码" in label
                or "验证" in label
                or (30 <= width <= 260 and 15 <= height <= 120)
            )
            if not looks_like_captcha:
                continue
            if src.startswith("data:image/") and "base64," in src:
                candidates.append(src.split("base64,", 1)[1])
                continue
            try:
                response = page.request.get(urljoin(page.url, src), timeout=10000)
                if response.ok:
                    candidates.append(base64.b64encode(response.body()).decode("ascii"))
            except Exception:
                continue
        helper = OcrHelper()
        for image_b64 in candidates[:4]:
            try:
                text = _clean_captcha_text(helper.get_captcha_text(image_b64=image_b64))
                if len(text) >= 4:
                    logger.info("[SubtitleManualUpload] 下载页验证码 OCR 完成 host=%s length=%s", _host(page.url), len(text))
                    return text
            except Exception as exc:
                logger.warning("[SubtitleManualUpload] 下载页验证码 OCR 失败 host=%s error=%s", _host(page.url), exc)
        return ""

    @staticmethod
    def _read_playwright_download(download: Any, url: str) -> Tuple[str, bytes, str]:
        path = download.path()
        filename = download.suggested_filename or Path(urlparse(url).path).name or "subtitle.zip"
        if path:
            return filename, Path(path).read_bytes(), url
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            tmp_path = Path(tmp_file.name)
        try:
            download.save_as(str(tmp_path))
            return filename, tmp_path.read_bytes(), url
        finally:
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass

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

    def _prepare_cookie_for_url(self, url: str) -> None:
        cookie = self._configured_cookie_header(url)
        if not cookie:
            return
        if self.engine == DEFAULT_ENGINE:
            self._set_browser_cookie_header(url, cookie)

    def _set_browser_cookie_header(self, url: str, cookie: str) -> None:
        host = urlparse(url).hostname or ""
        if not host:
            return
        context = self._ensure_context()
        cookies = []
        for name, value in _parse_cookie_header(cookie).items():
            cookies.append(
                {
                    "name": name,
                    "value": value,
                    "domain": host,
                    "path": "/",
                    "httpOnly": False,
                    "secure": urlparse(url).scheme == "https",
                }
            )
        if not cookies:
            return
        try:
            context.add_cookies(cookies)
        except Exception as exc:
            logger.warning("[SubtitleManualUpload] 注入站点 Cookie 失败 host=%s count=%s error=%s", _host(url), len(cookies), exc)

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
                cookies=self._configured_cookie_header(url) or None,
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
        configured = self._configured_cookie_header(url)
        if self.engine != DEFAULT_ENGINE or not self._context:
            return configured
        try:
            cookies = self._context.cookies([url])
        except Exception:
            return configured
        pairs = []
        for item in cookies or []:
            name = str(item.get("name") or "").strip()
            value = str(item.get("value") or "")
            if name:
                pairs.append(f"{name}={value}")
        return _merge_cookie_headers(configured, "; ".join(pairs))

    def _configured_cookie_header(self, url: str) -> str:
        host = (urlparse(url).hostname or "").lower()
        if not host:
            return ""
        for cookie_host, cookie in self.site_cookies.items():
            if host == cookie_host or host.endswith(f".{cookie_host}"):
                return cookie
        return ""


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
        detail_links = self._collect_result_links(text)
        results: List[OnlineSubtitleResult] = []
        raw_count = len(detail_links)
        for detail_url, search_title in detail_links[:20]:
            try:
                item = self._parse_subtitle_page(detail_url, keyword, targets, search_title)
                if item:
                    results.append(item)
            except Exception as exc:
                logger.warning(
                    "[SubtitleManualUpload] SubHD 单条字幕解析失败 host=%s error=%s",
                    _host(detail_url),
                    exc,
                )
        filtered = _filter_relevant_results(results, keyword, targets)
        logger.info(
            "[SubtitleManualUpload] SubHD 搜索结果过滤完成 host=%s raw=%s parsed=%s kept=%s max_score=%s",
            _host(final_url),
            raw_count,
            len(results),
            len(filtered),
            max([item.score for item in filtered], default=0),
        )
        if not filtered:
            logger.info("[SubtitleManualUpload] SubHD 未解析到高相关字幕条目 final_host=%s", _host(final_url))
        return filtered[:30]

    def download(self, result: Dict[str, Any], captcha_code: str = "") -> Tuple[str, bytes]:
        page_url = result.get("page_url") or ""
        sid = result.get("result_id") or ""
        download_url = result.get("download_url") or (f"{self.root_url}/down/{sid}" if sid else "")
        if not download_url:
            raise ValueError("SubHD 没有可下载链接")
        filename, content, final_url = self.fetcher.get_bytes(download_url, referer=page_url)
        if self._looks_like_html(content, filename):
            if captcha_code:
                filename, content, final_url = self.fetcher.get_bytes_interactive(
                    download_url,
                    referer=page_url,
                    captcha_code=captcha_code,
                )
                if not self._looks_like_html(content, filename):
                    return filename or self._safe_download_name(result), content
            raise CaptchaRequiredError(
                self._html_download_reason(content, page_url or download_url),
                provider=self.provider_id,
                verify_url=page_url or download_url,
                captcha_hint="SubHD 下载页需要验证码或站点验证，请在验证页完成后重试，或手动下载后上传。",
            )
        logger.info(
            "[SubtitleManualUpload] SubHD 在线字幕下载完成 final_host=%s size=%s",
            _host(final_url),
            len(content),
        )
        return filename or self._safe_download_name(result), content

    def _collect_result_links(self, text: str) -> List[Tuple[str, str]]:
        links: List[Tuple[str, str]] = []
        seen = set()
        for link in _extract_links(text):
            href = link.href
            if not href.startswith("/a/"):
                continue
            url = urljoin(self.root_url, href)
            if url in seen:
                continue
            seen.add(url)
            links.append((url, self._clean_text(link.text)))
        return links

    def _parse_subtitle_page(
        self,
        detail_url: str,
        keyword: str,
        targets: List[Dict[str, Any]],
        search_title: str = "",
    ) -> Optional[OnlineSubtitleResult]:
        status, text, _ = self.fetcher.get_text(detail_url, referer=self.root_url)
        if status >= 400 or not text:
            return None
        title = search_title or self._clean_text(_first_nonempty_link_text(text, "/a/")) or self._html_title(text) or Path(detail_url).name
        download_url = ""
        for link in _extract_links(text):
            if "/down/" in link.href or "下载字幕" in link.text:
                download_url = urljoin(self.root_url, link.href)
                break
        sid = Path(urlparse(download_url or detail_url).path).name
        if not sid or not title:
            return None
        season, episode = _episode_from_text(title) or (0, 0)
        return OnlineSubtitleResult(
            provider=self.provider_id,
            provider_label=self.display_name,
            result_id=sid,
            title=title,
            page_url=detail_url,
            download_url=download_url or f"{self.root_url}/down/{sid}",
            language=_guess_language_label(title),
            format=_guess_subtitle_format(title),
            season=season,
            episode=episode,
            score=_score_result(title, keyword, targets),
            source=self.display_name,
            note="自动解析自 SubHD 字幕页",
            requires_captcha=True,
            captcha_hint="下载时可能需要输入 SubHD 验证码。",
            download_steps="SubHD 搜索页 -> 字幕页 /a -> 下载页 /down -> 验证码/文件",
        )

    @staticmethod
    def _clean_text(value: str) -> str:
        return re.sub(r"\s+", " ", html.unescape(value or "")).strip()

    @classmethod
    def _html_download_reason(cls, content: bytes, page_url: str) -> str:
        text = _decode_bytes(content[:12000], None)
        lowered = text.lower()
        if any(token in lowered for token in ["verify", "captcha"]) or "验证码" in text or "验证" in text:
            return "SubHD 下载需要验证码或站点验证；请按页面提示完成验证后重试，或手动下载字幕包后上传。"
        if "登录" in text or "login" in lowered:
            return "SubHD 返回登录/验证页面而不是字幕文件；请使用手动链接在浏览器完成站点流程后上传字幕包。"
        logger.info(
            "[SubtitleManualUpload] SubHD 下载返回 HTML host=%s title=%s",
            _host(page_url),
            cls._html_title(text),
        )
        return "SubHD 返回网页而不是字幕文件，可能需要验证码或站点验证；请使用手动搜索链接下载后再上传。"

    @staticmethod
    def _html_title(text: str) -> str:
        match = re.search(r"<title[^>]*>(.*?)</title>", text or "", flags=re.I | re.S)
        if not match:
            return ""
        return re.sub(r"\s+", " ", html.unescape(match.group(1))).strip()[:80]


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
                    provider_label=self.display_name,
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
                    note="Zimuku 搜索结果，下载时会继续解析详情页和下载源",
                    downloadable=True,
                    requires_captcha=True,
                    captcha_hint="Zimuku 可能需要站点验证码。",
                    download_steps="Zimuku 搜索页 -> 详情页 -> 下载页 -> 下载源 -> 验证码/文件",
                )
            )
        filtered = _filter_relevant_results(_dedupe_results(results), keyword, targets)
        logger.info(
            "[SubtitleManualUpload] Zimuku 搜索结果过滤完成 host=%s raw=%s kept=%s max_score=%s",
            _host(final_url),
            len(results),
            len(filtered),
            max([item.score for item in filtered], default=0),
        )
        return filtered[:30]

    def download(self, result: Dict[str, Any], captcha_code: str = "") -> Tuple[str, bytes]:
        page_url = str(result.get("page_url") or result.get("download_url") or "").strip()
        if not page_url:
            raise ValueError("Zimuku 缺少详情页链接")
        logger.info("[SubtitleManualUpload] Zimuku 开始解析下载流程 stage=detail host=%s", _host(page_url))
        status, text, final_url = self.fetcher.get_text(page_url, referer=self.root_url)
        if _is_zimuku_security_page(text):
            text = self._solve_security_page(text, final_url)
        if status >= 400 and not text:
            raise ValueError(f"Zimuku 详情页访问失败，HTTP {status}")
        candidates = self._download_candidates(text, final_url or page_url)
        if not candidates:
            raise CaptchaRequiredError(
                "Zimuku 未解析到可自动下载的下载源；请打开详情页手动选择下载源，或下载后回到本插件上传。",
                provider=self.provider_id,
                verify_url=final_url or page_url,
                captcha_hint="详情页可能需要验证码或登录态后才显示下载源。",
            )
        return self._try_download_candidates(candidates, referer=final_url or page_url, captcha_code=captcha_code)

    def _try_download_candidates(self, candidates: List[str], *, referer: str, captcha_code: str = "") -> Tuple[str, bytes]:
        last_error = ""
        visited = set()
        for url in candidates[:8]:
            if url in visited:
                continue
            visited.add(url)
            try:
                logger.info("[SubtitleManualUpload] Zimuku 尝试下载源 stage=download host=%s", _host(url))
                filename, content, final_url = self.fetcher.get_bytes(url, referer=referer)
                if not _looks_like_html_content(content, filename):
                    logger.info(
                        "[SubtitleManualUpload] Zimuku 字幕下载完成 host=%s size=%s",
                        _host(final_url),
                        len(content),
                    )
                    return filename or Path(urlparse(final_url).path).name or "zimuku-subtitle.zip", content
                text = _decode_bytes(content[:200000], None)
                nested = self._download_candidates(text, final_url or url)
                if nested:
                    nested_name, nested_content = self._try_download_candidates(
                        nested,
                        referer=final_url or url,
                        captcha_code=captcha_code,
                    )
                    return nested_name, nested_content
                if _is_zimuku_security_page(text) or _looks_like_captcha_page(text):
                    try:
                        name, data, _ = self.fetcher.get_bytes_interactive(url, referer=referer, captcha_code=captcha_code)
                        return name, data
                    except CaptchaRequiredError:
                        raise
                    except Exception as exc:
                        logger.warning("[SubtitleManualUpload] Zimuku 交互式验证码下载失败 host=%s error=%s", _host(url), exc)
                    raise CaptchaRequiredError(
                        "Zimuku 下载需要验证码或站点验证；请打开验证页完成后重试，或手动下载后上传。",
                        provider=self.provider_id,
                        verify_url=final_url or url,
                        captcha_hint="下载源页面返回验证码/验证页面。",
                    )
                last_error = "下载源返回网页而不是字幕文件"
            except CaptchaRequiredError:
                raise
            except Exception as exc:
                last_error = str(exc)
        raise ValueError(f"Zimuku 下载源解析失败：{last_error or '没有可用下载源'}")

    def _download_candidates(self, text: str, base_url: str) -> List[str]:
        candidates: List[str] = []
        for link in _extract_links(text):
            href = (link.href or "").strip()
            label = (link.text or "").strip()
            if not href or href.startswith("#") or href.startswith("javascript:"):
                continue
            lowered_href = href.lower()
            lowered_label = label.lower()
            looks_download = (
                any(token in lowered_href for token in ["/download", "/down", "/dld", "download", "down="])
                or any(ext in lowered_href for ext in [".zip", ".rar", ".7z", ".srt", ".ass", ".ssa"])
                or any(token in lowered_label for token in ["下载", "download", "字幕"])
            )
            if not looks_download:
                continue
            url = urljoin(base_url or self.root_url, href)
            if url not in candidates:
                candidates.append(url)
        return candidates

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
        status["message"] = "已配置 API Key，优先使用官方 API" if self.api_key else "未配置 API Key；默认不参与自动搜索，可手动勾选后尝试网页仿真"
        return status

    def manual_url(self, keyword: str) -> str:
        return f"{self.root_url}/sub/?{urlencode({'searchword': keyword})}"

    def search(self, keyword: str, targets: List[Dict[str, Any]], scope: str) -> List[OnlineSubtitleResult]:
        if self.api_key:
            return self._search_api(keyword, targets)
        logger.info("[SubtitleManualUpload] 射手网(伪) 未配置 API Key，使用网页仿真降级搜索 host=%s", _host(self.root_url))
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
                    provider_label=self.display_name,
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
                    note="未配置 API Key，浏览器仿真解析自射手网(伪)",
                    downloadable=True,
                )
            )
        if not results:
            logger.info("[SubtitleManualUpload] 射手网(伪) 未解析到字幕条目 final_host=%s", _host(final_url))
        return _dedupe_results(results)[:30]

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
            season, episode = _episode_from_text(title) or (0, 0)
            results.append(
                OnlineSubtitleResult(
                    provider=self.provider_id,
                    provider_label=self.display_name,
                    result_id=sid,
                    title=title,
                    page_url=f"{self.root_url}/sub/{sid}",
                    download_url=f"assrt-api:{sid}",
                    language=_guess_language_label(" ".join([title, str(item.get("lang") or ""), str(item.get("desc") or "")])),
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


class OnlineSubtitleSearchService:
    def __init__(
        self,
        *,
        engine: str = DEFAULT_ENGINE,
        use_proxy: bool = False,
        provider_roots: Optional[Dict[str, str]] = None,
        assrt_api_key: str = "",
        assrt_api_url: str = DEFAULT_ASSRT_API_URL,
        site_cookies: Optional[Dict[str, str]] = None,
    ):
        self.fetcher = OnlinePageClient(engine=engine, use_proxy=use_proxy, site_cookies=site_cookies)
        roots = normalize_provider_roots(provider_roots)
        self.providers: Dict[str, BaseSubtitleProvider] = {
            "subhd": SubhdProvider(self.fetcher, root_url=roots["subhd"]),
            "zimuku": ZimukuProvider(self.fetcher, root_url=roots["zimuku"]),
            "assrt": AssrtProvider(
                self.fetcher,
                root_url=roots["assrt"],
                api_key=assrt_api_key,
                api_url=assrt_api_url,
            ),
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
            "site_cookie_hosts": sorted(self.fetcher.site_cookies.keys()),
        }

    def manual_links(self, keywords: List[str], providers: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        links: List[Dict[str, Any]] = []
        provider_ids = list(self.providers.keys()) if providers is None else [item for item in providers if item in self.providers]
        for provider_id in provider_ids:
            provider = self.providers[provider_id]
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
        results.sort(key=lambda item: (_provider_priority(item), item.score, item.title), reverse=True)
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


def _normalize_site_cookies(value: Optional[Dict[str, Any]]) -> Dict[str, str]:
    raw = value if isinstance(value, dict) else {}
    cookies: Dict[str, str] = {}
    for host, cookie in raw.items():
        normalized_host = str(host or "").strip().lower().lstrip(".")
        normalized_cookie = _normalize_cookie_header(cookie)
        if normalized_host and normalized_cookie:
            cookies[normalized_host] = normalized_cookie
    return cookies


def _normalize_cookie_header(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text.lower().startswith("cookie:"):
        text = text.split(":", 1)[1].strip()
    return "; ".join(f"{name}={cookie_value}" for name, cookie_value in _parse_cookie_header(text).items())


def _parse_cookie_header(value: Any) -> Dict[str, str]:
    cookies: Dict[str, str] = {}
    for part in str(value or "").replace("\r", ";").replace("\n", ";").split(";"):
        if "=" not in part:
            continue
        name, cookie_value = part.split("=", 1)
        name = name.strip()
        cookie_value = cookie_value.strip()
        if not name:
            continue
        cookies[name] = cookie_value
    return cookies


def _merge_cookie_headers(*values: Any) -> str:
    merged: Dict[str, str] = {}
    for value in values:
        merged.update(_parse_cookie_header(value))
    return "; ".join(f"{name}={cookie_value}" for name, cookie_value in merged.items())


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
    if any(key in text for key in ["繁", "cht", "zh-hant", "zh-tw"]) or re.search(
        r"(^|[\s._\-\[\]()])(?:tw|hk)(?=$|[\s._\-\[\]()])",
        text,
    ):
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


def _filter_relevant_results(
    results: Iterable[OnlineSubtitleResult],
    keyword: str,
    targets: List[Dict[str, Any]],
) -> List[OnlineSubtitleResult]:
    return [item for item in results if _has_relevance_signal(item.title, keyword, targets)]


def _has_relevance_signal(title: str, keyword: str, targets: List[Dict[str, Any]]) -> bool:
    haystack = (title or "").lower()
    for part in re.split(r"[\s._-]+", (keyword or "").lower()):
        if len(part) >= 2 and part in haystack:
            return True
    hint = _episode_from_text(title)
    if hint:
        season, episode = hint
        for target in targets:
            target_season = int(target.get("season") or 0)
            target_episode = int(target.get("episode") or 0)
            if episode == target_episode and (not season or not target_season or season == target_season):
                return True
    for target in targets:
        for field in ["title", "basename", "filename"]:
            value = str(target.get(field) or "").lower()
            for part in re.split(r"[\s._-]+", value):
                if len(part) >= 2 and part in haystack:
                    return True
    return False


def _provider_priority(item: OnlineSubtitleResult) -> int:
    if item.provider == "assrt":
        return 30
    if item.provider == "zimuku":
        return 20
    if item.provider == "subhd":
        return 10
    return 0


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
