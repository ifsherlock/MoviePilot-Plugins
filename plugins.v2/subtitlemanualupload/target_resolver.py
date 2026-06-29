from __future__ import annotations

import re
import json
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple


NormalizeText = Callable[[Any], str]
SafeInt = Callable[[Any, int], int]
HashText = Callable[[str], str]
EpisodeHint = Callable[[str], Optional[Dict[str, int]]]
SubtitleFilesForTarget = Callable[[Dict[str, Any]], List[Dict[str, Any]]]
DetectLanguageProfile = Callable[[str, bytes], Dict[str, Any]]
NormalizeLanguageSuffix = Callable[[Any], str]
LanguageSuffixCheck = Callable[[Any], bool]
SubtitleBackupPath = Callable[[Path], Path]
TitleAliasExtractor = Callable[[Any], List[str]]


class TargetEntryCache:
    def __init__(
        self,
        entry_map: OrderedDict[str, Dict[str, Any]],
        *,
        max_size: int,
        normalize_text: NormalizeText,
    ) -> None:
        self._entry_map = entry_map
        self._max_size = max_size
        self._normalize_text = normalize_text

    def remember(self, entries: List[Dict[str, Any]]) -> None:
        for entry in entries:
            target_id = self._normalize_text(entry.get("id"))
            if not target_id:
                continue
            if target_id in self._entry_map:
                self._entry_map.move_to_end(target_id)
            self._entry_map[target_id] = entry
        while len(self._entry_map) > self._max_size:
            self._entry_map.popitem(last=False)

    def clear(self) -> None:
        self._entry_map.clear()

    def prune(self, entry_is_valid: Callable[[Dict[str, Any]], bool]) -> None:
        for target_id, entry in list(self._entry_map.items()):
            if not entry_is_valid(entry):
                self._entry_map.pop(target_id, None)

    def get(self, target_id: str) -> Optional[Dict[str, Any]]:
        return self._entry_map.get(self._normalize_text(target_id))

    def discard(self, target_id: str) -> None:
        self._entry_map.pop(self._normalize_text(target_id), None)

    def items(self) -> List[Tuple[str, Dict[str, Any]]]:
        return list(self._entry_map.items())

    def count(self) -> int:
        return len(self._entry_map)


def _default_normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _default_safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def media_type_text(value: Any) -> str:
    raw = str(getattr(value, "value", value) or "").strip().lower()
    if raw in {"movie", "电影", "mediatype.movie"}:
        return "movie"
    if raw in {"tv", "电视剧", "series", "mediatype.tv"}:
        return "tv"
    return ""


def poster_url(
    poster_path: Any,
    prefix: str = "w500",
    *,
    settings_obj: Any = None,
    normalize_text: NormalizeText = _default_normalize_text,
) -> str:
    poster = normalize_text(poster_path)
    if not poster:
        return ""
    if poster.startswith(("http://", "https://")):
        if prefix:
            return re.sub(r"(/t/p/)[^/]+/", rf"\g<1>{prefix}/", poster, count=1)
        return poster
    if not poster.startswith("/"):
        poster = f"/{poster}"
    domain = normalize_text(getattr(settings_obj, "TMDB_IMAGE_DOMAIN", "")) or "image.tmdb.org"
    return f"https://{domain}/t/p/{prefix}{poster}"


def history_type_text(
    value: Any,
    *,
    normalize_text: NormalizeText = _default_normalize_text,
) -> str:
    normalized = media_type_text(value)
    if normalized == "movie":
        return "电影"
    if normalized == "tv":
        return "电视剧"
    return normalize_text(value)


def number_from_tag(
    value: Any,
    *,
    normalize_text: NormalizeText = _default_normalize_text,
    safe_int: SafeInt = _default_safe_int,
) -> int:
    match = re.search(r"\d+", normalize_text(value))
    return safe_int(match.group(0), 0) if match else 0


def extract_episode_hint(
    file_name: str,
    *,
    safe_int: SafeInt = _default_safe_int,
) -> Optional[Dict[str, int]]:
    cleaned = str(file_name or "")
    patterns = [
        re.compile(r"(?i)\bS(?P<season>\d{1,2})[\s._-]*E(?P<episode>\d{1,3})\b"),
        re.compile(r"(?i)\b(?P<season>\d{1,2})x(?P<episode>\d{1,3})\b"),
        re.compile(r"第\s*(?P<season>\d{1,2})\s*季.*?第\s*(?P<episode>\d{1,3})\s*[集话話]"),
        re.compile(r"第\s*(?P<episode>\d{1,3})\s*[集话話]"),
    ]
    for pattern in patterns:
        match = pattern.search(cleaned)
        if not match:
            continue
        season = safe_int(match.groupdict().get("season"), 0)
        episode = safe_int(match.groupdict().get("episode"), 0)
        if episode:
            return {"season": season, "episode": episode}
    return None


def is_local_video_path(
    storage: str,
    path: str,
    *,
    normalize_text: NormalizeText = _default_normalize_text,
    settings_obj: Any = None,
    stream_exts: Iterable[str] = (),
    trust_transfer_history_paths: bool = False,
) -> bool:
    if normalize_text(storage) != "local" or not path:
        return False
    suffix = Path(path).suffix.lower()
    configured_exts = getattr(settings_obj, "RMT_MEDIAEXT", set()) or set()
    allowed_exts = {
        ext.lower() if str(ext).startswith(".") else f".{str(ext).lower()}"
        for ext in configured_exts
    }
    allowed_exts.update(stream_exts)
    if suffix and allowed_exts and suffix not in allowed_exts:
        return False
    if trust_transfer_history_paths:
        return True
    try:
        return Path(path).is_file()
    except Exception:
        return False


def event_value(obj: Any, *names: str, default: Any = "") -> Any:
    for name in names:
        if isinstance(obj, dict) and name in obj:
            return obj.get(name)
        if hasattr(obj, name):
            return getattr(obj, name)
    return default


def is_stream_path(
    path: Any,
    *,
    normalize_text: NormalizeText = _default_normalize_text,
    stream_exts: Iterable[str] = (),
) -> bool:
    return Path(normalize_text(path)).suffix.lower() in set(stream_exts)


