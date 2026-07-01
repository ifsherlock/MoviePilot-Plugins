from __future__ import annotations

import base64
import html
import io
import json
import re
import ssl
import struct
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import quote, urlencode, urljoin, urlparse

from app.core.config import settings
from app.log import logger

from .clients import OnlinePageClient
from .keyword_builder import _unique_keywords
from .matcher import _extract_years, _normalize_imdb_tt
from .models import HtmlLink, OnlineSubtitleResult


DEFAULT_PROVIDER_ROOTS = {
    "subhd": "https://subhd.tv",
    "zimuku": "https://zmk.pw",
    "assrt": "https://2.assrt.net",
    "opensubtitles": "https://www.opensubtitles.com",
}
LEGACY_PROVIDER_ROOTS = {
    "zimuku": {"https://zimuku.org"},
}
DEFAULT_ASSRT_API_URL = "https://api.assrt.net"
DEFAULT_OPENSUBTITLES_API_URL = "https://api.opensubtitles.com/api/v1"
INTERACTIVE_DOWNLOAD_EVENT_TIMEOUT_MS = 12000


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


def _looks_like_html_bytes(content: bytes, filename: str = "") -> bool:
    suffix = Path(filename or "").suffix.lower()
    if suffix in {".zip", ".rar", ".srt", ".ass", ".ssa", ".sub", ".vtt", ".webvtt", ".sbv"}:
        return False
    head = (content or b"")[:300].lstrip().lower()
    return head.startswith(b"<!doctype html") or head.startswith(b"<html") or b"<title>" in head


def normalize_root_url(value: Any, default: str) -> str:
    url = str(value or "").strip().rstrip("/")
    if not re.match(r"^https?://", url, flags=re.I):
        return default
    return url


def normalize_provider_roots(value: Optional[Dict[str, Any]]) -> Dict[str, str]:
    raw = value if isinstance(value, dict) else {}
    roots: Dict[str, str] = {}
    for provider_id, default_url in DEFAULT_PROVIDER_ROOTS.items():
        normalized = normalize_root_url(raw.get(provider_id), default_url)
        if normalized in LEGACY_PROVIDER_ROOTS.get(provider_id, set()):
            normalized = default_url
        roots[provider_id] = normalized
    return roots


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


__all__ = [name for name in globals() if not name.startswith("__")]
