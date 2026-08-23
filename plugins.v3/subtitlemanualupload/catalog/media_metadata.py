from __future__ import annotations

import re
from typing import Any, Callable, Dict, Iterable, List, Tuple

from .target_normalizers import NormalizeText, SafeInt, _default_normalize_text


TitleAliasExtractor = Callable[[Any], List[str]]


def _latin_title(text: str) -> bool:
    return bool(text and re.search(r"[A-Za-z]", text) and not re.search(r"[\u3400-\u9fff\u3040-\u30ff\uac00-\ud7af]", text))


def english_title_from_aliases(aliases: List[str]) -> str:
    for item in aliases or []:
        if _latin_title(item):
            return item
    return ""


def tmdb_aliases(
    *values: Any,
    extract_title_aliases_func: TitleAliasExtractor,
) -> List[str]:
    aliases: List[str] = []

    def walk(value: Any) -> None:
        if isinstance(value, (list, tuple)):
            for item in value:
                walk(item)
            return
        aliases.extend(extract_title_aliases_func(value))

    for value in values:
        walk(value)
    result: List[str] = []
    seen = set()
    for item in aliases:
        key = item.lower()
        if key and key not in seen:
            seen.add(key)
            result.append(item)
    return result[:80]


def english_title_from_tmdb_values(
    *values: Any,
    extract_title_aliases_func: TitleAliasExtractor,
    normalize_text: NormalizeText = _default_normalize_text,
) -> str:
    candidates: List[str] = []

    def add_title(value: Any) -> None:
        for item in extract_title_aliases_func(value):
            if _latin_title(item):
                candidates.append(item)

    def walk(value: Any) -> None:
        if isinstance(value, (list, tuple)):
            for item in value:
                walk(item)
            return
        if not isinstance(value, dict):
            return
        lang = normalize_text(value.get("iso_639_1")).lower()
        country = normalize_text(value.get("iso_3166_1")).lower()
        if lang == "en" or country in {"us", "gb", "uk"}:
            data = value.get("data")
            if isinstance(data, dict):
                add_title({key: data.get(key) for key in ("title", "name")})
            add_title({key: value.get(key) for key in ("title", "name")})
        for key in ["data", "titles", "results", "translations", "alternative_titles", "aliases"]:
            walk(value.get(key))

    for value in values:
        walk(value)
    seen = set()
    for item in candidates:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        return item
    return ""


def tmdb_detail_payload(
    detail: Any,
    *,
    extract_title_aliases_func: TitleAliasExtractor,
    normalize_text: NormalizeText = _default_normalize_text,
) -> Dict[str, Any]:
    if not detail:
        return {}

    def value(*keys: str) -> Any:
        for key in keys:
            if isinstance(detail, dict) and key in detail:
                return detail.get(key)
            if hasattr(detail, key):
                return getattr(detail, key)
        return None

    translations = value("translations")
    alternative_titles = value("alternative_titles")
    aliases = tmdb_aliases(
        translations,
        alternative_titles,
        extract_title_aliases_func=extract_title_aliases_func,
    )
    return {
        "original_language": value("original_language") or "",
        "origin_country": value("origin_country") or [],
        "production_countries": value("production_countries") or [],
        "original_title": value("original_title", "original_name") or "",
        "en_title": english_title_from_tmdb_values(
            translations,
            alternative_titles,
            extract_title_aliases_func=extract_title_aliases_func,
            normalize_text=normalize_text,
        ) or english_title_from_aliases(aliases),
        "tmdb_aliases": aliases,
    }


def apply_tmdb_detail(target: Dict[str, Any], detail: Dict[str, Any]) -> None:
    for key in ["original_language", "origin_country", "production_countries", "original_title", "tmdb_aliases"]:
        value = detail.get(key)
        if value and not target.get(key):
            target[key] = value
    if detail.get("en_title") and not target.get("en_title"):
        target["en_title"] = detail["en_title"]