def entry_path_is_valid(
    entry: Dict[str, Any],
    *,
    normalize_text: NormalizeText = _default_normalize_text,
    trust_transfer_history_paths: bool = False,
) -> bool:
    storage = normalize_text(entry.get("storage")) or "local"
    if storage != "local":
        return True
    path = normalize_text(entry.get("path"))
    if not path:
        return False
    if trust_transfer_history_paths:
        return True
    try:
        return Path(path).is_file()
    except Exception:
        return False


def entry_filesystem_signature(
    entry: Dict[str, Any],
    *,
    normalize_text: NormalizeText = _default_normalize_text,
) -> str:
    storage = normalize_text(entry.get("storage")) or "local"
    path_text = normalize_text(entry.get("path"))
    if storage != "local" or not path_text:
        return f"{storage}|{path_text}|remote"
    path = Path(path_text)
    normalized_path = path_text.lower().replace("\\", "/")
    try:
        stat = path.stat()
        parent_mtime = path.parent.stat().st_mtime_ns if path.parent.exists() else 0
        return "|".join(
            [
                "local",
                normalized_path,
                "1",
                str(stat.st_size),
                str(stat.st_mtime_ns),
                str(parent_mtime),
            ]
        )
    except FileNotFoundError:
        return f"local|{normalized_path}|0"
    except Exception as exc:
        return f"local|{normalized_path}|error:{type(exc).__name__}"


def entry_matches_keyword(
    entry: Dict[str, Any],
    keyword: str,
    *,
    normalize_text: NormalizeText = _default_normalize_text,
) -> bool:
    clean_keyword = normalize_text(keyword).lower()
    if not clean_keyword:
        return True
    haystack = " ".join(
        normalize_text(entry.get(key)).lower()
        for key in ("title", "filename", "basename", "relative_path")
    )
    return all(part in haystack for part in re.split(r"\s+", clean_keyword) if part)


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


def suggest_target(
    subtitle_info: Dict[str, Any],
    targets: List[Dict[str, Any]],
    *,
    extract_episode_hint: EpisodeHint,
) -> Optional[str]:
    if not targets:
        return None
    if len(targets) == 1:
        return targets[0]["id"]

    hint = extract_episode_hint(subtitle_info.get("source_name"))
    if not hint:
        return None

    season = hint.get("season", 0)
    episode = hint.get("episode", 0)
    for target in targets:
        if target.get("season", 0) == season and target.get("episode", 0) == episode:
            return target["id"]

    if season == 0:
        candidate_seasons = {target.get("season", 0) for target in targets if target.get("season", 0)}
        if len(candidate_seasons) == 1:
            only_season = next(iter(candidate_seasons))
            for target in targets:
                if target.get("season", 0) == only_season and target.get("episode", 0) == episode:
                    return target["id"]
    return None


def auto_fill_missing_targets(
    preview_items: List[Dict[str, Any]],
    targets: List[Dict[str, Any]],
    *,
    extract_episode_hint: EpisodeHint,
) -> None:
    unresolved = [item for item in preview_items if not item.get("target_id")]
    if not unresolved:
        return
    used_target_ids = {item.get("target_id") for item in preview_items if item.get("target_id")}
    remaining_targets = [target for target in targets if target.get("id") not in used_target_ids]
    if len(unresolved) != len(remaining_targets):
        return
    sorted_targets = sorted(
        remaining_targets,
        key=lambda item: (item.get("season", 0), item.get("episode", 0), item.get("label", "")),
    )
    sorted_items = sorted(
        unresolved,
        key=lambda item: (extract_episode_hint(item.get("source_name") or "") or {}).get("episode", 0),
    )
    for item, target in zip(sorted_items, sorted_targets):
        item["target_id"] = target["id"]


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


