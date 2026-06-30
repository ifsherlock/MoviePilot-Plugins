from __future__ import annotations

import http.cookiejar
import json
import re
import ssl
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.parse import unquote, urlparse, urlunparse

from app.core.config import settings
from app.log import logger

from .models import CaptchaRequiredError


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
)
DEFAULT_ENGINE = "cloakbrowser"
MP_BROWSER_ENGINE = "mp_browser"
ONLINE_ENGINES = {DEFAULT_ENGINE, MP_BROWSER_ENGINE}


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
                    time.sleep(0.5 * (2**attempt))
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
                    time.sleep(0.5 * (2**attempt))
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