def flatten_media_values(
    value: Any,
    keys: Tuple[str, ...] = (),
    *,
    normalize_text: NormalizeText = _default_normalize_text,
) -> List[str]:
    values: List[str] = []

    def walk(item: Any) -> None:
        if item is None:
            return
        if isinstance(item, dict):
            for key in keys or ("iso_3166_1", "iso_639_1", "code", "value", "name", "english_name"):
                if key in item:
                    walk(item.get(key))
            return
        if isinstance(item, (list, tuple, set)):
            for child in item:
                walk(child)
            return
        text = normalize_text(item)
        if not text:
            return
        for part in re.split(r"[,/|]+", text):
            clean = normalize_text(part).lower().replace("_", "-")
            if clean:
                values.append(clean)

    walk(value)
    return values


def is_chinese_language_code(
    value: Any,
    *,
    normalize_text: NormalizeText,
    chinese_language_codes: Iterable[str],
) -> bool:
    codes = set(chinese_language_codes)
    code = normalize_text(value).lower().replace("_", "-")
    base = re.split(r"[-\s]+", code, maxsplit=1)[0] if code else ""
    return code in codes or base in codes


def is_chinese_country_value(
    value: Any,
    *,
    normalize_text: NormalizeText,
    chinese_country_codes: Iterable[str],
    chinese_region_names: Iterable[str],
) -> bool:
    country_codes = set(chinese_country_codes)
    region_names = set(chinese_region_names)
    text = normalize_text(value).lower().replace("_", "-")
    base = re.split(r"[-\s]+", text, maxsplit=1)[0] if text else ""
    return text in country_codes or base in country_codes or text in region_names


def chinese_category_evidence(
    entry: Dict[str, Any],
    *,
    normalize_text: NormalizeText,
    chinese_category_pattern: Any,
) -> str:
    values = []
    for key in ["library_name", "media_category", "media_category_name", "category", "category_name", "type_name"]:
        raw = entry.get(key)
        if isinstance(raw, (list, tuple, set)):
            values.extend(normalize_text(item) for item in raw)
        else:
            values.append(normalize_text(raw))
    text = " ".join(item for item in values if item)
    if text and chinese_category_pattern.search(text):
        return "MP 分类/库名包含华语标识"
    return ""


def auto_media_for_entry(
    entry: Dict[str, Any],
    *,
    tmdb_detail_for_media_func: Callable[[Dict[str, Any]], Dict[str, Any]],
) -> Dict[str, Any]:
    media = {
        "media_type": entry.get("media_type"),
        "title": entry.get("title"),
        "year": entry.get("year"),
        "tmdb_id": entry.get("tmdb_id"),
        "douban_id": entry.get("douban_id"),
        "original_language": entry.get("original_language"),
        "origin_country": entry.get("origin_country"),
        "production_countries": entry.get("production_countries"),
        "original_title": entry.get("original_title") or entry.get("original_name"),
        "en_title": entry.get("en_title"),
        "tmdb_aliases": entry.get("tmdb_aliases"),
    }
    tmdb_detail = tmdb_detail_for_media_func(media)
    if tmdb_detail:
        apply_tmdb_detail(media, tmdb_detail)
        apply_tmdb_detail(entry, tmdb_detail)
    return media


def is_chinese_transfer_media(
    entry: Dict[str, Any],
    *,
    auto_media_for_entry_func: Callable[[Dict[str, Any]], Dict[str, Any]],
    normalize_text: NormalizeText,
    chinese_language_codes: Iterable[str],
    chinese_country_codes: Iterable[str],
    chinese_region_names: Iterable[str],
    chinese_category_pattern: Any,
) -> Tuple[bool, str]:
    category_reason = chinese_category_evidence(
        entry,
        normalize_text=normalize_text,
        chinese_category_pattern=chinese_category_pattern,
    )
    if category_reason:
        return True, category_reason

    media = auto_media_for_entry_func(entry)
    languages = flatten_media_values(
        media.get("original_language"),
        ("iso_639_1", "code", "value", "name", "english_name"),
        normalize_text=normalize_text,
    )
    for language in languages:
        if is_chinese_language_code(
            language,
            normalize_text=normalize_text,
            chinese_language_codes=chinese_language_codes,
        ):
            return True, f"TMDB original_language={language}"

    country_values = [
        *flatten_media_values(
            media.get("origin_country"),
            ("iso_3166_1", "code", "value", "name", "english_name"),
            normalize_text=normalize_text,
        ),
        *flatten_media_values(
            media.get("production_countries"),
            ("iso_3166_1", "code", "value", "name", "english_name"),
            normalize_text=normalize_text,
        ),
    ]
    for country in country_values:
        if is_chinese_country_value(
            country,
            normalize_text=normalize_text,
            chinese_country_codes=chinese_country_codes,
            chinese_region_names=chinese_region_names,
        ):
            return True, f"TMDB country={country}"

    if media.get("tmdb_id"):
        return False, "TMDB 未提供中文语种/地区证据"
    return False, "中文识别证据不足"