class SubtitleInventory:
    def __init__(
        self,
        *,
        subtitle_exts: Iterable[str],
        stream_exts: Iterable[str],
        embedded_text_codecs: Iterable[str],
        embedded_image_codecs: Iterable[str],
        embedded_probe_cache: "OrderedDict[str, List[Dict[str, Any]]]",
        embedded_probe_cache_max_size: int,
        trust_transfer_history_paths: bool,
        normalize_text: NormalizeText,
        normalize_language_suffix: NormalizeLanguageSuffix,
        detect_language_profile: DetectLanguageProfile,
        is_chinese_language_suffix: LanguageSuffixCheck,
        safe_int: SafeInt,
        subtitle_backup_path: SubtitleBackupPath,
        subprocess_module: Any,
        logger_warning: Callable[..., None],
    ) -> None:
        self._subtitle_exts = set(subtitle_exts)
        self._stream_exts = set(stream_exts)
        self._embedded_text_codecs = set(embedded_text_codecs)
        self._embedded_image_codecs = set(embedded_image_codecs)
        self._embedded_probe_cache = embedded_probe_cache
        self._embedded_probe_cache_max_size = embedded_probe_cache_max_size
        self._trust_transfer_history_paths = trust_transfer_history_paths
        self._normalize_text = normalize_text
        self._normalize_language_suffix = normalize_language_suffix
        self._detect_language_profile = detect_language_profile
        self._language_suffix_is_chinese = is_chinese_language_suffix
        self._safe_int = safe_int
        self._subtitle_backup_path = subtitle_backup_path
        self._subprocess = subprocess_module
        self._logger_warning = logger_warning

    def subtitle_files_for_target(self, target_entry: Dict[str, Any]) -> List[Dict[str, Any]]:
        storage = self._normalize_text(target_entry.get("storage")) or "local"
        if storage != "local":
            return []
        if self._trust_transfer_history_paths:
            return []

        video_path_raw = self._normalize_text(target_entry.get("path"))
        if not video_path_raw:
            return []

        video_path = Path(video_path_raw)
        media_dir = video_path.parent
        if not media_dir.exists() or not media_dir.is_dir():
            return []

        stem = video_path.stem
        subtitles: List[Dict[str, Any]] = []
        try:
            for sub_file in media_dir.iterdir():
                if not sub_file.is_file():
                    continue
                if sub_file.suffix.lower() not in self._subtitle_exts:
                    continue
                if sub_file.stem != stem and not sub_file.name.startswith(f"{stem}."):
                    continue
                try:
                    raw_bytes = sub_file.read_bytes()
                except Exception:
                    raw_bytes = b""
                language_profile = self._detect_language_profile(sub_file.name, raw_bytes)
                backup_path = self._subtitle_backup_path(sub_file)
                subtitles.append(
                    {
                        "name": sub_file.name,
                        "path": str(sub_file),
                        "relative_path": str(sub_file).replace("\\", "/"),
                        "ext": sub_file.suffix.lower(),
                        "language_suffix": language_profile.get("suffix", ""),
                        "language_category": language_profile.get("category", ""),
                        "backup_path": str(backup_path) if backup_path.exists() else "",
                        "backup_available": backup_path.exists(),
                        "size": sub_file.stat().st_size,
                        "modified_at": datetime.fromtimestamp(sub_file.stat().st_mtime).isoformat(timespec="seconds"),
                    }
                )
        except Exception as exc:
            self._logger_warning(
                "[SubtitleManualUpload] 读取外挂字幕失败 video=%s error=%s",
                video_path.name,
                exc,
            )
        subtitles.sort(key=lambda item: item.get("name", ""))
        return subtitles

    def embedded_subtitle_tracks_for_target(self, target_entry: Dict[str, Any]) -> List[Dict[str, Any]]:
        storage = self._normalize_text(target_entry.get("storage")) or "local"
        path_text = self._normalize_text(target_entry.get("path"))
        if storage != "local" or not path_text or self._is_stream_path(path_text):
            return []
        if self._trust_transfer_history_paths:
            return []

        video_path = Path(path_text)
        if not video_path.is_file():
            return []

        cache_key = self.embedded_subtitle_probe_cache_key(video_path)
        if cache_key:
            cached = self._embedded_probe_cache.get(cache_key)
            if cached is not None:
                self._embedded_probe_cache.move_to_end(cache_key)
                return [dict(item) for item in cached]

        try:
            completed = self._subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-select_streams",
                    "s",
                    "-show_entries",
                    "stream=index,codec_name,disposition:stream_tags=language,title",
                    "-of",
                    "json",
                    str(video_path),
                ],
                stdout=self._subprocess.PIPE,
                stderr=self._subprocess.PIPE,
                text=True,
                check=True,
                timeout=8,
            )
            payload = json.loads(completed.stdout or "{}")
        except FileNotFoundError:
            self._logger_warning("[SubtitleManualUpload] ffprobe 不可用，无法检查内嵌字幕 video=%s", video_path.name)
            return []
        except self._subprocess.TimeoutExpired:
            self._logger_warning("[SubtitleManualUpload] 检查内嵌字幕超时 video=%s", video_path.name)
            return []
        except Exception as exc:
            self._logger_warning("[SubtitleManualUpload] 检查内嵌字幕失败 video=%s error=%s", video_path.name, exc)
            return []

        tracks: List[Dict[str, Any]] = []
        for stream in payload.get("streams") or []:
            if not isinstance(stream, dict):
                continue
            disposition = stream.get("disposition") if isinstance(stream.get("disposition"), dict) else {}
            if disposition.get("forced"):
                continue
            tags = stream.get("tags") if isinstance(stream.get("tags"), dict) else {}
            codec = self._normalize_text(stream.get("codec_name")).lower()
            language = self._normalize_text(tags.get("language"))
            title = self._normalize_text(tags.get("title"))
            usable = self.embedded_subtitle_track_is_usable(codec, title, disposition)
            if not usable:
                suffix = "und"
            else:
                suffix = self.embedded_subtitle_language_suffix(language, title)
                if suffix == "und":
                    sampled_suffix = self.embedded_subtitle_sample_language_suffix(
                        video_path,
                        stream.get("index"),
                        codec,
                    )
                    if self._language_suffix_is_chinese(sampled_suffix):
                        suffix = sampled_suffix
            is_chinese = usable and self._language_suffix_is_chinese(suffix)
            tracks.append(
                {
                    "index": stream.get("index"),
                    "codec": codec,
                    "language": language,
                    "title": title,
                    "language_suffix": suffix,
                    "is_chinese": is_chinese,
                }
            )
        if cache_key:
            self._embedded_probe_cache[cache_key] = [dict(item) for item in tracks]
            self._embedded_probe_cache.move_to_end(cache_key)
            while len(self._embedded_probe_cache) > self._embedded_probe_cache_max_size:
                self._embedded_probe_cache.popitem(last=False)
        return tracks

    def embedded_subtitle_language_suffix(self, language: Any, title: Any = "") -> str:
        language_text = self._normalize_text(language).strip().lower()
        title_text = self._normalize_text(title).strip().lower()
        normalized_language = self._normalize_language_suffix(language_text)
        if normalized_language.startswith("zh-hans"):
            return "chi"
        if normalized_language.startswith("zh-hant"):
            return "cht"
        if re.search(r"繁中|繁体|繁體|traditional|zh[-_ ]?hant|zh[-_ ]?tw", language_text):
            return "cht"
        if re.search(r"简中|简体|簡體|simplified|zh[-_ ]?hans|zh[-_ ]?cn", language_text):
            return "chi"
        if re.search(r"chinese|mandarin|cantonese|中文|汉语|漢語|普通话|普通話|粤语|粵語", language_text):
            return "chi"
        if normalized_language != "und":
            return normalized_language
        if not title_text:
            return "und"
        if re.search(r"繁中|繁体|繁體|traditional|zh[-_ ]?hant|zh[-_ ]?tw", title_text):
            return "cht"
        if re.search(r"简中|简体|簡體|simplified|zh[-_ ]?hans|zh[-_ ]?cn", title_text):
            return "chi"
        if re.search(r"中文字幕|中字|中文|汉语|漢語|普通话|普通話", title_text):
            return "chi"
        return "und"

    def embedded_subtitle_probe_cache_key(self, video_path: Path) -> str:
        try:
            stat = video_path.stat()
        except Exception:
            return ""
        return f"{video_path}|{stat.st_size}|{stat.st_mtime_ns}"

    def embedded_subtitle_track_is_usable(
        self,
        codec: Any,
        title: Any = "",
        disposition: Optional[Dict[str, Any]] = None,
    ) -> bool:
        codec_text = self._normalize_text(codec).lower()
        if codec_text in self._embedded_image_codecs:
            return False
        disposition = disposition if isinstance(disposition, dict) else {}
        if disposition.get("forced") or disposition.get("comment"):
            return False
        title_text = self._normalize_text(title).strip().lower()
        if not title_text:
            return True
        return not bool(
            re.search(
                r"forced|signs?|songs?|commentary|comment|sdh|closed captions?|"
                r"特效|歌词|注释|旁白|强制|強制",
                title_text,
            )
        )

    def embedded_subtitle_sample_language_suffix(self, video_path: Path, stream_index: Any, codec_name: Any) -> str:
        codec = self._normalize_text(codec_name).lower()
        if codec not in self._embedded_text_codecs:
            return "und"
        index = self._safe_int(stream_index, -1)
        if index < 0:
            return "und"
        try:
            completed = self._subprocess.run(
                [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-nostdin",
                    "-i",
                    str(video_path),
                    "-map",
                    f"0:{index}",
                    "-f",
                    "srt",
                    "-",
                ],
                stdout=self._subprocess.PIPE,
                stderr=self._subprocess.PIPE,
                check=True,
                timeout=8,
            )
        except Exception:
            return "und"
        if not completed.stdout:
            return "und"
        return self._detect_language_profile(f"embedded.{codec}.srt", completed.stdout[:20000]).get("suffix", "und")

    def remove_ext_marks(self, video_path: Path) -> None:
        for sub_file in video_path.parent.iterdir():
            if not sub_file.is_file():
                continue
            if sub_file.suffix.lower() not in self._subtitle_exts:
                continue
            if not sub_file.name.startswith(f"{video_path.stem}."):
                continue
            new_name = sub_file.name.replace(".default.", ".").replace(".forced.", ".")
            if new_name == sub_file.name:
                continue
            target = sub_file.with_name(new_name)
            if target.exists():
                target.unlink()
            sub_file.rename(target)

    def _is_stream_path(self, path: Any) -> bool:
        return is_stream_path(path, normalize_text=self._normalize_text, stream_exts=self._stream_exts)


