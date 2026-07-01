from __future__ import annotations

import base64
import html
import io
import json
import re
import struct
import tempfile
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import quote, urlencode, urljoin, urlparse

from app.core.config import settings
from app.log import logger

from .clients import (
    DEFAULT_ENGINE,
    MP_BROWSER_ENGINE,
    ONLINE_ENGINES,
    USER_AGENT,
    OnlineDirectDownloader,
    OnlinePageClient,
    _browser_proxy,
    _can_import,
    _compact_error_message,
    _content_magic,
    _decode_bytes,
    _format_browser_error,
    _format_network_error,
    _host,
    _is_retryable_network_error,
    _looks_like_html_content,
    _mp_browser_looks_configured,
    _playwright_proxy_from_value,
    normalize_online_engine,
)
from .keyword_builder import (
    AMBIGUOUS_SINGLE_TITLE_TOKENS,
    GENERIC_TITLE_ALIAS_CODES,
    GENERIC_TITLE_ALIAS_WORDS,
    OPENSUBTITLES_SEARCH_LANGUAGES,
    _alias_values,
    _as_list,
    _clean_keyword,
    _clean_title_alias,
    _clean_tv_basename_keyword,
    _contains_cjk,
    _contains_japanese,
    _contains_korean,
    _english_search_titles,
    _explicit_title_values,
    _is_ambiguous_single_title_alias,
    _is_cjk_text,
    _is_generic_language_alias,
    _looks_english_title,
    _looks_translation_metadata,
    _media_title_aliases,
    _normalize_code,
    _normalize_title_for_match,
    _original_titles,
    _query_plan_for_keyword,
    _query_source_for_keyword,
    _region_bucket,
    _region_bucket_label,
    _search_titles_by_region,
    _series_title_aliases,
    _strong_title_matches,
    _title_aliases,
    _title_matches,
    _unique_keywords,
    build_search_keywords,
    extract_title_aliases,
)
from .models import CaptchaRequiredError, HtmlLink, OnlineSubtitleResult


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
        for field in ["year", "title", "basename", "filename", "path"]:
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


def _opensubtitles_metadata_conflicts(attrs: Dict[str, Any], targets: List[Dict[str, Any]]) -> bool:
    target_tmdb_ids = {
        str(target.get("tmdb_id") or "").strip()
        for target in targets or []
        if str(target.get("tmdb_id") or "").strip()
    }
    target_imdb_ids = {
        _normalize_imdb_tt(target.get("imdb_id"))
        for target in targets or []
        if _normalize_imdb_tt(target.get("imdb_id"))
    }
    result_tmdb_ids: set[str] = set()
    result_imdb_ids: set[str] = set()

    def collect(value: Any) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                key_lower = str(key or "").lower()
                if key_lower in {"tmdb_id", "feature_tmdb_id"}:
                    text = str(item or "").strip()
                    if text and text not in {"0", "None", "null"}:
                        result_tmdb_ids.add(text)
                    continue
                if key_lower in {"imdb_id", "feature_imdb_id"}:
                    imdb = _normalize_imdb_tt(item)
                    if imdb:
                        result_imdb_ids.add(imdb)
                    continue
                collect(item)
        elif isinstance(value, list):
            for item in value:
                collect(item)

    collect(attrs or {})
    return bool(
        (target_tmdb_ids and result_tmdb_ids and target_tmdb_ids.isdisjoint(result_tmdb_ids))
        or (target_imdb_ids and result_imdb_ids and target_imdb_ids.isdisjoint(result_imdb_ids))
    )


def _safe_opensubtitles_title_identity(
    attrs: Dict[str, Any],
    file_info: Dict[str, Any],
    targets: List[Dict[str, Any]],
) -> bool:
    feature = attrs.get("feature_details") if isinstance(attrs.get("feature_details"), dict) else {}
    values = [
        attrs.get("release"),
        attrs.get("movie_name"),
        feature.get("title"),
        feature.get("movie_name"),
        file_info.get("file_name"),
    ]
    haystacks = [str(value or "") for value in values if str(value or "").strip()]
    for alias in _title_aliases({}, targets):
        if _is_ambiguous_single_title_alias(alias):
            continue
        if any(_strong_title_matches(alias, haystack) for haystack in haystacks):
            return True
    return False


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
    if media_type == "tv" and not series_matched and not metadata_matched:
        title_matched = False
        reject_reason = reject_reason or "剧名身份不匹配"
    if media_type == "tv" and episode_required and not episode_ok:
        reject_reason = reject_reason or "季集不匹配"
    safe_tv_title_identity = (
        media_type == "tv"
        and year_reject_reason
        and _safe_opensubtitles_title_identity(attrs, file_info, targets)
    )
    if safe_tv_title_identity and reject_reason == year_reject_reason:
        reject_reason = ""

    if _guess_language_label(title):
        score += 6

    identity_ok = title_matched or metadata_matched or file_title_matched
    if not identity_ok:
        reject_reason = reject_reason or "无标题或媒体身份信号"
    year_ok_for_strong = (
        not target_year
        or not result_years
        or target_year in result_years
        or safe_tv_title_identity
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

# Keep internal helpers available to split provider modules.
__all__ = [name for name in globals() if not name.startswith("__")]