class MediaMetadataService:
    def __init__(
        self,
        *,
        tmdb_chain_factory: Any,
        media_type_tv: Any,
        media_type_movie: Any,
        tmdb_detail_cache: Dict[str, Dict[str, Any]],
        logger_warning: Callable[..., None],
        normalize_text: NormalizeText,
        safe_int: SafeInt,
        media_type_text_func: Callable[[Any], str],
        extract_title_aliases_func: TitleAliasExtractor,
        chinese_language_codes: Iterable[str],
        chinese_country_codes: Iterable[str],
        chinese_region_names: Iterable[str],
        chinese_category_pattern: Any,
    ) -> None:
        self._tmdb_chain_factory = tmdb_chain_factory
        self._media_type_tv = media_type_tv
        self._media_type_movie = media_type_movie
        self._tmdb_detail_cache = tmdb_detail_cache
        self._logger_warning = logger_warning
        self._normalize_text = normalize_text
        self._safe_int = safe_int
        self._media_type_text = media_type_text_func
        self._extract_title_aliases = extract_title_aliases_func
        self._chinese_language_codes = set(chinese_language_codes)
        self._chinese_country_codes = set(chinese_country_codes)
        self._chinese_region_names = set(chinese_region_names)
        self._chinese_category_pattern = chinese_category_pattern

    def tmdb_detail_for_media(self, media: Dict[str, Any]) -> Dict[str, Any]:
        tmdb_id = self._safe_int(media.get("tmdb_id"), 0)
        media_type = self._media_type_text(media.get("media_type"))
        if not tmdb_id or self._tmdb_chain_factory is None:
            return {}
        cache_key = f"{media_type}:{tmdb_id}"
        if cache_key in self._tmdb_detail_cache:
            return dict(self._tmdb_detail_cache[cache_key])
        try:
            mp_type = self._media_type_tv if media_type == "tv" else self._media_type_movie
            detail = self._tmdb_chain_factory().tmdb_info(tmdbid=tmdb_id, mtype=mp_type)
        except TypeError:
            try:
                mp_type = self._media_type_tv if media_type == "tv" else self._media_type_movie
                detail = self._tmdb_chain_factory().tmdb_info(tmdb_id=tmdb_id, mtype=mp_type)
            except Exception as exc:
                self._logger_warning("[SubtitleManualUpload] 读取 TMDB 详情失败 tmdb=%s type=%s error=%s", tmdb_id, media_type, exc)
                return {}
        except Exception as exc:
            self._logger_warning("[SubtitleManualUpload] 读取 TMDB 详情失败 tmdb=%s type=%s error=%s", tmdb_id, media_type, exc)
            return {}
        payload = self.tmdb_detail_payload(detail)
        self._tmdb_detail_cache[cache_key] = payload
        return dict(payload)

    def tmdb_detail_payload(self, detail: Any) -> Dict[str, Any]:
        return tmdb_detail_payload(
            detail,
            extract_title_aliases_func=self._extract_title_aliases,
            normalize_text=self._normalize_text,
        )

    def auto_media_for_entry(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        return auto_media_for_entry(entry, tmdb_detail_for_media_func=self.tmdb_detail_for_media)

    def is_chinese_transfer_media(self, entry: Dict[str, Any]) -> Tuple[bool, str]:
        return is_chinese_transfer_media(
            entry,
            auto_media_for_entry_func=self.auto_media_for_entry,
            normalize_text=self._normalize_text,
            chinese_language_codes=self._chinese_language_codes,
            chinese_country_codes=self._chinese_country_codes,
            chinese_region_names=self._chinese_region_names,
            chinese_category_pattern=self._chinese_category_pattern,
        )


__all__ = [name for name in globals() if not name.startswith("__")]