class MediaTargetResolver:
    def __init__(
        self,
        *,
        settings_obj: Any,
        meta_info_path: Optional[Callable[[Path], Any]],
        stream_exts: Iterable[str],
        trust_transfer_history_paths: bool,
        normalize_text: NormalizeText,
        safe_int: SafeInt,
        hash_text: HashText,
        extract_episode_hint: EpisodeHint,
        subtitle_files_provider: SubtitleFilesForTarget,
        load_local_entries: Callable[..., List[Dict[str, Any]]],
        group_entries_as_media: Callable[[List[Dict[str, Any]], int], List[Dict[str, Any]]],
        tmdb_detail_for_media: Callable[[Dict[str, Any]], Dict[str, Any]],
        apply_tmdb_detail: Callable[[Dict[str, Any], Dict[str, Any]], None],
        target_entry_cache: TargetEntryCache,
    ) -> None:
        self._settings = settings_obj
        self._meta_info_path = meta_info_path
        self._stream_exts = set(stream_exts)
        self._trust_transfer_history_paths = trust_transfer_history_paths
        self._normalize_text = normalize_text
        self._safe_int = safe_int
        self._hash_text = hash_text
        self._extract_episode_hint = extract_episode_hint
        self._subtitle_files_provider = subtitle_files_provider
        self._load_local_entries = load_local_entries
        self._group_entries_as_media = group_entries_as_media
        self._tmdb_detail_for_media = tmdb_detail_for_media
        self._apply_tmdb_detail = apply_tmdb_detail
        self._target_entry_cache = target_entry_cache

    def media_type_text(self, value: Any) -> str:
        return media_type_text(value)

    def poster_url(self, poster_path: Any, prefix: str = "w500") -> str:
        return poster_url(
            poster_path,
            prefix,
            settings_obj=self._settings,
            normalize_text=self._normalize_text,
        )

    def history_type_text(self, value: Any) -> str:
        return history_type_text(value, normalize_text=self._normalize_text)

    def number_from_tag(self, value: Any) -> int:
        return number_from_tag(value, normalize_text=self._normalize_text, safe_int=self._safe_int)

    def is_local_video_path(self, storage: str, path: str) -> bool:
        return is_local_video_path(
            storage,
            path,
            normalize_text=self._normalize_text,
            settings_obj=self._settings,
            stream_exts=self._stream_exts,
            trust_transfer_history_paths=self._trust_transfer_history_paths,
        )

    def build_entry_from_history(self, history: Any) -> Optional[Dict[str, Any]]:
        if not getattr(history, "status", False):
            return None

        raw_fileitem = getattr(history, "dest_fileitem", None)
        fileitem = raw_fileitem if isinstance(raw_fileitem, dict) else {}
        storage = self._normalize_text(fileitem.get("storage") or getattr(history, "dest_storage", "")) or "local"
        path = self._normalize_text(fileitem.get("path") or getattr(history, "dest", ""))
        if not self.is_local_video_path(storage, path):
            return None

        file_path = Path(path)
        filename = self._normalize_text(fileitem.get("name")) or file_path.name
        basename = self._normalize_text(fileitem.get("basename")) or file_path.stem
        media_type = self.media_type_text(getattr(history, "type", ""))
        if not media_type:
            return None

        title = self._normalize_text(getattr(history, "title", ""))
        year = self._normalize_text(getattr(history, "year", ""))
        season = self.number_from_tag(getattr(history, "seasons", ""))
        episode = self.number_from_tag(getattr(history, "episodes", ""))
        if not season or not episode:
            try:
                meta = self._meta_info_path(file_path) if self._meta_info_path else None
                season = season or self._safe_int(
                    getattr(meta, "begin_season", None) or getattr(meta, "season", None),
                    0,
                )
                episode = episode or self._safe_int(
                    getattr(meta, "begin_episode", None) or getattr(meta, "episode", None),
                    0,
                )
            except Exception:
                pass
        episode_hint = self._extract_episode_hint(filename or basename)
        if episode_hint:
            season = season or episode_hint.get("season", 0)
            episode = episode or episode_hint.get("episode", 0)
        if media_type == "tv" and episode and not season:
            season = 1

        tmdb_id = self._safe_int(getattr(history, "tmdbid", 0), 0)
        douban_id = self._normalize_text(getattr(history, "doubanid", ""))
        media_key = self._hash_text(f"{media_type}|{tmdb_id}|{douban_id}|{title}|{year}")
        entry_id = self._hash_text(f"{storage}|{path}")
        if media_type == "tv":
            prefix = f"S{season:02d}E{episode:02d}" if season and episode else basename
            target_label = f"{prefix} · {filename}"
        else:
            target_label = filename or (f"{title} ({year})" if year else title)

        return {
            "id": entry_id,
            "media_key": media_key,
            "media_type": media_type,
            "title": title,
            "year": year,
            "tmdb_id": tmdb_id,
            "douban_id": douban_id,
            "poster_url": self.poster_url(getattr(history, "image", "")),
            "poster_thumb_url": self.poster_url(getattr(history, "image", ""), "w185"),
            "season": season,
            "episode": episode,
            "path": path,
            "basename": basename,
            "filename": filename,
            "storage": storage,
            "library_name": "MoviePilot 媒体库",
            "relative_path": path.replace("\\", "/"),
            "target_label": target_label,
            "writable": True,
            "date": self._normalize_text(getattr(history, "date", "")),
        }

    def transfer_event_paths(self, transferinfo: Any) -> List[str]:
        raw_paths = event_value(transferinfo, "file_list_new", default=[]) or []
        if isinstance(raw_paths, (str, Path)):
            raw_paths = [raw_paths]
        paths = [self._normalize_text(item) for item in raw_paths if self._normalize_text(item)]
        if not paths:
            target_path = self._normalize_text(event_value(transferinfo, "target_path", default=""))
            if target_path:
                paths = [target_path]
        result = []
        for path in paths:
            if self.is_local_video_path("local", path):
                result.append(path)
        return result

    def entries_from_transfer_event(self, event_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        meta = event_data.get("meta") if isinstance(event_data, dict) else None
        mediainfo = event_data.get("mediainfo") if isinstance(event_data, dict) else None
        transferinfo = event_data.get("transferinfo") if isinstance(event_data, dict) else None
        paths = self.transfer_event_paths(transferinfo)
        if not paths:
            return []

        media_type = self.media_type_text(event_value(mediainfo, "type", default=""))
        title = self._normalize_text(
            event_value(mediainfo, "title", "name", default="")
            or event_value(meta, "name", "title", default="")
        )
        year = self._normalize_text(event_value(mediainfo, "year", "release_year", default=""))
        tmdb_id = self._safe_int(event_value(mediainfo, "tmdb_id", "tmdbid", default=0), 0)
        douban_id = self._normalize_text(event_value(mediainfo, "douban_id", "doubanid", default=""))
        season = self._safe_int(
            event_value(meta, "begin_season", "season", default=0)
            or event_value(mediainfo, "season", default=0),
            0,
        )
        episode = self._safe_int(
            event_value(meta, "begin_episode", "episode", default=0)
            or event_value(mediainfo, "episode", default=0),
            0,
        )
        episode_list = event_value(meta, "episode_list", default=[]) or []
        if not episode and isinstance(episode_list, list) and len(episode_list) == 1:
            episode = self._safe_int(episode_list[0], 0)
        if not media_type:
            media_type = "tv" if season or episode else "movie"

        entries: List[Dict[str, Any]] = []
        for path in paths:
            video_path = Path(path)
            basename = video_path.stem
            filename = video_path.name
            hint = self._extract_episode_hint(filename) or {}
            item_season = season or self._safe_int(hint.get("season"), 0)
            item_episode = episode or self._safe_int(hint.get("episode"), 0)
            item_title = title or basename
            media_key = self._hash_text(f"{media_type}|{tmdb_id}|{douban_id}|{item_title}|{year}")
            target_label = (
                f"S{item_season:02d}E{item_episode:02d} · {filename}"
                if media_type == "tv" and item_season and item_episode
                else filename
            )
            entries.append(
                {
                    "id": self._hash_text(f"local|{path}"),
                    "media_key": media_key,
                    "media_type": media_type,
                    "title": item_title,
                    "year": year,
                    "tmdb_id": tmdb_id,
                    "douban_id": douban_id,
                    "poster_url": self.poster_url(event_value(mediainfo, "poster_path", "image", default="")),
                    "poster_thumb_url": self.poster_url(
                        event_value(mediainfo, "poster_path", "image", default=""),
                        "w185",
                    ),
                    "season": item_season,
                    "episode": item_episode,
                    "path": path,
                    "basename": basename,
                    "filename": filename,
                    "storage": "local",
                    "library_name": "MoviePilot 入库事件",
                    "relative_path": path.replace("\\", "/"),
                    "target_label": target_label,
                    "writable": True,
                    "date": datetime.now().isoformat(timespec="seconds"),
                }
            )
        return entries

    def merge_seasons(self, entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seasons: Dict[int, Dict[str, Any]] = {}
        for entry in entries:
            season = self._safe_int(entry.get("season"), 0)
            episode = self._safe_int(entry.get("episode"), 0)
            if not season:
                continue
            item = seasons.setdefault(
                season,
                {
                    "season": season,
                    "name": f"第 {season} 季",
                    "episode_count": 0,
                    "poster_url": "",
                    "local_count": 0,
                    "episodes": [],
                    "available": False,
                },
            )
            item["local_count"] += 1
            item["available"] = True
            if episode and episode not in item["episodes"]:
                item["episodes"].append(episode)

        result = list(seasons.values())
        for item in result:
            item["episodes"] = sorted(item.get("episodes") or [])
            item["episode_count"] = len(item["episodes"])
        result.sort(key=lambda item: item.get("season", 0))
        return result

    def targets_for_media(
        self,
        media_type: str,
        tmdb_id: Any = None,
        douban_id: Any = None,
        title: str = "",
        year: str = "",
        season: Any = None,
    ) -> Dict[str, Any]:
        clean_type = self.media_type_text(media_type)
        clean_tmdb_id = self._safe_int(tmdb_id, 0)
        clean_title = self._normalize_text(title)
        clean_year = self._normalize_text(year)
        clean_douban_id = self._normalize_text(douban_id)

        entries = []
        seen_paths = set()
        for entry in self._load_local_entries(allow_stale=True):
            if clean_type and entry.get("media_type") != clean_type:
                continue
            if clean_tmdb_id and self._safe_int(entry.get("tmdb_id"), 0) != clean_tmdb_id:
                continue
            if clean_douban_id and self._normalize_text(entry.get("douban_id")) != clean_douban_id:
                continue
            if not clean_tmdb_id and not clean_douban_id and clean_title and entry.get("title") != clean_title:
                continue
            if clean_year and entry.get("year") != clean_year:
                continue
            if entry["path"] not in seen_paths:
                seen_paths.add(entry["path"])
                entries.append(entry)

        entries.sort(key=lambda item: (item.get("season", 0), item.get("episode", 0), item.get("filename", "")))
        media_groups = self._group_entries_as_media(entries, 1)
        media = media_groups[0] if media_groups else {
            "id": self._hash_text(f"{clean_type}|{clean_tmdb_id}|{douban_id}|{clean_title}|{clean_year}"),
            "media_id": "",
            "media_type": clean_type,
            "title": clean_title,
            "year": clean_year,
            "tmdb_id": clean_tmdb_id,
            "douban_id": self._normalize_text(douban_id),
            "poster_url": "",
            "poster_thumb_url": "",
            "local_count": 0,
            "season_count": 0,
        }
        tmdb_detail = self._tmdb_detail_for_media(media)
        if tmdb_detail:
            self._apply_tmdb_detail(media, tmdb_detail)
        seasons = self.merge_seasons(entries) if media.get("media_type") == "tv" else []

        season_value = self._normalize_text(season)
        selected_season: Any = "all"
        if media.get("media_type") == "tv" and season_value not in {"", "all", "0"}:
            selected_season = self._safe_int(season_value, 0) or "all"

        visible_entries = entries
        if media.get("media_type") == "tv" and selected_season != "all":
            visible_entries = [entry for entry in entries if self._safe_int(entry.get("season"), 0) == selected_season]

        self._target_entry_cache.remember(visible_entries)
        targets = [self.target_from_entry(entry) for entry in visible_entries]
        if tmdb_detail:
            for target in targets:
                self._apply_tmdb_detail(target, tmdb_detail)

        return {
            "media": media,
            "seasons": seasons,
            "selected_season": selected_season,
            "targets": targets,
            "target_count": len(visible_entries),
            "all_target_count": len(entries),
        }

    def is_stream_path(self, path: Any) -> bool:
        return is_stream_path(path, normalize_text=self._normalize_text, stream_exts=self._stream_exts)

    def target_from_entry(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        subtitles = self._subtitle_files_provider(entry)
        path = self._normalize_text(entry.get("path"))
        return {
            "id": entry.get("id"),
            "label": entry.get("target_label"),
            "basename": entry.get("basename"),
            "path": path,
            "media_type": entry.get("media_type"),
            "title": entry.get("title"),
            "tmdb_id": entry.get("tmdb_id"),
            "douban_id": entry.get("douban_id"),
            "season": entry.get("season", 0),
            "episode": entry.get("episode", 0),
            "year": entry.get("year", ""),
            "library_name": entry.get("library_name"),
            "relative_path": entry.get("relative_path"),
            "original_language": entry.get("original_language"),
            "origin_country": entry.get("origin_country"),
            "production_countries": entry.get("production_countries"),
            "original_title": entry.get("original_title"),
            "original_name": entry.get("original_name"),
            "en_title": entry.get("en_title"),
            "tmdb_aliases": entry.get("tmdb_aliases"),
            "storage": entry.get("storage", "local"),
            "writable": entry.get("writable", True),
            "is_stream": self.is_stream_path(path),
            "has_subtitle": bool(subtitles),
            "subtitle_count": len(subtitles),
            "subtitles": subtitles,
        }


class LocalMediaCatalog:
    def __init__(
        self,
        owner: Any,
        *,
        transfer_history: Any,
        http_exception: Any,
        logger: Any,
        target_entry_cache: TargetEntryCache,
        threading_module: Any = None,
    ) -> None:
        self._owner = owner
        self._transfer_history = transfer_history
        self._http_exception = http_exception
        self._logger = logger
        self._target_entry_cache = target_entry_cache
        self._threading = threading_module

    def filter_existing_local_entries(self, entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        owner = self._owner
        filtered = [entry for entry in entries if isinstance(entry, dict) and owner._entry_path_is_valid(entry)]
        dropped = len(entries or []) - len(filtered)
        if dropped:
            self._logger.info("[SubtitleManualUpload] 已剔除失效本地视频目标 count=%s", dropped)
        return filtered

    def prune_local_entries_cache(self) -> None:
        owner = self._owner
        cache = owner._local_entries_cache or {}
        entries = [entry for entry in cache.get("entries") or [] if isinstance(entry, dict)]
        if not entries:
            return
        filtered = self.filter_existing_local_entries(entries)
        if len(filtered) == len(entries):
            return
        media_count = len({entry.get("media_key") for entry in filtered if entry.get("media_key")})
        owner._local_entries_cache = {
            **cache,
            "entries": filtered,
            "media_count": media_count,
            "persisted": False,
        }
        self._target_entry_cache.prune(owner._entry_path_is_valid)
        self.reset_media_index_cache()
        owner._invalidate_match_history_cache()
        self.persist_local_cache()

    def merge_local_entries_cache(self, entries: List[Dict[str, Any]]) -> None:
        owner = self._owner
        if not entries:
            return
        entries = self.filter_existing_local_entries(entries)
        if not entries:
            return
        cache = owner._local_entries_cache or {}
        existing = self.filter_existing_local_entries(
            [item for item in cache.get("entries") or [] if isinstance(item, dict)]
        )
        by_path = {entry.get("path"): entry for entry in entries if entry.get("path")}
        merged = list(entries)
        for entry in existing:
            if entry.get("path") not in by_path:
                merged.append(entry)
            if len(merged) >= owner._cache_max_entries:
                break
        media_count = len({entry.get("media_key") for entry in merged if entry.get("media_key")})
        owner._local_entries_cache = {
            "loaded_at": datetime.now(),
            "entries": merged[: owner._cache_max_entries],
            "media_count": media_count,
            "persisted": False,
        }
        self._target_entry_cache.remember(entries)
        self.reset_media_index_cache()
        owner._invalidate_match_history_cache()
        self.persist_local_cache()

    def local_cache_file(self) -> Path:
        return self._owner.get_data_path() / "local_entries_cache.json"

    def persist_local_cache(self) -> None:
        owner = self._owner
        cache = owner._local_entries_cache or {}
        loaded_at = owner._cache_loaded_at(cache.get("loaded_at"))
        payload = {
            "loaded_at": loaded_at.isoformat(timespec="seconds") if loaded_at else "",
            "entries": cache.get("entries") or [],
            "media_count": int(cache.get("media_count") or 0),
        }
        try:
            cache_file = self.local_cache_file()
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        except Exception as exc:
            self._logger.warning("[SubtitleManualUpload] 写入本地资源持久化缓存失败: %s", exc)

    def restore_persisted_local_cache(self) -> bool:
        owner = self._owner
        try:
            cache_file = self.local_cache_file()
            if not cache_file.exists():
                return False
            payload = json.loads(cache_file.read_text(encoding="utf-8"))
        except Exception as exc:
            self._logger.warning("[SubtitleManualUpload] 读取本地资源持久化缓存失败: %s", exc)
            return False
        entries = payload.get("entries") if isinstance(payload, dict) else []
        loaded_at = owner._cache_loaded_at(payload.get("loaded_at")) if isinstance(payload, dict) else None
        if not loaded_at or not isinstance(entries, list):
            return False
        valid_entries = self.filter_existing_local_entries([entry for entry in entries if isinstance(entry, dict)])
        media_count = len({entry.get("media_key") for entry in valid_entries if entry.get("media_key")})
        owner._local_entries_cache = {
            "loaded_at": loaded_at,
            "entries": valid_entries,
            "media_count": media_count,
            "persisted": True,
        }
        self._target_entry_cache.remember(owner._local_entries_cache["entries"])
        self.reset_media_index_cache()
        self._logger.info(
            "[SubtitleManualUpload] 已恢复本地资源持久化缓存 entries=%s medias=%s",
            len(owner._local_entries_cache["entries"]),
            media_count,
        )
        return True

    def load_local_entries(self, *, force: bool = False, allow_stale: bool = False) -> List[Dict[str, Any]]:
        owner = self._owner
        self.prune_local_entries_cache()
        cache = owner._local_entries_cache or {}
        loaded_at = owner._cache_loaded_at(cache.get("loaded_at"))
        now = datetime.now()
        if not force and loaded_at and (now - loaded_at).total_seconds() < owner._cache_ttl_seconds:
            return list(cache.get("entries") or [])
        if not force and not loaded_at and self.restore_persisted_local_cache():
            cache = owner._local_entries_cache or {}
            loaded_at = owner._cache_loaded_at(cache.get("loaded_at"))
            if loaded_at and (now - loaded_at).total_seconds() < owner._cache_ttl_seconds:
                return list(cache.get("entries") or [])
        if not force and allow_stale and cache.get("entries"):
            owner._start_background_cache_refresh()
            return list(cache.get("entries") or [])

        try:
            histories = self._transfer_history.list_by_page(
                db=None,
                page=1,
                count=owner._cache_max_entries,
                status=True,
            ) or []
        except Exception as exc:
            raise self._http_exception(status_code=500, detail=f"读取 MoviePilot 本地整理记录失败: {exc}") from exc

        entries: List[Dict[str, Any]] = []
        seen_paths = set()
        for history in histories:
            entry = owner._build_entry_from_history(history)
            if not entry:
                continue
            if not owner._entry_path_is_valid(entry):
                continue
            path = entry.get("path")
            if path in seen_paths:
                continue
            seen_paths.add(path)
            entries.append(entry)
            if len(entries) >= owner._cache_max_entries:
                break

        media_count = len({entry.get("media_key") for entry in entries if entry.get("media_key")})
        owner._local_entries_cache = {
            "loaded_at": now,
            "entries": entries,
            "media_count": media_count,
            "persisted": False,
        }
        self._target_entry_cache.remember(entries)
        self.reset_media_index_cache()
        owner._invalidate_match_history_cache()
        self.persist_local_cache()
        self._logger.info(
            "[SubtitleManualUpload] 本地资源缓存已刷新 entries=%s medias=%s",
            len(entries),
            media_count,
        )
        return list(entries)

    def start_background_cache_refresh(self) -> None:
        owner = self._owner
        if owner._cache_refreshing:
            return
        owner._cache_refreshing = True
        owner._cache_refresh_started_at = datetime.now().isoformat(timespec="seconds")
        owner._cache_refresh_completed_at = ""
        owner._cache_refresh_error = ""

        def worker():
            try:
                self.load_local_entries(force=True)
                owner._cache_refresh_completed_at = datetime.now().isoformat(timespec="seconds")
                owner._cache_refresh_error = ""
            except Exception as exc:
                owner._cache_refresh_error = str(exc)
                self._logger.warning("[SubtitleManualUpload] 后台刷新本地资源缓存失败: %s", exc)
            finally:
                owner._cache_refreshing = False

        self._threading.Thread(
            target=worker,
            name="SubtitleManualUploadCacheRefresh",
            daemon=True,
        ).start()

    def refresh_local_cache(self) -> List[Dict[str, Any]]:
        owner = self._owner
        self._target_entry_cache.clear()
        self.reset_media_index_cache()
        owner._invalidate_match_history_cache()
        owner._local_entries_cache = {"loaded_at": None, "entries": [], "media_count": 0, "persisted": False}
        return self.load_local_entries(force=True)

    def cache_status(self) -> Dict[str, Any]:
        owner = self._owner
        cache = owner._local_entries_cache or {}
        loaded_at = owner._cache_loaded_at(cache.get("loaded_at"))
        expires_in = 0
        stale = False
        if loaded_at:
            age = (datetime.now() - loaded_at).total_seconds()
            expires_in = max(0, int(owner._cache_ttl_seconds - age))
            stale = age >= owner._cache_ttl_seconds
        return {
            "ready": bool(loaded_at),
            "persisted": bool(cache.get("persisted")),
            "stale": stale,
            "refreshing": bool(owner._cache_refreshing),
            "refresh_started_at": owner._cache_refresh_started_at,
            "refresh_completed_at": owner._cache_refresh_completed_at,
            "refresh_error": owner._cache_refresh_error,
            "trust_transfer_history_paths": bool(owner._trust_transfer_history_paths),
            "ttl_seconds": owner._cache_ttl_seconds,
            "expires_in": expires_in,
            "updated_at": loaded_at.isoformat(timespec="seconds") if loaded_at else "",
            "entry_count": len(cache.get("entries") or []),
            "media_count": int(cache.get("media_count") or 0),
            "media_index_count": len(owner._media_index_cache or {}),
            "target_cache_count": self._target_entry_cache.count(),
            "max_entries": owner._cache_max_entries,
        }

    def reset_media_index_cache(self) -> None:
        self._owner._media_index_cache = OrderedDict()

    def media_index_cache_key(self, keyword: str, media_type: str) -> str:
        owner = self._owner
        clean_keyword = owner._normalize_text(keyword).lower()
        expected_type = owner._media_type_text(media_type) or "all"
        return f"{expected_type}\0{clean_keyword}"

    def media_index_cache_get(self, key: str, entries: List[Dict[str, Any]]) -> Optional[List[Dict[str, Any]]]:
        owner = self._owner
        cache = owner._media_index_cache or OrderedDict()
        item = cache.get(key)
        if not item:
            return None
        loaded_at = owner._cache_loaded_at((owner._local_entries_cache or {}).get("loaded_at"))
        cached_loaded_at = owner._cache_loaded_at(item.get("loaded_at"))
        if cached_loaded_at != loaded_at or int(item.get("entry_count") or 0) != len(entries):
            cache.pop(key, None)
            return None
        cache.move_to_end(key)
        return [dict(media) for media in item.get("medias") or [] if isinstance(media, dict)]

    def media_index_cache_set(self, key: str, entries: List[Dict[str, Any]], medias: List[Dict[str, Any]]) -> None:
        owner = self._owner
        cache = owner._media_index_cache or OrderedDict()
        cache[key] = {
            "loaded_at": (owner._local_entries_cache or {}).get("loaded_at"),
            "entry_count": len(entries),
            "medias": [dict(media) for media in medias],
        }
        cache.move_to_end(key)
        while len(cache) > owner._media_index_cache_max_keys:
            cache.popitem(last=False)
        owner._media_index_cache = cache

    async def search_media_candidates(
        self,
        keyword: str,
        media_type: str,
        limit: int,
        offset: int = 0,
    ) -> Tuple[List[Dict[str, Any]], int]:
        owner = self._owner
        clean_keyword = owner._normalize_text(keyword)
        expected_type = owner._media_type_text(media_type)
        all_entries = self.load_local_entries(allow_stale=True)
        cache_key = self.media_index_cache_key(clean_keyword, media_type)
        all_candidates = self.media_index_cache_get(cache_key, all_entries)
        if all_candidates is None:
            entries: List[Dict[str, Any]] = []
            for entry in all_entries:
                if expected_type and entry.get("media_type") != expected_type:
                    continue
                if not owner._entry_matches_keyword(entry, clean_keyword):
                    continue
                entries.append(entry)
            all_candidates = owner._group_entries_as_media(entries, 0)
            self.media_index_cache_set(cache_key, all_entries, all_candidates)
        total = len(all_candidates)
        candidates = all_candidates[offset: offset + limit]
        return candidates, total

    def group_entries_as_media(self, entries: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
        owner = self._owner
        groups: Dict[str, Dict[str, Any]] = {}
        for entry in entries:
            key = entry["media_key"]
            group = groups.setdefault(
                key,
                {
                    "id": key,
                    "media_id": key,
                    "media_type": entry.get("media_type"),
                    "title": entry.get("title"),
                    "en_title": "",
                    "year": entry.get("year"),
                    "tmdb_id": entry.get("tmdb_id"),
                    "douban_id": entry.get("douban_id"),
                    "poster_url": entry.get("poster_url"),
                    "poster_thumb_url": entry.get("poster_thumb_url") or owner._poster_url(entry.get("poster_url"), "w185"),
                    "backdrop_url": "",
                    "overview": "",
                    "vote_average": 0,
                    "local_count": 0,
                    "season_count": 0,
                    "latest_at": entry.get("date", ""),
                    "_entries": [],
                },
            )
            group["_entries"].append(entry)
            group["local_count"] += 1
            if entry.get("poster_url") and not group.get("poster_url"):
                group["poster_url"] = entry["poster_url"]
            if entry.get("poster_thumb_url") and not group.get("poster_thumb_url"):
                group["poster_thumb_url"] = entry["poster_thumb_url"]
            if entry.get("date") and entry["date"] > group.get("latest_at", ""):
                group["latest_at"] = entry["date"]

        result = []
        for group in groups.values():
            seasons = owner._merge_seasons(group.pop("_entries"))
            group["seasons"] = seasons
            group["season_count"] = len(seasons)
            result.append(group)
        result.sort(key=lambda item: (item.get("latest_at", ""), item.get("title", "")), reverse=True)
        return result[:limit] if limit else result

    def resolve_targets(self, target_ids: Iterable[str]) -> Dict[str, Dict[str, Any]]:
        owner = self._owner
        target_id_list = [owner._normalize_text(item) for item in target_ids if owner._normalize_text(item)]
        target_id_set = set(target_id_list)
        result: Dict[str, Dict[str, Any]] = {}
        for target_id in target_id_list:
            entry = self._target_entry_cache.get(target_id)
            if entry and owner._entry_path_is_valid(entry):
                result[target_id] = entry
            elif entry:
                self._target_entry_cache.discard(target_id)
        missing_ids = target_id_set - set(result.keys())
        if not missing_ids:
            return result

        self._logger.info(
            "[SubtitleManualUpload] 目标缓存未命中，回查本地整理记录 target_ids=%s missing=%s",
            owner._brief_ids(target_id_list),
            len(missing_ids),
        )

        def take_matches(source_entries: List[Dict[str, Any]]) -> None:
            for entry in source_entries:
                target_id = owner._normalize_text(entry.get("id"))
                if target_id not in missing_ids:
                    continue
                self._target_entry_cache.remember([entry])
                result[target_id] = entry
                missing_ids.remove(target_id)
                if not missing_ids:
                    break

        try:
            take_matches(self.load_local_entries(allow_stale=True))
            if missing_ids:
                take_matches(self.load_local_entries(force=True))
        except Exception as exc:
            self._logger.error("[SubtitleManualUpload] 回查本地整理记录失败: %s", exc)
            return result

        if missing_ids:
            self._logger.warning(
                "[SubtitleManualUpload] 仍有目标无法解析 target_ids=%s missing=%s",
                owner._brief_ids(target_id_list),
                len(missing_ids),
            )
        return result

    def cached_unlocked_targets(self, locked_ids: set) -> List[Dict[str, Any]]:
        owner = self._owner
        entries: List[Dict[str, Any]] = []
        for target_id, entry in self._target_entry_cache.items():
            if owner._normalize_text(target_id) in locked_ids:
                continue
            if owner._entry_path_is_valid(entry):
                entries.append(entry)
        return entries
